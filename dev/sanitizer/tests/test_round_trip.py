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
from typing import Any

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.tests.inventory import FIXTURES_DIR
from cadrumo.tests.justificante_parse_cache import parse_committed_justificante_fixture

from ..residual_identity import is_self_replacement

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


def synthetic_pool_of(sidecar: dict[str, Any]) -> set[str]:
    """Return the values a sidecar may legitimately vouch for as synthetic.

    The pool is read out of the artefact under judgement, which is the one
    direction that can inflate the clean set here: the gate asks whether the
    parser pulled a SANITISED identity, and the set of values that count as
    sanitised is supplied by the same sidecar. A rewrite whose ``real`` equals
    its ``synthetic`` changes nothing in the document yet lands a row naming
    the surviving cleartext, so the real identity becomes a member of its own
    exoneration set and the assertions below pass on the value they exist to
    catch. Production accepts that rewrite today.

    The row contradicts itself, and that is the join taken here: ``real_sha256``
    is the digest of the cleartext, so a row where it also digests the
    ``synthetic`` is claiming a value was replaced by itself. Such a row is cut.
    A row carrying no ``real_sha256`` asserts nothing of the kind and is
    admitted unchanged - 150 of the 180 committed rows are in that state, so
    the join narrows nothing that is merely under-documented.
    """
    return {
        synthetic
        for replacement in sidecar["replacements_applied"]
        if (synthetic := replacement.get("synthetic")) is not None and not is_self_replacement(replacement, synthetic)
    }


def test_committed_fixtures_parse_and_match_sidecars() -> None:
    """Every committed fixture parses and exposes synthetic CSV/NIF values.

    The synthetic-pool comparison is the half that matters: it proves the
    parser pulled a SANITISED identity out of the fixture rather than a real
    one. Every route to an empty pool used to skip that comparison silently -
    a sidecar without its replacements list, or a list with no synthetic - so
    a fixture carrying a real identity would have passed by not being asked.

    The pool itself comes from the artefact under judgement; see
    :func:`synthetic_pool_of` for the row it therefore refuses to read.
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
        synthetic_pool = synthetic_pool_of(sidecar)
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


_SPECIMEN_NIF = "00000000T"
"""Checksum-valid but all-zero, so it cannot resemble a real taxpayer."""

_SPECIMEN_IBAN = "ES8200000000000000000000"
_SPECIMEN_SYNTHETIC_IBAN = "ES6011111111111111111111"


def _no_op_rewrite_sidecar() -> tuple[bytes, dict[str, Any]]:
    """Sanitise a specimen with a rewrite that replaces the NIF by itself.

    Built through production: the replacement records validate the synthetic's
    SHAPE and never that it differs from the cleartext, so ``real == synthetic``
    is a state ``sanitize_pdf`` accepts and records. The IBAN alongside it is a
    genuine replacement, which is what lets the teeth below check both
    directions from one specimen. Neither value is ever committed.
    """
    from pydantic import SecretStr

    from cadrumo.tests.pdf_fixtures import text_pdf_bytes

    from .._pipeline import sanitize_pdf
    from .._records import IbanReplacement, NifReplacement, TokenMap

    token_map = TokenMap(
        nif=(NifReplacement(real=SecretStr(_SPECIMEN_NIF), synthetic=_SPECIMEN_NIF, surface_label="taxpayer NIF"),),
        iban=(
            IbanReplacement(
                real=SecretStr(_SPECIMEN_IBAN),
                synthetic=_SPECIMEN_SYNTHETIC_IBAN,
                surface_label="domiciliacion IBAN",
            ),
        ),
    )
    source = text_pdf_bytes((f"NIF: {_SPECIMEN_NIF}", f"Codigo Cuenta Cliente (IBAN): {_SPECIMEN_IBAN}"))
    result = sanitize_pdf(source, token_map)
    return result.output_bytes, {"replacements_applied": [row.model_dump() for row in result.replacements_applied]}


def test_a_self_replacing_row_cannot_vouch_for_the_value_it_left_standing() -> None:
    """Detector teeth: the cleartext must not be admitted by its own row.

    The empty-manifest control is what separates a real leak from a mere
    disagreement: scanned against no manifest at all the specimen is dirty,
    which proves the cleartext genuinely survived the no-op rewrite rather
    than the pool simply holding a different opinion about it.
    """
    from ..residual_identity import ResidualKind, scan_for_residual_identities

    output, sidecar = _no_op_rewrite_sidecar()
    rows = sidecar["replacements_applied"]
    assert any(row.get("synthetic") == _SPECIMEN_NIF for row in rows), (
        "the sanitiser recorded no row for the no-op rewrite, so these teeth bite on nothing"
    )

    survived = scan_for_residual_identities(output, {"replacements_applied": []})
    assert ResidualKind.NIF_NIE in {finding.kind for finding in survived}, (
        "the cleartext NIF did not survive the no-op rewrite, so the pool membership below proves nothing"
    )

    unjoined = {row["synthetic"] for row in rows if row.get("synthetic") is not None}
    assert _SPECIMEN_NIF in unjoined, "the specimen no longer reproduces the self-accounting shape this gate is about"
    assert _SPECIMEN_NIF not in synthetic_pool_of(sidecar), (
        "a row claiming a value was replaced by itself was admitted into the synthetic pool, "
        "so a parsed cleartext identity would read as a sanitised one"
    )


def test_a_genuine_replacement_is_still_vouched_for() -> None:
    """The anti-noise arm: the join must cut only the contradicting row."""
    _, sidecar = _no_op_rewrite_sidecar()

    assert _SPECIMEN_SYNTHETIC_IBAN in synthetic_pool_of(sidecar), (
        "a genuine replacement lost its place in the pool, which would fail every honest fixture"
    )


def test_a_row_without_a_real_digest_is_admitted_unchanged() -> None:
    """Most committed rows assert no digest, and must keep their standing."""
    sidecar: dict[str, Any] = {"replacements_applied": [{"synthetic": "Y0000001S", "surface": "content_stream"}]}

    assert synthetic_pool_of(sidecar) == {"Y0000001S"}
