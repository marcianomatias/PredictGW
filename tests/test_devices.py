"""
PredictGW — Tests for Device Abstraction and Buffer.
"""

import sys
import os
import time
import unittest
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.base_device import TagConfig, TagLimit, TagReading, DeviceStatus
from core.data_buffer import DataBuffer
from core.simulator import SimulatedInverterDevice, SimulatedPLCDevice


# Sample device configs for testing
INVERTER_CONFIG = {
    "id": "test_inverter",
    "name": "Test Inverter",
    "type": "inverter",
    "protocol": "json_http",
    "connection": {"host": "localhost", "port": 80},
    "poll_interval_ms": 100,
    "tags": [
        {
            "name": "Corrente",
            "unit": "A",
            "key": "current",
            "limits": {
                "warning_low": 0.5,
                "warning_high": 1.8,
                "critical_low": 0.2,
                "critical_high": 2.5,
                "hysteresis": 0.05,
            },
        },
        {
            "name": "Frequência",
            "unit": "Hz",
            "key": "frequency",
            "limits": {
                "warning_low": 45.0,
                "warning_high": 62.0,
                "critical_low": 40.0,
                "critical_high": 65.0,
            },
        },
    ],
    "predictive": {
        "target_tag": "Corrente",
        "critical_limit": 2.5,
        "model": "prophet",
        "anomaly_method": "isolation_forest",
    },
}

PLC_CONFIG = {
    "id": "test_plc",
    "name": "Test PLC",
    "type": "plc",
    "protocol": "modbus_tcp",
    "connection": {"host": "localhost", "port": 502, "unit_id": 1},
    "poll_interval_ms": 100,
    "tags": [
        {"name": "Sensor 1", "type": "digital_input", "register_type": "discrete_input", "address": 0},
        {"name": "Motor 1", "type": "digital_output", "register_type": "coil", "address": 0},
        {
            "name": "Pressão",
            "type": "analog",
            "unit": "bar",
            "register_type": "input_register",
            "address": 0,
            "scale": 0.1,
            "limits": {"warning_high": 8.0, "critical_high": 10.0},
        },
    ],
    "predictive": {
        "target_tag": "Pressão",
        "critical_limit": 10.0,
        "model": "arima",
        "anomaly_method": "stl",
    },
}


class TestTagLimit(unittest.TestCase):
    def test_normal(self):
        limit = TagLimit({
            "warning_low": 1.0,
            "warning_high": 5.0,
            "critical_low": 0.5,
            "critical_high": 6.0,
        })
        self.assertEqual(limit.evaluate(3.0), "normal")

    def test_warning_high(self):
        limit = TagLimit({"warning_high": 5.0, "critical_high": 6.0})
        self.assertEqual(limit.evaluate(5.5), "warning_high")

    def test_critical_high(self):
        limit = TagLimit({"warning_high": 5.0, "critical_high": 6.0})
        self.assertEqual(limit.evaluate(7.0), "critical_high")

    def test_none_value(self):
        limit = TagLimit({"warning_high": 5.0})
        self.assertEqual(limit.evaluate(None), "unknown")


class TestSimulatedInverter(unittest.TestCase):
    def setUp(self):
        self.device = SimulatedInverterDevice(INVERTER_CONFIG)

    def test_connect(self):
        self.assertTrue(self.device.connect())

    def test_read_tags(self):
        self.device.connect()
        readings = self.device.read_tags()
        self.assertIn("Corrente", readings)
        self.assertIn("Frequência", readings)
        self.assertIsNotNone(readings["Corrente"].value)
        self.assertEqual(readings["Corrente"].quality, "good")

    def test_device_info(self):
        info = self.device.device_info
        self.assertEqual(info["id"], "test_inverter")
        self.assertEqual(info["type"], "inverter")

    def test_multiple_reads_produce_variation(self):
        self.device.connect()
        values = []
        for _ in range(10):
            readings = self.device.read_tags()
            values.append(readings["Corrente"].value)
        # Values should not all be identical
        self.assertTrue(len(set(values)) > 1)


class TestSimulatedPLC(unittest.TestCase):
    def setUp(self):
        self.device = SimulatedPLCDevice(PLC_CONFIG)

    def test_connect(self):
        self.assertTrue(self.device.connect())

    def test_read_tags(self):
        self.device.connect()
        readings = self.device.read_tags()
        self.assertIn("Sensor 1", readings)
        self.assertIn("Motor 1", readings)
        self.assertIn("Pressão", readings)

    def test_digital_values_are_binary(self):
        self.device.connect()
        readings = self.device.read_tags()
        for tag_name, reading in readings.items():
            tag_cfg = next(
                (t for t in self.device.tags if t.name == tag_name), None
            )
            if tag_cfg and tag_cfg.tag_type in ("digital_input", "digital_output"):
                self.assertIn(reading.value, [0.0, 1.0])


class TestDataBuffer(unittest.TestCase):
    def setUp(self):
        self.buffer = DataBuffer(max_size=100)

    def test_append_and_get(self):
        readings = {
            "Corrente": TagReading("Corrente", 1.5, "A"),
            "Freq": TagReading("Freq", 60.0, "Hz"),
        }
        self.buffer.append("dev1", readings)
        df = self.buffer.get_buffer("dev1")
        self.assertEqual(len(df), 1)
        self.assertIn("Corrente", df.columns)

    def test_circular_behavior(self):
        self.buffer = DataBuffer(max_size=5)
        for i in range(10):
            readings = {"val": TagReading("val", float(i), "")}
            self.buffer.append("dev1", readings)

        df = self.buffer.get_buffer("dev1")
        self.assertEqual(len(df), 5)
        self.assertEqual(df["val"].iloc[0], 5.0)
        self.assertEqual(df["val"].iloc[-1], 9.0)

    def test_get_tag_series(self):
        for i in range(20):
            readings = {"Corrente": TagReading("Corrente", 1.0 + i * 0.1, "A")}
            self.buffer.append("dev1", readings)

        series = self.buffer.get_tag_series("dev1", "Corrente")
        self.assertEqual(len(series), 20)

    def test_statistics(self):
        for i in range(20):
            readings = {"Corrente": TagReading("Corrente", 1.0 + i * 0.1, "A")}
            self.buffer.append("dev1", readings)

        stats = self.buffer.get_statistics("dev1", "Corrente")
        self.assertIn("mean", stats)
        self.assertIn("std", stats)
        self.assertIn("trend", stats)
        self.assertEqual(stats["trend"], "rising")

    def test_export_for_r(self):
        for i in range(5):
            readings = {"val": TagReading("val", float(i), "")}
            self.buffer.append("dev1", readings)

        export = self.buffer.export_for_r("dev1", "val")
        self.assertEqual(len(export["timestamps"]), 5)
        self.assertEqual(len(export["values"]), 5)

    def test_empty_buffer(self):
        df = self.buffer.get_buffer("nonexistent")
        self.assertTrue(df.empty)


class TestPolling(unittest.TestCase):
    def test_inverter_polling(self):
        device = SimulatedInverterDevice(INVERTER_CONFIG)
        device.start_polling()
        time.sleep(0.5)  # Wait for a few polls
        self.assertTrue(device.is_online)
        self.assertGreater(device._total_polls, 0)
        device.stop_polling()

    def test_plc_polling(self):
        device = SimulatedPLCDevice(PLC_CONFIG)
        device.start_polling()
        time.sleep(0.5)
        self.assertTrue(device.is_online)
        device.stop_polling()


if __name__ == "__main__":
    unittest.main()
