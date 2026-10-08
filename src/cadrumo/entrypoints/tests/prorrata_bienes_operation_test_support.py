"""Real profile-store fixtures for prorrata and capital-goods operation conformance."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from ...application.bienes_inversion.declare_command import (
    BienInversionDeclarationCommand,
    build_bien_inversion_record,
)
from ...application.bienes_inversion.ports import BienesInversionIvaRegisterRepositoryFactory
from ...application.bienes_inversion.registered_contracts import (
    BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID,
)
from ...application.bienes_inversion.registered_requests import (
    BienesInversionDeclareRequest,
    BienesInversionListRequest,
)
from ...application.bienes_inversion.service import BienesInversionRegisterService
from ...core.operations import OperationEffect
from ...domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts


@dataclass(frozen=True, slots=True)
class BienesInversionOperationConformanceCase:
    """One correctly typed capital-goods operation request and its expected effect."""

    request: BaseModel
    expected_effect: OperationEffect
    expected_record: BienInversionIvaRecord


def bienes_inversion_conformance_record(
    definition_id: str,
    *,
    operation: PinnedAuthorityOperation,
) -> BienInversionIvaRecord:
    """Build the exact complete canonical declaration used by each conformance case."""
    if definition_id not in {
        BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID,
        BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    }:
        raise ValueError(f"unsupported capital-goods conformance definition: {definition_id}")
    identifier = (
        "bienes-conformance-list"
        if definition_id == BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID
        else "bienes-conformance-declare"
    )
    with validating_governed_facts(operation):
        return build_bien_inversion_record(
            BienInversionDeclarationCommand(
                identifier=identifier,
                description="Conformance capital good",
                acquisition_year=2025,
                acquisition_ledger_id=f"{identifier}-ledger",
                cuota_soportada=Decimal("2100.00"),
                prorrata_inicial_pct=Decimal("60"),
                kind="mueble",
                art108_elegible=True,
                prorrata_sector_id="sector-conformance",
                disposal_year=2026,
                disposal_regime="sujeta_no_exenta",
            ),
        )


def prepare_bienes_inversion_operation_conformance_case(
    definition_id: str,
    profile_id: UUID,
    *,
    repository_factory: BienesInversionIvaRegisterRepositoryFactory,
    operation: PinnedAuthorityOperation,
) -> BienesInversionOperationConformanceCase:
    """Seed or request a canonical record through the encrypted profile repository."""
    bucket_id = str(profile_id)
    service = BienesInversionRegisterService(repository=repository_factory(bucket_id=bucket_id))

    if definition_id == BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID:
        expected_record = bienes_inversion_conformance_record(definition_id, operation=operation)
        service.declare(expected_record)
        return BienesInversionOperationConformanceCase(
            request=BienesInversionListRequest(profile_id=profile_id),
            expected_effect=OperationEffect.NONE,
            expected_record=expected_record,
        )

    if definition_id == BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID:
        expected_record = bienes_inversion_conformance_record(definition_id, operation=operation)
        return BienesInversionOperationConformanceCase(
            request=BienesInversionDeclareRequest(
                profile_id=profile_id,
                identifier=expected_record.identifier,
                description="Conformance capital good",
                acquisition_year=2025,
                acquisition_ledger_id=expected_record.acquisition_ledger_id,
                cuota_soportada={"decimal": "2100.00"},
                prorrata_inicial_pct={"decimal": "60"},
                kind="mueble",
                art108_elegible=True,
                prorrata_sector_id="sector-conformance",
                disposal_year=2026,
                disposal_regime="sujeta_no_exenta",
            ),
            expected_effect=OperationEffect.UPDATED,
            expected_record=expected_record,
        )

    raise ValueError(f"unsupported capital-goods conformance definition: {definition_id}")


def read_bienes_inversion_operation_conformance_register(
    profile_id: UUID,
    *,
    repository_factory: BienesInversionIvaRegisterRepositoryFactory,
) -> BienesInversionIvaRegister:
    """Read back the complete register from the exact profile's encrypted repository."""
    service = BienesInversionRegisterService(repository=repository_factory(bucket_id=str(profile_id)))
    return service.list_all()


__all__ = [
    "BienesInversionOperationConformanceCase",
    "bienes_inversion_conformance_record",
    "prepare_bienes_inversion_operation_conformance_case",
    "read_bienes_inversion_operation_conformance_register",
]
