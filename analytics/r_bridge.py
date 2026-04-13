"""
PredictGW — R Bridge
Integração Python → R via rpy2, com fallback Python puro.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Caminho do script R
R_SCRIPT_PATH = str(
    Path(__file__).parent / "predictive_models.R"
)


class RBridge:
    """
    Bridge entre Python e R usando rpy2.
    Se R ou rpy2 não estiverem disponíveis, usa fallback Python
    (scikit-learn + statsmodels).
    """

    def __init__(self, r_engine: str = "auto"):
        """
        Args:
            r_engine: "r" = forçar R, "python" = forçar Python, "auto" = tentar R
        """
        self._r_available = False
        self._r_engine = r_engine
        self._r_session = None

        if r_engine != "python":
            self._try_init_r()

        if not self._r_available:
            logger.info(
                "R não disponível. Usando fallback Python "
                "(scikit-learn + statsmodels)."
            )

    def _try_init_r(self) -> None:
        """Tenta inicializar o R via rpy2."""
        try:
            import rpy2.robjects as ro
            from rpy2.robjects import pandas2ri

            pandas2ri.activate()

            # Carregar o script R
            if os.path.exists(R_SCRIPT_PATH):
                ro.r.source(R_SCRIPT_PATH)
                self._r_session = ro
                self._r_available = True
                logger.info("✅ R Engine inicializado via rpy2.")
            else:
                logger.warning(
                    f"Script R não encontrado: {R_SCRIPT_PATH}"
                )
        except ImportError:
            logger.info("rpy2 não instalado.")
        except Exception as e:
            logger.warning(f"Erro ao inicializar R: {e}")

    @property
    def engine(self) -> str:
        return "r" if self._r_available else "python"

    def status(self) -> dict:
        return {
            "engine": self.engine,
            "r_available": self._r_available,
            "r_script_path": R_SCRIPT_PATH,
            "r_script_exists": os.path.exists(R_SCRIPT_PATH),
        }

    # ============================================================
    # Detecção de Anomalias
    # ============================================================

    def detect_anomalies(
        self,
        values: list[float],
        method: str = "isolation_forest",
    ) -> dict:
        """
        Detecta anomalias nos dados.
        
        Args:
            values: Lista de leituras da variável
            method: "isolation_forest" ou "stl"
        
        Returns:
            Dict com scores, is_anomaly, anomaly_count, method, status
        """
        if self._r_available:
            return self._detect_anomalies_r(values, method)
        else:
            return self._detect_anomalies_python(values, method)

    def _detect_anomalies_r(
        self, values: list[float], method: str
    ) -> dict:
        """Executa detecção de anomalias no R."""
        try:
            ro = self._r_session
            r_values = ro.FloatVector(values)
            result = ro.r["detect_anomalies"](r_values, method=method)
            return self._r_list_to_dict(result)
        except Exception as e:
            logger.error(f"Erro no R (anomalias): {e}")
            return self._detect_anomalies_python(values, method)

    def _detect_anomalies_python(
        self, values: list[float], method: str
    ) -> dict:
        """Fallback Python: Isolation Forest via scikit-learn."""
        arr = np.array(values)

        if len(arr) < 20:
            return {
                "scores": [0.0] * len(arr),
                "is_anomaly": [False] * len(arr),
                "anomaly_count": 0,
                "method": f"{method}_python_fallback",
                "status": "insufficient_data",
            }

        try:
            if method == "isolation_forest":
                from sklearn.ensemble import IsolationForest

                model = IsolationForest(
                    n_estimators=100,
                    contamination=0.05,
                    random_state=42,
                )
                X = arr.reshape(-1, 1)
                model.fit(X)
                scores = -model.score_samples(X)
                predictions = model.predict(X)
                is_anomaly = (predictions == -1).tolist()

                return {
                    "scores": scores.tolist(),
                    "is_anomaly": is_anomaly,
                    "anomaly_count": sum(is_anomaly),
                    "method": "isolation_forest_sklearn",
                    "status": "success",
                }
            else:
                # STL fallback via statsmodels
                return self._stl_python(arr)

        except ImportError:
            return self._zscore_fallback(arr)
        except Exception as e:
            logger.error(f"Erro Python (anomalias): {e}")
            return self._zscore_fallback(arr)

    def _stl_python(self, arr: np.ndarray) -> dict:
        """STL decomposition via statsmodels."""
        try:
            from statsmodels.tsa.seasonal import STL

            period = min(60, len(arr) // 3)
            if period < 2:
                return self._zscore_fallback(arr)

            result = STL(arr, period=period).fit()
            remainder = result.resid
            threshold = 2.5 * np.nanstd(remainder)
            is_anomaly = (np.abs(remainder) > threshold).tolist()

            return {
                "trend": result.trend.tolist(),
                "seasonal": result.seasonal.tolist(),
                "remainder": remainder.tolist(),
                "is_anomaly": is_anomaly,
                "anomaly_count": sum(is_anomaly),
                "threshold": float(threshold),
                "method": "stl_statsmodels",
                "status": "success",
            }
        except Exception:
            return self._zscore_fallback(arr)

    def _zscore_fallback(self, arr: np.ndarray) -> dict:
        """Fallback final: Z-score."""
        mean = np.mean(arr)
        std = np.std(arr)

        if std == 0:
            return {
                "scores": [0.0] * len(arr),
                "is_anomaly": [False] * len(arr),
                "anomaly_count": 0,
                "method": "zscore_fallback",
                "status": "success",
            }

        z_scores = np.abs((arr - mean) / std)
        is_anomaly = (z_scores > 2.5).tolist()

        return {
            "scores": z_scores.tolist(),
            "is_anomaly": is_anomaly,
            "anomaly_count": sum(is_anomaly),
            "threshold": 2.5,
            "method": "zscore_fallback",
            "status": "success",
        }

    # ============================================================
    # Previsão de RUL
    # ============================================================

    def predict_rul(
        self,
        timestamps: list[str],
        values: list[float],
        critical_limit: float,
        method: str = "prophet",
        horizon_hours: int = 72,
    ) -> dict:
        """
        Prevê o Remaining Useful Life (RUL).
        
        Args:
            timestamps: Lista de timestamps ISO
            values: Lista de leituras
            critical_limit: Limite crítico superior
            method: "prophet" ou "arima"
            horizon_hours: Horizonte de previsão
        
        Returns:
            Dict com rul_hours, failure_timestamp, confidence, etc.
        """
        if self._r_available:
            return self._predict_rul_r(
                timestamps, values, critical_limit, method, horizon_hours
            )
        else:
            return self._predict_rul_python(
                timestamps, values, critical_limit, method, horizon_hours
            )

    def _predict_rul_r(
        self,
        timestamps: list[str],
        values: list[float],
        critical_limit: float,
        method: str,
        horizon_hours: int,
    ) -> dict:
        """Executa previsão de RUL no R."""
        try:
            ro = self._r_session
            ts_json = json.dumps(timestamps)
            val_json = json.dumps(values)

            result_json = ro.r["predict_rul"](
                ro.r["fromJSON"](ts_json),
                ro.FloatVector(values),
                critical_limit,
                method=method,
            )
            return json.loads(str(result_json[0]))
        except Exception as e:
            logger.error(f"Erro no R (RUL): {e}")
            return self._predict_rul_python(
                timestamps, values, critical_limit, method, horizon_hours
            )

    def _predict_rul_python(
        self,
        timestamps: list[str],
        values: list[float],
        critical_limit: float,
        method: str,
        horizon_hours: int,
    ) -> dict:
        """Fallback Python: regressão linear + ARIMA (statsmodels)."""
        arr = np.array(values)

        if len(arr) < 30:
            return {
                "rul_hours": None,
                "failure_timestamp": None,
                "confidence": 0,
                "method": f"{method}_python_fallback",
                "status": "insufficient_data",
            }

        try:
            if method == "arima":
                return self._arima_python(
                    timestamps, arr, critical_limit, horizon_hours
                )
        except Exception:
            pass

        # Linear regression fallback
        return self._linear_rul(timestamps, arr, critical_limit)

    def _arima_python(
        self,
        timestamps: list[str],
        arr: np.ndarray,
        critical_limit: float,
        horizon_hours: int,
    ) -> dict:
        """ARIMA via statsmodels."""
        try:
            from statsmodels.tsa.arima.model import ARIMA

            model = ARIMA(arr, order=(2, 1, 1))
            fitted = model.fit()
            n_ahead = min(500, horizon_hours * 30)
            forecast = fitted.forecast(steps=n_ahead)

            breach_indices = np.where(forecast > critical_limit)[0]

            if len(breach_indices) > 0:
                steps_to_failure = breach_indices[0]
                ts_parsed = pd.to_datetime(timestamps)
                avg_interval = (
                    (ts_parsed.max() - ts_parsed.min()).total_seconds()
                    / len(timestamps)
                )
                rul_seconds = steps_to_failure * avg_interval
                rul_hours = rul_seconds / 3600
                failure_time = ts_parsed.max() + pd.Timedelta(
                    seconds=rul_seconds
                )

                return {
                    "rul_hours": round(rul_hours, 2),
                    "failure_timestamp": failure_time.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "forecast_values": forecast[:100].tolist(),
                    "critical_limit": critical_limit,
                    "confidence": 0.65,
                    "method": "arima_statsmodels",
                    "status": "failure_predicted",
                }
            else:
                return {
                    "rul_hours": float("inf"),
                    "failure_timestamp": None,
                    "forecast_values": forecast[:100].tolist(),
                    "critical_limit": critical_limit,
                    "confidence": 0.65,
                    "method": "arima_statsmodels",
                    "status": "no_failure_in_horizon",
                }
        except Exception as e:
            logger.warning(f"ARIMA falhou: {e}")
            return self._linear_rul(timestamps, arr, critical_limit)

    def _linear_rul(
        self,
        timestamps: list[str],
        arr: np.ndarray,
        critical_limit: float,
    ) -> dict:
        """Regressão linear simples para RUL."""
        x = np.arange(len(arr))
        coeffs = np.polyfit(x, arr, 1)
        slope = coeffs[0]
        current = arr[-1]

        if slope <= 0:
            return {
                "rul_hours": float("inf"),
                "failure_timestamp": None,
                "slope_per_step": float(slope),
                "confidence": 0.4,
                "method": "linear_fallback",
                "status": "no_rising_trend",
            }

        steps_to_failure = (critical_limit - current) / slope

        if steps_to_failure <= 0:
            return {
                "rul_hours": 0,
                "failure_timestamp": pd.Timestamp.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "confidence": 0.4,
                "method": "linear_fallback",
                "status": "already_exceeded",
            }

        ts_parsed = pd.to_datetime(timestamps)
        avg_interval = (
            (ts_parsed.max() - ts_parsed.min()).total_seconds()
            / len(timestamps)
        )
        rul_seconds = steps_to_failure * avg_interval
        rul_hours = rul_seconds / 3600
        failure_time = ts_parsed.max() + pd.Timedelta(seconds=rul_seconds)

        return {
            "rul_hours": round(rul_hours, 2),
            "failure_timestamp": failure_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "slope_per_step": float(slope),
            "confidence": 0.4,
            "method": "linear_fallback",
            "status": "failure_predicted",
        }

    # ============================================================
    # Pipeline Completo
    # ============================================================

    def run_full_analysis(
        self,
        timestamps: list[str],
        values: list[float],
        critical_limit: float,
        anomaly_method: str = "isolation_forest",
        rul_method: str = "prophet",
        uptime_ratio: float = 1.0,
    ) -> dict:
        """
        Pipeline completo de análise preditiva.
        
        Returns:
            Dict com anomalies, rul, health score
        """
        if self._r_available:
            try:
                return self._run_full_r(
                    timestamps, values, critical_limit,
                    anomaly_method, rul_method, uptime_ratio,
                )
            except Exception as e:
                logger.error(f"Pipeline R falhou: {e}")

        # Fallback Python
        anomalies = self.detect_anomalies(values, anomaly_method)
        rul = self.predict_rul(
            timestamps, values, critical_limit, rul_method
        )
        health = self._calculate_health_python(
            anomalies, rul, values, uptime_ratio
        )

        return {
            "anomalies": anomalies,
            "rul": rul,
            "health": health,
            "engine": self.engine,
            "data_points": len(values),
        }

    def _run_full_r(
        self,
        timestamps: list[str],
        values: list[float],
        critical_limit: float,
        anomaly_method: str,
        rul_method: str,
        uptime_ratio: float,
    ) -> dict:
        """Pipeline completo via R."""
        ro = self._r_session
        ts_json = json.dumps(timestamps)
        val_json = json.dumps(values)

        result_json = ro.r["run_predictive_analysis"](
            ts_json, val_json, critical_limit,
            anomaly_method, rul_method, uptime_ratio,
        )
        result = json.loads(str(result_json[0]))
        result["engine"] = "r"
        return result

    def _calculate_health_python(
        self,
        anomalies: dict,
        rul: dict,
        values: list[float],
        uptime_ratio: float,
    ) -> dict:
        """Calcula health score em Python."""
        arr = np.array(values)

        # Anomaly score (0-100, 100 = sem anomalias)
        total = len(anomalies.get("is_anomaly", []))
        count = anomalies.get("anomaly_count", 0)
        if total > 0:
            anomaly_ratio = count / total
            anomaly_score = max(0, (1 - anomaly_ratio * 5)) * 100
        else:
            anomaly_score = 100

        # RUL score
        rul_hours = rul.get("rul_hours")
        if rul_hours is None or rul_hours == float("inf"):
            rul_score = 100
        elif rul_hours <= 0:
            rul_score = 0
        elif rul_hours < 1:
            rul_score = 10
        elif rul_hours < 4:
            rul_score = 30
        elif rul_hours < 12:
            rul_score = 50
        elif rul_hours < 24:
            rul_score = 70
        elif rul_hours < 72:
            rul_score = 85
        else:
            rul_score = 100

        # Variance score
        mean_val = np.mean(arr) if len(arr) > 0 else 0
        if mean_val != 0 and len(arr) > 1:
            cv = np.std(arr) / abs(mean_val)
        else:
            cv = 0
        variance_score = max(0, min(100, (1 - min(1, cv)) * 100))

        # Uptime score
        uptime_score = max(0, min(100, uptime_ratio * 100))

        # Composite
        score = round(
            anomaly_score * 0.40
            + rul_score * 0.30
            + variance_score * 0.20
            + uptime_score * 0.10,
            1,
        )

        # Classification
        if score >= 85:
            classification, color = "Excelente", "#22c55e"
        elif score >= 70:
            classification, color = "Bom", "#84cc16"
        elif score >= 50:
            classification, color = "Atenção", "#eab308"
        elif score >= 30:
            classification, color = "Alerta", "#f97316"
        else:
            classification, color = "Crítico", "#ef4444"

        return {
            "score": score,
            "classification": classification,
            "color": color,
            "components": {
                "anomaly_score": round(anomaly_score, 1),
                "rul_score": round(rul_score, 1),
                "variance_score": round(variance_score, 1),
                "uptime_score": round(uptime_score, 1),
            },
            "rul_hours": rul_hours,
            "anomaly_count": count,
        }

    def _r_list_to_dict(self, r_obj) -> dict:
        """Converte objeto R (lista nomeada) para dict Python."""
        try:
            import rpy2.robjects as ro

            result = {}
            names = list(r_obj.names)
            for i, name in enumerate(names):
                val = r_obj[i]
                if isinstance(val, ro.vectors.FloatVector):
                    result[name] = list(val)
                elif isinstance(val, ro.vectors.BoolVector):
                    result[name] = [bool(v) for v in val]
                elif isinstance(val, ro.vectors.StrVector):
                    result[name] = (
                        str(val[0]) if len(val) == 1 else list(val)
                    )
                elif isinstance(val, ro.vectors.IntVector):
                    result[name] = (
                        int(val[0]) if len(val) == 1 else list(val)
                    )
                else:
                    result[name] = str(val)
            return result
        except Exception:
            return {}
