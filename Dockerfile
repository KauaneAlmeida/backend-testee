# ==========================================
# DOCKERFILE OTIMIZADO PARA CLOUD RUN
# ==========================================

# Imagem base Python 3.11 slim
FROM python:3.11-slim

# Metadata
LABEL maintainer="law-firm-backend"
LABEL version="2.0.0"

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Criar usuário não-root (segurança)
RUN adduser --disabled-password --gecos '' --uid 1000 appuser

# Copiar e instalar dependências Python PRIMEIRO (cache otimizado)
COPY requirements.txt ./ 
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY app/ ./app/

# Criar diretório para logs
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

# Mudar para usuário não-root
USER appuser

# Porta que Cloud Run espera ($PORT é injetada automaticamente)
EXPOSE 8080

# Variáveis de ambiente padrão para produção
ENV ENABLE_BAILEYS=false \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check otimizado
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# ==========================================
# ✅ COMANDO DE INICIALIZAÇÃO CRÍTICO
# ==========================================
# Cloud Run executa este comando
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --timeout-keep-alive 300
