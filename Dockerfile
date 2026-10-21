FROM python:3.14.3-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=0 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY panopticon/ ./panopticon/

RUN uv sync --locked --no-dev --no-editable

RUN groupadd --gid 10001 panopticon \
    && useradd --uid 10001 --gid panopticon --no-create-home panopticon \
    && mkdir -p /app/keys /app/logs /app/data \
    && chown panopticon:panopticon /app/keys /app/logs /app/data

USER panopticon

FROM runtime AS api

EXPOSE 8000

CMD ["python", "-m", "panopticon.api.server"]

FROM runtime AS ssh

EXPOSE 2222

CMD ["python", "-m", "panopticon.honeypots.ssh.server"]
