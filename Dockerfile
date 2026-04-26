# Prowpt MCP server (Streamable HTTP transport).
#
# The same package still ships to PyPI with the stdio transport for local
# IDE installs; this image runs the remote HTTP transport used by Claude.ai
# and ChatGPT connectors.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip \
 && pip install ".[http]"

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/healthz').read()" || exit 1

ENV PROWPT_API_URL=http://backend:8000 \
    PROWPT_MCP_BIND=0.0.0.0:8001

CMD ["sh", "-c", "prowpt-mcp --transport http --bind ${PROWPT_MCP_BIND} --api-url ${PROWPT_API_URL}"]
