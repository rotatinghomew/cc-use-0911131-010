from __future__ import annotations
from typing import Any
from warning_threshold_lab.vintages.runtime import RunState, SQLiteLedger, fingerprint, number, sequence

class ExperimentRunner:
    artifact_key = 'experiment_frontier'

    def execute(self, state: RunState, stages: list[Any], ledger: SQLiteLedger) -> None:
        stage_scores = []
        for stage in stages:
            stage.apply(state)
            stage_scores.append(state.artifacts[stage.name]["score"])
            ledger.save(state)
        baseline = number(state.payload.get("metrics", {}).get("rain"))
        candidates = []
        for delta in (-30, -20, -10, 0, 10, 20, 30):
            threshold = max(0.0, baseline + delta)
            misses = sum(score < threshold / 2 for score in stage_scores)
            alerts = sum(score >= threshold / 2 for score in stage_scores)
            cost = misses * 5 + alerts * 1.2 + abs(delta) * 0.05
            candidates.append({"threshold": threshold, "misses": misses, "alerts": alerts, "cost": round(cost, 6)})
        frontier = sorted(candidates, key=lambda item: (item["cost"], item["threshold"]))
        state.artifacts[self.artifact_key] = {"baseline": baseline, "candidates": candidates, "recommended": frontier[0], "frontier": frontier[:3], "signature": fingerprint(candidates)}
        state.emit(self.artifact_key, "experiment_frontier_completed", candidates=len(candidates))
