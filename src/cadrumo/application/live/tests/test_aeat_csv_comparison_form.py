"""One CSV spelling, one identifier, across the live evidence surfaces.

Three live sites decide whether a receipt is the one a filing record already
points at, and each previously carried its own copy of the AEAT CSV comparison
form. They agreed with the canonical transform character-for-character, so no
test could tell them apart from the authority -- which is precisely why they
survived: a second form only shows itself the day it stops agreeing.

The case variance these assert on is real rather than hypothetical, and the
reason is worth naming, because it is not uniform. ``Justificante.csv`` and
``JustificanteCaptureSnapshot.csv`` both carry the canonical
:data:`~core.identity.AeatCsv` alias, which normalises at the model boundary, so
those two can never present a variant spelling. The values that CAN are the ones
crossing a boundary that only trims: ``ExternalEvidence.reference_id``, and the
CSV recovered out of a cotejo URL. Those are the surfaces exercised below,
because they are the surfaces where two spellings of one identifier can actually
meet.

See Also:
    :class:`~ModeloRecord`
        The filing record whose external evidence these comparisons resolve.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....adapters.inbound.pdf.utils import source_pdf_reference_path
from ....core.period import Period
from ....domain.justificante import Justificante
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from ..filed_observation_persistence import (
    _existing_justificante_evidence_matches,
    _filed_observation_source_metadata,
)
from ..justificante import _existing_capture_evidence_matches_current_csv
from ._filed_capture_history_support import _prior_303_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "39039039-0390-4390-8390-390390390390"
_CLOCK = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)

#: One identifier in three spellings. The canonical form is what AEAT prints and
#: what the cotejo endpoint must receive back; the others are what a trimming-only
#: boundary can hand a comparison.
_CANONICAL_CSV = "LIVECAP130ABCD01"
_LOWERCASE_CSV = "livecap130abcd01"
_PADDED_MIXED_CSV = "  LiveCap130Abcd01  "

#: A genuinely different identifier, used to keep every "matches" assertion from
#: being satisfiable by a comparison that returns True unconditionally.
_OTHER_CSV = "LIVECAP130ZZZZ99"


def _receipt(csv: str) -> Justificante:
    pdf_bytes = f"%PDF-1.4\n% synthetic justificante {csv}\n%%EOF\n".encode()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    return Justificante(
        csv=csv,
        modelo="130",
        period=Period.from_year_and_code(2026, "1T"),
        ejercicio="2026",
        presentation_id=None,
        presented_at=_CLOCK,
        tax_id="X1234567L",
        total_a_ingresar=None,
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
        source_pdf_path=source_pdf_reference_path(digest),
        source_pdf_sha256=digest,
        parsed_at=_CLOCK,
    )


def _filing_pointing_at(reference_id: str, *, kind: ExternalEvidenceKind) -> ModeloRecord:
    work_unit_id = hashlib.sha256(f"130:2026:1T:{reference_id}".encode()).hexdigest()
    revision_id = hashlib.sha256(f"rev:{reference_id}".encode()).hexdigest()
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            filed_by="aeat-live-capture-test",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        filed_at=_CLOCK,
        filed_by="aeat-live-capture-test",
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(kind=kind, reference_id=reference_id, imported_at=_CLOCK),
    )


def test_the_alias_does_not_already_answer_this() -> None:
    """The variant spellings survive to the comparison, so the assertions below have work to do.

    ``ExternalEvidence.reference_id`` trims but does not uppercase. If it ever
    gains the canonical alias the comparisons become trivially equal, and every
    test in this module would keep passing while proving nothing -- so the
    premise is asserted rather than assumed.
    """
    trimmed_variant = _filing_pointing_at(
        _PADDED_MIXED_CSV,
        kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
    ).external_evidence
    assert trimmed_variant is not None
    assert trimmed_variant.reference_id != _CANONICAL_CSV, (
        "the evidence reference now normalises at its own boundary, so these "
        "comparisons no longer meet two spellings of one identifier; retarget "
        "this module at whichever boundary still trims only"
    )


@pytest.mark.parametrize("spelling", [_CANONICAL_CSV, _LOWERCASE_CSV, _PADDED_MIXED_CSV])
def test_filed_history_evidence_matches_a_receipt_however_the_reference_is_spelled(spelling: str) -> None:
    """A justificante-backed reference is the same evidence in any spelling."""
    filing = _filing_pointing_at(spelling, kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF)

    assert _existing_justificante_evidence_matches(filing, _receipt(_CANONICAL_CSV)) is True


def test_filed_history_evidence_still_refuses_a_different_receipt() -> None:
    """The discriminating half: normalising must not collapse two identifiers into one."""
    filing = _filing_pointing_at(_OTHER_CSV, kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF)

    assert _existing_justificante_evidence_matches(filing, _receipt(_CANONICAL_CSV)) is False


@pytest.mark.parametrize("spelling", [_CANONICAL_CSV, _LOWERCASE_CSV, _PADDED_MIXED_CSV])
def test_capture_evidence_matches_the_current_csv_however_it_is_spelled(spelling: str) -> None:
    """The capture stamping path reads the same identity as the filed-history path."""
    filing = _filing_pointing_at(spelling, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

    assert _existing_capture_evidence_matches_current_csv(filing, _CANONICAL_CSV) is True


def test_capture_evidence_still_refuses_a_different_csv() -> None:
    """The discriminating half for the capture path."""
    filing = _filing_pointing_at(_OTHER_CSV, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

    assert _existing_capture_evidence_matches_current_csv(filing, _CANONICAL_CSV) is False


def test_persisted_register_metadata_carries_one_entry_per_identifier() -> None:
    """The writing side of the key the cross-period gate reads back.

    Deduplicating on a trim alone let two spellings of one CSV survive as two
    entries, which then reached persistence as a comma-joined pair and read back
    as two references for one receipt. This is the same second-key defect as the
    comparison sites, on the side that creates the value rather than the side
    that compares it.
    """
    observation = _prior_303_observation(
        pending_compensation=Decimal("0.00"),
        result=Decimal("-1.00"),
    )

    metadata = _filed_observation_source_metadata(
        observation,
        justificante_csvs=(_PADDED_MIXED_CSV, _LOWERCASE_CSV, _CANONICAL_CSV),
    )

    assert metadata["aeat_justificante_csv"] == _CANONICAL_CSV
    assert "aeat_justificante_csvs" not in metadata, (
        "three spellings of one CSV were persisted as more than one reference"
    )


def test_persisted_register_metadata_still_carries_two_genuine_references() -> None:
    """The discriminating half: a real second receipt must survive the deduplication."""
    observation = _prior_303_observation(
        pending_compensation=Decimal("0.00"),
        result=Decimal("-1.00"),
    )

    metadata = _filed_observation_source_metadata(
        observation,
        justificante_csvs=(_LOWERCASE_CSV, _OTHER_CSV),
    )

    assert "aeat_justificante_csv" not in metadata
    assert metadata["aeat_justificante_csvs"] == f"{_CANONICAL_CSV},{_OTHER_CSV}"
