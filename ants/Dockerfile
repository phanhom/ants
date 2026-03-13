# Ants runtime: Queen or Worker (compose overrides CMD).
FROM python:3.13-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml ./
COPY ants/ ants/
COPY configs/ configs/
RUN pip install --no-cache-dir -e .

FROM python:3.13-slim AS runtime
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY . .

EXPOSE 22100
CMD ["uvicorn", "ants.queen.api:app", "--host", "0.0.0.0", "--port", "22100"]
