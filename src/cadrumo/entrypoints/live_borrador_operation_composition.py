"""Exact-profile encrypted snapshots and canonical in-memory PDF parsing."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..adapters.inbound.borrador.parser import parse_borrador
from ..adapters.inbound.borrador.schema import BorradorParseMode
from ..application.live.borrador_100_operation_ports import (
    Borrador100ImportObservation,
    Borrador100OperationPorts,
    Borrador100PrintedValue,
)
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.user_profile.profile_record_repository import ProfileRecordRepository
from ..application.user_profile.projections import record_to_path_values
from ..application.workbench_generation_calendar import declared_tax_id
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.calculations.registry.schema_extraction import ExtractionProfileDefinition
from ..domain.calculations.registry.schema_references import TemporalSupportEnvelope
from .adapter_composition_ports import build_borrador_100_snapshot_repository


class _CanonicalBorradorParser:
    """Translate the existing parser's facts through the application port."""

    def parse(
        self,
        pdf_bytes: bytes,
        *,
        filing_year: int,
        supported_filing_years: TemporalSupportEnvelope,
        extraction_profile: ExtractionProfileDefinition,
    ) -> Borrador100ImportObservation:
        observation = parse_borrador(
            pdf_bytes,
            filing_year=filing_year,
            supported_filing_years=supported_filing_years,
            extraction_profile=extraction_profile,
            parse_mode=BorradorParseMode.REGISTRY_PROFILE,
        )
        return Borrador100ImportObservation(
            ejercicio=observation.ejercicio,
            extraction_profile_id=observation.registry_extraction_profile_id,
            extraction_coverage=observation.extraction_coverage,
            artefact_kind=observation.artefact_kind.value,
            source_pdf_sha256=observation.source_pdf_sha256,
            tax_id=observation.tax_id,
            values=tuple(
                Borrador100PrintedValue(
                    casilla_id=row.casilla_id,
                    value=(
                        row.printed_value
                        if row.printed_value is None or isinstance(row.printed_value, Decimal)
                        else str(row.printed_value)
                    ),
                )
                for row in observation.values
            ),
            warnings=observation.warnings,
        )


def build_borrador_100_operation_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> Borrador100OperationPorts:
    """Compose local capabilities only inside the admitted profile worker."""
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return Borrador100OperationPorts(
        profile_id=profile_id,
        operation=operation,
        repository=build_borrador_100_snapshot_repository(bucket_id=str(profile_id)),
        parser=_CanonicalBorradorParser(),
        profile_tax_id=lambda: _profile_tax_id(profile_id, operation),
    )


def _profile_tax_id(profile_id: UUID, operation: PinnedAuthorityOperation) -> str | None:
    record = ProfileRecordRepository.for_current_session(
        profile_id, profile_decode_context=operation.profile_decode_context()
    ).load(profile_id)
    return declared_tax_id(record_to_path_values(record))
