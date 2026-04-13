"""
PredictGW — Trend Chart Component
Gráficos de tendência com Plotly para variáveis analógicas.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Optional


# Dark theme template for all charts
CHART_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(17,24,39,0.8)",
    font=dict(family="Inter, sans-serif", color="#94a3b8"),
    margin=dict(l=50, r=20, t=40, b=40),
    xaxis=dict(
        gridcolor="rgba(148,163,184,0.08)",
        zerolinecolor="rgba(148,163,184,0.1)",
    ),
    yaxis=dict(
        gridcolor="rgba(148,163,184,0.08)",
        zerolinecolor="rgba(148,163,184,0.1)",
    ),
    legend=dict(
        bgcolor="rgba(26,31,46,0.9)",
        bordercolor="rgba(148,163,184,0.1)",
        borderwidth=1,
        font=dict(size=11),
    ),
)


def render_trend_chart(
    df: pd.DataFrame,
    tag_name: str,
    unit: str = "",
    warning_high: float = None,
    critical_high: float = None,
    warning_low: float = None,
    critical_low: float = None,
    anomaly_indices: list = None,
    title: str = None,
    height: int = 300,
) -> None:
    """
    Renderiza um gráfico de tendência para uma variável.
    
    Args:
        df: DataFrame com coluna 'timestamp' e a tag
        tag_name: Nome da coluna da tag
        unit: Unidade de medida
        warning_high/low, critical_high/low: Limites
        anomaly_indices: Índices de pontos anômalos
        title: Título do gráfico
        height: Altura em pixels
    """
    if df.empty or tag_name not in df.columns:
        st.info(f"Aguardando dados para {tag_name}...")
        return

    fig = go.Figure()

    # Série principal
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df[tag_name],
        mode="lines",
        name=tag_name,
        line=dict(color="#3b82f6", width=3, shape="spline"),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.15)",
        hovertemplate=f"<b>{tag_name}</b><br>"
                      f"Valor: %{{y:.2f}} {unit}<br>"
                      f"Hora: %{{x|%H:%M:%S}}<extra></extra>",
    ))

    # Limites de histerese
    if warning_high is not None:
        fig.add_hline(
            y=warning_high, line_dash="dash",
            line_color="#f59e0b", line_width=1,
            annotation_text=f"⚠ Warning ({warning_high}{unit})",
            annotation_position="bottom right",
            annotation_font_color="#f59e0b",
            annotation_font_size=10,
        )
    if critical_high is not None:
        fig.add_hline(
            y=critical_high, line_dash="dot",
            line_color="#ef4444", line_width=1.5,
            annotation_text=f"🔴 Crítico ({critical_high}{unit})",
            annotation_position="top right",
            annotation_font_color="#ef4444",
            annotation_font_size=10,
        )
    if warning_low is not None:
        fig.add_hline(
            y=warning_low, line_dash="dash",
            line_color="#f59e0b", line_width=1,
            annotation_text=f"⚠ Warning ({warning_low}{unit})",
            annotation_position="top right",
            annotation_font_color="#f59e0b",
            annotation_font_size=10,
        )
    if critical_low is not None:
        fig.add_hline(
            y=critical_low, line_dash="dot",
            line_color="#ef4444", line_width=1.5,
            annotation_text=f"🔴 Crítico ({critical_low}{unit})",
            annotation_position="bottom right",
            annotation_font_color="#ef4444",
            annotation_font_size=10,
        )

    # Marcação de anomalias
    if anomaly_indices and len(anomaly_indices) > 0:
        anomaly_mask = pd.Series(False, index=df.index)
        valid_indices = [i for i in anomaly_indices if i < len(df)]
        if valid_indices:
            anomaly_mask.iloc[valid_indices] = True
            anomaly_df = df[anomaly_mask]

            fig.add_trace(go.Scatter(
                x=anomaly_df["timestamp"],
                y=anomaly_df[tag_name],
                mode="markers",
                name="Anomalia",
                marker=dict(
                    color="#ef4444",
                    size=10,
                    symbol="diamond",
                    line=dict(color="#ffffff", width=2),
                ),
                hovertemplate=f"<b>⚠ ANOMALIA</b><br>"
                              f"Valor: %{{y:.2f}} {unit}<br>"
                              f"Hora: %{{x|%H:%M:%S}}<extra></extra>",
            ))

    fig.update_layout(
        **CHART_LAYOUT,
        title=dict(
            text=title or f"📈 {tag_name} ({unit})",
            font=dict(size=13, color="#e2e8f0"),
        ),
        height=height,
        xaxis_title="",
        yaxis_title=f"{unit}" if unit else "",
        showlegend=True,
    )

    st.plotly_chart(fig, width="stretch")


def render_multi_trend(
    df: pd.DataFrame,
    tag_names: list[str],
    units: list[str] = None,
    title: str = "Tendências",
    height: int = 400,
) -> None:
    """Renderiza múltiplas séries no mesmo gráfico."""
    if df.empty:
        st.info("Aguardando dados...")
        return

    colors = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4", "#f97316"]
    units = units or [""] * len(tag_names)

    fig = go.Figure()

    for i, (tag, unit) in enumerate(zip(tag_names, units)):
        if tag not in df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df[tag],
            mode="lines",
            name=f"{tag} ({unit})",
            line=dict(color=colors[i % len(colors)], width=3, shape="spline"),
            hovertemplate=f"<b>{tag}</b>: %{{y:.2f}} {unit}<extra></extra>",
        ))

    fig.update_layout(
        **CHART_LAYOUT,
        title=dict(
            text=f"📊 {title}",
            font=dict(size=13, color="#e2e8f0"),
        ),
        height=height,
        showlegend=True,
        hovermode="x unified",
    )

    st.plotly_chart(fig, width="stretch")


def render_forecast_chart(
    historical: pd.DataFrame,
    tag_name: str,
    forecast_values: list = None,
    forecast_lower: list = None,
    forecast_upper: list = None,
    critical_limit: float = None,
    failure_timestamp: str = None,
    unit: str = "",
    height: int = 350,
) -> None:
    """
    Renderiza gráfico de previsão com bandas de confiança.
    """
    fig = go.Figure()

    # Dados históricos
    if not historical.empty and tag_name in historical.columns:
        fig.add_trace(go.Scatter(
            x=historical["timestamp"],
            y=historical[tag_name],
            mode="lines",
            name="Histórico",
            line=dict(color="#3b82f6", width=3, shape="spline"),
            fill="tozeroy",
            fillcolor="rgba(59, 130, 246, 0.1)",
        ))

    # Previsão
    if forecast_values:
        try:
            n = len(forecast_values)
            last_ts = (
                pd.to_datetime(historical["timestamp"].iloc[-1])
                if not historical.empty
                else pd.Timestamp.now()
            )
            # Build forecast timestamps using timedelta to avoid freq issues
            forecast_ts = [
                last_ts + pd.Timedelta(minutes=i + 1) for i in range(n)
            ]

            fig.add_trace(go.Scatter(
                x=forecast_ts,
                y=forecast_values,
                mode="lines",
                name="Previsão",
                line=dict(color="#8b5cf6", width=3, dash="dash", shape="spline"),
                fill="tozeroy",
                fillcolor="rgba(139, 92, 246, 0.1)",
            ))

            # Bandas de confiança
            if forecast_upper and forecast_lower:
                fig.add_trace(go.Scatter(
                    x=list(forecast_ts) + list(forecast_ts[::-1]),
                    y=list(forecast_upper) + list(forecast_lower[::-1]),
                    fill="toself",
                    fillcolor="rgba(139,92,246,0.1)",
                    line=dict(color="rgba(0,0,0,0)"),
                    name="Intervalo de Confiança",
                    showlegend=True,
                ))
        except Exception:
            pass  # Silently skip forecast if timestamp parsing fails

    # Limite crítico
    if critical_limit is not None:
        fig.add_hline(
            y=critical_limit,
            line_dash="dot",
            line_color="#ef4444",
            line_width=2,
            annotation_text=f"🔴 Limite Crítico: {critical_limit}{unit}",
            annotation_position="top right",
            annotation_font_color="#ef4444",
        )

    # Timestamp de falha prevista
    if failure_timestamp:
        try:
            failure_dt = pd.to_datetime(failure_timestamp)
        except Exception:
            failure_dt = failure_timestamp
        fig.add_vline(
            x=failure_dt,
            line_dash="dash",
            line_color="#ef4444",
            line_width=1.5,
            annotation_text="⚠ Falha Prevista",
            annotation_position="top",
            annotation_font_color="#ef4444",
        )

    fig.update_layout(
        **CHART_LAYOUT,
        title=dict(
            text=f"🔮 Previsão — {tag_name}",
            font=dict(size=13, color="#e2e8f0"),
        ),
        height=height,
        showlegend=True,
    )

    st.plotly_chart(fig, width="stretch")
