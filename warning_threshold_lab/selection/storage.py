"""方案选择记录的 SQLite 持久化。

与既有 runs/events/idempotency/failures 表共存于同一数据库，新增选择专属
表，并通过 refs 与 vintages、labels、replay、guardrails 各阶段互相引用。
旧评分功能（ApplicationService 与 experiments.command）保持不变。
"""
from __future__ import annotations
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from warning_threshold_lab.vintages.runtime import fingerprint, stable_json

SELECTION_TABLES = (
    "selections",
    "selection_folds",
    "selection_candidates",
    "selection_refs",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SelectionLedger:
    def __init__(self, database: str):
        self.database = str(database)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS selections(
                    selection_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL CHECK(status IN ('release','hold')),
                    selected TEXT,
                    input_fingerprint TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    source_versions_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS selection_folds(
                    selection_id TEXT NOT NULL,
                    fold_id TEXT NOT NULL,
                    train_event_ids TEXT NOT NULL,
                    test_event_ids TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    PRIMARY KEY(selection_id, fold_id),
                    FOREIGN KEY(selection_id) REFERENCES selections(selection_id)
                );
                CREATE TABLE IF NOT EXISTS selection_candidates(
                    selection_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    eligible INTEGER NOT NULL,
                    detail_json TEXT NOT NULL,
                    PRIMARY KEY(selection_id, candidate_id),
                    FOREIGN KEY(selection_id) REFERENCES selections(selection_id)
                );
                CREATE TABLE IF NOT EXISTS selection_refs(
                    selection_id TEXT NOT NULL,
                    ref_kind TEXT NOT NULL,
                    ref_key TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    PRIMARY KEY(selection_id, ref_kind, ref_key),
                    FOREIGN KEY(selection_id) REFERENCES selections(selection_id)
                );
                """
            )

    def save_selection(
        self,
        selection_id: str,
        record: Mapping[str, Any],
        input_fingerprint: str,
        refs: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        refs = refs or []
        with self._lock, self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO selections(selection_id,status,selected,input_fingerprint,record_json,source_versions_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    selection_id,
                    record["status"],
                    record.get("selected"),
                    input_fingerprint,
                    stable_json(record),
                    stable_json(record.get("source_versions", {})),
                    utc_now(),
                ),
            )
            for fold in record["folds"]:
                connection.execute(
                    "INSERT OR REPLACE INTO selection_folds(selection_id,fold_id,train_event_ids,test_event_ids,detail_json) VALUES(?,?,?,?,?)",
                    (
                        selection_id,
                        fold["fold_id"],
                        stable_json(fold["train_event_ids"]),
                        stable_json(fold["test_event_ids"]),
                        stable_json(fold),
                    ),
                )
            for candidate in record["candidate_results"]:
                connection.execute(
                    "INSERT OR REPLACE INTO selection_candidates(selection_id,candidate_id,eligible,detail_json) VALUES(?,?,?,?)",
                    (
                        selection_id,
                        candidate["candidate_id"],
                        1 if candidate["eligible"] else 0,
                        stable_json(candidate),
                    ),
                )
            for ref in refs:
                connection.execute(
                    "INSERT OR REPLACE INTO selection_refs(selection_id,ref_kind,ref_key,detail_json) VALUES(?,?,?,?)",
                    (
                        selection_id,
                        str(ref["ref_kind"]),
                        str(ref["ref_key"]),
                        stable_json(ref),
                    ),
                )

    def load_selection(self, selection_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM selections WHERE selection_id=?", (selection_id,)
            ).fetchone()
        if row is None:
            return None
        import json
        return json.loads(row["record_json"])

    def find_by_input_fingerprint(self, input_fingerprint: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM selections WHERE input_fingerprint=? ORDER BY created_at DESC LIMIT 1",
                (input_fingerprint,),
            ).fetchone()
        if row is None:
            return None
        import json
        return json.loads(row["record_json"])

    def refs_for(self, selection_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT detail_json FROM selection_refs WHERE selection_id=? ORDER BY ref_kind, ref_key",
                (selection_id,),
            ).fetchall()
        import json
        return [json.loads(r["detail_json"]) for r in rows]

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            return {
                name: int(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
                for name in SELECTION_TABLES
            }

    def stage_signatures(self) -> dict[str, str | None]:
        """读取既有评分流程留下的阶段工件指纹，作为互相引用的锚点。"""
        signatures: dict[str, str | None] = {
            "vintages": None,
            "labels": None,
            "replay": None,
            "guardrails": None,
        }
        with self.connect() as connection:
            has_runs = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runs'"
            ).fetchone()
            if has_runs is None:
                return signatures
            rows = connection.execute(
                "SELECT artifacts FROM runs ORDER BY updated_at DESC"
            ).fetchall()
        import json
        stage_to_key = {
            "event_vintage": "vintages",
            "outcome_truth": "labels",
            "counterfactual": "replay",
            "operational_limits": "guardrails",
        }
        for row in rows:
            try:
                artifacts = json.loads(row["artifacts"])
            except (TypeError, ValueError):
                continue
            for stage, key in stage_to_key.items():
                if signatures[key] is None and isinstance(artifacts, dict) and stage in artifacts:
                    signatures[key] = artifacts[stage].get("signature")
        return signatures

