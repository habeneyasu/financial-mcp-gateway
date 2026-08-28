# syntax=docker/dockerfile:1
# Supports both local Docker Compose and Hugging Face Spaces (Docker SDK).
# HF Spaces: runs as user 1000, serves on port 7860 via space_app.py.
# Local:     runs as root, serves MCP on 8000 / chat on 8001 via server.py.

FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_HTTP_TIMEOUT=120 \
    PATH="/app/.venv/bin:$PATH"

# HF Spaces requires a non-root user with uid 1000
RUN useradd -m -u 1000 user

WORKDIR /app

# Install dependencies first (cache layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev --no-editable

# Copy application code
COPY --chown=1000:1000 pyproject.toml uv.lock README.md \
     server.py space_app.py chat_app.py client.py config.py db.py main.py ./
COPY --chown=1000:1000 src ./src

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable \
    && rm /bin/uv

RUN mkdir -p /app/data && chown -R 1000:1000 /app/data

USER 1000

# HF Spaces serves on 7860; local compose overrides CMD per service
EXPOSE 7860 8000 8001
CMD ["python", "space_app.py"]
