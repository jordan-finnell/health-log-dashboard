# Production image for the dashboard. Contains code and the committed example/demo configs only:
# the service-account key, sheet id and app password are bind-mounted at run time (compose.yaml).
FROM python:3.13-slim

# uv for a locked, reproducible install. Keep the version inside the pyproject build-system range.
COPY --from=ghcr.io/astral-sh/uv:0.8.19 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# uid/gid 1000 matches the WSL user, so the container can read the chmod 600 secrets file
# bind-mounted from the WSL filesystem.
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid 1000 --create-home app

WORKDIR /app

# Dependencies first, so code changes don't reinstall them. The project itself isn't installed:
# it runs from /app/src via PYTHONPATH.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY app ./app
COPY config ./config
COPY .streamlit ./.streamlit

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src

USER app
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4)"

CMD ["streamlit", "run", "app/Home.py", "--server.address=0.0.0.0", "--server.port=8501"]
