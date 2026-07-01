# Backend API image (FastAPI + uvicorn). Dev-oriented: source is bind-mounted at
# runtime for --reload; only dependencies are baked into the image.
FROM python:3.12-slim

# uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Keep the virtualenv OUTSIDE /app so bind-mounting the source at runtime does not
# shadow it with the host's macOS-built .venv (that venv is Linux-incompatible).
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install deps first (own layer) for build caching — only re-runs when lockfile changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# App code. Overlaid by the bind mount at runtime, but present for a standalone image.
COPY . .
RUN uv sync --frozen

EXPOSE 8000
# uvicorn resolves from /opt/venv (on PATH); 0.0.0.0 so the published port is reachable.
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
