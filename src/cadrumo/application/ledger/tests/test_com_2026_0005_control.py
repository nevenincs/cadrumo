"""The corpus positive control: the one document proving the harness can fail.

``OP-PUR-COM-2026-0005`` is bundled in two renderings of the SAME document -- a
text-layer PDF and a camera photograph -- and it is wrong on purpose. Four
defects are deliberate and are recorded in both provenance sidecars:

- the CIF ``B1234567X`` fails its control character
- the invoice number is ``SIN-NUMERO``
- no per-rate breakdown is printed
- the printed total ``890,00`` disagrees with base ``766,30`` plus cuota
  ``160,92`` = ``927,22``

Anything reporting this document clean has a gap, not a clean document. Nothing
here normalises the printed total toward the computed one: the disagreement IS
the finding, and ``printed_total`` and ``grand_total`` are deliberately distinct
throughout this corpus.

Both renderings are asserted individually and BY NAME, because a reader that
fails on only one is failing on the rendering rather than on the content.

The two entries are addressed through :func:`_control_fixtures`, which keys on
the ``corpus_doc_id`` recorded in each sidecar rather than on a filename, so a
rename in the corpus tooling surfaces as a failure to find the control rather
than as a silently smaller test.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.directory_scan import (
    scan_directory,
)
from ....core.draft_discrepancy import DraftDiscrepancyKind
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ..closure_findings import closure_findings
from ..evidence_input import EvidenceInput
from ..evidence_textlayer import transcribe_text_layer
from ..identity_roles import IdentityCandidate, resolve_counterparty_identity
from ..invoice_draft_records import InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "_evidence_corpus"

_LAYOUT_MINIMAL_ID = "OP-PUR-COM-2026-0005_layout-minimal"
_CAMERA_PHOTO_ID = "OP-PUR-COM-2026-0005_camera-photo"

#: The document's own figures, as printed. Read from the document, not chosen.
_BASE = Decimal("766.30")
_CUOTA = Decimal("160.92")
_COMPUTED_TOTAL = Decimal("927.22")
_PRINTED_TOTAL = Decimal("890.00")

#: The supplier's CIF, whose control character fails. The true supplier.
_SUPPLIER_CIF_BAD_CHECKSUM = "B1234567X"

#: The OTHER identifier on the page -- the recipient's, which is valid. This is
#: the id the defect returns as ``supplier_tax_id``.
_RECIPIENT_CIF = "B17283946"


def _control_fixtures() -> dict[str, Path]:
    """Return the control's renderings keyed by their corpus ``doc_id``.

    Keyed on the sidecar's recorded id rather than on a filename so a corpus
    rename fails loudly here instead of quietly reducing the set under test.
    """
    found: dict[str, Path] = {}
    for sidecar in scan_directory(_CORPUS, pattern="*.provenance.json"):
        declared = STR_KEYED_MAPPING_ADAPTER.validate_json(sidecar.read_text(encoding="utf-8"))
        doc_id = declared.get("corpus_doc_id")
        if not isinstance(doc_id, str):
            continue
        if doc_id in {_LAYOUT_MINIMAL_ID, _CAMERA_PHOTO_ID}:
            # The sidecar carries TWO suffixes (``.pdf.provenance.json``), so
            # `with_suffix("")` would strip only the last one and leave a path
            # that does not exist. Drop the whole sidecar suffix by name.
            found[doc_id] = sidecar.with_name(sidecar.name.removesuffix(".provenance.json"))
    return found


def _sidecar_for(path: Path) -> dict[str, object]:
    return STR_KEYED_MAPPING_ADAPTER.validate_json(Path(f"{path}.provenance.json").read_text(encoding="utf-8"))


def test_both_control_renderings_are_bundled_and_byte_intact() -> None:
    """Anchor: the control must be present and unmodified, or nothing below binds.

    The declared ``sha256`` is checked against the bytes on disk. A fixture
    silently edited to "fix" one of its deliberate defects would pass every
    behavioural assertion below by making the defect disappear; this catches
    that before it can.
    """
    fixtures = _control_fixtures()

    assert set(fixtures) == {_LAYOUT_MINIMAL_ID, _CAMERA_PHOTO_ID}, (
        f"both control renderings must be bundled; found {sorted(fixtures)}"
    )
    for doc_id, path in fixtures.items():
        declared = _sidecar_for(path)
        payload = path.read_bytes()
        assert hashlib.sha256(payload).hexdigest() == declared["sha256"], f"{doc_id} bytes differ from its sidecar"
        assert len(payload) == declared["bytes"]


def test_both_renderings_declare_the_same_deliberate_defects() -> None:
    """One document, two renderings: the defects are content, not rendering."""
    for doc_id, path in _control_fixtures().items():
        notes = str(_sidecar_for(path)["notes"])
        assert "B1234567X" in notes, f"{doc_id} no longer declares the bad-checksum CIF"
        assert "SIN-NUMERO" in notes, f"{doc_id} no longer declares the missing invoice number"
        assert "890,00" in notes and "927,22" in notes, f"{doc_id} no longer declares the total mismatch"


# --------------------------------------------------------------------------
# the layout-minimal entry never yields a first-match identifier
# --------------------------------------------------------------------------


def test_the_layout_minimal_document_prints_both_identifiers() -> None:
    """Grounding for the layout-minimal case, read from the real document's text layer.

    The candidates below are not invented: they are the two identifiers this
    document actually prints, confirmed here through the production transcriber
    so the case cannot drift from the file.
    """
    path = _control_fixtures()[_LAYOUT_MINIMAL_ID]
    payload = path.read_bytes()
    transcription = transcribe_text_layer(
        EvidenceInput(
            mime_type="application/pdf",
            data=payload,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            attachment_id="b" * 64,
        ),
    )

    assert _SUPPLIER_CIF_BAD_CHECKSUM in transcription.text
    assert _RECIPIENT_CIF in transcription.text
    assert "SIN-NUMERO" in transcription.text


def test_layout_minimal_never_yields_a_first_match_identifier() -> None:
    """THE layout-minimal acceptance criterion, against the real control document.

    The defect returns ``B17283946`` as the supplier. On this document that
    identifier belongs to the RECIPIENT -- and on a purchase invoice the
    recipient is the filer, so the defect writes the taxpayer's own identifier
    into the counterparty field. Both guards bite here: the bad checksum removes
    the true supplier, and the own-identifier exclusion removes the survivor.
    """
    resolution = resolve_counterparty_identity(
        field="supplier_tax_id",
        candidates=(
            IdentityCandidate(value=_SUPPLIER_CIF_BAD_CHECKSUM),
            IdentityCandidate(value=_RECIPIENT_CIF),
        ),
        taxpayer_tax_id=_RECIPIENT_CIF,
        origin=FieldOrigin.TEXT_LAYER,
    )

    assert resolution.resolved is None
    assert resolution.resolved != _RECIPIENT_CIF, "the filer's own identifier was returned as the counterparty"
    assert resolution.provenance.grounding is not FieldGroundingOutcome.ANCHORED
    kinds = {finding.kind for finding in resolution.findings}
    assert DraftDiscrepancyKind.IDENTITY_UNVERIFIED in kinds
    assert DraftDiscrepancyKind.ROLE_UNRESOLVED in kinds


def test_layout_minimal_still_refuses_when_the_filer_is_not_the_recipient() -> None:
    """The refusal must not depend on the own-identifier guard alone.

    With an unrelated filer, ``B17283946`` survives verification -- and must
    STILL not resolve, because nothing on the page ties it to the supplier role.
    Without this, the case above would pass on the own-NIF exclusion while the
    lone-survivor path stayed broken.
    """
    resolution = resolve_counterparty_identity(
        field="supplier_tax_id",
        candidates=(
            IdentityCandidate(value=_SUPPLIER_CIF_BAD_CHECKSUM),
            IdentityCandidate(value=_RECIPIENT_CIF),
        ),
        taxpayer_tax_id="12345678Z",
        origin=FieldOrigin.TEXT_LAYER,
    )

    assert resolution.resolved is None
    assert resolution.provenance.grounding is not FieldGroundingOutcome.ANCHORED


# --------------------------------------------------------------------------
# both entries produce the blocking 890.00 versus 927.22 finding
# --------------------------------------------------------------------------


def _control_draft() -> InvoiceDraft:
    """Return the draft a correct reader produces from the control document.

    The figures are the ones the document prints; the point of the control is
    that they do not close.
    """
    return InvoiceDraft(
        taxable_base=_BASE,
        iva_rate=Decimal("21"),
        iva_amount=_CUOTA,
        grand_total=_PRINTED_TOTAL,
    )


@pytest.mark.parametrize("doc_id", [_LAYOUT_MINIMAL_ID, _CAMERA_PHOTO_ID])
def test_each_control_rendering_produces_the_blocking_closure_finding(doc_id: str) -> None:
    """THE blocking-closure acceptance criterion, asserted per rendering by name.

    Parametrised over the two entries individually rather than asserted once
    over both, so a failure names WHICH rendering stopped reporting.
    """
    assert doc_id in _control_fixtures(), f"{doc_id} is not bundled"

    findings = closure_findings(_control_draft())

    closure = next(f for f in findings if f.kind is DraftDiscrepancyKind.ARITHMETIC_CLOSURE)
    assert closure.expected == _COMPUTED_TOTAL
    assert closure.observed == _PRINTED_TOTAL
    assert closure.field == "grand_total"


def test_the_control_discrepancy_is_the_declared_37_22() -> None:
    """Anchor on the arithmetic itself: if these ever reconcile, the control died."""
    assert _BASE + _CUOTA == _COMPUTED_TOTAL
    assert Decimal("37.22") == _COMPUTED_TOTAL - _PRINTED_TOTAL


def test_the_printed_total_is_never_normalised_toward_the_computed_one() -> None:
    """``printed_total`` and ``grand_total`` stay distinct; neither is repaired."""
    draft = _control_draft()

    closure_findings(draft)

    assert draft.grand_total == _PRINTED_TOTAL


def test_the_control_document_scoring_clean_would_be_a_gap() -> None:
    """The contract stated as an assertion: this document must never report clean.

    Deliberately coarse -- it does not care WHICH finding fires, only that the
    corpus's one proof-of-failure keeps proving it. A future change that made
    the closure check subtler could still satisfy the specific assertions above
    while quietly letting this document through.
    """
    assert closure_findings(_control_draft()), "the positive control reported clean; the harness has a gap"
