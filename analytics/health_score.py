"""
PredictGW — Health Score Calculator
Calcula e gerencia o Health Score de cada dispositivo.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class HealthScoreResult:
    """Resultado do cálculo de Health Score para um dispositivo."""

    def __init__(self, result: dict):
        health = result.get("health", {})
        self.score: float = health.get("score", 0)
        self.classification: str = health.get("classification", "Desconhecido")
        self.color: str = health.get("color", "#6b7280")
        self.components: dict = health.get("components", {})
        self.rul_hours: Optional[float] = health.get("rul_hours")
        self.anomaly_count: int = health.get("anomaly_count", 0)

        # Full analysis results
        self.anomalies: dict = result.get("anomalies", {})
        self.rul: dict = result.get("rul", {})
        self.engine: str = result.get("engine", "unknown")
        self.data_points: int = result.get("data_points", 0)

    @property
    def rul_text(self) -> str:
        """Texto legível para o RUL."""
        if self.rul_hours is None or self.rul_hours == float("inf"):
            return "Sem risco previsto"
        elif self.rul_hours <= 0:
            return "⚠️ LIMITE EXCEDIDO"
        elif self.rul_hours < 1:
            return f"🔴 {int(self.rul_hours * 60)} min"
        elif self.rul_hours < 24:
            return f"🟠 {self.rul_hours:.1f} horas"
        elif self.rul_hours < 72:
            return f"🟡 {self.rul_hours / 24:.1f} dias"
        else:
            return f"🟢 {self.rul_hours / 24:.0f} dias"

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "classification": self.classification,
            "color": self.color,
            "components": self.components,
            "rul_hours": self.rul_hours,
            "rul_text": self.rul_text,
            "anomaly_count": self.anomaly_count,
            "engine": self.engine,
            "data_points": self.data_points,
        }


class HealthScoreManager:
    """Gerencia os Health Scores de todos os dispositivos."""

    def __init__(self):
        self._scores: dict[str, HealthScoreResult] = {}

    def update(self, device_id: str, analysis_result: dict) -> HealthScoreResult:
        """Atualiza o Health Score de um dispositivo."""
        result = HealthScoreResult(analysis_result)
        self._scores[device_id] = result
        return result

    def get_score(self, device_id: str) -> Optional[HealthScoreResult]:
        """Retorna o último Health Score de um dispositivo."""
        return self._scores.get(device_id)

    def get_all_scores(self) -> dict[str, HealthScoreResult]:
        """Retorna todos os Health Scores."""
        return dict(self._scores)

    def get_overall_score(self) -> float:
        """Retorna o score médio do sistema."""
        if not self._scores:
            return 100.0
        scores = [s.score for s in self._scores.values()]
        return round(sum(scores) / len(scores), 1)

    def get_worst_device(self) -> Optional[tuple[str, HealthScoreResult]]:
        """Retorna o dispositivo em pior estado."""
        if not self._scores:
            return None
        worst = min(self._scores.items(), key=lambda x: x[1].score)
        return worst
