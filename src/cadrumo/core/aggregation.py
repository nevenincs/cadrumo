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
from decimal import Decimal
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

    Placed in :mod:`core` (cross-layer home) because the domain registry
    schema declares the field and the application/adapter layers read it; the
    closed :class:`BindingAggregationOp` set is the only key real binding
    aggregation mappings carry in the registry authoring tree. The model is
    strict and frozen, matching the registry schema's
    :data:`~core.STRICT_FROZEN_CONFIG` convention, so an unknown ``op`` or
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

    Placed in :mod:`core` (cross-layer home) because the domain registry
    schema declares the field and the application/adapter layers read it. The
    closed :class:`RelationAggregationOp` set is the only key real relation
    aggregation mappings carry in the registry authoring tree (every relation
    declares ``aggregation = {op = "copy" | "sum"}`` or none). The model is strict
    and frozen, matching the registry schema's
    :data:`~core.STRICT_FROZEN_CONFIG` convention, so an unknown ``op`` or a
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

    Placed in :mod:`core` (cross-layer home) so the deadline domain and
    application aggregation layer can both import without violating the
    hexagonal direction (domain → core is always legal; domain → application
    is forbidden).

    This lightweight cadence enum is an aggregation/deadline taxonomy, not the
    public :class:`~core.Period` classifier. Concrete filing-period values
    should use :class:`~core.Period` and its exported ``PeriodKind``, which
    also distinguishes instalment and extended registry tokens.
    """

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class RowSetGroupingKind(StrEnum):
    """Canonical row-set source-kind discriminators for detail-record assembly.

    Placed in :mod:`core` (cross-layer home) because both the application
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
    - ``BindingSourceKind.DONATIVO_DONOR`` (``"donativo_donor"``)
      ↔ ``DONATIVO`` (``"donativo"``)
    """

    WITHHOLDING = "withholding"
    RELATED_PARTY = "related_party"
    FOREIGN_ASSET = "foreign_asset"
    ATRIBUCION = "atribucion"
    REFUND = "refund"
    DONATIVO = "donativo"


class BindingSourceKind(StrEnum):
    """The single canonical closed set of binding/source-mesh tokens.

    Every :class:`~domain.calculations.registry.DataBindingDefinition`
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
    registry binding definitions AND the application resolver mesh: the
    counterpart subset (:data:`COUNTERPART_SOURCE_KINDS`)
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
    # Modelo 151 régimen especial de impatriados (Ley Beckham, art. 93 LIRPF)
    # Spanish-source base aggregation. Reads the bucket ledger like the other
    # ledger-aggregation sources, but its per-row classifier admits INCOMING
    # income ONLY when source_jurisdiction resolves to ES (art. 93.2: the
    # impatriado is taxed by IRNR scope rules, not the art. 8 worldwide base),
    # admits trabajo income (the class the M130 income pipeline excludes), and
    # segregates every foreign-source or jurisdiction-unresolved row as a typed
    # BECKHAM_FOREIGN_SOURCE_SEGREGATED issue (never a silent ES coercion). Feeds
    # impatriado.base-liquidable-general.
    LEDGER_IMPATRIADO_INCOME_AGGREGATION = "ledger_impatriado_income_aggregation"
    # Modelo 210 IRNR explicit-income projection. It owns the gross-income
    # casilla only after a transaction supplies a persisted M210 classification
    # and the calculation selects the matching official tipo-renta code.
    LEDGER_IRNR_INCOME_AGGREGATION = "ledger_irnr_income_aggregation"
    # Per-perceptor retención aggregation: the calc-mesh source that reads the
    # dedicated per-perceptor retención store (RETENCION_OBSERVATIONS_NAMESPACE,
    # operator-supplied — NOT the bucket ledger, so deliberately NOT in
    # LEDGER_BINDING_SOURCE_KINDS and NOT carrying the ``ledger_`` prefix) and
    # materialises the Modelo 180/193 "número total de perceptores" count via
    # the validated distinct-NIF primitive (aggregate_retenciones_180.
    # total_perceptors) — replacing the wrong sum-of-quarterly-M115-counts relation.
    RETENCIONES_AGGREGATION = "retenciones_aggregation"
    # Modelo 390 year-end IVA compensation carry partition: reads filed Modelo
    # 303 compensation states and materialises AEAT boxes 97 / 662 together from
    # the FIFO carry projection. This is a registry-declared source because the
    # two annual boxes are not independent relation copy/sum folds.
    IVA_COMPENSATION_ANNUAL_PARTITION = "iva_compensation_annual_partition"
    # Capital-goods IVA deduction regularización (LIVA arts. 107-110): the source
    # that would materialise Modelo 303 casilla 43 / the Modelo 390 regularización
    # field from the profile-scoped bienes-de-inversión register plus definitive
    # prorrata percentages. It is registry-declared and source-mesh enrolled for
    # the governed M303/M390 binding targets; the separate advisory path remains
    # available for operator review when the definitive prorrata fact is missing
    # or only a non-blocking proposed value can be shown.
    BIENES_INVERSION_REGULARIZACION = "bienes_inversion_regularizacion"
    # Annual prorrata-general regularización por porcentaje definitivo (LIVA arts.
    # 104-105): the source that would materialise Modelo 303 casilla 44 / the
    # Modelo 390 annual regularización field from the provisional percentage
    # (prior-year definitive, art. 105.Uno) applied across the year and the
    # current-year definitive percentage (art. 104) over full-year volumes.
    # Registry-declared live mesh source once the provisional-carry store and Q4
    # regularisation path are proven end to end.
    PRORRATA_REGULARIZACION = "prorrata_regularizacion"
    # Mesh-only sourcing decisions with NO registry binding declaration. Both are
    # resolved by a pre-mesh gate, not a registry `DataBindingDefinition.source`:
    # `borrador` materialises the Modelo 100 borrador prefill
    # (Modelo100BorradorSourceResolver) and `iva_wallet_decision` carries the M303
    # IVA-wallet compensación decision (IvaWalletDecisionSourceResolver). They are
    # first-class members of the canonical union, so the mesh carries
    # `BindingSourceKind` members rather than bare strings;
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
    # RowSetGroupingKind value; the other four carry their distinct
    # source-token value (see ROW_SET_GROUPING_FOR_BINDING_SOURCE).
    WITHHOLDING = RowSetGroupingKind.WITHHOLDING.value
    FOREIGN_ASSET = RowSetGroupingKind.FOREIGN_ASSET.value
    RELATED_PARTY_OPERATION = "related_party_operation"
    ATRIBUCION_MEMBER = "atribucion_member"
    REFUND_OPERATION = "refund_operation"
    # Modelo 182 (Ley 49/2002 art. 24, Orden EHA/3021/2007) per-donor register:
    # the "registro tipo 2" detail row carrying the donor's NIF, importe
    # donado, porcentaje de deducción aplicable, and the recurrencia flag
    # (donativo plurianual a la misma entidad, LIRPF art. 68.3 / LIS art. 20).
    # No live resolver yet - Sheets-pull-only, the same deferred shape as the
    # sibling detail-record families (ATRIBUCION_MEMBER, RELATED_PARTY_OPERATION,
    # REFUND_OPERATION); the latter two remain registered in DEFERRED_SOURCE_KINDS
    # (application/aggregation/_source_mesh.py).
    DONATIVO_DONOR = "donativo_donor"


ROW_SET_GROUPING_FOR_BINDING_SOURCE: Final[Mapping[BindingSourceKind, RowSetGroupingKind]] = MappingProxyType(
    {
        BindingSourceKind.WITHHOLDING: RowSetGroupingKind.WITHHOLDING,
        BindingSourceKind.FOREIGN_ASSET: RowSetGroupingKind.FOREIGN_ASSET,
        BindingSourceKind.RELATED_PARTY_OPERATION: RowSetGroupingKind.RELATED_PARTY,
        BindingSourceKind.ATRIBUCION_MEMBER: RowSetGroupingKind.ATRIBUCION,
        BindingSourceKind.REFUND_OPERATION: RowSetGroupingKind.REFUND,
        BindingSourceKind.DONATIVO_DONOR: RowSetGroupingKind.DONATIVO,
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

A derived subset of :class:`BindingSourceKind`: the counterpart families
settle against a transaction, a purchase-invoice
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
    source
    for source in BindingSourceKind
    if source.value.startswith("ledger_") and source is not BindingSourceKind.LEDGER_TRANSACTION
)
"""Ledger-aggregation binding source kinds (all seven), derived from the enum.

Every binding whose ``source`` is a member reads its values from the
bucket-scoped ledger (transaction-classified IVA / OSS aggregation, Renta
first-slice income/expense aggregation, the M130 pago-fraccionado gasto
cumulative aggregation, or the M151 impatriado Spanish-source base
aggregation, M151 impatriado income, or M210 explicit IRNR income). The
``ledger_`` namespace derives the set directly from the canonical enum;
``ledger_transaction`` remains a counterpart source rather than a ledger
aggregation. Cross-domain consumers route through this frozenset
so the registry stays the single source of truth for ledger readiness.
"""


class BindingTypedEnumKind(StrEnum):
    """The closed set of substrate enum-class names a binding value bridges.

    A :class:`~domain.calculations.registry.DataBindingDefinition` whose
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
    :class:`~domain.calculations.registry._query_reports.ModeloBindingQueryRow`
    projection, the borrador resolver, the Sheets-pull router); a
    :class:`~enum.StrEnum` serialises to its value, so
    narrowing the field from ``str | None`` to this enum changes the static type
    without changing any stored, compared, or emitted string (the
    modelo-enum-hardening precedent). Do NOT rename a stored token.

    Declared in :mod:`core` as a closed value set per the architecture
    contract; the loader hydrates the registry TOML's raw token to its member at
    the schema boundary (see
    :meth:`~domain.calculations.registry.DataBindingDefinition._coerce_typed_enum`).
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
    :mod:`core` as a closed value set per the architecture contract.

    ``WORK_INCOME`` and ``WORK_INCOME_DIRECTOR`` both fold into the Modelo 111
    *rendimientos del trabajo* block (casillas 01-06) — the form carries a
    single trabajo block and does not split them — but they carry distinct
    statutory retención treatments (Modelo 190 separates them by clave A vs E):
    ``WORK_INCOME`` (ordinary empleados) follows the personalised progressive
    procedure of LIRPF art. 101.1; ``WORK_INCOME_DIRECTOR`` (administradores y
    miembros de consejos de administración) follows the FIXED rate of LIRPF
    art. 101.2. See :func:`work_income_retencion_treatment`.
    """

    # Modelo 111 schemes (quarterly retenciones IRPF on labor + activities)
    WORK_INCOME = "rendimientos_trabajo"  # clave A (empleados, escala progresiva art 101.1)
    WORK_INCOME_DIRECTOR = "rendimientos_trabajo_administrador"  # clave E (administrador, tipo fijo art 101.2)
    ECONOMIC_ACTIVITY = "actividades_economicas"  # clave G
    PROFESSIONAL = "actividades_profesionales"  # clave H (subset of G)
    PRIZE = "premios"  # clave I (lottery, prize)
    # Modelo 115 schemes (urban rental withholding)
    URBAN_RENTAL = "arrendamiento_urbano"  # locales de negocio
    # Modelo 123 schemes (capital mobiliario, dividends, interest)
    CAPITAL_INTEREST = "intereses"  # clave I (interest income)
    CAPITAL_DIVIDEND = "dividendos"  # clave A (dividend income)
    CAPITAL_OTHER = "otros_capital_mobiliario"  # clave C (other capital income)


#: FIXED retención rate on rendimientos del trabajo perceived "por la condición de
#: administradores y miembros de los consejos de administración, de las juntas que
#: hagan sus veces, y demás miembros de otros órganos representativos". Binding
#: provision: LIRPF art. 101.2 (Ley 35/2006, BOE-A-2006-20764), developed by RIRPF
#: art. 80.1.3.º (RD 439/2007). Confirmed against the bundled consolidated LIRPF
#: art-101 corpus ("será del 35 por ciento"). This is the GENERAL fixed tipo —
#: distinct from the personalised progressive escala of art. 101.1 (19/24/30/37/45/47
#: por ciento) that applies to ordinary empleados.
ADMINISTRADOR_RETENCION_RATE: Final[Decimal] = Decimal("0.35")

#: REDUCED fixed retención rate that replaces the 35 % when the administrador/consejero
#: rendimientos proceed from "entidades con un importe neto de la cifra de negocios
#: inferior a 100.000 euros". Binding provision: LIRPF art. 101.2 segundo inciso
#: (Ley 35/2006), developed by RIRPF art. 80.1.3.º. Confirmed against the bundled
#: consolidated LIRPF art-101 corpus ("el porcentaje de retención e ingreso a cuenta
#: será del 19 por ciento").
ADMINISTRADOR_RETENCION_REDUCED_RATE: Final[Decimal] = Decimal("0.19")

#: LIRPF art. 101.2 INCN ceiling: the reduced 19 % administrador rate applies iff the
#: paying entity's importe neto de la cifra de negocios is STRICTLY below this amount
#: ("inferior a 100.000 euros"); at or above it the general 35 % applies. Binding
#: provision: LIRPF art. 101.2 (Ley 35/2006) / RIRPF art. 80.1.3.º (RD 439/2007).
ADMINISTRADOR_RETENCION_REDUCED_INCN_THRESHOLD_EUR: Final[Decimal] = Decimal("100000")


class WorkIncomeRetencionTreatment(BaseModel):
    """Statutory retención treatment for a rendimientos-del-trabajo scheme.

    Separates the personalised progressive procedure the law applies to ordinary
    empleados (LIRPF art. 101.1, developed by RIRPF arts. 80/82-86) from the FIXED
    rate LIRPF art. 101.2 sets for administradores y miembros de consejos de
    administración. ``is_fixed_rate`` is ``False`` for the progressive empleado
    treatment (the per-perceptor percentage is a personalised computation, so no
    single rate is carried) and ``True`` for the administrador treatment, which
    carries the general fixed rate plus the reduced rate and its INCN threshold.

    A tiny closed carrier per this module's contract; the rate values are the
    grounded module constants (:data:`ADMINISTRADOR_RETENCION_RATE` et al.).
    """

    model_config = STRICT_FROZEN_CONFIG

    scheme: RetencionScheme
    is_fixed_rate: bool
    fixed_rate: Decimal | None = None
    fixed_reduced_rate: Decimal | None = None
    fixed_reduced_incn_threshold_eur: Decimal | None = None
    legal_refs: tuple[str, ...]


_WORK_INCOME_RETENCION_TREATMENTS: Mapping[RetencionScheme, WorkIncomeRetencionTreatment] = MappingProxyType(
    {
        RetencionScheme.WORK_INCOME: WorkIncomeRetencionTreatment(
            scheme=RetencionScheme.WORK_INCOME,
            is_fixed_rate=False,
            legal_refs=("ley-35-2006:art-101", "rd-439-2007:art-80", "rd-439-2007:art-86"),
        ),
        RetencionScheme.WORK_INCOME_DIRECTOR: WorkIncomeRetencionTreatment(
            scheme=RetencionScheme.WORK_INCOME_DIRECTOR,
            is_fixed_rate=True,
            fixed_rate=ADMINISTRADOR_RETENCION_RATE,
            fixed_reduced_rate=ADMINISTRADOR_RETENCION_REDUCED_RATE,
            fixed_reduced_incn_threshold_eur=ADMINISTRADOR_RETENCION_REDUCED_INCN_THRESHOLD_EUR,
            legal_refs=("ley-35-2006:art-101", "rd-439-2007:art-80"),
        ),
    },
)


def work_income_retencion_treatment(scheme: RetencionScheme) -> WorkIncomeRetencionTreatment | None:
    """Return the statutory :class:`WorkIncomeRetencionTreatment` for a work-income scheme.

    Returns ``None`` for non-work-income schemes (actividades, premios, capital,
    arrendamiento), which are not governed by the LIRPF art. 101.1/101.2 trabajo
    procedure. Use it to distinguish the empleado (progressive) treatment from the
    administrador/consejero (fixed art. 101.2) treatment at the operator boundary.
    """
    return _WORK_INCOME_RETENCION_TREATMENTS.get(scheme)


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
    to the stored token). Declared in :mod:`core` as a closed value set per the
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

    Source: AEAT Modelo 347 instrucciones. Declared in :mod:`core` as a
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


class IntracomOperationType(StrEnum):
    """Modelo 349 operation-key letters carried by invoice records."""

    E = "E"
    H = "H"
    M = "M"
    S = "S"
    T = "T"
    R = "R"
    A = "A"
    ADQUISICION_SERVICIOS = "I"
    D = "D"
    C = "C"


class ForeignAssetClass(StrEnum):
    """Modelo 720 asset classes (clave de tipo de bien).

    Source: AEAT Modelo 720 instrucciones. Each clave is declared separately;
    the declarability gate applies the 50,000 EUR floor to the regulatory
    obligation block that contains the class after the aggregator runs.
    Declared in :mod:`core` as a closed value set.
    """

    ACCOUNT = "cuenta_entidad_financiera"  # Modelo 720 clave C
    SECURITY = "valor_derecho_extranjero"  # Modelo 720 clave V
    COLLECTIVE_INVESTMENT = "institucion_inversion_colectiva"  # Modelo 720 clave I
    INSURANCE = "seguro_renta_temporal_vitalicia"  # Modelo 720 clave S
    REAL_ESTATE = "inmueble_derecho_real_extranjero"  # Modelo 720 clave B
    VIRTUAL_CURRENCY = "moneda_virtual"  # Modelo 721 sibling; no Modelo 720 clave
