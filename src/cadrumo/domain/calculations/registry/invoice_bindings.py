"""Invoice-shaped registry binding helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG, BindingSourceKind, Period
from ....core.aggregation import INVOICE_BINDING_SOURCE_KINDS, BindingAggregationOp
from ....core.identity import TaxIdIdentityToken
from ._m347_threshold import m347_declarable_party_ids
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import (
    M347_OPERATION_CLAVES,
    M349_OPERATION_CLAVES,
    BindingExportDataType,
    intracommunity_clave_validator,
    invariant_diagnostics,
    operation_clave_validator,
    selector_against_model,
    unique_tuple,
    uppercase_alpha_code,
    validate_rectification_fields,
)
from .binding_selector_utils import selector_as_dict as _selector_as_dict
from .errors import RegistryValidationError
from .ids import BindingId
from .quantity_screen_enrolment import independent_quantity_facts
from .schema import DataBindingDefinition, ModeloRevision

_RectificationScope = Literal["only_rectifications", "exclude_rectifications", "any"]
_InvoiceGrouping = Literal["operator_clave", "operator_clave_period", "contraparte_clave"]
_InvoiceRowField = Literal[
    "party_tax_id",
    "country_code",
    "party_legal_name",
    "clave",
    "base_imponible",
    "importe_total",
    "importe_q1",
    "importe_q2",
    "importe_q3",
    "importe_q4",
    "rectified_year",
    "rectified_period",
    "rectified_base_previous",
]

# Canonical invoice-shaped binding source kinds. Re-exported from
# :data:`core.aggregation.INVOICE_BINDING_SOURCE_KINDS`, which derives the
# set from :class:`~core.BindingSourceKind` (the single source-kind
# taxonomy) rather than hand-listing strings. Every consumer that needs "is
# this binding an invoice binding?" routes through this name.
__all__ = [
    "InvoiceObservation",
    "InvoiceObservationRequirement",
    "Modelo349OperadorClaveTotal",
    "Modelo349OperadorTotalsParity",
    "compute_modelo_349_operador_totals_parity",
    "invoice_binding_requirements",
    "is_m347_declarante_summary_invoice_binding",
    "m347_operation_clave",
    "resolve_invoice_binding_row_values",
    "resolve_invoice_binding_values",
    "resolve_invoice_family_row_values",
    "resolve_invoice_family_scalar_values",
    "validate_invoice_binding",
    "validate_invoice_binding_definition",
    "validate_invoice_family_fact_and_aggregation",
]

# Invoice-source bindings (modelo-agnostic factual aggregation from the user's
# invoice ledger). Used by IVA modelos (303, 349, 369, 390) and any other
# modelo that aggregates invoice facts into casilla values. Bindings of source
# "invoice" carry no legal authority of their own; legal/source refs declared
# alongside the binding identify the law backing the inclusion criteria.
# ---------------------------------------------------------------------------


class InvoiceObservation(BaseModel):
    """One factual line from the user's invoice ledger.

    The fields are scoped to the facts every IVA modelo needs to classify a
    transaction. ``base_amount`` carries the taxable base; ``invoice_total_amount``
    carries the gross invoice total for modelos such as M347 whose declaration
    floor is not the taxable-base amount. ``intracommunity_clave`` follows the
    AEAT clave-de-operacion enum (E, M, H, A, T, S, I, R, D, C) for M349.
    ``operation_clave`` carries M347's OWN, unrelated clave-de-operacion
    vocabulary (A-G; see :func:`m347_operation_clave`) -- the two claves share
    no values in common and a row must never mix them.
    ``iva_regime`` is open-ended so domestic-IVA modelos can carry their regime
    classification alongside.
    """

    model_config = STRICT_FROZEN_CONFIG

    invoice_id: str = Field(min_length=1, max_length=128)
    source_kind: BindingSourceKind
    party_tax_id: TaxIdIdentityToken
    country_code: str = Field(min_length=2, max_length=2)
    transaction_date: date
    base_amount: Decimal
    invoice_total_amount: Decimal | None = None
    iva_regime: str | None = Field(default=None, max_length=64)
    intracommunity_clave: str | None = Field(default=None, max_length=2)
    operation_clave: str | None = Field(default=None, max_length=1)
    is_rectification: bool = False
    rectified_year: int | None = Field(default=None, ge=2000, le=2099)
    rectified_period: str | None = Field(default=None, max_length=8)
    rectified_base_previous: Decimal | None = None
    party_legal_name: str | None = Field(default=None, max_length=200)

    _country_code_uppercase = field_validator("country_code")(uppercase_alpha_code("country_code"))
    _clave_uppercase = field_validator("intracommunity_clave")(intracommunity_clave_validator())
    _operation_clave_valid = field_validator("operation_clave")(
        operation_clave_validator(field_label="operation_clave", claves=M347_OPERATION_CLAVES),
    )

    @field_validator("source_kind", mode="before")
    @classmethod
    def _coerce_source_kind(cls, value: object) -> object:
        if isinstance(value, str) and not isinstance(value, BindingSourceKind):
            try:
                return BindingSourceKind(value)
            except ValueError as exc:
                raise RegistryValidationError(f"invoice source_kind {value!r} is not a BindingSourceKind") from exc
        return value

    @field_validator("source_kind")
    @classmethod
    def _source_kind_is_invoice_family(cls, value: BindingSourceKind) -> BindingSourceKind:
        if value not in INVOICE_BINDING_SOURCE_KINDS:
            raise RegistryValidationError(f"invoice source_kind {value!r} is not an invoice binding source")
        return value

    @field_validator("base_amount", "invoice_total_amount", "rectified_base_previous", mode="before")
    @classmethod
    def _decimal_amount(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("invoice amounts must be Decimal")
        return value

    @model_validator(mode="after")
    def _validate_rectification(self) -> InvoiceObservation:
        validate_rectification_fields(self)
        return self


class InvoiceObservationRequirement(BaseModel):
    """Invoice-fact slice declared by one or more invoice-source bindings.

    Modelo runtimes use this introspection to ask the invoice ledger for the
    minimal set of observations the bindings need.
    """

    model_config = STRICT_FROZEN_CONFIG

    binding_ids: tuple[BindingId, ...] = Field(min_length=1)
    claves: tuple[str, ...] = ()
    rectification_scope: _RectificationScope = "any"
    iva_regime: str | None = None

    _values_unique = field_validator("binding_ids", "claves")(unique_tuple("invoice requirement tuple"))


class _InvoiceSelector(BaseModel):
    """Strict validator for the selector mapping of an invoice-source binding."""

    model_config = STRICT_FROZEN_CONFIG

    fact: _InvoiceFact
    claves: tuple[str, ...] = ()
    rectification_scope: _RectificationScope = "any"
    iva_regime: str | None = Field(default=None, max_length=64)
    row_field: _InvoiceRowField | None = None
    grouping: _InvoiceGrouping | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: BindingExportDataType | None = None
    """Scalar type of the value this row field contributes to the export.

    The same fact ``BindingRowExportSelector.data_type`` carries; declared here
    so the selector model admits the key, since a source-family selector is
    validated whole against its own strict model. Optional while the families
    adopt it.
    """

    @field_validator("claves")
    @classmethod
    def _claves_uppercase_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("invoice selector claves entries must be unique")
        for clave in value:
            if clave != clave.upper():
                raise RegistryValidationError("invoice selector clave must be uppercase")
        return value

    @model_validator(mode="after")
    def _claves_within_grouping_vocabulary(self) -> _InvoiceSelector:
        """Check ``claves`` against the vocabulary its OWN grouping declares.

        A field validator cannot see ``grouping`` (declared after ``claves``
        in this model), so the closed-set membership check -- as opposed to
        the shape checks above -- runs here, once both fields are available.
        M347's ``contraparte_clave`` grouping and M349's two groupings share
        the ``claves`` field but never its vocabulary; validating every
        selector against M349's set alone would refuse every legitimate M347
        binding.
        """
        claves_vocabulary = M347_OPERATION_CLAVES if self.grouping == "contraparte_clave" else M349_OPERATION_CLAVES
        for clave in self.claves:
            if clave not in claves_vocabulary:
                raise RegistryValidationError(f"invoice selector clave {clave!r} is not an AEAT clave de operacion")
        return self


def _invoice_selector(binding: DataBindingDefinition) -> _InvoiceSelector:
    try:
        return _InvoiceSelector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed invoice selector") from exc


def is_m347_declarante_summary_invoice_binding(binding: DataBindingDefinition) -> bool:
    """Return whether ``binding`` is the M347 declarante-summary invoice binding.

    The canonical, single-defined predicate over ``_M347_DECLARANTE_SUMMARY_RECORD``,
    read through the typed :func:`_invoice_selector` rather than a raw
    ``selector_as_dict(binding).get("record")``: a caller outside this module
    (``application/invoices/_source_resolver.py``) once carried its own copy of
    both the literal and a ``.get()`` read, so a rename of the ``record`` field
    would have silently, permanently misclassified the M347 declarante-summary
    binding as absent rather than raising.

    ``binding.source`` is checked first because :class:`_InvoiceSelector`
    validates only invoice-family selectors; a non-invoice binding's selector
    shape is a different family's concept entirely, never this one's business.
    """
    if binding.source not in INVOICE_BINDING_SOURCE_KINDS:
        return False
    return _invoice_selector(binding).record == _M347_DECLARANTE_SUMMARY_RECORD


def m347_operation_clave(source_kind: BindingSourceKind | str) -> str | None:
    """Return the M347 clave de operacion determinable from ``source_kind`` alone.

    Grounded against RD 1065/2007 art. 33.1. Only two of the seven claves are
    determinable from the invoice direction alone:

    * ``PAYABLE_INVOICE`` (an invoice the taxpayer must pay -- a purchase) is
      clave ``A``, adquisiciones de bienes y servicios superiores a
      3.005,06 EUR.
    * ``COLLECTIBLE_INVOICE`` (an invoice the taxpayer will collect -- a
      sale) is clave ``B``, entregas de bienes y prestaciones de servicios
      superiores a 3.005,06 EUR.

    Claves F/G (mediación de agencia de viajes under RD 1619/2012 disposición
    adicional cuarta) are classified by the resolver caller from a fact this
    function's single ``source_kind`` argument cannot carry -- the invoice's
    own travel-agency mediation flag, not its direction. The remaining three
    claves each still need a fact neither this function nor the resolver
    caller has: ``C`` (cobros por cuenta de terceros) needs a
    professional-fees-collection classification distinct from ordinary
    purchase/sale direction; ``D``/``E`` key on the FILER's own type (entidad
    pública, partido, sindicato, ...) rather than on any transaction
    classification. Returns ``None`` for those and for any non-invoice source
    kind, rather than guessing -- a caller distinguishing them needs a fact
    this function does not have, not a default.

    ``source_kind`` also accepts a bare ``str`` value-equal to a member: the
    registry's own TOML-to-enum hydration boundary can still hold the raw
    value when this is consulted, and comparison below is by equality, never
    identity, so a value-equal string classifies exactly like its member.
    """
    if source_kind == BindingSourceKind.PAYABLE_INVOICE:
        return "A"
    if source_kind == BindingSourceKind.COLLECTIBLE_INVOICE:
        return "B"
    return None


def invoice_binding_requirements(
    revision: ModeloRevision,
) -> tuple[InvoiceObservationRequirement, ...]:
    """Return invoice ledger slices needed by ``revision``'s invoice bindings.

    Args:
        revision: The :class:`ModeloRevision` whose invoice bindings
            are inspected.

    Returns:
        Tuple of :class:`InvoiceObservationRequirement` records describing
        each distinct invoice-fact slice the revision requires.
    """
    grouped: dict[
        tuple[tuple[str, ...], _RectificationScope, str | None],
        set[BindingId],
    ] = {}
    for binding in revision.bindings:
        if binding.source not in INVOICE_BINDING_SOURCE_KINDS:
            continue
        selector = _validated_invoice_selector(binding)
        key = (tuple(sorted(selector.claves)), selector.rectification_scope, selector.iva_regime)
        grouped.setdefault(key, set()).add(binding.id)
    requirements: list[InvoiceObservationRequirement] = []
    for (claves, scope, regime), binding_ids in sorted(
        grouped.items(),
        key=lambda item: (item[0][0], item[0][1], item[0][2] or ""),
    ):
        requirements.append(
            InvoiceObservationRequirement(
                binding_ids=tuple(sorted(binding_ids)),
                claves=claves,
                rectification_scope=scope,
                iva_regime=regime,
            ),
        )
    return tuple(requirements)


_InvoiceFact = Literal["operator_count", "base_sum", "invoice_total_sum", "rectified_base_delta_sum", "row_field"]
_INVOICE_FACTS: frozenset[_InvoiceFact] = frozenset(
    {"operator_count", "base_sum", "invoice_total_sum", "rectified_base_delta_sum", "row_field"},
)
#: The invoice facts that are SCALAR MONEY MEASURES, and so are the only ones a
#: quantity screen could ever fold. ``operator_count`` counts parties rather than
#: measuring money, and ``row_field`` projects one column of a detail row rather
#: than aggregating anything; neither is a quantity, so neither is classified
#: below. Restricting the classified set is deliberate: declaring a non-quantity
#: "independent" would hand a future screen a fact it cannot sum.
_INVOICE_SCALAR_MEASURE_FACTS: frozenset[str] = frozenset(
    {"base_sum", "invoice_total_sum", "rectified_base_delta_sum"},
)

#: Facts that re-measure the SAME magnitude, each with the reason it does so.
#:
#: ``base_sum`` and ``invoice_total_sum`` are two readings of one invoice's
#: magnitude, and a revision declares whichever its modelo's law requires. The
#: registry bears this out symmetrically: M347 draws ``invoice_total_sum`` and
#: never ``base_sum``, M349 draws ``base_sum`` and never ``invoice_total_sum``.
#: That mirror is why the pair is a classification rather than two coincidences
#: -- either omission read alone looks like a gap.
_INVOICE_ALTERNATIVE_MEASURE_FACTS: Mapping[str, str] = {
    "base_sum": (
        "measures the invoice as its taxable base, IVA excluded; the reading Modelo 349 uses, "
        "because an intra-EU supply carries no repercutido IVA and the recapitulative statement "
        "declares the base. One of two magnitude measures a revision picks between"
    ),
    "invoice_total_sum": (
        "measures the same invoice as its total with IVA included; the reading Modelo 347 uses, "
        "whose declared magnitude is the importe total de la operación. The IVA-inclusive sibling "
        "of base_sum, never declared alongside it"
    ),
}

#: DERIVED as the complement, exactly as the ledger families derive theirs, so the
#: two cannot drift apart -- and so the shared helper's refusals apply here too: a
#: classified fact outside the supported set, or one carrying a blank reason, fails
#: at import.
#:
#: NO QUANTITY SCREEN RUNS ON THE INVOICE FAMILY TODAY. This declaration is
#: deliberately authored ahead of one. The classification is a reading of AEAT law
#: rather than anything derivable from the code, so recording it here is the point:
#: whoever extends the screen inherits the reasoning instead of re-deriving it under
#: time pressure, and mis-classifying a genuinely independent quantity as an
#: alternative measure is the one direction no check can catch.
#:
#: ``rectified_base_delta_sum`` is INDEPENDENT: a rectification delta is a separate
#: declared quantity, not a third reading of the invoice's magnitude, so a revision
#: declaring either magnitude measure still needs it drawn separately.
_INVOICE_INDEPENDENT_QUANTITY_FACTS: frozenset[str] = independent_quantity_facts(
    _INVOICE_SCALAR_MEASURE_FACTS,
    _INVOICE_ALTERNATIVE_MEASURE_FACTS,
)

_M347_DECLARANTE_SUMMARY_RECORD = "m347_declarante_summary"

_OPERATOR_CLAVE_PERIOD_ONLY_FIELDS: frozenset[str] = frozenset(
    {"rectified_year", "rectified_period", "rectified_base_previous"},
)

# Row fields the InvoiceObservation model cannot supply at all. The
# validator rejects bindings asking for these so the failure surfaces
# at snapshot-build rather than as a silent missing column at runtime.
# ``party_legal_name`` is NOT on this list: AEAT modelo-349 operator
# rows require it, and a missing legal_name in an observation is a
# real-data defect that must surface loudly at row-build time rather
# than be filtered out by a binding-validation guard.
_OPTIONAL_ONLY_INVOICE_ROW_FIELDS: frozenset[str] = frozenset[str]()


def validate_invoice_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate an invoice-source binding before it reaches runtime."""
    _validated_invoice_selector(binding)


def validate_invoice_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate an invoice-source binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector against
    :class:`_InvoiceSelector` and lifts the invoice fact/op invariants to build
    time, preserving the underlying pydantic field error. Both this validator and
    the invoice resolvers run the same inner
    :func:`_validated_invoice_selector`, so the fact/op invariants are genuinely
    re-checked at resolve time; :func:`validate_invoice_binding_definition` is the
    public raise-style wrapper over that same inner check.
    """
    failures = selector_against_model(binding, _InvoiceSelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "invoice", lambda b: _validated_invoice_selector(b))


def _validated_invoice_selector(binding: DataBindingDefinition) -> _InvoiceSelector:
    selector = _invoice_selector(binding)
    validate_invoice_family_fact_and_aggregation(binding, selector, family_label="invoice", strict_scalar_shape=True)
    return selector


def validate_invoice_family_fact_and_aggregation(
    binding: DataBindingDefinition,
    selector: _InvoiceSelector,
    *,
    family_label: str,
    strict_scalar_shape: bool,
) -> None:
    """Shared invoice/counterpart fact + aggregation-op cross-invariant.

    The invoice and counterpart families share one selector shape
    (:class:`_InvoiceSelector`) and one fact set (:data:`_INVOICE_FACTS`); their
    op/fact cross-checks were near-verbatim copies differing only in the
    family-name in the unsupported-fact message and in whether the invoice-only
    scalar-shape guards (``non-row fact must not declare row_field/grouping`` and
    ``op 'rows' requires fact 'row_field'``) run. ``family_label`` selects the
    error wording; ``strict_scalar_shape`` toggles the invoice-only guards (the
    counterpart variant historically omitted them, so the flag preserves that
    behaviour exactly).
    """
    if selector.fact not in _INVOICE_FACTS:
        raise RegistryValidationError(
            f"binding {binding.id!r} declares unsupported {family_label} fact {selector.fact!r}",
        )
    op = binding_aggregation_op(binding)
    _validate_scalar_invoice_fact_op(binding, selector, op)
    if selector.record == _M347_DECLARANTE_SUMMARY_RECORD and selector.fact not in {
        "operator_count",
        "invoice_total_sum",
    }:
        raise RegistryValidationError(
            f"binding {binding.id!r} M347 declarant summary must use operator_count or invoice_total_sum",
        )
    if selector.fact == "row_field":
        _validate_row_field_invoice_fact(binding, selector, op)
    elif strict_scalar_shape and (selector.row_field is not None or selector.grouping is not None):
        raise RegistryValidationError(f"binding {binding.id!r} non-row fact must not declare row_field or grouping")
    if strict_scalar_shape and op == BindingAggregationOp.ROWS and selector.fact != "row_field":
        raise RegistryValidationError(f"binding {binding.id!r} aggregation op 'rows' requires fact 'row_field'")


def _validate_scalar_invoice_fact_op(
    binding: DataBindingDefinition,
    selector: _InvoiceSelector,
    op: BindingAggregationOp,
) -> None:
    """Validate the aggregation op + scope of the scalar (non-``row_field``) facts.

    Enforces that ``operator_count`` uses ``count_distinct``, that ``base_sum`` /
    ``rectified_base_delta_sum`` use ``sum``, and that ``rectified_base_delta_sum``
    is scoped to rectifications. No-op for ``row_field`` (handled separately).
    """
    if selector.fact == "operator_count" and op != BindingAggregationOp.COUNT_DISTINCT:
        raise RegistryValidationError(
            f"binding {binding.id!r} fact 'operator_count' requires aggregation op 'count_distinct'",
        )
    if (
        selector.fact in {"base_sum", "invoice_total_sum", "rectified_base_delta_sum"}
        and op != BindingAggregationOp.SUM
    ):
        raise RegistryValidationError(f"binding {binding.id!r} fact {selector.fact!r} requires aggregation op 'sum'")
    if selector.fact == "rectified_base_delta_sum" and selector.rectification_scope != "only_rectifications":
        raise RegistryValidationError(
            f"binding {binding.id!r} fact 'rectified_base_delta_sum' "
            "requires rectification_scope 'only_rectifications'",
        )


def _validate_row_field_invoice_fact(
    binding: DataBindingDefinition,
    selector: _InvoiceSelector,
    op: BindingAggregationOp,
) -> None:
    """Validate the ``row_field``-fact requirements on a row-producer binding.

    Requires aggregation op ``rows``, a declared ``row_field`` and ``grouping``,
    and enforces the ``operator_clave_period`` grouping / ``only_rectifications``
    scope coupling for the rectification-only row fields.
    """
    if op != BindingAggregationOp.ROWS:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
    if selector.row_field is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key")
    if selector.row_field in _OPTIONAL_ONLY_INVOICE_ROW_FIELDS:
        raise RegistryValidationError(
            f"binding {binding.id!r} row_field {selector.row_field!r} is optional on the underlying "
            f"observation and cannot be required by a row-producer binding",
        )
    if selector.grouping is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'grouping' selector key")
    if selector.grouping == "operator_clave_period" and selector.rectification_scope != "only_rectifications":
        raise RegistryValidationError(
            f"binding {binding.id!r} grouping 'operator_clave_period' requires "
            f"rectification_scope 'only_rectifications'",
        )
    if selector.row_field in _OPERATOR_CLAVE_PERIOD_ONLY_FIELDS:
        if selector.grouping != "operator_clave_period":
            raise RegistryValidationError(
                f"binding {binding.id!r} row_field {selector.row_field!r} requires grouping 'operator_clave_period'",
            )
        if selector.rectification_scope != "only_rectifications":
            raise RegistryValidationError(
                f"binding {binding.id!r} row_field {selector.row_field!r} requires "
                f"rectification_scope 'only_rectifications'",
            )


def resolve_invoice_family_scalar_values(
    revision: ModeloRevision,
    *,
    source_kinds: frozenset[str] | frozenset[object],
    validate_selector: Callable[[DataBindingDefinition], _InvoiceSelector],
    observations_for_binding: Callable[[DataBindingDefinition], tuple[InvoiceObservation, ...]],
) -> dict[BindingId, Decimal]:
    """Resolve scalar bindings on a :class:`ModeloRevision` for one invoice family into Decimal aggregates.

    Shared core for both the invoice and counterpart scalar resolvers; the two
    differed only in (a) the family membership set, (b) the per-family selector
    validator, and (c) whether observations are filtered directly (invoice) or
    matched by ``source_kind`` and converted from counterpart observations.
    Row-producer bindings (``fact == "row_field"``) are skipped here.
    """
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source not in source_kinds:
            continue
        selector = validate_selector(binding)
        if selector.fact == "row_field":
            continue
        scope_filtered = tuple(_filter_invoice_observations(observations_for_binding(binding), selector))
        resolved[binding.id] = _aggregate_invoice_binding(binding, selector, scope_filtered)
    return resolved


def resolve_invoice_family_row_values(
    revision: ModeloRevision,
    *,
    source_kinds: frozenset[str] | frozenset[object],
    validate_selector: Callable[[DataBindingDefinition], _InvoiceSelector],
    observations_for_binding: Callable[[DataBindingDefinition], tuple[InvoiceObservation, ...]],
    cohort_by_source: bool,
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Resolve row-producer bindings on a :class:`ModeloRevision` for one invoice family into per-row values.

    Shared core for both the invoice and counterpart row resolvers. Bindings
    sharing the same cohort key share one-based row indexes so that an export
    record with ``repeat = "binding_rows"`` correlates field values across
    bindings on the same row. The counterpart family adds ``binding.source`` to
    the cohort key (``cohort_by_source = True``) so a different counterpart
    source kind does not share rows; the invoice family does not.

    M347's ``contraparte_clave`` grouping needs every clave to share ONE row
    sequence, because the diseño de registro's Tipo-2 declarado record is one
    shared physical sequence regardless of clave (grounded in the
    tui-architecture modelo 347 contraparte binding inventory reference).
    That now falls out of ``cohort_by_source`` directly rather than needing a
    grouping-keyed exception: every ``contraparte_clave`` binding declares the
    combined-direction :attr:`~core.BindingSourceKind.M347_THIRD_PARTY_OPERATION`
    source (see that member's docstring), so ``binding.source`` is already
    identical across claves and the cohort key naturally coincides. M349's own
    two groupings, which still declare distinct ``payable_invoice`` /
    ``collectible_invoice`` sources per binding, are unaffected.
    """
    resolved: dict[tuple[BindingId, int], Decimal | str] = {}
    cohorts: dict[
        tuple[object, _InvoiceGrouping, _RectificationScope, tuple[str, ...], str | None],
        list[tuple[DataBindingDefinition, _InvoiceSelector]],
    ] = {}
    for binding in revision.bindings:
        if binding.source not in source_kinds:
            continue
        selector = validate_selector(binding)
        if selector.fact != "row_field":
            continue
        assert selector.grouping is not None  # guarded by validator
        cohort_source = binding.source if cohort_by_source else None
        cohort_key = (
            cohort_source,
            selector.grouping,
            selector.rectification_scope,
            tuple(sorted(selector.claves)),
            selector.iva_regime,
        )
        cohorts.setdefault(cohort_key, []).append((binding, selector))
    for members in cohorts.values():
        sample_binding, sample_selector = members[0]
        grouping = sample_selector.grouping
        assert grouping is not None
        scope_filtered = tuple(
            _filter_invoice_observations(observations_for_binding(sample_binding), sample_selector),
        )
        rows = _build_invoice_rows(grouping, scope_filtered)
        for binding, selector in members:
            assert selector.row_field is not None  # guarded by validator
            for row_index, row in enumerate(rows, start=1):
                value = row.get(selector.row_field)
                if value is None:
                    raise RegistryValidationError(
                        f"binding {binding.id!r} row_field {selector.row_field!r} not produced "
                        f"for grouping {grouping!r}",
                    )
                resolved[(binding.id, row_index)] = value
    return resolved


def resolve_invoice_binding_values(
    revision: ModeloRevision,
    observations: Iterable[InvoiceObservation],
) -> dict[BindingId, Decimal]:
    """Resolve scalar invoice-source bindings into Decimal aggregates.

    Row-producer bindings (``aggregation.op == "rows"``) are skipped here; they
    are resolved by :func:`resolve_invoice_binding_row_values`.

    Args:
        revision: The :class:`ModeloRevision` whose bindings are resolved.
        observations: Invoice ledger lines to aggregate over.
    """
    available = tuple(observations)
    m347_summary_values, invoice_family_revision = _resolve_m347_declarante_summary_values(revision, available)
    invoice_family_values = resolve_invoice_family_scalar_values(
        invoice_family_revision,
        source_kinds=INVOICE_BINDING_SOURCE_KINDS,
        validate_selector=_validated_invoice_selector,
        observations_for_binding=lambda binding: _observations_for_binding_source(available, binding),
    )
    return {**invoice_family_values, **m347_summary_values}


def resolve_invoice_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[InvoiceObservation],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Resolve row-producer invoice bindings into per-row indexed values.

    Bindings with ``aggregation.op == "rows"`` aggregate observations into rows
    deterministically grouped by ``selector.grouping``. Bindings sharing the
    same grouping/scope/clave-filter share row indexes, so that an export
    record with ``repeat = "binding_rows"`` can correlate field values across
    bindings on the same row. Returns a flat mapping keyed by
    ``(binding_id, row_index)``. Row indexes are one-based to match
    ``ModeloBindingValue.row_index``.

    Args:
        revision: The :class:`ModeloRevision` whose row-producer bindings to resolve.
        observations: Typed :class:`InvoiceObservation` rows the row-producer
            bindings group, filter, and aggregate into indexed row values.
    """
    available = tuple(observations)
    rows = resolve_invoice_family_row_values(
        revision,
        source_kinds=INVOICE_BINDING_SOURCE_KINDS,
        validate_selector=_validated_invoice_selector,
        observations_for_binding=lambda binding: _observations_for_binding_source(available, binding),
        cohort_by_source=True,
    )
    return _m349_public_row_union(_normalise_m349_nif_export_rows(rows))


def _observations_for_binding_source(
    observations: tuple[InvoiceObservation, ...],
    binding: DataBindingDefinition,
) -> tuple[InvoiceObservation, ...]:
    if binding.source == BindingSourceKind.M347_THIRD_PARTY_OPERATION:
        # A binding declaring the combined-direction source reads BOTH
        # underlying invoice directions: each InvoiceObservation still
        # carries its own true PAYABLE_INVOICE/COLLECTIBLE_INVOICE direction
        # as its own source_kind (see M347_THIRD_PARTY_OPERATION's
        # docstring), so this union is the resolver honouring what the
        # binding's own declared source now truthfully claims to consume --
        # the M347 declarante-summary totals and the per-counterparty
        # contraparte_clave row family both declare this source.
        return tuple(
            observation
            for observation in observations
            if observation.source_kind in (BindingSourceKind.PAYABLE_INVOICE, BindingSourceKind.COLLECTIBLE_INVOICE)
        )
    return tuple(observation for observation in observations if observation.source_kind == binding.source)


def _resolve_m347_declarante_summary_values(
    revision: ModeloRevision,
    available: tuple[InvoiceObservation, ...],
) -> tuple[dict[BindingId, Decimal], ModeloRevision]:
    summary_bindings: list[DataBindingDefinition] = []
    invoice_family_bindings: list[DataBindingDefinition] = []
    for binding in revision.bindings:
        if binding.source not in INVOICE_BINDING_SOURCE_KINDS:
            invoice_family_bindings.append(binding)
            continue
        selector = _validated_invoice_selector(binding)
        if selector.record == _M347_DECLARANTE_SUMMARY_RECORD:
            summary_bindings.append(binding)
            continue
        invoice_family_bindings.append(binding)

    if not summary_bindings:
        return {}, revision

    declarable_party_ids = _m347_declarable_party_ids(available)
    thresholded = tuple(observation for observation in available if observation.party_tax_id in declarable_party_ids)
    resolved: dict[BindingId, Decimal] = {}
    for binding in summary_bindings:
        selector = _validated_invoice_selector(binding)
        resolved[binding.id] = _aggregate_invoice_binding(
            binding,
            selector,
            tuple(_filter_invoice_observations(thresholded, selector)),
        )
    return resolved, revision.model_copy(update={"bindings": tuple(invoice_family_bindings)})


def _m347_declarable_party_ids(observations: tuple[InvoiceObservation, ...]) -> frozenset[str]:
    totals: dict[str, Decimal] = {}
    for observation in observations:
        totals[observation.party_tax_id] = totals.get(observation.party_tax_id, Decimal("0")) + _invoice_total_amount(
            observation,
        )
    return m347_declarable_party_ids(totals)


def _invoice_total_amount(observation: InvoiceObservation) -> Decimal:
    if observation.invoice_total_amount is None:
        raise RegistryValidationError(
            f"invoice_total_sum binding requires invoice_total_amount on observation {observation.invoice_id!r}",
        )
    return observation.invoice_total_amount


_M349_EXPORT_NIF_COUNTRY_BINDINGS: dict[BindingId, BindingId] = {
    "iva-349-operador-row-nif": "iva-349-operador-row-codigo-pais",
    "iva-349-rectificacion-row-nif": "iva-349-rectificacion-row-codigo-pais",
    "iva-349-operador-row-nif-adquisicion": "iva-349-operador-row-codigo-pais-adquisicion",
    "iva-349-rectificacion-row-nif-adquisicion": "iva-349-rectificacion-row-codigo-pais-adquisicion",
}
_M349_PAYABLE_ROW_BINDING_MIRRORS: dict[BindingId, BindingId] = {
    "iva-349-operador-row-codigo-pais-adquisicion": "iva-349-operador-row-codigo-pais",
    "iva-349-operador-row-nif-adquisicion": "iva-349-operador-row-nif",
    "iva-349-operador-row-apellidos-adquisicion": "iva-349-operador-row-apellidos",
    "iva-349-operador-row-clave-adquisicion": "iva-349-operador-row-clave",
    "iva-349-operador-row-base-adquisicion": "iva-349-operador-row-base",
    "iva-349-rectificacion-row-codigo-pais-adquisicion": "iva-349-rectificacion-row-codigo-pais",
    "iva-349-rectificacion-row-nif-adquisicion": "iva-349-rectificacion-row-nif",
    "iva-349-rectificacion-row-apellidos-adquisicion": "iva-349-rectificacion-row-apellidos",
    "iva-349-rectificacion-row-clave-adquisicion": "iva-349-rectificacion-row-clave",
    "iva-349-rectificacion-row-ejercicio-adquisicion": "iva-349-rectificacion-row-ejercicio",
    "iva-349-rectificacion-row-periodo-adquisicion": "iva-349-rectificacion-row-periodo",
    "iva-349-rectificacion-row-base-rectificada-adquisicion": "iva-349-rectificacion-row-base-rectificada",
    "iva-349-rectificacion-row-base-anterior-adquisicion": "iva-349-rectificacion-row-base-anterior",
}
_M349_OPERADOR_PUBLIC_ROW_BINDINGS: frozenset[BindingId] = frozenset(
    {
        "iva-349-operador-row-codigo-pais",
        "iva-349-operador-row-nif",
        "iva-349-operador-row-apellidos",
        "iva-349-operador-row-clave",
        "iva-349-operador-row-base",
    },
)
_M349_RECTIFICACION_PUBLIC_ROW_BINDINGS: frozenset[BindingId] = frozenset(
    {
        "iva-349-rectificacion-row-codigo-pais",
        "iva-349-rectificacion-row-nif",
        "iva-349-rectificacion-row-apellidos",
        "iva-349-rectificacion-row-clave",
        "iva-349-rectificacion-row-ejercicio",
        "iva-349-rectificacion-row-periodo",
        "iva-349-rectificacion-row-base-rectificada",
        "iva-349-rectificacion-row-base-anterior",
    },
)


class Modelo349OperadorClaveTotal(BaseModel):
    """One clave's operator count and base-imponible sum, reconstructed from the operador row set.

    Groups the per-operador ``iva-349-operador-row-*`` detail (the AEAT Diseño
    de Registros Tipo-2 "registro de operador" rows) by ``clave de operación``
    and carries that clave's distinct-operator count and summed base
    imponible. Mirrors :class:`WithholdingClaveBreakdown` for the Modelo 349
    intracommunity-operator axis.
    """

    model_config = STRICT_FROZEN_CONFIG

    clave: str = Field(min_length=1, max_length=1)
    operator_count: int = Field(ge=0)
    base_total: Decimal


class Modelo349OperadorTotalsParity(BaseModel):
    """Totals-parity verdict between the per-operador row set and the Modelo 349 declarant summary.

    Modelo 349's declarant-summary scalar casillas (``decl.numero-operadores``,
    ``decl.importe-operaciones``) and the per-operador-clave row-producer
    bindings (``iva-349-operador-row-*``) are resolved by two structurally
    INDEPENDENT code paths over the same :class:`InvoiceObservation` set:
    :func:`resolve_invoice_binding_values` folds the observations directly
    into a scalar (:func:`_aggregate_invoice_binding`'s ``operator_count`` /
    ``base_sum`` facts), while :func:`resolve_invoice_binding_row_values`
    groups them into per-``(country, party_tax_id, clave)`` rows
    (:func:`_build_operator_clave_rows`). Nothing in the registry
    cross-checks that the two paths agree, so a defect in either aggregator —
    or a manual-entry :class:`~domain.modelos.Modelo349OperadorRow` set
    that omits an operator the summary already counted — would silently
    under- or over-declare one side without detection.

    This model is the pure comparison result of that cross-check: the sum of
    every reconstructed operador row's base imponible against the resolved
    ``decl.importe-operaciones`` value, and the count of distinct
    ``(country_code, party_tax_id, clave)`` operador rows against the resolved
    ``decl.numero-operadores`` value. ``is_consistent`` is ``True`` only when
    the operator-count delta is exactly zero and the base-imponible delta is
    within ``tolerance`` — a divergence on either axis surfaces as a loud,
    actionable finding (``no-silent-under-declaration``), never a silent pass.
    """

    model_config = STRICT_FROZEN_CONFIG

    by_clave: tuple[Modelo349OperadorClaveTotal, ...] = Field(default_factory=tuple)
    operator_row_total: int = Field(ge=0)
    operator_summary_total: int = Field(ge=0)
    operator_delta: int
    base_row_total: Decimal
    base_summary_total: Decimal
    base_delta: Decimal
    tolerance: Decimal = Field(ge=Decimal("0"))
    is_consistent: bool


def compute_modelo_349_operador_totals_parity(
    revision: ModeloRevision,
    observations: Iterable[InvoiceObservation],
    *,
    operator_summary_total: Decimal,
    base_summary_total: Decimal,
    tolerance: Decimal = Decimal("0"),
) -> Modelo349OperadorTotalsParity:
    """Cross-check the per-operador row set against the resolved Modelo 349 declarant summary.

    Args:
        revision: The :class:`ModeloRevision` whose ``iva-349-operador-row-*``
            row-producer bindings are resolved into the operador row set.
        observations: The :class:`InvoiceObservation` rows the revision's
            invoice-source bindings aggregate (exclude-rectifications scope
            only feeds the operador row set; rectification observations are a
            distinct AEAT record type and are excluded from this axis by the
            registry's own binding selectors).
        operator_summary_total: The resolved value of casilla
            ``decl.numero-operadores``, typically read from
            ``revision.casilla_values["decl.numero-operadores"]``.
        base_summary_total: The resolved value of casilla
            ``decl.importe-operaciones``, typically read from
            ``revision.casilla_values["decl.importe-operaciones"]``.
        tolerance: Maximum absolute EUR delta on the base-imponible axis that
            does not surface a divergence. THE REGISTRY IS THE AUTHORITY FOR
            THIS VALUE and publishes it per revision: resolve it with
            ``snapshot.verification_policy().tolerance`` and pass it. The
            default is exact equality rather than a cent: Modelo 349's own
            revisions declare no verification expectations at all, and with
            no published contract there is no authority to widen the
            comparison -- guessing strict yields a visible finding, guessing
            loose yields a silent omission. The operator-count axis is an
            exact integer match with no tolerance regardless.

    Returns:
        A :class:`Modelo349OperadorTotalsParity` verdict. ``is_consistent`` is
        ``False`` whenever the reconstructed operator count differs at all, or
        the reconstructed base imponible diverges from ``base_summary_total``
        by more than ``tolerance`` — a dropped or double-counted operador row
        must surface as a divergence, never silently collapse into
        ``is_consistent=True``.
    """
    rows = resolve_invoice_binding_row_values(revision, observations)
    nif_by_row = {
        row_index: value
        for (binding_id, row_index), value in rows.items()
        if binding_id == "iva-349-operador-row-nif" and isinstance(value, str)
    }
    country_by_row = {
        row_index: value
        for (binding_id, row_index), value in rows.items()
        if binding_id == "iva-349-operador-row-codigo-pais" and isinstance(value, str)
    }
    clave_by_row = {
        row_index: value
        for (binding_id, row_index), value in rows.items()
        if binding_id == "iva-349-operador-row-clave" and isinstance(value, str)
    }
    base_by_row = {
        row_index: value
        for (binding_id, row_index), value in rows.items()
        if binding_id == "iva-349-operador-row-base" and isinstance(value, Decimal)
    }
    operators: set[tuple[str, str, str]] = set()
    operator_base: dict[tuple[str, str, str], Decimal] = {}
    base_row_total = Decimal("0")
    for row_index in sorted(base_by_row):
        clave = clave_by_row.get(row_index)
        country = country_by_row.get(row_index)
        nif = nif_by_row.get(row_index)
        if clave is None or country is None or nif is None:
            continue
        key = (country, nif, clave)
        operators.add(key)
        operator_base[key] = operator_base.get(key, Decimal("0")) + base_by_row[row_index]
        base_row_total += base_by_row[row_index]
    by_clave_operators: dict[str, set[tuple[str, str]]] = {}
    by_clave_base: dict[str, Decimal] = {}
    for (country, nif, clave), base in operator_base.items():
        by_clave_operators.setdefault(clave, set()).add((country, nif))
        by_clave_base[clave] = by_clave_base.get(clave, Decimal("0")) + base
    by_clave = tuple(
        Modelo349OperadorClaveTotal(
            clave=clave,
            operator_count=len(by_clave_operators[clave]),
            base_total=by_clave_base[clave],
        )
        for clave in sorted(by_clave_operators)
    )
    operator_row_total = len(operators)
    operator_delta = operator_row_total - int(operator_summary_total)
    base_delta = base_row_total - base_summary_total
    is_consistent = operator_delta == 0 and abs(base_delta) <= tolerance
    return Modelo349OperadorTotalsParity(
        by_clave=by_clave,
        operator_row_total=operator_row_total,
        operator_summary_total=int(operator_summary_total),
        operator_delta=operator_delta,
        base_row_total=base_row_total,
        base_summary_total=base_summary_total,
        base_delta=base_delta,
        tolerance=tolerance,
        is_consistent=is_consistent,
    )


def _normalise_m349_nif_export_rows(
    rows: dict[tuple[BindingId, int], Decimal | str],
) -> dict[tuple[BindingId, int], Decimal | str]:
    normalised = dict(rows)
    for (binding_id, row_index), value in rows.items():
        country_binding = _M349_EXPORT_NIF_COUNTRY_BINDINGS.get(binding_id)
        if country_binding is None:
            continue
        country_value = rows.get((country_binding, row_index))
        if not isinstance(value, str) or not isinstance(country_value, str):
            continue
        normalised[(binding_id, row_index)] = _m349_export_nif_number(value, country_value)
    return normalised


def _m349_public_row_union(
    rows: dict[tuple[BindingId, int], Decimal | str],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Append payable acquisition rows onto the public Modelo 349 row ids."""
    merged = dict(rows)
    operador_offset = _max_row_index(rows, _M349_OPERADOR_PUBLIC_ROW_BINDINGS)
    rectificacion_offset = _max_row_index(rows, _M349_RECTIFICACION_PUBLIC_ROW_BINDINGS)
    for (binding_id, row_index), value in sorted(rows.items()):
        public_binding = _M349_PAYABLE_ROW_BINDING_MIRRORS.get(binding_id)
        if public_binding is None:
            continue
        offset = rectificacion_offset if public_binding in _M349_RECTIFICACION_PUBLIC_ROW_BINDINGS else operador_offset
        merged[(public_binding, row_index + offset)] = value
    return merged


def _max_row_index(rows: Mapping[tuple[BindingId, int], object], bindings: frozenset[BindingId]) -> int:
    return max((row_index for (binding_id, row_index) in rows if binding_id in bindings), default=0)


def _build_invoice_rows(
    grouping: _InvoiceGrouping,
    observations: tuple[InvoiceObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    if grouping == "operator_clave":
        return _build_operator_clave_rows(observations)
    if grouping == "operator_clave_period":
        return _build_operator_clave_period_rows(observations)
    if grouping == "contraparte_clave":
        return _build_contraparte_clave_rows(observations)
    raise RegistryValidationError(f"unsupported invoice row grouping {grouping!r}")


def _build_operator_clave_rows(
    observations: tuple[InvoiceObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    grouped: dict[tuple[str, str, str], _OperatorClaveAccumulator] = {}
    for observation in observations:
        if observation.intracommunity_clave is None:
            continue
        key = (
            observation.country_code,
            observation.party_tax_id,
            observation.intracommunity_clave,
        )
        bucket = grouped.setdefault(
            key,
            _OperatorClaveAccumulator(
                country_code=observation.country_code,
                party_tax_id=observation.party_tax_id,
                clave=observation.intracommunity_clave,
                party_legal_name=observation.party_legal_name,
                base_total=Decimal("0"),
            ),
        )
        bucket.base_total += observation.base_amount
        if bucket.party_legal_name is None and observation.party_legal_name is not None:
            bucket.party_legal_name = observation.party_legal_name
    rows: list[Mapping[str, Decimal | str]] = []
    for key in sorted(grouped):
        bucket = grouped[key]
        row: dict[str, Decimal | str] = {
            "country_code": bucket.country_code,
            "party_tax_id": bucket.party_tax_id,
            "clave": bucket.clave,
            "base_imponible": bucket.base_total,
        }
        if bucket.party_legal_name is not None:
            row["party_legal_name"] = bucket.party_legal_name
        rows.append(row)
    return tuple(rows)


_M347_QUARTER_TOKENS: tuple[Literal["1T", "2T", "3T", "4T"], ...] = ("1T", "2T", "3T", "4T")
_M347_QUARTER_ROW_FIELDS: Mapping[Literal["1T", "2T", "3T", "4T"], str] = {
    "1T": "importe_q1",
    "2T": "importe_q2",
    "3T": "importe_q3",
    "4T": "importe_q4",
}


def _m347_quarter_of(value: date) -> Literal["1T", "2T", "3T", "4T"]:
    """Return the calendar quarter token ``value`` falls in.

    Routed through :meth:`~core.Period.contains`, the one canonical period
    boundary authority (``aeat-registry-authority-flow``'s period-boundary
    rule) -- no locally re-derived month-range arithmetic. Uses ``value``'s
    OWN calendar year, not a filing-year argument this row-producer has no
    access to: the diseño's Q1-Q4 fields are the ordinary calendar quarter an
    operation falls in, independent of which filing year's declaration
    reports it.
    """
    for token in _M347_QUARTER_TOKENS:
        if Period.from_year_and_code(value.year, token).contains(value):
            return token
    msg = f"date {value!r} does not fall in any calendar quarter"  # pragma: no cover - contains() is exhaustive
    raise RegistryValidationError(msg)


class _ContraparteClaveAccumulator(BaseModel):
    """Mutable accumulator for contraparte_clave row aggregation (modelo 347)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    country_code: str
    party_tax_id: TaxIdIdentityToken
    clave: str
    party_legal_name: str | None
    importe_total: Decimal
    importe_q1: Decimal
    importe_q2: Decimal
    importe_q3: Decimal
    importe_q4: Decimal


def _build_contraparte_clave_rows(
    observations: tuple[InvoiceObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    """Group invoice observations into modelo 347 contraparte rows.

    Mirrors :func:`_build_operator_clave_rows`'s (country, counterparty,
    clave) grouping shape exactly, keyed on ``operation_clave`` -- M347's own
    clave vocabulary -- rather than M349's ``intracommunity_clave``. The two
    fields are disjoint by construction (:class:`InvoiceObservation`'s
    validators enforce each against its own closed set), so an observation
    can only ever be grouped by the one this function reads.

    Aggregates ``invoice_total_amount`` rather than ``base_amount``: RD
    1065/2007 art. 34.2.a) requires the declared IMPORTE ANUAL to be the
    total contraprestacion including cuotas and recargos, not the taxable
    base alone (recorded in the tui-architecture modelo 347 contraparte
    binding inventory reference).

    Also buckets that same amount into the calendar quarter of
    ``transaction_date`` -- the diseño's mandatory, unconditional "IMPORTE DE
    LAS OPERACIONES [Nth] TRIMESTRE" fields (RD 1065/2007 art. 33.1's "se
    suministrará desglosada trimestralmente"), ungated by any "Sólo..."
    exception the way ``importe-metalico`` / ``operacion-seguro`` /
    ``arrendamiento-local-negocio`` / the transmisiones-inmuebles pair are.
    The quarterly buckets accumulate in the SAME loop that sums
    ``importe_total``, so the annual total is the sum of the four quarters by
    construction, not by a separate reconciling step.
    """
    grouped: dict[tuple[str, str, str], _ContraparteClaveAccumulator] = {}
    for observation in observations:
        if observation.operation_clave is None:
            continue
        if observation.invoice_total_amount is None:
            raise RegistryValidationError(
                f"invoice observation {observation.invoice_id!r} declares operation_clave "
                f"{observation.operation_clave!r} but no invoice_total_amount",
            )
        key = (
            observation.country_code,
            observation.party_tax_id,
            observation.operation_clave,
        )
        bucket = grouped.setdefault(
            key,
            _ContraparteClaveAccumulator(
                country_code=observation.country_code,
                party_tax_id=observation.party_tax_id,
                clave=observation.operation_clave,
                party_legal_name=observation.party_legal_name,
                importe_total=Decimal("0"),
                importe_q1=Decimal("0"),
                importe_q2=Decimal("0"),
                importe_q3=Decimal("0"),
                importe_q4=Decimal("0"),
            ),
        )
        bucket.importe_total += observation.invoice_total_amount
        quarter_field = _M347_QUARTER_ROW_FIELDS[_m347_quarter_of(observation.transaction_date)]
        setattr(bucket, quarter_field, getattr(bucket, quarter_field) + observation.invoice_total_amount)
        if bucket.party_legal_name is None and observation.party_legal_name is not None:
            bucket.party_legal_name = observation.party_legal_name
    rows: list[Mapping[str, Decimal | str]] = []
    for key in sorted(grouped):
        bucket = grouped[key]
        row: dict[str, Decimal | str] = {
            "country_code": bucket.country_code,
            "party_tax_id": bucket.party_tax_id,
            "clave": bucket.clave,
            "importe_total": bucket.importe_total,
            "importe_q1": bucket.importe_q1,
            "importe_q2": bucket.importe_q2,
            "importe_q3": bucket.importe_q3,
            "importe_q4": bucket.importe_q4,
        }
        if bucket.party_legal_name is not None:
            row["party_legal_name"] = bucket.party_legal_name
        rows.append(row)
    return tuple(rows)


def _build_operator_clave_period_rows(
    observations: tuple[InvoiceObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    grouped: dict[
        tuple[str, str, str, int, str],
        _OperatorClavePeriodAccumulator,
    ] = {}
    for observation in observations:
        if observation.intracommunity_clave is None:
            continue
        if observation.rectified_year is None or observation.rectified_period is None:
            raise RegistryValidationError(
                "operator_clave_period grouping requires rectification metadata on every observation",
            )
        key = (
            observation.country_code,
            observation.party_tax_id,
            observation.intracommunity_clave,
            observation.rectified_year,
            observation.rectified_period,
        )
        bucket = grouped.setdefault(
            key,
            _OperatorClavePeriodAccumulator(
                country_code=observation.country_code,
                party_tax_id=observation.party_tax_id,
                clave=observation.intracommunity_clave,
                party_legal_name=observation.party_legal_name,
                rectified_year=observation.rectified_year,
                rectified_period=observation.rectified_period,
                base_total=Decimal("0"),
                base_previous_total=Decimal("0"),
            ),
        )
        bucket.base_total += observation.base_amount
        previous = observation.rectified_base_previous
        assert previous is not None  # guarded by InvoiceObservation validator
        bucket.base_previous_total += previous
        if bucket.party_legal_name is None and observation.party_legal_name is not None:
            bucket.party_legal_name = observation.party_legal_name
    rows: list[Mapping[str, Decimal | str]] = []
    for key in sorted(grouped):
        bucket = grouped[key]
        row: dict[str, Decimal | str] = {
            "country_code": bucket.country_code,
            "party_tax_id": bucket.party_tax_id,
            "clave": bucket.clave,
            "rectified_year": str(bucket.rectified_year),
            "rectified_period": bucket.rectified_period,
            "base_imponible": bucket.base_total,
            "rectified_base_previous": bucket.base_previous_total,
        }
        if bucket.party_legal_name is not None:
            row["party_legal_name"] = bucket.party_legal_name
        rows.append(row)
    return tuple(rows)


def _m349_export_nif_number(party_tax_id: str, country_code: str) -> str:
    from ...modelos import m349_nif_number_for_export

    try:
        return m349_nif_number_for_export(party_tax_id, country_code)
    except ValueError as exc:
        raise RegistryValidationError(str(exc)) from exc


class _OperatorClaveAccumulator(BaseModel):
    """Mutable accumulator for operator_clave row aggregation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    country_code: str
    party_tax_id: TaxIdIdentityToken
    clave: str
    party_legal_name: str | None
    base_total: Decimal


class _OperatorClavePeriodAccumulator(BaseModel):
    """Mutable accumulator for operator_clave_period row aggregation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    country_code: str
    party_tax_id: TaxIdIdentityToken
    clave: str
    party_legal_name: str | None
    rectified_year: int
    rectified_period: str
    base_total: Decimal
    base_previous_total: Decimal


def _filter_invoice_observations(
    observations: Iterable[InvoiceObservation],
    selector: _InvoiceSelector,
) -> Iterable[InvoiceObservation]:
    clave_filter = set(selector.claves)
    # M347's contraparte_clave grouping filters on operation_clave -- its OWN,
    # disjoint clave vocabulary -- never on M349's intracommunity_clave. Every
    # other grouping (including no grouping declared, e.g. scalar selectors)
    # keeps the established intracommunity_clave filter.
    clave_field = "operation_clave" if selector.grouping == "contraparte_clave" else "intracommunity_clave"
    for observation in observations:
        if selector.rectification_scope == "only_rectifications" and not observation.is_rectification:
            continue
        if selector.rectification_scope == "exclude_rectifications" and observation.is_rectification:
            continue
        if clave_filter and getattr(observation, clave_field) not in clave_filter:
            continue
        if selector.iva_regime is not None and observation.iva_regime != selector.iva_regime:
            continue
        yield observation


def _aggregate_invoice_binding(
    binding: DataBindingDefinition,
    selector: _InvoiceSelector,
    observations: tuple[InvoiceObservation, ...],
) -> Decimal:
    op = binding_aggregation_op(binding)
    if selector.fact == "operator_count":
        if op != BindingAggregationOp.COUNT_DISTINCT:
            raise RegistryValidationError(
                f"binding {binding.id!r} fact 'operator_count' requires aggregation op 'count_distinct'",
            )
        if selector.record == _M347_DECLARANTE_SUMMARY_RECORD:
            return Decimal(len({observation.party_tax_id for observation in observations}))
        # AEAT defines this count as the number of Tipo 2 records (one per
        # (operator, clave) pair for the operador grouping; one per (operator,
        # clave, ejercicio, periodo) for the rectificacion grouping). Per
        # Orden EHA/769/2010 Anexo positions 138-146 and 162-170: "Número de
        # registros de tipo 2 con clave de operación, posición 133, igual a
        # 'E', 'M', 'H', 'T', 'A', 'S', 'I', 'R', 'D' o 'C'."
        if selector.rectification_scope == "only_rectifications":
            return Decimal(
                len(
                    {
                        (
                            observation.party_tax_id,
                            observation.country_code,
                            observation.intracommunity_clave,
                            observation.rectified_year,
                            observation.rectified_period,
                        )
                        for observation in observations
                    },
                ),
            )
        return Decimal(
            len(
                {
                    (
                        observation.party_tax_id,
                        observation.country_code,
                        observation.intracommunity_clave,
                    )
                    for observation in observations
                },
            ),
        )
    if selector.fact == "base_sum":
        if op != BindingAggregationOp.SUM:
            raise RegistryValidationError(f"binding {binding.id!r} fact 'base_sum' requires aggregation op 'sum'")
        return sum((observation.base_amount for observation in observations), Decimal("0"))
    if selector.fact == "invoice_total_sum":
        if op != BindingAggregationOp.SUM:
            raise RegistryValidationError(
                f"binding {binding.id!r} fact 'invoice_total_sum' requires aggregation op 'sum'",
            )
        return sum((_invoice_total_amount(observation) for observation in observations), Decimal("0"))
    if selector.fact == "rectified_base_delta_sum":
        if op != BindingAggregationOp.SUM:
            raise RegistryValidationError(
                f"binding {binding.id!r} fact 'rectified_base_delta_sum' requires aggregation op 'sum'",
            )
        total = Decimal("0")
        for observation in observations:
            if not observation.is_rectification:
                raise RegistryValidationError(f"binding {binding.id!r} requires rectification observations only")
            previous = observation.rectified_base_previous
            assert previous is not None  # guaranteed by InvoiceObservation validator
            total += observation.base_amount - previous
        return total
    raise RegistryValidationError(f"binding {binding.id!r} declares unsupported invoice fact {selector.fact!r}")


InvoiceSelector = _InvoiceSelector
RectificationScope = _RectificationScope
invoice_selector = _invoice_selector


# ---------------------------------------------------------------------------
