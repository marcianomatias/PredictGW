"""
PredictGW — Simulador de Dados Industriais
Gera dados realistas para inversores e CLPs sem hardware real.
"""

import math
import random
import logging
from datetime import datetime
from typing import Optional

from core.base_device import BaseDevice, TagReading

logger = logging.getLogger(__name__)


class SimulatedInverterDevice(BaseDevice):
    """
    Simula um inversor com dados realistas:
    - Corrente com drift gradual (simula desgaste)
    - Frequência com oscilação normal
    - Temperatura correlacionada com corrente
    - RPM proporcional à frequência
    """

    def __init__(self, device_config: dict):
        super().__init__(device_config)
        self._tick = 0
        self._base_current = 1.2          # Corrente nominal
        self._current_drift = 0.0         # Drift acumulado (simula desgaste)
        self._drift_rate = 0.0002         # A por tick (~0.05A/hora com polling 1s)
        self._anomaly_active = False
        self._anomaly_start_tick = 0
        self._cycle_phase = random.uniform(0, 2 * math.pi)

    def connect(self) -> bool:
        logger.info(f"[{self.id}] Simulador de inversor conectado.")
        return True

    def disconnect(self) -> None:
        logger.info(f"[{self.id}] Simulador de inversor desconectado.")

    def read_tags(self) -> dict[str, TagReading]:
        self._tick += 1
        timestamp = datetime.now()
        readings = {}

        # Drift gradual de corrente (simula desgaste de rolamento)
        self._current_drift += self._drift_rate

        # Ativar anomalia aleatória (1% de chance por tick)
        if not self._anomaly_active and random.random() < 0.001:
            self._anomaly_active = True
            self._anomaly_start_tick = self._tick
            logger.info(f"[{self.id}] 🔥 Anomalia simulada iniciada!")

        anomaly_extra = 0.0
        if self._anomaly_active:
            anomaly_duration = self._tick - self._anomaly_start_tick
            anomaly_extra = 0.3 * math.sin(anomaly_duration * 0.1) + 0.2
            if anomaly_duration > 100:
                self._anomaly_active = False
                logger.info(f"[{self.id}] ✅ Anomalia simulada encerrada.")

        # Ciclo industrial: rampa → patamar → idle
        cycle_t = (self._tick % 300) / 300.0  # Ciclo de 5 min (com poll 1s)
        if cycle_t < 0.1:
            load_factor = cycle_t / 0.1  # Rampa de subida
        elif cycle_t < 0.8:
            load_factor = 1.0            # Patamar
        else:
            load_factor = (1.0 - cycle_t) / 0.2  # Rampa de descida

        for tag in self.tags:
            value = self._generate_tag_value(
                tag.key, load_factor, anomaly_extra, timestamp
            )
            readings[tag.name] = TagReading(
                name=tag.name,
                value=round(value, 3) if value is not None else None,
                unit=tag.unit,
                timestamp=timestamp,
                quality="good",
            )

        return readings

    def _generate_tag_value(
        self, key: str, load: float, anomaly: float, ts: datetime
    ) -> float:
        """Gera valor realista para cada tag do inversor."""
        noise = random.gauss(0, 0.02)
        t = self._tick * 0.01

        if key == "current":
            base = self._base_current * load
            return max(0, base + self._current_drift + anomaly + noise)

        elif key == "frequency":
            target_freq = 60.0 * load
            return max(0, target_freq + random.gauss(0, 0.3))

        elif key == "temperature":
            # Temperatura com inércia térmica (lag da corrente)
            current = self._base_current * load + self._current_drift
            ambient = 25.0 + 5.0 * math.sin(t * 0.005)  # Variação ambiente
            heat = current * 15.0  # Aquecimento proporcional
            return ambient + heat + random.gauss(0, 0.5)

        elif key == "rpm":
            freq = 60.0 * load
            # RPM = (120 * freq) / polos (assumindo 4 polos)
            rpm = (120.0 * freq) / 4.0
            return max(0, rpm + random.gauss(0, 10))

        elif key == "dc_bus_voltage":
            return 380.0 + random.gauss(0, 5) + 10 * load

        else:
            return random.uniform(0, 100)


class SimulatedPLCDevice(BaseDevice):
    """
    Simula um CLP com:
    - Entradas digitais com padrões cíclicos
    - Saídas digitais baseadas em lógica ladder simplificada
    - Sensores analógicos com tendências industriais
    """

    def __init__(self, device_config: dict):
        super().__init__(device_config)
        self._tick = 0
        self._digital_states: dict[str, bool] = {}
        self._analog_bases: dict[str, float] = {}
        self._drift_values: dict[str, float] = {}

        # Inicializar estados
        for tag in self.tags:
            if tag.tag_type in ("digital_input", "digital_output"):
                self._digital_states[tag.name] = False
            elif tag.tag_type == "analog":
                if tag.limits:
                    mid = (
                        (tag.limits.warning_low or 0)
                        + (tag.limits.warning_high or 100)
                    ) / 2
                    self._analog_bases[tag.name] = mid
                else:
                    self._analog_bases[tag.name] = 50.0
                self._drift_values[tag.name] = 0.0

    def connect(self) -> bool:
        logger.info(f"[{self.id}] Simulador de CLP conectado.")
        return True

    def disconnect(self) -> None:
        logger.info(f"[{self.id}] Simulador de CLP desconectado.")

    def read_tags(self) -> dict[str, TagReading]:
        self._tick += 1
        timestamp = datetime.now()
        readings = {}

        # Atualizar estados digitais
        self._update_digital_states()

        for tag in self.tags:
            if tag.tag_type in ("digital_input", "digital_output"):
                value = float(self._digital_states.get(tag.name, False))
            elif tag.tag_type == "analog":
                value = self._generate_analog_value(tag)
            else:
                value = 0.0

            readings[tag.name] = TagReading(
                name=tag.name,
                value=round(value, 3),
                unit=tag.unit,
                timestamp=timestamp,
                quality="good",
            )

        return readings

    def _update_digital_states(self) -> None:
        """Simula lógica ladder: sensores ativam saídas."""
        cycle = self._tick % 200

        for tag in self.tags:
            if tag.tag_type == "digital_input":
                # Padrão cíclico para sensores
                if "Nível Alto" in tag.name:
                    self._digital_states[tag.name] = cycle > 150
                elif "Nível Baixo" in tag.name:
                    self._digital_states[tag.name] = cycle < 50
                elif "Pressostato" in tag.name:
                    self._digital_states[tag.name] = 40 < cycle < 180
                elif "Emergência" in tag.name:
                    # Emergência rara
                    self._digital_states[tag.name] = random.random() < 0.002
                elif "Presença" in tag.name:
                    # Sensor de presença com ciclos rápidos
                    self._digital_states[tag.name] = (
                        (self._tick % 20) < 10
                    )
                else:
                    self._digital_states[tag.name] = random.random() > 0.5

            elif tag.tag_type == "digital_output":
                # Lógica simplificada baseada em inputs
                if "Bomba" in tag.name or "Motor" in tag.name:
                    self._digital_states[tag.name] = 20 < cycle < 180
                elif "Válvula" in tag.name:
                    self._digital_states[tag.name] = 30 < cycle < 170
                elif "Alarme" in tag.name:
                    self._digital_states[tag.name] = cycle > 190

    def _generate_analog_value(self, tag) -> float:
        """Gera valor analógico com tendência industrial."""
        base = self._analog_bases.get(tag.name, 50.0)
        drift = self._drift_values.get(tag.name, 0.0)

        # Drift lento (desgaste)
        drift += random.gauss(0.001, 0.003)
        self._drift_values[tag.name] = drift

        # Variação de processo
        t = self._tick * 0.02
        process_var = math.sin(t + hash(tag.name) % 100) * (base * 0.05)

        # Ruído
        noise = random.gauss(0, base * 0.01)

        value = base + drift + process_var + noise

        # Clamp to positive
        return max(0, value)
