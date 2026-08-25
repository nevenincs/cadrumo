"""Shared support for directory-mode loader tests."""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

from .....core import scan_directory
from .....core.resources import bundled_path
from .. import ModeloDefinition, ModeloSource
from .._loader import (
    _REVISION_SECTION_FIELDS,
    discover_modelo_sources,
    load_modelo_directory,
    load_modelo_source,
    load_registry_tree,
)
from .._schema import ModeloRevision

_REVISION_HEADER_RE = re.compile(r'^\[\[?revisions\.(?:"([^"]+)"|([A-Za-z0-9_-]+))(?=[.\]])')
_REVISION_FIELD_RE = re.compile(r'^\[\[?revisions\.(?:"[^"]+"|[A-Za-z0-9_-]+)\.([A-Za-z0-9_]+)')
_MAX_SINGLE_FILE_MODELO_LINES = 2_000
_MAX_TOML_FRAGMENT_LINES = 1_750
_MAX_TOML_ROW_CHARS = 600
_TOML_CASILLA_ID_KEY = "casilla_id"
_COMPLETENESS_CASILLA_0001 = "0001"
_COMPLETENESS_CASILLA_0002 = "0002"
_MINIMAL_MANIFEST_TEXT = '[modelo]\nid = "999"\n'
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
    return scan_directory(_committed_modelos_dir(), pattern="*.toml", recursive=True)


@cache
def _committed_toml_paths_by_modelo_id() -> dict[str, tuple[Path, ...]]:
    paths_by_modelo_id: dict[str, list[Path]] = {}
    modelos_dir = _committed_modelos_dir()
    for path in _committed_modelo_toml_paths():
        relative = path.relative_to(modelos_dir)
        if len(relative.parts) < 3 or relative.parts[1] != "revisions":
            continue
        paths_by_modelo_id.setdefault(relative.parts[0], []).append(path)
    return {modelo_id: tuple(sorted(paths)) for modelo_id, paths in paths_by_modelo_id.items()}


@cache
def _committed_toml_paths_by_fragment_revision() -> dict[tuple[str, str], tuple[Path, ...]]:
    paths_by_revision: dict[tuple[str, str], list[Path]] = {}
    modelos_dir = _committed_modelos_dir()
    for path in _committed_modelo_toml_paths():
        relative = path.relative_to(modelos_dir)
        if len(relative.parts) < 4 or relative.parts[1] != "revisions" or relative.parts[2].endswith(".toml"):
            continue
        paths_by_revision.setdefault((relative.parts[0], relative.parts[2]), []).append(path)
    return {revision_key: tuple(sorted(paths)) for revision_key, paths in paths_by_revision.items()}


def _standard_manifest_text(_description: str) -> str:
    return """
[modelo]
id = "999"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip()


def _standard_revision_preamble_text(source_ref: str = "aeat-manual", *, declare_legal_refs: bool = True) -> str:
    """Build the standard ``[revisions."2025"]`` scalar preamble.

    ``declare_legal_refs=False`` omits the ``legal_refs`` line entirely
    (rather than declaring an empty one) so a caller can prove a
    redeclaration guard fires only when the manifest already carries the
    field — a manifest silent on ``legal_refs`` is a different shape than
    one that names it.
    """
    legal_refs_line = 'legal_refs = ["ley-58-2003:art-29"]\n' if declare_legal_refs else ""
    return (
        '[revisions."2025"]\n'
        "valid_from = 2025-01-01\n"
        'period_selector = { years = [2025], periods = ["0A"] }\n'
        f"{legal_refs_line}"
        f'source_refs = ["{source_ref}"]\n'
    )


def _write_standard_manifest(target_dir: Path, title: str) -> None:
    (target_dir / "manifest.toml").write_text(_standard_manifest_text(title), encoding="utf-8", newline="\n")


def _write_standard_revision_preamble(path: Path) -> None:
    path.write_text(_standard_revision_preamble_text(), encoding="utf-8", newline="\n")


def _write_modelo(
    root: Path,
    *,
    casilla_fragment: str,
    revision_id: str = "2025",
    manifest_extra: str = "",
    manifest_text: str | None = None,
    fragment_extra: str = "",
    declare_legal_refs: bool = True,
) -> Path:
    """Materialise a minimal fragmented modelo (``root/999``) and return its directory.

    ``manifest_extra`` is appended to the standard ``revision.toml`` scalar
    preamble; ``fragment_extra`` is appended to the one casilla-section
    fragment. Pass ``manifest_text`` to replace the whole ``revision.toml``
    body outright instead of appending to the standard preamble (for tests
    proving where a value lives, not just what it says).
    """
    modelo_dir = root / "999"
    revision_dir = modelo_dir / "revisions" / revision_id
    (revision_dir / "casillas").mkdir(parents=True)
    _write_standard_manifest(modelo_dir, "Test")
    (revision_dir / "revision.toml").write_text(
        (
            _standard_revision_preamble_text(declare_legal_refs=declare_legal_refs) + manifest_extra
            if manifest_text is None
            else manifest_text
        ),
        encoding="utf-8", newline="\n")
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(
        casilla_fragment + fragment_extra,
        encoding="utf-8", newline="\n")
    return modelo_dir


def _load_revision(modelo_dir: Path, *, revision_id: str = "2025") -> ModeloRevision:
    return load_modelo_directory(modelo_dir).revisions[revision_id]


def _build_directory_layout(
    target_dir: Path,
    *,
    manifest_text: str,
    revision_files: dict[str, str],
) -> None:
    """Materialise a directory-mode modelo at ``target_dir``."""

    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "manifest.toml").write_text(manifest_text, encoding="utf-8", newline="\n")
    revisions_dir = target_dir / "revisions"
    revisions_dir.mkdir(exist_ok=True)
    for filename, content in revision_files.items():
        (revisions_dir / filename).write_text(content, encoding="utf-8", newline="\n")


def write_extracted_corpus_sidecar(corpus_path: Path, *, anchor: str, text: str) -> None:
    """Materialise the ``.extracted.json`` sidecar a legal reference resolves against.

    Legal verification does not read the raw corpus HTML: it resolves ONE
    anchored unit out of the sidecar and matches ``required_text`` against that
    unit alone, so a fixture that writes only the ``.html`` is refused with
    ``missing extracted corpus sidecar``. Any test whose registry tree declares
    a legal reference with ``required_text`` therefore has to write this
    alongside the corpus file.

    Args:
        corpus_path: The corpus file the legal reference's ``corpus_ref``
            points at; the sidecar is written beside it.
        anchor: The anchor segment of the ``corpus_ref`` (the part after ``#``).
        text: Provision text for that unit; must contain the reference's
            ``required_text`` for verification to pass.
    """
    corpus_path.with_name(corpus_path.name + ".extracted.json").write_text(
        json.dumps({"units": [{"anchor": anchor, "text": text}]}),
        encoding="utf-8",
        newline="\n",
    )


def write_fragmented_revision(revision_dir: Path, revision_text: str) -> None:
    """Materialise a full revision TOML as the fragmented layout.

    Splits ``revision_text`` (a whole ``[revisions."<id>"]`` table with inline
    section arrays) into a scalar-only ``revision.toml`` manifest plus one
    ``<section>/0001-<section>.toml`` fragment per section, matching the
    fragmented-layout invariant the loader now enforces. Comments directly above
    a section header travel with that section.
    """
    lines = revision_text.splitlines(keepends=True)
    header_indexes = [index for index, line in enumerate(lines) if _REVISION_HEADER_RE.match(line)]
    starts = _revision_block_starts(lines, header_indexes)
    scalar_blocks, section_blocks = _partition_revision_blocks(lines, header_indexes, starts)
    _write_fragmented_revision_blocks(revision_dir, scalar_blocks, section_blocks)


def _revision_block_starts(lines: list[str], header_indexes: list[int]) -> list[int]:
    starts: list[int] = []
    for position, header_index in enumerate(header_indexes):
        start = header_index
        lower = header_indexes[position - 1] + 1 if position > 0 else 0
        while start - 1 >= lower and lines[start - 1].lstrip().startswith("#"):
            start -= 1
        starts.append(start)
    return starts


def _partition_revision_blocks(
    lines: list[str],
    header_indexes: list[int],
    starts: list[int],
) -> tuple[list[str], dict[str, list[str]]]:
    scalar_blocks: list[str] = []
    section_blocks: dict[str, list[str]] = {}
    for position, header_index in enumerate(header_indexes):
        start = starts[position]
        end = starts[position + 1] if position + 1 < len(header_indexes) else len(lines)
        block = "".join(lines[start:end])
        field_match = _REVISION_FIELD_RE.match(lines[header_index])
        field = field_match.group(1) if field_match else None
        if field is not None and field in _REVISION_SECTION_FIELDS:
            section_blocks.setdefault(field, []).append(block)
        else:
            scalar_blocks.append(block)
    return scalar_blocks, section_blocks


def _write_fragmented_revision_blocks(
    revision_dir: Path,
    scalar_blocks: list[str],
    section_blocks: dict[str, list[str]],
) -> None:
    revision_dir.mkdir(parents=True, exist_ok=True)
    (revision_dir / "revision.toml").write_text(
        "".join(scalar_blocks).rstrip("\n") + "\n", encoding="utf-8", newline="\n"
    )
    for field, blocks in section_blocks.items():
        section_dir = revision_dir / field
        section_dir.mkdir(parents=True, exist_ok=True)
        fragment_slug = field.replace("_", "-")
        (section_dir / f"0001-{fragment_slug}.toml").write_text(
            "".join(blocks).strip("\n") + "\n", encoding="utf-8", newline="\n"
        )


def _minimal_fragment_revision_layout(
    target_dir: Path,
    *,
    revision_text: str = _MINIMAL_REVISION_TEXT,
    fragment_dirs: tuple[str, ...] = (),
) -> Path:
    """Materialise a minimal ``revisions/2025/`` tree and return that revision dir."""

    revision_dir = target_dir / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    (target_dir / "manifest.toml").write_text(_MINIMAL_MANIFEST_TEXT, encoding="utf-8", newline="\n")
    (revision_dir / "revision.toml").write_text(revision_text, encoding="utf-8", newline="\n")
    for relative_dir in fragment_dirs:
        (revision_dir / relative_dir).mkdir(parents=True)
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
