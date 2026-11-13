"""离线方案选择：按时间与过程隔离的嵌套交叉验证。

设计原则（与值班组约定一致，仅做离线分析，不连接真实发布系统）：

1. 持续过程（event）是最小隔离单位。一次跨夜跨区过程的全部切片只能整体
   进入同一个 fold，不能一半挑方案、一半做检验。
2. 标签只能在 ``label_known_at`` 之后使用；在分析时点 ``as_of`` 仍未确认的
   过程属于未决标签，不能冒充已知事实，既不进入验证 fold，也不计入命中或
   漏报，只作为未决证据单独报告。
3. fold 按时间前向扩展（expanding window）。每个外层 fold 的训练集只允许
   使用在测试集首个过程起报前就已确认标签的过程；检验只在从未参与任何
   调参的外层测试过程上汇报，禁止用最终检验窗口调好阈值再报告其成绩。
4. 训练内得到的归一化与分区规则随候选冻结（frozen_artifacts）；未来数据
   只能用于之后的版本。
5. 运营约束是硬性护栏：当班复核容量 capacity、可接受漏报上限 miss_budget、
   期望提前量 min_lead_hours。没有候选能被证据支持时结论必须是 hold。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

# 起报窗口：事件开始前多少小时内、且在事件结束前的同区提醒才计入该事件。
# 样例分数窗口为事件前 12 小时，默认取 12；输入可覆盖。
DEFAULT_HORIZON_HOURS = 12.0
# 外层 fold 最少训练过程数与测试过程数。
MIN_TRAIN_EVENTS = 6
OUTER_TEST_SIZE = 3
# 内层出参的最少训练过程数。
INNER_MIN_TRAIN = 4
# 可发布所需的有效样本下限，防止在极少数过程上硬下结论。
MIN_EVALUABLE_EVENTS = 6
MIN_EVALUABLE_POSITIVES = 4
# 分区出参时，单区正样本不足该值则向全区统一阈值收缩，避免小样本分区过拟合。
MIN_ZONE_POSITIVES = 3
# 阈值网格（风险分位于 0~1）。
THRESHOLD_GRID = [round(0.35 + 0.025 * i, 4) for i in range(26)]  # 0.35 .. 0.975


class SelectionError(ValueError):
    """输入不满足方案选择所需的完整性约束。"""


def parse_ts(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _finite(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise SelectionError("risk score must be finite")
    return result


@dataclass(frozen=True, slots=True)
class ScoreRow:
    score_id: str
    event_id: str
    zone: str
    at: datetime
    known_at: datetime
    risk: float
    shift_id: str


@dataclass(frozen=True, slots=True)
class Event:
    event_id: str
    zones: tuple[str, ...]
    start: datetime
    end: datetime
    label_known_at: datetime
    outcome: bool
    revision: int


@dataclass(frozen=True, slots=True)
class Alert:
    event_id: str
    zone: str
    at: datetime
    shift_id: str
    risk: float
    candidate_id: str
    source: str  # registered | fitted

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "zone": self.zone,
            "at": iso(self.at),
            "shift_id": self.shift_id,
            "risk": round(self.risk, 6),
            "candidate_id": self.candidate_id,
            "source": self.source,
        }


@dataclass(slots=True)
class CandidateConfig:
    candidate_id: str
    kind: str  # uniform | zonal
    cooldown_hours: float
    uniform_threshold: float | None = None
    zone_thresholds: dict[str, float] | None = None
    source: str = "registered"
    parent_id: str | None = None
    frozen_artifacts: dict[str, Any] = field(default_factory=dict)

    def threshold_for(self, zone: str) -> float:
        if self.kind == "uniform":
            return float(self.uniform_threshold)
        thresholds = self.zone_thresholds or {}
        if zone not in thresholds:
            # 未见过的分区回退到冻结的全局阈值，保证未来数据可用同一规则。
            return float(self.frozen_artifacts.get("fallback_threshold", 0.65))
        return float(thresholds[zone])

    def spec(self) -> dict[str, Any]:
        if self.kind == "uniform":
            params = {"threshold": round(float(self.uniform_threshold), 6)}
        else:
            params = {"thresholds": {z: round(v, 6) for z, v in (self.zone_thresholds or {}).items()},
                      "fallback_threshold": round(float(self.frozen_artifacts.get("fallback_threshold", 0.65)), 6)}
        return {
            "candidate_id": self.candidate_id,
            "kind": self.kind,
            "cooldown_hours": self.cooldown_hours,
            "source": self.source,
            "parent_id": self.parent_id,
            "params": params,
            "frozen_artifacts": self.frozen_artifacts,
        }


def load_analysis(payload: Mapping[str, Any]) -> dict[str, Any]:
    """解析并校验输入，返回规范化后的分数、过程、候选与约束。"""
    if not isinstance(payload, Mapping):
        raise SelectionError("input payload must be an object")
    as_of_raw = payload.get("as_of")
    if not as_of_raw:
        raise SelectionError("as_of is required")
    as_of = parse_ts(as_of_raw)

    raw_events = payload.get("events")
    raw_scores = payload.get("scores")
    if not isinstance(raw_events, list) or not raw_events:
        raise SelectionError("events must be a non-empty list")
    if not isinstance(raw_scores, list) or not raw_scores:
        raise SelectionError("scores must be a non-empty list")

    events: dict[str, Event] = {}
    for item in raw_events:
        try:
            event = Event(
                event_id=str(item["event_id"]),
                zones=tuple(str(z) for z in item["zones"]),
                start=parse_ts(item["start"]),
                end=parse_ts(item["end"]),
                label_known_at=parse_ts(item["label_known_at"]),
                outcome=bool(item["outcome"]),
                revision=int(item.get("revision", 1)),
            )
        except KeyError as exc:
            raise SelectionError(f"event missing field: {exc.args[0]}") from None
        if event.end <= event.start:
            raise SelectionError(f"event {event.event_id} end must be after start")
        if not event.zones:
            raise SelectionError(f"event {event.event_id} has no zones")
        if event.event_id in events:
            raise SelectionError(f"duplicate event_id {event.event_id}")
        events[event.event_id] = event

    scores: list[ScoreRow] = []
    seen_score_ids: set[str] = set()
    for item in raw_scores:
        try:
            row = ScoreRow(
                score_id=str(item["score_id"]),
                event_id=str(item["event_id"]),
                zone=str(item["zone"]),
                at=parse_ts(item["at"]),
                known_at=parse_ts(item["known_at"]),
                risk=_finite(item["risk"]),
                shift_id=str(item["shift_id"]),
            )
        except KeyError as exc:
            raise SelectionError(f"score missing field: {exc.args[0]}") from None
        if row.score_id in seen_score_ids:
            raise SelectionError(f"duplicate score_id {row.score_id}")
        seen_score_ids.add(row.score_id)
        if row.event_id not in events:
            raise SelectionError(f"score {row.score_id} references unknown event {row.event_id}")
        if row.known_at > as_of:
            raise SelectionError(
                f"score {row.score_id} known_at {iso(row.known_at)} is after as_of; 未来分数不能进入离线分析"
            )
        if not 0.0 <= row.risk <= 1.0:
            raise SelectionError(f"score {row.score_id} risk outside [0,1]")
        scores.append(row)

    candidates = _load_candidates(payload.get("candidates"), events)
    try:
        capacity = int(_finite(payload.get("capacity")))
        miss_budget = _finite(payload.get("miss_budget"))
        min_lead_hours = _finite(payload.get("min_lead_hours"))
    except (TypeError, ValueError) as exc:
        raise SelectionError(f"operational constraint invalid: {exc}") from None
    if capacity < 1:
        raise SelectionError("capacity must be >= 1")
    if not 0.0 <= miss_budget <= 1.0:
        raise SelectionError("miss_budget must be within [0,1]")
    if min_lead_hours < 0:
        raise SelectionError("min_lead_hours must be >= 0")
    horizon_hours = _finite(payload.get("horizon_hours", DEFAULT_HORIZON_HOURS))
    if horizon_hours <= 0:
        raise SelectionError("horizon_hours must be positive")

    return {
        "as_of": as_of,
        "events": events,
        "scores": scores,
        "candidates": candidates,
        "capacity": capacity,
        "miss_budget": miss_budget,
        "min_lead_hours": min_lead_hours,
        "horizon_hours": horizon_hours,
        "seed": payload.get("seed"),
    }


def _load_candidates(raw: Any, events: Mapping[str, Event]) -> list[CandidateConfig]:
    if not isinstance(raw, list) or not raw:
        raise SelectionError("candidates must be a non-empty list")
    configs: list[CandidateConfig] = []
    seen: set[str] = set()
    for item in raw:
        cid = str(item.get("candidate_id", "")).strip()
        if not cid or cid in seen:
            raise SelectionError("candidate_id required and unique")
        seen.add(cid)
        kind = str(item.get("kind", ""))
        cooldown = _finite(item.get("cooldown_hours", 0))
        if cooldown < 0:
            raise SelectionError(f"candidate {cid} cooldown_hours must be >= 0")
        if kind == "uniform":
            configs.append(CandidateConfig(
                candidate_id=cid, kind=kind, cooldown_hours=cooldown,
                uniform_threshold=_finite(item["threshold"]),
            ))
        elif kind == "zonal":
            thresholds = {str(z): _finite(v) for z, v in (item.get("thresholds") or {}).items()}
            if not thresholds:
                raise SelectionError(f"zonal candidate {cid} requires thresholds")
            unknown = set(thresholds) - {z for e in events.values() for z in e.zones}
            if unknown:
                raise SelectionError(f"candidate {cid} thresholds reference unknown zones {sorted(unknown)}")
            configs.append(CandidateConfig(
                candidate_id=cid, kind=kind, cooldown_hours=cooldown,
                zone_thresholds=dict(thresholds),
                frozen_artifacts={"fallback_threshold": min(thresholds.values())},
            ))
        else:
            raise SelectionError(f"candidate {cid} has unsupported kind {kind}")
    return configs


# --------------------------------------------------------------------------- #
# 反事实回放：按信息时点逐时生成提醒，同区冷却，持续过程不拆成多个命中
# --------------------------------------------------------------------------- #

def replay_alerts(
    config: CandidateConfig,
    scores: Sequence[ScoreRow],
    candidate_id: str | None = None,
) -> list[Alert]:
    """对一个候选配置做离线反事实回放。

    只使用 ``known_at <= as_of`` 的分数（load 阶段已保证），按信息可用时间
    排序；同一 (event, zone) 内距上次提醒不足 cooldown 的高分不再提醒，从而
    控制重复提醒。冷却按分区独立计时。
    """
    cid = candidate_id or config.candidate_id
    ordered = sorted(scores, key=lambda r: (r.known_at, r.at, r.zone, r.score_id))
    last_alert: dict[tuple[str, str], datetime] = {}
    alerts: list[Alert] = []
    for row in ordered:
        threshold = config.threshold_for(row.zone)
        if row.risk < threshold:
            continue
        key = (row.event_id, row.zone)
        last = last_alert.get(key)
        if last is not None and (row.at - last).total_seconds() / 3600.0 < config.cooldown_hours:
            continue
        alerts.append(Alert(
            event_id=row.event_id, zone=row.zone, at=row.at, shift_id=row.shift_id,
            risk=row.risk, candidate_id=cid, source=config.source,
        ))
        last_alert[key] = row.at
    return alerts


def _match_window(event: Event, horizon_hours: float) -> tuple[datetime, datetime]:
    return event.start - timedelta(hours=horizon_hours), event.end


def shift_loads(alerts: Sequence[Alert]) -> dict[str, int]:
    loads: dict[str, int] = {}
    for alert in alerts:
        loads[alert.shift_id] = loads.get(alert.shift_id, 0) + 1
    return dict(sorted(loads.items()))


# --------------------------------------------------------------------------- #
# 时间与过程隔离的 fold 构建
# --------------------------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class Fold:
    fold_id: str
    train_event_ids: tuple[str, ...]
    test_event_ids: tuple[str, ...]
    embargo_ok: bool
    reason: str


def build_outer_folds(
    events: Mapping[str, Event],
    as_of: datetime,
    horizon_hours: float = DEFAULT_HORIZON_HOURS,
    min_train: int = MIN_TRAIN_EVENTS,
    test_size: int = OUTER_TEST_SIZE,
) -> tuple[list[Fold], list[str]]:
    """前向扩展 fold。返回 (folds, 未决过程ID)。

    只纳入 ``label_known_at <= as_of`` 的已决过程，按事件 start 排序。
    每个 fold 的测试集是连续的 ``test_size`` 个过程，训练集是其之前的全部
    已决过程。embargo 以测试集首个过程的开始时点为界：训练集标签必须在该
    时点之前确认（标签在对应事件结束之后才确认属正常业务情形）。起报时
    尚未确认的标签由 ``as_of`` 过滤与逐时 ``known_at`` 回放另行保证不被
    提前使用，二者共同防止标签穿越。
    """
    decided = sorted(
        (e for e in events.values() if e.label_known_at <= as_of),
        key=lambda e: (e.start, e.event_id),
    )
    pending = sorted(
        (e.event_id for e in events.values() if e.label_known_at > as_of),
        key=lambda eid: events[eid].start,
    )
    folds: list[Fold] = []
    index = min_train
    fold_no = 0
    # 每个外层 fold 固定取 test_size 个测试过程；剩余不足一个测试块的已决
    # 过程并入最后一个 fold 的测试集，确保所有已决过程都得到 OOF 检验，不
    # 允许把尾部过程悄悄丢弃后只报告成绩更好的窗口。
    while index < len(decided):
        train = decided[:index]
        remaining = len(decided) - index
        take = test_size if remaining >= test_size else remaining
        test = decided[index:index + take]
        latest_train_label = max(e.label_known_at for e in train)
        earliest_test_start = min(e.start for e in test)
        embargo_ok = latest_train_label <= earliest_test_start
        reason = (
            "训练集标签均在测试集首个过程开始之前确认"
            if embargo_ok
            else "训练集存在测试集开始后才确认的标签，embargo 不通过"
        )
        folds.append(Fold(
            fold_id=f"outer-{fold_no}",
            train_event_ids=tuple(e.event_id for e in train),
            test_event_ids=tuple(e.event_id for e in test),
            embargo_ok=embargo_ok,
            reason=reason,
        ))
        fold_no += 1
        index += take
    return folds, pending


def build_inner_splits(train_events: Sequence[Event], min_train: int = INNER_MIN_TRAIN) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    """内层前向验证，仅用于在训练集内部挑选阈值，绝不接触外层测试过程。"""
    ordered = sorted(train_events, key=lambda e: (e.start, e.event_id))
    splits: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    index = min_train
    if len(ordered) <= min_train:
        # 训练过程太少，无法再切内层，直接在全量训练集上按规则出参。
        return splits
    while index < len(ordered):
        inner_train = ordered[:index]
        inner_test = ordered[index:min(index + 2, len(ordered))]
        splits.append((tuple(e.event_id for e in inner_train), tuple(e.event_id for e in inner_test)))
        index += len(inner_test)
    return splits


# --------------------------------------------------------------------------- #
# 训练内出参：归一化/分区规则在此产生并冻结
# --------------------------------------------------------------------------- #

def _scores_for_events(scores: Sequence[ScoreRow], event_ids: Iterable[str]) -> list[ScoreRow]:
    wanted = set(event_ids)
    return [r for r in scores if r.event_id in wanted]


def _fit_uniform(
    scores: Sequence[ScoreRow],
    events: Mapping[str, Event],
    train_ids: Sequence[str],
    cooldown_hours: float,
    parent_id: str,
    candidate_id: str,
    constraints: Mapping[str, float] | None = None,
) -> CandidateConfig:
    """在训练过程上扫描阈值网格，按运营约束内的漏报/提醒量折优。

    若提供约束（capacity/miss_budget/min_lead_hours），则只在训练集上满足
    全部护栏的阈值中择优，避免用“几乎不提醒”的高阈值在测试集上伪装容量
    合规；没有任何阈值满足护栏时退回纯漏报/提醒量排序，并在冻结工件中标注
    ``guardrail_feasible=False``，交由外层护栏继续拦截。
    """
    train_events = [events[eid] for eid in train_ids]
    train_scores = _scores_for_events(scores, train_ids)
    positives = {e.event_id for e in train_events if e.outcome}
    scored: list[tuple[tuple[float, ...], float, dict[str, Any], bool]] = []
    for threshold in THRESHOLD_GRID:
        config = CandidateConfig(
            candidate_id=candidate_id, kind="uniform", cooldown_hours=cooldown_hours,
            uniform_threshold=threshold, source="fitted", parent_id=parent_id,
        )
        alerts = replay_alerts(config, train_scores)
        metrics = _aggregate(alerts, train_events)
        # 训练内目标：先保证不漏（漏报数最少），再减少提醒总量，再偏好高阈值
        # （高阈值提醒更少、对容量更友好）。
        key = (metrics["misses"], metrics["alerts"], -threshold)
        feasible = True
        if constraints is not None:
            guard = evaluate_guardrails(
                metrics,
                int(constraints["capacity"]),
                float(constraints["miss_budget"]),
                float(constraints["min_lead_hours"]),
            )
            feasible = guard["all_passed"]
        scored.append((key, threshold, metrics, feasible))
    feasible_rows = [row for row in scored if row[3]]
    chosen_pool = feasible_rows if feasible_rows else scored
    best_key, best_threshold, _, _ = min(chosen_pool, key=lambda row: row[0])
    # 归一化信息随候选冻结：训练分位数与正样本计数，供未来版本审计。
    risks = sorted(r.risk for r in train_scores)
    frozen = {
        "trained_on_event_ids": list(train_ids),
        "positive_event_count": len(positives),
        "score_quantiles": {
            "p50": round(_quantile(risks, 0.5), 6),
            "p90": round(_quantile(risks, 0.9), 6),
        },
        "fallback_threshold": round(best_threshold, 6),
        "grid": [THRESHOLD_GRID[0], THRESHOLD_GRID[-1]],
        "guardrail_feasible_in_training": bool(feasible_rows),
    }
    return CandidateConfig(
        candidate_id=candidate_id, kind="uniform", cooldown_hours=cooldown_hours,
        uniform_threshold=best_threshold, source="fitted", parent_id=parent_id,
        frozen_artifacts=frozen,
    )


def _fit_zonal(
    scores: Sequence[ScoreRow],
    events: Mapping[str, Event],
    train_ids: Sequence[str],
    cooldown_hours: float,
    parent_id: str,
    candidate_id: str,
    constraints: Mapping[str, float] | None = None,
) -> CandidateConfig:
    """分区阈值：每区在训练过程上独立寻优，小样本区向全区阈值收缩。"""
    train_events = [events[eid] for eid in train_ids]
    train_scores = _scores_for_events(scores, train_ids)
    zones = sorted({r.zone for r in train_scores})
    # 先求全区基准阈值（复用 uniform 寻优逻辑，但不产生新的 frozen 嵌套）。
    base = _fit_uniform(scores, events, train_ids, cooldown_hours, parent_id,
                        candidate_id + "-base", constraints)
    base_threshold = float(base.uniform_threshold)
    zone_thresholds: dict[str, float] = {}
    zone_artifacts: dict[str, Any] = {}
    for zone in zones:
        zone_positive_events = {
            e.event_id for e in train_events if e.outcome and zone in e.zones
        }
        zone_scores = [r for r in train_scores if r.zone == zone]
        if len(zone_positive_events) < MIN_ZONE_POSITIVES:
            # 小样本分区：向全区统一阈值收缩，避免过拟合。
            zone_thresholds[zone] = base_threshold
            zone_artifacts[zone] = {
                "positive_event_count": len(zone_positive_events),
                "shrunk_to_global": True,
                "threshold": round(base_threshold, 6),
            }
            continue
        rows: list[tuple[tuple[float, ...], float, bool]] = []
        zone_event_ids = {e.event_id for e in train_events if zone in e.zones}
        zone_events = [events[eid] for eid in zone_event_ids]
        for threshold in THRESHOLD_GRID:
            config = CandidateConfig(
                candidate_id=candidate_id, kind="uniform", cooldown_hours=cooldown_hours,
                uniform_threshold=threshold, source="fitted", parent_id=parent_id,
            )
            alerts = [a for a in replay_alerts(config, zone_scores) if a.zone == zone]
            metrics = _aggregate(alerts, zone_events)
            feasible = True
            if constraints is not None:
                guard = evaluate_guardrails(
                    metrics,
                    int(constraints["capacity"]),
                    float(constraints["miss_budget"]),
                    float(constraints["min_lead_hours"]),
                )
                feasible = guard["all_passed"]
            rows.append(((metrics["misses"], metrics["alerts"], -threshold), threshold, feasible))
        feasible_rows = [row for row in rows if row[2]]
        _, best_threshold, _ = min(feasible_rows or rows, key=lambda row: row[0])
        zone_thresholds[zone] = best_threshold
        zone_artifacts[zone] = {
            "positive_event_count": len(zone_positive_events),
            "shrunk_to_global": False,
            "threshold": round(best_threshold, 6),
        }
    frozen = {
        "trained_on_event_ids": list(train_ids),
        "min_zone_positives": MIN_ZONE_POSITIVES,
        "zone_rules": zone_artifacts,
        "fallback_threshold": round(base_threshold, 6),
        "normalization": base.frozen_artifacts.get("score_quantiles", {}),
        "guardrail_feasible_in_training": base.frozen_artifacts.get(
            "guardrail_feasible_in_training", True
        ),
    }
    return CandidateConfig(
        candidate_id=candidate_id, kind="zonal", cooldown_hours=cooldown_hours,
        zone_thresholds=zone_thresholds, source="fitted", parent_id=parent_id,
        frozen_artifacts=frozen,
    )


def _quantile(ordered_values: Sequence[float], fraction: float) -> float:
    if not ordered_values:
        return 0.0
    position = max(0.0, min(1.0, fraction)) * (len(ordered_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered_values) - 1)
    weight = position - lower
    return ordered_values[lower] * (1 - weight) + ordered_values[upper] * weight


def inner_tune(
    registered: CandidateConfig,
    scores: Sequence[ScoreRow],
    events: Mapping[str, Event],
    train_ids: Sequence[str],
    constraints: Mapping[str, float],
) -> CandidateConfig:
    """外层 fold 训练阶段：在内层验证约束下出参并冻结。"""
    candidate_id = registered.candidate_id + ":fit"
    if registered.kind == "uniform":
        return _fit_uniform(scores, events, train_ids, registered.cooldown_hours,
                            registered.candidate_id, candidate_id, constraints)
    return _fit_zonal(scores, events, train_ids, registered.cooldown_hours,
                      registered.candidate_id, candidate_id, constraints)


# --------------------------------------------------------------------------- #
# 指标聚合与护栏
# --------------------------------------------------------------------------- #

def _aggregate(
    alerts: Sequence[Alert],
    scoped_events: Sequence[Event],
) -> dict[str, Any]:
    """把提醒折算为事件级计量项（持续过程不拆成多个命中）。

    计量口径：
    - 事件命中 hit：outcome=true 的过程在其起报窗口内至少有一条提醒；同一
      过程只计一次命中，不因跨夜跨区切片重复计数。
    - 漏报 miss：outcome=true 的过程在窗口内无任何提醒。
    - 提前量 lead_hours：命中过程首条提醒相对事件 start 的小时数，报告中位
      数、最小值与观测数。
    - 重复提醒 repeat_alerts：命中过程各分区提醒总数减 1，即冷却后仍发生的
      再次提醒（值班组重点压降项）。
    - 误报 false_alarm：落在 outcome=false 过程上的提醒，分过程级与提醒级。
    - 空窗误报 gap_false_alarms：由 ``_evaluate_on_events`` 另行统计不落在
      任何过程起报窗口/影响区内的提醒。
    - 容量 max_shift_load：同一 shift_id 内的最大提醒数，对应当班复核能力。
    未决过程在进入本函数前已由 fold 构建与 as_of 过滤排除。
    """
    loads = shift_loads(alerts)
    scoped_ids = {e.event_id for e in scoped_events}
    scoped_alerts = [a for a in alerts if a.event_id in scoped_ids]
    hits = misses = false_alert_events = 0
    leads: list[float] = []
    repeat_alerts = 0
    alerts_on_positive = 0
    alerts_on_negative = 0
    by_event: dict[str, list[Alert]] = {}
    for alert in scoped_alerts:
        by_event.setdefault(alert.event_id, []).append(alert)
    for event in scoped_events:
        event_alerts = by_event.get(event.event_id, [])
        if event.outcome:
            if event_alerts:
                hits += 1
                alerts_on_positive += len(event_alerts)
                repeat_alerts += max(0, len(event_alerts) - 1)
                first = min(a.at for a in event_alerts)
                leads.append((event.start - first).total_seconds() / 3600.0)
            else:
                misses += 1
        elif event_alerts:
            false_alert_events += 1
            alerts_on_negative += len(event_alerts)
    positive_total = hits + misses
    decided_total = len(scoped_events)
    return {
        "events_scored": decided_total,
        "positive_events": positive_total,
        "negative_events": decided_total - positive_total,
        "hits": hits,
        "misses": misses,
        "miss_rate": round(misses / positive_total, 6) if positive_total else None,
        "hit_rate": round(hits / positive_total, 6) if positive_total else None,
        "false_alarm_events": false_alert_events,
        "alerts_on_positive_events": alerts_on_positive,
        "alerts_on_negative_events": alerts_on_negative,
        "repeat_alerts": repeat_alerts,
        "alerts": len(scoped_alerts),
        "max_shift_load": max(loads.values(), default=0),
        "shift_loads": loads,
        "median_lead_hours": round(_quantile(sorted(leads), 0.5), 3) if leads else None,
        "min_lead_hours": round(min(leads), 3) if leads else None,
        "lead_observations": len(leads),
    }


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> dict[str, float | None]:
    """Wilson 二项区间，用于在小样本上诚实表达命中率的不确定性。"""
    if trials <= 0:
        return {"lower": None, "upper": None, "point": None}
    phat = successes / trials
    denom = 1 + z * z / trials
    center = (phat + z * z / (2 * trials)) / denom
    margin = (z * math.sqrt(phat * (1 - phat) / trials + z * z / (4 * trials * trials))) / denom
    return {
        "point": round(phat, 6),
        "lower": round(max(0.0, center - margin), 6),
        "upper": round(min(1.0, center + margin), 6),
    }


def evaluate_guardrails(
    metrics: Mapping[str, Any],
    capacity: int,
    miss_budget: float,
    min_lead_hours: float,
) -> dict[str, Any]:
    """硬性运营护栏；任一不过，该候选不能仅凭点估计发布。"""
    checks = {
        "capacity": {
            "observed": metrics.get("max_shift_load", 0),
            "limit": capacity,
            "passed": metrics.get("max_shift_load", 0) <= capacity,
            "rule": "每班复核提醒数 max_shift_load <= capacity",
        },
        "miss_budget": {
            "observed": metrics.get("miss_rate"),
            "limit": miss_budget,
            "passed": (metrics.get("miss_rate") is not None and metrics["miss_rate"] <= miss_budget),
            "rule": "事件漏报率 miss_rate <= miss_budget",
        },
        "min_lead": {
            "observed": metrics.get("median_lead_hours"),
            "limit": min_lead_hours,
            "passed": (
                metrics.get("median_lead_hours") is not None
                and metrics["median_lead_hours"] >= min_lead_hours
            ),
            "rule": "命中事件提前量中位数 median_lead_hours >= min_lead_hours",
        },
    }
    return {"checks": checks, "all_passed": all(item["passed"] for item in checks.values())}


# --------------------------------------------------------------------------- #
# 顶层选择流程
# --------------------------------------------------------------------------- #

@dataclass(slots=True)
class CandidateEvaluation:
    candidate_id: str
    kind: str
    source: str
    parent_id: str | None
    spec: dict[str, Any]
    fold_metrics: list[dict[str, Any]]
    pooled: dict[str, Any]
    guardrails: dict[str, Any]
    eligible: bool
    eligibility_reasons: list[str]
    utility: float
    frozen_fold_configs: list[dict[str, Any]]


def _pool_fold_metrics(fold_metrics: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    hits = sum(m["hits"] for m in fold_metrics)
    misses = sum(m["misses"] for m in fold_metrics)
    positives = hits + misses
    negatives = sum(m["negative_events"] for m in fold_metrics)
    false_events = sum(m["false_alarm_events"] for m in fold_metrics)
    alerts_pos = sum(m["alerts_on_positive_events"] for m in fold_metrics)
    alerts_neg = sum(m["alerts_on_negative_events"] for m in fold_metrics)
    repeats = sum(m["repeat_alerts"] for m in fold_metrics)
    alerts = sum(m["alerts"] for m in fold_metrics)
    max_load = max((m["max_shift_load"] for m in fold_metrics), default=0)
    leads = [lv for m in fold_metrics for lv in m.get("lead_values", [])]
    events_scored = sum(m["events_scored"] for m in fold_metrics)
    return {
        "events_scored": events_scored,
        "positive_events": positives,
        "negative_events": negatives,
        "hits": hits,
        "misses": misses,
        "miss_rate": round(misses / positives, 6) if positives else None,
        "hit_rate": round(hits / positives, 6) if positives else None,
        "false_alarm_events": false_events,
        "alerts_on_positive_events": alerts_pos,
        "alerts_on_negative_events": alerts_neg,
        "repeat_alerts": repeats,
        "alerts": alerts,
        "max_shift_load": max_load,
        "median_lead_hours": round(_quantile(sorted(leads), 0.5), 3) if leads else None,
        "min_lead_hours": round(min(leads), 3) if leads else None,
        "lead_observations": len(leads),
        "hit_rate_wilson95": wilson_interval(hits, positives),
    }


def _utility(pooled: Mapping[str, Any]) -> float:
    """发布后运营视角的综合效用（仅在护栏通过的候选间比较）。

    漏报权重最高，其次重复提醒（值班组明确要求减少重复提醒），再次负过程
    误报与总体复核量。数值越小越优。
    """
    miss_rate = pooled["miss_rate"] or 0.0
    positives = pooled["positive_events"] or 0
    score = (
        miss_rate * 100.0
        + pooled["repeat_alerts"] * 2.0
        + pooled["false_alarm_events"] * 4.0
        + pooled["alerts_on_negative_events"] * 1.0
        + pooled["max_shift_load"] * 0.5
    )
    # 复杂模型惩罚：分区策略参数更多，同分时偏好统一策略，抑制过拟合。
    return round(score, 6)


def run_selection(analysis: Mapping[str, Any]) -> dict[str, Any]:
    events: Mapping[str, Event] = analysis["events"]
    scores: Sequence[ScoreRow] = analysis["scores"]
    registered: Sequence[CandidateConfig] = analysis["candidates"]
    as_of: datetime = analysis["as_of"]
    capacity = analysis["capacity"]
    miss_budget = analysis["miss_budget"]
    min_lead_hours = analysis["min_lead_hours"]
    horizon_hours = analysis["horizon_hours"]

    folds, pending_ids = build_outer_folds(events, as_of, horizon_hours=horizon_hours)
    usable_folds = [f for f in folds if f.embargo_ok]

    reasons: list[str] = []
    if not usable_folds:
        reasons.append("没有通过 embargo 校验的时间隔离 fold，证据不足以发布")
    decided_events = [e for e in events.values() if e.label_known_at <= as_of]
    positive_decided = sum(1 for e in decided_events if e.outcome)
    if len(decided_events) < MIN_EVALUABLE_EVENTS:
        reasons.append(f"已决过程仅 {len(decided_events)} 个，少于最小有效样本 {MIN_EVALUABLE_EVENTS}")
    if positive_decided < MIN_EVALUABLE_POSITIVES:
        reasons.append(f"已决正样本仅 {positive_decided} 个，少于最小有效正样本 {MIN_EVALUABLE_POSITIVES}")

    evaluations: list[CandidateEvaluation] = []
    fold_records: list[dict[str, Any]] = []

    for fold in usable_folds:
        train_events = [events[eid] for eid in fold.train_event_ids]
        test_events = [events[eid] for eid in fold.test_event_ids]
        # embargo 复核：训练集标签必须在测试集首个过程开始之前确认。
        # horizon_cut 同时记录测试集最早起报参考时点，便于人工核对。
        earliest_test_start = min(e.start for e in test_events)
        horizon_cut = earliest_test_start - timedelta(hours=horizon_hours)
        horizon_ok = max(e.label_known_at for e in train_events) <= earliest_test_start
        fold_record = {
            "fold_id": fold.fold_id,
            "train_event_ids": list(fold.train_event_ids),
            "test_event_ids": list(fold.test_event_ids),
            "embargo_ok": fold.embargo_ok,
            "horizon_embargo_ok": horizon_ok,
            "horizon_cut_at": iso(horizon_cut),
            "reason": fold.reason,
            "inner_splits": [
                {"train_event_ids": list(a), "test_event_ids": list(b)}
                for a, b in build_inner_splits(train_events)
            ],
            "candidates": [],
        }
        fold_records.append(fold_record)

        test_scores = _scores_for_events(scores, fold.test_event_ids)
        for reg in registered:
            # 1) 登记候选：参数冻结于输入，直接在测试过程上回放。
            registered_metrics = _evaluate_on_events(reg, test_scores, test_events, horizon_hours)
            fold_record["candidates"].append({
                "candidate_id": reg.candidate_id,
                "source": "registered",
                "metrics": registered_metrics,
                "spec": reg.spec(),
            })
            # 2) 训练内出参候选：只用本 fold 训练集调参，规则冻结后用于测试集。
            fit_constraints = {
                "capacity": capacity,
                "miss_budget": miss_budget,
                "min_lead_hours": min_lead_hours,
            }
            fitted = inner_tune(reg, scores, events, fold.train_event_ids, fit_constraints)
            fitted_metrics = _evaluate_on_events(fitted, test_scores, test_events, horizon_hours)
            fold_record["candidates"].append({
                "candidate_id": fitted.candidate_id,
                "source": "fitted",
                "parent_id": reg.candidate_id,
                "metrics": fitted_metrics,
                "spec": fitted.spec(),
            })

    # 汇总每个候选（登记候选 + 训练出参候选）的跨 fold OOF 证据。
    candidate_ids: list[str] = []
    for reg in registered:
        candidate_ids.append(reg.candidate_id)
        candidate_ids.append(reg.candidate_id + ":fit")

    for cid in candidate_ids:
        per_fold: list[dict[str, Any]] = []
        frozen_configs: list[dict[str, Any]] = []
        specs: dict[str, Any] = {}
        kind = source = ""
        parent_id: str | None = None
        for fold_record in fold_records:
            entry = next(c for c in fold_record["candidates"] if c["candidate_id"] == cid)
            metrics = dict(entry["metrics"])
            metrics["fold_id"] = fold_record["fold_id"]
            per_fold.append(metrics)
            frozen_configs.append({
                "fold_id": fold_record["fold_id"],
                "train_event_ids": fold_record["train_event_ids"],
                "spec": entry["spec"],
            })
            specs = entry["spec"]
            kind = entry["spec"]["kind"]
            source = entry["spec"]["source"]
            parent_id = entry["spec"]["parent_id"]
        pooled = _pool_fold_metrics(per_fold)
        guardrails = evaluate_guardrails(pooled, capacity, miss_budget, min_lead_hours)
        eligible, why = _eligibility(pooled, guardrails, per_fold, len(usable_folds), reasons)
        evaluations.append(CandidateEvaluation(
            candidate_id=cid, kind=kind, source=source, parent_id=parent_id,
            spec=specs, fold_metrics=per_fold, pooled=pooled, guardrails=guardrails,
            eligible=eligible, eligibility_reasons=why, utility=_utility(pooled),
            frozen_fold_configs=frozen_configs,
        ))

    eligible_sorted = sorted(
        (e for e in evaluations if e.eligible),
        key=lambda e: (e.utility, 0 if e.kind == "uniform" else 1, e.candidate_id),
    )
    selected_id = eligible_sorted[0].candidate_id if eligible_sorted else None
    status = "release" if selected_id is not None else "hold"
    if status == "hold":
        if not eligible_sorted:
            reasons.append("全部候选未通过运营护栏或有效样本不足，按规则保持 hold，不按分数硬选")
    else:
        reasons.append(f"候选 {selected_id} 在全部外层测试 fold（未参与调参）上通过护栏，证据支持发布")

    # 未决过程：标签在 as_of 后确认，单独回放提醒但不计入命中/漏报。
    pending_records = _pending_report(registered, scores, events, pending_ids, horizon_hours)

    return {
        "status": status,
        "selected": selected_id,
        "folds": fold_records,
        "candidate_results": [_candidate_result_dict(e) for e in evaluations],
        "reasons": reasons,
        "pending": {
            "as_of": iso(as_of),
            "pending_event_ids": pending_ids,
            "rule": "label_known_at 晚于 as_of 的过程不进入 fold、不计命中漏报，仅报告其提醒负载",
            "events": pending_records,
        },
        "effective_sample": {
            "decided_events": len(decided_events),
            "positive_events": positive_decided,
            "usable_folds": len(usable_folds),
            "min_evaluable_events": MIN_EVALUABLE_EVENTS,
            "min_evaluable_positives": MIN_EVALUABLE_POSITIVES,
        },
        "constraints": {
            "capacity": capacity,
            "miss_budget": miss_budget,
            "min_lead_hours": min_lead_hours,
            "horizon_hours": horizon_hours,
        },
    }


def _evaluate_on_events(
    config: CandidateConfig,
    test_scores: Sequence[ScoreRow],
    test_events: Sequence[Event],
    horizon_hours: float,
) -> dict[str, Any]:
    alerts = replay_alerts(config, test_scores)
    metrics = _aggregate(alerts, test_events)
    # 保存逐 fold 的提前量原值，供跨 fold 汇总分位数。
    leads: list[float] = []
    by_event: dict[str, list[Alert]] = {}
    for alert in alerts:
        by_event.setdefault(alert.event_id, []).append(alert)
    for event in test_events:
        event_alerts = by_event.get(event.event_id, [])
        if event.outcome and event_alerts:
            first = min(a.at for a in event_alerts)
            leads.append((event.start - first).total_seconds() / 3600.0)
    metrics["lead_values"] = [round(v, 3) for v in leads]
    # 空窗误报：不落在任何测试过程窗口/分区内的提醒。
    gap = 0
    for alert in alerts:
        in_window = False
        for event in test_events:
            w0, w1 = _match_window(event, horizon_hours)
            if alert.event_id == event.event_id and alert.zone in event.zones and w0 <= alert.at <= w1:
                in_window = True
                break
        if not in_window:
            gap += 1
    metrics["gap_false_alarms"] = gap
    return metrics


def _eligibility(
    pooled: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    per_fold: Sequence[Mapping[str, Any]],
    fold_count: int,
    global_reasons: Sequence[str],
) -> tuple[bool, list[str]]:
    why: list[str] = []
    if global_reasons:
        why.extend(global_reasons)
    failed = [name for name, check in guardrails["checks"].items() if not check["passed"]]
    if failed:
        why.append("护栏未通过: " + ",".join(failed))
    if pooled["positive_events"] < MIN_EVALUABLE_POSITIVES:
        why.append(f"跨 fold 正样本 {pooled['positive_events']} 少于 {MIN_EVALUABLE_POSITIVES}")
    if pooled["events_scored"] < MIN_EVALUABLE_EVENTS:
        why.append(f"跨 fold 已决过程 {pooled['events_scored']} 少于 {MIN_EVALUABLE_EVENTS}")
    # 鲁棒性：容量与漏报护栏必须在每个 fold 都通过（这两项是硬运营约束）。
    fragile_folds = [
        m["fold_id"] for m in per_fold
        if m["max_shift_load"] > _fold_limit(guardrails, "capacity")
        or (m["miss_rate"] is not None and m["miss_rate"] > _fold_limit(guardrails, "miss_budget"))
    ]
    if fragile_folds:
        why.append("部分 fold 触发容量/漏报护栏: " + ",".join(fragile_folds))
    return (not why), why


def _fold_limit(guardrails: Mapping[str, Any], name: str) -> float:
    return float(guardrails["checks"][name]["limit"])


def _candidate_result_dict(e: CandidateEvaluation) -> dict[str, Any]:
    return {
        "candidate_id": e.candidate_id,
        "kind": e.kind,
        "source": e.source,
        "parent_id": e.parent_id,
        "spec": e.spec,
        "eligible": e.eligible,
        "eligibility_reasons": e.eligibility_reasons,
        "utility": e.utility,
        "pooled_metrics": e.pooled,
        "guardrails": e.guardrails,
        "fold_metrics": e.fold_metrics,
        "frozen_fold_configs": e.frozen_fold_configs,
    }


def _pending_report(
    registered: Sequence[CandidateConfig],
    scores: Sequence[ScoreRow],
    events: Mapping[str, Event],
    pending_ids: Sequence[str],
    horizon_hours: float,
) -> list[dict[str, Any]]:
    report = []
    for cid0 in pending_ids:
        event = events[cid0]
        event_scores = [r for r in scores if r.event_id == cid0]
        entry = {
            "event_id": cid0,
            "label_known_at": iso(event.label_known_at),
            "outcome": "pending",
            "candidates": [],
        }
        for reg in registered:
            alerts = replay_alerts(reg, event_scores)
            loads = shift_loads(alerts)
            entry["candidates"].append({
                "candidate_id": reg.candidate_id,
                "alerts": len(alerts),
                "max_shift_load": max(loads.values(), default=0),
                "shift_loads": loads,
                "alert_detail": [a.as_dict() for a in alerts],
                "note": "标签未决，提醒计入容量观察但不计命中/漏报/误报",
            })
        report.append(entry)
    return report
