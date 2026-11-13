"""生成 hold 场景样例 fixtures/analysis/hold_input.json。

用于把“不能发布”作为正常、可核对的业务结果：
- 13 个跨午夜持续过程（当日 23:00 至次日 05:00），覆盖两个分区；
- 标签在过程结束后 24 小时才确认（label_known_at = start + 30h），即延后确认；
- 前 12 个过程在 as_of 前已决，最后 1 个过程标签未决（但其逐时分数已可见）；
- 两个分区的风险分持续位于阈值网格最大值之上，配合 2 小时冷却，任何候选
  （含训练内出参候选）每班都会产生超过 capacity=2 的提醒，因此全部方案
  都超容量，结论只能是 hold，不允许硬选分数最高的候选。

仅依赖标准库，固定输出（无随机数）。运行：
    python3 fixtures/analysis/generate_hold_fixture.py
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUTPUT = Path(__file__).with_name("hold_input.json")


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build() -> dict:
    first_day = datetime(2026, 4, 1, tzinfo=timezone.utc)
    start_days = [first_day + timedelta(days=7 * i) for i in range(13)]
    events: list[dict] = []
    scores: list[dict] = []
    for i, day0 in enumerate(start_days):
        start = day0.replace(hour=23)
        end = start + timedelta(hours=6)  # 跨午夜
        label_at = start + timedelta(hours=30)  # 过程结束 24 小时后才确认
        events.append({
            "event_id": f"night{i}",
            "zones": ["a", "b"],
            "start": iso(start),
            "end": iso(end),
            "label_known_at": iso(label_at),
            "revision": 1,
            "outcome": i % 3 != 1,  # 约 2/3 为正样本，保证每个测试 fold 正样本充足
        })
        for h in range(12):
            at = start - timedelta(hours=12 - h)
            for zone in ("a", "b"):
                # 0.981~0.985 稳定高分：网格内任何阈值（最高 0.975）都会反复
                # 提醒，所有候选每班负载都 > capacity=2，无法靠调参降到容量内。
                risk = round(0.981 + 0.001 * ((h + (0 if zone == "a" else 1)) % 5), 3)
                scores.append({
                    "score_id": f"{i}-{zone}-{h}",
                    "event_id": f"night{i}",
                    "zone": zone,
                    "at": iso(at),
                    "known_at": iso(at),
                    "risk": risk,
                    "shift_id": f"nshift{i}-{zone}",
                })
    as_of = start_days[-1] + timedelta(hours=23)
    return {
        "seed": 91,
        "as_of": iso(as_of),
        "scores": scores,
        "events": events,
        "capacity": 2,
        "miss_budget": 0.25,
        "min_lead_hours": 2,
        "horizon_hours": 12,
        "candidates": [
            {"candidate_id": "uniform", "kind": "uniform",
             "threshold": 0.9, "cooldown_hours": 2},
            {"candidate_id": "zonal", "kind": "zonal",
             "thresholds": {"a": 0.9, "b": 0.92}, "cooldown_hours": 2},
        ],
    }


def main() -> None:
    payload = build()
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    decided = [
        e["event_id"] for e in payload["events"]
        if datetime.fromisoformat(e["label_known_at"].replace("Z", "+00:00"))
        <= datetime.fromisoformat(payload["as_of"].replace("Z", "+00:00"))
    ]
    pending = [e["event_id"] for e in payload["events"] if e["event_id"] not in decided]
    print(f"wrote {OUTPUT} decided={decided} pending={pending}")


if __name__ == "__main__":
    main()
