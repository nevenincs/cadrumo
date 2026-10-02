"""Read current ledger membership through the registry-selected source owners.

This is a verify-time observation, never a replacement calculation or a write.
Only declared ledger families run; their existing admission/window rules decide
which transaction identities contributed or remain declarable but held back.

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`:
        The stored values and original caller modes under verification.
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`:
        The selected binding/source ownership declarations.
    :class:`~cadrumo.domain.modelos.work_unit.WorkUnit`:
        The bucket and filing coordinate whose membership is queried.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...core.aggregation import LEDGER_BINDING_SOURCE_KINDS, BindingSourceKind
from ...core.errors.hierarchy import CadrumoError
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit import WorkUnit
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..actividad_asset.ports import ActivityAssetHistoryRepository
from ..bienes_inversion.ports import BienesInversionIvaRegisterRepositoryProtocol
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..ledger.usage_ratio_repository import UsageRatioProfileLoader
from ..modelo.work_profile import ModeloWorkProfile
from .modelo_bindings import (
    LedgerImpatriadoIncomeAggregationSourceResolver,
    LedgerIrnrIncomeAggregationSourceResolver,
    LedgerIvaAggregationSourceResolver,
    LedgerRentaGastosPagoFraccionadoAggregationSourceResolver,
    LedgerRentaIncomeAggregationSourceResolver,
)
from .modelo_bindings_renta_expenses import LedgerRentaGastosEstimacionDirectaAggregationSourceResolver
from .oss_ioss import OssIossLedgerSourceResolver
from .source_mesh import CalculationSourceContext, ModeloSourceResolver


@dataclass(frozen=True, slots=True)
class LedgerMembershipPorts:
    """Required read capabilities of the enrolled ledger source owners."""

    transaction_repository: TransactionCatalogueRepositoryProtocol
    invoice_catalogue_read_ports: InvoiceCatalogueReadPorts
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol
    bienes_inversion_repository: BienesInversionIvaRegisterRepositoryProtocol
    activity_asset_history_repository: ActivityAssetHistoryRepository
    usage_ratio_profile_loader: UsageRatioProfileLoader


@dataclass(frozen=True, slots=True)
class LedgerSourceMembership:
    """Transient observed identities; unavailable membership is never empty proof."""

    observed_transaction_ids: tuple[str, ...] = ()
    available: bool = True
    ledger_sources_declared: bool = False


def ledger_transaction_ref_identity(source_ref: str | None) -> str | None:
    """Read a canonical transaction ref, including a ledger-owned line suffix."""
    if source_ref is None or not source_ref.startswith("transaction:"):
        return None
    identity = source_ref.removeprefix("transaction:").split(":", 1)[0]
    if len(identity) != 64 or any(character not in "0123456789abcdef" for character in identity):
        return None
    return identity


def query_ledger_membership(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    profile: ModeloWorkProfile,
    ports: LedgerMembershipPorts,
) -> LedgerSourceMembership:
    """Observe selected ledger contributors/held-back rows using saved caller modes."""
    selected = frozenset(binding.source for binding in revision.bindings) & LEDGER_BINDING_SOURCE_KINDS
    if not selected:
        return LedgerSourceMembership()
    context = CalculationSourceContext(
        bucket_id=work_unit.bucket_id,
        work_unit_id=work_unit.work_unit_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        revision=revision,
        profile=profile,
        m210_official_tipo_renta_code=target.m210_official_tipo_renta_code,
        m210_gross_income_source_mode=target.m210_gross_income_source_mode,
    )
    observed: set[str] = set()
    handled: set[BindingSourceKind] = set()
    try:
        # Loading the existing investment register is read-only. Calculation's
        # migration capability is deliberately absent from these ports.
        investment = (
            ports.bienes_inversion_repository.load() if BindingSourceKind.LEDGER_IVA_AGGREGATION in selected else None
        )
        resolvers: tuple[ModeloSourceResolver, ...] = (
            LedgerIvaAggregationSourceResolver(
                transaction_repository=ports.transaction_repository,
                invoice_catalogue_read_ports=ports.invoice_catalogue_read_ports,
                prorrata_register_repository=ports.prorrata_register_repository,
                investment_asset_register=investment,
                investment_asset_profile_id=work_unit.bucket_id,
            ),
            LedgerRentaIncomeAggregationSourceResolver(ports=ports.invoice_catalogue_read_ports),
            LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
                ports=ports.invoice_catalogue_read_ports,
                prorrata_register_repository=ports.prorrata_register_repository,
                usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
                activity_asset_history_repository=ports.activity_asset_history_repository,
            ),
            LedgerRentaGastosPagoFraccionadoAggregationSourceResolver(
                transaction_repository=ports.transaction_repository,
                prorrata_register_repository=ports.prorrata_register_repository,
                activity_asset_history_repository=ports.activity_asset_history_repository,
            ),
            LedgerImpatriadoIncomeAggregationSourceResolver(transaction_repository=ports.transaction_repository),
            LedgerIrnrIncomeAggregationSourceResolver(transaction_repository=ports.transaction_repository),
            OssIossLedgerSourceResolver(ports=ports.invoice_catalogue_read_ports),
        )
        for resolver in resolvers:
            owned = frozenset(resolver.owned_sources) & selected
            if not owned:
                continue
            resolution = resolver.resolve(context)
            handled.update(owned)
            observed.update(resolution.source_transaction_ids)
            for diagnostic in resolution.diagnostics:
                if diagnostic.reason == "storage_degraded":
                    return LedgerSourceMembership(available=False, ledger_sources_declared=True)
                # Only existing declarable blockers supply held-back membership;
                # advisories and legal exclusions do not become new ledger rows.
                if diagnostic.reason not in {
                    "source_domain_not_ready",
                    "iva_selected_scope_evidence_failure",
                    "unrouted_observation",
                    "unrouted_declarable_quantity",
                }:
                    continue
                identity = ledger_transaction_ref_identity(diagnostic.source_ref)
                if identity is not None:
                    observed.add(identity)
                elif diagnostic.reason == "source_domain_not_ready":
                    return LedgerSourceMembership(available=False, ledger_sources_declared=True)
    except CadrumoError:
        return LedgerSourceMembership(available=False, ledger_sources_declared=True)
    return LedgerSourceMembership(
        observed_transaction_ids=tuple(sorted(observed)),
        available=frozenset(handled) == selected,
        ledger_sources_declared=True,
    )


__all__ = [
    "LedgerMembershipPorts",
    "LedgerSourceMembership",
    "ledger_transaction_ref_identity",
    "query_ledger_membership",
]
