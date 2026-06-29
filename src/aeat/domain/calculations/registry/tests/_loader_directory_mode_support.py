"""Shared support for directory-mode loader tests."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from .....core.resources import bundled_path
from .. import CasillaId, ModeloDefinition, ModeloSource, validated_casilla_id
from .._loader import (
    discover_modelo_sources,
    load_modelo_source,
    load_registry_tree,
)

_REVISION_HEADER_RE = re.compile(r'^\[\[?revisions\.(?:"([^"]+)"|([A-Za-z0-9_-]+))(?=[.\]])')
_MAX_SINGLE_FILE_MODELO_LINES = 2_000
_MAX_TOML_FRAGMENT_LINES = 1_750
_MAX_TOML_ROW_CHARS = 600
_TOML_CASILLA_ID_KEY = "casilla_id"
_COMPLETENESS_CASILLA_0001: CasillaId = validated_casilla_id(
    "0001",
    surface="_COMPLETENESS_CASILLA_0001",
)
_COMPLETENESS_CASILLA_0002: CasillaId = validated_casilla_id(
    "0002",
    surface="_COMPLETENESS_CASILLA_0002",
)
_MINIMAL_MANIFEST_TEXT = '[modelo]\nid = "999"\ntitle = "x"\n'
_MINIMAL_REVISION_TEXT = '[revisions."2025"]\nvalid_from = 2025-01-01\n'


@cache
def _committed_registry_root() -> Path:
    return bundled_path("registry", "aeat")


@cache
def _committed_modelos_dir() -> Path:
    return _committed_registry_root() / "modelos"


@cache
def _committed_modelo_sources() -> tuple[ModeloSource, ...]:
    return discover_modelo_sources(_committed_modelos_dir())


@cache
def _committed_modelo_sources_by_id() -> dict[str, ModeloSource]:
    return {source.modelo_id: source for source in _committed_modelo_sources()}


@cache
def _committed_modelo(modelo_id: str) -> ModeloDefinition:
    return load_modelo_source(_committed_modelo_sources_by_id()[modelo_id])


@cache
def _committed_registry_modelos() -> tuple[ModeloDefinition, ...]:
    modelos, _catalogues = load_registry_tree(_committed_registry_root())
    return modelos


@cache
def _committed_modelo_toml_paths() -> tuple[Path, ...]:
    return tuple(sorted(_committed_modelos_dir().rglob("*.toml")))


@cache
def _committed_non_locale_modelo_toml_paths() -> tuple[Path, ...]:
    return tuple(path for path in _committed_modelo_toml_paths() if not any(part == "locales" for part in path.parts))


@cache
def _committed_non_locale_toml_paths_by_modelo_id() -> dict[str, tuple[Path, ...]]:
    paths_by_modelo_id: dict[str, list[Path]] = {}
    modelos_dir = _committed_modelos_dir()
    for path in _committed_non_locale_modelo_toml_paths():
        relative = path.relative_to(modelos_dir)
        if len(relative.parts) < 3 or relative.parts[1] != "revisions":
            continue
        paths_by_modelo_id.setdefault(relative.parts[0], []).append(path)
    return {modelo_id: tuple(sorted(paths)) for modelo_id, paths in paths_by_modelo_id.items()}


@cache
def _committed_non_locale_toml_paths_by_fragment_revision() -> dict[tuple[str, str], tuple[Path, ...]]:
    paths_by_revision: dict[tuple[str, str], list[Path]] = {}
    modelos_dir = _committed_modelos_dir()
    for path in _committed_non_locale_modelo_toml_paths():
        relative = path.relative_to(modelos_dir)
        if len(relative.parts) < 4 or relative.parts[1] != "revisions" or relative.parts[2].endswith(".toml"):
            continue
        paths_by_revision.setdefault((relative.parts[0], relative.parts[2]), []).append(path)
    return {revision_key: tuple(sorted(paths)) for revision_key, paths in paths_by_revision.items()}


def _standard_manifest_text(title: str) -> str:
    return f"""
[modelo]
id = "999"
title = "{title}"
official_name = "{title}"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip()


def _standard_revision_preamble_text() -> str:
    return """
[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip()


def _write_standard_manifest(target_dir: Path, title: str) -> None:
    (target_dir / "manifest.toml").write_text(_standard_manifest_text(title), encoding="utf-8")


def _write_standard_revision_preamble(path: Path) -> None:
    path.write_text(_standard_revision_preamble_text(), encoding="utf-8")


def _build_directory_layout(
    target_dir: Path,
    *,
    manifest_text: str,
    revision_files: dict[str, str],
) -> None:
    """Materialise a directory-mode modelo at ``target_dir``."""

    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "manifest.toml").write_text(manifest_text, encoding="utf-8")
    revisions_dir = target_dir / "revisions"
    revisions_dir.mkdir(exist_ok=True)
    for filename, content in revision_files.items():
        (revisions_dir / filename).write_text(content, encoding="utf-8")


def _minimal_fragment_revision_layout(
    target_dir: Path,
    *,
    revision_text: str = _MINIMAL_REVISION_TEXT,
    fragment_dirs: tuple[str, ...] = (),
) -> Path:
    """Materialise a minimal ``revisions/2025/`` tree and return that revision dir."""

    revision_dir = target_dir / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    (target_dir / "manifest.toml").write_text(_MINIMAL_MANIFEST_TEXT, encoding="utf-8")
    (revision_dir / "revision.toml").write_text(revision_text, encoding="utf-8")
    for relative_dir in fragment_dirs:
        (revision_dir / relative_dir).mkdir(parents=True)
    return revision_dir


def _write_locale_fragment(locales_dir: Path, language: str, filename: str, text: str) -> None:
    language_dir = locales_dir / language
    language_dir.mkdir(parents=True, exist_ok=True)
    (language_dir / filename).write_text(text, encoding="utf-8")


def _write_minimal_localized_modelo(target_dir: Path, casilla_ids: tuple[str, ...]) -> Path:
    revision_dir = target_dir / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    (target_dir / "manifest.toml").write_text(
        """
[modelo]
id = "999"
title = "Localized loader test"
official_name = "Localized loader test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    casilla_tables = "\n".join(
        f"""
[[revisions."2025".casillas]]
id = "{casilla_id}"
number = "{index}"
label = "Casilla {index}"
section = ["liquidacion"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip()
        for index, casilla_id in enumerate(casilla_ids, start=1)
    )
    (revision_dir / "revision.toml").write_text(
        f"""
[revisions."2025"]
valid_from = 2025-01-01
period_selector = {{ years = [2025], periods = ["0A"] }}
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

{casilla_tables}
""".lstrip(),
        encoding="utf-8",
    )
    return revision_dir


def _split_single_file_modelo_text(text: str) -> tuple[str, str, dict[str, str]]:
    """Split one modelo TOML into manifest text and revision table text."""

    manifest_lines: list[str] = []
    revision_lines: list[str] = []
    revision_lines_by_id: dict[str, list[str]] = {}
    current_revision_id: str | None = None
    in_revision = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        match = _REVISION_HEADER_RE.match(stripped)
        if stripped.startswith("[revisions") or stripped.startswith("[[revisions"):
            in_revision = True
            if match is None:
                raise AssertionError(f"cannot determine revision id from TOML header {stripped!r}")
            current_revision_id = match.group(1) or match.group(2)
            assert current_revision_id is not None
            revision_lines_by_id.setdefault(current_revision_id, [])
        if in_revision:
            revision_lines.append(line)
            if current_revision_id is None:
                raise AssertionError(f"revision line appeared before a revision header: {line!r}")
            revision_lines_by_id[current_revision_id].append(line)
        else:
            manifest_lines.append(line)

    return (
        "".join(manifest_lines),
        "".join(revision_lines),
        {revision_id: "".join(lines) for revision_id, lines in revision_lines_by_id.items()},
    )
