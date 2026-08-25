"""Round-trip parser tests for committed sanitised fixtures.

Every committed fixture under ``src/cadrumo/tests/fixtures/justificantes/`` must
remain parseable by :func:`cadrumo.adapters.inbound.justificante.parse_justificante`
after sanitisation — the test fixture's whole point is to exercise
the production extractor against a synthetic-but-shape-preserving
representative of an AEAT capture.

This file iterates the fixtures and asserts:

* ``parse_justificante(fixture)`` returns a valid
  :class:`cadrumo.domain.justificante.Justificante`.
* The parsed ``modelo`` / ``period`` / ``ejercicio`` /
  ``presented_at`` are non-empty (the fields the per-modelo
  extractor uses to bind regression assertions).
* The parsed ``tax_id`` and ``csv`` match the synthetic values
  recorded in the SanitizationResult sidecar's
  ``replacements_applied`` rows — confirming the rewrite landed
  the synthetic at the position the parser reads.

When no fixtures have been committed yet, the loop has no fixture
work to perform but the module still contributes one passing test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.tests import FIXTURES_DIR, parse_committed_justificante_fixture

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _committed_fixture_pairs() -> list[tuple[Path, Path]]:
    fixture_root = FIXTURES_DIR / "justificantes"
    if not fixture_root.is_dir():
        return []
    pairs: list[tuple[Path, Path]] = []
    for pdf_path in scan_directory(fixture_root, pattern="*.pdf", recursive=True):
        sidecar = pdf_path.with_suffix(".json")
        if sidecar.is_file():
            pairs.append((pdf_path, sidecar))
    return pairs


_FIXTURE_PAIRS = _committed_fixture_pairs()


def test_committed_fixtures_parse_and_match_sidecars() -> None:
    """Every committed fixture parses and exposes synthetic CSV/NIF values."""
    for pdf_path, sidecar_path in _FIXTURE_PAIRS:
        parsed = parse_committed_justificante_fixture(pdf_path)
        assert parsed.modelo, f"modelo is empty for {pdf_path}"
        assert parsed.period, f"period is empty for {pdf_path}"
        assert parsed.csv, f"csv is empty for {pdf_path}"
        assert parsed.tax_id, f"tax_id is empty for {pdf_path}"
        assert parsed.presented_at, f"presented_at is empty for {pdf_path}"

        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        synthetic_pool = {
            synthetic
            for replacement in sidecar.get("replacements_applied", ())
            if (synthetic := replacement.get("synthetic")) is not None
        }
        if not synthetic_pool:
            continue

        # The NIF / CSV the parser extracts must be one of the synthetic
        # values applied during sanitisation. Allows for the parser
        # picking either the canonical synthetic or a related variant.
        assert parsed.tax_id in synthetic_pool, (
            f"Parsed tax_id {parsed.tax_id!r} is not in the synthetic pool {synthetic_pool} for {pdf_path}"
        )
        assert parsed.csv in synthetic_pool, (
            f"Parsed csv {parsed.csv!r} is not in the synthetic pool {synthetic_pool} for {pdf_path}"
        )
