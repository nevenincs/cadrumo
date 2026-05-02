"""Filesystem loader for synthetic filing-history fixtures.

Resolves and reads the JSON corpus under
``tests/fixtures/filing_history/<modelo>/`` into strict
:class:`aeat.application.filing._testing_schema.FilingRecord` instances
through :func:`load_filing_history`. All pydantic v2 strict validation
errors and IO failures are surfaced as
:exc:`aeat.core.errors.FilingFixtureError`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from ...core.errors import FilingFixtureError
from ...core.logging import get_logger
from ._testing_schema import FilingRecord

_logger = get_logger(__name__)

_FIXTURE_SUBPATH = ("tests", "fixtures", "filing_history")


def _resolve_fixtures_root() -> Path:
    """Resolve the repository-rooted synthetic fixtures directory.

    Walks parent directories from this file until a directory
    containing ``tests/fixtures/filing_history/`` is found. The
    walk terminates at the filesystem root.

    Returns:
        The absolute :class:`~pathlib.Path` to the fixtures root.

    Raises:
        FilingFixtureError: When the fixtures root cannot be
            located relative to this module.
    """
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        root = candidate
        for part in _FIXTURE_SUBPATH:
            root = root / part
        if root.is_dir():
            return root
    raise FilingFixtureError(
        f"Could not resolve synthetic fixtures root from {here!s}; "
        f"expected a sibling {'/'.join(_FIXTURE_SUBPATH)} directory."
    )


SYNTHETIC_FIXTURES_ROOT: Path = _resolve_fixtures_root()
"""Absolute path to ``tests/fixtures/filing_history/``."""


def _modelo_dir(modelo: str) -> Path:
    return SYNTHETIC_FIXTURES_ROOT / f"modelo_{modelo}"


def _iter_fixture_paths(modelo: str | None) -> Iterator[Path]:
    if modelo is not None:
        target = _modelo_dir(modelo)
        if not target.is_dir():
            raise FilingFixtureError(f"No synthetic fixtures for modelo {modelo!r} at {target!s}")
        yield from sorted(target.glob("*.json"))
        return
    for child in sorted(SYNTHETIC_FIXTURES_ROOT.iterdir()):
        if child.is_dir() and child.name.startswith("modelo_"):
            yield from sorted(child.glob("*.json"))


def _load_one(path: Path) -> FilingRecord:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FilingFixtureError(f"Cannot read fixture {path!s}: {exc}") from exc
    # Sanity-check the JSON so a malformed file surfaces a crisp error
    # before pydantic sees it.
    try:
        json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FilingFixtureError(f"Malformed JSON in fixture {path!s}: {exc}") from exc
    try:
        # ``model_validate_json`` applies pydantic v2's JSON-mode
        # coercion (ISO datetimes, Decimal from strings) while still
        # enforcing ``strict=True`` on non-string-typed fields.
        return FilingRecord.model_validate_json(raw)
    except ValidationError as exc:
        raise FilingFixtureError(f"Fixture {path!s} failed schema validation: {exc}") from exc


def load_filing_history(
    modelo: str | None = None,
    period: str | None = None,
) -> Iterator[FilingRecord]:
    """Yield synthetic filing records from the repository corpus.

    The iterator is deterministic: records are yielded in sorted
    order first by modelo directory, then by filename. This keeps
    test ordering stable across platforms.

    Args:
        modelo: If given, restrict to a single modelo (e.g.
            ``"130"``). Must match an existing ``modelo_<id>``
            directory under :data:`SYNTHETIC_FIXTURES_ROOT`.
        period: If given, yield only records whose :attr:`period`
            equals this value exactly (e.g. ``"2024Q1"``).

    Yields:
        Each :class:`FilingRecord` parsed through strict pydantic
        validation.

    Raises:
        FilingFixtureError: When the fixtures directory cannot be
            reached, a file cannot be read, JSON parsing fails, or
            a payload fails strict validation (including the
            synthetic-only invariant checks).
    """
    for path in _iter_fixture_paths(modelo):
        record = _load_one(path)
        if period is not None and record.period != period:
            continue
        _logger.debug("loaded synthetic fixture record_id=%s path=%s", record.record_id, path)
        yield record


__all__ = [
    "SYNTHETIC_FIXTURES_ROOT",
    "load_filing_history",
]
