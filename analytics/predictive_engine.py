"""
PredictGW — Predictive Engine
Orquestrador que executa o pipeline preditivo periodicamente.
"""

import logging
import threading
import time
from typing import Optional

from core.data_buffer import DataBuffer
from core.device_manager import DeviceManager
from analytics.r_bridge import RBridge
from analytics.health_score import HealthScoreManager, HealthScoreResult

logger = logging.getLogger(__name__)


class PredictiveEngine:
    """
    Motor preditivo que executa análises periódicas em todos os dispositivos.
    Pipeline: DataBuffer → R Bridge (ou Python) → Health Score
    """

    def __init__(
        self,
        device_manager: DeviceManager,
        r_engine: str = "auto",
        interval_s: int = 30,
    ):
        self._dm = device_manager
        self._bridge = RBridge(r_engine=r_engine)
        self._health_manager = HealthScoreManager()
        self._interval_s = interval_s
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_results: dict[str, dict] = {}
        self._lock = threading.Lock()

    @property
    def health_manager(self) -> HealthScoreManager:
        return self._health_manager

    @property
    def bridge(self) -> RBridge:
        return self._bridge

    @property
    def last_results(self) -> dict:
        with self._lock:
            return dict(self._last_results)

    def start(self) -> None:
        """Inicia o motor preditivo."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._analysis_loop,
            name="predictive-engine",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"🧠 Motor Preditivo iniciado "
            f"(engine={self._bridge.engine}, "
            f"intervalo={self._interval_s}s)"
        )

    def stop(self) -> None:
        """Para o motor preditivo."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        logger.info("⏹ Motor Preditivo parado.")

    def _analysis_loop(self) -> None:
        """Loop principal de análise."""
        while self._running:
            try:
                self._run_analysis_cycle()
            except Exception as e:
                logger.error(f"Erro no ciclo de análise: {e}")

            time.sleep(self._interval_s)

    def _run_analysis_cycle(self) -> None:
        """Executa um ciclo completo de análise em todos os dispositivos."""
        buffer = self._dm.buffer
        devices = self._dm.devices

        for dev_id, device in devices.items():
            if not device.is_online:
                continue

            predictive_cfg = device.predictive_config
            if not predictive_cfg:
                continue

            target_tag = predictive_cfg.get("target_tag")
            critical_limit = predictive_cfg.get("critical_limit")
            anomaly_method = predictive_cfg.get(
                "anomaly_method", "isolation_forest"
            )
            rul_method = predictive_cfg.get("model", "prophet")
            lookback = predictive_cfg.get("lookback_window", 200)

            if not target_tag or critical_limit is None:
                continue

            # Obter dados do buffer
            data = buffer.export_for_r(dev_id, target_tag)
            if len(data["values"]) < 30:
                logger.debug(
                    f"[{dev_id}] Dados insuficientes para análise "
                    f"({len(data['values'])} pontos)"
                )
                continue

            # Limitar ao lookback window
            values = data["values"][-lookback:]
            timestamps = data["timestamps"][-lookback:]

            try:
                # Executar pipeline completo
                result = self._bridge.run_full_analysis(
                    timestamps=timestamps,
                    values=values,
                    critical_limit=critical_limit,
                    anomaly_method=anomaly_method,
                    rul_method=rul_method,
                    uptime_ratio=device.uptime_ratio,
                )

                # Atualizar Health Score
                health_result = self._health_manager.update(dev_id, result)

                with self._lock:
                    self._last_results[dev_id] = result

                logger.info(
                    f"[{dev_id}] Health Score: {health_result.score} "
                    f"({health_result.classification}) — "
                    f"RUL: {health_result.rul_text}"
                )

            except Exception as e:
                logger.error(
                    f"[{dev_id}] Erro na análise preditiva: {e}"
                )

    def run_single_analysis(self, device_id: str) -> Optional[dict]:
        """Executa análise sob demanda para um dispositivo específico."""
        device = self._dm.get_device(device_id)
        if not device:
            return None

        buffer = self._dm.buffer
        predictive_cfg = device.predictive_config

        target_tag = predictive_cfg.get("target_tag", "")
        critical_limit = predictive_cfg.get("critical_limit", 100)
        anomaly_method = predictive_cfg.get(
            "anomaly_method", "isolation_forest"
        )
        rul_method = predictive_cfg.get("model", "prophet")

        data = buffer.export_for_r(device_id, target_tag)
        if len(data["values"]) < 10:
            return {"status": "insufficient_data", "points": len(data["values"])}

        result = self._bridge.run_full_analysis(
            timestamps=data["timestamps"],
            values=data["values"],
            critical_limit=critical_limit,
            anomaly_method=anomaly_method,
            rul_method=rul_method,
            uptime_ratio=device.uptime_ratio,
        )

        self._health_manager.update(device_id, result)

        with self._lock:
            self._last_results[device_id] = result

        return result

    def get_status(self) -> dict:
        """Status do motor preditivo."""
        return {
            "running": self._running,
            "engine": self._bridge.engine,
            "interval_s": self._interval_s,
            "devices_analyzed": len(self._last_results),
            "overall_health": self._health_manager.get_overall_score(),
            "r_status": self._bridge.status(),
        }
