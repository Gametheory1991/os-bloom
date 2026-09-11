FROM python:3.12-slim
WORKDIR /app

COPY collector/pyproject.toml /app/collector/pyproject.toml
COPY collector/src /app/collector/src
RUN pip install --no-cache-dir /app/collector

COPY config.yaml /app/config.yaml
COPY ui /app/ui

ENV CONFIG_PATH=/app/config.yaml
ENV DB_PATH=/tmp/bloom.db
ENV SERVE_UI=1
ENV UI_PATH=/app/ui
ENV PORT=10000

EXPOSE 10000
CMD ["python", "-m", "collector.main"]
