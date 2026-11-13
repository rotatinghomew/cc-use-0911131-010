"""方案选择应用服务：装配输入、执行隔离验证、冻结证据、落库并输出记录。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from warning_threshold_lab.selection.analysis import (
    SelectionError,
    load_analysis,
    run_selection,
)
from warning_threshold_lab.selection.storage import SelectionLedger
from warning_threshold_lab.vintages.runtime import fingerprint

MODULE_VERSION = "warning_threshold_lab.selection-1.0.0"
# 既有评分阶段与引用键的映射，保留旧评分功能并互相引用。
STAGE_REF_MAP = {
    "vintages": "event_vintage",
    "labels": "outcome_truth",
    "replay": "counterfactual",
    "guardrails": "operational_limits",
}


def _source_versions(payload: Mapping[str, Any], stage_signatures: Mapping[str, Any]) -> dict[str, Any]:
    event_revisions = sorted(
        f"{e['event_id']}:rev{e.get('revision', 1)}" for e in payload.get("events", []) if isinstance(e, Mapping)
    )
    candidate_versions = [
        {
            "candidate_id": c.get("candidate_id"),
            "kind": c.get("kind"),
            "fingerprint": fingerprint(c),
        }
        for c in payload.get("candidates", [])
        if isinstance(c, Mapping)
    ]
    return {
        "module": MODULE_VERSION,
        "input_fingerprint": fingerprint(payload),
        "seed": payload.get("seed"),
        "as_of": payload.get("as_of"),
        "event_revisions": event_revisions,
        "candidate_versions": candidate_versions,
        "legacy_stage_signatures": dict(stage_signatures),
        "freeze_policy": (
            "训练内归一化与分区规则随候选冻结在 frozen_artifacts；"
            "as_of 之后的未来数据只能用于之后的版本"
        ),
    }


def build_refs(record: Mapping[str, Any], stage_signatures: Mapping[str, Any]) -> list[dict[str, Any]]:
    """构造与 vintages/labels/replay/guardrails 及 fold 的互相引用。"""
    refs: list[dict[str, Any]] = []
    for ref_key, stage in STAGE_REF_MAP.items():
        refs.append({
            "ref_kind": ref_key,
            "ref_key": stage,
            "stage": stage,
            "signature": stage_signatures.get(ref_key),
            "relation": "selection_consumes_legacy_stage_artifact",
        })
    for fold in record["folds"]:
        refs.append({
            "ref_kind": "fold",
            "ref_key": fold["fold_id"],
            "train_event_ids": fold["train_event_ids"],
            "test_event_ids": fold["test_event_ids"],
            "relation": "time_and_event_isolated_fold",
        })
    for pending in record.get("pending", {}).get("pending_event_ids", []):
        refs.append({
            "ref_kind": "label",
            "ref_key": pending,
            "relation": "pending_label_excluded_from_scoring",
        })
    return refs


def select_from_payload(
    payload: Mapping[str, Any],
    database: str | Path,
    selection_id: str | None = None,
) -> dict[str, Any]:
    """执行完整选择流程并持久化。返回可直接写 JSON 的选择记录。"""
    analysis = load_analysis(payload)
    result = run_selection(analysis)

    ledger = SelectionLedger(database)
    stage_signatures = ledger.stage_signatures()
    source_versions = _source_versions(payload, stage_signatures)

    input_fp = fingerprint(payload)
    if selection_id is None:
        # 同一输入幂等：选择 ID 由输入指纹与模块版本决定。
        selection_id = "sel-" + fingerprint([input_fp, MODULE_VERSION])[:16]

    record = {
        "selection_id": selection_id,
        "status": result["status"],
        "selected": result["selected"],
        "folds": result["folds"],
        "candidate_results": result["candidate_results"],
        "reasons": result["reasons"],
        "source_versions": source_versions,
        "pending": result["pending"],
        "effective_sample": result["effective_sample"],
        "constraints": result["constraints"],
    }
    refs = build_refs(record, stage_signatures)
    ledger.save_selection(selection_id, record, input_fp, refs)
    record["storage"] = ledger.stats()
    record["refs"] = refs
    return record


def select_from_files(
    input_path: str | Path,
    database: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    record = select_from_payload(payload, database)
    if output_path is not None:
        Path(output_path).write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=False),
            encoding="utf-8",
        )
    return record
