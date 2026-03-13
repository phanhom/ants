# Ants runtime: API or Agent (compose overrides CMD).
# Base: Python 3.14 slim. If image not found, use 3.13-slim.
ARG PYTHON_VERSION=3.14-slim
FROM python:${PYTHON_VERSION} AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
COPY README.md ./
COPY ants/ ants/
COPY configs/ configs/
RUN pip install --no-cache-dir -e .

# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY . .

# Default: run root API. Child containers override CMD to run bootstrap.
EXPOSE 22000
CMD ["uvicorn", "ants.api.main:app", "--host", "0.0.0.0", "--port", "22000"]
