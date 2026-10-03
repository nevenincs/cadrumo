"""Load one filing record and its work unit, both owned by the requesting profile."""

from __future__ import annotations

from uuid import UUID

from ...domain.modelos.filing_record import ModeloRecord
from ...domain.modelos.work_unit import WorkUnit
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .verification_repository_ports import VerificationRepositoryBundle


def _require_filing_unit_coordinate(record: ModeloRecord, unit: WorkUnit, bucket_id: str) -> None:
    """Require the loaded unit's exact profile and filing coordinate before release."""
    if (
        unit.bucket_id != bucket_id
        or unit.work_unit_id != record.work_unit_id
        or unit.modelo != record.modelo
        or unit.filing_year != record.filing_year
        or unit.period != record.period
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def load_profile_filing_record(
    bundle: VerificationRepositoryBundle, *, profile_id: UUID, filing_record_id: str
) -> tuple[ModeloRecord, WorkUnit]:
    """Return the profile's filing record and the exact work unit it was filed for.

    A repository, record or unit outside the profile, or a unit whose coordinates
    differ from the record's, refuses as a profile mismatch before anything is
    returned; a record or unit that does not exist refuses the operation.
    """
    bucket_id = str(profile_id)
    if bundle.filing.bucket_id != bucket_id or bundle.work_unit.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    record = bundle.filing.load().get(filing_record_id)
    if record is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if record.bucket_id != bucket_id or record.filing_record_id != filing_record_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    unit = bundle.work_unit.load().get(record.work_unit_id)
    if unit is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    _require_filing_unit_coordinate(record, unit, bucket_id)
    return record, unit
