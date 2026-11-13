# Image for the public demo (Fly.io, see fly.toml). Runs from source: no wheel is built.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Dependencies first, so a code change does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY knowledge ./knowledge
COPY src ./src
COPY docker-entrypoint.sh ./

EXPOSE 7860
# Migrations run here, not as a Fly release_command: release machines do not have the volume.
ENTRYPOINT ["./docker-entrypoint.sh"]
