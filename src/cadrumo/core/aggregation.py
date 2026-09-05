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

from .models import STRICT_FROZEN_CONFIG


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


class AggregationCaptureKind(StrEnum):
    """Which ingestion path wrote a per-perceptor aggregation observation batch.

    CAPTURE PROVENANCE, and a different axis from two neighbours it is easy to
    confuse with. It is not
    :class:`~application.calculations.ObservationSourceKind`, which classifies
    whether a persisted modelo observation is official AEAT filing evidence; and
    it is not the inner ``source_kind`` on a retención observation, which records
    whether the underlying row came from a ledger transaction or a payable
    invoice. All three have worn the name ``source_kind``.

    That distinction was load-bearing before it was enforceable. The two
    aggregation stores are exempt from the official-evidence displacement guard
    precisely BECAUSE no evidence-authority value can reach them, and that
    exemption rested on the field being a free-form ``str`` that happened to
    carry one token. Nothing refused ``"aeat_sede_justificante"`` into either
    store, and on the day something wrote it the exemption would have become
    wrong silently. Typing the axis converts the disjointness from an observation
    about today's content into a load-time refusal.

    One member is not a defect. The set is closed at what the code actually
    produces; a second ingestion path adds its own member here, deliberately,
    rather than arriving as an unreviewed string.
    """

    AGGREGATE_PULL = "aggregate_pull"


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
    GASTO193 = "gasto193"
    WITHHOLDING296 = "withholding296"


class CalculationSourceLineageRole(StrEnum):
    """A persisted source node's role in one resolver-produced provenance graph."""

    PRIMARY = "primary"
    """Durable resolved economic object whose resolver owns the binding source."""

    CONTRIBUTOR = "contributor"
    """Upstream fact linked to, but never substituting for, a primary object."""


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
    # A byte run whose value AEAT fixes in the diseno de registro itself -- the
    # record-type marker, the modelo number, a sheet discriminator. Distinct from
    # MANUAL_INPUT because no operator supplies it: routing a constant through the
    # manual channel makes it answerable-blank, and a blank emits behind a valid
    # digest. The value rides on the binding selector; see design_constant_bindings.
    DESIGN_CONSTANT = "design_constant"
    # Ledger-aggregation sources (all five ledger kinds).
    LEDGER_OSS_AGGREGATION = "ledger_oss_aggregation"
    LEDGER_IVA_AGGREGATION = "ledger_iva_aggregation"
    # Modelo 100 first-slice gastos under estimación directa (LIRPF arts. 28-30),
    # routed per SpendingCategory across the 14 first-slice casillas over the
    # annual (period "0A") window. Carries the invoice-evidence, category-profile
    # deductibility and proportionality machinery the pago-fraccionado sibling
    # below has no use for.
    LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION = "ledger_renta_gastos_estimacion_directa_aggregation"
    LEDGER_RENTA_INCOME_AGGREGATION = "ledger_renta_income_aggregation"
    # Modelo 130 pago-fraccionado deductible gastos (casilla 02 "Gastos")
    # cumulative aggregation. The OUTGOING sibling of
    # ``ledger_renta_income_aggregation``: the same lightweight ledger-projection
    # mechanism and cumulative year-to-date window, applied to the gastos
    # dimension.
    #
    # Both renta gastos sources carry the AEAT "Gastos" stem
    # (aeat-naming) and each is qualified by the régimen it serves,
    # because the M100 first-slice boxes are gastos too (casilla 0203 is "Gastos
    # financieros"): a bare ``gasto`` would not say which régimen it belongs to.
    # ``ledger_renta_gastos_estimacion_directa_aggregation`` stays a separate,
    # constraint-shape-divergent mechanism and is deliberately not reused for
    # this quarterly cumulative sum.
    LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION = "ledger_renta_gastos_pago_fraccionado_aggregation"
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
    # Modelo 390 annual simplified-regime summary: consumes the one immutable,
    # filed-current Modelo 303 4T CalculationRevision and its evidence rather
    # than a scalar observation or relation prefill.  Its 10-box envelope is
    # keyed by canonical M390 CasillaIds and persisted on the target revision.
    M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY = "m303_regimen_simplificado_annual_summary"
    # Capital-goods IVA deduction regularización (LIVA arts. 107-110): the source
    # that would materialise Modelo 303 casilla 43 / the Modelo 390 regularización
    # field from the profile-scoped bienes-de-inversión register plus definitive
    # prorrata percentages. It is registry-declared and source-mesh enrolled for
    # the governed M303/M390 binding targets; the separate advisory path remains
    # available for operator review when the definitive prorrata fact is missing
    # or only a non-blocking proposed value can be shown.
    BIENES_INVERSION_REGULARIZACION = "bienes_inversion_regularizacion"
    # Modelo 100 inventory stock valuation. This source consumes the dedicated,
    # profile-scoped inventory schedule and owns the mutually exclusive 0177 /
    # 0182 projection from audited opening and closing stock. It is deliberately
    # distinct from the transaction-ledger aggregation family and from capital-
    # goods IVA regularisation.
    INVENTORY = "inventory"
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
    # Modelo 347 "operaciones con terceras personas" combined-direction source.
    # RD 1065/2007 art. 33.1 defines the declared population as one
    # undifferentiated concept before any direction split: "tendran la
    # consideracion de operaciones tanto las entregas de bienes y
    # prestaciones de servicios como las adquisiciones de los mismos" -- a
    # sale and a purchase are the SAME "operacion" concept the annual
    # declaration reports, not two. A binding that declares one direction
    # (payable or collectible) while its resolver reads both is untruthful
    # about what it consumes; this member names the combined population the
    # law itself already treats as singular, for bindings whose selector
    # spans both invoice directions (the M347 declarante-summary totals and
    # the per-counterparty contraparte_clave row family). It is invoice-
    # shaped (a member of INVOICE_BINDING_SOURCE_KINDS) and resolved by the
    # same InvoiceCatalogueSourceResolver as PAYABLE_INVOICE/COLLECTIBLE_INVOICE;
    # each underlying InvoiceObservation still carries its own true
    # PAYABLE_INVOICE/COLLECTIBLE_INVOICE direction as its own source_kind, so
    # per-invoice direction (art. 33.1's quarterly separate accounting of
    # entregas y adquisiciones) is never lost, only the BINDING's declared
    # source is honest about spanning both.
    M347_THIRD_PARTY_OPERATION = "m347_third_party_operation"
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
    # Modelo 193 hoja-anexo gastos relationship rows (NIF del contribuyente
    # plus the annual gastos de administracion y deposito amount), the same
    # deferred Sheets-pull-only shape as the donativo family.
    GASTO193_CONTRIBUTOR = "gasto193_contributor"
    # Modelo 296 perceptor rows (IRNR retenciones): its own clave
    # vocabulary (numeric renta claves) cannot ride the shared
    # withholding family's A-L set, so it declares its own detail-record
    # source in the same deferred Sheets-pull-only shape.
    WITHHOLDING296 = "withholding296"


ROW_SET_GROUPING_FOR_BINDING_SOURCE: Final[Mapping[BindingSourceKind, RowSetGroupingKind]] = MappingProxyType(
    {
        BindingSourceKind.WITHHOLDING: RowSetGroupingKind.WITHHOLDING,
        BindingSourceKind.FOREIGN_ASSET: RowSetGroupingKind.FOREIGN_ASSET,
        BindingSourceKind.RELATED_PARTY_OPERATION: RowSetGroupingKind.RELATED_PARTY,
        BindingSourceKind.ATRIBUCION_MEMBER: RowSetGroupingKind.ATRIBUCION,
        BindingSourceKind.REFUND_OPERATION: RowSetGroupingKind.REFUND,
        BindingSourceKind.DONATIVO_DONOR: RowSetGroupingKind.DONATIVO,
        BindingSourceKind.GASTO193_CONTRIBUTOR: RowSetGroupingKind.GASTO193,
        BindingSourceKind.WITHHOLDING296: RowSetGroupingKind.WITHHOLDING296,
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
        BindingSourceKind.M347_THIRD_PARTY_OPERATION,
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

COUNTERPART_SOURCE_KIND_ORDER: Final[tuple[CounterpartSourceKind, ...]] = (
    BindingSourceKind.LEDGER_TRANSACTION,
    BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
    BindingSourceKind.PAYABLE_INVOICE,
    BindingSourceKind.COLLECTIBLE_INVOICE,
)
"""Operator-facing display order for :data:`COUNTERPART_SOURCE_KINDS`.

This is the order the ``--kind`` help text and alias table present to an
operator (documented in ``docs/how-to/review-queue.md``), so it is
authoritative and MUST NOT be reordered incidentally.
:data:`COUNTERPART_SOURCE_KINDS` derives its membership from this tuple so
the two can never drift apart.
"""

COUNTERPART_SOURCE_KINDS: Final[frozenset[CounterpartSourceKind]] = frozenset(COUNTERPART_SOURCE_KIND_ORDER)


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
    if source_kind is BindingSourceKind.LEDGER_TRANSACTION:
        return BindingSourceKind.LEDGER_TRANSACTION
    if source_kind is BindingSourceKind.PURCHASE_INVOICE_EVIDENCE:
        return BindingSourceKind.PURCHASE_INVOICE_EVIDENCE
    if source_kind is BindingSourceKind.PAYABLE_INVOICE:
        return BindingSourceKind.PAYABLE_INVOICE
    if source_kind is BindingSourceKind.COLLECTIBLE_INVOICE:
        return BindingSourceKind.COLLECTIBLE_INVOICE
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
first-slice income and estimación directa gastos aggregation, the M130
pago-fraccionado gastos cumulative aggregation, or the M151 impatriado base
aggregation, M151 impatriado income, or M210 explicit IRNR income). The
``ledger_`` namespace derives the set directly from the canonical enum;
``ledger_transaction`` remains a counterpart source rather than a ledger
aggregation. Cross-domain consumers route through this frozenset
so the registry stays the single source of truth for ledger readiness.
"""


OBSERVATION_BACKED_BINDING_SOURCE_KINDS: Final[frozenset[BindingSourceKind]] = frozenset(
    {
        BindingSourceKind.PREVIOUS_FILING,
        BindingSourceKind.RELATION_PREFILL,
    },
)
"""Binding source kinds whose value is read back from a prior-filed observation.

Both name a figure the taxpayer already declared — a direct same-modelo carry,
or a cross-modelo fold-in materialised into a relation-prefill slot — rather than
a value this application derives. Consumers that must not treat such a value as
independent evidence, or that must not compare it against the observation store
it came from, route through this frozenset.

MEMBERSHIP IS SEMANTIC, NOT LEXICAL, and this is the one per-family collection
that cannot be derived by construction the way
:data:`LEDGER_BINDING_SOURCE_KINDS` is from the ``ledger_`` namespace: the two
members share no naming property, only the behaviour of reading the observation
store. So adding a source kind here is a judgement, and the question to ask is
whether its resolver reads a prior-filed observation — not whether its token
looks like these two. That is stated rather than papered over, because a
hand-listed set that claims to be derived is worse than one that admits it is
not.

DO NOT WIDEN THIS TO THE CARRY-FORWARD OVERRIDE TIER. The caller-override
precedence ladder declares a superset that additionally carries the IVA
compensación annual partition and the prorrata regularización. That is a
different concept — which values an operator override may displace — and folding
it in here silently widens two registry validation guards.
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


class LedgerIncomeGrounding(StrEnum):
    """Whether a ledger income row's contribution rests on declared invoice substrate.

    An actividad-económica income row reaches a modelo income casilla by one of
    two structurally different routes, and the difference is a LEGAL one, not a
    presentation detail:

    - ``SUBSTRATE_DECLARED`` — the row carries an explicit ``taxable_base``
      (the IVA-exclusive base imponible from its invoice). Every income fact
      reads a real declared figure.
    - ``CASH_FALLBACK`` — no base is declared, so the only measure available is
      the raw bank-credited amount. That figure is net of any retención
      practicada and may be IVA-inclusive, so it is neither the ingresos
      íntegros the return asks for nor a base: the ``ingresos_integros_sum``
      fact folds the cash in (mis-measuring in a direction that depends on the
      invoice), while ``taxable_base_sum`` contributes nothing for the row.

    Declared in :mod:`core` as a closed value set per the architecture
    contract, so the domain registry protocol and the application aggregation
    pipeline key on ONE marker rather than each re-deriving the distinction
    from ``taxable_base_amount is None``. Consumers must branch on the member,
    never on field-nullness: the marker is the fact.
    """

    SUBSTRATE_DECLARED = "substrate_declared"
    CASH_FALLBACK = "cash_fallback"


class InvoiceDevengoRank(StrEnum):
    """Which source produced the LIVA art. 75 devengo date an invoice files under.

    Period attribution -- which quarter a cuota is declared in, which filing
    year an annual reconciliation sees -- resolves on the art. 75 devengo date.
    That date is when the operation occurred, and the invoice date appears
    nowhere in art. 75.Uno: a B2B invoice may be issued up to the fifteenth of
    the following month while still belonging to the earlier period, so the
    issue date is wrong at exactly the month and quarter boundaries where
    attribution changes.

    A fallback chain therefore cannot hand back a bare date. The two ranks
    below are not two spellings of one answer: one is a fact the taxpayer
    recorded, the other is a substitute that is right most of the time and
    wrong precisely where it matters. Returning them undifferentiated would let
    a consumer treat the substitute as the fact, which is the mistake the
    marker exists to prevent.

    Declared in :mod:`core` as a closed value set per the architecture
    contract, beside :class:`LedgerIncomeGrounding`, which answers the parallel
    question for the income measure. Consumers must branch on the member, never
    on ``operation_date is None``: the marker is the fact.

    D10's third named rank -- the bank movement date -- is NOT a member here.
    An invoice always carries an issue date, so the invoice-side chain
    terminates at :attr:`ISSUE_DATE_PROXY` and can never reach a movement date;
    the movement-date substitution belongs to the ledger-transaction side,
    whose dates have their own owners in
    :mod:`cadrumo.domain.transactions.dates`. Declaring a member no producer
    on this axis can emit would be dead capacity wearing the shape of coverage.
    """

    OPERATION_DATE_DECLARED = "operation_date_declared"
    """The invoice records its own devengo-relevant date and it was used.

    Covers both art. 75 clauses: the general-regime operation date
    (art. 75.Uno) and a pago anticipado's collection date (art. 75.Dos). Which
    clause supplied it is a separate axis, recorded on the invoice's own
    ``operation_date_role``; this marker answers only whether the date is a
    declared fact or a substitute.
    """

    ISSUE_DATE_PROXY = "issue_date_proxy"
    """No devengo date was recorded, so the issue date stood in for it.

    The attribution is a best available guess, not a legal determination. It
    agrees with the declared fact for every operation invoiced in its own
    period and diverges exactly at the boundary cases, so a period whose
    figures rest on this rank is one an operator should be told about.
    """


class LedgerWithholdingDerivation(StrEnum):
    """How a ledger income row's retención figure was arrived at.

    A ledger row never *declares* its retención -- no transaction field records
    one -- so every non-zero figure on this surface is derived, and the reader
    needs to know from what. Without the marker three structurally different
    situations are one indistinguishable ``Decimal("0")``: a row that genuinely
    had nothing withheld, a row whose substrate was too thin to tell, and a row
    whose arithmetic implied a withholding so large the figure was refused. The
    last is the dangerous one, because a refused inference and a real zero look
    identical in the sum.

    Declared in :mod:`core` as a closed value set per the architecture
    contract, beside :class:`LedgerIncomeGrounding`, which answers the parallel
    question for the income measure.
    """

    NOT_APPLICABLE = "not_applicable"
    """The row is not an actividad-económica receipt, so no retención arises."""

    NO_SUBSTRATE = "no_substrate"
    """No base is declared, or the cuota is not determinable from what is.

    The withholding is unknown, not zero. The row still contributes its cash to
    the income measure, so it under-claims the offsetting credit.
    """

    NONE_WITHHELD = "none_withheld"
    """Substrate sufficed and the cash covers the invoice: nothing was withheld."""

    DECLARED_ON_LINKED_INVOICE = "declared_on_linked_invoice"
    """Read from the retención the linked sales invoice itself declares.

    The strongest source available: the figure the document states, not one
    reconstructed from what reached the bank. Preferred over every inference
    below it, because a declared figure beats a derived one.
    """

    INFERRED_FROM_DECLARED_CUOTA = "inferred_from_declared_cuota"
    """Derived as invoice gross minus cash, with the cuota read from the row."""

    INFERRED_FROM_CATEGORY_ZERO_CUOTA = "inferred_from_category_zero_cuota"
    """Derived the same way, with the cuota taken as zero because the declared
    IVA category makes it zero by law.

    This is what lets an IVA-exempt professional service recover its retención:
    the operation has no cuota to record, so requiring a recorded one excluded
    precisely the invoices whose withholding matters most.
    """

    REFUSED_ABOVE_SUPPORTED_RATE = "refused_above_supported_rate"
    """The inference exceeded the registry maximum supported rate and was dropped.

    An implied withholding above the RIRPF art. 95.1 general rate is evidence
    that the recorded cash is the base without IVA rather than a net-of-retención
    payment. Emitting the figure anyway would persist a fabricated withholding;
    capping it at the bound would invent one at exactly the legal maximum. The
    figure is therefore zero and this marker says why.
    """


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


class WorkIncomeRetencionTreatment(BaseModel):
    """Statutory retención PROCEDURE for a rendimientos-del-trabajo scheme.

    Separates the personalised progressive procedure the law applies to ordinary
    empleados (LIRPF art. 101.1, developed by RIRPF arts. 80/82-86) from the FIXED
    rate LIRPF art. 101.2 sets for administradores y miembros de consejos de
    administración. ``is_fixed_rate`` is ``False`` for the progressive empleado
    treatment (the per-perceptor percentage is a personalised computation, so no
    single rate is carried) and ``True`` for the administrador treatment.

    A tiny closed carrier of the STRUCTURAL fact -- which procedure a scheme
    follows -- per this module's contract of closed value sets and taxonomy
    only. The fixed rate VALUES themselves (35 %, 19 %, the 100.000 € INCN
    threshold) are regulatory data resolved from the registry, not module
    constants: this layer is imported BY the registry schema and must not
    import back from it (``aeat-architecture-boundaries``), so a caller
    needing the actual figures reads them from
    :func:`~domain.transactions.load_administrador_retencion_rates` /
    :func:`~domain.transactions.administrador_retencion_legal_refs` instead --
    the same layer the sibling RIRPF art. 95 rate set already lives in.
    """

    model_config = STRICT_FROZEN_CONFIG

    scheme: RetencionScheme
    is_fixed_rate: bool


_WORK_INCOME_RETENCION_TREATMENTS: Mapping[RetencionScheme, WorkIncomeRetencionTreatment] = MappingProxyType(
    {
        RetencionScheme.WORK_INCOME: WorkIncomeRetencionTreatment(
            scheme=RetencionScheme.WORK_INCOME,
            is_fixed_rate=False,
        ),
        RetencionScheme.WORK_INCOME_DIRECTOR: WorkIncomeRetencionTreatment(
            scheme=RetencionScheme.WORK_INCOME_DIRECTOR,
            is_fixed_rate=True,
        ),
    },
)


def work_income_retencion_treatment(scheme: RetencionScheme) -> WorkIncomeRetencionTreatment | None:
    """Return the statutory :class:`WorkIncomeRetencionTreatment` for a work-income scheme.

    Returns ``None`` for non-work-income schemes (actividades, premios, capital,
    arrendamiento), which are not governed by the LIRPF art. 101.1/101.2 trabajo
    procedure. Use it to distinguish the empleado (progressive) treatment from the
    administrador/consejero (fixed art. 101.2) treatment at the operator boundary.
    The actual fixed-rate figures live in :mod:`domain.transactions`, not here.
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


class TravelAgencyMediationType(StrEnum):
    """RD 1619/2012 disposición adicional cuarta mediation-service classification.

    That disposition lets a travel agency, acting as intermediary "en nombre
    y por cuenta ajena", invoice a listed set of services (passenger
    transport and luggage; hostelería/acampamento/balneario; restauración y
    catering; short-term transport-means rental; visits to museums/galleries/
    monuments/gardens/parks; access to cultural/artistic/sporting/scientific/
    educational/recreational events, fairs and exhibitions; travel insurance;
    and services under the special travel-agency IVA regime) under the
    agency's own invoice series rather than the actual supplier's. Modelo
    347's claves F ("ventas agencia viaje", any listed service, ISSUED
    direction) and G ("compras agencia viaje", air passenger transport only,
    RECEIVED direction) key on this fact, not on invoice direction alone.

    ``MEDIATED_SERVICE`` covers the full listed set and is the fact clave F
    checks for. ``AIR_PASSENGER_TRANSPORT`` is the narrower subset clave G
    checks for -- G names only "transportes de viajeros y sus equipajes por
    vía aérea", not the disposition's full service list, so a RECEIVED
    invoice for a non-air mediated service (e.g. mediated hostelería) is
    neither F nor G and falls through to the ordinary A/B classification.
    """

    MEDIATED_SERVICE = "mediated_service"
    AIR_PASSENGER_TRANSPORT = "air_passenger_transport"


class ThirdPartyDeclarationRole(StrEnum):
    """The filer's Modelo 347 declaring role -- orthogonal to :class:`EntityType`.

    :class:`EntityType` selects the TAX a taxpayer is assessed under (IRPF,
    Impuesto sobre Sociedades, or régimen de atribución de rentas), and that
    selection in turn drives which modelos, calendar and rate schedule apply.
    This axis answers a different question entirely: whether the filer's own
    institutional ROLE additionally requires declaring Modelo 347 claves C, D
    or E, a fact that coexists with any :class:`EntityType` value unchanged. A
    colegio profesional that also collects fees on behalf of its colegiados
    is a ``LEGAL_ENTITY`` for tax purposes, full stop; it is SEPARATELY a
    ``THIRD_PARTY_FEE_COLLECTOR`` for Modelo 347 clave C purposes, and neither
    fact touches the other.

    Every member is named for the population it identifies rather than for
    the article that names it, because article numbers renumber and a
    renumbering should be a citation update, not a member rename. Legal
    grounding lives here and in each binding's own ``legal_refs``, never in
    the member's own name:

    Attributes:
        THIRD_PARTY_FEE_COLLECTOR: RD 1065/2007 art. 31.3 -- a sociedad,
            asociación, colegio profesional or other entity that collects
            professional fees or intellectual/industrial/authorship-rights
            income on behalf of its socios, asociados or colegiados. Feeds
            clave C alone, at its own 300,51 EUR threshold (arts. 32.c,
            33.4) rather than the general 3.005,06 EUR floor.
        PROPIEDAD_HORIZONTAL_ENTITY: RD 1065/2007 art. 31.1's last
            paragraph -- a comunidad de propietarios under Ley 49/1960 sobre
            propiedad horizontal. Feeds clave D.
        SOCIAL_CHARACTER_ENTITY: RD 1065/2007 art. 31.1's last paragraph,
            cross-referencing Ley 37/1992 (LIVA) art. 20.tres -- a private
            entity or establishment of carácter social. Feeds clave D.
        STATUTORY_INFORMATION_DUTY_ENTITY: RD 1065/2007 art. 31.2,
            cross-referencing Ley 58/2003 (LGT) art. 94.1 and 94.2 -- the
            authorities, public bodies, cámaras y corporaciones, colegios y
            asociaciones profesionales, mutualidades de previsión social and
            other entities exercising public functions subject to the
            general duty to supply tax information, together with the
            partidos políticos, sindicatos and asociaciones empresariales
            LGT art. 94.2 subjects to the same duty. Feeds clave D.
        PUBLIC_ADMINISTRATION_ENTITY: RD 1065/2007 art. 31.2's second
            paragraph -- "las entidades integradas en las distintas
            Administraciones públicas", a narrower population properly
            contained within ``STATUTORY_INFORMATION_DUTY_ENTITY`` but named
            as its own member because clave E is EXCLUSIVE to it while
            clave D is not: modelling the subset as a distinct member lets
            clave D check the broader set and clave E check this member
            alone, without re-deriving the subset relationship at each call
            site. Feeds clave D (as part of the broader population) and,
            exclusively, clave E.
    """

    THIRD_PARTY_FEE_COLLECTOR = "third_party_fee_collector"
    PROPIEDAD_HORIZONTAL_ENTITY = "propiedad_horizontal_entity"
    SOCIAL_CHARACTER_ENTITY = "social_character_entity"
    STATUTORY_INFORMATION_DUTY_ENTITY = "statutory_information_duty_entity"
    PUBLIC_ADMINISTRATION_ENTITY = "public_administration_entity"


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
