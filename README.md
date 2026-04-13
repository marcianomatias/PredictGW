<h1 align="center">PredictGW — Industrial Predictive Monitoring Gateway</h1>

<p align="center">
  <strong>Gateway SCADA Moderno para Monitoramento de Ativos Industriais e Análise Preditiva</strong><br>
  Desenvolvido por <strong>Marciano Matias</strong>
</p>

---

## 📌 Visão Geral

O **PredictGW** é um sistema modular "Plug & Play" projetado para ambientes industriais (Indústria 4.0), que atua como um Gateway de Telemetria e Monitoramento. Ele foi desenvolvido com foco em alta performance, robustez e uma interface estética futurista (Dark Premium).

O sistema suporta nativamente protocolos industriais como **Modbus TCP** e **REST/JSON**, gerindo múltiplos dispositivos simultaneamente (Inversores de Frequência, CLPs e Sensores Inteligentes) através de uma arquitetura baseada em concorrência (Threads) provendo inteligência artificial analítica na beira da máquina (*Edge Computing*).

## ✨ Principais Funcionalidades

1. **Protocolos Industriais Plug & Play**: Suporte para Múltiplas Fontes (Modbus/TCP e JSON HTTP). A adição de novos dispositivos é tão simples quanto atualizar o arquivo *config.yaml*.
2. **Dashboard SCADA Premium**: Interface avançada Web gerada em Python, utilizando SVGs hiper-responsivos, *glassmorphism* e Dark Mode absoluto, projetada sob medida para ambientes de alto rigor visual.
3. **Anomalias & Previsão de Falha (RUL - Remaining Useful Life)**:
   - **Machine Learning Integrado**: O Motor Preditivo utiliza Scikit-Learn e Statsmodels para detectar Outliers (Isolation Forest) e projetar o tempo restante de vida útil dos equipamentos.
   - **Fallback Dinâmico**: A plataforma engloba scripts R via *rpy2*, mas se readapta perfeitamente para Python Nativo caso a linguagem R falte no host.
4. **Exportação de Relatórios Avançados**:
   - Geração dinâmica de PDFs robustos detalhando o status, saúde geral, alertas e buffer de cada sensor.
   - Exportação bruta (CSV) em tempo real da memória unificada persistida.
5. **Multi-Threaded Polling Engine**: Ciclo de leitura isolado e ininterrupto para estabilidade de I/O em paralelo à interface administrativa.

## 🏗️ Arquitetura do Sistema

O projeto é estruturado em três domínios principais:

*   **`core/` (Backend Edge)**: Gestão dos protocolos (`JSONDevice`, `ModbusDevice`), roteamento de rede, configuração (via YAML) e Buffer Circular em Memória que sustenta a retenção otimizada dos Timestamps utilizando `pandas`.
*   **`analytics/` (Motor Preditivo)**: Classe `HealthManager` e `PredictiveEngine` encarregadas da orquestração dos dados matemáticos, executando periodicamente a identificação das anomalias sem bloquear a thread principal usando as capacidades preditivas de IA.
*   **`ui/` (Interface do Usuário)**: Operada via Streamlit modificado contendo os dashboards de `Inversores`, `CLPs`, `Análise Preditiva` e `Sistema`. Foram reescritos os componentes gráficos (`gauge`, `io_matrix`, `health_badge`) como instâncias injetáveis garantindo responsividade vetorial.


## 🚀 Como Executar o Projeto

### 1. Pré-Requisitos

Certifique-se de ter o Python 3.10+ (ou superior) instalado e um ambiente virtual ativado:

```bash
# Criação do ambiente virtual
python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
```

### 2. Instalação das Dependências

Instale as bibliotecas base utilizando o NPM/Pip.

```bash
pip install pandas numpy streamlit plotly pyyaml pymodbus scikit-learn statsmodels fpdf2
```

*(Opcional: Instale o `rpy2` se desejar habilitar a integração com R-Scripts profundos caso o R Base já esteja no seu sistema).*


### 3. Ajuste o Arquivo de Configuração

Configure e crie/edite o seu arquivo `config.yaml` caso precise mudar as variáveis ou simular dispositivos fora da rede em: `core/config.yaml`

```yaml
system:
  simulation_mode: true
  buffer_capacity: 500
```

### 4. Inicialização do Gateway

A interface web utiliza a engine Streamlit, configurada internamente pela infraestrutura da pasta raiz para usar a UI otimizada de SCADA:

```bash
streamlit run ui/app.py
```
O console injetará o status dos CLPs, Inversores e do Motor Preditivo. Acesse http://localhost:8501 e veja os monitoramentos na sua tela.

## ⚙️ Implantação e Servidor Contínuo
Recomenda-se rodar usando gerenciadores em background (como SystemD no Linux ou no cron/nohup). A configuração do `.streamlit/config.toml` previne que a aplicação mude para Light Mode indevidamente, o que é mandatório para um deployment seguro em chão de fábrica. 

---
### Direitos e Autoria
**Sistema Preditivo Gateway (PredictGW)** foi arquitetado e **Software-Engineered por Marciano Matias.**
© 2026 Reservado.
