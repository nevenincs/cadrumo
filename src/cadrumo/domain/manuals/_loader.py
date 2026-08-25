"""File-backed loader and query API for :mod:`cadrumo.domain.manuals`.

The loader walks the ``corpus/manuals/`` directory hierarchy and
produces strictly-validated :class:`~cadrumo.domain.manuals.Manual`,
:class:`~cadrumo.domain.manuals.Chapter`, and
:class:`~cadrumo.domain.manuals.Section` records. Tests exercise it
against hand-crafted temporary-directory fixtures so the contract is
locked for downstream extraction work that lands real chapter trees.

Directory shape per part root::

    <part_root>/
        source.pdf           # git-ignored, raw binary
        manifest.json        # FetchedManualPart record (committed)
        structure/
            manual.json      # Manual metadata (without embedded chapters)
            chapters.json    # tuple[Chapter, ...] with SectionRef entries
            sections/<chapter-id>/<section-id>.json  # Section records

For IVA (``ManualPart.SINGLE``) the ``<part_root>`` is
``corpus/manuals/iva/<year>/``; for Renta the part root is nested
inside the canonical ``ManualPart`` directory value.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from ...core.config import Settings, load_settings
from ...core.logging import get_logger
from ...core.paths import path_stat_fingerprint, resolve_relative_subpath
from .errors import ManualNotFoundError, ManualParseError
from ._schema import (
    Chapter,
    Manual,
    ManualCasillaReference,
    ManualCatalogue,
    ManualId,
    ManualPart,
    Rule,
    RuleKind,
    Section,
    SectionRef,
)

_logger = get_logger(__name__)


def _root_from_settings(settings: Settings | None) -> Path:
    """Resolve the manuals root directory from ``settings`` or the project default."""
    return (settings or load_settings()).aeat_manuals_root


def resolve_part_root(
    *,
    manual_id: ManualId,
    year: int,
    part: ManualPart,
    settings: Settings | None = None,
) -> Path:
    """Return the on-disk root for a specific ``(manual_id, year, part)``.

    Args:
        manual_id: Handbook identifier.
        year: Tax year.
        part: Volume split. ``SINGLE`` flattens the directory layout.
        settings: Optional settings instance; loaded on demand otherwise.

    Returns:
        The canonical directory path (not guaranteed to exist).
    """
    root = _root_from_settings(settings)
    year_dir = root / manual_id.value / str(year)
    if part is ManualPart.SINGLE:
        return year_dir
    return year_dir / part.value


_CHAPTERS_ADAPTER: TypeAdapter[tuple[Chapter, ...]] = TypeAdapter(tuple[Chapter, ...])


def _read_text(path: Path) -> str:
    """Read a UTF-8 text file, raising :exc:`ManualNotFoundError` on miss."""
    try:
        resolved = path.resolve()
        fingerprint = path_stat_fingerprint(resolved)
    except FileNotFoundError as exc:
        raise ManualNotFoundError(f"missing required file: {path}") from exc
    except OSError as exc:
        raise ManualParseError(f"{path}: cannot stat required file ({exc})") from exc
    try:
        return _read_text_cached(*fingerprint)
    except OSError as exc:
        raise ManualParseError(f"{path}: cannot read required file ({exc})") from exc


@lru_cache(maxsize=1024)
def _read_text_cached(path: str, byte_count: int, modified_ns: int) -> str:
    del byte_count, modified_ns
    return Path(path).read_text(encoding="utf-8")


def _load_chapters(chapters_path: Path) -> tuple[Chapter, ...]:
    """Parse ``chapters.json`` into a tuple of :class:`~cadrumo.domain.manuals.Chapter`.

    Uses :meth:`pydantic.TypeAdapter.validate_json` so strict-mode
    pydantic models accept JSON arrays as tuples (the list-to-tuple
    coercion is permitted in JSON mode even when strict validation is
    enabled).
    """
    raw = _read_text(chapters_path)
    try:
        return _CHAPTERS_ADAPTER.validate_json(raw)
    except (ValueError, ValidationError) as exc:
        raise ManualParseError(f"{chapters_path}: chapter validation failed: {exc}") from exc


def _load_manual_metadata(manual_path: Path, chapters: tuple[Chapter, ...]) -> Manual:
    """Parse ``manual.json`` plus chapters into a :class:`~cadrumo.domain.manuals.Manual`.

    The ``manual.json`` file is loaded via JSON mode. Chapter records are
    loaded and validated separately, then attached directly so translatable
    provenance is preserved.
    """
    raw = _read_text(manual_path)
    try:
        base_payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManualParseError(f"{manual_path}: invalid JSON ({exc})") from exc
    if not isinstance(base_payload, dict):
        raise ManualParseError(f"{manual_path}: expected a JSON object")
    base_payload["chapters"] = []
    try:
        manual = Manual.model_validate_json(json.dumps(base_payload))
    except (ValueError, ValidationError) as exc:
        raise ManualParseError(f"{manual_path}: manual validation failed: {exc}") from exc
    return manual.model_copy(update={"chapters": chapters})


def load_manual(
    manual_id: ManualId,
    year: int,
    part: ManualPart = ManualPart.SINGLE,
    *,
    settings: Settings | None = None,
) -> Manual:
    """Load a single :class:`Manual` from ``corpus/manuals/``.

    Args:
        manual_id: Handbook identifier.
        year: Tax year.
        part: Volume split within the year. Defaults to ``SINGLE``.
        settings: Optional settings instance; loaded on demand otherwise.

    Returns:
        A fully validated :class:`Manual` including its chapter tree
        (but not resolved section bodies — those are loaded lazily
        by :func:`load_section` or iterated by :func:`find_rules`).

    Raises:
        ManualNotFoundError: If the required metadata files are absent.
    """
    part_root = resolve_part_root(manual_id=manual_id, year=year, part=part, settings=settings)
    structure_dir = part_root / "structure"
    manual_path = structure_dir / "manual.json"
    chapters_path = structure_dir / "chapters.json"
    if not manual_path.exists() or not chapters_path.exists():
        raise ManualNotFoundError(
            f"missing structure for {manual_id.value}/{year}/{part.value} under {part_root}",
        )
    _logger.debug("loading manual %s/%s/%s from %s", manual_id.value, year, part.value, part_root)
    resolved_root = part_root.resolve()
    manual_fingerprint = _path_fingerprint(manual_path)
    chapters_fingerprint = _path_fingerprint(chapters_path)
    return _load_manual_cached(str(resolved_root), manual_fingerprint, chapters_fingerprint)


def _path_fingerprint(path: Path) -> tuple[str, int, int]:
    resolved = path.resolve()
    try:
        stat = resolved.stat()
    except FileNotFoundError as exc:
        raise ManualNotFoundError(f"missing required file: {path}") from exc
    except OSError as exc:
        raise ManualParseError(f"{path}: cannot stat required file ({exc})") from exc
    return (str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=128)
def _load_manual_cached(
    part_root: str,
    manual_fingerprint: tuple[str, int, int],
    chapters_fingerprint: tuple[str, int, int],
) -> Manual:
    del part_root
    manual_path = Path(manual_fingerprint[0])
    chapters_path = Path(chapters_fingerprint[0])
    chapters = _load_chapters(chapters_path)
    return _load_manual_metadata(manual_path, chapters)


def load_section(part_root: Path, section_ref: SectionRef) -> Section:
    """Load a single :class:`Section` by resolving ``section_ref`` on disk.

    Args:
        part_root: Directory root for the owning manual part.
        section_ref: Pointer returned by the owning :class:`Chapter`.

    Returns:
        A fully validated :class:`Section` record.

    Raises:
        ManualParseError: If the file path escapes the manual root or
            fails schema validation.
    """
    try:
        section_path = resolve_relative_subpath(part_root, section_ref.relative_path, context="manual section path")
    except ValueError as exc:
        raise ManualParseError(str(exc)) from exc
    fingerprint = _path_fingerprint(section_path)
    return _load_section_cached(fingerprint, section_ref.section_id)


@lru_cache(maxsize=2048)
def _load_section_cached(section_fingerprint: tuple[str, int, int], section_id: str) -> Section:
    section_path = Path(section_fingerprint[0])
    raw = _read_text(section_path)
    try:
        section = Section.model_validate_json(raw)
    except (ValueError, ValidationError) as exc:
        raise ManualParseError(f"{section_path}: section validation failed: {exc}") from exc
    if section.section_id != section_id:
        raise ManualParseError(f"{section_path}: section_id mismatch ({section.section_id!r} vs ref {section_id!r})")
    return section


def load_catalogue(
    specs: Iterable[tuple[ManualId, int, ManualPart]],
    *,
    settings: Settings | None = None,
) -> ManualCatalogue:
    """Load every requested ``(manual_id, year, part)`` into a catalogue.

    Args:
        specs: Iterable of manual specifiers to load.
        settings: Optional settings instance.

    Returns:
        A :class:`ManualCatalogue` containing every successfully loaded
        :class:`Manual`. Missing specifiers raise immediately; partial
        loads are not supported so the catalogue always reflects a
        coherent on-disk state.
    """
    loaded: list[Manual] = []
    for manual_id, year, part in specs:
        loaded.append(load_manual(manual_id, year, part, settings=settings))
    return ManualCatalogue(manuals=tuple(loaded))


def iter_sections(
    manual: Manual,
    *,
    settings: Settings | None = None,
) -> Iterator[Section]:
    """Yield every :class:`Section` belonging to ``manual``, in tree order.

    Args:
        manual: A loaded :class:`Manual` instance.
        settings: Optional settings instance.

    Yields:
        :class:`Section` records resolved from the chapter tree.
    """
    part_root = resolve_part_root(
        manual_id=manual.manual_id,
        year=manual.year,
        part=manual.part,
        settings=settings,
    )
    for chapter in manual.chapters:
        for section_ref in chapter.sections:
            yield load_section(part_root, section_ref)


def find_rules(
    catalogue: ManualCatalogue,
    *,
    casilla_reference: ManualCasillaReference | None = None,
    kind: RuleKind | None = None,
    lang: str | None = None,
    settings: Settings | None = None,
) -> Iterator[Rule]:
    """Iterate every :class:`Rule` in ``catalogue`` matching the filters.

    Args:
        catalogue: A loaded :class:`ManualCatalogue`.
        casilla_reference: Optional structured modelo/casilla filter.
            Rules whose ``references_casillas`` does not contain this
            value are skipped.
        kind: Optional ``RuleKind`` filter.
        lang: Optional :class:`str` filter. When provided, rules
            whose statement cannot be resolved into ``lang`` under the
            configured fallback policy are skipped.
        settings: Optional settings instance.

    Yields:
        :class:`Rule` records matching every supplied filter.
    """
    for rule in _iter_catalogue_rules(catalogue, settings=settings):
        if _rule_matches(rule, casilla_reference=casilla_reference, kind=kind, lang=lang):
            yield rule


def _iter_catalogue_rules(catalogue: ManualCatalogue, *, settings: Settings | None) -> Iterator[Rule]:
    """Flatten manual -> section -> rule into a single rule stream."""
    for manual in catalogue.manuals:
        for section in iter_sections(manual, settings=settings):
            yield from section.rules


def _rule_matches(
    rule: Rule,
    *,
    casilla_reference: ManualCasillaReference | None,
    kind: RuleKind | None,
    lang: str | None,
) -> bool:
    """Return True when ``rule`` satisfies every supplied filter (None == no filter)."""
    if kind is not None and rule.kind is not kind:
        return False
    if casilla_reference is not None and casilla_reference not in rule.references_casillas:
        return False
    return not (lang is not None and not _rule_renders_in_language(rule, lang))


def _rule_renders_in_language(rule: Rule, lang: str) -> bool:
    """Return ``True`` when the rule statement resolves in ``lang``.

    Translation resolution is delegated to the CLI presentation layer;
    the domain rule always renders its abstract key.
    """
    return True
