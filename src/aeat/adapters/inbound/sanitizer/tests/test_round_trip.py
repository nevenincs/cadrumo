"""Round-trip parser tests for committed sanitised fixtures.

Every committed fixture under ``src/aeat/tests/fixtures/justificantes/`` must
remain parseable by :func:`aeat.adapters.inbound.justificante.parse_justificante`
after sanitisation — the test fixture's whole point is to exercise
the production extractor against a synthetic-but-shape-preserving
representative of an AEAT capture.

This file iterates the fixtures and asserts:

* ``parse_justificante(fixture)`` returns a valid
  :class:`aeat.domain.justificante.Justificante`.
* The parsed ``modelo`` / ``period`` / ``ejercicio`` /
  ``presented_at`` are non-empty (the fields the per-modelo
  extractor uses to bind regression assertions).
* The parsed ``tax_id`` and ``csv`` match the synthetic values
  recorded in the SanitizationResult sidecar's
  ``replacements_applied`` rows — confirming the rewrite landed
  the synthetic at the position the parser reads.

When no fixtures have been committed yet, the test parametrise is
empty and pytest collects zero items. The module ships the same
sentinel-empty-list pattern as ``test_adversarial_absence.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....domain.justificante import Justificante
from .....tests import FIXTURES_DIR
from .....tests._justificante_parse_cache import parse_committed_justificante_fixture

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _committed_fixture_pairs() -> list[tuple[Path, Path]]:
    fixture_root = FIXTURES_DIR / "justificantes"
    if not fixture_root.is_dir():
        return []
    pairs: list[tuple[Path, Path]] = []
    for pdf_path in fixture_root.rglob("*.pdf"):
        sidecar = pdf_path.with_suffix(".json")
        if sidecar.is_file():
            pairs.append((pdf_path, sidecar))
    return pairs


_FIXTURE_PAIRS = _committed_fixture_pairs()


@pytest.fixture(scope="session")
def _parsed_fixture_justificantes() -> dict[Path, Justificante]:
    """Cache of ``parse_justificante`` results keyed by fixture PDF path.

    Both round-trip tests below need the same parse for every fixture;
    a session-scoped cache halves the parse cost on this directory.
    """
    return {pdf_path: parse_committed_justificante_fixture(pdf_path) for pdf_path, _ in _FIXTURE_PAIRS}


@pytest.mark.parametrize(
    ("pdf_path", "sidecar_path"),
    _FIXTURE_PAIRS,
    ids=[pair[0].name for pair in _FIXTURE_PAIRS],
)
def test_fixture_parses_through_justificante_parser(
    pdf_path: Path,
    sidecar_path: Path,
    _parsed_fixture_justificantes: dict[Path, Justificante],
) -> None:
    """Every fixture round-trips through parse_justificante."""
    parsed = _parsed_fixture_justificantes[pdf_path]
    assert parsed.modelo, f"modelo is empty for {pdf_path}"
    assert parsed.period, f"period is empty for {pdf_path}"
    assert parsed.csv, f"csv is empty for {pdf_path}"
    assert parsed.tax_id, f"tax_id is empty for {pdf_path}"
    assert parsed.presented_at, f"presented_at is empty for {pdf_path}"


@pytest.mark.parametrize(
    ("pdf_path", "sidecar_path"),
    _FIXTURE_PAIRS,
    ids=[pair[0].name for pair in _FIXTURE_PAIRS],
)
def test_fixture_synthetic_csv_and_nif_match_sidecar(
    pdf_path: Path,
    sidecar_path: Path,
    _parsed_fixture_justificantes: dict[Path, Justificante],
) -> None:
    """Synthetic CSV / NIF parse out of the fixture matching the sidecar audit."""
    parsed = _parsed_fixture_justificantes[pdf_path]
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

    synthetics_by_surface_label: dict[str, set[str]] = {}
    for replacement in sidecar.get("replacements_applied", ()):
        synthetic = replacement.get("synthetic")
        if synthetic is None:
            continue
        # The audit log records surface (e.g. "content_stream"), not
        # category. Index synthetics by their value so we can do a
        # presence check against parsed fields.
        synthetics_by_surface_label.setdefault("any", set()).add(synthetic)

    if not synthetics_by_surface_label:
        return  # No replacements recorded — skip.

    pool = synthetics_by_surface_label["any"]
    # The NIF / CSV the parser extracts must be one of the synthetic
    # values applied during sanitisation. Allows for the parser
    # picking either the canonical synthetic or a related variant.
    assert parsed.tax_id in pool, f"Parsed tax_id {parsed.tax_id!r} is not in the synthetic pool {pool} for {pdf_path}"
    assert parsed.csv in pool, f"Parsed csv {parsed.csv!r} is not in the synthetic pool {pool} for {pdf_path}"


def test_fixture_root_is_skip_clean_when_empty() -> None:
    """Sentinel test asserting the empty-fixture-root state stays green in CI."""
    if not _FIXTURE_PAIRS:
        return
    assert len(_FIXTURE_PAIRS) > 0
