# Ants

Multi-agent collaboration: each ant = one Docker container, governed by AIP and exposed through a single status API.

- **蚁后 (queen)**: Root container = 二把手/老板；接收用户（老板的上级）指令，拆解后下发给工人容器。
- **Workers**: 蚁后启动时根据 `configs/agents/` 创建所有工人容器；每个工人暴露 HTTP 接口接收任务与上报。
- **API**: 对外接口 `/status`（端口 `22000`）、`POST /instruction`（用户指令入口）。
- **Protocol**: AIP (Ants Interaction Protocol) for same-host and remote ant-to-ant communication.

See [docs/DESIGN.md](docs/DESIGN.md) for design and [docs/function.md](docs/function.md) for technical details.

## Run

```bash
# Install (host)
pip install -e .

# API (host)
uvicorn ants.api.main:app --reload --port 22000

# Or with Docker (image defaults to API)
docker build -t ants .
docker run -p 22000:22000 ants
```

## Docker Compose

From repo root (so `PWD` is set for spawn volume binds):

```bash
export PWD=$(pwd)
docker-compose up -d
# 蚁后 (queen): http://localhost:22000/status , POST /instruction
```

Service name: `queen` (蚁后). Optional: set `ANTS_ADMIN_TOKEN` in `.env` for `/internal/configs` and `POST /internal/spawn`.

## Run 蚁后 (single container)

```bash
docker run -p 22000:22000 \
  -e ANTS_HOST_PROJECT_ROOT="$(pwd)" \
  -e ANTS_IMAGE=ants:latest \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)":/app/host \
  ants
```

Base image: `python:3.14-slim`. If unavailable, set Dockerfile `ARG PYTHON_VERSION=3.13-slim`.
