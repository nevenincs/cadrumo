"""Resolve registered calculation source families for a bucket."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.irnr import M210GrossIncomeSourceMode
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.iva_wallet_carry_targets import (
    iva_wallet_owned_binding_ids_for_revision,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..user_profile.profile_read_ports import ProfileReadPorts
from ._calculation_source_staging import (
    add_expected_missing_binding_diagnostics as _add_expected_missing_binding_diagnostics,
)
from ._calculation_source_staging import (
    add_terminal_origin_diagnostics as _add_terminal_origin_diagnostics,
)
from ._calculation_source_staging import (
    add_unhandled_source_diagnostics as _add_unhandled_source_diagnostics,
)
from ._calculation_source_staging import (
    resolve_prorrata_regularizacion_sources as _resolve_prorrata_regularizacion_sources,
)
from ._transaction_catalogue_cache import MemoizedTransactionCatalogueRepository
from .calculation_action_ports import (
    CalculationActionPorts,
)
from .calculation_route import CalculationRouteStage as _CalculationRouteStage
from .calculation_route import require_calculation_route_resolver as _require_calculation_route_resolver
from .m303_regimen_simplificado_scope import (
    m303_regimen_simplificado_annual_summary_applies_to_profile,
    taxpayer_profile_for_work,
)
from .work_profile import ModeloWorkProfile, ModeloWorkProfilePathValues

if TYPE_CHECKING:
    from ...domain.bienes_inversion.register import BienesInversionIvaRegister
    from ...domain.calculations.registry.detail_record_bindings import Modelo720RowObservation
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ..aggregation.foreign_assets import ForeignAssetIngestObservation
    from ..aggregation.source_mesh import (
        CalculationSourceResolution,
    )
    from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
    from ..prorrata_register.ports import ProrrataRegisterServiceRepositoryProtocol


def resolve_bucket_source_mesh(
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    *,
    ports: CalculationActionPorts,
    foreign_asset_observations: tuple[ForeignAssetIngestObservation, ...],
    foreign_asset_row_observations: tuple[Modelo720RowObservation, ...],
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    m210_official_tipo_renta_code: str | None = None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = None,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    date_binding_values: Mapping[BindingId, date] | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    filing_period_date: date | None = None,
    profile: ModeloWorkProfile | None = None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> CalculationSourceResolution:
    """Resolve enrolled sources against one pinned operation and profile.

    Takes ``snapshot`` as a :class:`RegistrySnapshot`.
    """
    if profile is None:
        from .profile_readiness_gate import load_modelo_work_profile

        profile = load_modelo_work_profile(
            bucket_id=work_unit.bucket_id,
            profile_decode_context=ports.operation.profile_decode_context(),
        )
    profile_read_ports = (
        ports.profile_read_ports
        if profile is None
        else ProfileReadPorts(path_values=ModeloWorkProfilePathValues(profile=profile))
    )
    resolved_transaction_repository = ports.transaction_repository
    memoized_transaction_repository = (
        transaction_repository
        if transaction_repository is not None
        else MemoizedTransactionCatalogueRepository(resolved_transaction_repository)
    )
    prorrata_register_repository = ports.prorrata_register_repository
    iva_investment_asset_register = None
    iva_investment_asset_profile_id = None
    if any(binding.source == BindingSourceKind.LEDGER_IVA_AGGREGATION for binding in snapshot.revision.bindings):
        iva_investment_asset_register = resolved_transaction_repository.migrate_iva_deduction_authority(
            asset_profile_id=work_unit.bucket_id,
        )
        iva_investment_asset_profile_id = work_unit.bucket_id
    from ..aggregation.inventory import InventorySourceResolver
    from ..aggregation.source_mesh import (
        CalculationSourceContext,
        ModeloSourceResolver,
    )
    from ..calculations.m303_regimen_simplificado_annual_summary import (
        M303RegimenSimplificadoAnnualSummarySourceResolver,
    )
    from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts

    resolved_work_unit_repository = ports.work_unit_repository
    resolved_calculation_repository = ports.calculation_repository
    renta_catalogue_read_ports = InvoiceCatalogueReadPorts(
        invoice_reader=ports.invoice_catalogue_read_ports.invoice_reader,
        transaction_reader=memoized_transaction_repository,
    )
    context = CalculationSourceContext(
        bucket_id=work_unit.bucket_id,
        work_unit_id=work_unit.work_unit_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        revision=snapshot.revision,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        profile=profile,
        operation=ports.operation,
    )

    def resolve_declared(
        resolver: ModeloSourceResolver,
        *,
        stage: _CalculationRouteStage = "mesh",
    ) -> CalculationSourceResolution:
        _require_calculation_route_resolver(stage, resolver)
        return resolver.resolve(context)

    annual_summary_resolutions: tuple[CalculationSourceResolution, ...] = (
        resolve_declared(
            M303RegimenSimplificadoAnnualSummarySourceResolver(
                registry_snapshot=snapshot,
                work_unit_repository=resolved_work_unit_repository,
                calculation_repository=resolved_calculation_repository,
                filing_repository=ports.filing_repository,
                regimen_simplificado_applies=m303_regimen_simplificado_annual_summary_applies_to_profile(
                    taxpayer_profile_for_work(profile),
                ),
                operation=ports.operation,
            ),
            stage="conditional",
        ),
    )
    inventory_resolutions: tuple[CalculationSourceResolution, ...] = ()
    if any(binding.source is BindingSourceKind.INVENTORY for binding in snapshot.revision.bindings):
        inventory_resolutions = (
            resolve_declared(
                InventorySourceResolver(
                    inventory_repository=ports.inventory_repository,
                ),
            ),
        )
    source_resolution = _resolve_mesh_families(
        resolve_declared,
        snapshot,
        work_unit,
        ports,
        memoized_transaction_repository,
        prorrata_register_repository,
        iva_investment_asset_register,
        iva_investment_asset_profile_id,
        renta_catalogue_read_ports,
        profile_read_ports,
        foreign_asset_observations,
        foreign_asset_row_observations,
        inventory_resolutions,
        annual_summary_resolutions,
    )
    source_resolution = _source_resolution_excluding_iva_compensation(snapshot, source_resolution)
    source_resolution = _resolve_prorrata_regularizacion_sources(
        registry_snapshot=snapshot,
        work_unit=work_unit,
        context=context,
        source_resolution=source_resolution,
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        date_binding_values=date_binding_values,
        relation_values=relation_values,
        filing_period_date=filing_period_date,
        prorrata_register_repository=prorrata_register_repository,
        bienes_inversion_repository=ports.bienes_inversion_repository,
        observation_repository=ports.observation_repository,
        operation=ports.operation,
    )
    source_resolution = _add_unhandled_source_diagnostics(snapshot.revision, source_resolution)
    source_resolution = _add_terminal_origin_diagnostics(snapshot.revision, source_resolution)
    return _add_expected_missing_binding_diagnostics(snapshot.revision, source_resolution)


def _source_resolution_excluding_iva_compensation(
    snapshot: RegistrySnapshot,
    resolution: CalculationSourceResolution,
) -> CalculationSourceResolution:
    """Keep Modelo 303 prior-compensation owned exclusively by the IVA wallet."""
    excluded_bindings = _iva_wallet_source_ids(snapshot)
    if not _iva_wallet_sources_present(resolution, excluded_bindings=excluded_bindings):
        return resolution
    return _without_iva_wallet_sources(resolution, excluded_bindings=excluded_bindings)


def _iva_wallet_source_ids(snapshot: RegistrySnapshot) -> frozenset[BindingId]:
    """Resolve the binding identities owned by the IVA wallet.

    One set now answers both channels: the fold-value channel is keyed by the
    slot binding it materialises into, so the wallet's carry has a single
    identity rather than a binding id paired with a separate relation id.
    """
    return iva_wallet_owned_binding_ids_for_revision(
        modelo_id=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
    )


def _iva_wallet_sources_present(
    resolution: CalculationSourceResolution,
    *,
    excluded_bindings: frozenset[BindingId],
) -> bool:
    """Return whether a non-wallet resolver supplied a wallet-owned value."""
    return bool(
        excluded_bindings.intersection(resolution.binding_values)
        or excluded_bindings.intersection(resolution.relation_values),
    )


def _without_iva_wallet_sources(
    resolution: CalculationSourceResolution,
    *,
    excluded_bindings: frozenset[BindingId],
) -> CalculationSourceResolution:
    """Remove non-wallet values and provenance for wallet-owned identities."""
    return resolution.model_copy(
        update={
            "binding_values": {k: v for k, v in resolution.binding_values.items() if k not in excluded_bindings},
            "relation_values": {k: v for k, v in resolution.relation_values.items() if k not in excluded_bindings},
            "provenance": tuple(
                item
                for item in resolution.provenance
                if not any(item.source_ref.endswith(f":{binding_id}") for binding_id in excluded_bindings)
                and item.source_ref.split(":", 1)[0] not in excluded_bindings
            ),
        },
    )


def _resolve_mesh_families(
    resolve_declared: Callable[..., CalculationSourceResolution],
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    ports: CalculationActionPorts,
    memoized_transaction_repository: TransactionCatalogueRepositoryProtocol,
    prorrata_register_repository: ProrrataRegisterServiceRepositoryProtocol,
    iva_investment_asset_register: BienesInversionIvaRegister | None,
    iva_investment_asset_profile_id: str | None,
    renta_catalogue_read_ports: InvoiceCatalogueReadPorts,
    profile_read_ports: ProfileReadPorts,
    foreign_asset_observations: tuple[ForeignAssetIngestObservation, ...],
    foreign_asset_row_observations: tuple[Modelo720RowObservation, ...],
    inventory_resolutions: tuple[CalculationSourceResolution, ...],
    annual_summary_resolutions: tuple[CalculationSourceResolution, ...],
) -> CalculationSourceResolution:
    """Resolve each enrolled source family through the same mesh context."""
    from ..aggregation.atribucion_member import AtribucionMemberSourceResolver
    from ..aggregation.foreign_assets import ForeignAssetsAggregationSourceResolver
    from ..aggregation.modelo_bindings import (
        LedgerImpatriadoIncomeAggregationSourceResolver,
        LedgerIrnrIncomeAggregationSourceResolver,
        LedgerRentaGastosPagoFraccionadoAggregationSourceResolver,
        LedgerRentaIncomeAggregationSourceResolver,
    )
    from ..aggregation.modelo_bindings_iva import LedgerIvaAggregationSourceResolver
    from ..aggregation.modelo_bindings_renta_expenses import (
        LedgerRentaGastosEstimacionDirectaAggregationSourceResolver,
    )
    from ..aggregation.modelo_bindings_retenciones import RetencionesAggregationSourceResolver
    from ..aggregation.oss_ioss import OssIossLedgerSourceResolver
    from ..aggregation.source_resolution_operations import merge_source_resolutions
    from ..aggregation.withholding_source import WithholdingSourceResolver
    from ..calculations.iva_compensation_annual_partition import IvaCompensationAnnualPartitionSourceResolver
    from ..calculations.m115_no_relevant_payments import m115_no_relevant_payment_periods_for_bucket
    from ..calculations.multi_year import PreviousFilingSourceResolver
    from ..calculations.relation_prefill import RelationPrefillSourceResolver
    from ..invoices.source_resolver import InvoiceCatalogueSourceResolver

    return merge_source_resolutions(
        (
            resolve_declared(
                LedgerIvaAggregationSourceResolver(
                    transaction_repository=memoized_transaction_repository,
                    invoice_catalogue_read_ports=ports.invoice_catalogue_read_ports,
                    prorrata_register_repository=prorrata_register_repository,
                    investment_asset_register=iva_investment_asset_register,
                    investment_asset_profile_id=iva_investment_asset_profile_id,
                )
            ),
            resolve_declared(
                LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
                    ports=renta_catalogue_read_ports,
                    prorrata_register_repository=prorrata_register_repository,
                    usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
                    activity_asset_history_repository=ports.activity_asset_history_repository,
                )
            ),
            resolve_declared(
                LedgerRentaIncomeAggregationSourceResolver(
                    ports=renta_catalogue_read_ports,
                )
            ),
            resolve_declared(
                LedgerRentaGastosPagoFraccionadoAggregationSourceResolver(
                    transaction_repository=memoized_transaction_repository,
                    prorrata_register_repository=prorrata_register_repository,
                    usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
                    activity_asset_history_repository=ports.activity_asset_history_repository,
                )
            ),
            resolve_declared(
                LedgerImpatriadoIncomeAggregationSourceResolver(
                    transaction_repository=memoized_transaction_repository,
                )
            ),
            resolve_declared(
                LedgerIrnrIncomeAggregationSourceResolver(
                    transaction_repository=memoized_transaction_repository,
                )
            ),
            resolve_declared(
                OssIossLedgerSourceResolver(
                    ports=ports.invoice_catalogue_read_ports,
                )
            ),
            resolve_declared(
                RetencionesAggregationSourceResolver(
                    ports=ports.retencion_observation_ports,
                    m115_no_relevant_payment_periods=m115_no_relevant_payment_periods_for_bucket(
                        work_unit.bucket_id,
                        profile_path_values_reader=profile_read_ports.path_values,
                    ),
                ),
            ),
            resolve_declared(
                WithholdingSourceResolver(
                    ports=ports.percepciones_observation_ports,
                    retencion_ports=ports.retencion_observation_ports,
                )
            ),
            resolve_declared(
                InvoiceCatalogueSourceResolver(
                    ports=ports.invoice_source_ports,
                )
            ),
            resolve_declared(
                ForeignAssetsAggregationSourceResolver(
                    observations=foreign_asset_observations,
                    row_observations=foreign_asset_row_observations,
                    register_loader=ports.foreign_asset_register_repository.load,
                )
            ),
            resolve_declared(AtribucionMemberSourceResolver()),
            *inventory_resolutions,
            resolve_declared(
                PreviousFilingSourceResolver(
                    registry_snapshot=snapshot,
                    repository=ports.observation_repository,
                    iva_history_repository=ports.iva_compensation_history_repository,
                    profile_read_ports=profile_read_ports,
                    excluded_binding_ids=iva_wallet_owned_binding_ids_for_revision(
                        modelo_id=snapshot.modelo.id,
                        revision_id=snapshot.revision.id,
                    ),
                    operation=ports.operation,
                )
            ),
            resolve_declared(
                RelationPrefillSourceResolver(
                    registry_snapshot=snapshot,
                    repository=ports.observation_repository,
                    profile_read_ports=profile_read_ports,
                    operation=ports.operation,
                )
            ),
            resolve_declared(
                IvaCompensationAnnualPartitionSourceResolver(
                    registry_snapshot=snapshot,
                    repository=ports.observation_repository,
                    operation=ports.operation,
                )
            ),
            *annual_summary_resolutions,
        ),
    )
