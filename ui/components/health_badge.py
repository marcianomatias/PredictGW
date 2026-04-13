"""
PredictGW — Health Badge Component
Badge circular com Health Score 0-100 e classificação.
Usa streamlit.components.v1.html para renderização confiável.
"""

import streamlit as st
import streamlit.components.v1 as components


def render_health_badge(
    score: float,
    classification: str = "",
    color: str = "#10b981",
    size: int = 130,
    show_label: bool = True,
) -> None:
    """Renderiza o badge circular do Health Score."""
    pct = max(0, min(100, score))

    if not color:
        if score >= 85:
            color = "#22c55e"
        elif score >= 70:
            color = "#84cc16"
        elif score >= 50:
            color = "#eab308"
        elif score >= 30:
            color = "#f97316"
        else:
            color = "#ef4444"

    if not classification:
        if score >= 85:
            classification = "Excelente"
        elif score >= 70:
            classification = "Bom"
        elif score >= 50:
            classification = "Atenção"
        elif score >= 30:
            classification = "Alerta"
        else:
            classification = "Crítico"

    if score >= 85:
        icon = "💚"
    elif score >= 70:
        icon = "💛"
    elif score >= 50:
        icon = "🟡"
    elif score >= 30:
        icon = "🟠"
    else:
        icon = "🔴"

    r = size / 2 - 8
    circ = 2 * 3.14159 * r
    offset = circ * (1 - pct / 100)

    label_html = ""
    if show_label:
        label_html = f"""
        <div style="text-align:center; margin-top:0.5rem;">
            <span style="font-size:0.8rem; font-weight:700; color:{color};
                         font-family:Inter,sans-serif;">
                {icon} {classification}
            </span>
        </div>
        """

    html = f"""
    <div style="text-align:center;">
        <div style="position:relative; width:{size}px; height:{size}px; margin:0 auto;">
            <svg viewBox="0 0 {size} {size}" width="{size}" height="{size}"
                 style="transform:rotate(-90deg);">
                <circle cx="{size/2}" cy="{size/2}" r="{r}"
                    fill="none" stroke="#1e293b" stroke-width="8"/>
                <circle cx="{size/2}" cy="{size/2}" r="{r}"
                    fill="none" stroke="{color}" stroke-width="8"
                    stroke-linecap="round"
                    stroke-dasharray="{circ}"
                    stroke-dashoffset="{offset}"
                    style="transition:stroke-dashoffset 1s ease;
                           filter:drop-shadow(0 0 6px {color});"/>
            </svg>
            <div style="position:absolute; top:50%; left:50%;
                        transform:translate(-50%,-50%); text-align:center;">
                <div style="font-size:{size*0.22}px; font-weight:800; color:{color};
                     line-height:1; font-family:Inter,sans-serif;">{score:.0f}</div>
                <div style="font-size:{size*0.08}px; color:#64748b;
                     text-transform:uppercase; letter-spacing:0.1em;
                     margin-top:4px; font-weight:600;
                     font-family:Inter,sans-serif;">HEALTH</div>
            </div>
        </div>
        {label_html}
    </div>
    """
    components.html(html, height=size + (35 if show_label else 5))


def render_health_summary(
    components_data: dict,
    compact: bool = False,
) -> None:
    """Renderiza o breakdown do Health Score."""
    items = [
        ("Anomalias", components_data.get("anomaly_score", 0), "40%", "#3b82f6"),
        ("RUL", components_data.get("rul_score", 0), "30%", "#8b5cf6"),
        ("Variância", components_data.get("variance_score", 0), "20%", "#06b6d4"),
        ("Uptime", components_data.get("uptime_score", 0), "10%", "#10b981"),
    ]

    html = ""
    for label, value, weight, color in items:
        bar_width = max(0, min(100, value))
        html += f"""
        <div style="margin-bottom:0.5rem;">
            <div style="display:flex; justify-content:space-between;
                        font-size:0.7rem; color:#94a3b8; margin-bottom:3px;
                        font-family:Inter,sans-serif;">
                <span>{label} ({weight})</span>
                <span style="font-weight:700; color:{color};">{value:.0f}</span>
            </div>
            <div style="background:#1e293b; border-radius:4px; height:6px;
                        overflow:hidden;">
                <div style="background:{color}; width:{bar_width}%; height:100%;
                     border-radius:4px; transition:width 0.5s ease;
                     box-shadow:0 0 6px {color};"></div>
            </div>
        </div>
        """

    st.markdown(html, unsafe_allow_html=True)
