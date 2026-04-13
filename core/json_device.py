"""
PredictGW — JSONDevice
Implementação para inversores via HTTP/JSON (ESP32).
"""

import logging
from datetime import datetime
from typing import Optional

import requests

from core.base_device import BaseDevice, TagReading

logger = logging.getLogger(__name__)


class JSONDevice(BaseDevice):
    """
    Dispositivo que coleta dados via HTTP GET retornando JSON.
    Típico para inversores com ESP32 embarcado.
    """

    def __init__(self, device_config: dict):
        super().__init__(device_config)
        self._host: str = self.connection_config.get("host", "localhost")
        self._port: int = self.connection_config.get("port", 80)
        self._endpoint: str = self.connection_config.get(
            "endpoint", "/api/telemetry"
        )
        self._timeout: int = self.connection_config.get("timeout_s", 5)
        self._retries: int = self.connection_config.get("retries", 3)
        self._session: Optional[requests.Session] = None
        self._base_url = f"http://{self._host}:{self._port}"

    @property
    def url(self) -> str:
        return f"{self._base_url}{self._endpoint}"

    def connect(self) -> bool:
        """Cria uma sessão HTTP persistente."""
        try:
            self._session = requests.Session()
            self._session.headers.update({
                "Accept": "application/json",
                "User-Agent": "PredictGW/1.0",
            })
            # Test connection
            response = self._session.get(
                self.url, timeout=self._timeout
            )
            if response.status_code == 200:
                logger.info(
                    f"[{self.id}] Conexão HTTP estabelecida: {self.url}"
                )
                return True
            else:
                logger.warning(
                    f"[{self.id}] HTTP {response.status_code} em {self.url}"
                )
                return False
        except requests.ConnectionError:
            logger.warning(
                f"[{self.id}] Não foi possível conectar a {self.url}"
            )
            return False
        except Exception as e:
            logger.error(f"[{self.id}] Erro ao conectar: {e}")
            return False

    def disconnect(self) -> None:
        """Encerra a sessão HTTP."""
        if self._session:
            self._session.close()
            self._session = None
            logger.info(f"[{self.id}] Sessão HTTP encerrada.")

    def read_tags(self) -> dict[str, TagReading]:
        """
        Faz HTTP GET no endpoint e parseia o JSON de resposta.
        Espera formato: {"current": 1.3, "frequency": 60.0, ...}
        """
        readings = {}

        if not self._session:
            self._session = requests.Session()

        last_error = None
        for attempt in range(self._retries):
            try:
                response = self._session.get(
                    self.url, timeout=self._timeout
                )
                response.raise_for_status()
                data = response.json()

                timestamp = datetime.now()

                for tag in self.tags:
                    value = data.get(tag.key)
                    if value is not None:
                        try:
                            value = float(value)
                        except (ValueError, TypeError):
                            pass

                    readings[tag.name] = TagReading(
                        name=tag.name,
                        value=value,
                        unit=tag.unit,
                        timestamp=timestamp,
                        quality="good" if value is not None else "bad",
                    )

                return readings

            except requests.Timeout:
                last_error = f"Timeout ao acessar {self.url}"
                logger.warning(
                    f"[{self.id}] Timeout (tentativa {attempt + 1}/{self._retries})"
                )
            except requests.ConnectionError:
                last_error = f"Erro de conexão com {self.url}"
                logger.warning(
                    f"[{self.id}] Conexão recusada "
                    f"(tentativa {attempt + 1}/{self._retries})"
                )
            except Exception as e:
                last_error = str(e)
                logger.error(
                    f"[{self.id}] Erro na leitura "
                    f"(tentativa {attempt + 1}/{self._retries}): {e}"
                )

        # Se todas as tentativas falharam, retorna leituras com quality "bad"
        for tag in self.tags:
            readings[tag.name] = TagReading(
                name=tag.name,
                value=None,
                unit=tag.unit,
                timestamp=datetime.now(),
                quality="bad",
            )

        raise ConnectionError(
            f"[{self.id}] Falha após {self._retries} tentativas: {last_error}"
        )
