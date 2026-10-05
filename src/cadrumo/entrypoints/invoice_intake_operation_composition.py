"""Canonical encrypted catalogue intake composition for an exact profile worker."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from uuid import UUID

from ..adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
from ..application.invoices.catalogue_creation_ports import CatalogueCreationPorts, CatalogueInvoiceRateProviderPort
from ..application.invoices.catalogue_intake_operation_ports import (
    InvoiceIntakeCommit,
    InvoiceIntakePorts,
    InvoiceIntakeProviderAdmission,
)
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..core.errors.hierarchy import CadrumoError
from ..core.field_role import FieldRole
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.currency.models import EurRateLookup


class _AdmittedRateProvider:
    """Delegate canonical FX lookup after admission, with no lock over network."""

    def __init__(self, provider: CatalogueInvoiceRateProviderPort, admit: InvoiceIntakeProviderAdmission) -> None:
        self._provider = provider
        self._admit = admit

    @property
    def rate_source_id(self) -> str:
        return self._provider.rate_source_id

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        self._admit()
        return self._provider.lookup_eur_rate(currency, rate_date)


def build_invoice_intake_ports(
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    commit: InvoiceIntakeCommit,
    admit_provider: InvoiceIntakeProviderAdmission,
) -> InvoiceIntakePorts:
    """Bind the existing writer, FX algorithm and semantic column mapping lane."""
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    # Provider construction can discover or refresh credentials. The admission
    # completes before constructing the canonical provider or contacting it.
    def creation() -> CatalogueCreationPorts:
        admit_provider()
        ports = build_catalogue_creation_ports(bucket_id=str(profile_id), commit=commit)
        return replace(ports, rate_provider=_AdmittedRateProvider(ports.rate_provider, admit_provider))

    reasons: list[str] = []

    def mapper(headers: Sequence[str]) -> Sequence[FieldRole] | None:
        admit_provider()
        try:
            from ..adapters.outbound.llm.column_role_mapping import map_column_roles
        except ImportError:
            return None
        try:
            proposal = map_column_roles(headers)
        except CadrumoError:
            return None
        reasons.extend(
            f"column {item.column_index} {item.header!r}: proposed role {item.proposed_role!r} is not a permitted role"
            for item in proposal.rejected_role_proposals
        )
        reasons.extend(
            f"column {item.column_index} {item.header!r}: role {item.role.value!r} was already taken by column "
            f"{item.kept_column_index}"
            for item in proposal.discarded_duplicate_claims
        )
        reasons.extend(
            f"a role {item.proposed_role!r} was claimed for column {item.column_index}, which the table does not carry"
            for item in proposal.unknown_column_claims
        )
        return proposal.roles

    return InvoiceIntakePorts(
        profile_id=profile_id,
        operation=operation,
        creation=creation,
        mapper=mapper,
        mapping_reasons=lambda: tuple(reasons),
    )


__all__ = ["build_invoice_intake_ports"]
