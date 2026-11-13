from __future__ import annotations
import copy
import tempfile
import unittest
from pathlib import Path
from warning_threshold_lab.service import ApplicationService

BASE = {
    "case_id": "base-case", "status": "active", "source_system": "local-synthetic", "event_date": "2026-08-02",
    "amount": 128.5, "count": 8, "total": 16,
    "metrics": {"rain": 86, "confidence": 0.82, "delay_hours": 2, "coverage": 93.5},
    "attributes": {"risk_score": 78, "capacity": 24, "priority": 3, "zone": "mountain", "channel": "radio"},
    "tags": ["synthetic", "local", "warning", "warning_threshold_lab"],
    "records": [{"id": "r1", "value": 20, "status": "open"}, {"id": "r2", "value": 35, "status": "closed"}, {"id": "r3", "value": 55, "status": "open"}],
    "timeline": [{"at": "19:56", "start": 1, "end": 3}, {"at": "21:25", "start": 4, "end": 8}],
    "links": [{"from": "county", "to": "town", "weight": 3}, {"from": "town", "to": "village", "weight": 2}],
}

CASES = [
    {
        'name': 'warning_threshold_lab-g3-c00',
        'status': 'review', 'count': 1, 'total': 3,
        'rain': 9, 'confidence': 0.35, 'delay': 3,
        'risk': 27, 'capacity': 10, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c01',
        'status': 'closed', 'count': 2, 'total': 4,
        'rain': 16, 'confidence': 0.4, 'delay': 8,
        'risk': 40, 'capacity': 11, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c02',
        'status': 'new', 'count': 3, 'total': 5,
        'rain': 23, 'confidence': 0.45, 'delay': 13,
        'risk': 53, 'capacity': 12, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c03',
        'status': 'active', 'count': 4, 'total': 6,
        'rain': 30, 'confidence': 0.5, 'delay': 18,
        'risk': 66, 'capacity': 13, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c04',
        'status': 'pending', 'count': 5, 'total': 7,
        'rain': 37, 'confidence': 0.55, 'delay': 23,
        'risk': 79, 'capacity': 14, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c05',
        'status': 'review', 'count': 6, 'total': 8,
        'rain': 44, 'confidence': 0.6, 'delay': 28,
        'risk': 92, 'capacity': 15, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c06',
        'status': 'closed', 'count': 7, 'total': 9,
        'rain': 51, 'confidence': 0.65, 'delay': 33,
        'risk': 4, 'capacity': 16, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c07',
        'status': 'new', 'count': 8, 'total': 10,
        'rain': 58, 'confidence': 0.7, 'delay': 38,
        'risk': 17, 'capacity': 17, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c08',
        'status': 'active', 'count': 9, 'total': 11,
        'rain': 65, 'confidence': 0.75, 'delay': 43,
        'risk': 30, 'capacity': 18, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c09',
        'status': 'pending', 'count': 10, 'total': 12,
        'rain': 72, 'confidence': 0.8, 'delay': 48,
        'risk': 43, 'capacity': 19, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c10',
        'status': 'review', 'count': 11, 'total': 13,
        'rain': 79, 'confidence': 0.85, 'delay': 53,
        'risk': 56, 'capacity': 20, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c11',
        'status': 'closed', 'count': 12, 'total': 14,
        'rain': 86, 'confidence': 0.9, 'delay': 58,
        'risk': 69, 'capacity': 21, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c12',
        'status': 'new', 'count': 13, 'total': 15,
        'rain': 93, 'confidence': 0.35, 'delay': 63,
        'risk': 82, 'capacity': 22, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c13',
        'status': 'active', 'count': 14, 'total': 16,
        'rain': 100, 'confidence': 0.4, 'delay': 68,
        'risk': 95, 'capacity': 23, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c14',
        'status': 'pending', 'count': 15, 'total': 17,
        'rain': 107, 'confidence': 0.45, 'delay': 73,
        'risk': 7, 'capacity': 24, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c15',
        'status': 'review', 'count': 16, 'total': 18,
        'rain': 114, 'confidence': 0.5, 'delay': 78,
        'risk': 20, 'capacity': 25, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c16',
        'status': 'closed', 'count': 17, 'total': 19,
        'rain': 121, 'confidence': 0.55, 'delay': 83,
        'risk': 33, 'capacity': 26, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c17',
        'status': 'new', 'count': 1, 'total': 20,
        'rain': 128, 'confidence': 0.6, 'delay': 88,
        'risk': 46, 'capacity': 27, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c18',
        'status': 'active', 'count': 2, 'total': 21,
        'rain': 135, 'confidence': 0.65, 'delay': 93,
        'risk': 59, 'capacity': 28, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c19',
        'status': 'pending', 'count': 3, 'total': 22,
        'rain': 142, 'confidence': 0.7, 'delay': 2,
        'risk': 72, 'capacity': 29, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c20',
        'status': 'review', 'count': 4, 'total': 23,
        'rain': 149, 'confidence': 0.75, 'delay': 7,
        'risk': 85, 'capacity': 30, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c21',
        'status': 'closed', 'count': 5, 'total': 24,
        'rain': 156, 'confidence': 0.8, 'delay': 12,
        'risk': 98, 'capacity': 31, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c22',
        'status': 'new', 'count': 6, 'total': 25,
        'rain': 163, 'confidence': 0.85, 'delay': 17,
        'risk': 10, 'capacity': 32, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c23',
        'status': 'active', 'count': 7, 'total': 3,
        'rain': 170, 'confidence': 0.9, 'delay': 22,
        'risk': 23, 'capacity': 33, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c24',
        'status': 'pending', 'count': 8, 'total': 4,
        'rain': 177, 'confidence': 0.35, 'delay': 27,
        'risk': 36, 'capacity': 34, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c25',
        'status': 'review', 'count': 9, 'total': 5,
        'rain': 4, 'confidence': 0.4, 'delay': 32,
        'risk': 49, 'capacity': 35, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c26',
        'status': 'closed', 'count': 10, 'total': 6,
        'rain': 11, 'confidence': 0.45, 'delay': 37,
        'risk': 62, 'capacity': 36, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c27',
        'status': 'new', 'count': 11, 'total': 7,
        'rain': 18, 'confidence': 0.5, 'delay': 42,
        'risk': 75, 'capacity': 37, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c28',
        'status': 'active', 'count': 12, 'total': 8,
        'rain': 25, 'confidence': 0.55, 'delay': 47,
        'risk': 88, 'capacity': 38, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c29',
        'status': 'pending', 'count': 13, 'total': 9,
        'rain': 32, 'confidence': 0.6, 'delay': 52,
        'risk': 0, 'capacity': 39, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c30',
        'status': 'review', 'count': 14, 'total': 10,
        'rain': 39, 'confidence': 0.65, 'delay': 57,
        'risk': 13, 'capacity': 40, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c31',
        'status': 'closed', 'count': 15, 'total': 11,
        'rain': 46, 'confidence': 0.7, 'delay': 62,
        'risk': 26, 'capacity': 10, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c32',
        'status': 'new', 'count': 16, 'total': 12,
        'rain': 53, 'confidence': 0.75, 'delay': 67,
        'risk': 39, 'capacity': 11, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c33',
        'status': 'active', 'count': 17, 'total': 13,
        'rain': 60, 'confidence': 0.8, 'delay': 72,
        'risk': 52, 'capacity': 12, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c34',
        'status': 'pending', 'count': 1, 'total': 14,
        'rain': 67, 'confidence': 0.85, 'delay': 77,
        'risk': 65, 'capacity': 13, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c35',
        'status': 'review', 'count': 2, 'total': 15,
        'rain': 74, 'confidence': 0.9, 'delay': 82,
        'risk': 78, 'capacity': 14, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c36',
        'status': 'closed', 'count': 3, 'total': 16,
        'rain': 81, 'confidence': 0.35, 'delay': 87,
        'risk': 91, 'capacity': 15, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c37',
        'status': 'new', 'count': 4, 'total': 17,
        'rain': 88, 'confidence': 0.4, 'delay': 92,
        'risk': 3, 'capacity': 16, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c38',
        'status': 'active', 'count': 5, 'total': 18,
        'rain': 95, 'confidence': 0.45, 'delay': 1,
        'risk': 16, 'capacity': 17, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c39',
        'status': 'pending', 'count': 6, 'total': 19,
        'rain': 102, 'confidence': 0.5, 'delay': 6,
        'risk': 29, 'capacity': 18, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c40',
        'status': 'review', 'count': 7, 'total': 20,
        'rain': 109, 'confidence': 0.55, 'delay': 11,
        'risk': 42, 'capacity': 19, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c41',
        'status': 'closed', 'count': 8, 'total': 21,
        'rain': 116, 'confidence': 0.6, 'delay': 16,
        'risk': 55, 'capacity': 20, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c42',
        'status': 'new', 'count': 9, 'total': 22,
        'rain': 123, 'confidence': 0.65, 'delay': 21,
        'risk': 68, 'capacity': 21, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c43',
        'status': 'active', 'count': 10, 'total': 23,
        'rain': 130, 'confidence': 0.7, 'delay': 26,
        'risk': 81, 'capacity': 22, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c44',
        'status': 'pending', 'count': 11, 'total': 24,
        'rain': 137, 'confidence': 0.75, 'delay': 31,
        'risk': 94, 'capacity': 23, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c45',
        'status': 'review', 'count': 12, 'total': 25,
        'rain': 144, 'confidence': 0.8, 'delay': 36,
        'risk': 6, 'capacity': 24, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c46',
        'status': 'closed', 'count': 13, 'total': 3,
        'rain': 151, 'confidence': 0.85, 'delay': 41,
        'risk': 19, 'capacity': 25, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g3-c47',
        'status': 'new', 'count': 14, 'total': 4,
        'rain': 158, 'confidence': 0.9, 'delay': 46,
        'risk': 32, 'capacity': 26, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
]

class CounterfactualTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "state.sqlite3"
        self.service = ApplicationService(self.database)

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, item, position):
        payload = copy.deepcopy(BASE)
        payload["case_id"] = item["name"]
        payload["status"] = item["status"]
        payload["count"] = item["count"]
        payload["total"] = item["total"]
        payload["metrics"].update(rain=item["rain"], confidence=item["confidence"], delay_hours=item["delay"])
        payload["attributes"].update(risk_score=item["risk"], capacity=item["capacity"], zone=item["zone"])
        payload["records"].append({"id": f"extra-{position}", "value": item["rain"] / 3, "status": item["status"]})
        return payload

    def test_business_matrix(self):
        for position, item in enumerate(CASES):
            with self.subTest(case=item["name"]):
                result = self.service.execute(self.payload(item, position), "matrix:" + item["name"])
                self.assertEqual(result["state"], "completed")
                self.assertEqual(result["project"], item["expected_project"])
                self.assertEqual(len(result["artifacts"]), item["expected_artifacts"])
                self.assertIn('counterfactual', result["artifacts"])
                projection = result["artifacts"]['counterfactual']
                self.assertGreaterEqual(projection["sample_count"], 4)
                self.assertGreaterEqual(projection["peak"], projection["median"])
                self.assertIn("bands", projection)
                self.assertGreater(result["event_count"], 7)

    def test_idempotent_replay(self):
        payload = self.payload(CASES[0], 0)
        first = self.service.execute(payload, "same-request")
        second = self.service.execute(payload, "same-request")
        self.assertEqual(first, second)
        self.assertEqual(first["storage"]["idempotency"], 0)
        self.assertEqual(self.service.ledger.stats()["idempotency"], 1)

    def test_partial_batch_failure(self):
        valid = self.payload(CASES[1], 1)
        invalid = copy.deepcopy(valid)
        invalid.pop("case_id")
        result = self.service.execute_batch([valid, invalid, self.payload(CASES[2], 2)])
        self.assertEqual(len(result["completed"]), 2)
        self.assertEqual(len(result["failed"]), 1)
        self.assertGreaterEqual(result["storage"]["failures"], 1)

    def test_domain_projection_is_stable(self):
        payload = self.payload(CASES[-1], len(CASES) - 1)
        result = self.service.execute(payload, "projection-check")
        projection = result["artifacts"]['counterfactual']
        self.assertEqual(projection["stage"], 'counterfactual')
        self.assertEqual(projection["focus"], '候选阈值反事实回放')
        self.assertIsInstance(projection["signature"], str)
        self.assertGreater(len(projection["signature"]), 20)

if __name__ == "__main__":
    unittest.main()
