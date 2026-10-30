FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1

# Application dependencies first (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# Prebuild the two environments the demo project is tested against, so a run never installs packages
RUN ./scripts/build_envs.sh
# The sandbox uid below must be able to read and run them
RUN chmod -R a+rX /app/demo

# Model-run code (pytest, diagnostic snippets) drops to this unprivileged uid, so it cannot read the server's secrets
ENV UP_SANDBOX_UID=65534

# Secrets are provided at runtime: NEBIUS_API_KEY, TAVILY_API_KEY, UP_ACCESS_CODE (enables live runs)
EXPOSE 8000
CMD ["sh", "-c", "uv run --frozen --no-dev uvicorn upgradepilot.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
