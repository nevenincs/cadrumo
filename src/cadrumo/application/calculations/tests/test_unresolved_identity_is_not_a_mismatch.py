"""An unidentifiable receipt and someone else's receipt are different blockers.

contract: ``filing_external_evidence_blockers`` reports
``UNRESOLVED_TAXPAYER_IDENTITY`` when no taxpayer identity is available to check
a justificante against, and ``MISMATCHED_EXTERNAL_EVIDENCE_RECORD`` only when an
identity IS available and disagrees with the stored receipt.

Both once produced the mismatch code, so an operator whose profile simply
carried no NIF was told their filed evidence was mismatched. That points at the
receipt -- a document they cannot change -- instead of at the profile field they
had not filled in. The gate stays fail-closed in both cases: an unidentifiable
receipt still blocks. Only the reason changes, and the reason is the part that
tells the operator what to do.

Driven through the real blocker builder over a real persisted
:class:`Justificante` and a real :class:`ModeloRecord`; nothing is stubbed.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....core import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.filing_record import ExternalEvidence, ExternalEvidenceKind, ModeloRecord, ModeloRecordStatus, derive_filing_record_id
from ....tests.secure_sql import isolated_runtime_profile
from .. import CrossPeriodCleanStateBlocker, filing_external_evidence_blockers
from ._cross_period_clean_state_support import _persist_justificante_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "39039039-0390-4390-8390-390390390391"
_OWNER_NIF = "X1234567L"
_OTHER_NIF = "B12345678"
_CSV = "JUSTIDENTITY1T"
_YEAR = 2025
_PERIOD = "1T"
_CLOCK = datetime(2025, 4, 15, 9, 0, tzinfo=UTC)


def _persist_justificante() -> None:
    """Persist the owner's real receipt through the package's existing seeder."""
    _persist_justificante_metadata(_CSV, modelo="303", period=_PERIOD, filing_year=_YEAR, tax_id=_OWNER_NIF)


def _filing() -> ModeloRecord:
    work_unit_id = hashlib.sha256(f"303:{_YEAR}:{_PERIOD}:{_CSV}".encode()).hexdigest()
    revision_id = hashlib.sha256(f"rev:{_CSV}".encode()).hexdigest()
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            filed_by="identity-blocker-test",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        filed_at=_CLOCK,
        filed_by="identity-blocker-test",
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id=_CSV,
            imported_at=_CLOCK,
        ),
    )


def _blockers_for(tmp_path: Path, taxpayer_tax_id: str | None) -> list[CrossPeriodCleanStateBlocker]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _persist_justificante()
        return filing_external_evidence_blockers(
            _filing(),
            "aeat_sede_justificante",
            JustificanteRepository(),
            taxpayer_tax_id,
        )


def test_the_owner_identity_raises_no_identity_blocker(tmp_path: Path) -> None:
    """POSITIVE CONTROL: the ordinary case is clean on both identity codes."""
    blockers = _blockers_for(tmp_path, _OWNER_NIF)

    assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD not in blockers
    assert CrossPeriodCleanStateBlocker.UNRESOLVED_TAXPAYER_IDENTITY not in blockers


def test_a_different_identity_is_reported_as_a_mismatch(tmp_path: Path) -> None:
    """A receipt belonging to someone else keeps the mismatch code."""
    blockers = _blockers_for(tmp_path, _OTHER_NIF)

    assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers
    assert CrossPeriodCleanStateBlocker.UNRESOLVED_TAXPAYER_IDENTITY not in blockers


@pytest.mark.parametrize("absent", ["", None], ids=["empty", "none"])
def test_an_absent_identity_is_reported_as_unresolved_not_mismatched(tmp_path: Path, absent: str | None) -> None:
    """The fix: absence names the profile gap instead of blaming the receipt."""
    blockers = _blockers_for(tmp_path, absent)

    assert CrossPeriodCleanStateBlocker.UNRESOLVED_TAXPAYER_IDENTITY in blockers
    assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD not in blockers


def test_an_absent_identity_still_blocks(tmp_path: Path) -> None:
    """The gate stays fail-closed: a nicer reason must not become a pass.

    Without this, "stop reporting a mismatch" could be satisfied by dropping the
    check, which would let an unidentifiable receipt satisfy the clean-state
    gate for a filing nobody proved belongs to this taxpayer.
    """
    assert _blockers_for(tmp_path, None), "an unidentifiable receipt must still block"
