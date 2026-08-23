#!/usr/bin/env bash
# Database migration runner

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Load environment variables from .env if it exists
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default DATABASE_URL if not set
DATABASE_URL="${DATABASE_URL:-postgresql://financial:test@localhost:5432/financial_database}"

echo "Running database migrations..."
echo "DATABASE_URL: $DATABASE_URL"

# Run migrations using uv
uv run python -m financial_database.db.migrations.runner