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


#: Below this the fixture corpus has stopped being read. Live: 63 committed
#: PDFs, 60 carrying a sidecar. A floor, not a pinned count.
_MINIMUM_CHECKED_FIXTURES = 20


def test_committed_fixtures_parse_and_match_sidecars() -> None:
    """Every committed fixture parses and exposes synthetic CSV/NIF values.

    The synthetic-pool comparison is the half that matters: it proves the
    parser pulled a SANITISED identity out of the fixture rather than a real
    one. Every route to an empty pool used to skip that comparison silently -
    a sidecar without its replacements list, or a list with no synthetic - so
    a fixture carrying a real identity would have passed by not being asked.
    """
    checked = 0
    for pdf_path, sidecar_path in _FIXTURE_PAIRS:
        parsed = parse_committed_justificante_fixture(pdf_path)
        assert parsed.modelo, f"modelo is empty for {pdf_path}"
        assert parsed.period, f"period is empty for {pdf_path}"
        assert parsed.csv, f"csv is empty for {pdf_path}"
        assert parsed.tax_id, f"tax_id is empty for {pdf_path}"
        assert parsed.presented_at, f"presented_at is empty for {pdf_path}"

        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        assert "replacements_applied" in sidecar, (
            f"{sidecar_path} carries no replacements list; a committed audit log without one "
            "cannot prove the identity this parser extracted was ever synthesised"
        )
        synthetic_pool = {
            synthetic
            for replacement in sidecar["replacements_applied"]
            if (synthetic := replacement.get("synthetic")) is not None
        }
        assert synthetic_pool, (
            f"{sidecar_path} records no synthetic value, so the comparison below would be "
            "skipped and this fixture never asked whether its identity is real"
        )
        checked += 1

        # The NIF / CSV the parser extracts must be one of the synthetic
        # values applied during sanitisation. Allows for the parser
        # picking either the canonical synthetic or a related variant.
        assert parsed.tax_id in synthetic_pool, (
            f"Parsed tax_id {parsed.tax_id!r} is not in the synthetic pool {synthetic_pool} for {pdf_path}"
        )
        assert parsed.csv in synthetic_pool, (
            f"Parsed csv {parsed.csv!r} is not in the synthetic pool {synthetic_pool} for {pdf_path}"
        )

    assert checked >= _MINIMUM_CHECKED_FIXTURES, (
        f"only {checked} committed fixture(s) reached the synthetic comparison, from "
        f"{len(_FIXTURE_PAIRS)} paired; below this the corpus has stopped being read and a "
        "clean result says nothing about whether a real identity survived sanitisation"
    )
