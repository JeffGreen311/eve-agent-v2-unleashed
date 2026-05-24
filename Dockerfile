FROM python:3.11-slim

WORKDIR /app

# System deps: git for tradingagents pip install, and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential && \
    rm -rf /var/lib/apt/lists/*

# Core runtime requirements (slim — skip playwright, chromadb, solana, eth, tradingagents)
COPY requirements.docker.txt /app/requirements.docker.txt
RUN pip install --no-cache-dir -r requirements.docker.txt

# Copy project
COPY . /app

# Default workspace is /workspace (mount a volume here)
ENV EVE_WORKSPACE=/workspace
ENV EVE_IN_DOCKER=1
ENV OLLAMA_BASE_URL=http://ollama:11434
ENV OLLAMA_HOST=http://ollama:11434
ENV OLLAMA_MODEL=eve-unleashed
ENV EVE_DEFAULT_PROVIDER=ollama
ENV EVE_DEFAULT_MODEL=eve-unleashed
ENV LOCAL_MODEL=eve-unleashed
ENV LOCAL_OLLAMA_URL=http://ollama:11434
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /workspace

EXPOSE 7777

CMD ["python", "eve_server.py"]
