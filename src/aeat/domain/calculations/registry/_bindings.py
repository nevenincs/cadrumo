"""Data binding helpers for registry-backed factual inputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...vat import (
    EUMemberState,
    InvoiceDirection,
    OssIossRegime,
    TransactionKind,
    VATRateKind,
)
from ._errors import RegistryValidationError
from ._schema import DataBindingDefinition, ModeloRevision

_RectificationScope = Literal["only_rectifications", "exclude_rectifications", "any"]

__all__ = [
    "DataBindingDefinition",
    "InvoiceObservation",
    "InvoiceObservationRequirement",
    "IvaLedgerObservation",
    "OssIossLedgerObservation",
    "RentaExpenseObservationProtocol",
    "RegistryFilingObservation",
    "RegistryFilingObservationRequirement",
    "invoice_binding_requirements",
    "previous_filing_observation_requirements",
    "resolve_bound_casilla_inputs",
    "resolve_invoice_binding_row_values",
    "resolve_invoice_binding_values",
    "resolve_ledger_iva_aggregation_binding_values",
    "resolve_ledger_oss_aggregation_binding_values",
    "resolve_ledger_renta_expense_aggregation_binding_values",
    "resolve_previous_filing_binding_values",
    "validate_invoice_binding_definition",
    "validate_ledger_iva_aggregation_binding_definition",
    "validate_ledger_oss_aggregation_binding_definition",
    "validate_ledger_renta_expense_aggregation_binding_definition",
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
                raise RegistryValidationError("observed casilla id must be non-empty")
            if isinstance(casilla_value, bool) or not isinstance(casilla_value, Decimal):
                raise RegistryValidationError(f"observed casilla {casilla_id!r} must be a Decimal")
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
            raise RegistryValidationError("observation requirement tuple entries must be unique")
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
            raise RegistryValidationError("previous-filing source_periods entries must be unique")
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
            raise RegistryValidationError("previous-filing period must be non-empty")
        return value

    @field_validator("source_casillas")
    @classmethod
    def _source_casillas_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("previous-filing source_casillas entries must be unique")
        return value

    @model_validator(mode="after")
    def _validate_period_selector(self) -> _PreviousFilingSelector:
        if self.period is not None and self.source_periods:
            raise RegistryValidationError("previous-filing selector must use period or source_periods, not both")
        if self.period is None and not self.source_periods:
            raise RegistryValidationError("previous-filing selector must declare period or source_periods")
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
            raise RegistryValidationError("country_code must be uppercase")
        if not value.isalpha():
            raise RegistryValidationError("country_code must be alphabetic")
        return value

    @field_validator("intracommunity_clave")
    @classmethod
    def _clave_uppercase(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value != value.upper():
            raise RegistryValidationError("intracommunity_clave must be uppercase")
        if value not in {"E", "M", "H", "A", "T", "S", "I", "R", "D", "C"}:
            raise RegistryValidationError(f"intracommunity_clave {value!r} is not an AEAT clave de operacion")
        return value

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
        if self.is_rectification:
            if self.rectified_year is None or self.rectified_period is None:
                raise RegistryValidationError(
                    "rectification observation must declare rectified_year and rectified_period"
                )
            if self.rectified_base_previous is None:
                raise RegistryValidationError("rectification observation must declare rectified_base_previous")
        else:
            if self.rectified_year is not None or self.rectified_period is not None:
                raise RegistryValidationError("non-rectification observation must not declare rectified_year/period")
            if self.rectified_base_previous is not None:
                raise RegistryValidationError("non-rectification observation must not declare rectified_base_previous")
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
            raise RegistryValidationError("invoice requirement tuple entries must be unique")
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
                    }
                )
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
                }
            )
        )
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


# ---------------------------------------------------------------------------
# Ledger OSS / IOSS aggregation source bindings.
#
# These bindings aggregate ledger lines whose VAT classification matches a
# regime + destination Member State + rate tier + invoice direction selector.
# The classification axes come from :mod:`aeat.domain.vat`; the binding source
# is the registry's ledger-driven aggregation kind for Modelo 369.
#
# The selector keys are validated against the substrate's closed enums at
# binding-definition time; the runtime resolver then consumes
# :class:`OssIossLedgerObservation` instances (per-line ledger facts already
# tagged with the substrate classification) and returns the aggregated value.
# ---------------------------------------------------------------------------


class OssIossLedgerObservation(BaseModel):
    """One factual ledger line tagged with substrate-grounded classification.

    Modelo 369 binding selectors filter these observations by the four
    classification axes (regime, destination Member State, rate tier,
    invoice direction) plus the optional transaction kind set; the
    runtime aggregates the matched lines through the binding's
    aggregation operator.

    Attributes:
        ledger_id: Stable id of the source ledger line.
        transaction_date: When the supply takes place.
        regime: OSS / IOSS Esquema the line is filed under.
        destination_member_state: Member State of consumption (the
            destination MS for the supply, which determines the
            applicable VAT rate per the OSS / IOSS rules).
        rate_kind: Substrate rate tier (general / reduced / etc.).
        invoice_direction: Whether the autónomo issued or received
            the invoice.
        transaction_kind: Substrate :class:`aeat.domain.vat.TransactionKind`
            the line resolves to.
        base_amount: Taxable base in EUR.
        iva_amount: VAT amount in EUR (already applied at the
            destination MS rate per OSS / IOSS rules).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ledger_id: str = Field(min_length=1, max_length=128)
    transaction_date: date
    regime: OssIossRegime
    destination_member_state: EUMemberState
    rate_kind: VATRateKind
    invoice_direction: InvoiceDirection
    transaction_kind: TransactionKind
    base_amount: Decimal
    iva_amount: Decimal


class _OssIossLedgerSelector(BaseModel):
    """Validated form of a ledger_oss_aggregation binding selector.

    The selector is expressed in TOML as a mapping of string-valued
    keys (the registry binding selector contract); this record coerces
    those strings into substrate enum members at validation time so
    downstream consumers see typed values.
    """

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    regime: OssIossRegime
    destination_member_state: EUMemberState
    rate_kind: VATRateKind
    invoice_direction: InvoiceDirection
    transaction_kinds: tuple[TransactionKind, ...] = Field(min_length=1)
    fact: Literal["iva_amount_sum", "base_amount_sum"] = "iva_amount_sum"

    @field_validator("transaction_kinds", mode="after")
    @classmethod
    def _kinds_unique(cls, value: tuple[TransactionKind, ...]) -> tuple[TransactionKind, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("transaction_kinds entries must be unique")
        return value


def _ledger_oss_selector(binding: DataBindingDefinition) -> _OssIossLedgerSelector:
    """Validate and parse a binding selector into a typed OSS / IOSS selector."""
    try:
        return _OssIossLedgerSelector.model_validate(dict(binding.selector))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed ledger_oss_aggregation selector") from exc


def validate_ledger_oss_aggregation_binding_definition(
    binding: DataBindingDefinition,
) -> None:
    """Validate a ``ledger_oss_aggregation`` binding's selector and aggregation.

    Raises:
        RegistryValidationError: If the selector is malformed (unknown
            regime / member state / rate kind / invoice direction /
            transaction kind), or if the aggregation operator is
            inconsistent with the declared fact.
    """
    if binding.source != "ledger_oss_aggregation":
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_oss_aggregation source")
    selector = _ledger_oss_selector(binding)

    if binding.aggregation is not None:
        op = str(binding.aggregation.get("op", "sum"))
        if op != "sum":
            raise RegistryValidationError(
                f"binding {binding.id!r} ledger_oss_aggregation supports only aggregation op 'sum', got {op!r}"
            )

    if selector.fact not in {"iva_amount_sum", "base_amount_sum"}:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_oss_aggregation supports only "
            f"facts {{iva_amount_sum, base_amount_sum}}, got {selector.fact!r}"
        )


def resolve_ledger_oss_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[OssIossLedgerObservation],
) -> dict[str, Decimal]:
    """Resolve every ``ledger_oss_aggregation`` binding on ``revision``.

    For each binding, observations are filtered by the four
    classification axes plus the transaction-kind set; matched
    observations are aggregated through the binding's declared fact
    (``iva_amount_sum`` defaults; ``base_amount_sum`` selects the base).
    The resolver is deterministic and side-effect-free.

    Args:
        revision: The :class:`ModeloRevision` whose bindings to resolve.
        observations: Iterable of substrate-classified ledger lines.

    Returns:
        Mapping of binding id to the aggregated Decimal value. Empty
        match sets resolve to ``Decimal("0")``.

    Raises:
        RegistryValidationError: If any selector is malformed.
    """
    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "ledger_oss_aggregation":
            continue
        selector = _ledger_oss_selector(binding)
        kinds = set(selector.transaction_kinds)
        matched = [
            observation
            for observation in available
            if observation.regime is selector.regime
            and observation.destination_member_state is selector.destination_member_state
            and observation.rate_kind is selector.rate_kind
            and observation.invoice_direction is selector.invoice_direction
            and observation.transaction_kind in kinds
        ]
        if selector.fact == "iva_amount_sum":
            total = sum((observation.iva_amount for observation in matched), Decimal("0"))
        else:
            total = sum((observation.base_amount for observation in matched), Decimal("0"))
        resolved[binding.id] = total
    return resolved


# ---------------------------------------------------------------------------
# Ledger IVA aggregation source bindings (cross-modelo IVA roll-out).
#
# Generic counterpart to :func:`resolve_ledger_oss_aggregation_binding_values`
# for the standard IVA modelos (303 autoliquidación trimestral, 322 grupos
# individual, 353 grupos agregado, 309 no periódica, 390 resumen anual).
# Aggregates ledger lines by the canonical IVA classification triple
# (VATCategory + VATRateKind + IvaFlowDirection) introduced by the
# IvaFlowDirection codification slice.
#
# OSS / IOSS bindings keep their dedicated source kind because they
# additionally carry the regime + destination Member State axes; this
# generic source covers domestic IVA, intra-community supplies /
# acquisitions, exports, imports, recargo de equivalencia, and
# domestic-reverse-charge operations.
# ---------------------------------------------------------------------------


from ...vat import VATCategory
from ...vat._flow import IvaFlowDirection


class IvaLedgerObservation(BaseModel):
    """One factual ledger line tagged with the IVA classification triple.

    Modelo 303 / 322 / 353 / 309 / 390 binding selectors filter these
    observations by category, rate kind, and flow direction; the
    runtime aggregates the matched lines through the binding's
    aggregation operator.

    Attributes:
        ledger_id: Stable id of the source ledger line.
        transaction_date: When the supply takes place.
        category: Substrate :class:`VATCategory` resolved by the
            classifier.
        rate_kind: Substrate :class:`VATRateKind` rate tier.
        flow_direction: Substrate :class:`IvaFlowDirection` (output /
            input / self-assessed reverse charge).
        base_amount: Taxable base in EUR.
        iva_amount: VAT amount in EUR (cuota repercutida or soportada,
            depending on flow direction).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ledger_id: str = Field(min_length=1, max_length=128)
    transaction_date: date
    category: VATCategory
    rate_kind: VATRateKind
    flow_direction: IvaFlowDirection
    base_amount: Decimal
    iva_amount: Decimal


class _IvaLedgerSelector(BaseModel):
    """Validated form of a ledger_iva_aggregation binding selector."""

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    categories: tuple[VATCategory, ...] = Field(min_length=1)
    rate_kinds: tuple[VATRateKind, ...] = Field(min_length=1)
    flow_direction: IvaFlowDirection
    fact: Literal["iva_amount_sum", "base_amount_sum"] = "iva_amount_sum"

    @field_validator("categories", mode="after")
    @classmethod
    def _categories_unique(cls, value: tuple[VATCategory, ...]) -> tuple[VATCategory, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("categories entries must be unique")
        return value

    @field_validator("rate_kinds", mode="after")
    @classmethod
    def _rate_kinds_unique(cls, value: tuple[VATRateKind, ...]) -> tuple[VATRateKind, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("rate_kinds entries must be unique")
        return value


def _iva_ledger_selector(binding: DataBindingDefinition) -> _IvaLedgerSelector:
    """Validate and parse a binding selector into a typed IVA selector."""
    try:
        return _IvaLedgerSelector.model_validate(dict(binding.selector))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed ledger_iva_aggregation selector") from exc


def validate_ledger_iva_aggregation_binding_definition(
    binding: DataBindingDefinition,
) -> None:
    """Validate a ``ledger_iva_aggregation`` binding's selector and aggregation.

    Raises:
        RegistryValidationError: If the selector is malformed (unknown
            category / rate kind / flow direction / fact, empty
            tuple), if the aggregation operator is not "sum", or if
            the binding source is not "ledger_iva_aggregation".
    """
    if binding.source != "ledger_iva_aggregation":
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_iva_aggregation source")
    selector = _iva_ledger_selector(binding)

    if binding.aggregation is not None:
        op = str(binding.aggregation.get("op", "sum"))
        if op != "sum":
            raise RegistryValidationError(
                f"binding {binding.id!r} ledger_iva_aggregation supports only aggregation op 'sum', got {op!r}"
            )

    if selector.fact not in {"iva_amount_sum", "base_amount_sum"}:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_iva_aggregation supports only "
            f"facts {{iva_amount_sum, base_amount_sum}}, got {selector.fact!r}"
        )


def resolve_ledger_iva_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
) -> dict[str, Decimal]:
    """Resolve every ``ledger_iva_aggregation`` binding on ``revision``.

    Filters observations by the three classification axes (category in
    selector.categories, rate_kind in selector.rate_kinds, flow_direction
    matches selector.flow_direction) and aggregates the matched lines'
    iva_amount or base_amount per the declared fact.

    Args:
        revision: The :class:`ModeloRevision` whose bindings to resolve.
        observations: Iterable of substrate-classified ledger lines.

    Returns:
        Mapping of binding id to the aggregated Decimal value. Empty
        match sets resolve to ``Decimal("0")``.
    """
    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "ledger_iva_aggregation":
            continue
        selector = _iva_ledger_selector(binding)
        cat_set = set(selector.categories)
        kind_set = set(selector.rate_kinds)
        matched = [
            observation
            for observation in available
            if observation.category in cat_set
            and observation.rate_kind in kind_set
            and observation.flow_direction is selector.flow_direction
        ]
        if selector.fact == "iva_amount_sum":
            total = sum((observation.iva_amount for observation in matched), Decimal("0"))
        else:
            total = sum((observation.base_amount for observation in matched), Decimal("0"))
        resolved[binding.id] = total
    return resolved


# ---------------------------------------------------------------------------
# Ledger Renta deductible-expense aggregation source bindings.
#
# These bindings consume first-slice Modelo 100 expense observations produced
# by the ledger/Renta aggregation layer. They deliberately aggregate already
# evaluated deductible amounts, so proportionality, legal category eligibility,
# invoice reconciliation, and period/date filtering stay outside the registry
# formula runtime.
#
# The registry accesses only four attributes on each observation. A Protocol
# avoids a cross-domain import (domain.calculations -> domain.renta) that
# violated the hexagonal boundary (linkage-design-audit F7).
# ---------------------------------------------------------------------------

# Casilla IDs covered by the first Renta expense slice (Modelo 100, period 0A).
# These must stay in sync with the binding selectors in the TOML; they are
# validated at registry load time so mismatches surface before any calculation.
_RENTA_100_FIRST_SLICE_CASILLAS: frozenset[str] = frozenset({"0186", "0192", "0199", "0203"})


class RentaExpenseObservationProtocol(Protocol):
    """Structural protocol for first-slice Renta expense observations.

    The registry only needs these four attributes to resolve
    ``ledger_renta_expense_aggregation`` bindings; the full
    :class:`~aeat.domain.renta.RentaDeductibleExpenseObservation` satisfies
    this protocol without any explicit declaration.

    Properties are declared read-only so that Literal-typed concrete attributes
    (e.g. ``modelo: Literal["100"]``) satisfy the protocol under strict
    covariant checking.
    """

    @property
    def modelo(self) -> str: ...

    @property
    def period(self) -> str: ...

    @property
    def target_casilla(self) -> str: ...

    @property
    def deductible_amount(self) -> Decimal: ...


class _RentaLedgerExpenseSelector(BaseModel):
    """Validated form of a ledger_renta_expense_aggregation binding selector."""

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    modelo: Literal["100"] = "100"
    period: Literal["0A"] = "0A"
    target_casilla: str = Field(min_length=4, max_length=4)
    fact: Literal["deductible_amount_sum"] = "deductible_amount_sum"


def _renta_ledger_expense_selector(binding: DataBindingDefinition) -> _RentaLedgerExpenseSelector:
    try:
        return _RentaLedgerExpenseSelector.model_validate(dict(binding.selector))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_renta_expense_aggregation selector"
        ) from exc


def validate_ledger_renta_expense_aggregation_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate a ``ledger_renta_expense_aggregation`` binding definition."""

    if binding.source != "ledger_renta_expense_aggregation":
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_renta_expense_aggregation source")
    selector = _renta_ledger_expense_selector(binding)
    if selector.target_casilla not in _RENTA_100_FIRST_SLICE_CASILLAS:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla {selector.target_casilla!r} "
            "is outside the first Modelo 100 Renta ledger expense slice"
        )
    op = str((binding.aggregation or {}).get("op", "sum"))
    if op != "sum":
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_expense_aggregation supports only aggregation op 'sum', got {op!r}"
        )
    if selector.fact != "deductible_amount_sum":
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_expense_aggregation supports only "
            f"fact 'deductible_amount_sum', got {selector.fact!r}"
        )


def resolve_ledger_renta_expense_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RentaExpenseObservationProtocol],
) -> dict[str, Decimal]:
    """Resolve every ``ledger_renta_expense_aggregation`` binding on ``revision``."""

    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "ledger_renta_expense_aggregation":
            continue
        selector = _renta_ledger_expense_selector(binding)
        matched = [
            observation
            for observation in available
            if observation.modelo == selector.modelo
            and observation.period == selector.period
            and observation.target_casilla == selector.target_casilla
        ]
        resolved[binding.id] = sum((observation.deductible_amount for observation in matched), Decimal("0"))
    return resolved


COUNTERPART_BINDING_SOURCE_KINDS: frozenset[str] = frozenset(
    {"invoice", "ledger_transaction", "purchase_invoice_evidence", "payable_invoice", "collectible_invoice"}
)


class CounterpartAggregationObservation(BaseModel):
    """One factual line from the user's counterpart aggregation source.

    Mirrors :class:`InvoiceObservation` plus a ``source_kind`` field that is
    matched against the declared counterpart-source binding.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_kind: str = Field(default="ledger_transaction", min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=128)
    party_tax_id: str = Field(min_length=1, max_length=64)
    country_code: str = Field(min_length=2, max_length=2)
    transaction_date: date
    base_amount: Decimal
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
            raise RegistryValidationError("country_code must be uppercase")
        if not value.isalpha():
            raise RegistryValidationError("country_code must be alphabetic")
        return value

    @field_validator("intracommunity_clave")
    @classmethod
    def _clave_uppercase(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value != value.upper():
            raise RegistryValidationError("intracommunity_clave must be uppercase")
        if value not in {"E", "M", "H", "A", "T", "S", "I", "R", "D", "C"}:
            raise RegistryValidationError(f"intracommunity_clave {value!r} is not an AEAT clave de operacion")
        return value

    @field_validator("base_amount", "rectified_base_previous")
    @classmethod
    def _decimal_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("counterpart amounts must be Decimal")
        return value

    @model_validator(mode="after")
    def _validate_rectification(self) -> CounterpartAggregationObservation:
        if self.is_rectification:
            if self.rectified_year is None or self.rectified_period is None:
                raise RegistryValidationError(
                    "rectification observation must declare rectified_year and rectified_period"
                )
            if self.rectified_base_previous is None:
                raise RegistryValidationError("rectification observation must declare rectified_base_previous")
        else:
            if self.rectified_year is not None or self.rectified_period is not None:
                raise RegistryValidationError("non-rectification observation must not declare rectified_year/period")
            if self.rectified_base_previous is not None:
                raise RegistryValidationError("non-rectification observation must not declare rectified_base_previous")
        return self


class CounterpartObservationRequirement(BaseModel):
    """Counterpart slice declared by one or more counterpart-source bindings."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    binding_ids: tuple[str, ...] = Field(min_length=1)
    source_kinds: tuple[str, ...] = Field(min_length=1)
    claves: tuple[str, ...] = ()
    rectification_scope: _RectificationScope = "any"

    @field_validator("binding_ids", "claves", "source_kinds")
    @classmethod
    def _values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("counterpart requirement tuple entries must be unique")
        return value


_COUNTERPART_FACTS = _INVOICE_FACTS


def _validated_counterpart_selector(binding: DataBindingDefinition) -> _InvoiceSelector:
    """Validate a counterpart-source binding selector with counterpart-flavoured errors."""

    selector = _invoice_selector(binding)
    if selector.fact not in _COUNTERPART_FACTS:
        raise RegistryValidationError(
            f"binding {binding.id!r} declares unsupported counterpart aggregation fact {selector.fact!r}"
        )
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
        if selector.row_field in _OPERATOR_CLAVE_PERIOD_ONLY_FIELDS:
            if selector.grouping != "operator_clave_period":
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} requires grouping 'operator_clave_period'"
                )
            if selector.rectification_scope != "only_rectifications":
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} "
                    f"requires rectification_scope 'only_rectifications'"
                )
        if selector.grouping == "operator_clave_period" and selector.rectification_scope != "only_rectifications":
            raise RegistryValidationError(
                f"binding {binding.id!r} grouping 'operator_clave_period' requires "
                f"rectification_scope 'only_rectifications'"
            )
    return selector


def _counterpart_to_invoice(observation: CounterpartAggregationObservation) -> InvoiceObservation:
    return InvoiceObservation(
        invoice_id=observation.source_id,
        party_tax_id=observation.party_tax_id,
        country_code=observation.country_code,
        transaction_date=observation.transaction_date,
        base_amount=observation.base_amount,
        vat_regime=None,
        intracommunity_clave=observation.intracommunity_clave,
        is_rectification=observation.is_rectification,
        rectified_year=observation.rectified_year,
        rectified_period=observation.rectified_period,
        rectified_base_previous=observation.rectified_base_previous,
        party_legal_name=observation.party_legal_name,
    )


def counterpart_binding_requirements(
    revision: ModeloRevision,
) -> tuple[CounterpartObservationRequirement, ...]:
    """Return counterpart slices needed by ``revision``'s counterpart bindings."""

    grouped: dict[tuple[tuple[str, ...], tuple[str, ...], _RectificationScope], set[str]] = {}
    for binding in revision.bindings:
        if binding.source not in COUNTERPART_BINDING_SOURCE_KINDS:
            continue
        selector = _validated_counterpart_selector(binding)
        source_kinds = (binding.source,)
        key = (source_kinds, tuple(sorted(selector.claves)), selector.rectification_scope)
        grouped.setdefault(key, set()).add(binding.id)
    requirements: list[CounterpartObservationRequirement] = []
    for (source_kinds, claves, scope), binding_ids in sorted(
        grouped.items(),
        key=lambda item: (item[0][0], item[0][1], item[0][2]),
    ):
        requirements.append(
            CounterpartObservationRequirement(
                binding_ids=tuple(sorted(binding_ids)),
                source_kinds=source_kinds,
                claves=claves,
                rectification_scope=scope,
            )
        )
    return tuple(requirements)


def resolve_counterpart_binding_values(
    revision: ModeloRevision,
    observations: Iterable[CounterpartAggregationObservation],
) -> dict[str, Decimal]:
    """Resolve scalar counterpart-source bindings into Decimal aggregates."""

    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if binding.source not in COUNTERPART_BINDING_SOURCE_KINDS:
            continue
        selector = _validated_counterpart_selector(binding)
        if selector.fact == "row_field":
            continue
        matched = tuple(
            _counterpart_to_invoice(observation)
            for observation in available
            if binding.source == "invoice" or observation.source_kind == binding.source
        )
        scope_filtered = tuple(_filter_invoice_observations(matched, selector))
        resolved[binding.id] = _aggregate_invoice_binding(binding, selector, scope_filtered)
    return resolved


def resolve_counterpart_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[CounterpartAggregationObservation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer counterpart-source bindings into per-row indexed values."""

    available = tuple(observations)
    resolved: dict[tuple[str, int], Decimal | str] = {}
    cohorts: dict[
        tuple[str, _InvoiceGrouping, _RectificationScope, tuple[str, ...]],
        list[tuple[DataBindingDefinition, _InvoiceSelector]],
    ] = {}
    for binding in revision.bindings:
        if binding.source not in COUNTERPART_BINDING_SOURCE_KINDS:
            continue
        selector = _validated_counterpart_selector(binding)
        if selector.fact != "row_field":
            continue
        assert selector.grouping is not None
        cohort_key = (
            binding.source,
            selector.grouping,
            selector.rectification_scope,
            tuple(sorted(selector.claves)),
        )
        cohorts.setdefault(cohort_key, []).append((binding, selector))
    for cohort_key, members in cohorts.items():
        source_kind, grouping, _, _ = cohort_key
        _, sample_selector = members[0]
        matched = tuple(
            _counterpart_to_invoice(observation)
            for observation in available
            if source_kind == "invoice" or observation.source_kind == source_kind
        )
        scope_filtered = tuple(_filter_invoice_observations(matched, sample_selector))
        rows = _build_invoice_rows(grouping, scope_filtered)
        for binding, selector in members:
            assert selector.row_field is not None
            for row_index, row in enumerate(rows, start=1):
                value = row.get(selector.row_field)
                if value is None:
                    raise RegistryValidationError(
                        f"binding {binding.id!r} row_field {selector.row_field!r} not produced "
                        f"for grouping {grouping!r}"
                    )
                resolved[(binding.id, row_index)] = value
    return resolved


_WithholdingRowField = Literal[
    "perceptor_tax_id",
    "perceptor_legal_name",
    "country_code",
    "clave",
    "subclave",
    "percibido_dinerario",
    "percibido_especie",
    "retencion_practicada",
    "ingreso_a_cuenta",
]
_WithholdingGrouping = Literal["per_perceptor", "per_perceptor_clave"]
_WITHHOLDING_FACTS = frozenset({"row_field", "perceptor_count", "percibido_sum", "retencion_sum"})


class WithholdingObservation(BaseModel):
    """Per-perceptor retencion / ingreso-a-cuenta observation for modelo 190 / 193."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_id: str = Field(min_length=1, max_length=128)
    perceptor_tax_id: str = Field(min_length=1, max_length=64)
    perceptor_legal_name: str = Field(default="", max_length=200)
    country_code: str = Field(default="ES", min_length=2, max_length=2)
    transaction_date: date
    clave: str = Field(min_length=1, max_length=2)
    subclave: str = Field(default="", max_length=4)
    percibido_dinerario: Decimal = Decimal("0")
    percibido_especie: Decimal = Decimal("0")
    retencion_practicada: Decimal = Decimal("0")
    ingreso_a_cuenta: Decimal = Decimal("0")

    @field_validator("country_code")
    @classmethod
    def _country_code_uppercase(cls, value: str) -> str:
        if value != value.upper() or not value.isalpha():
            raise RegistryValidationError("country_code must be uppercase alphabetic")
        return value

    @field_validator("clave")
    @classmethod
    def _clave_uppercase(cls, value: str) -> str:
        if value != value.upper():
            raise RegistryValidationError("withholding clave must be uppercase")
        return value

    @field_validator("percibido_dinerario", "percibido_especie", "retencion_practicada", "ingreso_a_cuenta")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("withholding amounts must be Decimal")
        if value < Decimal("0"):
            raise RegistryValidationError("withholding amounts must be non-negative")
        return value


class WithholdingObservationRequirement(BaseModel):
    """Withholding-source slice declared by one or more withholding bindings."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    binding_ids: tuple[str, ...] = Field(min_length=1)
    claves: tuple[str, ...] = ()

    @field_validator("binding_ids", "claves")
    @classmethod
    def _values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("withholding requirement tuple entries must be unique")
        return value


class _WithholdingSelector(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    fact: str = Field(min_length=1, max_length=64)
    claves: tuple[str, ...] = ()
    row_field: _WithholdingRowField | None = None
    grouping: _WithholdingGrouping | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)


def _withholding_selector(binding: DataBindingDefinition) -> _WithholdingSelector:
    try:
        return _WithholdingSelector.model_validate(binding.selector)
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed withholding selector") from exc


def _validated_withholding_selector(binding: DataBindingDefinition) -> _WithholdingSelector:
    selector = _withholding_selector(binding)
    if selector.fact not in _WITHHOLDING_FACTS:
        raise RegistryValidationError(
            f"binding {binding.id!r} declares unsupported withholding fact {selector.fact!r}"
        )
    op = str((binding.aggregation or {}).get("op", "sum"))
    if selector.fact == "perceptor_count" and op != "count_distinct":
        raise RegistryValidationError(
            f"binding {binding.id!r} fact 'perceptor_count' requires aggregation op 'count_distinct'"
        )
    if selector.fact in {"percibido_sum", "retencion_sum"} and op != "sum":
        raise RegistryValidationError(f"binding {binding.id!r} fact {selector.fact!r} requires aggregation op 'sum'")
    if selector.fact == "row_field":
        if op != "rows":
            raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
        if selector.row_field is None:
            raise RegistryValidationError(
                f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key"
            )
        if selector.grouping is None:
            raise RegistryValidationError(
                f"binding {binding.id!r} fact 'row_field' requires a 'grouping' selector key"
            )
    return selector


def withholding_binding_requirements(
    revision: ModeloRevision,
) -> tuple[WithholdingObservationRequirement, ...]:
    """Return withholding slices needed by ``revision``'s withholding bindings."""

    grouped: dict[tuple[str, ...], set[str]] = {}
    for binding in revision.bindings:
        if binding.source != "withholding":
            continue
        selector = _validated_withholding_selector(binding)
        key = tuple(sorted(selector.claves))
        grouped.setdefault(key, set()).add(binding.id)
    return tuple(
        WithholdingObservationRequirement(
            binding_ids=tuple(sorted(binding_ids)),
            claves=claves,
        )
        for claves, binding_ids in sorted(grouped.items())
    )


def _filter_withholding_observations(
    observations: Iterable[WithholdingObservation],
    selector: _WithholdingSelector,
) -> Iterable[WithholdingObservation]:
    clave_filter = set(selector.claves)
    for observation in observations:
        if clave_filter and observation.clave not in clave_filter:
            continue
        yield observation


def resolve_withholding_binding_values(
    revision: ModeloRevision,
    observations: Iterable[WithholdingObservation],
) -> dict[str, Decimal]:
    """Resolve scalar withholding-source bindings into Decimal aggregates."""

    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "withholding":
            continue
        selector = _validated_withholding_selector(binding)
        if selector.fact == "row_field":
            continue
        scope_filtered = tuple(_filter_withholding_observations(available, selector))
        if selector.fact == "perceptor_count":
            resolved[binding.id] = Decimal(len({obs.perceptor_tax_id for obs in scope_filtered}))
        elif selector.fact == "percibido_sum":
            resolved[binding.id] = sum(
                (obs.percibido_dinerario + obs.percibido_especie for obs in scope_filtered),
                Decimal("0"),
            )
        elif selector.fact == "retencion_sum":
            resolved[binding.id] = sum(
                (obs.retencion_practicada + obs.ingreso_a_cuenta for obs in scope_filtered),
                Decimal("0"),
            )
        else:  # pragma: no cover — guarded by validator
            raise RegistryValidationError(f"binding {binding.id!r} declares unsupported withholding fact")
    return resolved


def resolve_withholding_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[WithholdingObservation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer withholding bindings into per-row indexed values."""

    available = tuple(observations)
    resolved: dict[tuple[str, int], Decimal | str] = {}
    cohorts: dict[
        tuple[_WithholdingGrouping, tuple[str, ...]],
        list[tuple[DataBindingDefinition, _WithholdingSelector]],
    ] = {}
    for binding in revision.bindings:
        if binding.source != "withholding":
            continue
        selector = _validated_withholding_selector(binding)
        if selector.fact != "row_field":
            continue
        assert selector.grouping is not None
        cohort_key = (selector.grouping, tuple(sorted(selector.claves)))
        cohorts.setdefault(cohort_key, []).append((binding, selector))
    for cohort_key, members in cohorts.items():
        grouping = cohort_key[0]
        _, sample_selector = members[0]
        scope_filtered = tuple(_filter_withholding_observations(available, sample_selector))
        rows = _build_withholding_rows(grouping, scope_filtered)
        for binding, selector in members:
            assert selector.row_field is not None
            for row_index, row in enumerate(rows, start=1):
                value = row.get(selector.row_field)
                if value is None:
                    raise RegistryValidationError(
                        f"binding {binding.id!r} row_field {selector.row_field!r} not produced "
                        f"for grouping {grouping!r}"
                    )
                resolved[(binding.id, row_index)] = value
    return resolved


def _build_withholding_rows(
    grouping: _WithholdingGrouping,
    observations: tuple[WithholdingObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    """Group withholding observations into rows keyed by perceptor (and optionally clave)."""

    accum: dict[tuple[str, str, str, str], dict[str, Decimal | str]] = {}
    for observation in observations:
        if grouping == "per_perceptor":
            key = (observation.country_code, observation.perceptor_tax_id, "", "")
            row_clave = ""
            row_subclave = ""
        else:
            key = (
                observation.country_code,
                observation.perceptor_tax_id,
                observation.clave,
                observation.subclave,
            )
            row_clave = observation.clave
            row_subclave = observation.subclave
        bucket = accum.setdefault(
            key,
            {
                "country_code": observation.country_code,
                "perceptor_tax_id": observation.perceptor_tax_id,
                "perceptor_legal_name": observation.perceptor_legal_name,
                "clave": row_clave,
                "subclave": row_subclave,
                "percibido_dinerario": Decimal("0"),
                "percibido_especie": Decimal("0"),
                "retencion_practicada": Decimal("0"),
                "ingreso_a_cuenta": Decimal("0"),
            },
        )
        prev_dinerario = bucket["percibido_dinerario"]
        prev_especie = bucket["percibido_especie"]
        prev_retencion = bucket["retencion_practicada"]
        prev_ingreso = bucket["ingreso_a_cuenta"]
        assert isinstance(prev_dinerario, Decimal)
        assert isinstance(prev_especie, Decimal)
        assert isinstance(prev_retencion, Decimal)
        assert isinstance(prev_ingreso, Decimal)
        bucket["percibido_dinerario"] = prev_dinerario + observation.percibido_dinerario
        bucket["percibido_especie"] = prev_especie + observation.percibido_especie
        bucket["retencion_practicada"] = prev_retencion + observation.retencion_practicada
        bucket["ingreso_a_cuenta"] = prev_ingreso + observation.ingreso_a_cuenta
    return tuple(accum[key] for key in sorted(accum.keys()))


# ---------------------------------------------------------------------------
# Related-party operation source bindings (modelo 232).
#
# Legal authority: LIS art. 18 (operaciones vinculadas), RD 634/2015
# art. 13 (informe-país-por-país y declaración modelo 232), Orden
# HFP/816/2017 Anexo (diseno de registro modelo 232).
# ---------------------------------------------------------------------------


_RelatedPartyRowField = Literal[
    "counterparty_tax_id",
    "counterparty_legal_name",
    "country_code",
    "operation_kind_code",
    "transfer_pricing_method_code",
    "amount",
]


class RelatedPartyOperationObservation(BaseModel):
    """One related-party operation for modelo 232."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_id: str = Field(min_length=1, max_length=128)
    counterparty_tax_id: str = Field(min_length=1, max_length=64)
    counterparty_legal_name: str = Field(default="", max_length=200)
    country_code: str = Field(default="ES", min_length=2, max_length=2)
    transaction_date: date
    operation_kind_code: str = Field(min_length=1, max_length=4)
    transfer_pricing_method_code: str = Field(default="", max_length=4)
    amount: Decimal

    @field_validator("country_code")
    @classmethod
    def _country_code_uppercase(cls, value: str) -> str:
        if value != value.upper() or not value.isalpha():
            raise RegistryValidationError("country_code must be uppercase alphabetic")
        return value

    @field_validator("amount")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("related-party amount must be Decimal")
        return value


class _RelatedPartySelector(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    fact: str = Field(min_length=1, max_length=64)
    row_field: _RelatedPartyRowField | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)


def _validated_related_party_selector(binding: DataBindingDefinition) -> _RelatedPartySelector:
    try:
        selector = _RelatedPartySelector.model_validate(binding.selector)
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed related-party selector") from exc
    if selector.fact != "row_field":
        raise RegistryValidationError(
            f"binding {binding.id!r} declares unsupported related-party fact {selector.fact!r}"
        )
    op = str((binding.aggregation or {}).get("op", "rows"))
    if op != "rows":
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
    if selector.row_field is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key")
    return selector


def resolve_related_party_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[RelatedPartyOperationObservation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer related-party bindings into per-row indexed values."""

    available = tuple(observations)
    members: list[tuple[DataBindingDefinition, _RelatedPartySelector]] = []
    for binding in revision.bindings:
        if binding.source != "related_party_operation":
            continue
        selector = _validated_related_party_selector(binding)
        members.append((binding, selector))
    if not members:
        return {}
    rows = _build_related_party_rows(available)
    resolved: dict[tuple[str, int], Decimal | str] = {}
    for binding, selector in members:
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced for related-party rows"
                )
            resolved[(binding.id, row_index)] = value
    return resolved


def _build_related_party_rows(
    observations: tuple[RelatedPartyOperationObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    """Group related-party observations by (party, country, kind, method) summing amounts."""

    accum: dict[tuple[str, str, str, str], dict[str, Decimal | str]] = {}
    for obs in observations:
        key = (obs.country_code, obs.counterparty_tax_id, obs.operation_kind_code, obs.transfer_pricing_method_code)
        bucket = accum.setdefault(
            key,
            {
                "country_code": obs.country_code,
                "counterparty_tax_id": obs.counterparty_tax_id,
                "counterparty_legal_name": obs.counterparty_legal_name,
                "operation_kind_code": obs.operation_kind_code,
                "transfer_pricing_method_code": obs.transfer_pricing_method_code,
                "amount": Decimal("0"),
            },
        )
        prev = bucket["amount"]
        assert isinstance(prev, Decimal)
        bucket["amount"] = prev + obs.amount
    return tuple(accum[key] for key in sorted(accum.keys()))


# ---------------------------------------------------------------------------
# Foreign asset source bindings (modelo 720).
#
# Legal authority: RD 1065/2007 arts. 42 bis / 42 ter, Orden HAP/72/2013
# Anexo (modelo 720 diseno de registro). Threshold: 50,000 EUR per asset
# class (already encoded as a parameter on modelo 720).
# ---------------------------------------------------------------------------


_ForeignAssetRowField = Literal[
    "asset_class_code",
    "country_code",
    "currency_code",
    "asset_identifier",
    "valuation_amount",
    "acquisition_date",
]


class ForeignAssetObservation(BaseModel):
    """One foreign asset for modelo 720."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_id: str = Field(min_length=1, max_length=128)
    asset_class_code: str = Field(min_length=1, max_length=4)
    country_code: str = Field(min_length=2, max_length=2)
    currency_code: str = Field(default="EUR", min_length=3, max_length=3)
    asset_identifier: str = Field(default="", max_length=128)
    acquisition_date: date
    valuation_amount: Decimal

    @field_validator("country_code", "currency_code")
    @classmethod
    def _iso_code_uppercase(cls, value: str) -> str:
        if value != value.upper() or not value.isalpha():
            raise RegistryValidationError("ISO code must be uppercase alphabetic")
        return value

    @field_validator("valuation_amount")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("foreign asset valuation must be Decimal")
        if value < Decimal("0"):
            raise RegistryValidationError("foreign asset valuation must be non-negative")
        return value


class _ForeignAssetSelector(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    fact: str = Field(min_length=1, max_length=64)
    row_field: _ForeignAssetRowField | None = None
    asset_classes: tuple[str, ...] = ()
    record: str | None = Field(default=None, min_length=1, max_length=64)


def _validated_foreign_asset_selector(binding: DataBindingDefinition) -> _ForeignAssetSelector:
    try:
        selector = _ForeignAssetSelector.model_validate(binding.selector)
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed foreign-asset selector") from exc
    if selector.fact != "row_field":
        raise RegistryValidationError(
            f"binding {binding.id!r} declares unsupported foreign-asset fact {selector.fact!r}"
        )
    op = str((binding.aggregation or {}).get("op", "rows"))
    if op != "rows":
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
    if selector.row_field is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key")
    return selector


def resolve_foreign_asset_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[ForeignAssetObservation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer foreign-asset bindings into per-row indexed values."""

    available = tuple(observations)
    members: list[tuple[DataBindingDefinition, _ForeignAssetSelector]] = []
    cohort_classes: set[tuple[str, ...]] = set()
    for binding in revision.bindings:
        if binding.source != "foreign_asset":
            continue
        selector = _validated_foreign_asset_selector(binding)
        members.append((binding, selector))
        cohort_classes.add(tuple(sorted(selector.asset_classes)))
    if not members:
        return {}
    # All bindings in a cohort share the same asset_classes filter.
    sample_classes = next(iter(cohort_classes)) if cohort_classes else ()
    class_filter = set(sample_classes)
    filtered = tuple(obs for obs in available if not class_filter or obs.asset_class_code in class_filter)
    rows = _build_foreign_asset_rows(filtered)
    resolved: dict[tuple[str, int], Decimal | str] = {}
    for binding, selector in members:
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced for foreign-asset rows"
                )
            resolved[(binding.id, row_index)] = value
    return resolved


def _build_foreign_asset_rows(
    observations: tuple[ForeignAssetObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    rows: list[Mapping[str, Decimal | str]] = []
    for obs in sorted(
        observations,
        key=lambda o: (o.country_code, o.asset_class_code, o.asset_identifier, o.acquisition_date.isoformat()),
    ):
        rows.append(
            {
                "asset_class_code": obs.asset_class_code,
                "country_code": obs.country_code,
                "currency_code": obs.currency_code,
                "asset_identifier": obs.asset_identifier,
                "valuation_amount": obs.valuation_amount,
                "acquisition_date": obs.acquisition_date.isoformat(),
            }
        )
    return tuple(rows)


# ---------------------------------------------------------------------------
# Atribución member source bindings (modelo 184).
#
# Legal authority: Ley 35/2006 LIRPF arts. 87-90 (régimen de atribución de
# rentas), Orden HFP/227/2017 Anexo (modelo 184 diseno de registro).
# ---------------------------------------------------------------------------


_AtributionRowField = Literal[
    "member_tax_id",
    "member_legal_name",
    "country_code",
    "share_percentage",
    "base_imponible_assigned",
]


class AtributionMemberObservation(BaseModel):
    """One atribución member for modelo 184."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_id: str = Field(min_length=1, max_length=128)
    member_tax_id: str = Field(min_length=1, max_length=64)
    member_legal_name: str = Field(default="", max_length=200)
    country_code: str = Field(default="ES", min_length=2, max_length=2)
    transaction_date: date
    share_percentage: Decimal
    base_imponible_assigned: Decimal

    @field_validator("country_code")
    @classmethod
    def _country_code_uppercase(cls, value: str) -> str:
        if value != value.upper() or not value.isalpha():
            raise RegistryValidationError("country_code must be uppercase alphabetic")
        return value

    @field_validator("share_percentage")
    @classmethod
    def _share_within_bounds(cls, value: Decimal) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("share_percentage must be Decimal")
        if value < Decimal("0") or value > Decimal("100"):
            raise RegistryValidationError("share_percentage must be within [0, 100]")
        return value

    @field_validator("base_imponible_assigned")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("base_imponible_assigned must be Decimal")
        return value


class _AtributionSelector(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    fact: str = Field(min_length=1, max_length=64)
    row_field: _AtributionRowField | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)


def _validated_atribucion_selector(binding: DataBindingDefinition) -> _AtributionSelector:
    try:
        selector = _AtributionSelector.model_validate(binding.selector)
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed atribucion selector") from exc
    if selector.fact != "row_field":
        raise RegistryValidationError(
            f"binding {binding.id!r} declares unsupported atribucion fact {selector.fact!r}"
        )
    op = str((binding.aggregation or {}).get("op", "rows"))
    if op != "rows":
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
    if selector.row_field is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key")
    return selector


def resolve_atribucion_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[AtributionMemberObservation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer atribucion bindings into per-row indexed values."""

    available = tuple(observations)
    members: list[tuple[DataBindingDefinition, _AtributionSelector]] = []
    for binding in revision.bindings:
        if binding.source != "atribucion_member":
            continue
        selector = _validated_atribucion_selector(binding)
        members.append((binding, selector))
    if not members:
        return {}
    rows = tuple(
        {
            "member_tax_id": obs.member_tax_id,
            "member_legal_name": obs.member_legal_name,
            "country_code": obs.country_code,
            "share_percentage": obs.share_percentage,
            "base_imponible_assigned": obs.base_imponible_assigned,
        }
        for obs in sorted(available, key=lambda o: (o.country_code, o.member_tax_id))
    )
    resolved: dict[tuple[str, int], Decimal | str] = {}
    for binding, selector in members:
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced for atribucion rows"
                )
            resolved[(binding.id, row_index)] = value
    return resolved


# ---------------------------------------------------------------------------
# Refund operation source bindings (modelo 360).
#
# Legal authority: Ley 37/1992 art. 117 bis (devolucion 8a Directiva),
# Orden EHA/789/2010 Anexo (modelo 360 diseno de registro).
# ---------------------------------------------------------------------------


_RefundRowField = Literal[
    "member_state_code",
    "operation_kind_code",
    "operation_date",
    "supplier_tax_id",
    "refund_amount",
]


class RefundOperationObservation(BaseModel):
    """One foreign-MS refund operation for modelo 360."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_id: str = Field(min_length=1, max_length=128)
    member_state_code: str = Field(min_length=2, max_length=2)
    operation_kind_code: str = Field(min_length=1, max_length=4)
    operation_date: date
    supplier_tax_id: str = Field(min_length=1, max_length=64)
    refund_amount: Decimal

    @field_validator("member_state_code")
    @classmethod
    def _iso_code_uppercase(cls, value: str) -> str:
        if value != value.upper() or not value.isalpha():
            raise RegistryValidationError("member_state_code must be uppercase alphabetic")
        return value

    @field_validator("refund_amount")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("refund_amount must be Decimal")
        if value < Decimal("0"):
            raise RegistryValidationError("refund_amount must be non-negative")
        return value


class _RefundSelector(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    fact: str = Field(min_length=1, max_length=64)
    row_field: _RefundRowField | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)


def _validated_refund_selector(binding: DataBindingDefinition) -> _RefundSelector:
    try:
        selector = _RefundSelector.model_validate(binding.selector)
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed refund selector") from exc
    if selector.fact != "row_field":
        raise RegistryValidationError(
            f"binding {binding.id!r} declares unsupported refund fact {selector.fact!r}"
        )
    op = str((binding.aggregation or {}).get("op", "rows"))
    if op != "rows":
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
    if selector.row_field is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key")
    return selector


def resolve_refund_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[RefundOperationObservation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer refund-operation bindings into per-row indexed values."""

    available = tuple(observations)
    members: list[tuple[DataBindingDefinition, _RefundSelector]] = []
    for binding in revision.bindings:
        if binding.source != "refund_operation":
            continue
        selector = _validated_refund_selector(binding)
        members.append((binding, selector))
    if not members:
        return {}
    rows = tuple(
        {
            "member_state_code": obs.member_state_code,
            "operation_kind_code": obs.operation_kind_code,
            "operation_date": obs.operation_date.isoformat(),
            "supplier_tax_id": obs.supplier_tax_id,
            "refund_amount": obs.refund_amount,
        }
        for obs in sorted(available, key=lambda o: (o.member_state_code, o.operation_date.isoformat(), o.supplier_tax_id))
    )
    resolved: dict[tuple[str, int], Decimal | str] = {}
    for binding, selector in members:
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced for refund rows"
                )
            resolved[(binding.id, row_index)] = value
    return resolved
