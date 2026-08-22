FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /usr/local/bin/uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --locked

# Copy source code
COPY src/financial_database ./src/financial_database
COPY scripts/ ./scripts/
COPY docker/ ./docker/

# Create non-root user
RUN useradd -m appuser
USER appuser

CMD ["uv", "run", "pytest"]