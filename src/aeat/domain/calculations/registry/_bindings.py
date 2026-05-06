"""Data binding helpers for registry-backed factual inputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._errors import RegistryValidationError
from ._schema import DataBindingDefinition, ModeloRevision

_RectificationScope = Literal["only_rectifications", "exclude_rectifications", "any"]

__all__ = [
    "DataBindingDefinition",
    "InvoiceObservation",
    "InvoiceObservationRequirement",
    "RegistryFilingObservation",
    "RegistryFilingObservationRequirement",
    "invoice_binding_requirements",
    "previous_filing_observation_requirements",
    "resolve_bound_casilla_inputs",
    "resolve_invoice_binding_row_values",
    "resolve_invoice_binding_values",
    "resolve_previous_filing_binding_values",
    "validate_invoice_binding_definition",
]

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


class RegistryFilingObservation(BaseModel):
    """Observed casilla values from a filed declaration."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    casilla_values: Mapping[str, Decimal]

    @field_validator("casilla_values")
    @classmethod
    def _values_are_decimal(cls, value: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
        for casilla_id, casilla_value in value.items():
            if not casilla_id:
                raise ValueError("observed casilla id must be non-empty")
            if isinstance(casilla_value, bool) or not isinstance(casilla_value, Decimal):
                raise ValueError(f"observed casilla {casilla_id!r} must be a Decimal")
        return value


class RegistryFilingObservationRequirement(BaseModel):
    """Filed declaration required by one or more registry bindings."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    binding_ids: tuple[str, ...] = Field(min_length=1)
    source_casillas: tuple[str, ...] = Field(min_length=1)

    @field_validator("binding_ids", "source_casillas")
    @classmethod
    def _values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("observation requirement tuple entries must be unique")
        return value


def resolve_bound_casilla_inputs(
    revision: ModeloRevision,
    facts: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """Resolve factual binding values into casilla input values.

    ``facts`` is keyed by registry binding id. The binding layer only selects
    factual values; it does not own legal rates, thresholds, or casilla meaning.
    """

    for key, value in facts.items():
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError(f"binding fact {key!r} must be a Decimal")
    binding_ids = {binding.id for binding in revision.bindings}
    unknown = sorted(set(facts).difference(binding_ids))
    if unknown:
        raise RegistryValidationError(f"unknown binding fact ids: {unknown!r}")
    resolved: dict[str, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind != "bound":
            continue
        if casilla.binding is None:
            raise RegistryValidationError(f"bound casilla {casilla.id!r} has no binding")
        if casilla.binding not in facts:
            raise RegistryValidationError(f"missing binding fact for casilla {casilla.id!r}: {casilla.binding!r}")
        resolved[casilla.id] = facts[casilla.binding]
    return resolved


def previous_filing_observation_requirements(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> tuple[RegistryFilingObservationRequirement, ...]:
    """Return filed declarations needed by previous-filing bindings."""

    grouped: dict[tuple[str, int, str], dict[str, set[str]]] = {}
    for binding in revision.bindings:
        if binding.source != "previous_filing":
            continue
        selector = _previous_filing_selector(binding)
        expected_year = filing_year + selector.filing_year_delta
        for required_period in selector.required_periods:
            key = (selector.source_modelo, expected_year, required_period)
            bucket = grouped.setdefault(key, {"binding_ids": set(), "source_casillas": set()})
            bucket["binding_ids"].add(binding.id)
            bucket["source_casillas"].update(selector.source_casillas)
    return tuple(
        RegistryFilingObservationRequirement(
            modelo=modelo,
            filing_year=expected_year,
            period=required_period,
            binding_ids=tuple(sorted(values["binding_ids"])),
            source_casillas=tuple(sorted(values["source_casillas"])),
        )
        for (modelo, expected_year, required_period), values in sorted(grouped.items())
    )


def resolve_previous_filing_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RegistryFilingObservation],
    *,
    filing_year: int,
    period: str,
) -> dict[str, Decimal]:
    """Resolve previous-filing bindings from observed filed declarations."""

    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "previous_filing":
            continue
        selector = _previous_filing_selector(binding)
        expected_year = filing_year + selector.filing_year_delta
        values = []
        for required_period in selector.required_periods:
            matches = tuple(
                observation
                for observation in available
                if observation.modelo == selector.source_modelo
                and observation.filing_year == expected_year
                and observation.period == required_period
            )
            if len(matches) != 1:
                raise RegistryValidationError(
                    f"binding {binding.id!r} expected one observed filing "
                    f"{selector.source_modelo!r}/{expected_year}/{required_period!r}, found {len(matches)}"
                )
            for casilla_id in selector.source_casillas:
                casilla_value = matches[0].casilla_values.get(casilla_id)
                if casilla_value is None:
                    raise RegistryValidationError(
                        f"binding {binding.id!r} requires observed casilla {casilla_id!r} "
                        f"from {selector.source_modelo!r}/{expected_year}/{required_period!r}"
                    )
                values.append(casilla_value)
        resolved[binding.id] = _aggregate_previous_filing_binding(binding, values)
    return resolved


class _PreviousFilingSelector(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year_delta: int = 0
    period: str | None = Field(default=None, min_length=1, max_length=8)
    source_periods: tuple[str, ...] = ()
    source_casillas: tuple[str, ...] = Field(min_length=1)

    @field_validator("source_periods")
    @classmethod
    def _source_periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("previous-filing source_periods entries must be unique")
        return value

    @property
    def required_periods(self) -> tuple[str, ...]:
        if self.period is not None:
            return (self.period,)
        return self.source_periods

    @field_validator("period")
    @classmethod
    def _period_not_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("previous-filing period must be non-empty")
        return value

    @field_validator("source_casillas")
    @classmethod
    def _source_casillas_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("previous-filing source_casillas entries must be unique")
        return value

    @model_validator(mode="after")
    def _validate_period_selector(self) -> _PreviousFilingSelector:
        if self.period is not None and self.source_periods:
            raise ValueError("previous-filing selector must use period or source_periods, not both")
        if self.period is None and not self.source_periods:
            raise ValueError("previous-filing selector must declare period or source_periods")
        return self


def _previous_filing_selector(binding: DataBindingDefinition) -> _PreviousFilingSelector:
    try:
        return _PreviousFilingSelector.model_validate(binding.selector)
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed previous-filing selector") from exc


def _aggregate_previous_filing_binding(binding: DataBindingDefinition, values: list[Decimal]) -> Decimal:
    op = str((binding.aggregation or {}).get("op", "sum"))
    if op == "sum":
        return sum(values, Decimal("0"))
    if op == "copy":
        if len(values) != 1:
            raise RegistryValidationError(f"binding {binding.id!r} copy aggregation requires one source casilla")
        return values[0]
    raise RegistryValidationError(f"binding {binding.id!r} uses unsupported previous-filing aggregation {op!r}")


# ---------------------------------------------------------------------------
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
    enum (E, M, H, A, T, S, I, R, D, C). ``vat_regime`` is open-ended so
    domestic-IVA modelos can carry their regime classification alongside.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    invoice_id: str = Field(min_length=1, max_length=128)
    party_tax_id: str = Field(min_length=1, max_length=64)
    country_code: str = Field(min_length=2, max_length=2)
    transaction_date: date
    base_amount: Decimal
    vat_regime: str | None = Field(default=None, max_length=64)
    intracommunity_clave: str | None = Field(default=None, max_length=2)
    is_rectification: bool = False
    rectified_year: int | None = Field(default=None, ge=2000, le=2099)
    rectified_period: str | None = Field(default=None, max_length=8)
    rectified_base_previous: Decimal | None = None
    party_legal_name: str | None = Field(default=None, max_length=200)

    @field_validator("country_code")
    @classmethod
    def _country_code_uppercase(cls, value: str) -> str:
        if value != value.upper():
            raise ValueError("country_code must be uppercase")
        if not value.isalpha():
            raise ValueError("country_code must be alphabetic")
        return value

    @field_validator("intracommunity_clave")
    @classmethod
    def _clave_uppercase(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value != value.upper():
            raise ValueError("intracommunity_clave must be uppercase")
        if value not in {"E", "M", "H", "A", "T", "S", "I", "R", "D", "C"}:
            raise ValueError(f"intracommunity_clave {value!r} is not an AEAT clave de operacion")
        return value

    @field_validator("base_amount", "rectified_base_previous")
    @classmethod
    def _decimal_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise ValueError("invoice amounts must be Decimal")
        return value

    @model_validator(mode="after")
    def _validate_rectification(self) -> InvoiceObservation:
        if self.is_rectification:
            if self.rectified_year is None or self.rectified_period is None:
                raise ValueError("rectification observation must declare rectified_year and rectified_period")
            if self.rectified_base_previous is None:
                raise ValueError("rectification observation must declare rectified_base_previous")
        else:
            if self.rectified_year is not None or self.rectified_period is not None:
                raise ValueError("non-rectification observation must not declare rectified_year/period")
            if self.rectified_base_previous is not None:
                raise ValueError("non-rectification observation must not declare rectified_base_previous")
        return self


class InvoiceObservationRequirement(BaseModel):
    """Invoice-fact slice declared by one or more invoice-source bindings.

    Modelo runtimes use this introspection to ask the invoice ledger for the
    minimal set of observations the bindings need.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    binding_ids: tuple[str, ...] = Field(min_length=1)
    claves: tuple[str, ...] = ()
    rectification_scope: _RectificationScope = "any"
    vat_regime: str | None = None

    @field_validator("binding_ids", "claves")
    @classmethod
    def _values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("invoice requirement tuple entries must be unique")
        return value


class _InvoiceSelector(BaseModel):
    """Strict validator for the selector mapping of an invoice-source binding."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    fact: str = Field(min_length=1, max_length=64)
    claves: tuple[str, ...] = ()
    rectification_scope: _RectificationScope = "any"
    vat_regime: str | None = Field(default=None, max_length=64)
    row_field: _InvoiceRowField | None = None
    grouping: _InvoiceGrouping | None = None

    @field_validator("claves")
    @classmethod
    def _claves_uppercase_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("invoice selector claves entries must be unique")
        for clave in value:
            if clave != clave.upper():
                raise ValueError("invoice selector clave must be uppercase")
            if clave not in {"E", "M", "H", "A", "T", "S", "I", "R", "D", "C"}:
                raise ValueError(f"invoice selector clave {clave!r} is not an AEAT clave de operacion")
        return value


def _invoice_selector(binding: DataBindingDefinition) -> _InvoiceSelector:
    try:
        return _InvoiceSelector.model_validate(binding.selector)
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed invoice selector") from exc


def invoice_binding_requirements(
    revision: ModeloRevision,
) -> tuple[InvoiceObservationRequirement, ...]:
    """Return invoice ledger slices needed by ``revision``'s invoice bindings."""

    grouped: dict[
        tuple[tuple[str, ...], _RectificationScope, str | None],
        set[str],
    ] = {}
    for binding in revision.bindings:
        if binding.source != "invoice":
            continue
        selector = _validated_invoice_selector(binding)
        key = (tuple(sorted(selector.claves)), selector.rectification_scope, selector.vat_regime)
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
                vat_regime=regime,
            )
        )
    return tuple(requirements)


_INVOICE_FACTS = {
    "operator_count",
    "base_sum",
    "rectified_base_delta_sum",
    "row_field",
}

_OPERATOR_CLAVE_PERIOD_ONLY_FIELDS: frozenset[str] = frozenset(
    {"rectified_year", "rectified_period", "rectified_base_previous"}
)


def validate_invoice_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate an invoice-source binding before it reaches runtime."""

    _validated_invoice_selector(binding)


def _validated_invoice_selector(binding: DataBindingDefinition) -> _InvoiceSelector:
    selector = _invoice_selector(binding)
    _validate_invoice_fact_and_aggregation(binding, selector)
    return selector


def _validate_invoice_fact_and_aggregation(binding: DataBindingDefinition, selector: _InvoiceSelector) -> None:
    if selector.fact not in _INVOICE_FACTS:
        raise RegistryValidationError(f"binding {binding.id!r} declares unsupported invoice fact {selector.fact!r}")
    op = str((binding.aggregation or {}).get("op", "sum"))
    if selector.fact == "operator_count" and op != "count_distinct":
        raise RegistryValidationError(
            f"binding {binding.id!r} fact 'operator_count' requires aggregation op 'count_distinct'"
        )
    if selector.fact in {"base_sum", "rectified_base_delta_sum"} and op != "sum":
        raise RegistryValidationError(f"binding {binding.id!r} fact {selector.fact!r} requires aggregation op 'sum'")
    if selector.fact == "rectified_base_delta_sum" and selector.rectification_scope != "only_rectifications":
        raise RegistryValidationError(
            f"binding {binding.id!r} fact 'rectified_base_delta_sum' requires rectification_scope 'only_rectifications'"
        )
    if selector.fact == "row_field":
        if op != "rows":
            raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
        if selector.row_field is None:
            raise RegistryValidationError(
                f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key"
            )
        if selector.grouping is None:
            raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'grouping' selector key")
        if selector.grouping == "operator_clave_period" and selector.rectification_scope != "only_rectifications":
            raise RegistryValidationError(
                f"binding {binding.id!r} grouping 'operator_clave_period' requires "
                f"rectification_scope 'only_rectifications'"
            )
        if selector.row_field in _OPERATOR_CLAVE_PERIOD_ONLY_FIELDS:
            if selector.grouping != "operator_clave_period":
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} requires grouping 'operator_clave_period'"
                )
            if selector.rectification_scope != "only_rectifications":
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} requires "
                    f"rectification_scope 'only_rectifications'"
                )
    elif selector.row_field is not None or selector.grouping is not None:
        raise RegistryValidationError(f"binding {binding.id!r} non-row fact must not declare row_field or grouping")
    if op == "rows" and selector.fact != "row_field":
        raise RegistryValidationError(f"binding {binding.id!r} aggregation op 'rows' requires fact 'row_field'")


def resolve_invoice_binding_values(
    revision: ModeloRevision,
    observations: Iterable[InvoiceObservation],
) -> dict[str, Decimal]:
    """Resolve scalar invoice-source bindings into Decimal aggregates.

    Row-producer bindings (``aggregation.op == "rows"``) are skipped here; they
    are resolved by :func:`resolve_invoice_binding_row_values`.
    """

    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "invoice":
            continue
        selector = _validated_invoice_selector(binding)
        if selector.fact == "row_field":
            continue
        scope_filtered = tuple(_filter_invoice_observations(available, selector))
        resolved[binding.id] = _aggregate_invoice_binding(binding, selector, scope_filtered)
    return resolved


def resolve_invoice_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[InvoiceObservation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer invoice bindings into per-row indexed values.

    Bindings with ``aggregation.op == "rows"`` aggregate observations into rows
    deterministically grouped by ``selector.grouping``. Bindings sharing the
    same grouping/scope/clave-filter share row indexes, so that an export
    record with ``repeat = "binding_rows"`` can correlate field values across
    bindings on the same row. Returns a flat mapping keyed by
    ``(binding_id, row_index)``. Row indexes are one-based to match
    ``FilingBindingValue.row_index``.
    """

    available = tuple(observations)
    resolved: dict[tuple[str, int], Decimal | str] = {}
    # Group bindings by (grouping, rectification_scope, claves, vat_regime) so
    # that bindings sharing a row source share row indexes.
    cohorts: dict[
        tuple[_InvoiceGrouping, _RectificationScope, tuple[str, ...], str | None],
        list[tuple[DataBindingDefinition, _InvoiceSelector]],
    ] = {}
    for binding in revision.bindings:
        if binding.source != "invoice":
            continue
        selector = _validated_invoice_selector(binding)
        if selector.fact != "row_field":
            continue
        assert selector.grouping is not None  # guarded by validator
        cohort_key = (
            selector.grouping,
            selector.rectification_scope,
            tuple(sorted(selector.claves)),
            selector.vat_regime,
        )
        cohorts.setdefault(cohort_key, []).append((binding, selector))
    for cohort_key, members in cohorts.items():
        grouping = cohort_key[0]
        # The cohort selector for filtering is constant across members; use the
        # first member's selector for filtering.
        _, sample_selector = members[0]
        scope_filtered = tuple(_filter_invoice_observations(available, sample_selector))
        rows = _build_invoice_rows(grouping, scope_filtered)
        for binding, selector in members:
            assert selector.row_field is not None  # guarded by validator
            for row_index, row in enumerate(rows, start=1):
                value = row.get(selector.row_field)
                if value is None:
                    raise RegistryValidationError(
                        f"binding {binding.id!r} row_field {selector.row_field!r} not produced "
                        f"for grouping {grouping!r}"
                    )
                resolved[(binding.id, row_index)] = value
    return resolved


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
                "operator_clave_period grouping requires rectification metadata on every observation"
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

    model_config = ConfigDict(strict=True)

    country_code: str
    party_tax_id: str
    clave: str
    party_legal_name: str | None
    base_total: Decimal


class _OperatorClavePeriodAccumulator(BaseModel):
    """Mutable accumulator for operator_clave_period row aggregation."""

    model_config = ConfigDict(strict=True)

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
        if selector.vat_regime is not None and observation.vat_regime != selector.vat_regime:
            continue
        yield observation


def _aggregate_invoice_binding(
    binding: DataBindingDefinition,
    selector: _InvoiceSelector,
    observations: tuple[InvoiceObservation, ...],
) -> Decimal:
    op = str((binding.aggregation or {}).get("op", "sum"))
    if selector.fact == "operator_count":
        if op != "count_distinct":
            raise RegistryValidationError(
                f"binding {binding.id!r} fact 'operator_count' requires aggregation op 'count_distinct'"
            )
        operators = {(observation.party_tax_id, observation.country_code) for observation in observations}
        return Decimal(len(operators))
    if selector.fact == "base_sum":
        if op != "sum":
            raise RegistryValidationError(f"binding {binding.id!r} fact 'base_sum' requires aggregation op 'sum'")
        return sum((observation.base_amount for observation in observations), Decimal("0"))
    if selector.fact == "rectified_base_delta_sum":
        if op != "sum":
            raise RegistryValidationError(
                f"binding {binding.id!r} fact 'rectified_base_delta_sum' requires aggregation op 'sum'"
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
