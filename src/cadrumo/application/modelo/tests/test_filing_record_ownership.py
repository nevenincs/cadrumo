"""One loader binds a filing record and its work unit to the requesting profile."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from ....core.period import Period
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
)
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..filing_record_ownership import load_profile_filing_record
from ..verification_repository_ports import VerificationRepositoryBundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_REVISION_ID = "a" * 64
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2026, "1T")


def _unit(*, bucket_id: str = str(_PROFILE)) -> WorkUnit:
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id, modelo="303", filing_year=2026, period=_PERIOD, revision_id="test-revision"
        ),
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=_PERIOD,
        revision_id="test-revision",
        name="First-quarter return",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
        current_calculation_revision_id=_REVISION_ID,
    )


def _record(*, bucket_id: str = str(_PROFILE), period: Period = _PERIOD) -> ModeloRecord:
    unit_id = _unit().work_unit_id
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=unit_id, calculation_revision_id=_REVISION_ID, filed_by="gestoria source"
        ),
        work_unit_id=unit_id,
        calculation_revision_id=_REVISION_ID,
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        filed_at=_NOW,
        filed_by="gestoria source",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )


class _Repository:
    def __init__(self, catalogue: object, *, bucket_id: str = str(_PROFILE)) -> None:
        self.bucket_id = bucket_id
        self._catalogue = catalogue

    def load(self) -> object:
        return self._catalogue


def _bundle(
    *,
    record: ModeloRecord | None = None,
    unit: WorkUnit | None = None,
    filing_bucket_id: str = str(_PROFILE),
    work_bucket_id: str = str(_PROFILE),
    records: object | None = None,
    units: object | None = None,
) -> VerificationRepositoryBundle:
    filed = record or _record()
    owned_unit = unit or _unit()
    return cast(
        VerificationRepositoryBundle,
        cast(
            object,
            SimpleNamespace(
                filing=_Repository(
                    ModeloRecordCatalogue(records={filed.filing_record_id: filed}) if records is None else records,
                    bucket_id=filing_bucket_id,
                ),
                work_unit=_Repository(
                    WorkUnitCatalogue(work_units={owned_unit.work_unit_id: owned_unit}) if units is None else units,
                    bucket_id=work_bucket_id,
                ),
            ),
        ),
    )


def test_the_profiles_record_returns_with_the_unit_it_was_filed_for() -> None:
    record, unit = load_profile_filing_record(
        _bundle(), profile_id=_PROFILE, filing_record_id=_record().filing_record_id
    )

    assert record == _record()
    assert unit == _unit()


@pytest.mark.parametrize(
    ("bundle", "reason"),
    [
        (_bundle(filing_bucket_id=str(_OTHER_PROFILE)), AccessDenialCode.PROFILE_MISMATCH),
        (_bundle(work_bucket_id=str(_OTHER_PROFILE)), AccessDenialCode.PROFILE_MISMATCH),
        (_bundle(record=_record(bucket_id=str(_OTHER_PROFILE))), AccessDenialCode.PROFILE_MISMATCH),
        (
            _bundle(units=SimpleNamespace(get=lambda work_unit_id: _unit(bucket_id=str(_OTHER_PROFILE)))),
            AccessDenialCode.PROFILE_MISMATCH,
        ),
        (_bundle(record=_record(period=Period.from_year_and_code(2026, "2T"))), AccessDenialCode.PROFILE_MISMATCH),
        (_bundle(records=ModeloRecordCatalogue(records={})), AccessDenialCode.OPERATION_DENIED),
    ],
    ids=["filing-bucket", "work-bucket", "record-owner", "unit-owner", "record-period", "missing-record"],
)
def test_foreign_or_missing_ownership_is_refused(
    bundle: VerificationRepositoryBundle, reason: AccessDenialCode
) -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        load_profile_filing_record(bundle, profile_id=_PROFILE, filing_record_id=_record().filing_record_id)

    assert refused.value.reason is reason


def test_a_record_without_its_work_unit_is_denied() -> None:
    bundle = _bundle(units=WorkUnitCatalogue(work_units={}))

    with pytest.raises(ProfileAccessRefusedError) as refused:
        load_profile_filing_record(bundle, profile_id=_PROFILE, filing_record_id=_record().filing_record_id)

    assert refused.value.reason is AccessDenialCode.OPERATION_DENIED


def test_a_record_returned_for_another_id_is_a_profile_mismatch() -> None:
    requested = "b" * 64
    bundle = _bundle(records=SimpleNamespace(get=lambda filing_record_id: _record()))

    with pytest.raises(ProfileAccessRefusedError) as refused:
        load_profile_filing_record(bundle, profile_id=_PROFILE, filing_record_id=requested)

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
