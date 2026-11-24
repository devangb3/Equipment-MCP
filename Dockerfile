FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
COPY src/ src/
RUN uv sync --locked --no-editable
COPY tests/ tests/

ENV PATH="/app/.venv/bin:$PATH"
USER 65534:65534
CMD ["python", "-m", "pytest", "-p", "no:cacheprovider"]
