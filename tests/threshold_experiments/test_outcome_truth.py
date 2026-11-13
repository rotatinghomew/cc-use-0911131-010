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
        'name': 'warning_threshold_lab-g1-c00',
        'status': 'active', 'count': 1, 'total': 3,
        'rain': 3, 'confidence': 0.35, 'delay': 1,
        'risk': 9, 'capacity': 10, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c01',
        'status': 'pending', 'count': 2, 'total': 4,
        'rain': 10, 'confidence': 0.4, 'delay': 6,
        'risk': 22, 'capacity': 11, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c02',
        'status': 'review', 'count': 3, 'total': 5,
        'rain': 17, 'confidence': 0.45, 'delay': 11,
        'risk': 35, 'capacity': 12, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c03',
        'status': 'closed', 'count': 4, 'total': 6,
        'rain': 24, 'confidence': 0.5, 'delay': 16,
        'risk': 48, 'capacity': 13, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c04',
        'status': 'new', 'count': 5, 'total': 7,
        'rain': 31, 'confidence': 0.55, 'delay': 21,
        'risk': 61, 'capacity': 14, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c05',
        'status': 'active', 'count': 6, 'total': 8,
        'rain': 38, 'confidence': 0.6, 'delay': 26,
        'risk': 74, 'capacity': 15, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c06',
        'status': 'pending', 'count': 7, 'total': 9,
        'rain': 45, 'confidence': 0.65, 'delay': 31,
        'risk': 87, 'capacity': 16, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c07',
        'status': 'review', 'count': 8, 'total': 10,
        'rain': 52, 'confidence': 0.7, 'delay': 36,
        'risk': 100, 'capacity': 17, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c08',
        'status': 'closed', 'count': 9, 'total': 11,
        'rain': 59, 'confidence': 0.75, 'delay': 41,
        'risk': 12, 'capacity': 18, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c09',
        'status': 'new', 'count': 10, 'total': 12,
        'rain': 66, 'confidence': 0.8, 'delay': 46,
        'risk': 25, 'capacity': 19, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c10',
        'status': 'active', 'count': 11, 'total': 13,
        'rain': 73, 'confidence': 0.85, 'delay': 51,
        'risk': 38, 'capacity': 20, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c11',
        'status': 'pending', 'count': 12, 'total': 14,
        'rain': 80, 'confidence': 0.9, 'delay': 56,
        'risk': 51, 'capacity': 21, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c12',
        'status': 'review', 'count': 13, 'total': 15,
        'rain': 87, 'confidence': 0.35, 'delay': 61,
        'risk': 64, 'capacity': 22, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c13',
        'status': 'closed', 'count': 14, 'total': 16,
        'rain': 94, 'confidence': 0.4, 'delay': 66,
        'risk': 77, 'capacity': 23, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c14',
        'status': 'new', 'count': 15, 'total': 17,
        'rain': 101, 'confidence': 0.45, 'delay': 71,
        'risk': 90, 'capacity': 24, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c15',
        'status': 'active', 'count': 16, 'total': 18,
        'rain': 108, 'confidence': 0.5, 'delay': 76,
        'risk': 2, 'capacity': 25, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c16',
        'status': 'pending', 'count': 17, 'total': 19,
        'rain': 115, 'confidence': 0.55, 'delay': 81,
        'risk': 15, 'capacity': 26, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c17',
        'status': 'review', 'count': 1, 'total': 20,
        'rain': 122, 'confidence': 0.6, 'delay': 86,
        'risk': 28, 'capacity': 27, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c18',
        'status': 'closed', 'count': 2, 'total': 21,
        'rain': 129, 'confidence': 0.65, 'delay': 91,
        'risk': 41, 'capacity': 28, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c19',
        'status': 'new', 'count': 3, 'total': 22,
        'rain': 136, 'confidence': 0.7, 'delay': 0,
        'risk': 54, 'capacity': 29, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c20',
        'status': 'active', 'count': 4, 'total': 23,
        'rain': 143, 'confidence': 0.75, 'delay': 5,
        'risk': 67, 'capacity': 30, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c21',
        'status': 'pending', 'count': 5, 'total': 24,
        'rain': 150, 'confidence': 0.8, 'delay': 10,
        'risk': 80, 'capacity': 31, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c22',
        'status': 'review', 'count': 6, 'total': 25,
        'rain': 157, 'confidence': 0.85, 'delay': 15,
        'risk': 93, 'capacity': 32, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c23',
        'status': 'closed', 'count': 7, 'total': 3,
        'rain': 164, 'confidence': 0.9, 'delay': 20,
        'risk': 5, 'capacity': 33, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c24',
        'status': 'new', 'count': 8, 'total': 4,
        'rain': 171, 'confidence': 0.35, 'delay': 25,
        'risk': 18, 'capacity': 34, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c25',
        'status': 'active', 'count': 9, 'total': 5,
        'rain': 178, 'confidence': 0.4, 'delay': 30,
        'risk': 31, 'capacity': 35, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c26',
        'status': 'pending', 'count': 10, 'total': 6,
        'rain': 5, 'confidence': 0.45, 'delay': 35,
        'risk': 44, 'capacity': 36, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c27',
        'status': 'review', 'count': 11, 'total': 7,
        'rain': 12, 'confidence': 0.5, 'delay': 40,
        'risk': 57, 'capacity': 37, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c28',
        'status': 'closed', 'count': 12, 'total': 8,
        'rain': 19, 'confidence': 0.55, 'delay': 45,
        'risk': 70, 'capacity': 38, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c29',
        'status': 'new', 'count': 13, 'total': 9,
        'rain': 26, 'confidence': 0.6, 'delay': 50,
        'risk': 83, 'capacity': 39, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c30',
        'status': 'active', 'count': 14, 'total': 10,
        'rain': 33, 'confidence': 0.65, 'delay': 55,
        'risk': 96, 'capacity': 40, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c31',
        'status': 'pending', 'count': 15, 'total': 11,
        'rain': 40, 'confidence': 0.7, 'delay': 60,
        'risk': 8, 'capacity': 10, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c32',
        'status': 'review', 'count': 16, 'total': 12,
        'rain': 47, 'confidence': 0.75, 'delay': 65,
        'risk': 21, 'capacity': 11, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c33',
        'status': 'closed', 'count': 17, 'total': 13,
        'rain': 54, 'confidence': 0.8, 'delay': 70,
        'risk': 34, 'capacity': 12, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c34',
        'status': 'new', 'count': 1, 'total': 14,
        'rain': 61, 'confidence': 0.85, 'delay': 75,
        'risk': 47, 'capacity': 13, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c35',
        'status': 'active', 'count': 2, 'total': 15,
        'rain': 68, 'confidence': 0.9, 'delay': 80,
        'risk': 60, 'capacity': 14, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c36',
        'status': 'pending', 'count': 3, 'total': 16,
        'rain': 75, 'confidence': 0.35, 'delay': 85,
        'risk': 73, 'capacity': 15, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c37',
        'status': 'review', 'count': 4, 'total': 17,
        'rain': 82, 'confidence': 0.4, 'delay': 90,
        'risk': 86, 'capacity': 16, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c38',
        'status': 'closed', 'count': 5, 'total': 18,
        'rain': 89, 'confidence': 0.45, 'delay': 95,
        'risk': 99, 'capacity': 17, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c39',
        'status': 'new', 'count': 6, 'total': 19,
        'rain': 96, 'confidence': 0.5, 'delay': 4,
        'risk': 11, 'capacity': 18, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c40',
        'status': 'active', 'count': 7, 'total': 20,
        'rain': 103, 'confidence': 0.55, 'delay': 9,
        'risk': 24, 'capacity': 19, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c41',
        'status': 'pending', 'count': 8, 'total': 21,
        'rain': 110, 'confidence': 0.6, 'delay': 14,
        'risk': 37, 'capacity': 20, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c42',
        'status': 'review', 'count': 9, 'total': 22,
        'rain': 117, 'confidence': 0.65, 'delay': 19,
        'risk': 50, 'capacity': 21, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c43',
        'status': 'closed', 'count': 10, 'total': 23,
        'rain': 124, 'confidence': 0.7, 'delay': 24,
        'risk': 63, 'capacity': 22, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c44',
        'status': 'new', 'count': 11, 'total': 24,
        'rain': 131, 'confidence': 0.75, 'delay': 29,
        'risk': 76, 'capacity': 23, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c45',
        'status': 'active', 'count': 12, 'total': 25,
        'rain': 138, 'confidence': 0.8, 'delay': 34,
        'risk': 89, 'capacity': 24, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c46',
        'status': 'pending', 'count': 13, 'total': 3,
        'rain': 145, 'confidence': 0.85, 'delay': 39,
        'risk': 1, 'capacity': 25, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g1-c47',
        'status': 'review', 'count': 14, 'total': 4,
        'rain': 152, 'confidence': 0.9, 'delay': 44,
        'risk': 14, 'capacity': 26, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
]

class OutcomeTruthTests(unittest.TestCase):
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
                self.assertIn('outcome_truth', result["artifacts"])
                projection = result["artifacts"]['outcome_truth']
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
        projection = result["artifacts"]['outcome_truth']
        self.assertEqual(projection["stage"], 'outcome_truth')
        self.assertEqual(projection["focus"], '灾情和处置结果标签')
        self.assertIsInstance(projection["signature"], str)
        self.assertGreater(len(projection["signature"]), 20)

if __name__ == "__main__":
    unittest.main()
