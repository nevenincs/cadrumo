"""No real identity survives sanitisation in a committed real-corpus fixture.

The sibling adversarial gate asserts that the synthetic placeholders LANDED. It
never asserts that no real identity SURVIVED, and its docstring justifies the
omission by saying the test does not have the cleartext. This module is the
other half, and it disproves that justification: detection needs no cleartext,
only a pattern, a checksum, and the sidecar's own record of what the sanitiser
wrote. See :mod:`._residual_identity_scan` for the argument in full.

SCOPE, AND WHY IT IS PROVENANCE-DRIVEN RATHER THAN A LIST. Only fixtures whose
sidecar declares ``provenance = "real_corpus"`` are scanned. That is not an
exemption list -- the project rule ``fixture-provenance-declared-in-sidecar``
forbids hardcoding per-fixture exceptions in test source, and this is the
opposite: the scope is READ from each sidecar, so a new real specimen is
enrolled automatically the moment it lands.

The scope is principled, not convenient. A residual is a value that entered the
document as real and survived, so the risk class is exactly "a real document was
sanitised". A ``synthetic_generated`` fixture never carried a real identity: its
generator AUTHORS identity-shaped values outright and does not record them in
``replacements_applied``, because nothing was replaced. Scanning one therefore
measures the generator's own fakes, not a leak -- confirmed empirically, since
every checksum-valid hit across the committed tree today falls on a synthetic
fixture and every real-corpus fixture is clean.

Re-stamping a real fixture as synthetic to silence this gate does not work: the
provenance-vs-``/Producer`` cross-check in
``registry/tests/test_verification_source_fixture_metadata.py`` already fails a
sidecar claiming ``synthetic_generated`` on a PDF without the generator
signature. That gate owns the mis-stamp check; this one does not restate it.

HANDLING RULE. No assertion in this module can print a matched value. Findings
carry a pattern class, a surface, and an offset, and that is all the failure
message renders.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....tests._inventory import SRC_CADRUMO
from ._residual_identity_scan import (
    CHECKSUM_VERIFIED_KINDS,
    ResidualKind,
    scan_for_residual_identities,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

#: Obviously-fake identities used to prove the scanner actually fires.
#:
#: Both are checksum-valid but built from all-zero bodies so neither can
#: resemble a real document or account. ``00000000T`` is the AEAT control letter
#: for body ``0`` (``TRWAGMYFPDXBNJZSQVHLCKE[0]``); ``ES82`` + twenty zeros is
#: the mod-97 completion of an all-zero BBAN.
_FAKE_NIF = "00000000T"
_FAKE_IBAN = "ES8200000000000000000000"


def _real_corpus_fixtures() -> list[tuple[Path, Path]]:
    """Every committed artefact whose sidecar declares real provenance.

    Walks the whole package, not one fixture directory. The module docstring
    above promises the scope is READ from each sidecar so a new real specimen
    enrols "automatically the moment it lands"; scanning only
    ``fixtures/justificantes`` did not keep that promise. Four real-provenance
    artefacts live outside it in the ledger evidence corpus and were never
    scanned once.

    The narrowing also made this gate unsatisfiable the moment it landed. Its
    two justificante specimens had just been replaced with synthetic ones
    because they leaked, so the directory held no real specimen at all, and the
    non-emptiness guard below fired with a message asserting that NO committed
    fixture declares ``real_corpus`` -- while four do. A gate reporting a red
    on a false premise is worse than a silent one, because the premise is what
    a reader carries away.

    Both sidecar conventions in the tree are honoured: ``X.pdf`` beside
    ``X.json`` for the justificante fixtures, and ``X.<ext>`` beside
    ``X.<ext>.provenance.json`` for the evidence corpus. Non-PDF artefacts are
    included because the scan reads bytes and a JPEG can carry an identity in
    its metadata exactly as a PDF can in a content stream.
    """
    pairs: list[tuple[Path, Path]] = []
    seen: set[Path] = set()
    for sidecar_path in sorted(SRC_CADRUMO.rglob("*.json")):
        if "__pycache__" in sidecar_path.parts:
            continue
        name = sidecar_path.name
        if name.endswith(".provenance.json"):
            target = sidecar_path.parent / name[: -len(".provenance.json")]
        else:
            target = sidecar_path.with_suffix(".pdf")
        if not target.is_file() or target in seen:
            continue
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(sidecar, dict) and sidecar.get("provenance") == "real_corpus":
            seen.add(target)
            pairs.append((target, sidecar_path))
    return pairs


_REAL_CORPUS_FIXTURES = _real_corpus_fixtures()


def test_real_corpus_fixture_scope_is_not_empty() -> None:
    """The gate must have something to scan, or its green means nothing.

    Without this, deleting or re-stamping every real specimen would leave the
    scan loop iterating zero times and reporting success -- the same vacuity the
    sibling gate's own "when no fixtures are committed yet" branch tolerates.
    """
    assert _REAL_CORPUS_FIXTURES, (
        "no committed fixture declares provenance='real_corpus', so the residual-identity "
        "scan has nothing to check and its passing result is vacuous"
    )


@pytest.mark.parametrize(
    "pdf_path,sidecar_path",
    _REAL_CORPUS_FIXTURES,
    ids=[f"{p.parent.name}-{p.stem}" for p, _ in _REAL_CORPUS_FIXTURES],
)
def test_no_checksum_valid_identity_survives_in_a_real_corpus_fixture(
    pdf_path: Path,
    sidecar_path: Path,
) -> None:
    """No unaccounted-for, checksum-valid identity remains in a sanitised specimen."""
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    findings = scan_for_residual_identities(pdf_path.read_bytes(), sidecar)
    assert not findings, (
        f"RESIDUAL-IDENTITY [{pdf_path.parent.name}/{pdf_path.stem}]: "
        f"{len(findings)} checksum-valid identity value(s) survived sanitisation and are not "
        f"accounted for by the sidecar's replacements_applied.\n"
        + "\n".join(f"  {finding.describe()}" for finding in findings)
        + "\n  Values are deliberately not shown. Re-sanitise the specimen; do not add an exception."
    )


def test_scanner_flags_a_planted_identity_the_sidecar_does_not_account_for() -> None:
    """Anti-tautology proof: the scanner fires on a value nobody declared.

    The gate above is an absence assertion, and an absence assertion is worth
    nothing unless the detector behind it demonstrably fires. Planting two
    checksum-valid identities into a document whose sidecar declares no
    replacements must produce exactly two blocking findings.
    """
    planted = _pdf_bytes_containing(f"NIF {_FAKE_NIF} IBAN {_FAKE_IBAN}")
    findings = scan_for_residual_identities(planted, {"replacements_applied": []})
    kinds = {finding.kind for finding in findings}
    assert kinds == {ResidualKind.NIF_NIE, ResidualKind.IBAN}, (
        f"planted NIF and IBAN must both be flagged; got kinds {sorted(k.value for k in kinds)}"
    )


def test_scanner_does_not_flag_a_value_the_sidecar_accounts_for() -> None:
    """The other half of the proof: a declared synthetic is not a residual.

    This is the condition that makes cleartext-free detection possible. Without
    it every scan would drown in the sanitiser's own replacements, since a
    synthetic placeholder is identity-shaped and checksum-valid by design. If
    this test ever fails, the gate has become a noise generator and will be
    silenced -- the failure mode that left the original hole open.
    """
    planted = _pdf_bytes_containing(f"NIF {_FAKE_NIF} IBAN {_FAKE_IBAN}")
    sidecar = {
        "replacements_applied": [
            {"synthetic": _FAKE_NIF},
            {"synthetic": _FAKE_IBAN},
        ]
    }
    assert scan_for_residual_identities(planted, sidecar) == ()


def test_scanner_ignores_identity_shaped_values_that_fail_their_checksum() -> None:
    """The checksum layer must not be decorative.

    An eight-digit run followed by a letter is common in a content stream. If
    the scanner flagged shape alone it would fire constantly, so this pins that
    a wrong control letter and a wrong IBAN check are both ignored. Without it,
    a refactor that dropped the checksum call would still pass every other test
    in this module.
    """
    # Same bodies as the valid fixtures above, with deliberately wrong checks.
    wrong_nif = "00000000X"
    wrong_iban = "ES0000000000000000000000"
    planted = _pdf_bytes_containing(f"NIF {wrong_nif} IBAN {wrong_iban}")
    assert scan_for_residual_identities(planted, {"replacements_applied": []}) == ()


def test_advisory_kinds_are_excluded_from_the_blocking_tier() -> None:
    """Email and phone carry no checksum, so they must not fail a build.

    Measured over the committed tree, the phone pattern alone produces over a
    thousand matches, essentially all of them digit runs inside content streams
    rather than telephone numbers. A gate that fires that often is silenced
    rather than fixed, so the shape-only classes stay reportable but
    non-blocking.
    """
    assert {ResidualKind.NIF_NIE, ResidualKind.IBAN} == CHECKSUM_VERIFIED_KINDS
    assert ResidualKind.EMAIL not in CHECKSUM_VERIFIED_KINDS
    assert ResidualKind.PHONE not in CHECKSUM_VERIFIED_KINDS


def _pdf_bytes_containing(text: str) -> bytes:
    """Build a one-page PDF whose content stream carries ``text``."""
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=A4)
    pdf_canvas.setFont("Helvetica", 10)
    pdf_canvas.drawString(50, 700, text)
    pdf_canvas.showPage()
    pdf_canvas.save()
    return buffer.getvalue()
