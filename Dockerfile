FROM python:3.11-slim

WORKDIR /app

# Dependências do sistema (curl pra healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . .

# HF Spaces injeta a porta via env (default 7860)
ENV PORT=7860
EXPOSE 7860

# Roda com gunicorn (1 worker, timeout generoso pro startup que carrega parquets)
CMD gunicorn app:server --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --access-logfile -
