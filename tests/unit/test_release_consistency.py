"""Consistencia del release: versión ↔ CHANGELOG ↔ pyproject.

Si ``scripts/release.sh`` deja el repositorio descuadrado (versión sin
entrada en el CHANGELOG, fechas no ISO, versiones desordenadas o
``pyproject.toml`` sin actualizar), esta suite falla.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from financial_database import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"

SEMVER = r"\d+\.\d+\.\d+"
RELEASE_LINE = re.compile(
    rf"^## \[({SEMVER})\] - (\d{{4}}-\d{{2}}-\d{{2}})\s*$", re.MULTILINE
)
HEADER_LINE = re.compile(r"^## \[(.+?)\](?: - (.+?))?\s*$", re.MULTILINE)
SECTION_LINE = re.compile(r"^### (.+?)\s*$")


def changelog_text() -> str:
    return CHANGELOG.read_text(encoding="utf-8")


def version_key(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def test_version_matches_top_changelog_entry():
    releases = RELEASE_LINE.findall(changelog_text())
    assert releases, "CHANGELOG.md sin entradas '## [x.y.z] - YYYY-MM-DD'"
    assert releases[0][0] == __version__, (
        f"financial_database.__version__ ({__version__}) no coincide con la "
        f"primera entrada del CHANGELOG ({releases[0][0]})"
    )


def test_changelog_is_keep_a_changelog():
    headers = HEADER_LINE.findall(changelog_text())
    assert headers, "CHANGELOG.md sin encabezados '## [...]'"

    versions: list[str] = []
    for version, fecha in headers:
        if version.lower() == "unreleased":
            assert not fecha, "la sección 'Unreleased' no lleva fecha"
            continue
        assert re.fullmatch(SEMVER, version), f"versión no semántica: {version!r}"
        assert fecha and re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha), (
            f"la entrada {version} no tiene fecha ISO (YYYY-MM-DD): {fecha!r}"
        )
        versions.append(version)

    assert versions == sorted(versions, key=version_key, reverse=True), (
        "las versiones del CHANGELOG no están en orden descendente"
    )
    assert len(versions) == len(set(versions)), (
        "hay versiones duplicadas en el CHANGELOG"
    )


def test_every_release_has_a_section():
    """Cada versión publicada debe tener al menos una sección (### Added/...)."""
    releases_sin_seccion: list[str] = []
    version_actual = ""
    en_release = False
    tiene_seccion = False

    for linea in changelog_text().splitlines():
        encabezado = re.match(r"^## \[(.+?)\]", linea)
        if encabezado:
            if en_release and not tiene_seccion:
                releases_sin_seccion.append(version_actual)
            version_actual = encabezado.group(1)
            en_release = version_actual.lower() != "unreleased"
            tiene_seccion = False
            continue
        if en_release and SECTION_LINE.match(linea):
            tiene_seccion = True

    if en_release and not tiene_seccion:
        releases_sin_seccion.append(version_actual)

    assert not releases_sin_seccion, (
        f"estas versiones del CHANGELOG no tienen ninguna sección (### ...): "
        f"{releases_sin_seccion}"
    )


def test_pyproject_version_matches_package():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    declarada = data["project"]["version"]
    assert declarada == __version__, (
        f"pyproject.toml ({declarada}) y financial_database.__version__ "
        f"({__version__}) no coinciden"
    )
