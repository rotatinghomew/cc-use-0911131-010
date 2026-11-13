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
        'name': 'warning_threshold_lab-g2-c00',
        'status': 'pending', 'count': 1, 'total': 3,
        'rain': 6, 'confidence': 0.35, 'delay': 2,
        'risk': 18, 'capacity': 10, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c01',
        'status': 'review', 'count': 2, 'total': 4,
        'rain': 13, 'confidence': 0.4, 'delay': 7,
        'risk': 31, 'capacity': 11, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c02',
        'status': 'closed', 'count': 3, 'total': 5,
        'rain': 20, 'confidence': 0.45, 'delay': 12,
        'risk': 44, 'capacity': 12, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c03',
        'status': 'new', 'count': 4, 'total': 6,
        'rain': 27, 'confidence': 0.5, 'delay': 17,
        'risk': 57, 'capacity': 13, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c04',
        'status': 'active', 'count': 5, 'total': 7,
        'rain': 34, 'confidence': 0.55, 'delay': 22,
        'risk': 70, 'capacity': 14, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c05',
        'status': 'pending', 'count': 6, 'total': 8,
        'rain': 41, 'confidence': 0.6, 'delay': 27,
        'risk': 83, 'capacity': 15, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c06',
        'status': 'review', 'count': 7, 'total': 9,
        'rain': 48, 'confidence': 0.65, 'delay': 32,
        'risk': 96, 'capacity': 16, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c07',
        'status': 'closed', 'count': 8, 'total': 10,
        'rain': 55, 'confidence': 0.7, 'delay': 37,
        'risk': 8, 'capacity': 17, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c08',
        'status': 'new', 'count': 9, 'total': 11,
        'rain': 62, 'confidence': 0.75, 'delay': 42,
        'risk': 21, 'capacity': 18, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c09',
        'status': 'active', 'count': 10, 'total': 12,
        'rain': 69, 'confidence': 0.8, 'delay': 47,
        'risk': 34, 'capacity': 19, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c10',
        'status': 'pending', 'count': 11, 'total': 13,
        'rain': 76, 'confidence': 0.85, 'delay': 52,
        'risk': 47, 'capacity': 20, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c11',
        'status': 'review', 'count': 12, 'total': 14,
        'rain': 83, 'confidence': 0.9, 'delay': 57,
        'risk': 60, 'capacity': 21, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c12',
        'status': 'closed', 'count': 13, 'total': 15,
        'rain': 90, 'confidence': 0.35, 'delay': 62,
        'risk': 73, 'capacity': 22, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c13',
        'status': 'new', 'count': 14, 'total': 16,
        'rain': 97, 'confidence': 0.4, 'delay': 67,
        'risk': 86, 'capacity': 23, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c14',
        'status': 'active', 'count': 15, 'total': 17,
        'rain': 104, 'confidence': 0.45, 'delay': 72,
        'risk': 99, 'capacity': 24, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c15',
        'status': 'pending', 'count': 16, 'total': 18,
        'rain': 111, 'confidence': 0.5, 'delay': 77,
        'risk': 11, 'capacity': 25, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c16',
        'status': 'review', 'count': 17, 'total': 19,
        'rain': 118, 'confidence': 0.55, 'delay': 82,
        'risk': 24, 'capacity': 26, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c17',
        'status': 'closed', 'count': 1, 'total': 20,
        'rain': 125, 'confidence': 0.6, 'delay': 87,
        'risk': 37, 'capacity': 27, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c18',
        'status': 'new', 'count': 2, 'total': 21,
        'rain': 132, 'confidence': 0.65, 'delay': 92,
        'risk': 50, 'capacity': 28, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c19',
        'status': 'active', 'count': 3, 'total': 22,
        'rain': 139, 'confidence': 0.7, 'delay': 1,
        'risk': 63, 'capacity': 29, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c20',
        'status': 'pending', 'count': 4, 'total': 23,
        'rain': 146, 'confidence': 0.75, 'delay': 6,
        'risk': 76, 'capacity': 30, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c21',
        'status': 'review', 'count': 5, 'total': 24,
        'rain': 153, 'confidence': 0.8, 'delay': 11,
        'risk': 89, 'capacity': 31, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c22',
        'status': 'closed', 'count': 6, 'total': 25,
        'rain': 160, 'confidence': 0.85, 'delay': 16,
        'risk': 1, 'capacity': 32, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c23',
        'status': 'new', 'count': 7, 'total': 3,
        'rain': 167, 'confidence': 0.9, 'delay': 21,
        'risk': 14, 'capacity': 33, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c24',
        'status': 'active', 'count': 8, 'total': 4,
        'rain': 174, 'confidence': 0.35, 'delay': 26,
        'risk': 27, 'capacity': 34, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c25',
        'status': 'pending', 'count': 9, 'total': 5,
        'rain': 1, 'confidence': 0.4, 'delay': 31,
        'risk': 40, 'capacity': 35, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c26',
        'status': 'review', 'count': 10, 'total': 6,
        'rain': 8, 'confidence': 0.45, 'delay': 36,
        'risk': 53, 'capacity': 36, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c27',
        'status': 'closed', 'count': 11, 'total': 7,
        'rain': 15, 'confidence': 0.5, 'delay': 41,
        'risk': 66, 'capacity': 37, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c28',
        'status': 'new', 'count': 12, 'total': 8,
        'rain': 22, 'confidence': 0.55, 'delay': 46,
        'risk': 79, 'capacity': 38, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c29',
        'status': 'active', 'count': 13, 'total': 9,
        'rain': 29, 'confidence': 0.6, 'delay': 51,
        'risk': 92, 'capacity': 39, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c30',
        'status': 'pending', 'count': 14, 'total': 10,
        'rain': 36, 'confidence': 0.65, 'delay': 56,
        'risk': 4, 'capacity': 40, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c31',
        'status': 'review', 'count': 15, 'total': 11,
        'rain': 43, 'confidence': 0.7, 'delay': 61,
        'risk': 17, 'capacity': 10, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c32',
        'status': 'closed', 'count': 16, 'total': 12,
        'rain': 50, 'confidence': 0.75, 'delay': 66,
        'risk': 30, 'capacity': 11, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c33',
        'status': 'new', 'count': 17, 'total': 13,
        'rain': 57, 'confidence': 0.8, 'delay': 71,
        'risk': 43, 'capacity': 12, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c34',
        'status': 'active', 'count': 1, 'total': 14,
        'rain': 64, 'confidence': 0.85, 'delay': 76,
        'risk': 56, 'capacity': 13, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c35',
        'status': 'pending', 'count': 2, 'total': 15,
        'rain': 71, 'confidence': 0.9, 'delay': 81,
        'risk': 69, 'capacity': 14, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c36',
        'status': 'review', 'count': 3, 'total': 16,
        'rain': 78, 'confidence': 0.35, 'delay': 86,
        'risk': 82, 'capacity': 15, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c37',
        'status': 'closed', 'count': 4, 'total': 17,
        'rain': 85, 'confidence': 0.4, 'delay': 91,
        'risk': 95, 'capacity': 16, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c38',
        'status': 'new', 'count': 5, 'total': 18,
        'rain': 92, 'confidence': 0.45, 'delay': 0,
        'risk': 7, 'capacity': 17, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c39',
        'status': 'active', 'count': 6, 'total': 19,
        'rain': 99, 'confidence': 0.5, 'delay': 5,
        'risk': 20, 'capacity': 18, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c40',
        'status': 'pending', 'count': 7, 'total': 20,
        'rain': 106, 'confidence': 0.55, 'delay': 10,
        'risk': 33, 'capacity': 19, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c41',
        'status': 'review', 'count': 8, 'total': 21,
        'rain': 113, 'confidence': 0.6, 'delay': 15,
        'risk': 46, 'capacity': 20, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c42',
        'status': 'closed', 'count': 9, 'total': 22,
        'rain': 120, 'confidence': 0.65, 'delay': 20,
        'risk': 59, 'capacity': 21, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c43',
        'status': 'new', 'count': 10, 'total': 23,
        'rain': 127, 'confidence': 0.7, 'delay': 25,
        'risk': 72, 'capacity': 22, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c44',
        'status': 'active', 'count': 11, 'total': 24,
        'rain': 134, 'confidence': 0.75, 'delay': 30,
        'risk': 85, 'capacity': 23, 'zone': 'town',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c45',
        'status': 'pending', 'count': 12, 'total': 25,
        'rain': 141, 'confidence': 0.8, 'delay': 35,
        'risk': 98, 'capacity': 24, 'zone': 'village',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c46',
        'status': 'review', 'count': 13, 'total': 3,
        'rain': 148, 'confidence': 0.85, 'delay': 40,
        'risk': 10, 'capacity': 25, 'zone': 'mountain',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
    {
        'name': 'warning_threshold_lab-g2-c47',
        'status': 'closed', 'count': 14, 'total': 4,
        'rain': 155, 'confidence': 0.9, 'delay': 45,
        'risk': 23, 'capacity': 26, 'zone': 'river',
        'expected_project': 'warning_threshold_lab', 'expected_artifacts': 9,
    },
]

class WarningScorecardTests(unittest.TestCase):
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
                self.assertIn('warning_scorecard', result["artifacts"])
                projection = result["artifacts"]['warning_scorecard']
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
        projection = result["artifacts"]['warning_scorecard']
        self.assertEqual(projection["stage"], 'warning_scorecard')
        self.assertEqual(projection["focus"], '命中漏报误报指标')
        self.assertIsInstance(projection["signature"], str)
        self.assertGreater(len(projection["signature"]), 20)

if __name__ == "__main__":
    unittest.main()
