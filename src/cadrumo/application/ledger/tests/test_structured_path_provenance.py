"""An exactly-read value must reach the operator with an origin, like every other.

The structured projection built no provenance envelopes for any field -- not the
tax identifier, not the regime legend, not the postal codes. So a value read
EXACTLY from a machine-readable record, with no model anywhere near it and prompt
injection categorically impossible, arrived at the operator with no origin at
all, while a value a heuristic recovered from a PDF text layer arrived with a
full envelope.

That is a grounding violation rather than a cosmetic gap: provenance is required
to travel every domain boundary to the operator-facing surface. And it is the
same inversion this path keeps producing -- the most defensible values in the
system getting the least apparatus.

Every case drives the REAL path: bytes through the real encrypted evidence
service, read back through
:func:`~application.ledger.evidence_draft.extract_invoice_draft_from_evidence`.

See Also:
    :class:`~core.FieldOrigin`
        The origin axis, whose ``EXACT_STRUCTURED`` member this path now stamps.
    :class:`~core.FieldGroundingOutcome`
        The outcome axis, resolved by the same checker the text lane uses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....core.config import Settings
from ..evidence_draft import InvoiceDraft, extract_invoice_draft_from_evidence
from ..grounding_anchor import normalise_for_anchor_search
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects"]

_CORPUS = Path(__file__).parent / "_evidence_corpus"
_FACTURAE = "facturae_32_series_and_parties_invoice.xml"

# Fields the specimen states as text, so their verbatim form in the record IS
# the value. Amounts are excluded here deliberately: the parser types them on
# the way through, so their canonical form may differ from the printed one, and
# that case is asserted separately rather than assumed away.
_TEXT_FIELDS = ("supplier_tax_id", "supplier_name", "supplier_postal_code", "invoice_number")


def _draft(xml: str, *, settings: Settings, objects: SecureObjectRepository, tmp_path: Path) -> InvoiceDraft:
    staged = tmp_path / "document.xml"
    staged.write_text(xml, encoding="utf-8")
    evidence_id = _make_svc(settings, objects).add(bucket_id=_BUCKET_ID, source_path=staged).record.evidence_id
    return extract_invoice_draft_from_evidence(bucket_id=_BUCKET_ID, evidence_id=evidence_id, settings=settings)


def _corpus_xml() -> str:
    return (_CORPUS / _FACTURAE).read_text(encoding="utf-8")


def test_the_structured_path_stamps_an_origin_on_every_recovered_field(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """No value recovered from the record reaches the operator without an origin.

    Asserted over the fields the draft actually carries rather than a fixed list,
    so a field added to the structured projection later joins this gate when it
    is declared rather than when someone remembers.
    """
    draft = _draft(_corpus_xml(), settings=isolated_settings, objects=secure_objects, tmp_path=tmp_path)

    enveloped = {envelope.field for envelope in draft.provenance}
    assert enveloped, "the structured path produced no provenance at all"
    for field in _TEXT_FIELDS:
        assert getattr(draft, field) is not None, f"{field} was not recovered, so the case proves nothing"
        assert field in enveloped, f"{field} reached the operator with no origin"


def test_every_structured_envelope_declares_the_exact_structured_origin(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The origin is the one the taxonomy already reserves for this reading.

    ``EXACT_STRUCTURED`` exists precisely for a value read from the document's own
    machine-readable record, and no production site constructed it before this.
    Stamping anything else -- ``TEXT_LAYER`` in particular -- would launder an
    exact read into a heuristic one, which is the distinction the whole origin
    axis exists to preserve.
    """
    draft = _draft(_corpus_xml(), settings=isolated_settings, objects=secure_objects, tmp_path=tmp_path)

    origins = {envelope.origin for envelope in draft.provenance}
    assert origins == {FieldOrigin.EXACT_STRUCTURED}


def test_an_anchored_structured_value_really_occurs_in_the_document(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """An ANCHORED stamp is a check that ran, never a claim the reader asserted.

    The invariant that makes the whole envelope worth reading. A path that
    hand-set ANCHORED would produce exactly the same payload shape as one that
    ran the check, so the payload alone cannot tell them apart -- this looks past
    it, and confirms every anchor a stamp vouches for is genuinely in the source
    bytes.
    """
    xml = _corpus_xml()
    haystack = normalise_for_anchor_search(xml)
    draft = _draft(xml, settings=isolated_settings, objects=secure_objects, tmp_path=tmp_path)

    anchored = [e for e in draft.provenance if e.grounding is FieldGroundingOutcome.ANCHORED]
    assert anchored, "no field anchored, so the case cannot discriminate"
    for envelope in anchored:
        assert envelope.anchor is not None
        assert normalise_for_anchor_search(envelope.anchor) in haystack


def test_the_anchor_is_the_printed_form_and_never_the_element_path(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """An element path is a location, not evidence, and must not sit in the anchor.

    ``anchor`` means the verbatim form the value was read from. A schema path
    like ``AddressInSpain/PostCode`` says where the value lives, which is useful
    and true, but a downstream consumer reading the anchor treats it as the form
    a human would see -- so putting a path there would let a schema location be
    read as evidence about the document's face. The path belongs in the note.
    """
    draft = _draft(_corpus_xml(), settings=isolated_settings, objects=secure_objects, tmp_path=tmp_path)

    by_field = {envelope.field: envelope for envelope in draft.provenance}
    postal = by_field["supplier_postal_code"]
    assert postal.anchor == draft.supplier_postal_code
    assert postal.anchor is not None
    assert "/" not in postal.anchor
    # The location is still recorded, just not where evidence goes.
    assert "PostCode" in postal.note


def test_an_assembled_value_is_not_vouched_for_as_verbatim(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """A value the reader BUILT cannot claim to have been read verbatim.

    The discriminating case, and it was found in the bundled corpus rather than
    manufactured. Facturae states a natural person's name across three elements,
    and the reader joins them into the single display name the document means --
    so the assembled string appears nowhere in the record, and the check refuses
    to vouch for it. That is the mechanism working, not a defect in it: the
    joined name is the right value to carry and the wrong thing to call verbatim.

    Without this case the anchor check could be satisfied on every field of the
    corpus, and a check that never fails is indistinguishable from one that is
    hardcoded to pass.
    """
    draft = _draft(_corpus_xml(), settings=isolated_settings, objects=secure_objects, tmp_path=tmp_path)

    by_field = {envelope.field: envelope for envelope in draft.provenance}
    supplier = by_field["supplier_name"]

    assert draft.supplier_name is not None
    assert supplier.grounding is FieldGroundingOutcome.UNANCHORED
    assert supplier.anchor is None
    # The value still reaches the operator; only the claim about it is withheld.
    assert supplier.origin is FieldOrigin.EXACT_STRUCTURED
