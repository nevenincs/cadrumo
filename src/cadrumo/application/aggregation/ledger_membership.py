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
    :class:`~cadrumo.domain.calculations.registry.authority.PinnedAuthorityOperation`:
        The caller's generation retained throughout this read-only query.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ...core.aggregation import LEDGER_BINDING_SOURCE_KINDS, BindingSourceKind
from ...core.errors.hierarchy import CadrumoError
from ...core.logging import get_logger
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_sources import ActivityAssetConsumption
from ...domain.modelos.work_unit import WorkUnit
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..actividad_asset.ports import ActivityAssetHistoryRepository
from ..bienes_inversion.ports import BienesInversionIvaRegisterRepositoryProtocol
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..ledger.usage_ratio_repository import UsageRatioProfileLoader
from ..modelo.work_profile import ModeloWorkProfile
from .impatriado_income_bindings import LedgerImpatriadoIncomeAggregationSourceResolver
from .inventory import InventoryLedgerRepositoryProtocol, InventorySourceResolver
from .modelo_bindings import (
    LedgerIrnrIncomeAggregationSourceResolver,
    LedgerRentaIncomeAggregationSourceResolver,
)
from .modelo_bindings_iva import LedgerIvaAggregationSourceResolver
from .modelo_bindings_renta_expenses import (
    LedgerRentaGastosEstimacionDirectaAggregationSourceResolver,
    LedgerRentaGastosPagoFraccionadoAggregationSourceResolver,
)
from .oss_ioss_resolver import OssIossLedgerSourceResolver
from .renta_inmueble_resolver import RentaInmuebleSourceResolver
from .retencion_soportada_repository import RetencionSoportadaPorts
from .source_mesh import CalculationSourceContext, CalculationSourceDiagnostic, ModeloSourceResolver

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class LedgerMembershipPorts:
    """Required read capabilities of the enrolled ledger source owners."""

    transaction_repository: TransactionCatalogueRepositoryProtocol
    invoice_catalogue_read_ports: InvoiceCatalogueReadPorts
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol
    bienes_inversion_repository: BienesInversionIvaRegisterRepositoryProtocol
    activity_asset_history_repository: ActivityAssetHistoryRepository
    usage_ratio_profile_loader: UsageRatioProfileLoader
    inventory_repository: InventoryLedgerRepositoryProtocol
    retencion_soportada_ports: RetencionSoportadaPorts | None = None
    """The suffered-withholding store a let property's rows read; without it those rows cannot be observed."""


@dataclass(frozen=True, slots=True)
class LedgerSourceMembership:
    """Transient observed identities; unavailable membership is never empty proof."""

    observed_transaction_ids: tuple[str, ...] = ()
    available: bool = True
    ledger_sources_declared: bool = False
    activity_asset_consumption: ActivityAssetConsumption = field(default_factory=ActivityAssetConsumption)
    inventory_row_identities: frozenset[tuple[str, str]] = frozenset()
    book_claimed_transaction_ids: frozenset[str] = frozenset()
    """The ledger rows an inventory book's purchases claim, so the Modelo 100 expenses withhold them."""


BOOK_CLAIMED_REASON = "inventory_book_claimed_purchase"


def recorded_book_claimed_transaction_ids(target: CalculationRevision) -> frozenset[str]:
    """Read the claimed ledger rows a :class:`CalculationRevision` withheld, from its persisted notes."""
    return frozenset(
        identity
        for issue in target.source_issues
        if issue.reason == BOOK_CLAIMED_REASON
        and (identity := ledger_transaction_ref_identity(issue.source_ref)) is not None
    )


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
    operation: PinnedAuthorityOperation,
) -> LedgerSourceMembership:
    """Observe selected ledger contributors/held-back rows using saved caller modes.

    Args:
        target: Stored :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            whose caller modes and original membership are under verification.
        work_unit: The filing coordinate described by
            :class:`~cadrumo.domain.modelos.work_unit.WorkUnit`.
        revision: Selected :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
            declaring the ledger source owners to query.
        profile: Current checked filing profile.
        ports: Read-only capabilities for the selected ledger owners.
        operation: Caller-retained
            :class:`~cadrumo.domain.calculations.registry.authority.PinnedAuthorityOperation`
            that supplies every authority fact throughout the query.
    """
    with validating_governed_facts(operation):
        return _query_ledger_membership(
            target=target,
            work_unit=work_unit,
            revision=revision,
            profile=profile,
            ports=ports,
            operation=operation,
        )


def _query_ledger_membership(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    profile: ModeloWorkProfile,
    ports: LedgerMembershipPorts,
    operation: PinnedAuthorityOperation,
) -> LedgerSourceMembership:
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
        operation=operation,
        m210_official_tipo_renta_code=target.m210_official_tipo_renta_code,
        m210_gross_income_source_mode=target.m210_gross_income_source_mode,
    )
    try:
        membership = collect_ledger_membership(context=context, work_unit=work_unit, ports=ports, selected=selected)
        if not consumed_inventory_rows(target):
            return membership
        return replace(membership, inventory_row_identities=_observe_inventory_rows(context, ports))
    except (CadrumoError, LookupError) as exc:
        _log.debug("ledger membership unavailable error_type=%s", type(exc).__name__)
        return LedgerSourceMembership(available=False, ledger_sources_declared=True)


def consumed_inventory_rows(target: CalculationRevision) -> frozenset[tuple[str, str]]:
    """Read the activity and projection fingerprint recorded by a :class:`CalculationRevision`."""
    return frozenset(
        (identity.source_row_identity, identity.fingerprint)
        for identity in target.row_source_identities.values()
        if identity.source_kind is BindingSourceKind.INVENTORY
    )


def _observe_inventory_rows(
    context: CalculationSourceContext,
    ports: LedgerMembershipPorts,
) -> frozenset[tuple[str, str]]:
    """Resolve the same rows through the inventory owner; an unresolved cohort observes none."""
    resolution = InventorySourceResolver(inventory_repository=ports.inventory_repository).resolve(context)
    return frozenset(
        (identity.source_row_identity, identity.fingerprint) for identity in resolution.row_source_identities.values()
    )


def collect_ledger_membership(
    *,
    context: CalculationSourceContext,
    work_unit: WorkUnit,
    ports: LedgerMembershipPorts,
    selected: frozenset[BindingSourceKind],
) -> LedgerSourceMembership:
    """Collect the ledger membership of a work unit for the selected binding source kinds."""
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
        LedgerRentaIncomeAggregationSourceResolver(
            ports=ports.invoice_catalogue_read_ports,
            activity_asset_history_repository=ports.activity_asset_history_repository,
            transaction_repository=ports.transaction_repository,
        ),
        LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
            ports=ports.invoice_catalogue_read_ports,
            prorrata_register_repository=ports.prorrata_register_repository,
            usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
            activity_asset_history_repository=ports.activity_asset_history_repository,
            inventory_repository=ports.inventory_repository,
        ),
        LedgerRentaGastosPagoFraccionadoAggregationSourceResolver(
            transaction_repository=ports.transaction_repository,
            invoice_reader=ports.invoice_catalogue_read_ports.invoice_reader,
            prorrata_register_repository=ports.prorrata_register_repository,
            usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
            activity_asset_history_repository=ports.activity_asset_history_repository,
        ),
        LedgerImpatriadoIncomeAggregationSourceResolver(transaction_repository=ports.transaction_repository),
        LedgerIrnrIncomeAggregationSourceResolver(transaction_repository=ports.transaction_repository),
        OssIossLedgerSourceResolver(ports=ports.invoice_catalogue_read_ports),
    )
    observed: set[str] = set()
    asset_refs: set[str] = set()
    book_claimed: set[str] = set()
    handled: set[BindingSourceKind] = set()
    for resolver in resolvers:
        owned = frozenset(resolver.owned_sources) & selected
        if not owned:
            continue
        resolution = resolver.resolve(context)
        handled.update(owned)
        observed.update(resolution.source_transaction_ids)
        asset_refs.update(row.source_ref for row in resolution.provenance)
        for diagnostic in resolution.diagnostics:
            if not _record_membership_diagnostic(diagnostic, observed):
                return LedgerSourceMembership(available=False, ledger_sources_declared=True)
            if diagnostic.reason == BOOK_CLAIMED_REASON:
                identity = ledger_transaction_ref_identity(diagnostic.source_ref)
                if identity is not None:
                    book_claimed.add(identity)
    return LedgerSourceMembership(
        observed_transaction_ids=tuple(sorted(observed)),
        available=frozenset(handled) == selected,
        ledger_sources_declared=True,
        activity_asset_consumption=ActivityAssetConsumption.from_source_refs(asset_refs),
        book_claimed_transaction_ids=frozenset(book_claimed),
    )


def _record_membership_diagnostic(diagnostic: CalculationSourceDiagnostic, observed: set[str]) -> bool:
    """Record a held-back identity, returning false when membership is unavailable."""
    reason = diagnostic.reason
    if reason == "storage_degraded":
        return False
    # Only existing declarable blockers supply held-back membership; advisories
    # and legal exclusions do not become new ledger rows.
    if reason not in {
        "source_domain_not_ready",
        "iva_selected_scope_evidence_failure",
        "unrouted_observation",
        "unrouted_declarable_quantity",
    }:
        return True
    identity = ledger_transaction_ref_identity(diagnostic.source_ref)
    if identity is not None:
        observed.add(identity)
        return True
    return reason != "source_domain_not_ready"


def consumed_renta_inmueble_rows(target: CalculationRevision) -> frozenset[tuple[str, str]]:
    """Read each let property's identity and fingerprint recorded by a :class:`CalculationRevision`."""
    return frozenset(
        (identity.source_row_identity, identity.fingerprint)
        for identity in target.row_source_identities.values()
        if identity.source_kind is BindingSourceKind.RENTA_INMUEBLE
    )


def observe_renta_inmueble_rows(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    profile: ModeloWorkProfile,
    ports: LedgerMembershipPorts,
    operation: PinnedAuthorityOperation,
) -> frozenset[tuple[str, str]] | None:
    """Resolve the let properties again from the current profile, ledger and withholding records.

    A row's fingerprint covers its property and lease records, its linked
    ledger rows and its suffered withholding, never what the filer stated of it,
    so a statement made since the calculation moves nothing. A refused cohort
    observes no row. Returns ``None`` when a store cannot be read: an unread
    store is never proof that nothing moved.
    """
    if ports.retencion_soportada_ports is None:
        return None
    context = CalculationSourceContext(
        bucket_id=work_unit.bucket_id,
        work_unit_id=work_unit.work_unit_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        revision=revision,
        profile=profile,
        operation=operation,
        m210_official_tipo_renta_code=target.m210_official_tipo_renta_code,
        m210_gross_income_source_mode=target.m210_gross_income_source_mode,
    )
    try:
        with validating_governed_facts(operation):
            resolution = RentaInmuebleSourceResolver(
                transaction_repository=ports.transaction_repository,
                retencion_soportada_ports=ports.retencion_soportada_ports,
            ).resolve(context)
    except (CadrumoError, LookupError) as exc:
        _log.debug("renta inmueble membership unavailable error_type=%s", type(exc).__name__)
        return None
    if any(diagnostic.reason == "storage_degraded" for diagnostic in resolution.diagnostics):
        return None
    return frozenset(
        (identity.source_row_identity, identity.fingerprint) for identity in resolution.row_source_identities.values()
    )


__all__ = [
    "LedgerMembershipPorts",
    "LedgerSourceMembership",
    "consumed_inventory_rows",
    "consumed_renta_inmueble_rows",
    "ledger_transaction_ref_identity",
    "observe_renta_inmueble_rows",
    "query_ledger_membership",
    "recorded_book_claimed_transaction_ids",
]
