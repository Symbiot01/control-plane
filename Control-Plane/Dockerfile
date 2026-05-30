# Control Plane API – run on a VM with managed Postgres + Redis.
# Build: docker build -t control-plane .
# Run:  docker run --env-file .env -p 8000:8000 control-plane

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app

RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Uses GET /health (no auth). start-period allows Redis/DB/Firebase init on first boot.
HEALTHCHECK --interval=60s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
