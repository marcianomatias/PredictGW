"""
PredictGW — Main Streamlit Application
Dashboard industrial premium com abas para Inversores, CLPs e Análise Preditiva.
"""

import sys
import os
import time
import logging
from pathlib import Path
from datetime import datetime

import streamlit as st

# Add project root to path
PROJECT_ROOT = str(Path(__file__).parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.device_manager import DeviceManager
from analytics.predictive_engine import PredictiveEngine
from ui.views.inverters import render_inverters_page
from ui.views.plcs import render_plcs_page
from ui.views.predictive import render_predictive_page
from ui.export import export_buffer_csv, generate_report_pdf

# ============================================================
# Configuration
# ============================================================

st.set_page_config(
    page_title="PredictGW — Industrial Monitoring",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Load custom CSS
CSS_PATH = Path(__file__).parent / "styles" / "custom.css"
if CSS_PATH.exists():
    with open(CSS_PATH) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Google Fonts
st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">',
    unsafe_allow_html=True,
)

# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

# ============================================================
# Initialize System (cached)
# ============================================================


@st.cache_resource
def init_system():
    """Inicializa o DeviceManager e PredictiveEngine (singleton)."""
    config_path = os.path.join(PROJECT_ROOT, "config.yaml")

    dm = DeviceManager(config_path=config_path)
    dm.start()

    # Get R engine preference from config
    system_cfg = dm.config.get("system", {})
    r_engine = system_cfg.get("r_engine", "auto")
    analytics_interval = system_cfg.get("analytics_interval_s", 30)

    pe = PredictiveEngine(
        device_manager=dm,
        r_engine=r_engine,
        interval_s=analytics_interval,
    )
    pe.start()

    return dm, pe


device_manager, predictive_engine = init_system()


# ============================================================
# Header
# ============================================================

def render_header():
    """Renderiza o header do dashboard."""
    system_status = device_manager.get_system_status()
    engine_status = predictive_engine.get_status()
    overall_health = engine_status.get("overall_health", 100)

    # Health color
    if overall_health >= 85:
        h_color = "#22c55e"
    elif overall_health >= 70:
        h_color = "#84cc16"
    elif overall_health >= 50:
        h_color = "#eab308"
    elif overall_health >= 30:
        h_color = "#f97316"
    else:
        h_color = "#ef4444"

    sim_badge = ""
    if device_manager.simulation_mode:
        sim_badge = (
            '<span style="background: rgba(139,92,246,0.15); '
            'color: #a78bfa; padding: 4px 10px; border-radius: 100px; '
            'font-size: 0.65rem; font-weight: 700; '
            'text-transform: uppercase; letter-spacing: 0.05em; '
            'border: 1px solid rgba(139,92,246,0.3); '
            'margin-left: 12px;">🔬 SIMULAÇÃO</span>'
        )

    st.markdown(
        f"""
        <div class="header-bar">
            <div>
                <div class="header-title">
                    🏭 PredictGW {sim_badge}
                </div>
                <div class="header-subtitle">
                    Industrial Predictive Monitoring Gateway v1.0
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 1.5rem;">
                <div style="text-align: center;">
                    <div style="font-size: 0.65rem; color: #64748b; 
                         text-transform: uppercase; font-weight: 600;">
                        Dispositivos
                    </div>
                    <div style="font-size: 1.2rem; font-weight: 800;
                         color: #e2e8f0;">
                        <span style="color: #10b981;">
                            {system_status['online_devices']}</span>
                        <span style="color: #64748b; font-size: 0.8rem;"> / </span>
                        {system_status['total_devices']}
                    </div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 0.65rem; color: #64748b; 
                         text-transform: uppercase; font-weight: 600;">
                        Engine
                    </div>
                    <div style="font-size: 1rem; font-weight: 700; 
                         color: #8b5cf6;">
                        {engine_status['engine'].upper()}
                    </div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 0.65rem; color: #64748b; 
                         text-transform: uppercase; font-weight: 600;">
                        Health Geral
                    </div>
                    <div style="font-size: 1.3rem; font-weight: 800; 
                         color: {h_color};">
                        {overall_health:.0f}
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.65rem; color: #64748b;">
                        {datetime.now().strftime('%d/%m/%Y')}
                    </div>
                    <div style="font-size: 0.9rem; font-weight: 600; 
                         color: #e2e8f0;">
                        {datetime.now().strftime('%H:%M:%S')}
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


render_header()

# ============================================================
# Main Tabs
# ============================================================

tab_inv, tab_plc, tab_pred, tab_sys = st.tabs([
    "🔌 Inversores",
    "⚙️ CLPs",
    "📊 Análise Preditiva",
    "🛠️ Sistema",
])

# ---- Tab: Inversores ----
with tab_inv:
    render_inverters_page(
        inverters=device_manager.get_inverters(),
        buffer=device_manager.buffer,
        health_manager=predictive_engine.health_manager,
    )

# ---- Tab: CLPs ----
with tab_plc:
    render_plcs_page(
        plcs=device_manager.get_plcs(),
        buffer=device_manager.buffer,
        health_manager=predictive_engine.health_manager,
    )

# ---- Tab: Análise Preditiva ----
with tab_pred:
    render_predictive_page(
        device_manager=device_manager,
        predictive_engine=predictive_engine,
    )

# ---- Tab: Sistema ----
with tab_sys:
    st.markdown("### 🛠️ Status do Sistema")

    # System info
    sys_status = device_manager.get_system_status()

    sys_cols = st.columns(4)
    with sys_cols[0]:
        st.metric("Total Dispositivos", sys_status["total_devices"])
    with sys_cols[1]:
        st.metric("Online", sys_status["online_devices"])
    with sys_cols[2]:
        st.metric("Offline", sys_status["offline_devices"])
    with sys_cols[3]:
        engine_st = predictive_engine.get_status()
        st.metric("Engine", engine_st["engine"].upper())

    st.markdown("---")

    # Device details
    st.markdown("### 📋 Dispositivos Configurados")

    for dev_id, info in sys_status.get("devices", {}).items():
        status_emoji = {
            "online": "🟢",
            "warning": "🟡",
            "offline": "🔴",
            "error": "🔴",
            "connecting": "🔵",
        }.get(info["status"], "⚫")

        with st.expander(
            f"{status_emoji} {info['name']} ({dev_id})"
        ):
            detail_cols = st.columns(3)
            with detail_cols[0]:
                st.markdown(f"**Tipo:** {info['type']}")
                st.markdown(f"**Protocolo:** {info['protocol']}")
                st.markdown(f"**Status:** {info['status']}")
            with detail_cols[1]:
                st.markdown(f"**Total Polls:** {info['total_polls']}")
                st.markdown(f"**Sucesso:** {info['successful_polls']}")
                st.markdown(
                    f"**Uptime:** {info['uptime_ratio'] * 100:.1f}%"
                )
            with detail_cols[2]:
                st.markdown(f"**Tags:** {info['tags_count']}")
                st.markdown(
                    f"**Erros Consec.:** {info['consecutive_errors']}"
                )
                st.markdown(f"**Último Poll:** {info['last_poll_time']}")

    # Buffer info
    st.markdown("---")
    st.markdown("### 💾 Status do Buffer")

    buffer_info = device_manager.buffer.get_buffer_info()
    for dev_id, binfo in buffer_info.items():
        device = device_manager.get_device(dev_id)
        name = device.name if device else dev_id
        st.markdown(
            f"- **{name}**: {binfo['records']}/{binfo['max_size']} registros "
            f"({binfo['memory_bytes'] / 1024:.1f} KB)"
        )

    # Export Area
    st.markdown("---")
    st.markdown("### 📥 Exportação de Dados e Relatórios")
    st.markdown(
        "Utilize as opções abaixo para gerar relatórios detalhados em PDF ou extrair os "
        "dados puros em formato CSV para análise externa."
    )
    
    exp_cols = st.columns([1, 1, 2])
    with exp_cols[0]:
        pdf_data = generate_report_pdf(device_manager, predictive_engine.health_manager, predictive_engine)
        st.download_button(
            label="📄 Gerar Relatório (PDF)",
            data=pdf_data,
            file_name=f"PredictGW_Relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )
    with exp_cols[1]:
        csv_data = export_buffer_csv(device_manager.buffer, device_manager)
        st.download_button(
            label="📊 Exportar Dados (CSV)",
            data=csv_data,
            file_name=f"PredictGW_Dados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # R Engine details
    st.markdown("---")
    st.markdown("### 🧠 Motor Preditivo")
    r_status = predictive_engine.bridge.status()
    st.json(r_status)

    # Plug & Play instructions
    st.markdown("---")
    st.markdown("### 🔌 Plug & Play — Como Adicionar Dispositivos")
    st.markdown(
        """
        Para adicionar um novo dispositivo ao sistema, basta editar o arquivo
        `config.yaml` e adicionar um novo bloco sob `devices:`.
        
        **Exemplo — Adicionar CLP de Esteira:**
        ```yaml
        - id: "clp_esteira_01"
          name: "CLP Esteira Transportadora"
          type: "plc"
          protocol: "modbus_tcp"
          connection:
            host: "192.168.1.101"
            port: 502
            unit_id: 2
            timeout_s: 3
          tags:
            - name: "Motor Esteira"
              type: "digital_output"
              register_type: "coil"
              address: 0
            - name: "Velocidade"
              type: "analog"
              unit: "m/min"
              register_type: "input_register"
              address: 0
              scale: 0.01
              limits:
                warning_high: 25.0
                critical_high: 30.0
        ```
        
        Após salvar, reinicie a aplicação para detectar o novo dispositivo.
        """
    )

# ============================================================
# Footer Fixo (Profissional)
# ============================================================

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .predict-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background: rgba(10,14,23,0.85);
        backdrop-filter: blur(12px);
        border-top: 1px solid rgba(148,163,184,0.1);
        padding: 10px 0;
        z-index: 99999;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 15px;
        box-shadow: 0 -4px 30px rgba(0,0,0,0.5);
    }
    .predict-footer-text {
        font-family: 'Inter', sans-serif;
        font-size: 0.8rem;
        color: #94a3b8;
        letter-spacing: 0.05em;
    }
    .predict-dev-name {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .predict-badge {
        font-size: 0.65rem;
        color: #8b5cf6;
        background: rgba(139,92,246,0.15);
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        border: 1px solid rgba(139,92,246,0.3);
    }
    .predict-dot {
        width: 4px; height: 4px; border-radius: 50%;
        background: #475569;
    }
    
    /* Ensure body doesn't hide behind the footer */
    .stApp {
        padding-bottom: 60px !important;
    }
    </style>
    
    <div class="predict-footer">
        <span class="predict-footer-text">
            Desenvolvido por <strong class="predict-dev-name">Marciano Matias</strong>
        </span>
        <span class="predict-dot"></span>
        <span class="predict-footer-text" style="font-weight: 600;">© 2026</span>
        <span class="predict-dot"></span>
        <span class="predict-badge">PredictGW v1.0</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Auto-refresh
# ============================================================

# Refresh every 3 seconds
time.sleep(3)
st.rerun()
