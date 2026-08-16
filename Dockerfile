FROM python:3.12-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

COPY pyproject.toml uv.lock README.md ./

RUN uv sync \
    --locked \
    --no-dev \
    --no-install-project

COPY src ./src

RUN mkdir -p /app/data/gold

COPY data/gold/daily_incident_volume.parquet \
     /app/data/gold/daily_incident_volume.parquet

COPY data/gold/daily_incident_breakdown.parquet \
     /app/data/gold/daily_incident_breakdown.parquet

RUN uv sync \
    --locked \
    --no-dev

EXPOSE 8501

CMD ["uv", "run", "--no-sync", "streamlit", "run", "src/albus_hub/dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--server.fileWatcherType=none"]
