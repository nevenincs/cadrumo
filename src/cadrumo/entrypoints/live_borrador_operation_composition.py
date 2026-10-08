"""Exact-profile encrypted snapshots and canonical in-memory PDF parsing."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ..adapters.inbound.borrador.parser import parse_borrador
from ..adapters.inbound.borrador.schema import BorradorParseMode
from ..application.live.borrador_100_operation_ports import (
    Borrador100ImportObservation,
    Borrador100OperationPorts,
    Borrador100PrintedValue,
)
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.calculations.registry.schema_extraction import ExtractionProfileDefinition
from .adapter_composition import build_borrador_100_snapshot_repository


class _CanonicalBorradorParser:
    """Translate the existing parser's facts through the application port."""

    def parse(
        self,
        pdf_bytes: bytes,
        *,
        filing_year: int,
        extraction_profile: ExtractionProfileDefinition,
    ) -> Borrador100ImportObservation:
        observation = parse_borrador(
            pdf_bytes,
            año_override=filing_year,
            extraction_profile=extraction_profile,
            parse_mode=BorradorParseMode.REGISTRY_PROFILE,
        )
        return Borrador100ImportObservation(
            ejercicio=observation.ejercicio,
            extraction_profile_id=observation.registry_extraction_profile_id,
            extraction_coverage=observation.extraction_coverage,
            artefact_kind=observation.artefact_kind.value,
            source_pdf_sha256=observation.source_pdf_sha256,
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
    )
