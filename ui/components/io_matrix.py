"""
PredictGW — IO Matrix Component
Matriz visual de estados digitais para CLPs com indicadores LED.
Usa streamlit.components.v1.html para renderização confiável.
"""

import streamlit as st
import streamlit.components.v1 as components


def render_io_matrix(
    readings: dict,
    tags: list,
    title: str = "Estados I/O",
) -> None:
    """
    Renderiza uma matriz de I/O digitais com LEDs estilo SCADA.
    """
    digital_inputs = []
    digital_outputs = []

    for tag in tags:
        if tag.tag_type == "digital_input":
            reading = readings.get(tag.name)
            value = reading.value if reading else None
            digital_inputs.append((tag.name, value))
        elif tag.tag_type == "digital_output":
            reading = readings.get(tag.name)
            value = reading.value if reading else None
            digital_outputs.append((tag.name, value))

    css = """
    <style>
        body { margin: 0; padding: 0; background: transparent; font-family: Inter, sans-serif; }
        .section-label {
            color: #94a3b8; font-size: 0.75rem; text-transform: uppercase;
            letter-spacing: 0.05em; font-weight: 600; margin-bottom: 0.5rem;
        }
        .io-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            gap: 0.75rem; margin: 0.5rem 0;
        }
        .io-item {
            background: #1a1f2e; border: 1px solid rgba(148,163,184,0.1);
            border-radius: 8px; padding: 0.75rem; display: flex;
            align-items: center; gap: 0.625rem;
        }
        .io-led {
            width: 16px; height: 16px; border-radius: 50%; flex-shrink: 0;
            border: 2px solid rgba(255,255,255,0.1);
        }
        .io-led.on {
            background: #10b981;
            box-shadow: 0 0 10px #10b981, inset 0 0 4px rgba(255,255,255,0.3);
        }
        .io-led.off {
            background: #374151;
            box-shadow: inset 0 1px 3px rgba(0,0,0,0.3);
        }
        .io-led.alarm {
            background: #ef4444;
            box-shadow: 0 0 10px #ef4444, inset 0 0 4px rgba(255,255,255,0.3);
            animation: blink-led 0.5s infinite;
        }
        @keyframes blink-led {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        .io-name { font-size: 0.75rem; color: #94a3b8; font-weight: 500; line-height: 1.3; }
        .io-status { font-size: 0.7rem; font-weight: 700; margin-top: 2px; }
    </style>
    """

    html = css
    total_items = 0

    if digital_inputs:
        html += '<div class="section-label">📥 Entradas Digitais</div>'
        html += _build_led_grid(digital_inputs)
        total_items += len(digital_inputs)

    if digital_outputs:
        html += '<div class="section-label" style="margin-top:1rem;">📤 Saídas Digitais</div>'
        html += _build_led_grid(digital_outputs)
        total_items += len(digital_outputs)

    # Calculate height based on number of items
    rows = max(1, (total_items + 3) // 4)  # ~4 items per row
    height = rows * 85 + (60 if digital_inputs and digital_outputs else 30) + 30

    components.html(html, height=height)


def _build_led_grid(items: list[tuple[str, float | None]]) -> str:
    """Gera o HTML do grid de LEDs."""
    html = '<div class="io-grid">'

    for name, value in items:
        is_on = value is not None and value > 0
        is_alarm = "Emergência" in name or "Alarme" in name

        if is_alarm and is_on:
            led_class = "alarm"
            status_text = "ATIVO !"
            text_color = "#ef4444"
        elif is_on:
            led_class = "on"
            status_text = "ON"
            text_color = "#10b981"
        else:
            led_class = "off"
            status_text = "OFF"
            text_color = "#64748b"

        html += f"""
        <div class="io-item">
            <div class="io-led {led_class}"></div>
            <div>
                <div class="io-name">{name}</div>
                <div class="io-status" style="color:{text_color};">{status_text}</div>
            </div>
        </div>
        """

    html += '</div>'
    return html


def render_io_summary(
    readings: dict,
    tags: list,
) -> dict:
    """Retorna um sumário dos estados I/O."""
    di_on = di_off = do_on = do_off = 0

    for tag in tags:
        reading = readings.get(tag.name)
        value = reading.value if reading else None
        is_on = value is not None and value > 0

        if tag.tag_type == "digital_input":
            if is_on:
                di_on += 1
            else:
                di_off += 1
        elif tag.tag_type == "digital_output":
            if is_on:
                do_on += 1
            else:
                do_off += 1

    return {
        "digital_inputs_on": di_on,
        "digital_inputs_off": di_off,
        "digital_outputs_on": do_on,
        "digital_outputs_off": do_off,
        "total_on": di_on + do_on,
        "total_off": di_off + do_off,
    }
