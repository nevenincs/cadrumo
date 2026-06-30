"""Core aggregation taxonomy shared across registry, application, and adapters.

This module owns closed value sets and tiny pydantic carriers only; it does not
aggregate ledger rows, calculate casilla values, or perform source resolution.
The registry schema imports :class:`BindingAggregation`,
:class:`RelationAggregation`, and :class:`BindingSourceKind` to validate TOML
authoring input. Application resolvers and adapters import the same
:class:`BindingSourceKind` members so source tokens do not drift through bare
strings.

Keep the three axes separate:

- :class:`BindingAggregationOp` governs how a
  ``DataBindingDefinition.aggregation`` folds selected binding values.
- :class:`RelationAggregationOp` governs cross-modelo relation fold-ins.
- :class:`RowSetGroupingKind` is the downstream row-assembly grouping axis, not
  a binding ``source`` token; use
  :data:`ROW_SET_GROUPING_FOR_BINDING_SOURCE` only where a detail-record binding
  source must be projected into the row assembler.
"""

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


class RelationAggregationOp(StrEnum):
    """Closed set of aggregation operators a registry ``RelationDefinition`` may declare.

    A relation's ``aggregation.op`` selects how a cross-modelo fold-in folds its
    matched source filings: :attr:`COPY` carries a single source value through
    unchanged (the default when a relation declares no aggregation), and
    :attr:`SUM` adds the matched per-period source values (annual summaries). This
    is a deliberately separate axis from :class:`BindingAggregationOp` (which
    governs ``DataBindingDefinition`` folds and carries the binding-only ``rows``
    / ``count_distinct`` / ``prior_pagos_fraccionados`` members); the two are not
    interchanged. The complete set declared across the registry relation tree is
    ``copy`` and ``sum``.
    """

    COPY = "copy"
    SUM = "sum"


class RelationAggregation(BaseModel):
    """Typed aggregation rule carried by a registry ``RelationDefinition``.

    Placed in :mod:`aeat.core` (cross-layer home) because the domain registry
    schema declares the field and the application/adapter layers read it. The
    closed :class:`RelationAggregationOp` set is the only key real relation
    aggregation mappings carry in the registry authoring tree (every relation
    declares ``aggregation = {op = "copy" | "sum"}`` or none). The model is strict
    and frozen, matching the registry schema's
    :data:`~aeat.core.STRICT_FROZEN_CONFIG` convention, so an unknown ``op`` or a
    stray extra key is rejected at registry-build validation rather than silently
    re-parsed at resolve time. This is the relation sibling of
    :class:`BindingAggregation`; the two op axes are deliberately separate.
    """

    model_config = STRICT_FROZEN_CONFIG

    op: RelationAggregationOp

    @field_validator("op", mode="before")
    @classmethod
    def _coerce_op(cls, value: object) -> object:
        """Hydrate the registry TOML's raw ``op`` string into its enum member.

        The authoring tree declares ``aggregation.op`` as a plain string
        (``"copy"``, ``"sum"``). Under the strict model config a ``StrEnum`` field
        requires the actual member, not its value, so the raw string from
        ``model_validate`` would be rejected. Coercing the known closed-set string
        to its :class:`RelationAggregationOp` member at the boundary keeps the TOML
        plain while preserving strict rejection of an unknown op
        (``RelationAggregationOp(value)`` raises on an invalid value).
        """
        if isinstance(value, str) and not isinstance(value, RelationAggregationOp):
            return RelationAggregationOp(value)
        return value


class PeriodKind(StrEnum):
    """Authoritative period cadences shared across aggregation and deadline layers.

    Placed in :mod:`aeat.core` (cross-layer home) so the deadline domain and
    application aggregation layer can both import without violating the
    hexagonal direction (domain → core is always legal; domain → application
    is forbidden).

    This lightweight cadence enum is an aggregation/deadline taxonomy, not the
    public :class:`aeat.core.Period` classifier. Concrete filing-period values
    should use :class:`aeat.core.Period` and its exported ``PeriodKind``, which
    also distinguishes instalment and extended registry tokens.
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
    """The single canonical closed set of binding/source-mesh tokens.

    Every :class:`~aeat.domain.calculations.registry.DataBindingDefinition`
    declares exactly one ``source`` drawn from the registry-declared subset of
    this enum. The same enum also carries mesh-only source decisions such as
    :attr:`BORRADOR` and :attr:`IVA_WALLET_DECISION`, which are resolved before a
    registry binding is constructed and are parity-accounted as non-registry
    members. Per-family frozensets (invoice, ledger, counterpart) are
    **derived** from this enum rather than hand-maintained, so a new source token
    is added in exactly one place.

    BEHAVIOUR-PRESERVING LIFT: every member's string VALUE equals the source
    token that was previously a bare string (or a :class:`RowSetGroupingKind`
    member) in the ``DataBindingDefinition.source`` Literal. Those tokens live in
    registry TOML and may be persisted; a :class:`~enum.StrEnum` serialises to its
    value, so folding the mixed Literal onto this enum changes the static type
    without changing any stored or compared string (the modelo-enum-hardening
    precedent). Do NOT rename a stored token.

    This enum is the single canonical source-kind authority across BOTH the
    registry binding definitions AND the application resolver mesh (phase-2.1
    taxonomy unification): the counterpart subset (:data:`COUNTERPART_SOURCE_KINDS`)
    is derived from it, and the two grouping members reuse :class:`RowSetGroupingKind`
    values so the cross-layer aggregation taxonomy stays consistent; see
    :data:`ROW_SET_GROUPING_FOR_BINDING_SOURCE` for the detail-record
    source-token ↔ grouping-axis mapping.
    """

    # Profile / cross-filing / relation / manual scalar sources.
    PROFILE = "profile"
    PREVIOUS_FILING = "previous_filing"
    RELATION_PREFILL = "relation_prefill"
    MANUAL_INPUT = "manual_input"
    # Ledger-aggregation sources (all five ledger kinds).
    LEDGER_OSS_AGGREGATION = "ledger_oss_aggregation"
    LEDGER_IVA_AGGREGATION = "ledger_iva_aggregation"
    LEDGER_RENTA_EXPENSE_AGGREGATION = "ledger_renta_expense_aggregation"
    LEDGER_RENTA_INCOME_AGGREGATION = "ledger_renta_income_aggregation"
    # Modelo 130 pago-fraccionado deductible-expense (casilla 02 "Gastos")
    # cumulative aggregation. The OUTGOING sibling of
    # ``ledger_renta_income_aggregation``: the same lightweight ledger-projection
    # mechanism and cumulative year-to-date window, applied to the expense
    # dimension. Spanish stem ``gasto`` per the AEAT casilla 02 "Gastos" surface
    # (aeat-spanish-stem-naming); the M100 first-slice annual-expense source
    # ``ledger_renta_expense_aggregation`` is a constraint-shape-divergent
    # mechanism (invoice-evidence + category-profile + annual-window) and is
    # deliberately not reused for the M130 quarterly cumulative gasto sum.
    LEDGER_RENTA_GASTO_AGGREGATION = "ledger_renta_gasto_aggregation"
    # Per-perceptor retención aggregation: the calc-mesh source that reads the
    # dedicated per-perceptor retención store (RETENCION_OBSERVATIONS_NAMESPACE,
    # operator-supplied — NOT the bucket ledger, so deliberately NOT in
    # LEDGER_BINDING_SOURCE_KINDS and NOT carrying the ``ledger_`` prefix) and
    # materialises the Modelo 180/193 "número total de perceptores" count via
    # the validated distinct-NIF primitive (aggregate_retenciones_180.
    # total_perceptors) — replacing the wrong sum-of-quarterly-M115-counts relation
    # (RET-1, ADR 2026-06-24-retenciones-perceptor-count-adr).
    RETENCIONES_AGGREGATION = "retenciones_aggregation"
    # Modelo 390 year-end IVA compensation carry partition: reads filed Modelo
    # 303 compensation states and materialises AEAT boxes 97 / 662 together from
    # the FIFO carry projection. This is a registry-declared source because the
    # two annual boxes are not independent relation copy/sum folds.
    IVA_COMPENSATION_ANNUAL_PARTITION = "iva_compensation_annual_partition"
    # Mesh-only sourcing decisions with NO registry binding declaration. Both are
    # resolved by a pre-mesh gate, not a registry `DataBindingDefinition.source`:
    # `borrador` materialises the Modelo 100 borrador prefill
    # (Modelo100BorradorSourceResolver) and `iva_wallet_decision` carries the M303
    # IVA-wallet compensación decision (IvaWalletDecisionSourceResolver). They are
    # first-class members of the canonical union (phase-2.1 taxonomy unification)
    # so the mesh carries `BindingSourceKind` members rather than bare strings;
    # because no registry binding declares them, they are accounted for as
    # mesh-only in the enum↔registry parity gate, not as reserved-undeclared.
    BORRADOR = "borrador"
    IVA_WALLET_DECISION = "iva_wallet_decision"
    # Invoice / counterpart aggregation sources.
    PAYABLE_INVOICE = "payable_invoice"
    COLLECTIBLE_INVOICE = "collectible_invoice"
    LEDGER_TRANSACTION = "ledger_transaction"
    PURCHASE_INVOICE_EVIDENCE = "purchase_invoice_evidence"
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


type CounterpartSourceKind = Literal[
    BindingSourceKind.LEDGER_TRANSACTION,
    BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
    BindingSourceKind.PAYABLE_INVOICE,
    BindingSourceKind.COLLECTIBLE_INVOICE,
]
"""Canonical source-kind subset accepted by counterpart aggregation.

A derived subset of :class:`BindingSourceKind` (phase-2.1 taxonomy unification):
the counterpart families settle against a transaction, a purchase-invoice
evidence row, or a payable/collectible invoice. Replaces the former
``AggregationSourceKind``-derived subset, which was deleted in the same change.
"""

COUNTERPART_SOURCE_KINDS: Final[frozenset[CounterpartSourceKind]] = frozenset(
    {
        BindingSourceKind.LEDGER_TRANSACTION,
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
        BindingSourceKind.PAYABLE_INVOICE,
        BindingSourceKind.COLLECTIBLE_INVOICE,
    },
)


def counterpart_source_kind(value: object) -> CounterpartSourceKind:
    """Return ``value`` narrowed to the counterpart source-kind subset.

    Args:
        value: A :class:`BindingSourceKind` member or its stored string value.

    Returns:
        The same source kind narrowed to :data:`CounterpartSourceKind` for
        counterpart aggregation inputs.

    Raises:
        ValueError: When ``value`` is not a known :class:`BindingSourceKind`, or
            is known but outside the counterpart subset.
    """
    try:
        source_kind = value if isinstance(value, BindingSourceKind) else BindingSourceKind(value)
    except ValueError as exc:
        raise ValueError(f"unsupported source_kind {value!r}") from exc
    if source_kind in COUNTERPART_SOURCE_KINDS:
        return source_kind
    raise ValueError(
        "unsupported source_kind; use one of ledger_transaction, "
        "purchase_invoice_evidence, payable_invoice, collectible_invoice",
    )


LEDGER_BINDING_SOURCE_KINDS: Final[frozenset[BindingSourceKind]] = frozenset(
    {
        BindingSourceKind.LEDGER_OSS_AGGREGATION,
        BindingSourceKind.LEDGER_IVA_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_EXPENSE_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_GASTO_AGGREGATION,
    },
)
"""Ledger-aggregation binding source kinds (all five), derived from the enum.

Every binding whose ``source`` is a member reads its values from the
bucket-scoped ledger (transaction-classified IVA / OSS aggregation, Renta
first-slice income/expense aggregation, or the M130 pago-fraccionado gasto
cumulative aggregation). Cross-domain consumers route through this frozenset
so the registry stays the single source of truth for ledger readiness.
"""


class BindingTypedEnumKind(StrEnum):
    """The closed set of substrate enum-class names a binding value bridges.

    A :class:`~aeat.domain.calculations.registry.DataBindingDefinition` whose
    value bridges a closed-membership substrate axis declares ``typed_enum`` =
    one of these members. Each value is the NAME of the closed enum class a
    consumer routes the binding value through:

    - ``CENSO_EVENT_KIND`` (``"censo_event_kind"``) — Modelo 036 censo status.
    - ``CCAA`` (``"CCAA"``) — Modelo 100 autonomic-community tax residence.
    - ``ESTIMACION_DIRECTA_MODALIDAD`` (``"EstimacionDirectaModalidad"``) —
      Modelo 100 estimación-directa modality.
    - ``LEGAL_ENTITY_FORM`` (``"LegalEntityForm"``) — Modelo 200 legal form.

    BEHAVIOUR-PRESERVING LIFT: every member's string VALUE equals the
    annotation token that was previously a bare ``str`` in
    ``DataBindingDefinition.typed_enum``. Those tokens live in registry TOML and
    flow through operator-facing surfaces (``bindings list`` table, the
    :class:`ModeloBindingQueryRow` projection, the borrador resolver, the
    Sheets-pull router); a :class:`~enum.StrEnum` serialises to its value, so
    narrowing the field from ``str | None`` to this enum changes the static type
    without changing any stored, compared, or emitted string (the
    modelo-enum-hardening precedent). Do NOT rename a stored token.

    Declared in :mod:`aeat.core` as a closed value set per the architecture
    contract; the loader hydrates the registry TOML's raw token to its member at
    the schema boundary (see
    :meth:`~aeat.domain.calculations.registry.DataBindingDefinition._coerce_typed_enum`).
    It is the closed-set *annotation* on the binding, distinct from the engine
    ``input_channel`` (how a formula consumes the value); a binding may carry a
    ``typed_enum`` yet still be a numeric ``decimal`` channel.
    """

    CENSO_EVENT_KIND = "censo_event_kind"
    CCAA = "CCAA"
    ESTIMACION_DIRECTA_MODALIDAD = "EstimacionDirectaModalidad"
    LEGAL_ENTITY_FORM = "LegalEntityForm"


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


class RetencionClave(StrEnum):
    """Modelo 190 / 193 perceptor clave de percepción (the AEAT clave letter).

    Closed catalogue of the retención perceptor clave codes A-L, grounded in the
    Modelo 190 Diseño de Registros (Orden EHA/3127/2009, actualizada por Orden
    HAC/1431/2025), campo CLAVE DE PERCEPCIÓN: A trabajo (empleados), B
    pensionistas y haberes pasivos, C prestaciones o subsidios por desempleo, D
    prestaciones por desempleo en pago único, E consejeros y administradores, F
    cursos/conferencias/seminarios y obras, G actividades profesionales, H
    actividades agrícolas/ganaderas/forestales y empresariales en estimación
    objetiva, I actividades empresariales / propiedad intelectual e industrial, J
    imputación de rentas por cesión de derechos de imagen, K premios y
    aprovechamientos forestales, L rentas exentas y dietas exceptuadas de gravamen.
    Modelo 193 reuses the A-D letters for its own concepts; the stored clave is the
    LETTER and its per-modelo meaning is context, so a single letter catalogue
    covers both. The member name equals its AEAT clave letter (value byte-identical
    to the stored token). Declared in :mod:`aeat.core` as a closed value set per the
    architecture contract. The M349 / M347 operation "clave" is a DISTINCT taxonomy
    -- see :class:`OperationKind349` / :class:`OperationKind347`, not this enum.
    """

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"
    I = "I"  # noqa: E741 -- AEAT clave letter; the member name IS the canonical token
    J = "J"
    K = "K"
    L = "L"


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
