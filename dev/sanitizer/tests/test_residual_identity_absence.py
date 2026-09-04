"""No real identity survives sanitisation in a committed real-corpus fixture.

The sibling adversarial gate asserts that the synthetic placeholders LANDED. It
never asserts that no real identity SURVIVED, and its docstring justifies the
omission by saying the test does not have the cleartext. This module is the
other half, and it disproves that justification: detection needs no cleartext,
only a pattern, a checksum, and the sidecar's own record of what the sanitiser
wrote. See :mod:`dev.sanitizer.residual_identity` for the argument in full.

SCOPE, AND WHY IT IS PROVENANCE-DRIVEN RATHER THAN A LIST. Only fixtures whose
sidecar declares ``provenance = "real_corpus"`` are scanned. That is not an
exemption list -- the project rule ``aeat-quality-gates``
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

THE LIVE POSITIVE CONTROL, AND WHY IT IS NOT COMMITTED. The scans above are
absence assertions over already-sanitised artefacts. What they cannot show is
that the gate and the sanitiser AGREE: that a document the sanitiser really
processed passes the scan when checked against the manifest the sanitiser
really emitted. Every other proof in this module feeds a hand-written sidecar,
so a sanitiser that wrote a synthetic it forgot to record -- or recorded under a
different normalisation -- would false-positive on its own output, and a gate
that fires on correct output is a gate that gets silenced. That is the failure
mode the original hole came from.

:func:`test_the_gate_and_the_sanitiser_agree_end_to_end` closes it by building a
PRE-SANITISATION specimen: a document deliberately carrying checksum-valid
identity tokens, which the gate must FLAG, which the real ``sanitize_pdf`` then
processes, and whose output the gate must find CLEAN against the sanitiser's own
``replacements_applied``. Until the withdrawn real renders were replaced, the
leaking fixtures themselves were that control; replacing them removed it, and
this restores it.

The specimen is GENERATED IN-TEST and never committed. That is a deliberate
choice over the alternatives -- a new provenance value, or its own directory --
and the reasons are structural rather than aesthetic:

- A file that deliberately carries identity-shaped tokens is the one kind of
  file that must never enter git history, because history outlives every
  intention about it. That is the lesson the whole fixture replacement was
  about.
- It needs no exclusion at all. ``_real_corpus_fixtures`` walks COMMITTED
  artefacts under the package root, so an in-memory specimen is outside the
  scope by construction. A committed one would have to be taught to the scanner,
  and a scanner that knows about a specific specimen is the per-fixture
  allowlist ``aeat-quality-gates`` forbids, whatever it is
  called.
- Nothing is lost by it: ``sanitize_pdf`` takes bytes, not a path, so the
  end-to-end path is identical either way.

Its tokens are checksum-valid because the detectors verify checksums and would
not fire otherwise, and they are built from all-zero and all-one bodies so no
reader can mistake them for a real document or account.

HANDLING RULE. No assertion in this module can print a matched value. Findings
carry a pattern class, a surface, and an offset, and that is all the failure
message renders.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import SecretStr

from cadrumo.core.directory_scan import scan_directory
from cadrumo.tests import SRC_CADRUMO
from cadrumo.tests.pdf_fixtures import text_pdf_bytes

from .._pipeline import sanitize_pdf
from .._records import IbanReplacement, NameReplacement, NifReplacement, TokenMap
from ..residual_identity import CHECKSUM_VERIFIED_KINDS, ResidualKind, scan_for_residual_identities

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Synthetic specimen identities PLANTED to prove the scanner actually fires.
#:
#: Both are checksum-valid but built from all-zero bodies so neither can
#: resemble a real document or account. ``00000000T`` is the AEAT control letter
#: for body ``0`` (``TRWAGMYFPDXBNJZSQVHLCKE[0]``); ``ES82`` + twenty zeros is
#: the mod-97 completion of an all-zero BBAN.
#:
#: Named for what they ARE -- values planted into a specimen -- rather than for
#: what they are not. They are a positive control, not a test double: nothing
#: here stands in for a collaborator, and the real ``sanitize_pdf`` processes
#: them. The ``mock/fake/stub/spy/dummy`` vocabulary is banned tree-wide by
#: ``tests/test_mock_inventory.py`` precisely because it reads as substitution,
#: which would misdescribe these and mask a real double elsewhere. ``_PLANTED_``
#: also pairs with the ``_SYNTHETIC_`` values below, so the specimen's before
#: and after sides are one vocabulary.
_PLANTED_NIF = "00000000T"
_PLANTED_IBAN = "ES8200000000000000000000"

#: The legal-entity and prefixed spellings of the same all-zero convention.
#:
#: ``B00000000`` is an all-zero CIF body under the ``B`` kind, whose control is
#: a digit and is ``0`` for that body; ``ES00000000T`` is the intra-community
#: spelling of the planted NIF above. Both are as unmistakably synthetic as the
#: pair above and exist for the same reason: a class cannot be shown to refuse a
#: wrong control character unless it is also shown to accept a right one.
_PLANTED_CIF = "B00000000"
_PLANTED_NIF_IVA = "ES00000000T"
_PLANTED_NAME = "NOMBRE DE PRUEBA CERO"
"""The name the pre-sanitisation specimen carries before the sanitiser rewrites it.

Names carry no checksum, so this is never a blocking finding; it is here because
a specimen the sanitiser rewrites on only one axis would not exercise the
manifest across the categories a real ``TokenMap`` declares.
"""

#: What the sanitiser writes IN PLACE of the planted values.
#:
#: Both are checksum-valid, and deliberately DIFFERENT from the planted pair, so
#: a sanitiser that failed to rewrite anything would leave the planted values in
#: place and the end-to-end control would still fire. All-one bodies keep them
#: as obviously synthetic on sight as the all-zero originals.
_SYNTHETIC_NIF = "Y0000001S"
_SYNTHETIC_IBAN = "ES6011111111111111111111"
_SYNTHETIC_NAME = "APELLIDO APELLIDO NOMBRE"


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
    for sidecar_path in scan_directory(SRC_CADRUMO, pattern="*.json", recursive=True):
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
    planted = _pdf_bytes_containing(f"NIF {_PLANTED_NIF} IBAN {_PLANTED_IBAN}")
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
    planted = _pdf_bytes_containing(f"NIF {_PLANTED_NIF} IBAN {_PLANTED_IBAN}")
    sidecar = {
        "replacements_applied": [
            {"synthetic": _PLANTED_NIF},
            {"synthetic": _PLANTED_IBAN},
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
    assert ResidualKind.EMAIL not in CHECKSUM_VERIFIED_KINDS
    assert ResidualKind.PHONE not in CHECKSUM_VERIFIED_KINDS
    assert frozenset(ResidualKind) - {ResidualKind.EMAIL, ResidualKind.PHONE} == CHECKSUM_VERIFIED_KINDS


@pytest.mark.parametrize(
    ("shape_only", "kind"),
    [
        # Each body below is the shape its class matches, carrying a control
        # character the AEAT algorithm does not produce for that body. The
        # expected control for an all-zero NIF body is 'T' and for the CIF body
        # 1234567 under kind 'B' it is '4', both derived from the published
        # algorithm rather than from this scanner's output.
        ("00000000X", ResidualKind.NIF_NIE),
        ("K0000000X", ResidualKind.NIF_NIE),
        ("B12345670", ResidualKind.CIF),
        ("ESB12345670", ResidualKind.NIF_IVA),
        ("ES00000000X", ResidualKind.NIF_IVA),
        ("ES0000000000000000000000", ResidualKind.IBAN),
    ],
)
def test_every_blocking_class_is_admitted_by_arithmetic_and_not_by_shape(
    shape_only: str,
    kind: ResidualKind,
) -> None:
    """A blocking class must reject its own shape when the check character is wrong.

    Membership of :data:`CHECKSUM_VERIFIED_KINDS` is a claim that arithmetic,
    not shape, admits the match. Asserting the membership alone would let a
    class join the blocking tier with a validator that accepts everything, so
    each class is made to refuse a specimen of exactly its own shape.
    """
    planted = _pdf_bytes_containing(f"identity {shape_only}")

    findings = scan_for_residual_identities(planted, {"replacements_applied": []})

    assert kind not in {finding.kind for finding in findings}, (
        f"{kind.value} reported a specimen of its own shape whose control character is wrong, "
        "so the class is admitted by shape rather than by its checksum"
    )


def test_a_legal_entity_identity_and_its_prefixed_spelling_are_both_found() -> None:
    """The refusal proofs above are worthless unless the classes also fire.

    A scanner carrying only the natural-person shape reported a document naming
    a company by its tax identity as clean, and the same blindness covered the
    prefixed spelling of every shape. Both are planted here with control
    characters the published algorithm does produce, so a class that quietly
    stopped matching cannot pass as a class that found nothing to report.
    """
    planted = _pdf_bytes_containing(f"empresa {_PLANTED_CIF} intracomunitario {_PLANTED_NIF_IVA}")

    findings = scan_for_residual_identities(planted, {"replacements_applied": []})

    assert {ResidualKind.CIF, ResidualKind.NIF_IVA} <= {finding.kind for finding in findings}, (
        "a legal-entity identity and an ES-prefixed identity must both be blocking findings; "
        f"got kinds {sorted(k.value for k in {f.kind for f in findings})}"
    )


def test_the_gate_and_the_sanitiser_agree_end_to_end() -> None:
    """A document the sanitiser really processed passes its own manifest.

    The live positive control. Three claims in sequence, and each one is load
    bearing:

    1. The gate FLAGS the pre-sanitisation specimen. Without this the rest could
       pass on a document that never carried anything, which is exactly how an
       absence assertion goes quietly vacuous.
    2. The real :func:`sanitize_pdf` processes it -- no stub, no hand-built
       output.
    3. The gate finds the OUTPUT clean when checked against the sanitiser's own
       ``replacements_applied``. This is the seam nothing else covers: every
       other proof here supplies a sidecar written by the test, so a synthetic
       the sanitiser wrote but failed to record would go unnoticed until it
       false-positived on a real operator's file.

    The specimen plants its identity on two different surfaces -- DocInfo and a
    content stream -- because the sanitiser treats them separately and a fix that
    covered only one would still satisfy a single-surface specimen.
    """
    source = _pre_sanitisation_specimen()

    before = scan_for_residual_identities(source, {"replacements_applied": []})
    assert {finding.kind for finding in before} == {ResidualKind.NIF_NIE, ResidualKind.IBAN}, (
        "the pre-sanitisation specimen must be visibly dirty to the gate, or the clean "
        f"result below proves nothing; got kinds {sorted(k.value for k in {f.kind for f in before})}"
    )

    result = sanitize_pdf(source, _pre_sanitisation_token_map())
    sidecar = {"replacements_applied": [row.model_dump() for row in result.replacements_applied]}

    after = scan_for_residual_identities(result.output_bytes, sidecar)
    assert not after, (
        "the residual gate flags genuine sanitiser output when checked against the manifest "
        "the sanitiser itself emitted. Either a real value survived, or a synthetic the "
        "sanitiser wrote is missing from replacements_applied -- both make this gate fire on "
        "correct output, which is how a gate gets silenced.\n"
        + "\n".join(f"  {finding.describe()}" for finding in after)
    )


def test_the_end_to_end_control_depends_on_a_complete_manifest() -> None:
    """Anti-vacuity proof for the control above: drop a row, and it must fire.

    The clean result above could hold for the wrong reason -- if the scan simply
    found nothing identity-shaped in the output, the manifest would be
    irrelevant and the seam would still be uncovered. Removing the NIF row from
    the sanitiser's own manifest must therefore turn the output dirty, which
    proves the output really does carry a checksum-valid synthetic and that the
    manifest really is what accounts for it.
    """
    result = sanitize_pdf(_pre_sanitisation_specimen(), _pre_sanitisation_token_map())
    rows = [row.model_dump() for row in result.replacements_applied]
    without_nif = [row for row in rows if row["synthetic"] != _SYNTHETIC_NIF]
    assert len(without_nif) < len(rows), "the sanitiser must have recorded the NIF replacement"

    findings = scan_for_residual_identities(result.output_bytes, {"replacements_applied": without_nif})

    assert ResidualKind.NIF_NIE in {finding.kind for finding in findings}, (
        "dropping the NIF row from the manifest left the scan clean, so the end-to-end control "
        "above is not actually checking the output against the manifest"
    )


def _pre_sanitisation_specimen() -> bytes:
    """A document deliberately carrying checksum-valid identity, never committed.

    See the module docstring for why this is generated rather than stored. The
    values are the same all-zero planted pair the planted-identity proofs use,
    so a reader meets one vocabulary rather than two.
    """
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=A4, invariant=True)
    # DocInfo: a surface the sanitiser scrubs separately from page content.
    pdf_canvas.setTitle(f"Justificante {_PLANTED_NIF}")
    pdf_canvas.setAuthor(_PLANTED_NAME)
    pdf_canvas.setFont("Helvetica", 10)
    pdf_canvas.drawString(50, 760, f"NIF: {_PLANTED_NIF}")
    pdf_canvas.drawString(50, 740, f"Apellidos y nombre: {_PLANTED_NAME}")
    pdf_canvas.drawString(50, 720, f"Codigo Cuenta Cliente (IBAN): {_PLANTED_IBAN}")
    pdf_canvas.showPage()
    pdf_canvas.save()
    return buffer.getvalue()


def _pre_sanitisation_token_map() -> TokenMap:
    """The operator-supplied rewrite for the specimen above.

    The synthetics are themselves checksum-valid -- a placeholder has to be, or
    it would not round-trip through the parsers that read these documents -- and
    that is precisely why the manifest matters: after sanitisation the output
    still contains identity-shaped, checksum-valid values, and only
    ``replacements_applied`` distinguishes them from a residual.
    """
    return TokenMap(
        nif=(NifReplacement(real=SecretStr(_PLANTED_NIF), synthetic=_SYNTHETIC_NIF, surface_label="taxpayer NIF"),),
        name=(
            NameReplacement(real=SecretStr(_PLANTED_NAME), synthetic=_SYNTHETIC_NAME, surface_label="taxpayer name"),
        ),
        iban=(
            IbanReplacement(
                real=SecretStr(_PLANTED_IBAN), synthetic=_SYNTHETIC_IBAN, surface_label="domiciliacion IBAN"
            ),
        ),
    )


def _pdf_bytes_containing(text: str) -> bytes:
    """Build a one-page PDF whose content stream carries ``text``."""
    return text_pdf_bytes((text,))
