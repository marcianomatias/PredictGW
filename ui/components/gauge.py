"""
PredictGW — Gauge Component
Indicador circular animado com SVG para métricas de inversores.
Usa streamlit.components.v1.html para renderização confiável.
"""

import streamlit as st
import streamlit.components.v1 as components
import math


def render_gauge(
    value: float,
    min_val: float,
    max_val: float,
    title: str,
    unit: str = "",
    warning_high: float = None,
    critical_high: float = None,
    warning_low: float = None,
    critical_low: float = None,
    size: int = 160,
) -> None:
    """
    Renderiza um gauge circular SVG no Streamlit.
    """
    clamped = max(min_val, min(max_val, value)) if value is not None else min_val
    pct = (clamped - min_val) / (max_val - min_val) if max_val > min_val else 0

    color = "#10b981"
    if value is not None:
        if critical_high and value >= critical_high:
            color = "#ef4444"
        elif critical_low and value <= critical_low:
            color = "#ef4444"
        elif warning_high and value >= warning_high:
            color = "#f59e0b"
        elif warning_low and value <= warning_low:
            color = "#f59e0b"

    cx, cy = size / 2, size / 2
    radius = size / 2 - 15
    stroke_width = 10
    start_angle = 135
    end_angle = 405
    total_angle = end_angle - start_angle
    value_angle = start_angle + pct * total_angle

    bg_arc = _arc_path(cx, cy, radius, start_angle, end_angle)
    val_arc = _arc_path(cx, cy, radius, start_angle, value_angle)

    ticks_svg = ""
    for lim_val, lim_color in [
        (warning_low, "#f59e0b"),
        (warning_high, "#f59e0b"),
        (critical_low, "#ef4444"),
        (critical_high, "#ef4444"),
    ]:
        if lim_val is not None and min_val < lim_val < max_val:
            lim_pct = (lim_val - min_val) / (max_val - min_val)
            lim_angle = start_angle + lim_pct * total_angle
            rad = math.radians(lim_angle)
            x1 = cx + (radius - 8) * math.cos(rad)
            y1 = cy + (radius - 8) * math.sin(rad)
            x2 = cx + (radius + 8) * math.cos(rad)
            y2 = cy + (radius + 8) * math.sin(rad)
            ticks_svg += (
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'stroke="{lim_color}" stroke-width="2" opacity="0.6"/>'
            )

    display_val = f"{value:.1f}" if value is not None else "—"
    filter_id = f"glow-{title.replace(' ', '').replace('ê','e').replace('á','a').replace('ã','a')}"

    html = f"""
    <div style="text-align:center; padding:0.5rem;">
        <svg viewBox="0 0 {size} {size}" width="{size}" height="{size}"
             style="filter: drop-shadow(0 2px 8px rgba(0,0,0,0.3));">
            <defs>
                <filter id="{filter_id}">
                    <feGaussianBlur stdDeviation="3" result="blur"/>
                    <feMerge>
                        <feMergeNode in="blur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
            </defs>
            <path d="{bg_arc}" fill="none" stroke="#1e293b"
                  stroke-width="{stroke_width}" stroke-linecap="round"/>
            <path d="{val_arc}" fill="none" stroke="{color}"
                  stroke-width="{stroke_width}" stroke-linecap="round"
                  filter="url(#{filter_id})"
                  style="transition: all 0.5s ease;"/>
            {ticks_svg}
            <text x="{cx}" y="{cy - 5}" text-anchor="middle"
                  fill="{color}" font-size="24" font-weight="800"
                  font-family="Inter, sans-serif">{display_val}</text>
            <text x="{cx}" y="{cy + 14}" text-anchor="middle"
                  fill="#94a3b8" font-size="11" font-weight="600"
                  font-family="Inter, sans-serif">{unit}</text>
            <text x="15" y="{size - 5}" fill="#64748b" font-size="9"
                  font-family="Inter, sans-serif">{min_val:.0f}</text>
            <text x="{size - 15}" y="{size - 5}" fill="#64748b" font-size="9"
                  text-anchor="end"
                  font-family="Inter, sans-serif">{max_val:.0f}</text>
        </svg>
        <div style="font-size:0.8rem; color:#94a3b8; margin-top:0.5rem;
             padding-bottom:0.5rem;
             font-weight:600; text-transform:uppercase; letter-spacing:0.05em;
             font-family:Inter,sans-serif;">{title}</div>
    </div>
    """
    components.html(html, height=size + 55)


def _arc_path(
    cx: float, cy: float, r: float,
    start_deg: float, end_deg: float,
) -> str:
    """Gera o path SVG para um arco."""
    start_rad = math.radians(start_deg)
    end_rad = math.radians(end_deg)

    x1 = cx + r * math.cos(start_rad)
    y1 = cy + r * math.sin(start_rad)
    x2 = cx + r * math.cos(end_rad)
    y2 = cy + r * math.sin(end_rad)

    angle_diff = end_deg - start_deg
    large_arc = 1 if angle_diff > 180 else 0

    return f"M {x1} {y1} A {r} {r} 0 {large_arc} 1 {x2} {y2}"
