"""
PredictGW — BaseDevice
Classe abstrata que define a interface para todos os dispositivos industriais.
"""

import time
import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DeviceStatus:
    """Status possíveis de um dispositivo."""
    ONLINE = "online"
    OFFLINE = "offline"
    WARNING = "warning"
    ERROR = "error"
    CONNECTING = "connecting"


class TagReading:
    """Leitura individual de uma tag/registrador."""

    def __init__(self, name: str, value: Any, unit: str = "",
                 timestamp: Optional[datetime] = None,
                 quality: str = "good"):
        self.name = name
        self.value = value
        self.unit = unit
        self.timestamp = timestamp or datetime.now()
        self.quality = quality  # "good", "bad", "uncertain"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "quality": self.quality,
        }


class TagLimit:
    """Limites de histerese para uma tag."""

    def __init__(self, config: dict):
        self.warning_low = config.get("warning_low")
        self.warning_high = config.get("warning_high")
        self.critical_low = config.get("critical_low")
        self.critical_high = config.get("critical_high")
        self.hysteresis = config.get("hysteresis", 0)

    def evaluate(self, value: float) -> str:
        """Retorna o estado da leitura baseado nos limites."""
        if value is None:
            return "unknown"
        if self.critical_low is not None and value <= self.critical_low:
            return "critical_low"
        if self.critical_high is not None and value >= self.critical_high:
            return "critical_high"
        if self.warning_low is not None and value <= self.warning_low:
            return "warning_low"
        if self.warning_high is not None and value >= self.warning_high:
            return "warning_high"
        return "normal"


class TagConfig:
    """Configuração de uma tag do dispositivo."""

    def __init__(self, config: dict):
        self.name: str = config["name"]
        self.unit: str = config.get("unit", "")
        self.key: str = config.get("key", "")
        self.tag_type: str = config.get("type", "analog")
        self.register_type: str = config.get("register_type", "")
        self.address: int = config.get("address", 0)
        self.scale: float = config.get("scale", 1.0)
        self.offset: float = config.get("offset", 0.0)
        self.limits: Optional[TagLimit] = None
        if "limits" in config:
            self.limits = TagLimit(config["limits"])


class BaseDevice(ABC):
    """
    Classe base abstrata para dispositivos industriais.
    Define a interface de coleta que deve ser implementada por cada protocolo.
    """

    def __init__(self, device_config: dict):
        self.id: str = device_config["id"]
        self.name: str = device_config["name"]
        self.device_type: str = device_config["type"]
        self.protocol: str = device_config["protocol"]
        self.connection_config: dict = device_config.get("connection", {})
        self.poll_interval_ms: int = device_config.get("poll_interval_ms", 2000)
        self.predictive_config: dict = device_config.get("predictive", {})

        # Parse tags
        self.tags: list[TagConfig] = []
        for tag_cfg in device_config.get("tags", []):
            self.tags.append(TagConfig(tag_cfg))

        # State
        self._status: str = DeviceStatus.OFFLINE
        self._last_readings: dict[str, TagReading] = {}
        self._last_poll_time: Optional[datetime] = None
        self._error_count: int = 0
        self._consecutive_errors: int = 0
        self._total_polls: int = 0
        self._successful_polls: int = 0

        # Threading
        self._lock = threading.Lock()
        self._polling = False
        self._poll_thread: Optional[threading.Thread] = None

    # ---- Properties ----

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_online(self) -> bool:
        return self._status in (DeviceStatus.ONLINE, DeviceStatus.WARNING)

    @property
    def uptime_ratio(self) -> float:
        if self._total_polls == 0:
            return 0.0
        return self._successful_polls / self._total_polls

    @property
    def last_readings(self) -> dict[str, TagReading]:
        with self._lock:
            return dict(self._last_readings)

    @property
    def device_info(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.device_type,
            "protocol": self.protocol,
            "status": self._status,
            "is_online": self.is_online,
            "uptime_ratio": round(self.uptime_ratio, 4),
            "total_polls": self._total_polls,
            "successful_polls": self._successful_polls,
            "consecutive_errors": self._consecutive_errors,
            "last_poll_time": (
                self._last_poll_time.isoformat() if self._last_poll_time else None
            ),
            "tags_count": len(self.tags),
        }

    # ---- Abstract Methods ----

    @abstractmethod
    def connect(self) -> bool:
        """Estabelece conexão com o dispositivo. Retorna True se bem-sucedido."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Encerra a conexão com o dispositivo."""
        pass

    @abstractmethod
    def read_tags(self) -> dict[str, TagReading]:
        """
        Lê todas as tags configuradas do dispositivo.
        Retorna dict: {tag_name: TagReading}
        """
        pass

    # ---- Polling Engine ----

    def start_polling(self) -> None:
        """Inicia o loop de polling em thread separada."""
        if self._polling:
            logger.warning(f"[{self.id}] Polling já em execução.")
            return

        self._polling = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            name=f"poll-{self.id}",
            daemon=True,
        )
        self._poll_thread.start()
        logger.info(f"[{self.id}] Polling iniciado ({self.poll_interval_ms}ms)")

    def stop_polling(self) -> None:
        """Para o loop de polling."""
        self._polling = False
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)
        logger.info(f"[{self.id}] Polling parado.")

    def _poll_loop(self) -> None:
        """Loop principal de polling."""
        # Tenta conectar
        self._status = DeviceStatus.CONNECTING
        try:
            if self.connect():
                self._status = DeviceStatus.ONLINE
                logger.info(f"[{self.id}] Conectado com sucesso.")
            else:
                self._status = DeviceStatus.OFFLINE
                logger.warning(f"[{self.id}] Falha na conexão inicial.")
        except Exception as e:
            self._status = DeviceStatus.OFFLINE
            logger.error(f"[{self.id}] Erro ao conectar: {e}")

        while self._polling:
            try:
                self._total_polls += 1
                readings = self.read_tags()

                with self._lock:
                    self._last_readings = readings
                    self._last_poll_time = datetime.now()

                self._successful_polls += 1
                self._consecutive_errors = 0

                # Avaliar limites para determinar status
                has_warning = False
                has_critical = False
                for tag_name, reading in readings.items():
                    tag_cfg = next(
                        (t for t in self.tags if t.name == tag_name), None
                    )
                    if tag_cfg and tag_cfg.limits and reading.value is not None:
                        state = tag_cfg.limits.evaluate(reading.value)
                        if "critical" in state:
                            has_critical = True
                        elif "warning" in state:
                            has_warning = True

                if has_critical:
                    self._status = DeviceStatus.ERROR
                elif has_warning:
                    self._status = DeviceStatus.WARNING
                else:
                    self._status = DeviceStatus.ONLINE

            except Exception as e:
                self._consecutive_errors += 1
                self._error_count += 1
                logger.error(
                    f"[{self.id}] Erro no polling "
                    f"(tentativa {self._consecutive_errors}): {e}"
                )

                if self._consecutive_errors >= 5:
                    self._status = DeviceStatus.OFFLINE
                    logger.warning(
                        f"[{self.id}] Marcado como OFFLINE após "
                        f"{self._consecutive_errors} erros consecutivos."
                    )

            time.sleep(self.poll_interval_ms / 1000.0)

        # Cleanup
        try:
            self.disconnect()
        except Exception as e:
            logger.error(f"[{self.id}] Erro ao desconectar: {e}")

    def get_readings_dict(self) -> dict:
        """Retorna as últimas leituras como dict simples para serialização."""
        result = {
            "device_id": self.id,
            "device_name": self.name,
            "device_type": self.device_type,
            "status": self._status,
            "timestamp": datetime.now().isoformat(),
            "tags": {},
        }
        with self._lock:
            for tag_name, reading in self._last_readings.items():
                tag_cfg = next(
                    (t for t in self.tags if t.name == tag_name), None
                )
                tag_data = reading.to_dict()
                if tag_cfg and tag_cfg.limits:
                    tag_data["state"] = tag_cfg.limits.evaluate(reading.value)
                result["tags"][tag_name] = tag_data
        return result
