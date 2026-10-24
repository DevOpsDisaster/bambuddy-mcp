# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.5 AS uv

FROM python:3.12-slim-bookworm AS builder
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable --python /usr/local/bin/python

FROM python:3.12-slim-bookworm
LABEL org.opencontainers.image.title="Bambuddy MCP" \
      org.opencontainers.image.source="https://github.com/DevOpsDisaster/bambuddy-mcp" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"
RUN groupadd --gid 10001 bambuddy && useradd --uid 10001 --gid 10001 --no-create-home bambuddy
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY LICENSE ./LICENSE
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BAMBUDDY_MCP_TRANSPORT=streamable-http \
    BAMBUDDY_MCP_HOST=0.0.0.0 \
    BAMBUDDY_MCP_PORT=8000
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['BAMBUDDY_MCP_PORT'] + '/healthz', timeout=3).close()"]
ENTRYPOINT ["bambuddy-mcp"]
