"""Core aggregation taxonomy shared across application and adapter layers."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Literal

from pydantic import BaseModel, field_validator

from ._models import STRICT_FROZEN_CONFIG
from .logging import get_logger

_log = get_logger(__name__)


class BindingAggregationOp(StrEnum):
    """Closed set of aggregation operators a registry binding may declare.

    A binding's ``aggregation.op`` selects how the resolver folds the selected
    source values into the bound casilla value. The members below are the
    complete set declared on a ``DataBindingDefinition.aggregation`` across the
    registry authoring tree; relation aggregation (``copy``/``sum`` on a
    ``RelationDefinition``) and formula-expression operators are a separate,
    unrelated axis and are not modelled here.

    Members:
        SUM: Add the selected source values (default for the scalar-folding
            families: previous-filing, counterpart, invoice, ledger,
            withholding).
        ROWS: Emit one detail row per selected observation rather than folding
            to a scalar (default for the detail-record families:
            related-party, foreign-asset, atribución, refund).
        COPY: Carry a single source value through unchanged; refuses when more
            than one source value is selected.
        COUNT_DISTINCT: Count the distinct operators/perceptores behind the
            selected observations (e.g. Modelo 349 operator counts).
        PRIOR_PAGOS_FRACCIONADOS: Modelo 130 cumulative pago-fraccionado carry
            that nets the prior positive declaration against the running total.
    """

    SUM = "sum"
    ROWS = "rows"
    COPY = "copy"
    COUNT_DISTINCT = "count_distinct"
    PRIOR_PAGOS_FRACCIONADOS = "prior_pagos_fraccionados"


class BindingAggregation(BaseModel):
    """Typed aggregation rule carried by a registry ``DataBindingDefinition``.

    Placed in :mod:`aeat.core` (cross-layer home) because the domain registry
    schema declares the field and the application/adapter layers read it; the
    closed :class:`BindingAggregationOp` set is the only key real binding
    aggregation mappings carry in the registry authoring tree. The model is
    strict and frozen, matching the registry schema's
    :data:`~aeat.core.STRICT_FROZEN_CONFIG` convention, so an unknown ``op`` or
    a stray extra key is rejected at registry-build validation rather than
    silently re-parsed at resolve time.
    """

    model_config = STRICT_FROZEN_CONFIG

    op: BindingAggregationOp

    @field_validator("op", mode="before")
    @classmethod
    def _coerce_op(cls, value: object) -> object:
        """Hydrate the registry TOML's raw ``op`` string into its enum member.

        The authoring tree declares ``aggregation.op`` as a plain string
        (``"sum"``, ``"copy"``, ...). Under the strict model config a
        ``StrEnum`` field requires the actual member, not its value, so the raw
        string from ``model_validate`` would be rejected. Coercing the known
        closed-set string to its :class:`BindingAggregationOp` member at the
        boundary keeps the TOML plain while preserving strict rejection of an
        unknown op (``BindingAggregationOp(value)`` raises on an invalid value).
        """
        if isinstance(value, str) and not isinstance(value, BindingAggregationOp):
            return BindingAggregationOp(value)
        return value


class AggregationSourceKind(StrEnum):
    """Accepted source-kind taxonomy for per-modelo aggregation providers.

    The retired bare invoice alias was removed during C4 invoice unification.
    Registry bindings and aggregation observations must use one of the
    load-bearing source kinds below; invoice-shaped validators route through the
    canonical payable / collectible / purchase-evidence taxonomy rather than a
    standalone alias.

    Consumer search across ``src/aeat`` on 2026-06-11 found no remaining
    ``AggregationSourceKind.INVOICE`` references after the migration; residual
    ``source="invoice"`` literals are rejection tests only.
    """

    LEDGER_TRANSACTION = "ledger_transaction"
    PURCHASE_INVOICE_EVIDENCE = "purchase_invoice_evidence"
    PAYABLE_INVOICE = "payable_invoice"
    COLLECTIBLE_INVOICE = "collectible_invoice"


type CounterpartSourceKind = Literal[
    AggregationSourceKind.LEDGER_TRANSACTION,
    AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE,
    AggregationSourceKind.PAYABLE_INVOICE,
    AggregationSourceKind.COLLECTIBLE_INVOICE,
]
"""Canonical source-kind subset accepted by counterpart aggregation."""

COUNTERPART_SOURCE_KINDS: Final[frozenset[CounterpartSourceKind]] = frozenset(
    {
        AggregationSourceKind.LEDGER_TRANSACTION,
        AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE,
        AggregationSourceKind.PAYABLE_INVOICE,
        AggregationSourceKind.COLLECTIBLE_INVOICE,
    },
)


def counterpart_source_kind(value: object) -> CounterpartSourceKind:
    """Return ``value`` narrowed to the counterpart source-kind subset."""
    try:
        source_kind = value if isinstance(value, AggregationSourceKind) else AggregationSourceKind(value)
    except ValueError as exc:
        raise ValueError(f"unsupported source_kind {value!r}") from exc
    if source_kind in COUNTERPART_SOURCE_KINDS:
        return source_kind
    raise ValueError(
        "unsupported source_kind; use one of ledger_transaction, "
        "purchase_invoice_evidence, payable_invoice, collectible_invoice",
    )


class PeriodKind(StrEnum):
    """Authoritative period cadences shared across aggregation and deadline layers.

    Placed in :mod:`aeat.core` (cross-layer home) so the deadline domain and
    application aggregation layer can both import without violating the
    hexagonal direction (domain → core is always legal; domain → application
    is forbidden).
    """

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class RowSetGroupingKind(StrEnum):
    """Canonical row-set source-kind discriminators for detail-record assembly.

    Placed in :mod:`aeat.core` (cross-layer home) because both the application
    assembly layer and the domain registry schema reference these values, and
    domain → application imports are forbidden under the hexagonal contract.

    This is the **row-assembly grouping axis** consumed in the application layer
    (`_row_set_assembly.py`), a separate concept from the binding ``source``
    token enumerated by :class:`BindingSourceKind`. For the three detail-record
    families whose grouping member differs from the binding source token, the
    correspondence is intentional and explicit; see
    :data:`ROW_SET_GROUPING_FOR_BINDING_SOURCE`:

    - ``BindingSourceKind.WITHHOLDING`` (``"withholding"``) ↔ ``WITHHOLDING``
    - ``BindingSourceKind.FOREIGN_ASSET`` (``"foreign_asset"``) ↔ ``FOREIGN_ASSET``
    - ``BindingSourceKind.RELATED_PARTY_OPERATION`` (``"related_party_operation"``)
      ↔ ``RELATED_PARTY`` (``"related_party"``)
    - ``BindingSourceKind.ATRIBUCION_MEMBER`` (``"atribucion_member"``)
      ↔ ``ATRIBUCION`` (``"atribucion"``)
    - ``BindingSourceKind.REFUND_OPERATION`` (``"refund_operation"``)
      ↔ ``REFUND`` (``"refund"``)
    """

    WITHHOLDING = "withholding"
    RELATED_PARTY = "related_party"
    FOREIGN_ASSET = "foreign_asset"
    ATRIBUCION = "atribucion"
    REFUND = "refund"


class BindingSourceKind(StrEnum):
    """The single canonical closed set of registry binding ``source`` tokens.

    Every :class:`~aeat.domain.calculations.registry.DataBindingDefinition`
    declares exactly one ``source`` drawn from this enum. The members below are
    the complete set of source tokens declared across the registry authoring
    tree; the per-family frozensets (invoice, ledger, counterpart) are
    **derived** from this enum rather than hand-maintained, so a new source
    token is added in exactly one place.

    BEHAVIOUR-PRESERVING LIFT: every member's string VALUE equals the source
    token that was previously a bare string (or an
    :class:`AggregationSourceKind` / :class:`RowSetGroupingKind` member) in the
    ``DataBindingDefinition.source`` Literal. Those tokens live in registry TOML
    and may be persisted; a :class:`~enum.StrEnum` serialises to its value, so
    folding the mixed Literal onto this enum changes the static type without
    changing any stored or compared string (the modelo-enum-hardening
    precedent). Do NOT rename a stored token.

    The four invoice/counterpart members reuse the :class:`AggregationSourceKind`
    values and the two grouping members reuse :class:`RowSetGroupingKind` values
    so the cross-layer aggregation taxonomy stays consistent; see
    :data:`ROW_SET_GROUPING_FOR_BINDING_SOURCE` for the detail-record
    source-token ↔ grouping-axis mapping.
    """

    # Profile / cross-filing / relation / manual scalar sources.
    PROFILE = "profile"
    PREVIOUS_FILING = "previous_filing"
    RELATION_PREFILL = "relation_prefill"
    MANUAL_INPUT = "manual_input"
    # Ledger-aggregation sources (all four ledger kinds).
    LEDGER_OSS_AGGREGATION = "ledger_oss_aggregation"
    LEDGER_IVA_AGGREGATION = "ledger_iva_aggregation"
    LEDGER_RENTA_EXPENSE_AGGREGATION = "ledger_renta_expense_aggregation"
    LEDGER_RENTA_INCOME_AGGREGATION = "ledger_renta_income_aggregation"
    # Invoice / counterpart aggregation sources (value-aligned with
    # AggregationSourceKind).
    PAYABLE_INVOICE = AggregationSourceKind.PAYABLE_INVOICE.value
    COLLECTIBLE_INVOICE = AggregationSourceKind.COLLECTIBLE_INVOICE.value
    LEDGER_TRANSACTION = AggregationSourceKind.LEDGER_TRANSACTION.value
    PURCHASE_INVOICE_EVIDENCE = AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE.value
    # Detail-record families. WITHHOLDING / FOREIGN_ASSET reuse the
    # RowSetGroupingKind value; the other three carry their distinct
    # source-token value (see ROW_SET_GROUPING_FOR_BINDING_SOURCE).
    WITHHOLDING = RowSetGroupingKind.WITHHOLDING.value
    FOREIGN_ASSET = RowSetGroupingKind.FOREIGN_ASSET.value
    RELATED_PARTY_OPERATION = "related_party_operation"
    ATRIBUCION_MEMBER = "atribucion_member"
    REFUND_OPERATION = "refund_operation"


ROW_SET_GROUPING_FOR_BINDING_SOURCE: Final[Mapping[BindingSourceKind, RowSetGroupingKind]] = MappingProxyType(
    {
        BindingSourceKind.WITHHOLDING: RowSetGroupingKind.WITHHOLDING,
        BindingSourceKind.FOREIGN_ASSET: RowSetGroupingKind.FOREIGN_ASSET,
        BindingSourceKind.RELATED_PARTY_OPERATION: RowSetGroupingKind.RELATED_PARTY,
        BindingSourceKind.ATRIBUCION_MEMBER: RowSetGroupingKind.ATRIBUCION,
        BindingSourceKind.REFUND_OPERATION: RowSetGroupingKind.REFUND,
    },
)
"""Explicit detail-record binding-source ↔ row-assembly grouping correspondence.

The binding ``source`` token (e.g. ``"related_party_operation"``) and the
row-assembly :class:`RowSetGroupingKind` value (e.g. ``"related_party"``) are
distinct strings for the three families whose source token carries the
``_operation`` / ``_member`` suffix; this mapping makes the relationship
explicit so a reader is not misled into assuming the two axes share a value.
"""


INVOICE_BINDING_SOURCE_KINDS: Final[frozenset[BindingSourceKind]] = frozenset(
    {
        BindingSourceKind.COLLECTIBLE_INVOICE,
        BindingSourceKind.PAYABLE_INVOICE,
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
    },
)
"""Invoice-shaped binding source kinds, derived from :class:`BindingSourceKind`."""


LEDGER_BINDING_SOURCE_KINDS: Final[frozenset[BindingSourceKind]] = frozenset(
    {
        BindingSourceKind.LEDGER_OSS_AGGREGATION,
        BindingSourceKind.LEDGER_IVA_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_EXPENSE_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
    },
)
"""Ledger-aggregation binding source kinds (all four), derived from the enum.

Every binding whose ``source`` is a member reads its values from the
bucket-scoped ledger (transaction-classified IVA / OSS aggregation or Renta
first-slice income/expense aggregation). Cross-domain consumers route through
this frozenset so the registry stays the single source of truth for ledger
readiness.
"""


class RetencionScheme(StrEnum):
    """Closed catalogue of retenciones schemes across the retenciones family.

    Each scheme maps to one of the casillas (or grouped casillas) on a
    retenciones modelo form. The mapping from scheme to modelo lives in the
    per-modelo entry-point functions; this enum is the union. Declared in
    :mod:`aeat.core` as a closed value set per the architecture contract.
    """

    # Modelo 111 schemes (quarterly retenciones IRPF on labor + activities)
    WORK_INCOME = "rendimientos_trabajo"  # clave A
    ECONOMIC_ACTIVITY = "actividades_economicas"  # clave G
    PROFESSIONAL = "actividades_profesionales"  # clave H (subset of G)
    PRIZE = "premios"  # clave I (lottery, prize)
    # Modelo 115 schemes (urban rental withholding)
    URBAN_RENTAL = "arrendamiento_urbano"  # locales de negocio
    # Modelo 123 schemes (capital mobiliario, dividends, interest)
    CAPITAL_INTEREST = "intereses"  # clave I (interest income)
    CAPITAL_DIVIDEND = "dividendos"  # clave A (dividend income)
    CAPITAL_OTHER = "otros_capital_mobiliario"  # clave C (other capital income)


class OperationKind347(StrEnum):
    """Modelo 347 operation kinds (clave de operación).

    Source: AEAT Modelo 347 instrucciones. Declared in :mod:`aeat.core` as a
    closed value set per the architecture contract.
    """

    DELIVERY = "entregas_y_prestaciones"  # clave A
    ACQUISITION = "adquisiciones_y_recepciones"  # clave B
    INSURANCE = "operaciones_seguros"  # clave C
    RENTAL = "arrendamientos_locales"  # clave D
    SUBSIDY = "subvenciones_y_ayudas"  # clave E


class OperationKind349(StrEnum):
    """Modelo 349 intracomunitarias operation kinds.

    Source: AEAT Modelo 349 instrucciones. The clave maps from the underlying
    directionality (entrega/adquisición) and operation type (bienes/servicios).
    """

    INTRA_DELIVERY = "entrega_intracomunitaria_bienes"  # clave E
    INTRA_ACQUISITION = "adquisicion_intracomunitaria_bienes"  # clave A
    INTRA_SERVICE_OUT = "prestacion_servicios_intracom"  # clave S
    INTRA_SERVICE_IN = "adquisicion_servicios_intracom"  # clave I
    TRIANGULAR = "triangular"  # clave T


class ForeignAssetClass(StrEnum):
    """Modelo 720 asset classes (clave de tipo de bien).

    Source: AEAT Modelo 720 instrucciones. Each class is declared separately;
    the declarability gate (50,000 EUR per class) is applied after the
    aggregator runs. Declared in :mod:`aeat.core` as a closed value set.
    """

    ACCOUNT = "cuenta_entidad_financiera"  # clave C
    SECURITY = "valor_seguro_renta"  # clave V
    REAL_ESTATE = "inmueble_extranjero"  # clave I
    INSURANCE = "seguro_renta_temporal_vitalicia"  # clave S
    VIRTUAL_CURRENCY = "moneda_virtual"  # clave M
