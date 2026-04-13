"""
PredictGW — DeviceManager
Gerenciador que instancia e coordena dispositivos a partir do config.yaml.
Factory pattern com detecção automática de dispositivos offline.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional

import yaml

from core.base_device import BaseDevice, DeviceStatus
from core.data_buffer import DataBuffer
from core.json_device import JSONDevice
from core.modbus_device import ModbusDevice
from core.simulator import SimulatedInverterDevice, SimulatedPLCDevice

logger = logging.getLogger(__name__)

# Mapeamento de protocolos → classes
DEVICE_CLASSES = {
    "json_http": JSONDevice,
    "modbus_tcp": ModbusDevice,
}

SIMULATOR_CLASSES = {
    "inverter": SimulatedInverterDevice,
    "plc": SimulatedPLCDevice,
}


class DeviceManager:
    """
    Gerenciador central de dispositivos.
    Carrega configuração, instancia dispositivos e coordena polling/buffer.
    """

    def __init__(self, config_path: str = "config.yaml"):
        self._config_path = config_path
        self._config: dict = {}
        self._devices: dict[str, BaseDevice] = {}
        self._buffer: Optional[DataBuffer] = None
        self._simulation_mode: bool = True
        self._running: bool = False
        self._collector_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._load_config()
        self._init_devices()

    def _load_config(self) -> None:
        """Carrega e valida o arquivo de configuração."""
        config_file = Path(self._config_path)
        if not config_file.exists():
            raise FileNotFoundError(
                f"Arquivo de configuração não encontrado: {self._config_path}"
            )

        with open(config_file, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        system = self._config.get("system", {})
        self._simulation_mode = system.get("simulation_mode", True)
        buffer_size = system.get("buffer_size", 500)
        self._buffer = DataBuffer(max_size=buffer_size)
        self._poll_interval = system.get("poll_interval_ms", 2000) / 1000.0

        logger.info(
            f"Configuração carregada: "
            f"simulation={'ON' if self._simulation_mode else 'OFF'}, "
            f"buffer_size={buffer_size}"
        )

    def _init_devices(self) -> None:
        """Instancia dispositivos a partir da configuração (Factory Pattern)."""
        devices_config = self._config.get("devices", [])

        for dev_cfg in devices_config:
            dev_id = dev_cfg.get("id", "unknown")
            dev_type = dev_cfg.get("type", "unknown")
            protocol = dev_cfg.get("protocol", "unknown")

            try:
                if self._simulation_mode:
                    # Modo simulação: usa simuladores
                    sim_class = SIMULATOR_CLASSES.get(dev_type)
                    if sim_class:
                        device = sim_class(dev_cfg)
                        logger.info(
                            f"[{dev_id}] Simulador instanciado: {dev_type}"
                        )
                    else:
                        logger.warning(
                            f"[{dev_id}] Tipo desconhecido para simulação: "
                            f"{dev_type}"
                        )
                        continue
                else:
                    # Modo real: usa classes de protocolo
                    dev_class = DEVICE_CLASSES.get(protocol)
                    if dev_class:
                        device = dev_class(dev_cfg)
                        logger.info(
                            f"[{dev_id}] Dispositivo instanciado: "
                            f"{protocol}"
                        )
                    else:
                        logger.warning(
                            f"[{dev_id}] Protocolo desconhecido: {protocol}"
                        )
                        continue

                self._devices[dev_id] = device

            except Exception as e:
                logger.error(
                    f"[{dev_id}] Erro ao instanciar dispositivo: {e}"
                )

        logger.info(
            f"Total de dispositivos instanciados: {len(self._devices)}"
        )

    # ---- Lifecycle ----

    def start(self) -> None:
        """Inicia a coleta de todos os dispositivos."""
        if self._running:
            logger.warning("DeviceManager já está em execução.")
            return

        self._running = True

        # Iniciar polling de cada dispositivo
        for device in self._devices.values():
            device.start_polling()

        # Iniciar thread de coleta para o buffer
        self._collector_thread = threading.Thread(
            target=self._collection_loop,
            name="data-collector",
            daemon=True,
        )
        self._collector_thread.start()

        logger.info("✅ DeviceManager iniciado. Coletando dados...")

    def stop(self) -> None:
        """Para a coleta de todos os dispositivos."""
        self._running = False

        for device in self._devices.values():
            device.stop_polling()

        if self._collector_thread and self._collector_thread.is_alive():
            self._collector_thread.join(timeout=10)

        logger.info("⏹ DeviceManager parado.")

    def _collection_loop(self) -> None:
        """Loop que coleta leituras e alimenta o buffer."""
        while self._running:
            for dev_id, device in self._devices.items():
                try:
                    readings = device.last_readings
                    if readings:
                        self._buffer.append(dev_id, readings)
                except Exception as e:
                    logger.error(
                        f"[{dev_id}] Erro ao coletar para buffer: {e}"
                    )

            time.sleep(self._poll_interval)

    # ---- Acessors ----

    @property
    def devices(self) -> dict[str, BaseDevice]:
        return dict(self._devices)

    @property
    def buffer(self) -> DataBuffer:
        return self._buffer

    @property
    def config(self) -> dict:
        return self._config

    @property
    def simulation_mode(self) -> bool:
        return self._simulation_mode

    def get_device(self, device_id: str) -> Optional[BaseDevice]:
        return self._devices.get(device_id)

    def get_inverters(self) -> dict[str, BaseDevice]:
        """Retorna apenas dispositivos do tipo inversor."""
        return {
            dev_id: dev
            for dev_id, dev in self._devices.items()
            if dev.device_type == "inverter"
        }

    def get_plcs(self) -> dict[str, BaseDevice]:
        """Retorna apenas dispositivos do tipo CLP."""
        return {
            dev_id: dev
            for dev_id, dev in self._devices.items()
            if dev.device_type == "plc"
        }

    def get_system_status(self) -> dict:
        """Status geral do sistema."""
        devices_info = {}
        online_count = 0
        total_count = len(self._devices)

        for dev_id, device in self._devices.items():
            info = device.device_info
            devices_info[dev_id] = info
            if device.is_online:
                online_count += 1

        return {
            "simulation_mode": self._simulation_mode,
            "total_devices": total_count,
            "online_devices": online_count,
            "offline_devices": total_count - online_count,
            "buffer_info": self._buffer.get_buffer_info() if self._buffer else {},
            "devices": devices_info,
        }

    def reload_config(self) -> None:
        """Recarrega a configuração e reinicia dispositivos."""
        logger.info("Recarregando configuração...")
        self.stop()
        time.sleep(1)
        self._devices.clear()
        self._load_config()
        self._init_devices()
        self.start()
        logger.info("✅ Configuração recarregada com sucesso.")
