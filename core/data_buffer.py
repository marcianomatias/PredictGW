"""
PredictGW — DataBuffer
Buffer circular em memória usando pandas DataFrame.
Armazena os últimos N registros de cada dispositivo para análise preditiva.
"""

import logging
import threading
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class DataBuffer:
    """
    Buffer circular thread-safe baseado em pandas DataFrame.
    Mantém os últimos N registros por dispositivo.
    """

    def __init__(self, max_size: int = 500):
        self._max_size = max_size
        self._buffers: dict[str, pd.DataFrame] = {}
        self._lock = threading.Lock()

    def append(self, device_id: str, readings: dict) -> None:
        """
        Adiciona uma leitura ao buffer do dispositivo.
        
        Args:
            device_id: ID do dispositivo
            readings: Dict de {tag_name: TagReading}
        """
        with self._lock:
            timestamp = datetime.now()
            row = {"timestamp": timestamp, "device_id": device_id}

            for tag_name, reading in readings.items():
                row[tag_name] = reading.value
                row[f"{tag_name}_quality"] = reading.quality

            new_row = pd.DataFrame([row])

            if device_id not in self._buffers:
                self._buffers[device_id] = new_row
            else:
                self._buffers[device_id] = pd.concat(
                    [self._buffers[device_id], new_row],
                    ignore_index=True,
                )

                # Manter apenas os últimos N registros
                if len(self._buffers[device_id]) > self._max_size:
                    self._buffers[device_id] = self._buffers[device_id].iloc[
                        -self._max_size:
                    ].reset_index(drop=True)

    def get_buffer(
        self, device_id: str, last_n: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Retorna o DataFrame do buffer de um dispositivo.
        
        Args:
            device_id: ID do dispositivo
            last_n: Se especificado, retorna apenas os últimos N registros
        
        Returns:
            DataFrame com as leituras
        """
        with self._lock:
            if device_id not in self._buffers:
                return pd.DataFrame()

            df = self._buffers[device_id].copy()

            if last_n is not None and len(df) > last_n:
                df = df.iloc[-last_n:].reset_index(drop=True)

            return df

    def get_tag_series(
        self, device_id: str, tag_name: str, last_n: Optional[int] = None
    ) -> pd.Series:
        """
        Retorna uma série temporal de uma tag específica.
        
        Args:
            device_id: ID do dispositivo
            tag_name: Nome da tag
            last_n: Últimos N registros
        
        Returns:
            Series indexada por timestamp
        """
        df = self.get_buffer(device_id, last_n)
        if df.empty or tag_name not in df.columns:
            return pd.Series(dtype=float)

        series = df.set_index("timestamp")[tag_name].dropna()
        return series

    def get_statistics(self, device_id: str, tag_name: str) -> dict:
        """Retorna estatísticas descritivas de uma tag."""
        series = self.get_tag_series(device_id, tag_name)
        if series.empty:
            return {}

        return {
            "count": len(series),
            "mean": round(series.mean(), 4),
            "std": round(series.std(), 4),
            "min": round(series.min(), 4),
            "max": round(series.max(), 4),
            "last": round(series.iloc[-1], 4),
            "trend": self._calculate_trend(series),
        }

    def _calculate_trend(self, series: pd.Series) -> str:
        """Calcula a tendência da série (subindo, descendo, estável)."""
        if len(series) < 10:
            return "insufficient_data"

        recent = series.iloc[-10:]
        x = np.arange(len(recent))
        slope = np.polyfit(x, recent.values, 1)[0]

        mean_val = recent.mean()
        if mean_val == 0:
            return "stable"

        relative_slope = abs(slope / mean_val)

        if relative_slope < 0.001:
            return "stable"
        elif slope > 0:
            return "rising"
        else:
            return "falling"

    def get_all_device_ids(self) -> list[str]:
        """Retorna IDs de todos os dispositivos com dados no buffer."""
        with self._lock:
            return list(self._buffers.keys())

    def get_buffer_info(self) -> dict:
        """Informações sobre o estado do buffer."""
        with self._lock:
            info = {}
            for device_id, df in self._buffers.items():
                info[device_id] = {
                    "records": len(df),
                    "max_size": self._max_size,
                    "columns": list(df.columns),
                    "memory_bytes": df.memory_usage(deep=True).sum(),
                }
            return info

    def clear(self, device_id: Optional[str] = None) -> None:
        """Limpa o buffer de um dispositivo ou todos."""
        with self._lock:
            if device_id:
                self._buffers.pop(device_id, None)
            else:
                self._buffers.clear()

    def export_for_r(self, device_id: str, tag_name: str) -> dict:
        """
        Exporta dados no formato esperado pelo script R.
        
        Returns:
            Dict com 'timestamps' (list[str]) e 'values' (list[float])
        """
        series = self.get_tag_series(device_id, tag_name)
        if series.empty:
            return {"timestamps": [], "values": []}

        return {
            "timestamps": [
                ts.strftime("%Y-%m-%d %H:%M:%S") for ts in series.index
            ],
            "values": series.values.tolist(),
        }
