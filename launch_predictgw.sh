#!/bin/bash
# PredictGW Launcher for Fedora

WORKDIR="/home/mms/Downloads/workspce/Predict"
cd "$WORKDIR"

# Verifica se o ambiente virtual existe, se não avisa
if [ ! -f ".venv/bin/activate" ]; then
    notify-send "PredictGW Erro" "Ambiente virtual (.venv) não encontrado!" -u critical
    exit 1
fi

# Inicia o servidor do Streamlit caso não esteja rodando
if ! pgrep -f "streamlit run ui/app.py" > /dev/null; then
    source .venv/bin/activate
    nohup streamlit run ui/app.py --server.port 8501 --server.headless true > /tmp/predictgw.log 2>&1 &
    sleep 3 # Aguarda o backend subir
fi

# Abre a aplicação num formato "Desktop App Window" usando Chromium/Chrome se disponível,
# caso contrário usa o xdg-open normal (Edge/Firefox padrão).
if command -v google-chrome &> /dev/null; then
    google-chrome --app="http://localhost:8501" --window-size=1200,900 --class="PredictGW"
elif command -v chromium-browser &> /dev/null; then
    chromium-browser --app="http://localhost:8501" --window-size=1200,900 --class="PredictGW"
elif command -v microsoft-edge &> /dev/null; then
    microsoft-edge --app="http://localhost:8501" --window-size=1200,900 --class="PredictGW"
else
    xdg-open "http://localhost:8501"
fi
