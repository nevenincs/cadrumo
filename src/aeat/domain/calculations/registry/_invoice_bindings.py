"""Invoice-shaped registry binding helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG
from ....core.aggregation import INVOICE_BINDING_SOURCE_KINDS, BindingAggregationOp
from ._binding_aggregation import binding_aggregation_op
from ._binding_selector_utils import (
    intracommunity_clave_validator,
    invariant_diagnostics,
    selector_against_model,
    unique_tuple,
    uppercase_alpha_code,
    validate_rectification_fields,
)
from ._binding_selector_utils import selector_as_dict as _selector_as_dict
from ._errors import RegistryValidationError
from ._ids import BindingId
from ._schema import DataBindingDefinition, ModeloRevision

_RectificationScope = Literal["only_rectifications", "exclude_rectifications", "any"]
_InvoiceGrouping = Literal["operator_clave", "operator_clave_period"]
_InvoiceRowField = Literal[
    "party_tax_id",
    "country_code",
    "party_legal_name",
    "clave",
    "base_imponible",
    "rectified_year",
    "rectified_period",
    "rectified_base_previous",
]

# Canonical invoice-shaped binding source kinds. Re-exported from
# :data:`aeat.core.aggregation.INVOICE_BINDING_SOURCE_KINDS`, which derives the
# set from :class:`~aeat.core.BindingSourceKind` (the single source-kind
# taxonomy) rather than hand-listing strings. Every consumer that needs "is
# this binding an invoice binding?" routes through this name.
__all__ = [
    "INVOICE_BINDING_SOURCE_KINDS",
    "InvoiceObservation",
    "InvoiceObservationRequirement",
    "invoice_binding_requirements",
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
    transaction. ``intracommunity_clave`` follows the AEAT clave-de-operacion
    enum (E, M, H, A, T, S, I, R, D, C). ``iva_regime`` is open-ended so
    domestic-IVA modelos can carry their regime classification alongside.
    """

    model_config = STRICT_FROZEN_CONFIG

    invoice_id: str = Field(min_length=1, max_length=128)
    party_tax_id: str = Field(min_length=1, max_length=64)
    country_code: str = Field(min_length=2, max_length=2)
    transaction_date: date
    base_amount: Decimal
    iva_regime: str | None = Field(default=None, max_length=64)
    intracommunity_clave: str | None = Field(default=None, max_length=2)
    is_rectification: bool = False
    rectified_year: int | None = Field(default=None, ge=2000, le=2099)
    rectified_period: str | None = Field(default=None, max_length=8)
    rectified_base_previous: Decimal | None = None
    party_legal_name: str | None = Field(default=None, max_length=200)

    _country_code_uppercase = field_validator("country_code")(uppercase_alpha_code("country_code"))
    _clave_uppercase = field_validator("intracommunity_clave")(intracommunity_clave_validator())

    @field_validator("base_amount", "rectified_base_previous")
    @classmethod
    def _decimal_amount(cls, value: Decimal | None) -> Decimal | None:
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

    @field_validator("claves")
    @classmethod
    def _claves_uppercase_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("invoice selector claves entries must be unique")
        for clave in value:
            if clave != clave.upper():
                raise RegistryValidationError("invoice selector clave must be uppercase")
            if clave not in {"E", "M", "H", "A", "T", "S", "I", "R", "D", "C"}:
                raise RegistryValidationError(f"invoice selector clave {clave!r} is not an AEAT clave de operacion")
        return value


def _invoice_selector(binding: DataBindingDefinition) -> _InvoiceSelector:
    try:
        return _InvoiceSelector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed invoice selector") from exc


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


_InvoiceFact = Literal["operator_count", "base_sum", "rectified_base_delta_sum", "row_field"]
_INVOICE_FACTS: frozenset[_InvoiceFact] = frozenset(
    {"operator_count", "base_sum", "rectified_base_delta_sum", "row_field"},
)

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
_OPTIONAL_ONLY_INVOICE_ROW_FIELDS: frozenset[str] = frozenset()


def validate_invoice_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate an invoice-source binding before it reaches runtime."""
    _validated_invoice_selector(binding)


def validate_invoice_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate an invoice-source binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector against
    :class:`_InvoiceSelector` and lifts the invoice fact/op invariants to build
    time, preserving the underlying pydantic field error. This is the
    ``list[str]`` companion to the raise-style
    :func:`validate_invoice_binding_definition` (kept as a defence-in-depth
    resolve-time re-check).
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
    if selector.fact in {"base_sum", "rectified_base_delta_sum"} and op != BindingAggregationOp.SUM:
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
    return resolve_invoice_family_scalar_values(
        revision,
        source_kinds=INVOICE_BINDING_SOURCE_KINDS,
        validate_selector=_validated_invoice_selector,
        observations_for_binding=lambda _binding: available,
    )


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
    return resolve_invoice_family_row_values(
        revision,
        source_kinds=INVOICE_BINDING_SOURCE_KINDS,
        validate_selector=_validated_invoice_selector,
        observations_for_binding=lambda _binding: available,
        cohort_by_source=False,
    )


def _build_invoice_rows(
    grouping: _InvoiceGrouping,
    observations: tuple[InvoiceObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    if grouping == "operator_clave":
        return _build_operator_clave_rows(observations)
    if grouping == "operator_clave_period":
        return _build_operator_clave_period_rows(observations)
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


class _OperatorClaveAccumulator(BaseModel):
    """Mutable accumulator for operator_clave row aggregation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    country_code: str
    party_tax_id: str
    clave: str
    party_legal_name: str | None
    base_total: Decimal


class _OperatorClavePeriodAccumulator(BaseModel):
    """Mutable accumulator for operator_clave_period row aggregation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    country_code: str
    party_tax_id: str
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
    for observation in observations:
        if selector.rectification_scope == "only_rectifications" and not observation.is_rectification:
            continue
        if selector.rectification_scope == "exclude_rectifications" and observation.is_rectification:
            continue
        if clave_filter and observation.intracommunity_clave not in clave_filter:
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


# ---------------------------------------------------------------------------
