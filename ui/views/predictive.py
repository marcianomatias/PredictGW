"""
PredictGW — Página de Análise Preditiva
Visualização de resultados do motor preditivo com gráficos de forecast.
"""

import streamlit as st
import pandas as pd

from core.device_manager import DeviceManager
from analytics.predictive_engine import PredictiveEngine
from ui.components.trend_chart import render_forecast_chart
from ui.components.health_badge import render_health_badge, render_health_summary


def render_predictive_page(
    device_manager: DeviceManager,
    predictive_engine: PredictiveEngine,
) -> None:
    """Renderiza a página de análise preditiva."""

    # Engine status
    engine_status = predictive_engine.get_status()

    st.markdown(
        f"""
        <div class="metric-card info" style="margin-bottom: 1.5rem;">
            <div style="display: flex; align-items: center; 
                        justify-content: space-between;">
                <div>
                    <div class="metric-label">Motor Preditivo</div>
                    <div style="font-size: 1.2rem; font-weight: 700; 
                                color: #e2e8f0;">
                        🧠 Engine: <span style="color: #8b5cf6;">
                        {engine_status['engine'].upper()}</span>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.75rem; color: #94a3b8;">
                        Intervalo: {engine_status['interval_s']}s
                    </div>
                    <div style="font-size: 0.75rem; color: #94a3b8;">
                        Dispositivos analisados: 
                        {engine_status['devices_analyzed']}
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Overall health
    overall_score = engine_status.get("overall_health", 100)
    health_manager = predictive_engine.health_manager
    last_results = predictive_engine.last_results

    # Top-level health overview
    st.markdown("### 🏥 Saúde Geral do Sistema")

    ov_cols = st.columns([1, 3])
    with ov_cols[0]:
        render_health_badge(
            score=overall_score,
            size=140,
            show_label=True,
        )

    with ov_cols[1]:
        # Device health cards
        all_scores = health_manager.get_all_scores()
        if all_scores:
            score_cols = st.columns(min(len(all_scores), 4))
            for i, (dev_id, hs) in enumerate(all_scores.items()):
                device = device_manager.get_device(dev_id)
                name = device.name if device else dev_id
                with score_cols[i % len(score_cols)]:
                    st.markdown(
                        f"""
                        <div class="metric-card" style="text-align: center;">
                            <div class="metric-label">{name}</div>
                            <div class="metric-value" 
                                 style="color: {hs.color};">
                                {hs.score:.0f}
                            </div>
                            <div style="font-size: 0.7rem; color: {hs.color};
                                 font-weight: 600; margin-top: 4px;">
                                {hs.classification}
                            </div>
                            <div style="font-size: 0.65rem; color: #64748b;
                                 margin-top: 2px;">
                                RUL: {hs.rul_text}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        else:
            st.info("⏳ Aguardando primeira análise preditiva...")

    st.markdown("---")

    # Detailed analysis per device
    st.markdown("### 📊 Análise Detalhada por Dispositivo")

    devices = device_manager.devices
    for dev_id, device in devices.items():
        if not device.predictive_config:
            continue

        target_tag = device.predictive_config.get("target_tag", "")
        critical_limit = device.predictive_config.get("critical_limit")

        with st.expander(f"🔍 {device.name} — {target_tag}", expanded=True):
            result = last_results.get(dev_id)
            health_result = health_manager.get_score(dev_id)

            if not result:
                st.info(
                    f"⏳ Aguardando dados suficientes para "
                    f"{device.name}..."
                )
                continue

            # Analysis details in columns
            detail_cols = st.columns([1, 1, 2])

            with detail_cols[0]:
                if health_result:
                    render_health_badge(
                        score=health_result.score,
                        classification=health_result.classification,
                        color=health_result.color,
                        size=100,
                    )

            with detail_cols[1]:
                if health_result:
                    render_health_summary(health_result.components)

                anomalies = result.get("anomalies", {})
                rul = result.get("rul", {})

                st.markdown(
                    f"""
                    <div style="margin-top: 0.5rem; padding: 0.75rem;
                         background: rgba(26,31,46,0.8); 
                         border-radius: 8px;
                         border: 1px solid rgba(148,163,184,0.1);">
                        <div style="font-size: 0.7rem; color: #94a3b8;
                             margin-bottom: 0.5rem; font-weight: 600;">
                            📋 Detalhes
                        </div>
                        <div style="font-size: 0.75rem; color: #e2e8f0;">
                            Anomalias: <b>{anomalies.get('anomaly_count', 0)}</b><br>
                            Método: <b>{anomalies.get('method', '—')}</b><br>
                            RUL: <b>{rul.get('status', '—')}</b><br>
                            Pontos: <b>{result.get('data_points', 0)}</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with detail_cols[2]:
                # Forecast chart
                df = device_manager.buffer.get_buffer(dev_id, last_n=200)
                forecast_values = rul.get("forecast_values")
                forecast_lower = rul.get("forecast_lower")
                forecast_upper = rul.get("forecast_upper")
                failure_ts = rul.get("failure_timestamp")

                if not df.empty and target_tag in df.columns:
                    render_forecast_chart(
                        historical=df,
                        tag_name=target_tag,
                        forecast_values=forecast_values,
                        forecast_lower=forecast_lower,
                        forecast_upper=forecast_upper,
                        critical_limit=critical_limit,
                        failure_timestamp=failure_ts,
                        unit=next(
                            (t.unit for t in device.tags
                             if t.name == target_tag),
                            "",
                        ),
                        height=300,
                    )
                else:
                    st.info("Aguardando dados para forecast...")
