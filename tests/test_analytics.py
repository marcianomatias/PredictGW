"""
PredictGW — Tests for Analytics Pipeline.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analytics.r_bridge import RBridge
from analytics.health_score import HealthScoreResult, HealthScoreManager
import numpy as np


class TestRBridgePythonFallback(unittest.TestCase):
    """Testa o fallback Python do R Bridge."""

    def setUp(self):
        self.bridge = RBridge(r_engine="python")

    def test_engine_is_python(self):
        self.assertEqual(self.bridge.engine, "python")

    def test_detect_anomalies_insufficient_data(self):
        result = self.bridge.detect_anomalies([1.0, 2.0, 3.0])
        self.assertEqual(result["status"], "insufficient_data")

    def test_detect_anomalies_normal_data(self):
        np.random.seed(42)
        normal_data = np.random.normal(10, 0.5, 100).tolist()
        result = self.bridge.detect_anomalies(normal_data)
        self.assertIn("anomaly_count", result)
        self.assertIn("is_anomaly", result)
        # Normal data should have very few anomalies
        self.assertLess(result["anomaly_count"], 10)

    def test_detect_anomalies_with_outliers(self):
        np.random.seed(42)
        data = np.random.normal(10, 0.5, 100).tolist()
        # Inject outliers
        data[50] = 50.0
        data[75] = 55.0
        result = self.bridge.detect_anomalies(data)
        self.assertGreater(result["anomaly_count"], 0)

    def test_predict_rul_insufficient_data(self):
        result = self.bridge.predict_rul(
            ["2024-01-01 00:00:00"] * 5,
            [1.0, 1.1, 1.2, 1.3, 1.4],
            critical_limit=2.0,
        )
        self.assertEqual(result["status"], "insufficient_data")

    def test_predict_rul_rising_trend(self):
        np.random.seed(42)
        n = 100
        timestamps = [
            f"2024-01-01 {i // 60:02d}:{i % 60:02d}:00"
            for i in range(n)
        ]
        # Trending upward
        values = [1.0 + i * 0.01 + np.random.normal(0, 0.02) for i in range(n)]

        result = self.bridge.predict_rul(
            timestamps, values, critical_limit=2.5, method="arima"
        )
        self.assertIn(result["status"], [
            "failure_predicted", "no_failure_in_horizon"
        ])

    def test_predict_rul_no_rising_trend(self):
        np.random.seed(42)
        n = 50
        timestamps = [
            f"2024-01-01 {i // 60:02d}:{i % 60:02d}:00"
            for i in range(n)
        ]
        # Stable data
        values = [1.0 + np.random.normal(0, 0.01) for _ in range(n)]

        result = self.bridge.predict_rul(
            timestamps, values, critical_limit=2.5
        )
        # Should not predict failure or have long RUL
        if result.get("rul_hours"):
            self.assertTrue(
                result["rul_hours"] == float("inf")
                or result["status"] in ("no_rising_trend", "no_failure_in_horizon")
            )

    def test_full_analysis(self):
        np.random.seed(42)
        n = 100
        timestamps = [
            f"2024-01-01 {i // 60:02d}:{i % 60:02d}:00"
            for i in range(n)
        ]
        values = [1.0 + i * 0.005 + np.random.normal(0, 0.05) for i in range(n)]

        result = self.bridge.run_full_analysis(
            timestamps=timestamps,
            values=values,
            critical_limit=2.5,
        )

        self.assertIn("anomalies", result)
        self.assertIn("rul", result)
        self.assertIn("health", result)
        self.assertIn("score", result["health"])
        self.assertGreaterEqual(result["health"]["score"], 0)
        self.assertLessEqual(result["health"]["score"], 100)


class TestHealthScore(unittest.TestCase):
    def test_health_score_result(self):
        result = {
            "health": {
                "score": 85.0,
                "classification": "Excelente",
                "color": "#22c55e",
                "components": {
                    "anomaly_score": 90,
                    "rul_score": 100,
                    "variance_score": 80,
                    "uptime_score": 100,
                },
                "rul_hours": None,
                "anomaly_count": 2,
            },
            "anomalies": {},
            "rul": {},
            "engine": "python",
            "data_points": 100,
        }
        hs = HealthScoreResult(result)
        self.assertEqual(hs.score, 85.0)
        self.assertEqual(hs.classification, "Excelente")
        self.assertEqual(hs.rul_text, "Sem risco previsto")

    def test_health_manager(self):
        manager = HealthScoreManager()
        result = {
            "health": {
                "score": 45.0,
                "classification": "Atenção",
                "color": "#eab308",
                "components": {},
                "rul_hours": 5.5,
                "anomaly_count": 10,
            },
            "anomalies": {},
            "rul": {},
        }
        hs = manager.update("dev1", result)
        self.assertEqual(hs.score, 45.0)

        retrieved = manager.get_score("dev1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.score, 45.0)

    def test_overall_score(self):
        manager = HealthScoreManager()
        for dev_id, score in [("d1", 80), ("d2", 60), ("d3", 90)]:
            result = {
                "health": {
                    "score": score,
                    "classification": "",
                    "color": "",
                    "components": {},
                    "rul_hours": None,
                    "anomaly_count": 0,
                },
                "anomalies": {},
                "rul": {},
            }
            manager.update(dev_id, result)

        overall = manager.get_overall_score()
        self.assertAlmostEqual(overall, 76.7, places=1)


if __name__ == "__main__":
    unittest.main()
