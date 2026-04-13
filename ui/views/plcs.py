"""
PredictGW — Página de CLPs
Matriz de estados I/O e gráficos de tendência para sensores analógicos.
"""

import streamlit as st
import pandas as pd

from core.base_device import BaseDevice, DeviceStatus
from core.data_buffer import DataBuffer
from analytics.health_score import HealthScoreManager
from ui.components.io_matrix import render_io_matrix, render_io_summary
from ui.components.trend_chart import render_trend_chart, render_multi_trend
from ui.components.health_badge import render_health_badge, render_health_summary


def render_plcs_page(
    plcs: dict[str, BaseDevice],
    buffer: DataBuffer,
    health_manager: HealthScoreManager,
) -> None:
    """Renderiza a página completa de monitoramento de CLPs."""

    if not plcs:
        st.info("⚙️ Nenhum CLP configurado no sistema.")
        return

    for dev_id, device in plcs.items():
        _render_plc_card(dev_id, device, buffer, health_manager)
        st.markdown("<br>", unsafe_allow_html=True)


def _render_plc_card(
    dev_id: str,
    device: BaseDevice,
    buffer: DataBuffer,
    health_manager: HealthScoreManager,
) -> None:
    """Renderiza o card de um CLP individual."""

    # Status
    status_class = {
        DeviceStatus.ONLINE: "online",
        DeviceStatus.WARNING: "warning",
        DeviceStatus.OFFLINE: "offline",
        DeviceStatus.ERROR: "offline",
        DeviceStatus.CONNECTING: "connecting",
    }.get(device.status, "offline")

    # Header
    st.markdown(
        f"""
        <div class="device-card">
            <div class="device-header">
                <div>
                    <span class="status-dot {status_class}"></span>
                    <span class="device-name">{device.name}</span>
                </div>
                <div>
                    <span class="device-protocol">
                        {device.protocol.upper().replace('_', ' ')}
                    </span>
                    <span class="device-protocol" style="margin-left: 8px;">
                        Unit {device.connection_config.get('unit_id', '?')}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not device.is_online and device.status != DeviceStatus.CONNECTING:
        st.warning(
            f"⚠️ **{device.name}** está OFFLINE. "
            f"Verifique a conexão Modbus TCP "
            f"({device.connection_config.get('host', '?')}:"
            f"{device.connection_config.get('port', '?')})"
        )
        return

    readings = device.last_readings

    # Layout: IO Matrix + Health + Summary
    col_io, col_health = st.columns([3, 1])

    with col_io:
        # IO Matrix
        render_io_matrix(readings, device.tags, title=f"I/O — {device.name}")

        # IO Summary metrics
        summary = render_io_summary(readings, device.tags)
        io_cols = st.columns(4)
        with io_cols[0]:
            st.metric("📥 DI ON", summary["digital_inputs_on"])
        with io_cols[1]:
            st.metric("📥 DI OFF", summary["digital_inputs_off"])
        with io_cols[2]:
            st.metric("📤 DO ON", summary["digital_outputs_on"])
        with io_cols[3]:
            st.metric("📤 DO OFF", summary["digital_outputs_off"])

    with col_health:
        health = health_manager.get_score(dev_id)
        if health:
            render_health_badge(
                score=health.score,
                classification=health.classification,
                color=health.color,
                size=110,
            )
            st.markdown("---")
            render_health_summary(health.components, compact=True)

            if health.rul_hours is not None and health.rul_hours != float("inf"):
                st.markdown(
                    f"""
                    <div style="text-align: center; margin-top: 0.5rem;
                         padding: 0.5rem; background: rgba(239,68,68,0.1);
                         border-radius: 8px; border: 1px solid rgba(239,68,68,0.2);">
                        <div style="font-size: 0.7rem; color: #f87171;
                             text-transform: uppercase; font-weight: 600;">
                            Falha Prevista
                        </div>
                        <div style="font-size: 1.1rem; font-weight: 800;
                             color: #ef4444; margin-top: 4px;">
                            {health.rul_text}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div style="text-align: center; color: #64748b; '
                'font-size: 0.8rem; padding: 1rem;">'
                '⏳ Calculando Health Score...</div>',
                unsafe_allow_html=True,
            )

    # Analog sensors section
    st.markdown("---")
    analog_tags = [t for t in device.tags if t.tag_type == "analog"]

    if analog_tags:
        st.markdown(
            '<p style="color: #94a3b8; font-size: 0.75rem; '
            'text-transform: uppercase; letter-spacing: 0.05em; '
            'font-weight: 600;">📊 Sensores Analógicos</p>',
            unsafe_allow_html=True,
        )

        # Metrics for analog values
        analog_cols = st.columns(min(len(analog_tags), 4))
        for i, tag in enumerate(analog_tags):
            reading = readings.get(tag.name)
            value = reading.value if reading else None
            stats = buffer.get_statistics(dev_id, tag.name)

            with analog_cols[i % len(analog_cols)]:
                delta = None
                if stats and "mean" in stats and value is not None:
                    delta = f"{value - stats['mean']:+.2f}"

                st.metric(
                    label=f"{tag.name} ({tag.unit})",
                    value=f"{value:.2f}" if value is not None else "—",
                    delta=delta,
                )

        # Trend charts for analog tags
        df = buffer.get_buffer(dev_id, last_n=200)

        if not df.empty:
            # Individual trend for target tag
            target_tag = device.predictive_config.get("target_tag", "")
            if target_tag:
                target_cfg = next(
                    (t for t in device.tags if t.name == target_tag), None
                )
                if target_cfg and target_tag in df.columns:
                    limits_kwargs = {}
                    if target_cfg.limits:
                        limits_kwargs = {
                            "warning_high": target_cfg.limits.warning_high,
                            "warning_low": target_cfg.limits.warning_low,
                            "critical_high": target_cfg.limits.critical_high,
                            "critical_low": target_cfg.limits.critical_low,
                        }

                    anomaly_indices = None
                    health = health_manager.get_score(dev_id)
                    if health and health.anomalies:
                        is_anomaly = health.anomalies.get("is_anomaly", [])
                        anomaly_indices = [
                            i for i, v in enumerate(is_anomaly) if v
                        ]

                    render_trend_chart(
                        df=df,
                        tag_name=target_tag,
                        unit=target_cfg.unit,
                        anomaly_indices=anomaly_indices,
                        title=(
                            f"📈 {target_tag} — "
                            f"Tendência com Detecção de Anomalias"
                        ),
                        **limits_kwargs,
                    )

            # Multi-trend for all analog tags
            analog_names = [
                t.name for t in analog_tags if t.name in df.columns
            ]
            analog_units = [
                t.unit for t in analog_tags if t.name in df.columns
            ]

            if len(analog_names) > 1:
                render_multi_trend(
                    df=df,
                    tag_names=analog_names,
                    units=analog_units,
                    title=f"{device.name} — Sensores Analógicos",
                )
        else:
            st.info("⏳ Aguardando dados para gráficos...")
