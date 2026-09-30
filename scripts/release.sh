#!/usr/bin/env bash
# =============================================================================
# release.sh — Publica un release semántico de Financial-DataBase.
#
#   ./scripts/release.sh patch "Fix companyfacts pagination"
#   ./scripts/release.sh minor "Add a new price provider"
#   ./scripts/release.sh major "Breaking schema migration"
#
# Opciones:
#   --dry-run   Hace todo (versión, changelog) pero NO commitea, etiqueta,
#               empuja ni crea el release de GitHub. Deja los cambios en el
#               árbol para revisarlos (git reset --hard HEAD para descartar).
#
# Precondiciones (si alguna falla, sale con error y no toca nada):
#   1. Árbol de trabajo limpio.
#   2. Rama main sincronizada con origin/main (hace git fetch antes).
#   3. Los tests unitarios pasan (python -m pytest tests/unit -q); la suite
#      de integración necesita PostgreSQL y queda fuera del gate.
#   4. La deuda de ruff no crece respecto a config/lint_baseline.
#
# Specifics de este repo:
#   - La versión vive en dos sitios y debe coincidir: __version__ en
#     src/financial_database/__init__.py y version en pyproject.toml.
#   - Si hay migraciones nuevas desde el último tag y el bump es patch, avisa
#     (una migración que rompe compatibilidad exige major/minor).
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION_FILE="src/financial_database/__init__.py"
PYPROJECT="pyproject.toml"
CHANGELOG="CHANGELOG.md"
BASELINE="config/lint_baseline"
DRY_RUN=0

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  ⚠\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

# --- Argumentos --------------------------------------------------------------
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) ARGS+=("$arg") ;;
  esac
done
BUMP="${ARGS[0]:-}"
MESSAGE="${ARGS[1]:-}"

case "$BUMP" in
  patch|minor|major) ;;
  *)
    echo "Uso: ./scripts/release.sh <patch|minor|major> \"<mensaje>\" [--dry-run]" >&2
    exit 2
    ;;
esac
[ -n "$MESSAGE" ] || { echo "Falta el mensaje del release." >&2; exit 2; }

# --- Herramientas ------------------------------------------------------------
if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
  PYTHON_BIN="venv/bin/python"
else
  PYTHON_BIN="python3"
fi
if [ -x ".venv/bin/ruff" ]; then
  RUFF_BIN=".venv/bin/ruff"
elif command -v ruff >/dev/null 2>&1; then
  RUFF_BIN="ruff"
else
  fail "ruff no está instalado (ni .venv/bin/ruff ni en el PATH)."
fi

# --- 1. Árbol limpio ---------------------------------------------------------
info "1/9  Árbol de trabajo limpio"
if [ -n "$(git status --porcelain)" ]; then
  git status --short
  fail "Hay cambios sin commitear: haz commit (o stash) antes de publicar."
fi
ok "sin cambios pendientes"

# --- 2. Rama y sincronización ------------------------------------------------
info "2/9  Rama main sincronizada con origin/main"
RAMA="$(git rev-parse --abbrev-ref HEAD)"
[ "$RAMA" = "main" ] || fail "No estás en main (estás en '$RAMA')."
git fetch --quiet origin main
LOCAL="$(git rev-parse HEAD)"
REMOTO="$(git rev-parse origin/main)"
[ "$LOCAL" = "$REMOTO" ] || fail "main no está sincronizada con origin/main (local ${LOCAL:0:7}, remoto ${REMOTO:0:7})."
ok "main == origin/main (${LOCAL:0:7})"

# --- 3. Tests ----------------------------------------------------------------
info "3/9  Tests unitarios (${PYTHON_BIN} -m pytest tests/unit -q)"
"$PYTHON_BIN" -m pytest tests/unit -q || fail "Los tests no pasan: no se etiqueta un release con tests rotos."
ok "tests OK (la suite de integración necesita PostgreSQL y queda fuera)"

# --- 4. Ruff: la deuda no crece (ratchet) ------------------------------------
info "4/9  Ruff: la deuda no debe crecer (baseline ${BASELINE})"
# ruff check/format salen con código 1 cuando hay deuda: captura la salida
# sin que pipefail aborte el script (el gate compara contra el baseline).
CHECK_JSON="$("$RUFF_BIN" check . --output-format json || true)"
CHECK_ERRORS="$(printf '%s' "$CHECK_JSON" | "$PYTHON_BIN" -c 'import json,sys; print(len(json.load(sys.stdin)))')"
FORMAT_FILES="$("$RUFF_BIN" format --check . 2>&1 | tail -1 | grep -oE '^[0-9]+ files? would be reformatted' | grep -oE '^[0-9]+' || true)"
FORMAT_FILES="${FORMAT_FILES:-0}"
BASELINE_CHECK="$(sed -n 's/^check_errors=\([0-9]\+\)$/\1/p' "$BASELINE" | head -1)"
BASELINE_FORMAT="$(sed -n 's/^format_files=\([0-9]\+\)$/\1/p' "$BASELINE" | head -1)"
if [ -z "$BASELINE_CHECK" ] || [ -z "$BASELINE_FORMAT" ]; then
  fail "No se pudo leer $BASELINE (check_errors= / format_files=)."
fi
ok "ruff check: ${CHECK_ERRORS} errores (baseline ${BASELINE_CHECK})"
ok "ruff format: ${FORMAT_FILES} archivos sin formatear (baseline ${BASELINE_FORMAT})"
[ "$CHECK_ERRORS" -le "$BASELINE_CHECK" ] || fail "ruff check ha crecido (${CHECK_ERRORS} > ${BASELINE_CHECK}): arregla los errores nuevos."
[ "$FORMAT_FILES" -le "$BASELINE_FORMAT" ] || fail "ruff format ha crecido (${FORMAT_FILES} > ${BASELINE_FORMAT}): formatea los archivos nuevos."
if [ "$CHECK_ERRORS" -lt "$BASELINE_CHECK" ] || [ "$FORMAT_FILES" -lt "$BASELINE_FORMAT" ]; then
  warn "la deuda ha bajado: actualiza ${BASELINE} a check_errors=${CHECK_ERRORS} y format_files=${FORMAT_FILES}"
fi

# --- 5. Versión nueva --------------------------------------------------------
info "5/9  Calculando la versión nueva"
CURRENT="$(sed -n 's/^__version__ = "\([0-9]\+\.[0-9]\+\.[0-9]\+\)"/\1/p' "$VERSION_FILE" | head -1)"
[ -n "$CURRENT" ] || fail "No se pudo leer __version__ de $VERSION_FILE."
PYPROJECT_VERSION="$(sed -n 's/^version = "\([0-9]\+\.[0-9]\+\.[0-9]\+\)"/\1/p' "$PYPROJECT" | head -1)"
[ "$CURRENT" = "$PYPROJECT_VERSION" ] || fail "Versión desincronizada: ${VERSION_FILE}=${CURRENT} y ${PYPROJECT}=${PYPROJECT_VERSION}."
IFS=. read -r MAJOR MINOR PATCH <<< "$CURRENT"
case "$BUMP" in
  patch) PATCH=$((PATCH + 1)) ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
esac
NEW="${MAJOR}.${MINOR}.${PATCH}"
git rev-parse -q --verify "refs/tags/v${NEW}" >/dev/null && fail "El tag v${NEW} ya existe."
ok "${CURRENT} -> ${NEW} (${BUMP})"

case "$BUMP" in
  patch) SECTION="Fixed" ;;
  minor) SECTION="Added" ;;
  major) SECTION="Changed" ;;
esac

# --- 5b. Migraciones (specific de este repo) ---------------------------------
LAST_TAG="$(git describe --tags --abbrev=0 2>/dev/null || true)"
if [ -n "$LAST_TAG" ]; then
  MIGRACIONES="$(git diff --name-only "${LAST_TAG}..HEAD" -- 'src/financial_database/db/migrations' | wc -l | tr -d ' ')"
  if [ "$MIGRACIONES" -gt 0 ]; then
    warn "${MIGRACIONES} archivo(s) de migración nuevos desde ${LAST_TAG}"
    if [ "$BUMP" = "patch" ]; then
      warn "bump patch con migraciones nuevas: valora minor/major si rompen compatibilidad"
    fi
  else
    ok "sin migraciones nuevas desde ${LAST_TAG}"
  fi
else
  ok "sin tags previos: la comprobación de migraciones se activa en el próximo release"
fi

# --- 6. Versión en los ficheros ----------------------------------------------
info "6/9  Actualizando la versión"
sed -i "s/^__version__ = \"${CURRENT}\"/__version__ = \"${NEW}\"/" "$VERSION_FILE"
sed -i "s/^version = \"${CURRENT}\"/version = \"${NEW}\"/" "$PYPROJECT"
ok "${VERSION_FILE} y ${PYPROJECT} -> ${NEW}"

for README in README.md README.es.md; do
  if [ -f "$README" ] && grep -q "badge/version-" "$README"; then
    sed -i "s|badge/version-[0-9]\+\.[0-9]\+\.[0-9]\+-|badge/version-${NEW}-|" "$README"
    ok "${README}: badge -> ${NEW}"
  fi
done

# --- 7. CHANGELOG ------------------------------------------------------------
info "7/9  Añadiendo la entrada al CHANGELOG"
"$PYTHON_BIN" - "$CHANGELOG" "$NEW" "$SECTION" "$MESSAGE" <<'PY'
import sys
from datetime import date
from pathlib import Path

changelog, version, section, message = sys.argv[1:5]
text = Path(changelog).read_text(encoding="utf-8")
entry = f"## [{version}] - {date.today():%Y-%m-%d}\n\n### {section}\n\n- {message}\n\n"
idx = text.find("## [")
text = text[:idx] + entry + text[idx:] if idx != -1 else text.rstrip() + "\n\n" + entry
Path(changelog).write_text(text, encoding="utf-8")
print(f"  ✓ CHANGELOG.md: {version} ({section})")
PY

if [ "$DRY_RUN" = "1" ]; then
  info "DRY-RUN: cambios preparados (sin commit, tag ni push)"
  git --no-pager diff --stat
  echo
  echo "Revisa los cambios y descártalos con: git reset --hard HEAD"
  exit 0
fi

# --- 8. Commit y tag ---------------------------------------------------------
info "8/9  Commit y tag anotado"
git add "$VERSION_FILE" "$PYPROJECT" "$CHANGELOG"
for README in README.md README.es.md; do
  [ -f "$README" ] && git add "$README"
done
git commit -m "chore(release): bump version to ${NEW}"
git tag -a "v${NEW}" -m "$MESSAGE"
ok "commit $(git rev-parse --short HEAD) y tag v${NEW}"

# --- 9. Push y GitHub release ------------------------------------------------
info "9/9  Push y release en GitHub"
git push origin main
git push origin "v${NEW}"
ok "main y v${NEW} empujados"

if command -v gh >/dev/null 2>&1; then
  gh release create "v${NEW}" \
    --title "v${NEW} — ${MESSAGE}" \
    --notes-file "$CHANGELOG" \
    --latest
  ok "release v${NEW} creado en GitHub"
else
  echo "  AVISO: gh no está instalado; crea el release manualmente en GitHub."
fi

echo
echo "✅ Release v${NEW} publicado (${SECTION}: ${MESSAGE})"
