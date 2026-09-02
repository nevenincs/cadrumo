"""Invoice-shaped registry binding helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator

from ....core.aggregation import INVOICE_BINDING_SOURCE_KINDS, BindingAggregationOp, BindingSourceKind
from ....core.country_code import CountryCodeAlpha2
from ....core.filing_year import FilingYear
from ....core.identity import TaxIdIdentityToken
from ....core.models import STRICT_FROZEN_CONFIG
from ._invoice_row_materialization import (
    build_invoice_rows,
    m349_public_row_union,
    normalise_m349_nif_export_rows,
)
from ._m347_threshold import m347_clave_c_declarable_party_ids, m347_declarable_party_ids
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
from .schema_base import coerce_enum_member


class RectificationScope(StrEnum):
    """Which rectification rows an invoice or counterpart selector admits."""

    ONLY_RECTIFICATIONS = "only_rectifications"
    """Rectification rows alone."""

    EXCLUDE_RECTIFICATIONS = "exclude_rectifications"
    """Every row except rectifications."""

    ANY = "any"
    """No rectification filter; the default when a selector is silent."""


RectificationScopeField = Annotated[RectificationScope, BeforeValidator(coerce_enum_member(RectificationScope))]
"""Registry ``rectification_scope`` token hydrated into a member.

Registry schema models validate under ``strict=True``, which refuses a bare TOML
string for an enum-typed field, so the token is coerced at the boundary.
"""


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
    country_code: CountryCodeAlpha2
    transaction_date: date
    base_amount: Decimal
    invoice_total_amount: Decimal | None = None
    iva_regime: str | None = Field(default=None, max_length=64)
    intracommunity_clave: str | None = Field(default=None, max_length=2)
    operation_clave: str | None = Field(default=None, max_length=1)
    is_rectification: bool = False
    rectified_year: FilingYear | None = None
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
    rectification_scope: RectificationScopeField = RectificationScope.ANY
    iva_regime: str | None = None

    _values_unique = field_validator("binding_ids", "claves")(unique_tuple("invoice requirement tuple"))


class _InvoiceSelector(BaseModel):
    """Strict validator for the selector mapping of an invoice-source binding."""

    model_config = STRICT_FROZEN_CONFIG

    fact: _InvoiceFact
    claves: tuple[str, ...] = ()
    rectification_scope: RectificationScopeField = RectificationScope.ANY
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
    (``application/invoices/source_resolver.py``) once carried its own copy of
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
        tuple[tuple[str, ...], RectificationScope, str | None],
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
        tuple[object, _InvoiceGrouping, RectificationScope, tuple[str, ...], str | None],
        list[tuple[DataBindingDefinition, _InvoiceSelector]],
    ] = {}
    for binding in revision.bindings:
        if binding.source not in source_kinds:
            continue
        selector = validate_selector(binding)
        if selector.fact != "row_field":
            continue
        grouping = selector.grouping
        if grouping is None:
            raise RegistryValidationError(
                f"binding {binding.id!r} fact 'row_field' requires a 'grouping' selector key",
            )
        cohort_source = binding.source if cohort_by_source else None
        cohort_key = (
            cohort_source,
            grouping,
            selector.rectification_scope,
            tuple(sorted(selector.claves)),
            selector.iva_regime,
        )
        cohorts.setdefault(cohort_key, []).append((binding, selector))
    for members in cohorts.values():
        sample_binding, sample_selector = members[0]
        grouping = sample_selector.grouping
        if grouping is None:
            raise RegistryValidationError(
                f"binding {sample_binding.id!r} row cohort carries no 'grouping' selector key",
            )
        scope_filtered = tuple(
            _filter_invoice_observations(observations_for_binding(sample_binding), sample_selector),
        )
        rows = build_invoice_rows(
            grouping,
            scope_filtered,
            m347_threshold_filter=_m347_row_family_threshold_filter,
        )
        for binding, selector in members:
            row_field = selector.row_field
            if row_field is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key",
                )
            for row_index, row in enumerate(rows, start=1):
                value = row.get(row_field)
                if value is None:
                    raise RegistryValidationError(
                        f"binding {binding.id!r} row_field {row_field!r} not produced for grouping {grouping!r}",
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
    return m349_public_row_union(normalise_m349_nif_export_rows(rows))


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


def _m347_row_family_threshold_filter(
    observations: tuple[InvoiceObservation, ...],
) -> tuple[InvoiceObservation, ...]:
    """Filter the per-row family's observations, clave C judged on its own floor.

    Clave C carries its OWN, lower 300,51 EUR floor (RD 1065/2007 arts. 32.c,
    33.4), applied ALONGSIDE -- never instead of -- the general 3.005,06 EUR
    floor every other clave shares: the same party can carry both ordinary
    operations and a clave-C collection in the same year, and each must be
    judged against its own figure.

    Filters observation-by-observation on a (party, clave-bucket) pair
    rather than returning a flat party-id set: a beneficiary who clears the
    LOWER clave-C floor but not the general floor must still lose their
    below-floor ORDINARY rows, and a flat "party is declarable" set would
    let those through once the party cleared either floor at all.
    """
    clave_c_totals: dict[str, Decimal] = {}
    general_totals: dict[str, Decimal] = {}
    for observation in observations:
        totals = clave_c_totals if observation.operation_clave == "C" else general_totals
        totals[observation.party_tax_id] = totals.get(observation.party_tax_id, Decimal("0")) + _invoice_total_amount(
            observation,
        )
    clave_c_declarable = m347_clave_c_declarable_party_ids(clave_c_totals)
    general_declarable = m347_declarable_party_ids(general_totals)
    return tuple(
        observation
        for observation in observations
        if (observation.operation_clave == "C" and observation.party_tax_id in clave_c_declarable)
        or (observation.operation_clave != "C" and observation.party_tax_id in general_declarable)
    )


def _invoice_total_amount(observation: InvoiceObservation) -> Decimal:
    if observation.invoice_total_amount is None:
        raise RegistryValidationError(
            f"invoice_total_sum binding requires invoice_total_amount on observation {observation.invoice_id!r}",
        )
    return observation.invoice_total_amount


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
            if previous is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} rectification observation declares no rectified base to compare",
                )
            total += observation.base_amount - previous
        return total
    raise RegistryValidationError(f"binding {binding.id!r} declares unsupported invoice fact {selector.fact!r}")


InvoiceSelector = _InvoiceSelector
invoice_selector = _invoice_selector


# ---------------------------------------------------------------------------
