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
        'name': 'warning_threshold_lab-g0-c00',
        'status': 'new', 'count': 1, 'total': 3,
        'rain': 0, 'confidence': 0.35, 'delay': 0,
        'risk': 0, 'capacity': 10, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c01',
        'status': 'active', 'count': 2, 'total': 4,
        'rain': 7, 'confidence': 0.4, 'delay': 5,
        'risk': 13, 'capacity': 11, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c02',
        'status': 'pending', 'count': 3, 'total': 5,
        'rain': 14, 'confidence': 0.45, 'delay': 10,
        'risk': 26, 'capacity': 12, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c03',
        'status': 'review', 'count': 4, 'total': 6,
        'rain': 21, 'confidence': 0.5, 'delay': 15,
        'risk': 39, 'capacity': 13, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c04',
        'status': 'closed', 'count': 5, 'total': 7,
        'rain': 28, 'confidence': 0.55, 'delay': 20,
        'risk': 52, 'capacity': 14, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c05',
        'status': 'new', 'count': 6, 'total': 8,
        'rain': 35, 'confidence': 0.6, 'delay': 25,
        'risk': 65, 'capacity': 15, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c06',
        'status': 'active', 'count': 7, 'total': 9,
        'rain': 42, 'confidence': 0.65, 'delay': 30,
        'risk': 78, 'capacity': 16, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c07',
        'status': 'pending', 'count': 8, 'total': 10,
        'rain': 49, 'confidence': 0.7, 'delay': 35,
        'risk': 91, 'capacity': 17, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c08',
        'status': 'review', 'count': 9, 'total': 11,
        'rain': 56, 'confidence': 0.75, 'delay': 40,
        'risk': 3, 'capacity': 18, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c09',
        'status': 'closed', 'count': 10, 'total': 12,
        'rain': 63, 'confidence': 0.8, 'delay': 45,
        'risk': 16, 'capacity': 19, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c10',
        'status': 'new', 'count': 11, 'total': 13,
        'rain': 70, 'confidence': 0.85, 'delay': 50,
        'risk': 29, 'capacity': 20, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c11',
        'status': 'active', 'count': 12, 'total': 14,
        'rain': 77, 'confidence': 0.9, 'delay': 55,
        'risk': 42, 'capacity': 21, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c12',
        'status': 'pending', 'count': 13, 'total': 15,
        'rain': 84, 'confidence': 0.35, 'delay': 60,
        'risk': 55, 'capacity': 22, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c13',
        'status': 'review', 'count': 14, 'total': 16,
        'rain': 91, 'confidence': 0.4, 'delay': 65,
        'risk': 68, 'capacity': 23, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c14',
        'status': 'closed', 'count': 15, 'total': 17,
        'rain': 98, 'confidence': 0.45, 'delay': 70,
        'risk': 81, 'capacity': 24, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c15',
        'status': 'new', 'count': 16, 'total': 18,
        'rain': 105, 'confidence': 0.5, 'delay': 75,
        'risk': 94, 'capacity': 25, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c16',
        'status': 'active', 'count': 17, 'total': 19,
        'rain': 112, 'confidence': 0.55, 'delay': 80,
        'risk': 6, 'capacity': 26, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c17',
        'status': 'pending', 'count': 1, 'total': 20,
        'rain': 119, 'confidence': 0.6, 'delay': 85,
        'risk': 19, 'capacity': 27, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c18',
        'status': 'review', 'count': 2, 'total': 21,
        'rain': 126, 'confidence': 0.65, 'delay': 90,
        'risk': 32, 'capacity': 28, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c19',
        'status': 'closed', 'count': 3, 'total': 22,
        'rain': 133, 'confidence': 0.7, 'delay': 95,
        'risk': 45, 'capacity': 29, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c20',
        'status': 'new', 'count': 4, 'total': 23,
        'rain': 140, 'confidence': 0.75, 'delay': 4,
        'risk': 58, 'capacity': 30, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c21',
        'status': 'active', 'count': 5, 'total': 24,
        'rain': 147, 'confidence': 0.8, 'delay': 9,
        'risk': 71, 'capacity': 31, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c22',
        'status': 'pending', 'count': 6, 'total': 25,
        'rain': 154, 'confidence': 0.85, 'delay': 14,
        'risk': 84, 'capacity': 32, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c23',
        'status': 'review', 'count': 7, 'total': 3,
        'rain': 161, 'confidence': 0.9, 'delay': 19,
        'risk': 97, 'capacity': 33, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c24',
        'status': 'closed', 'count': 8, 'total': 4,
        'rain': 168, 'confidence': 0.35, 'delay': 24,
        'risk': 9, 'capacity': 34, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c25',
        'status': 'new', 'count': 9, 'total': 5,
        'rain': 175, 'confidence': 0.4, 'delay': 29,
        'risk': 22, 'capacity': 35, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c26',
        'status': 'active', 'count': 10, 'total': 6,
        'rain': 2, 'confidence': 0.45, 'delay': 34,
        'risk': 35, 'capacity': 36, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c27',
        'status': 'pending', 'count': 11, 'total': 7,
        'rain': 9, 'confidence': 0.5, 'delay': 39,
        'risk': 48, 'capacity': 37, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c28',
        'status': 'review', 'count': 12, 'total': 8,
        'rain': 16, 'confidence': 0.55, 'delay': 44,
        'risk': 61, 'capacity': 38, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c29',
        'status': 'closed', 'count': 13, 'total': 9,
        'rain': 23, 'confidence': 0.6, 'delay': 49,
        'risk': 74, 'capacity': 39, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c30',
        'status': 'new', 'count': 14, 'total': 10,
        'rain': 30, 'confidence': 0.65, 'delay': 54,
        'risk': 87, 'capacity': 40, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c31',
        'status': 'active', 'count': 15, 'total': 11,
        'rain': 37, 'confidence': 0.7, 'delay': 59,
        'risk': 100, 'capacity': 10, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c32',
        'status': 'pending', 'count': 16, 'total': 12,
        'rain': 44, 'confidence': 0.75, 'delay': 64,
        'risk': 12, 'capacity': 11, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c33',
        'status': 'review', 'count': 17, 'total': 13,
        'rain': 51, 'confidence': 0.8, 'delay': 69,
        'risk': 25, 'capacity': 12, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c34',
        'status': 'closed', 'count': 1, 'total': 14,
        'rain': 58, 'confidence': 0.85, 'delay': 74,
        'risk': 38, 'capacity': 13, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c35',
        'status': 'new', 'count': 2, 'total': 15,
        'rain': 65, 'confidence': 0.9, 'delay': 79,
        'risk': 51, 'capacity': 14, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c36',
        'status': 'active', 'count': 3, 'total': 16,
        'rain': 72, 'confidence': 0.35, 'delay': 84,
        'risk': 64, 'capacity': 15, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c37',
        'status': 'pending', 'count': 4, 'total': 17,
        'rain': 79, 'confidence': 0.4, 'delay': 89,
        'risk': 77, 'capacity': 16, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c38',
        'status': 'review', 'count': 5, 'total': 18,
        'rain': 86, 'confidence': 0.45, 'delay': 94,
        'risk': 90, 'capacity': 17, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c39',
        'status': 'closed', 'count': 6, 'total': 19,
        'rain': 93, 'confidence': 0.5, 'delay': 3,
        'risk': 2, 'capacity': 18, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c40',
        'status': 'new', 'count': 7, 'total': 20,
        'rain': 100, 'confidence': 0.55, 'delay': 8,
        'risk': 15, 'capacity': 19, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c41',
        'status': 'active', 'count': 8, 'total': 21,
        'rain': 107, 'confidence': 0.6, 'delay': 13,
        'risk': 28, 'capacity': 20, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c42',
        'status': 'pending', 'count': 9, 'total': 22,
        'rain': 114, 'confidence': 0.65, 'delay': 18,
        'risk': 41, 'capacity': 21, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c43',
        'status': 'review', 'count': 10, 'total': 23,
        'rain': 121, 'confidence': 0.7, 'delay': 23,
        'risk': 54, 'capacity': 22, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c44',
        'status': 'closed', 'count': 11, 'total': 24,
        'rain': 128, 'confidence': 0.75, 'delay': 28,
        'risk': 67, 'capacity': 23, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c45',
        'status': 'new', 'count': 12, 'total': 25,
        'rain': 135, 'confidence': 0.8, 'delay': 33,
        'risk': 80, 'capacity': 24, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c46',
        'status': 'active', 'count': 13, 'total': 3,
        'rain': 142, 'confidence': 0.85, 'delay': 38,
        'risk': 93, 'capacity': 25, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g0-c47',
        'status': 'pending', 'count': 14, 'total': 4,
        'rain': 149, 'confidence': 0.9, 'delay': 43,
        'risk': 5, 'capacity': 26, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
]

class EventVintageTests(unittest.TestCase):
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
                self.assertIn('event_vintage', result["artifacts"])
                projection = result["artifacts"]['event_vintage']
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
        projection = result["artifacts"]['event_vintage']
        self.assertEqual(projection["stage"], 'event_vintage')
        self.assertEqual(projection["focus"], '过程样本与数据版本')
        self.assertIsInstance(projection["signature"], str)
        self.assertGreater(len(projection["signature"]), 20)

if __name__ == "__main__":
    unittest.main()
