"""
PredictGW — Página de Inversores
Visualização de telemetria com gauges, tendências e histerese.
"""

import streamlit as st
import pandas as pd

from core.base_device import BaseDevice, DeviceStatus
from core.data_buffer import DataBuffer
from analytics.health_score import HealthScoreManager
from ui.components.gauge import render_gauge
from ui.components.trend_chart import render_trend_chart, render_multi_trend
from ui.components.health_badge import render_health_badge, render_health_summary


def render_inverters_page(
    inverters: dict[str, BaseDevice],
    buffer: DataBuffer,
    health_manager: HealthScoreManager,
) -> None:
    """Renderiza a página completa de monitoramento de inversores."""

    if not inverters:
        st.info("🔌 Nenhum inversor configurado no sistema.")
        return

    for dev_id, device in inverters.items():
        _render_inverter_card(dev_id, device, buffer, health_manager)


def _render_inverter_card(
    dev_id: str,
    device: BaseDevice,
    buffer: DataBuffer,
    health_manager: HealthScoreManager,
) -> None:
    """Renderiza o card de um inversor individual."""

    # Status indicator
    status_class = {
        DeviceStatus.ONLINE: "online",
        DeviceStatus.WARNING: "warning",
        DeviceStatus.OFFLINE: "offline",
        DeviceStatus.ERROR: "offline",
        DeviceStatus.CONNECTING: "connecting",
    }.get(device.status, "offline")

    status_emoji = {
        DeviceStatus.ONLINE: "🟢",
        DeviceStatus.WARNING: "🟡",
        DeviceStatus.OFFLINE: "🔴",
        DeviceStatus.ERROR: "🔴",
        DeviceStatus.CONNECTING: "🔵",
    }.get(device.status, "⚫")

    # Device header
    st.markdown(
        f"""
        <div class="device-card">
            <div class="device-header">
                <div>
                    <span class="status-dot {status_class}"></span>
                    <span class="device-name">{device.name}</span>
                </div>
                <span class="device-protocol">
                    {device.protocol.upper().replace('_', ' ')}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not device.is_online and device.status != DeviceStatus.CONNECTING:
        st.warning(
            f"⚠️ **{device.name}** está OFFLINE. "
            f"({device._consecutive_errors} erros consecutivos)"
        )
        return

    readings = device.last_readings

    # Layout: Gauges + Health Score
    col_gauges, col_health = st.columns([3, 1])

    with col_gauges:
        # Render gauges para cada tag
        gauge_cols = st.columns(min(len(device.tags), 5))
        for i, tag in enumerate(device.tags):
            reading = readings.get(tag.name)
            value = reading.value if reading else None

            with gauge_cols[i % len(gauge_cols)]:
                limits = {}
                if tag.limits:
                    limits = {
                        "warning_high": tag.limits.warning_high,
                        "warning_low": tag.limits.warning_low,
                        "critical_high": tag.limits.critical_high,
                        "critical_low": tag.limits.critical_low,
                    }

                # Determinar range do gauge
                min_val = (
                    (tag.limits.critical_low or 0) * 0.5
                    if tag.limits and tag.limits.critical_low
                    else 0
                )
                max_val = (
                    (tag.limits.critical_high or 100) * 1.2
                    if tag.limits and tag.limits.critical_high
                    else 100
                )

                render_gauge(
                    value=value if value is not None else 0,
                    min_val=min_val,
                    max_val=max_val,
                    title=tag.name,
                    unit=tag.unit,
                    **limits,
                )

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

    # Metrics row
    st.markdown("---")
    metric_cols = st.columns(len(device.tags))
    for i, tag in enumerate(device.tags):
        reading = readings.get(tag.name)
        value = reading.value if reading else None
        stats = buffer.get_statistics(dev_id, tag.name)

        with metric_cols[i]:
            delta = None
            delta_color = "normal"
            if stats and "mean" in stats and value is not None:
                delta_val = value - stats["mean"]
                delta = f"{delta_val:+.3f} {tag.unit}"
                if tag.limits:
                    state = tag.limits.evaluate(value)
                    if "critical" in state:
                        delta_color = "inverse"
                    elif "warning" in state:
                        delta_color = "off"

            st.metric(
                label=f"{tag.name} ({tag.unit})",
                value=f"{value:.2f}" if value is not None else "—",
                delta=delta,
                delta_color=delta_color,
            )

    # Trend charts
    st.markdown("---")
    df = buffer.get_buffer(dev_id, last_n=200)

    if not df.empty:
        # Tag de target preditivo
        target_tag = device.predictive_config.get("target_tag", "")
        if target_tag and target_tag in df.columns:
            target_cfg = next(
                (t for t in device.tags if t.name == target_tag), None
            )
            limits_kwargs = {}
            if target_cfg and target_cfg.limits:
                limits_kwargs = {
                    "warning_high": target_cfg.limits.warning_high,
                    "warning_low": target_cfg.limits.warning_low,
                    "critical_high": target_cfg.limits.critical_high,
                    "critical_low": target_cfg.limits.critical_low,
                }

            # Get anomaly indices if available
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
                unit=target_cfg.unit if target_cfg else "",
                anomaly_indices=anomaly_indices,
                title=f"📈 {target_tag} — Tendência com Detecção de Anomalias",
                **limits_kwargs,
            )

        # Multi-trend para todas as tags
        analog_tags = [
            t.name for t in device.tags
            if t.name in df.columns
        ]
        analog_units = [
            t.unit for t in device.tags
            if t.name in df.columns
        ]

        if len(analog_tags) > 1:
            render_multi_trend(
                df=df,
                tag_names=analog_tags,
                units=analog_units,
                title=f"{device.name} — Visão Geral",
            )
    else:
        st.info("⏳ Aguardando dados suficientes para gráficos...")
