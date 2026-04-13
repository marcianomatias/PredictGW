"""
PredictGW — ModbusDevice
Implementação para CLPs via Modbus TCP.
"""

import logging
from datetime import datetime
from typing import Optional

from core.base_device import BaseDevice, TagReading

logger = logging.getLogger(__name__)


class ModbusDevice(BaseDevice):
    """
    Dispositivo que coleta dados via Modbus TCP.
    Suporta leitura de Coils, Discrete Inputs, Holding Registers e Input Registers.
    """

    def __init__(self, device_config: dict):
        super().__init__(device_config)
        self._host: str = self.connection_config.get("host", "localhost")
        self._port: int = self.connection_config.get("port", 502)
        self._unit_id: int = self.connection_config.get("unit_id", 1)
        self._timeout: int = self.connection_config.get("timeout_s", 3)
        self._retries: int = self.connection_config.get("retries", 2)
        self._client = None

    def connect(self) -> bool:
        """Conecta ao CLP via Modbus TCP."""
        try:
            from pymodbus.client import ModbusTcpClient

            self._client = ModbusTcpClient(
                host=self._host,
                port=self._port,
                timeout=self._timeout,
                retries=self._retries,
            )

            if self._client.connect():
                logger.info(
                    f"[{self.id}] Modbus TCP conectado: "
                    f"{self._host}:{self._port} (unit={self._unit_id})"
                )
                return True
            else:
                logger.warning(
                    f"[{self.id}] Falha ao conectar Modbus TCP: "
                    f"{self._host}:{self._port}"
                )
                return False
        except ImportError:
            logger.error(
                f"[{self.id}] pymodbus não instalado. "
                "Execute: pip install pymodbus"
            )
            return False
        except Exception as e:
            logger.error(f"[{self.id}] Erro ao conectar Modbus: {e}")
            return False

    def disconnect(self) -> None:
        """Desconecta do CLP."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
            logger.info(f"[{self.id}] Modbus TCP desconectado.")

    def _read_register(self, tag) -> Optional[float]:
        """Lê um registrador/coil individual baseado na configuração da tag."""
        if not self._client:
            return None

        try:
            reg_type = tag.register_type
            address = tag.address

            if reg_type == "coil":
                result = self._client.read_coils(
                    address, count=1, slave=self._unit_id
                )
                if not result.isError():
                    return float(result.bits[0])

            elif reg_type == "discrete_input":
                result = self._client.read_discrete_inputs(
                    address, count=1, slave=self._unit_id
                )
                if not result.isError():
                    return float(result.bits[0])

            elif reg_type == "holding_register":
                result = self._client.read_holding_registers(
                    address, count=1, slave=self._unit_id
                )
                if not result.isError():
                    raw = result.registers[0]
                    return raw * tag.scale + tag.offset

            elif reg_type == "input_register":
                result = self._client.read_input_registers(
                    address, count=1, slave=self._unit_id
                )
                if not result.isError():
                    raw = result.registers[0]
                    return raw * tag.scale + tag.offset

            else:
                logger.warning(
                    f"[{self.id}] Tipo de registrador desconhecido: {reg_type}"
                )
                return None

        except Exception as e:
            logger.error(
                f"[{self.id}] Erro ao ler {tag.name} "
                f"({reg_type}@{address}): {e}"
            )
            return None

        return None

    def read_tags(self) -> dict[str, TagReading]:
        """
        Lê todas as tags configuradas via Modbus TCP.
        Para cada tag, lê o registrador correspondente e aplica scale/offset.
        """
        readings = {}
        timestamp = datetime.now()
        all_good = True

        for tag in self.tags:
            value = self._read_register(tag)

            quality = "good"
            if value is None:
                quality = "bad"
                all_good = False

            readings[tag.name] = TagReading(
                name=tag.name,
                value=value,
                unit=tag.unit,
                timestamp=timestamp,
                quality=quality,
            )

        if not all_good and self._client:
            # Verifica se a conexão ainda está ativa
            if not self._client.connected:
                raise ConnectionError(
                    f"[{self.id}] Conexão Modbus perdida."
                )

        return readings
