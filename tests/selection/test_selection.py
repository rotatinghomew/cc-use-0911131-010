from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from warning_threshold_lab.selection.analysis import (
    DEFAULT_HORIZON_HOURS,
    CandidateConfig,
    SelectionError,
    build_outer_folds,
    evaluate_guardrails,
    load_analysis,
    parse_ts,
    replay_alerts,
    run_selection,
    wilson_interval,
)
from warning_threshold_lab.selection.service import select_from_files, select_from_payload
from warning_threshold_lab.selection.storage import SelectionLedger

ROOT = Path(__file__).resolve().parents[2]
MAIN_FIXTURE = ROOT / "fixtures/analysis/input.json"
HOLD_FIXTURE = ROOT / "fixtures/analysis/hold_input.json"


def load_main():
    return json.loads(MAIN_FIXTURE.read_text(encoding="utf-8"))


class IsolationAndFoldTests(unittest.TestCase):
    def test_event_slices_never_split_between_train_and_test(self):
        payload = load_main()
        analysis = load_analysis(payload)
        record = run_selection(analysis)
        all_event_ids = set(analysis["events"])
        covered_test = set()
        for fold in record["folds"]:
            train = set(fold["train_event_ids"])
            test = set(fold["test_event_ids"])
            # 同一持续过程整体归属，不允许一半训练一半检验
            self.assertTrue(train.isdisjoint(test))
            # 训练集严格早于测试集（时间隔离）
            starts = {analysis["events"][eid].start for eid in train | test}
            latest_train = max(analysis["events"][eid].start for eid in train)
            earliest_test = min(analysis["events"][eid].start for eid in test)
            self.assertLess(latest_train, earliest_test)
            self.assertTrue(fold["embargo_ok"])
            self.assertTrue(fold["horizon_embargo_ok"])
            covered_test |= test
        # 每个测试过程都来自已决集合；前 min_train 个过程只作训练（前向扩展
        # 窗口的正常性质），任何过程都不会在同一 fold 同时进入训练和测试。
        decided = {eid for eid, e in analysis["events"].items() if e.label_known_at <= analysis["as_of"]}
        self.assertTrue(covered_test.issubset(decided))
        # 除首个训练块外，其余已决过程都应恰好出现一次于某个测试 fold（不丢尾部）
        first_train = set(record["folds"][0]["train_event_ids"])
        self.assertEqual(covered_test, decided - first_train)
        for fold in record["folds"]:
            self.assertTrue(set(fold["train_event_ids"]).isdisjoint(set(fold["test_event_ids"])))

    def test_fold_lists_train_and_test_event_ids(self):
        payload = load_main()
        analysis = load_analysis(payload)
        folds, _ = build_outer_folds(analysis["events"], analysis["as_of"],
                                     horizon_hours=analysis["horizon_hours"])
        self.assertGreaterEqual(len(folds), 2)
        for fold in folds:
            self.assertTrue(fold.train_event_ids)
            self.assertTrue(fold.test_event_ids)
            self.assertEqual(len(fold.test_event_ids), 3)

    def test_cross_midnight_event_kept_whole(self):
        payload = json.loads(HOLD_FIXTURE.read_text(encoding="utf-8"))
        analysis = load_analysis(payload)
        # 所有过程都跨午夜（23:00 -> 次日 05:00）
        for event in analysis["events"].values():
            self.assertEqual(event.start.day + (1 if event.end.hour < event.start.hour else 0),
                             event.start.day + 1)
            self.assertLess(event.start, event.end)
        record = run_selection(analysis)
        for fold in record["folds"]:
            for eid in fold["test_event_ids"]:
                self.assertNotIn(eid, fold["train_event_ids"])

    def test_embargo_blocks_label_leakage(self):
        payload = load_main()
        analysis = load_analysis(payload)
        # 构造一个标签在测试期才确认的场景：把训练尾部事件标签延后到测试事件之后
        events = dict(analysis["events"])
        ordered = sorted(events.values(), key=lambda e: e.start)
        from dataclasses import replace
        tainted = replace(ordered[0], label_known_at=ordered[8].label_known_at + timedelta(days=1))
        events[tainted.event_id] = tainted
        folds, _ = build_outer_folds(events, analysis["as_of"],
                                     horizon_hours=analysis["horizon_hours"])
        self.assertFalse(all(f.embargo_ok for f in folds))


class PendingLabelTests(unittest.TestCase):
    def test_unconfirmed_labels_excluded_from_folds_and_scoring(self):
        payload = load_main()
        analysis = load_analysis(payload)
        record = run_selection(analysis)
        # storm15 标签在 as_of 之后确认
        self.assertIn("storm15", record["pending"]["pending_event_ids"])
        for fold in record["folds"]:
            self.assertNotIn("storm15", fold["train_event_ids"])
            self.assertNotIn("storm15", fold["test_event_ids"])
        for candidate in record["candidate_results"]:
            scored = set()
            for m in candidate["fold_metrics"]:
                scored.update(m.get("fold_id", ""))  # fold id only; events counted implicitly
            # 池化指标只统计 15 个已决过程中的 9 个 OOF 测试过程
            self.assertEqual(candidate["pooled_metrics"]["events_scored"], 9)
        # 未决过程仍报告其提醒负载，但不计命中漏报
        pending_entry = next(e for e in record["pending"]["events"] if e["event_id"] == "storm15")
        self.assertEqual(pending_entry["outcome"], "pending")
        self.assertTrue(pending_entry["candidates"])

    def test_future_score_rejected_at_intake(self):
        payload = load_main()
        payload["scores"][0] = dict(payload["scores"][0])
        payload["scores"][0]["known_at"] = "2099-01-01T00:00:00Z"
        with self.assertRaises(SelectionError):
            load_analysis(payload)


class MetricDefinitionTests(unittest.TestCase):
    def setUp(self):
        payload = load_main()
        self.analysis = load_analysis(payload)
        self.record = run_selection(self.analysis)

    def test_hit_miss_lead_repeat_and_capacity_metrics(self):
        uniform = next(c for c in self.record["candidate_results"] if c["candidate_id"] == "uniform")
        pooled = uniform["pooled_metrics"]
        # 主样例 OOF：正过程全部命中、零漏报
        self.assertEqual(pooled["misses"], 0)
        self.assertEqual(pooled["hits"], pooled["positive_events"])
        self.assertEqual(pooled["miss_rate"], 0.0)
        self.assertIsNotNone(pooled["median_lead_hours"])
        self.assertGreaterEqual(pooled["median_lead_hours"], self.record["constraints"]["min_lead_hours"])
        # 重复提醒被显式计量（值班组关注项）
        self.assertGreaterEqual(pooled["repeat_alerts"], 0)
        # 容量按当班 shift 统计
        self.assertGreaterEqual(pooled["max_shift_load"], 1)
        for fold_metric in uniform["fold_metrics"]:
            self.assertIn("shift_loads", fold_metric)
            self.assertIn("gap_false_alarms", fold_metric)

    def test_sustained_process_counts_single_hit_not_many(self):
        # 同一过程跨多分区多小时多次提醒，命中只计一次，重复提醒另计
        config = CandidateConfig(
            candidate_id="c", kind="uniform", cooldown_hours=4,
            uniform_threshold=0.5, source="registered",
        )
        scores = [s for s in self.analysis["scores"] if s.event_id == "storm1"]
        alerts = replay_alerts(config, scores)
        self.assertGreater(len(alerts), 1)  # 多次提醒
        metric_fold = None
        for candidate in self.record["candidate_results"]:
            for m in candidate["fold_metrics"]:
                if "storm1" in str(m):
                    metric_fold = m
        # 直接用聚合器验证单过程命中口径
        from warning_threshold_lab.selection.analysis import _aggregate
        events = [self.analysis["events"]["storm1"]]
        agg = _aggregate(alerts, events)
        self.assertEqual(agg["hits"] + agg["misses"], 1)

    def test_wilson_interval_reflects_small_sample_uncertainty(self):
        interval = wilson_interval(3, 3)
        self.assertEqual(interval["point"], 1.0)
        self.assertLess(interval["lower"], 1.0)  # 全中也不能报 100% 确定
        self.assertEqual(interval["upper"], 1.0)
        empty = wilson_interval(0, 0)
        self.assertIsNone(empty["point"])

    def test_guardrails_are_hard_constraints(self):
        passed = evaluate_guardrails(
            {"max_shift_load": 2, "miss_rate": 0.1, "median_lead_hours": 3},
            capacity=2, miss_budget=0.25, min_lead_hours=2,
        )
        self.assertTrue(passed["all_passed"])
        breached = evaluate_guardrails(
            {"max_shift_load": 5, "miss_rate": 0.1, "median_lead_hours": 3},
            capacity=2, miss_budget=0.25, min_lead_hours=2,
        )
        self.assertFalse(breached["all_passed"])
        self.assertFalse(breached["checks"]["capacity"]["passed"])


class NoTestWindowTuningTests(unittest.TestCase):
    def test_fitted_threshold_derived_only_from_train_fold(self):
        payload = load_main()
        analysis = load_analysis(payload)
        record = run_selection(analysis)
        fitted = next(c for c in record["candidate_results"] if c["candidate_id"] == "uniform:fit")
        for frozen in fitted["frozen_fold_configs"]:
            trained = set(frozen["train_event_ids"])
            fold = next(f for f in record["folds"] if f["fold_id"] == frozen["fold_id"])
            self.assertEqual(trained, set(fold["train_event_ids"]))
            # 冻结规则只引用训练事件，绝不含测试事件
            for test_id in fold["test_event_ids"]:
                self.assertNotIn(test_id, frozen["spec"]["frozen_artifacts"]["trained_on_event_ids"])
            self.assertIn("score_quantiles", frozen["spec"]["frozen_artifacts"])

    def test_report_uses_oof_not_final_window_retuned_score(self):
        payload = load_main()
        analysis = load_analysis(payload)
        record = run_selection(analysis)
        # 每个候选的成绩是跨 fold 的 OOF 池化，测试事件从不参与自身阈值选择
        for candidate in record["candidate_results"]:
            fold_ids = {m["fold_id"] for m in candidate["fold_metrics"]}
            self.assertEqual(fold_ids, {f["fold_id"] for f in record["folds"]})
            self.assertIn("hit_rate_wilson95", candidate["pooled_metrics"])


class ReleaseDecisionTests(unittest.TestCase):
    def test_main_fixture_releases_supported_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "sel.sqlite3"
            record = select_from_files(MAIN_FIXTURE, db)
            self.assertEqual(record["status"], "release")
            self.assertIsNotNone(record["selected"])
            chosen = next(c for c in record["candidate_results"] if c["candidate_id"] == record["selected"])
            self.assertTrue(chosen["eligible"])
            self.assertTrue(chosen["guardrails"]["all_passed"])
            # 选择不是只看逐时准确率：utility 同时惩罚重复提醒与误报
            self.assertIn("utility", chosen)

    def test_hold_when_every_candidate_over_capacity(self):
        payload = json.loads(HOLD_FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "hold.sqlite3"
            record = select_from_payload(payload, db)
            self.assertEqual(record["status"], "hold")
            self.assertIsNone(record["selected"])
            # 全部候选（含训练出参候选）都超容量，不能硬选最高分
            for candidate in record["candidate_results"]:
                self.assertFalse(candidate["eligible"])
                self.assertFalse(candidate["guardrails"]["checks"]["capacity"]["passed"])
                self.assertGreater(
                    candidate["pooled_metrics"]["max_shift_load"],
                    record["constraints"]["capacity"],
                )
            self.assertTrue(any("hold" in reason for reason in record["reasons"]))

    def test_hold_is_a_persisted_business_result(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "hold.sqlite3"
            out = Path(directory) / "record.json"
            record = select_from_files(HOLD_FIXTURE, db, out)
            on_disk = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["status"], "hold")
            ledger = SelectionLedger(db)
            loaded = ledger.load_selection(record["selection_id"])
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["status"], "hold")
            self.assertIsNone(loaded["selected"])

    def test_min_sample_floor_forces_hold(self):
        payload = json.loads(HOLD_FIXTURE.read_text(encoding="utf-8"))
        # 把 as_of 提前到只有少量已决过程
        payload["as_of"] = "2026-04-09T00:00:00Z"
        # 同时剔除晚于 as_of 的分数引用，避免 intake 报错：保留前两个过程
        keep = {"night0", "night1"}
        payload["events"] = [e for e in payload["events"] if e["event_id"] in keep]
        payload["scores"] = [s for s in payload["scores"] if s["event_id"] in keep]
        with tempfile.TemporaryDirectory() as directory:
            record = select_from_payload(payload, Path(directory) / "x.sqlite3")
            self.assertEqual(record["status"], "hold")
            self.assertTrue(any("有效样本" in reason or "fold" in reason for reason in record["reasons"]))


class RecordContractAndStorageTests(unittest.TestCase):
    def test_record_contains_required_top_level_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            record = select_from_files(MAIN_FIXTURE, Path(directory) / "c.sqlite3")
            for key in ("selection_id", "status", "selected", "folds",
                        "candidate_results", "reasons", "source_versions"):
                self.assertIn(key, record)
            self.assertIn(record["status"], ("release", "hold"))
            for fold in record["folds"]:
                self.assertIn("train_event_ids", fold)
                self.assertIn("test_event_ids", fold)
            sv = record["source_versions"]
            for key in ("module", "input_fingerprint", "event_revisions",
                        "candidate_versions", "freeze_policy"):
                self.assertIn(key, sv)

    def test_refs_link_vintages_labels_replay_guardrails_and_folds(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "c.sqlite3"
            record = select_from_files(MAIN_FIXTURE, db)
            kinds = {ref["ref_kind"] for ref in record["refs"]}
            for expected in ("vintages", "labels", "replay", "guardrails", "fold", "label"):
                self.assertIn(expected, kinds)
            ledger = SelectionLedger(db)
            stored_refs = ledger.refs_for(record["selection_id"])
            self.assertEqual(len(stored_refs), len(record["refs"]))

    def test_idempotent_selection_id_for_same_input(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "c.sqlite3"
            first = select_from_files(MAIN_FIXTURE, db)
            second = select_from_files(MAIN_FIXTURE, db)
            self.assertEqual(first["selection_id"], second["selection_id"])

    def test_legacy_scoring_tables_coexist(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "coexist.sqlite3"
            select_from_files(MAIN_FIXTURE, db)
            # 旧评分功能在同一数据库上照常工作
            from warning_threshold_lab.service import run_fixture
            run_fixture(ROOT / "fixtures/demo.json", db)
            with sqlite3.connect(db) as connection:
                names = {r[0] for r in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ("runs", "events", "selections", "selection_folds",
                          "selection_candidates", "selection_refs"):
                self.assertIn(table, names)


class CliTests(unittest.TestCase):
    def test_module_cli_writes_output_and_db(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.json"
            database = Path(directory) / "cli.sqlite3"
            proc = subprocess.run(
                [sys.executable, "-m", "warning_threshold_lab.selection",
                 "--input", str(HOLD_FIXTURE), "--output", str(output),
                 "--database", str(database)],
                cwd=ROOT, capture_output=True, text=True, check=True,
            )
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "hold")
            self.assertIn("selection_id", json.loads(proc.stdout))

    def test_cli_rejects_bad_input_with_error_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.json"
            bad.write_text(json.dumps({"scores": []}), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "warning_threshold_lab.selection",
                 "--input", str(bad), "--output", str(Path(directory) / "o.json"),
                 "--database", str(Path(directory) / "db.sqlite3")],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("error", proc.stderr)


class UniformVsZonalTests(unittest.TestCase):
    def test_zonal_fit_shrinks_small_zones_to_global(self):
        payload = load_main()
        analysis = load_analysis(payload)
        record = run_selection(analysis)
        zonal_fit = next(c for c in record["candidate_results"] if c["candidate_id"] == "zonal:fit")
        for frozen in zonal_fit["frozen_fold_configs"]:
            rules = frozen["spec"]["frozen_artifacts"]["zone_rules"]
            for zone, rule in rules.items():
                # 小样本分区必须记录收缩行为或独立阈值，二者之一
                self.assertIn("shrunk_to_global", rule)
                self.assertIn("threshold", rule)

    def test_both_uniform_and_zonal_evaluated_under_same_constraints(self):
        payload = load_main()
        analysis = load_analysis(payload)
        record = run_selection(analysis)
        kinds = {c["kind"] for c in record["candidate_results"]}
        self.assertIn("uniform", kinds)
        self.assertIn("zonal", kinds)
        for candidate in record["candidate_results"]:
            limits = candidate["guardrails"]["checks"]
            self.assertEqual(limits["capacity"]["limit"], analysis["capacity"])
            self.assertEqual(limits["miss_budget"]["limit"], analysis["miss_budget"])
            self.assertEqual(limits["min_lead"]["limit"], analysis["min_lead_hours"])


if __name__ == "__main__":
    unittest.main()
