"""The single enrollment authority joining a provider kind to everything it needs.

A provider kind used to be real only by agreement between three tables that
could each be edited alone: a selector-model lookup, a validator lookup, and the
application route table. Seven authored kinds proved the arrangement does not
hold -- they carried a model and a validator, reached calculation, and had no
owner at all, visible only as an advisory diagnostic.

:data:`BINDING_PROVIDER_REGISTRATIONS` replaces the agreement with one row per
union member. The row carries the member's model, its build-time validator, the
value channels and aggregation operations the family can honour, the terminal
origin classes it can produce, its output shape, its filing disposition, its
route owner, and its authoring support. A kind is real when it has a row, and a
row is complete or the module refuses to import.

Two ownership shapes exist because two honest answers exist.
:class:`RouteOwnership` names a resolver on the production calculation route --
including the two pseudo-owners, which run no resolver class but are enrolled so
that operator input and a diseño constant are not mistaken for unrouted sources.
:class:`NonRuntimeOwnership` names the absence of a route as a declaration:
``disposition = "deferred"`` with the reason written down, so a kind nobody
routed is a stated gap rather than a silent zero.

The registration table lives in the domain because the declaration is domain
authority; the route table lives in the application beside its resolvers. The
join between them is therefore asserted where the dependency direction allows
it -- in the application module, which imports this one.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Literal, get_args, get_origin

from pydantic import BaseModel

from ....core.aggregation import (
    ROW_SET_GROUPING_FOR_BINDING_SOURCE,
    BindingAggregationOp,
    BindingSourceKind,
    RowSetGroupingKind,
)
from .bienes_inversion_regularizacion_bindings import BienesInversionRegularizacionProvider
from .binding_provider import BindingProvider
from .binding_terminal_origin import TerminalOriginClass
from .binding_value_contract import BindingValueChannel
from .bindings_previous_filing import PreviousFilingProvider, validate_previous_filing_binding
from .counterpart_bindings import validate_counterpart_binding
from .design_constant_bindings import DesignConstantProvider, validate_design_constant_binding
from .detail_record_bindings import (
    AtribucionMemberProvider,
    ForeignAssetProvider,
    RefundOperationProvider,
    RelatedPartyOperationProvider,
    validate_atribucion_binding,
    validate_foreign_asset_binding,
    validate_refund_binding,
    validate_related_party_binding,
)
from .donativo_bindings import DonativoDonorProvider, validate_donativo_binding
from .errors import RegistryValidationError
from .gasto193_bindings import Gasto193ContributorProvider, validate_gasto193_binding_selector_shape
from .ids import RevisionId
from .inventory_bindings import InventoryProvider, validate_inventory_binding
from .invoice_bindings import (
    CollectibleInvoiceProvider,
    LedgerTransactionProvider,
    M347ThirdPartyOperationProvider,
    PayableInvoiceProvider,
    PurchaseInvoiceEvidenceProvider,
    validate_invoice_binding,
)
from .irnr_ledger_bindings import LedgerIrnrIncomeProvider, validate_ledger_irnr_income_aggregation_binding
from .iva_compensation_annual_partition_bindings import IvaCompensationAnnualPartitionProvider
from .ledger_impatriado_bindings import (
    LedgerImpatriadoIncomeProvider,
    validate_ledger_impatriado_income_aggregation_binding,
)
from .ledger_iva_bindings import LedgerIvaProvider, validate_ledger_iva_aggregation_binding
from .ledger_oss_bindings import LedgerOssProvider, validate_ledger_oss_aggregation_binding
from .ledger_renta_gastos_estimacion_directa_bindings import (
    LedgerRentaGastosEstimacionDirectaProvider,
    validate_ledger_renta_gastos_estimacion_directa_aggregation_binding,
)
from .ledger_renta_gastos_pago_fraccionado_bindings import (
    LedgerRentaGastosPagoFraccionadoProvider,
    validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding,
)
from .ledger_renta_income_bindings import LedgerRentaIncomeProvider, validate_ledger_renta_income_aggregation_binding
from .m303_regimen_simplificado_annual_summary_bindings import M303RegimenSimplificadoAnnualSummaryProvider
from .manual_input_selector import ManualInputProvider
from .profile_bindings import ProfileProvider
from .prorrata_regularizacion_bindings import ProrrataRegularizacionProvider
from .relation_prefill_bindings import RelationPrefillProvider
from .retenciones_bindings import RetencionesAggregationProvider, validate_retenciones_aggregation_binding
from .withholding296_bindings import Withholding296Provider, validate_withholding296_binding_selector_shape
from .withholding_bindings import WithholdingProvider, validate_withholding_binding_selector_shape

if TYPE_CHECKING:
    from .schema import BindingDefinition

__all__ = [
    "BINDING_PROVIDER_REGISTRATIONS",
    "BindingProviderRegistration",
    "BindingProviderValidator",
    "BindingRouteStage",
    "NonRuntimeOwnership",
    "ProviderAuthoringSupport",
    "ProviderDisposition",
    "ProviderOutputShape",
    "ProviderRouteOwnership",
    "ProviderRowAssembly",
    "RouteOwnership",
    "provider_model_for",
    "registration_for",
    "validate_binding_against_registration",
    "validate_binding_provider_registrations",
    "validator_for",
]

type BindingProviderValidator = Callable[[BindingDefinition], list[str]]
"""One family's accumulating build-time validator: ``validate(binding) -> list[str]``."""

BindingRouteStage = Literal["pre_mesh", "mesh", "conditional", "post_mesh", "manual"]
"""A production calculation-route stage, spelled as the route table spells it."""

ProviderRowAssembly = Literal["grouped", "provider_native"]
"""Which of the two row channels assembles a row-producing family's rows.

``grouped`` families are assembled by the shared row-set assembler and name the
grouping axis it dispatches on. ``provider_native`` families emit their rows
from their own resolver -- the invoice catalogue its detail rows, the inventory
resolver its row binding values, the profile resolver its repeating typed
collections -- and name no grouping, because no grouped assembler consumes
them and a grouping the closed dispatcher does not know would fail at resolve
time rather than at build time.
"""

ProviderOutputShape = Literal["scalar", "rows", "scalar_and_rows"]
"""What a resolver for this kind can emit."""

ProviderDisposition = Literal["filing_grade", "advisory", "deferred", "non_runtime"]
"""How much weight a value from this kind may carry in a filing."""

ProviderAuthoringSupport = Literal["scaffold", "generator", "none"]
"""How much help an author gets writing a row of this kind."""


@dataclass(frozen=True, slots=True)
class RouteOwnership:
    """The production calculation-route owner of one provider kind.

    ``resolver_id`` and ``stage`` restate the route table's own values so the
    domain can carry them without importing application code; the application
    asserts the restatement is true at its own import time, which is the only
    place both tables are visible at once.
    """

    resolver_id: str
    stage: BindingRouteStage


@dataclass(frozen=True, slots=True)
class NonRuntimeOwnership:
    """The declared absence of a runtime owner for one provider kind.

    ``owner`` states who or what stands in for a resolver: a pseudo-owner name
    for a kind that needs no aggregation, or the reason a route is deferred.
    Spelling the absence out is what keeps it out of the silent-gap category.
    """

    owner: str


type ProviderRouteOwnership = RouteOwnership | NonRuntimeOwnership


@dataclass(frozen=True, slots=True)
class BindingProviderRegistration:
    """Everything that makes one provider kind real, in one row."""

    kind: BindingSourceKind
    provider_model: type[BaseModel]
    validator: BindingProviderValidator | None
    """The family's build-time gate, or ``None`` when the union member is the whole gate.

    A family whose only build-time invariant is its own provider shape needs no
    validator: the discriminated union has already constructed that member from
    the authored row, so re-validating the typed member against its own class
    can produce no diagnostic. ``None`` states that the member carries the gate,
    rather than dressing a no-op call up as one.
    """
    permitted_value_channels: frozenset[BindingValueChannel]
    permitted_aggregation_ops: frozenset[BindingAggregationOp]
    permitted_terminal_origins: frozenset[TerminalOriginClass]
    output: ProviderOutputShape
    disposition: ProviderDisposition
    route: ProviderRouteOwnership
    authoring: ProviderAuthoringSupport

    @property
    def names_source_casilla(self) -> bool:
        """Return whether this kind's provider member declares a source casilla coordinate.

        Derived from the member's own fields rather than restated as data, so a
        family cannot claim a coordinate its model does not carry. The typed
        source accessors read this to tell "this family has no source casilla"
        apart from "this family has one and the accessor forgot to narrow it".
        """
        fields = self.provider_model.model_fields
        return "source_casilla_id" in fields or "source_casilla_ids" in fields

    @property
    def names_source_modelo(self) -> bool:
        """Return whether this kind's provider member declares a source modelo coordinate."""
        return "source_modelo" in self.provider_model.model_fields

    @property
    def row_grouping(self) -> RowSetGroupingKind | None:
        """Return the grouping axis this kind's rows are assembled by, if any."""
        return ROW_SET_GROUPING_FOR_BINDING_SOURCE.get(self.kind)

    @property
    def row_assembly(self) -> ProviderRowAssembly:
        """Return which row channel assembles this kind's rows.

        Derived from the canonical grouping correspondence rather than restated
        as a field: a kind is ``grouped`` exactly when
        :data:`~core.aggregation.ROW_SET_GROUPING_FOR_BINDING_SOURCE` enrolls
        it, so the registration cannot claim an assembly mode the row-set
        dispatcher does not actually offer.
        """
        return "grouped" if self.row_grouping is not None else "provider_native"


_SCALAR_CHANNELS: Final = frozenset(
    {
        BindingValueChannel.DECIMAL,
        BindingValueChannel.INTEGER,
        BindingValueChannel.BOOLEAN,
        BindingValueChannel.TEXT,
        BindingValueChannel.DATE,
        BindingValueChannel.ENUM,
    },
)
"""Every channel that carries one value rather than a row family."""

_MONEY_CHANNELS: Final = frozenset({BindingValueChannel.DECIMAL})
_MONEY_OR_COUNT_CHANNELS: Final = frozenset({BindingValueChannel.DECIMAL, BindingValueChannel.INTEGER})
_ROW_CHANNELS: Final = frozenset({BindingValueChannel.ROW_SET})

_FOLD_OPS: Final = frozenset({BindingAggregationOp.SUM, BindingAggregationOp.COPY})
_ROW_OPS: Final = frozenset({BindingAggregationOp.ROWS})
_CARRY_OPS: Final = frozenset({BindingAggregationOp.COPY})

_MANUAL_INPUT_RESOLVER_ID: Final = "manual_input"
_DESIGN_CONSTANT_RESOLVER_ID: Final = "design_constant"

_PSEUDO_OWNER_RESOLVER_IDS: Final = frozenset({_MANUAL_INPUT_RESOLVER_ID, _DESIGN_CONSTANT_RESOLVER_ID})
"""Route owners that name no resolver class because there is nothing to run."""

_DEFERRED_DETAIL_RECORD_OWNER: Final = (
    "deferred: authored detail-record family with no executable route owner on the production calculation route"
)
_DEFERRED_INVOICE_OWNER: Final = (
    "deferred: invoice-shaped provider model with no executable route owner on the production calculation route"
)
_DEFERRED_PERCEPTOR_OWNER: Final = (
    "deferred: perceptor provider model with no executable route owner on the production calculation route"
)


def _filing_grade(
    kind: BindingSourceKind,
    provider_model: type[BaseModel],
    validator: BindingProviderValidator | None,
    *,
    channels: frozenset[BindingValueChannel],
    ops: frozenset[BindingAggregationOp],
    origins: frozenset[TerminalOriginClass],
    output: ProviderOutputShape,
    resolver_id: str,
    stage: BindingRouteStage,
) -> BindingProviderRegistration:
    return BindingProviderRegistration(
        kind=kind,
        provider_model=provider_model,
        validator=validator,
        permitted_value_channels=channels,
        permitted_aggregation_ops=ops,
        permitted_terminal_origins=origins,
        output=output,
        disposition="filing_grade",
        route=RouteOwnership(resolver_id=resolver_id, stage=stage),
        authoring="scaffold",
    )


def _deferred(
    kind: BindingSourceKind,
    provider_model: type[BaseModel],
    validator: BindingProviderValidator | None,
    *,
    origins: frozenset[TerminalOriginClass],
    owner: str,
) -> BindingProviderRegistration:
    """Register a kind whose route is declared missing rather than assumed.

    The provider model and validator are real -- an authored row of this kind is
    still refused when malformed -- but no resolver produces a value, so the
    disposition states that outright instead of letting the row resolve blank.
    """
    return BindingProviderRegistration(
        kind=kind,
        provider_model=provider_model,
        validator=validator,
        permitted_value_channels=_ROW_CHANNELS,
        permitted_aggregation_ops=_ROW_OPS,
        permitted_terminal_origins=origins,
        output="rows",
        disposition="deferred",
        route=NonRuntimeOwnership(owner=owner),
        authoring="scaffold",
    )


def _non_runtime(
    kind: BindingSourceKind,
    provider_model: type[BaseModel],
    validator: BindingProviderValidator | None,
    *,
    origin: TerminalOriginClass,
    resolver_id: str,
) -> BindingProviderRegistration:
    """Register a kind that is enrolled on the route but runs no resolver."""
    return BindingProviderRegistration(
        kind=kind,
        provider_model=provider_model,
        validator=validator,
        permitted_value_channels=_SCALAR_CHANNELS,
        permitted_aggregation_ops=_CARRY_OPS,
        permitted_terminal_origins=frozenset({origin}),
        output="scalar",
        disposition="non_runtime",
        route=RouteOwnership(resolver_id=resolver_id, stage="manual"),
        authoring="scaffold",
    )


def _ledger_aggregation(
    kind: BindingSourceKind,
    provider_model: type[BaseModel],
    validator: BindingProviderValidator | None,
    *,
    resolver_id: str,
    output: ProviderOutputShape = "scalar",
) -> BindingProviderRegistration:
    channels = _MONEY_CHANNELS if output == "scalar" else _MONEY_CHANNELS | _ROW_CHANNELS
    ops = _FOLD_OPS if output == "scalar" else _FOLD_OPS | _ROW_OPS
    return _filing_grade(
        kind,
        provider_model,
        validator,
        channels=channels,
        ops=ops,
        origins=frozenset({TerminalOriginClass.LEDGER_AGGREGATE}),
        output=output,
        resolver_id=resolver_id,
        stage="mesh",
    )


def _invoice_catalogue(
    kind: BindingSourceKind,
    provider_model: type[BaseModel],
) -> BindingProviderRegistration:
    return _filing_grade(
        kind,
        provider_model,
        validate_invoice_binding,
        channels=_MONEY_OR_COUNT_CHANNELS | _ROW_CHANNELS,
        ops=_FOLD_OPS | _ROW_OPS | frozenset({BindingAggregationOp.COUNT_DISTINCT}),
        origins=frozenset({TerminalOriginClass.INVOICE_CATALOGUE}),
        output="scalar_and_rows",
        resolver_id="invoice_catalogue",
        stage="mesh",
    )


_REGISTRATIONS: Final[tuple[BindingProviderRegistration, ...]] = (
    _non_runtime(
        BindingSourceKind.MANUAL_INPUT,
        ManualInputProvider,
        None,
        origin=TerminalOriginClass.OPERATOR_INPUT,
        resolver_id=_MANUAL_INPUT_RESOLVER_ID,
    ),
    _non_runtime(
        BindingSourceKind.DESIGN_CONSTANT,
        DesignConstantProvider,
        validate_design_constant_binding,
        origin=TerminalOriginClass.DESIGN_CONSTANT,
        resolver_id=_DESIGN_CONSTANT_RESOLVER_ID,
    ),
    _filing_grade(
        BindingSourceKind.PROFILE,
        ProfileProvider,
        None,
        # Scalar profile fields use the carry operation; repeating typed
        # profile collections emit provider-native row sets. The two shapes
        # share one provider kind, so both channels and cardinalities belong
        # to this registration.
        channels=_SCALAR_CHANNELS | _ROW_CHANNELS,
        ops=_CARRY_OPS | _ROW_OPS,
        origins=frozenset({TerminalOriginClass.PROFILE_FIELD}),
        output="scalar_and_rows",
        resolver_id="profile",
        stage="pre_mesh",
    ),
    _filing_grade(
        BindingSourceKind.PREVIOUS_FILING,
        PreviousFilingProvider,
        validate_previous_filing_binding,
        channels=_MONEY_OR_COUNT_CHANNELS,
        ops=_FOLD_OPS | frozenset({BindingAggregationOp.PRIOR_PAGOS_FRACCIONADOS}),
        origins=frozenset({TerminalOriginClass.FILED_MODELO_CASILLA}),
        output="scalar",
        resolver_id="previous_filing",
        stage="mesh",
    ),
    _filing_grade(
        BindingSourceKind.RELATION_PREFILL,
        RelationPrefillProvider,
        None,
        channels=_MONEY_OR_COUNT_CHANNELS,
        ops=_FOLD_OPS,
        origins=frozenset({TerminalOriginClass.FILED_MODELO_CASILLA}),
        output="scalar",
        resolver_id="relation_prefill",
        stage="mesh",
    ),
    _filing_grade(
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION,
        IvaCompensationAnnualPartitionProvider,
        None,
        channels=_MONEY_CHANNELS,
        ops=_FOLD_OPS,
        origins=frozenset(
            {TerminalOriginClass.FILED_MODELO_CASILLA, TerminalOriginClass.DERIVED_CALCULATION},
        ),
        output="scalar",
        resolver_id="iva_compensation_annual_partition",
        stage="mesh",
    ),
    _filing_grade(
        BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY,
        M303RegimenSimplificadoAnnualSummaryProvider,
        None,
        channels=_MONEY_CHANNELS,
        ops=_FOLD_OPS,
        origins=frozenset({TerminalOriginClass.FILED_MODELO_CASILLA}),
        output="scalar",
        resolver_id="m303_regimen_simplificado_annual_summary",
        stage="conditional",
    ),
    _filing_grade(
        BindingSourceKind.PRORRATA_REGULARIZACION,
        ProrrataRegularizacionProvider,
        None,
        channels=_MONEY_CHANNELS,
        ops=_FOLD_OPS,
        origins=frozenset({TerminalOriginClass.DERIVED_CALCULATION}),
        output="scalar",
        resolver_id="prorrata_regularizacion",
        stage="post_mesh",
    ),
    _filing_grade(
        BindingSourceKind.BIENES_INVERSION_REGULARIZACION,
        BienesInversionRegularizacionProvider,
        None,
        channels=_MONEY_CHANNELS,
        ops=_FOLD_OPS,
        origins=frozenset({TerminalOriginClass.DERIVED_CALCULATION}),
        output="scalar",
        resolver_id="bienes_inversion_regularizacion",
        stage="post_mesh",
    ),
    _ledger_aggregation(
        BindingSourceKind.LEDGER_IVA_AGGREGATION,
        LedgerIvaProvider,
        validate_ledger_iva_aggregation_binding,
        resolver_id="ledger_iva_aggregation",
    ),
    _ledger_aggregation(
        BindingSourceKind.LEDGER_OSS_AGGREGATION,
        LedgerOssProvider,
        validate_ledger_oss_aggregation_binding,
        resolver_id="ledger_oss_aggregation",
    ),
    _ledger_aggregation(
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        LedgerRentaIncomeProvider,
        validate_ledger_renta_income_aggregation_binding,
        resolver_id="ledger_renta_income_aggregation",
    ),
    _ledger_aggregation(
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
        LedgerRentaGastosEstimacionDirectaProvider,
        validate_ledger_renta_gastos_estimacion_directa_aggregation_binding,
        resolver_id="ledger_renta_gastos_estimacion_directa_aggregation",
    ),
    _ledger_aggregation(
        BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
        LedgerRentaGastosPagoFraccionadoProvider,
        validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding,
        resolver_id="ledger_renta_gastos_pago_fraccionado_aggregation",
    ),
    _ledger_aggregation(
        BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
        LedgerImpatriadoIncomeProvider,
        validate_ledger_impatriado_income_aggregation_binding,
        resolver_id="ledger_impatriado_income_aggregation",
    ),
    _ledger_aggregation(
        BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,
        LedgerIrnrIncomeProvider,
        validate_ledger_irnr_income_aggregation_binding,
        resolver_id="ledger_irnr_income_aggregation",
        output="scalar_and_rows",
    ),
    _filing_grade(
        BindingSourceKind.RETENCIONES_AGGREGATION,
        RetencionesAggregationProvider,
        validate_retenciones_aggregation_binding,
        # The family folds a taxable base or retention into money and a
        # distinct-perceptor headcount into an integer; both are authored facts
        # of the same provider, so both channels are permitted.
        channels=_MONEY_OR_COUNT_CHANNELS,
        ops=_FOLD_OPS,
        origins=frozenset({TerminalOriginClass.PERCEPTOR_OBSERVATION}),
        output="scalar",
        resolver_id="retenciones_aggregation",
        stage="mesh",
    ),
    _filing_grade(
        BindingSourceKind.WITHHOLDING,
        WithholdingProvider,
        validate_withholding_binding_selector_shape,
        # The perceptor detail records of modelos 190 and 193 are authored as
        # ``row_field`` withholding bindings, so the family emits a row family
        # as well as the folded scalars.
        channels=_MONEY_OR_COUNT_CHANNELS | _ROW_CHANNELS,
        ops=_FOLD_OPS | _ROW_OPS | frozenset({BindingAggregationOp.COUNT_DISTINCT}),
        origins=frozenset({TerminalOriginClass.PERCEPTOR_OBSERVATION}),
        output="scalar_and_rows",
        resolver_id="withholding",
        stage="mesh",
    ),
    _invoice_catalogue(BindingSourceKind.PAYABLE_INVOICE, PayableInvoiceProvider),
    _invoice_catalogue(BindingSourceKind.COLLECTIBLE_INVOICE, CollectibleInvoiceProvider),
    _invoice_catalogue(BindingSourceKind.M347_THIRD_PARTY_OPERATION, M347ThirdPartyOperationProvider),
    _filing_grade(
        BindingSourceKind.FOREIGN_ASSET,
        ForeignAssetProvider,
        validate_foreign_asset_binding,
        channels=_ROW_CHANNELS,
        ops=_ROW_OPS,
        origins=frozenset({TerminalOriginClass.DETAIL_RECORD}),
        output="rows",
        resolver_id="foreign_assets_aggregation",
        stage="mesh",
    ),
    _filing_grade(
        BindingSourceKind.ATRIBUCION_MEMBER,
        AtribucionMemberProvider,
        validate_atribucion_binding,
        channels=_MONEY_OR_COUNT_CHANNELS | _ROW_CHANNELS,
        ops=_FOLD_OPS | _ROW_OPS,
        origins=frozenset({TerminalOriginClass.PROFILE_FIELD}),
        output="scalar_and_rows",
        resolver_id="atribucion_member_profile",
        stage="mesh",
    ),
    _filing_grade(
        BindingSourceKind.INVENTORY,
        InventoryProvider,
        validate_inventory_binding,
        channels=_ROW_CHANNELS,
        ops=_ROW_OPS,
        origins=frozenset({TerminalOriginClass.DETAIL_RECORD}),
        output="rows",
        resolver_id="inventory",
        stage="mesh",
    ),
    _deferred(
        BindingSourceKind.RELATED_PARTY_OPERATION,
        RelatedPartyOperationProvider,
        validate_related_party_binding,
        origins=frozenset({TerminalOriginClass.DETAIL_RECORD}),
        owner=_DEFERRED_DETAIL_RECORD_OWNER,
    ),
    _deferred(
        BindingSourceKind.REFUND_OPERATION,
        RefundOperationProvider,
        validate_refund_binding,
        origins=frozenset({TerminalOriginClass.DETAIL_RECORD}),
        owner=_DEFERRED_DETAIL_RECORD_OWNER,
    ),
    _deferred(
        BindingSourceKind.DONATIVO_DONOR,
        DonativoDonorProvider,
        validate_donativo_binding,
        origins=frozenset({TerminalOriginClass.DETAIL_RECORD}),
        owner=_DEFERRED_DETAIL_RECORD_OWNER,
    ),
    _deferred(
        BindingSourceKind.GASTO193_CONTRIBUTOR,
        Gasto193ContributorProvider,
        validate_gasto193_binding_selector_shape,
        origins=frozenset({TerminalOriginClass.DETAIL_RECORD}),
        owner=_DEFERRED_DETAIL_RECORD_OWNER,
    ),
    _deferred(
        BindingSourceKind.LEDGER_TRANSACTION,
        LedgerTransactionProvider,
        validate_counterpart_binding,
        origins=frozenset({TerminalOriginClass.INVOICE_CATALOGUE}),
        owner=_DEFERRED_INVOICE_OWNER,
    ),
    _deferred(
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
        PurchaseInvoiceEvidenceProvider,
        validate_invoice_binding,
        origins=frozenset({TerminalOriginClass.INVOICE_CATALOGUE}),
        owner=_DEFERRED_INVOICE_OWNER,
    ),
    _deferred(
        BindingSourceKind.WITHHOLDING296,
        Withholding296Provider,
        validate_withholding296_binding_selector_shape,
        origins=frozenset({TerminalOriginClass.PERCEPTOR_OBSERVATION}),
        owner=_DEFERRED_PERCEPTOR_OWNER,
    ),
)


def _union_member_kinds() -> frozenset[BindingSourceKind]:
    """Return the kind literal of every member of the closed provider union.

    Read off the union itself rather than restated, so a member added to
    :data:`~.binding_provider.BindingProvider` without a registration row is an
    import-time refusal rather than a kind that quietly has no authority.
    """
    annotated_args = get_args(BindingProvider)
    members = get_args(annotated_args[0]) if annotated_args else ()
    return frozenset(BindingSourceKind(member.model_fields["kind"].default) for member in members)


def _require_no_duplicate_kinds(registrations: tuple[BindingProviderRegistration, ...]) -> None:
    seen: set[BindingSourceKind] = set()
    for registration in registrations:
        if registration.kind in seen:
            raise RegistryValidationError(
                f"binding provider kind {registration.kind.value!r} is registered more than once",
                context={"kind": registration.kind.value},
            )
        seen.add(registration.kind)


def _require_complete_union_coverage(registrations: tuple[BindingProviderRegistration, ...]) -> None:
    registered = frozenset(registration.kind for registration in registrations)
    expected = _union_member_kinds()
    if registered != expected:
        missing = sorted(kind.value for kind in expected - registered)
        unexpected = sorted(kind.value for kind in registered - expected)
        raise RegistryValidationError(
            "binding provider registrations must cover exactly the provider union members",
            context={"missing": missing, "unexpected": unexpected},
        )


def _require_provider_model_identity(registration: BindingProviderRegistration) -> None:
    declared = registration.provider_model.model_fields.get("kind")
    if declared is None or declared.default != registration.kind.value:
        raise RegistryValidationError(
            f"binding provider registration {registration.kind.value!r} names a model of another kind",
            context={"kind": registration.kind.value, "provider_model": registration.provider_model.__name__},
        )


def _require_channel_shape(registration: BindingProviderRegistration) -> None:
    carries_rows = BindingValueChannel.ROW_SET in registration.permitted_value_channels
    carries_scalar = bool(registration.permitted_value_channels & _SCALAR_CHANNELS)
    expected: ProviderOutputShape = (
        "scalar_and_rows" if carries_rows and carries_scalar else ("rows" if carries_rows else "scalar")
    )
    if expected != registration.output:
        raise RegistryValidationError(
            f"binding provider registration {registration.kind.value!r} declares output "
            f"{registration.output!r} but permits {expected!r} channels",
            context={"kind": registration.kind.value, "output": registration.output, "expected_output": expected},
        )
    if BindingAggregationOp.ROWS in registration.permitted_aggregation_ops and not carries_rows:
        raise RegistryValidationError(
            f"binding provider registration {registration.kind.value!r} permits the rows operation "
            "without permitting the row_set channel",
            context={"kind": registration.kind.value},
        )


def _require_declared_content(registration: BindingProviderRegistration) -> None:
    if not registration.permitted_value_channels:
        raise RegistryValidationError(
            f"binding provider registration {registration.kind.value!r} permits no value channel",
            context={"kind": registration.kind.value},
        )
    if not registration.permitted_aggregation_ops:
        raise RegistryValidationError(
            f"binding provider registration {registration.kind.value!r} permits no aggregation operation",
            context={"kind": registration.kind.value},
        )
    if not registration.permitted_terminal_origins:
        raise RegistryValidationError(
            f"binding provider registration {registration.kind.value!r} permits no terminal origin class",
            context={"kind": registration.kind.value},
        )


def _require_disposition_matches_route(registration: BindingProviderRegistration) -> None:
    if isinstance(registration.route, RouteOwnership):
        is_pseudo = registration.route.resolver_id in _PSEUDO_OWNER_RESOLVER_IDS
        if is_pseudo != (registration.disposition == "non_runtime"):
            raise RegistryValidationError(
                f"binding provider registration {registration.kind.value!r} pairs disposition "
                f"{registration.disposition!r} with resolver {registration.route.resolver_id!r}",
                context={"kind": registration.kind.value, "disposition": registration.disposition},
            )
        return
    if registration.disposition == "filing_grade":
        raise RegistryValidationError(
            f"binding provider registration {registration.kind.value!r} claims filing grade without a route owner",
            context={"kind": registration.kind.value},
        )
    if not registration.route.owner:
        raise RegistryValidationError(
            f"binding provider registration {registration.kind.value!r} declares no owner for its missing route",
            context={"kind": registration.kind.value},
        )


def _require_one_registration_per_pseudo_owner(registrations: tuple[BindingProviderRegistration, ...]) -> None:
    for resolver_id in sorted(_PSEUDO_OWNER_RESOLVER_IDS):
        claimants = tuple(
            registration
            for registration in registrations
            if isinstance(registration.route, RouteOwnership) and registration.route.resolver_id == resolver_id
        )
        if len(claimants) != 1:
            raise RegistryValidationError(
                f"binding provider pseudo-owner {resolver_id!r} must be claimed by exactly one registration",
                context={"resolver_id": resolver_id, "claimants": len(claimants)},
            )


def validate_binding_provider_registrations(
    registrations: tuple[BindingProviderRegistration, ...],
) -> Mapping[BindingSourceKind, BindingProviderRegistration]:
    """Refuse an incomplete, duplicated, or self-contradicting registration table.

    Returns the frozen kind-keyed view the accessors read, so the only way to
    obtain a usable table is to pass these checks.
    """
    _require_no_duplicate_kinds(registrations)
    _require_complete_union_coverage(registrations)
    _require_one_registration_per_pseudo_owner(registrations)
    for registration in registrations:
        _require_provider_model_identity(registration)
        _require_declared_content(registration)
        _require_channel_shape(registration)
        _require_disposition_matches_route(registration)
    return MappingProxyType({registration.kind: registration for registration in registrations})


BINDING_PROVIDER_REGISTRATIONS: Final[Mapping[BindingSourceKind, BindingProviderRegistration]] = (
    validate_binding_provider_registrations(_REGISTRATIONS)
)
"""The canonical enrollment authority, one row per provider union member."""


AUTHORED_LAYOUT_INTEGER_FIELD_NAMES: Final[frozenset[str]] = frozenset({"offset", "length", "decimals"})
"""Provider field names whose integer is a record-layout fact, not a filing coordinate.

``offset``, ``length`` and ``decimals`` describe where a value sits in an
official fixed-width record and how it is written, which is authored design data
that does not change with the filing context. Every other integer on a provider
member would pin the declaration to one concrete year, revision, or date, and is
refused. The list is explicit so that adding a fourth is a deliberate decision
with a stated reason rather than a field that slipped through.
"""

TEMPORAL_PROVIDER_FIELD_NAME: Final[str] = "temporal"
"""The one provider field allowed to carry numbers that move with the context.

The temporal union is where a relative coordinate is *supposed* to live: its
members carry offsets and spans that are resolved against the target filing
context. The guard therefore skips this field rather than descending into it.
"""


def _absolute_coordinate_leaves(annotation: object) -> bool:
    """Return whether one resolved annotation pins a concrete filing coordinate.

    Unwraps ``Annotated``, optionals and unions, then recognises the four shapes
    that name a coordinate rather than describe one: a plain ``int``, the
    ``RevisionId`` alias, a ``date``, and a ``Literal`` whose members are ints.
    ``bool`` is a subclass of ``int`` in Python but names a flag, not a
    coordinate, so it is not treated as one.
    """
    if annotation is RevisionId:
        return True
    origin = get_origin(annotation)
    if origin is Literal:
        return any(isinstance(arg, int) and not isinstance(arg, bool) for arg in get_args(annotation))
    if origin is not None:
        return any(_absolute_coordinate_leaves(arg) for arg in get_args(annotation))
    if not isinstance(annotation, type):
        return False
    if issubclass(annotation, bool):
        return False
    return issubclass(annotation, (int, date))


def absolute_coordinate_offenders(label: str, model: type[BaseModel]) -> tuple[str, ...]:
    """Return one diagnostic per field of ``model`` that pins a filing coordinate.

    Pure and model-agnostic, so the guard can be exercised against a fabricated
    provider class without touching the enrolled table.
    """
    return tuple(
        f"{label} declares absolute coordinate field {name!r}"
        for name, field_info in sorted(model.model_fields.items())
        if name != TEMPORAL_PROVIDER_FIELD_NAME
        and name not in AUTHORED_LAYOUT_INTEGER_FIELD_NAMES
        and _absolute_coordinate_leaves(field_info.annotation)
    )


def require_relative_provider_coordinates(
    registrations: Mapping[BindingSourceKind, BindingProviderRegistration] | None = None,
) -> None:
    """Refuse any registered provider member that pins a concrete filing coordinate.

    A binding declares timeless intent and derives its source coordinate from the
    target filing context at resolve time. The check is structural and runs over
    the *models* at import: it does not enumerate forbidden field names, so a
    newly added year, revision or date field is refused on the shape of its type
    rather than on whether anyone remembered to name it.

    Raises:
        RegistryValidationError: A registered provider member declares such a field.
    """
    table = BINDING_PROVIDER_REGISTRATIONS if registrations is None else registrations
    offenders: list[str] = []
    for kind, registration in table.items():
        offenders.extend(absolute_coordinate_offenders(f"provider {kind.value!r}", registration.provider_model))
    if offenders:
        raise RegistryValidationError(
            "binding providers must stay relative to the target filing context: " + "; ".join(sorted(offenders)),
            context={"offenders": "; ".join(sorted(offenders))},
        )


require_relative_provider_coordinates()


def registration_for(kind: BindingSourceKind) -> BindingProviderRegistration:
    """Return the registration for one provider kind.

    Raises:
        RegistryValidationError: The kind is not a member of the provider union,
            which the discriminated union has already refused at construction;
            reaching this means a caller invented a kind.
    """
    registration = BINDING_PROVIDER_REGISTRATIONS.get(kind)
    if registration is None:
        raise RegistryValidationError(
            f"binding provider kind {kind.value!r} has no registration",
            context={"kind": kind.value},
        )
    return registration


def validator_for(kind: BindingSourceKind) -> BindingProviderValidator | None:
    """Return the build-time validator enrolled for one provider kind, if it has one.

    ``None`` is the enrolled answer for a family whose provider member is its own
    complete gate, not a missing registration: a kind with no row cannot reach
    here at all.
    """
    return registration_for(kind).validator


def provider_model_for(kind: BindingSourceKind) -> type[BaseModel]:
    """Return the provider union member model enrolled for one provider kind."""
    return registration_for(kind).provider_model


def validate_binding_against_registration(binding: BindingDefinition) -> tuple[str, ...]:
    """Return the diagnostics a binding earns against its kind's registration.

    Checks only what the registration is the authority for -- the value channel,
    the aggregation operation, the scalar/rows agreement between the two, and
    the terminal-origin classes the family can actually produce. Provider shape
    stays with the family validator, which owns it.
    """
    registration = registration_for(binding.source)
    diagnostics: list[str] = []
    channel = binding.value.channel
    if channel not in registration.permitted_value_channels:
        permitted = ", ".join(sorted(member.value for member in registration.permitted_value_channels))
        diagnostics.append(
            f"binding {binding.id!r}: provider {registration.kind.value!r} does not produce the "
            f"{channel.value!r} value channel (permitted: {permitted})",
        )
    aggregation = binding.aggregation
    if aggregation is not None:
        op = aggregation.op
        if op not in registration.permitted_aggregation_ops:
            permitted = ", ".join(sorted(member.value for member in registration.permitted_aggregation_ops))
            diagnostics.append(
                f"binding {binding.id!r}: provider {registration.kind.value!r} does not support the "
                f"{op.value!r} aggregation operation (permitted: {permitted})",
            )
        if op is BindingAggregationOp.ROWS and channel is not BindingValueChannel.ROW_SET:
            diagnostics.append(
                f"binding {binding.id!r}: the {BindingAggregationOp.ROWS.value!r} aggregation operation "
                f"requires the {BindingValueChannel.ROW_SET.value!r} value channel, not {channel.value!r}",
            )
        if op is not BindingAggregationOp.ROWS and channel is BindingValueChannel.ROW_SET:
            diagnostics.append(
                f"binding {binding.id!r}: the {BindingValueChannel.ROW_SET.value!r} value channel "
                f"requires the {BindingAggregationOp.ROWS.value!r} aggregation operation, not {op.value!r}",
            )
    expected_grouping = registration.row_grouping
    declared_grouping = binding.value.row_grouping
    if channel is BindingValueChannel.ROW_SET:
        if expected_grouping is None and declared_grouping is not None:
            diagnostics.append(
                f"binding {binding.id!r}: provider {registration.kind.value!r} emits provider-native rows "
                f"and must not declare row grouping {declared_grouping.value!r}",
            )
        elif expected_grouping is not None and declared_grouping is None:
            diagnostics.append(
                f"binding {binding.id!r}: grouped provider {registration.kind.value!r} must declare "
                f"row grouping {expected_grouping.value!r}",
            )
        elif (
            expected_grouping is not None
            and declared_grouping is not None
            and declared_grouping is not expected_grouping
        ):
            diagnostics.append(
                f"binding {binding.id!r}: provider {registration.kind.value!r} must use row grouping "
                f"{expected_grouping.value!r}, not {declared_grouping.value!r}",
            )
    for expectation in binding.terminal_origins:
        if expectation.source_class not in registration.permitted_terminal_origins:
            permitted = ", ".join(sorted(member.value for member in registration.permitted_terminal_origins))
            diagnostics.append(
                f"binding {binding.id!r}: provider {registration.kind.value!r} cannot rest on terminal origin "
                f"{expectation.source_class.value!r} (permitted: {permitted})",
            )
    return tuple(diagnostics)
