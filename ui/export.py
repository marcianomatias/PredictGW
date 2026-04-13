"""
PredictGW — Export Module
Exportação de dados para CSV e relatórios PDF.
"""

import io
from datetime import datetime

import pandas as pd

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False


def export_buffer_csv(
    buffer,
    device_manager,
) -> bytes:
    """Exporta todos os dados do buffer como CSV."""
    all_frames = []

    for dev_id in buffer._buffers:
        df = buffer.get_buffer(dev_id, last_n=None)
        if not df.empty:
            device = device_manager.get_device(dev_id)
            name = device.name if device else dev_id
            df = df.copy()
            df.insert(0, "dispositivo_id", dev_id)
            df.insert(1, "dispositivo_nome", name)
            all_frames.append(df)

    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True)
    else:
        combined = pd.DataFrame({"info": ["Nenhum dado disponível"]})

    output = io.BytesIO()
    combined.to_csv(output, index=False, encoding="utf-8-sig")
    return output.getvalue()


def export_device_csv(
    buffer,
    dev_id: str,
    device_name: str,
) -> bytes:
    """Exporta dados de um dispositivo específico como CSV."""
    df = buffer.get_buffer(dev_id, last_n=None)
    if df.empty:
        df = pd.DataFrame({"info": [f"Sem dados para {device_name}"]})

    output = io.BytesIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    return output.getvalue()


def generate_report_pdf(
    device_manager,
    health_manager,
    predictive_engine,
) -> bytes:
    """Gera relatório PDF completo do sistema."""
    if not HAS_FPDF:
        return _generate_fallback_report(
            device_manager, health_manager, predictive_engine
        )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ---- HEADER ----
    pdf.set_fill_color(17, 24, 39) # Dark background
    pdf.rect(0, 0, 210, 45, "F")
    
    # Title
    pdf.set_y(12)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(139, 92, 246) # Purple vibrant
    pdf.cell(0, 10, "PredictGW", ln=True, align="C")
    
    # Subtitle
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(226, 232, 240)
    pdf.cell(0, 6, "Industrial Predictive Monitoring Gateway", ln=True, align="C")

    # Date
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 8, f"Relatório Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}", ln=True, align="C")
    
    pdf.ln(12)

    # ---- 1. Status do Sistema ----
    sys_status = device_manager.get_system_status()
    engine_status = predictive_engine.get_status()

    pdf.set_fill_color(248, 250, 252)
    pdf.rect(10, pdf.get_y(), 190, 40, "F")
    
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(15, 23, 42)
    pdf.set_xy(15, pdf.get_y() + 5)
    pdf.cell(0, 8, "1. Status do Sistema", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_x(15)
    _add_info_row(pdf, "Total de Dispositivos", str(sys_status["total_devices"]))
    pdf.set_x(15)
    _add_info_row(pdf, "Dispositivos Online", f"{sys_status['online_devices']} / {sys_status['total_devices']}")
    pdf.set_x(15)
    _add_info_row(pdf, "Motor Preditivo", engine_status["engine"].upper())
    pdf.set_x(15)
    _add_info_row(pdf, "Saúde Geral", f"{engine_status.get('overall_health', 100):.0f}/100")
    
    pdf.ln(12)

    # ---- 2. Dispositivos e Saúde ----
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, "2. Análise Detalhada dos Dispositivos", ln=True)
    pdf.set_draw_color(139, 92, 246)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    all_scores = health_manager.get_all_scores()
    
    for dev_id, info in sys_status.get("devices", {}).items():
        # Device Header
        status_color = (16, 185, 129) if info["status"] == "online" else (239, 68, 68)
        pdf.set_text_color(*status_color)
        pdf.set_font("Helvetica", "B", 12)
        status_icon = "✓" if info["status"] == "online" else "✗"
        pdf.cell(0, 8, f"{status_icon} {info['name']} ({dev_id})", ln=True)
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(71, 85, 105)
        
        # Grid format for device details
        start_y = pdf.get_y()
        pdf.set_xy(15, start_y)
        _add_info_row(pdf, "Protocolo", info["protocol"].upper())
        pdf.set_xy(15, pdf.get_y())
        _add_info_row(pdf, "Uptime", f"{info['uptime_ratio'] * 100:.1f}%")
        
        pdf.set_xy(80, start_y)
        _add_info_row(pdf, "Tags monitoradas", str(info["tags_count"]))
        pdf.set_xy(80, pdf.get_y() - 6) # Align horizontally
        pdf.ln(6)
        
        health = health_manager.get_score(dev_id)
        if health:
            pdf.set_xy(80, start_y + 6)
            _add_info_row(pdf, "Health Score", f"{health.score:.0f}/100 [{health.classification}]")
            pdf.ln(2)
            
            anom_count = health.components.get("anomaly_count", 0)
            pdf.set_x(15)
            _add_info_row(pdf, "Anomalias Detectadas", str(anom_count))
            
            if health.rul_hours is not None and health.rul_hours != float("inf"):
                pdf.set_x(15)
                _add_info_row(pdf, "Previsão de Falha", health.rul_text)
                
        pdf.ln(6)
        pdf.set_draw_color(226, 232, 240)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(4)

    # ---- 3. Resumo por Tabela ----
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, "3. Resumo Preditivo", ln=True)
    pdf.ln(2)

    if all_scores:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(139, 92, 246)
        pdf.set_text_color(255, 255, 255)
        pdf.set_draw_color(255, 255, 255)
        
        col_widths = [60, 25, 30, 45, 30]
        headers = ["Dispositivo", "Score", "Classe", "RUL", "Anomalias"]
        for w, h in zip(col_widths, headers):
            pdf.cell(w, 8, h, border=1, fill=True, align="C")
        pdf.ln()

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(51, 65, 85)
        pdf.set_fill_color(248, 250, 252)
        
        idx = 0
        for dev_id, hs in all_scores.items():
            fill = (idx % 2 == 0)
            idx += 1
            
            device = device_manager.get_device(dev_id)
            name = device.name if device else dev_id
            anom_count = hs.components.get("anomaly_count", 0)

            vals = [
                name[:25],
                f"{hs.score:.0f}",
                hs.classification,
                hs.rul_text if hs.rul_text else "-",
                str(anom_count),
            ]
            for w, v in zip(col_widths, vals):
                pdf.cell(w, 8, v, border=0, align="C", fill=fill)
            pdf.ln()
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, "Nenhum dado preditivo disponível no momento.", ln=True)

    # ---- Footer ----
    pdf.set_y(-25)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(148, 163, 184)
    pdf.set_draw_color(226, 232, 240)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)
    pdf.cell(0, 5, "Desenvolvido por Marciano Matias - PredictGW v1.0", align="C", ln=True)
    pdf.cell(0, 5, "Confidencial - Uso restrito", align="C", ln=True)

    output = io.BytesIO()
    pdf.output(output)
    return output.getvalue()


def _add_info_row(pdf, label: str, value: str):
    """Adiciona uma linha label: valor ao PDF."""
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(50, 6, label + ":", align="L")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, value, ln=True)


def _generate_fallback_report(device_manager, health_manager, predictive_engine) -> bytes:
    """Gera relatório de texto simples quando fpdf2 não está disponível."""
    lines = []
    lines.append("=" * 60)
    lines.append("PredictGW — Relatório do Sistema")
    lines.append(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    lines.append("=" * 60)
    lines.append("")

    sys_status = device_manager.get_system_status()
    engine_status = predictive_engine.get_status()

    lines.append(f"Dispositivos: {sys_status['online_devices']}/{sys_status['total_devices']} online")
    lines.append(f"Engine: {engine_status['engine'].upper()}")
    lines.append(f"Health Geral: {engine_status.get('overall_health', 100):.0f}/100")
    lines.append("")

    for dev_id, info in sys_status.get("devices", {}).items():
        lines.append(f"--- {info['name']} ({dev_id}) ---")
        lines.append(f"  Status: {info['status']}")
        lines.append(f"  Uptime: {info['uptime_ratio'] * 100:.1f}%")
        health = health_manager.get_score(dev_id)
        if health:
            lines.append(f"  Health: {health.score:.0f}/100 ({health.classification})")
        lines.append("")

    lines.append("Desenvolvido por Marciano Matias — PredictGW v1.0")
    return "\n".join(lines).encode("utf-8")
