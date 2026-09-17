"""Chain-entry invariants of the filing-record catalogue."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from cadrumo.core.period import Period
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    AeatRegisterRef,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "30330300-0000-4000-8000-000000000900"
_PERIOD = Period.from_year_and_code(2026, "1T")
_T1 = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_T2 = datetime(2026, 4, 12, 9, 0, tzinfo=UTC)
_T3 = datetime(2026, 4, 14, 9, 0, tzinfo=UTC)
_WORK_UNIT_ID = "a" * 64


def _record(
    revision_digit: str,
    *,
    origin: FilingOrigin,
    confirmation: AeatConfirmationState,
    filed_at: datetime,
    kind: FilingDeclarationKind = FilingDeclarationKind.ORIGINAL,
    **fields: object,
) -> ModeloRecord:
    revision_id = revision_digit * 64
    evidence = None
    if confirmation is AeatConfirmationState.CONFIRMADA:
        evidence = ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            reference_id=f"EXP-{revision_digit}",
            imported_at=filed_at,
        )
    payload: dict[str, object] = {
        "filing_record_id": derive_filing_record_id(
            work_unit_id=_WORK_UNIT_ID,
            calculation_revision_id=revision_id,
            filed_by="operator-A",
        ),
        "work_unit_id": _WORK_UNIT_ID,
        "calculation_revision_id": revision_id,
        "bucket_id": _BUCKET_ID,
        "modelo": ModeloCode("130"),
        "filing_year": 2026,
        "period": _PERIOD,
        "filed_at": filed_at,
        "filed_by": "operator-A",
        "origin": origin,
        "confirmation": confirmation,
        "declaration_kind": kind,
        "external_evidence": evidence,
    }
    payload.update(fields)
    return ModeloRecord.model_validate(payload)


def _superseded(record: ModeloRecord, successor: ModeloRecord, *, at: datetime, **fields: object) -> ModeloRecord:
    return record.model_copy(
        update={
            "status": ModeloRecordStatus.SUPERSEDIDO,
            "superseded_at": at,
            "superseded_by_filing_record_id": successor.filing_record_id,
            **fields,
        },
    )


def test_aeat_origin_requires_confirmation() -> None:
    with pytest.raises(ValidationError, match="AEAT-origin filing record must be confirmed"):
        _record("1", origin=FilingOrigin.AEAT, confirmation=AeatConfirmationState.PENDIENTE, filed_at=_T1)


def test_pending_record_refuses_an_aeat_register_reference() -> None:
    with pytest.raises(ValidationError, match="pendiente filing record must not carry an AEAT register reference"):
        _record(
            "1",
            origin=FilingOrigin.LOCAL,
            confirmation=AeatConfirmationState.PENDIENTE,
            filed_at=_T1,
            aeat_register=AeatRegisterRef(expediente_id="EXP-1"),
        )


@pytest.mark.parametrize("retired", [AeatConfirmationState.DESCARTADA, AeatConfirmationState.DISCREPANTE])
def test_retired_record_cannot_be_in_force(retired: AeatConfirmationState) -> None:
    with pytest.raises(ValidationError, match=f"{retired.value} filing record cannot be in force"):
        _record("1", origin=FilingOrigin.LOCAL, confirmation=retired, filed_at=_T1)


def test_aeat_accepted_is_derived_from_confirmation() -> None:
    pending = _record("1", origin=FilingOrigin.LOCAL, confirmation=AeatConfirmationState.PENDIENTE, filed_at=_T1)
    confirmed = _record("2", origin=FilingOrigin.LOCAL, confirmation=AeatConfirmationState.CONFIRMADA, filed_at=_T1)
    assert (pending.aeat_accepted, confirmed.aeat_accepted) == (False, True)
    assert "aeat_accepted" not in ModeloRecord.model_fields


def test_latest_confirmed_differs_from_current_while_a_correction_is_pending() -> None:
    confirmed = _record("1", origin=FilingOrigin.AEAT, confirmation=AeatConfirmationState.CONFIRMADA, filed_at=_T1)
    pending = _record(
        "2",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        filed_at=_T2,
        kind=FilingDeclarationKind.COMPLEMENTARIA,
        amends_filing_record_id=confirmed.filing_record_id,
    )
    catalogue = ModeloRecordCatalogue(
        records={
            confirmed.filing_record_id: _superseded(confirmed, pending, at=_T2),
            pending.filing_record_id: pending,
        },
    )
    assert catalogue.current_for(bucket_id=_BUCKET_ID, modelo="130", filing_year=2026, period=_PERIOD) == pending
    latest = catalogue.latest_confirmed_for(bucket_id=_BUCKET_ID, modelo="130", filing_year=2026, period=_PERIOD)
    assert latest is not None and latest.filing_record_id == confirmed.filing_record_id


def test_empty_chain_has_no_latest_confirmed_entry() -> None:
    assert (
        ModeloRecordCatalogue().latest_confirmed_for(
            bucket_id=_BUCKET_ID, modelo="130", filing_year=2026, period=_PERIOD
        )
        is None
    )


def test_discarded_correction_keeps_its_link_while_the_baseline_moves_on() -> None:
    confirmed = _record("1", origin=FilingOrigin.AEAT, confirmation=AeatConfirmationState.CONFIRMADA, filed_at=_T1)
    discarded = _record(
        "2",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        filed_at=_T2,
        kind=FilingDeclarationKind.COMPLEMENTARIA,
        amends_filing_record_id=confirmed.filing_record_id,
    )
    replacement = _record(
        "3",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        filed_at=_T3,
        kind=FilingDeclarationKind.COMPLEMENTARIA,
        amends_filing_record_id=confirmed.filing_record_id,
    )
    records = {
        confirmed.filing_record_id: _superseded(confirmed, replacement, at=_T2),
        discarded.filing_record_id: _superseded(
            discarded,
            replacement,
            at=_T3,
            confirmation=AeatConfirmationState.DESCARTADA,
        ),
        replacement.filing_record_id: replacement,
    }

    assert len(ModeloRecordCatalogue(records=records)) == 3

    still_pending = records | {
        discarded.filing_record_id: _superseded(discarded, replacement, at=_T3),
    }
    with pytest.raises(ValidationError, match="one-sided amendment link"):
        ModeloRecordCatalogue(records=still_pending)
