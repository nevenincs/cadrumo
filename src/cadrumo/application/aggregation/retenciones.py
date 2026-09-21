"""Pure aggregation primitives for the retenciones modelo family.

This module groups typed :class:`RetencionObservation` rows into stable
per-perceptor rollups and totals for Modelos 111, 115, 123, 180, 190, and 193.
Observations must carry canonical source kinds from
:class:`~core.aggregation.BindingSourceKind`; bare ``invoice`` provenance
is rejected in favour of ``payable_invoice`` or ``collectible_invoice``.

The live calculation mesh uses these primitives through
:class:`~.modelo_bindings_retenciones.RetencionesAggregationSourceResolver` for the
Modelo 180/193 distinct-NIF perceptor count. Modelo 190's distinct
perceptor/clave/subclave percepciones count is intentionally handled by
:class:`~.withholding_source.WithholdingSourceResolver`, not by this rollup
family.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, InstanceOf, NonNegativeInt, field_validator, model_validator

from ...core.aggregation import (
    COUNTERPART_SOURCE_KIND_ORDER,
    COUNTERPART_SOURCE_KINDS,
    BindingSourceKind,
    RetencionScheme,
    WorkIncomeRetencionTreatment,
)
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.tax_id import TaxIdIdentityToken
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.parsing.dates import IsoDateString
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from ...domain.calculations.registry.schema_base import DateAxis
from ._grouping import assert_rollup_totals_match, filter_observations_for_modelo, group_and_collect_names


def _retenciones_source_kind(value: object) -> BindingSourceKind:
    if isinstance(value, BindingSourceKind):
        source_kind = value
    elif isinstance(value, str):
        try:
            source_kind = BindingSourceKind(value)
        except ValueError as exc:
            raise ValueError(f"retenciones source_kind {value!r} is not a BindingSourceKind") from exc
    else:
        raise ValueError("retenciones source_kind must be a BindingSourceKind or source-kind string")
    if source_kind not in COUNTERPART_SOURCE_KINDS:
        allowed = ", ".join(COUNTERPART_SOURCE_KIND_ORDER)
        raise ValueError(f"retenciones source_kind {source_kind.value!r} is unsupported; use one of {allowed}")
    return source_kind


class Modelo180StructuredAddress(BaseModel):
    """Official property-address alternative used without a cadastral reference."""

    model_config = STRICT_FROZEN_CONFIG

    province_code: str = Field(pattern=r"^\d{2}$")
    municipality_code: str = Field(pattern=r"^\d{3}$")
    municipality: str = Field(min_length=1, max_length=30)
    locality: str = Field(min_length=1, max_length=30)
    postal_code: str = Field(pattern=r"^\d{5}$")
    street_type: str = Field(min_length=1, max_length=5)
    street_name: str = Field(min_length=1, max_length=50)
    number_type: str = Field(min_length=1, max_length=3)
    house_number: str = Field(min_length=1, max_length=5)
    number_qualifier: str = Field(default="", max_length=3)
    block: str = Field(default="", max_length=3)
    portal: str = Field(default="", max_length=3)
    staircase: str = Field(default="", max_length=3)
    floor: str = Field(default="", max_length=3)
    door: str = Field(default="", max_length=3)
    complement: str = Field(default="", max_length=40)


class Modelo180PropertyEvidence(BaseModel):
    """One allocation's explicit property and annual-recipient evidence."""

    model_config = STRICT_FROZEN_CONFIG

    property_key: str = Field(min_length=1, max_length=128)
    situation: Literal["1", "2", "3", "4"]
    cadastral_reference: str | None = Field(default=None, min_length=1, max_length=20)
    address: Modelo180StructuredAddress | None = None
    recipient_province_code: str = Field(pattern=r"^\d{2}$")
    modality: Literal["1", "2"]
    accrual_year: int = Field(ge=1900, le=9999)
    representative_nif: TaxIdIdentityToken | None = Field(default=None, min_length=1, max_length=16)

    @model_validator(mode="after")
    def _conditional_property_identity(self) -> Modelo180PropertyEvidence:
        if self.situation in {"1", "2", "3"}:
            if self.cadastral_reference is None:
                raise ValueError("situations 1-3 require a cadastral reference")
        elif self.cadastral_reference is not None or self.address is None:
            raise ValueError("situation 4 requires no cadastral reference and a structured address")
        return self

    @property
    def identity(self) -> str:
        """Return the accepted property identity, without recipient/grouping axes."""
        if self.cadastral_reference is not None:
            return f"{self.situation}:cadastral:{self.cadastral_reference.upper()}"
        return f"4:local:{self.property_key}"


class RetencionObservation(BaseModel):
    """One typed observation feeding a retenciones aggregator.

    The source ledger transaction (``source_object_id``) is referenced
    by its canonical source kind ``ledger_transaction``. Bare
    ``invoice`` source bindings are forbidden at the registry domain
    layer; observations originating from invoice records carry one of
    ``payable_invoice`` / ``collectible_invoice`` instead.

    ``perceptor_nif`` is normalised to its canonical identity token on
    construction, so the identity this aggregator groups by is the identity
    the encrypted per-perceptor store keys by. Holding the raw declaration
    here split the two: the repository trimmed and uppercased the NIF before
    hashing it into the object key, so two canonically-equal declarations
    produced two rollups and two perceptors in the count while sharing one
    stored row -- the later write overwriting the earlier evidence for a
    perceptor the declaration still counts twice.

    ``accrued_on`` is admitted by the canonical date authority. A ten-character
    length bound is not a date check: ``2026-99-99`` and ``2026-02-30`` both
    satisfy it, and the aggregators then summed and counted a row whose accrual
    date does not exist, with the encrypted store persisting it as declared
    evidence.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_kind: BindingSourceKind
    source_object_id: str = Field(min_length=1)
    perceptor_nif: TaxIdIdentityToken = Field(min_length=1, max_length=16)
    perceptor_name: str = Field(default="", max_length=200)
    scheme: RetencionScheme
    taxable_base: Decimal = Field(ge=Decimal("0"))
    retencion_amount: Decimal = Field(ge=Decimal("0"))
    accrued_on: IsoDateString = Field(min_length=10, max_length=10)
    modelo_180_property: Modelo180PropertyEvidence | None = None

    @field_validator("source_kind", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _source_kind_is_canonical(cls, value: object) -> BindingSourceKind:
        return _retenciones_source_kind(value)


class RetencionPerceptorRollup(BaseModel):
    """One row in the aggregation: a perceptor's totals across schemes."""

    model_config = STRICT_FROZEN_CONFIG

    source_kind: BindingSourceKind
    perceptor_nif: TaxIdIdentityToken = Field(min_length=1, max_length=16)
    perceptor_name: str = Field(default="", max_length=200)
    scheme: RetencionScheme
    observations_count: NonNegativeInt
    total_taxable_base: Decimal = Field(ge=Decimal("0"))
    total_retencion: Decimal = Field(ge=Decimal("0"))

    @field_validator("source_kind", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _source_kind_is_canonical(cls, value: object) -> BindingSourceKind:
        return _retenciones_source_kind(value)


class Modelo180Type2Row(BaseModel):
    """Canonical emitted-row identity and amounts for one Modelo 180 type-2 record."""

    model_config = STRICT_FROZEN_CONFIG

    filing_year: int
    perceptor_nif: TaxIdIdentityToken
    perceptor_name: str
    property_detail: Modelo180PropertyEvidence
    observations_count: NonNegativeInt
    taxable_base: Decimal
    retencion_amount: Decimal = Field(ge=Decimal("0"))

    @property
    def sign(self) -> Literal["positive", "reimbursement"]:
        """Return the sign axis required for reimbursement separation."""
        return "reimbursement" if self.taxable_base < 0 else "positive"


class RetencionesAggregation(BaseModel):
    """Aggregate output for a retenciones modelo + period.

    The output is content-addressable: identical input observations
    in any order produce the same rollup tuple (sorted by perceptor +
    scheme) and the same totals.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1)
    period: InstanceOf[Period]
    rollups: tuple[RetencionPerceptorRollup, ...] = Field(default_factory=tuple)
    total_perceptors: NonNegativeInt
    total_taxable_base: Decimal = Field(ge=Decimal("0"))
    total_retencion: Decimal = Field(ge=Decimal("0"))
    type2_rows: tuple[Modelo180Type2Row, ...] = ()
    type2_record_count: NonNegativeInt = 0

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _totals_match_rollups(self) -> RetencionesAggregation:
        assert_rollup_totals_match(
            self.rollups,
            checks=(
                ("total_taxable_base", self.total_taxable_base, lambda row: row.total_taxable_base),
                ("total_retencion", self.total_retencion, lambda row: row.total_retencion),
            ),
        )
        unique_perceptors = {row.perceptor_nif for row in self.rollups}
        if len(unique_perceptors) != self.total_perceptors:
            raise ValueError(
                f"total_perceptors {self.total_perceptors} does not match "
                f"distinct perceptor NIFs {len(unique_perceptors)}",
            )
        if self.type2_record_count != len(self.type2_rows):
            raise ValueError("type2_record_count must equal the canonical emitted row count")
        if self.modelo != "180" and self.type2_rows:
            raise ValueError("Modelo 180 type-2 rows cannot belong to another modelo")
        if self.modelo == "180" and self.type2_rows:
            if sum((row.taxable_base for row in self.type2_rows), Decimal("0")) != self.total_taxable_base:
                raise ValueError("Modelo 180 type-2 bases must reconcile with the declaration total")
            if sum((row.retencion_amount for row in self.type2_rows), Decimal("0")) != self.total_retencion:
                raise ValueError("Modelo 180 type-2 withholdings must reconcile with the declaration total")
        return self


@dataclass(frozen=True, slots=True)
class _RetencionesRegistryCatalogue:
    """Generic projection of the selected withholding scheme declarations."""

    model_schemes: Mapping[str, frozenset[RetencionScheme]]


def _resolved_withholding_scheme_fact(
    effective_date: date,
    *,
    authority: GovernedFactSource | None = None,
) -> ResolvedMappingFact:
    """Resolve the dated withholding-scheme mapping without a Python fallback.

    An explicit authority wins; otherwise the generation-pinned scope of the
    enclosing operation is used, exactly as the retención rate facts resolve.
    With neither there is no authority to answer and the resolution refuses.
    """
    authority = authority or governed_facts_in_scope()
    if authority is None:
        raise ValueError("withholding-scheme resolution requires a generation-pinned governed-fact source")
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="m111-m115-m123-withholding-scheme-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("withholding scheme declarations must resolve as a mapping fact")
    return resolved


def registry_work_income_retencion_treatments(
    effective_date: date,
    *,
    authority: GovernedFactSource | None = None,
) -> Mapping[RetencionScheme, WorkIncomeRetencionTreatment]:
    """Resolve work-income treatment declarations from the dated fact mapping."""
    resolved = _resolved_withholding_scheme_fact(effective_date, authority=authority)
    scheme_tokens: set[RetencionScheme] = set()
    treatment_values: list[str] = []
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise TypeError("withholding scheme mapping entries must be string-to-string")
        if entry.key.endswith(".schemes"):
            scheme_tokens.update(RetencionScheme(token.strip()) for token in entry.value.split(",") if token.strip())
        elif entry.key == "retencion.work_income.treatment":
            treatment_values.append(entry.value)
    if len(treatment_values) != 1:
        raise ValueError("withholding scheme catalogue must declare exactly one work-income treatment mapping")
    treatments: dict[RetencionScheme, WorkIncomeRetencionTreatment] = {}
    for declaration in (token.strip() for token in treatment_values[0].split(",") if token.strip()):
        scheme_token, separator, fixed_flag = declaration.partition("=")
        scheme_token = scheme_token.strip()
        fixed_flag = fixed_flag.strip()
        if not separator or not scheme_token or fixed_flag not in {"true", "false"}:
            raise ValueError(f"malformed work-income treatment declaration {declaration!r}")
        scheme = RetencionScheme(scheme_token)
        if scheme not in scheme_tokens:
            raise ValueError(f"work-income treatment names undeclared scheme {scheme.value!r}")
        if scheme in treatments:
            raise ValueError(f"duplicate work-income treatment declaration for {scheme.value!r}")
        treatments[scheme] = WorkIncomeRetencionTreatment(
            scheme=scheme,
            is_fixed_rate=fixed_flag == "true",
        )
    if not treatments:
        raise ValueError("work-income treatment mapping is empty")
    if not any(treatment.is_fixed_rate for treatment in treatments.values()) or not any(
        not treatment.is_fixed_rate for treatment in treatments.values()
    ):
        raise ValueError("work-income treatment mapping must include fixed and non-fixed declarations")
    return treatments


# Selected withholding schemes come from the pinned revision and dated mapping fact.
def _registry_retenciones_catalogue(
    period: Period,
    *,
    modelo: str,
    operation: PinnedAuthorityOperation,
) -> _RetencionesRegistryCatalogue:
    """Resolve the selected modelo's scheme catalogue without a Python fallback."""
    operation.revision_for_context(
        modelo,
        filing_year=period.filing_year,
        period=period.registry_token,
        on=period.end_date,
    )
    resolved = _resolved_withholding_scheme_fact(period.end_date, authority=operation)
    model_schemes: dict[str, frozenset[RetencionScheme]] = {}
    prefix = "modelo."
    suffix = ".schemes"
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise TypeError("withholding scheme mapping entries must be string-to-string")
        if not entry.key.startswith(prefix) or not entry.key.endswith(suffix):
            continue
        model_id = entry.key[len(prefix) : -len(suffix)].strip()
        if not model_id or model_id in model_schemes:
            raise ValueError(f"duplicate or empty withholding scheme declaration key {entry.key!r}")
        tokens = tuple(token.strip() for token in entry.value.split(",") if token.strip())
        if not tokens:
            raise ValueError(f"withholding scheme declaration {entry.key!r} is empty")
        try:
            schemes = frozenset(RetencionScheme(token) for token in tokens)
        except ValueError as exc:
            raise ValueError(f"withholding scheme declaration {entry.key!r} contains an unknown scheme") from exc
        if len(schemes) != len(tokens):
            raise ValueError(f"withholding scheme declaration {entry.key!r} contains duplicate schemes")
        model_schemes[model_id] = schemes
    if modelo not in model_schemes:
        raise ValueError(f"withholding scheme catalogue has no declaration for modelo {modelo!r}")
    return _RetencionesRegistryCatalogue(model_schemes=model_schemes)


def _aggregate_for_modelo(
    observations: tuple[RetencionObservation, ...],
    *,
    modelo: str,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> RetencionesAggregation:
    """Shared per-modelo aggregation using the selected registry catalogue."""
    registry_catalogue = _registry_retenciones_catalogue(period, modelo=modelo, operation=operation)
    filtered = filter_observations_for_modelo(
        observations,
        modelo=modelo,
        catalogue=registry_catalogue.model_schemes,
        attribute_fn=lambda obs: obs.scheme,
        aggregator_label="retenciones aggregator",
    )
    grouped, perceptor_names = group_and_collect_names(
        filtered,
        group_key_fn=lambda obs: (obs.source_kind, obs.perceptor_nif, obs.scheme),
        identity_key_fn=lambda obs: (obs.source_kind, obs.perceptor_nif),
        name_fn=lambda obs: obs.perceptor_name,
    )
    rollups: list[RetencionPerceptorRollup] = []
    for (source_kind, nif, scheme), group in sorted(
        grouped.items(),
        key=lambda kv: (kv[0][0], kv[0][1], kv[0][2].value),
    ):
        total_base = sum((g.taxable_base for g in group), Decimal("0"))
        total_ret = sum((g.retencion_amount for g in group), Decimal("0"))
        rollups.append(
            RetencionPerceptorRollup(
                source_kind=source_kind,
                perceptor_nif=nif,
                perceptor_name=perceptor_names.get((source_kind, nif), ""),
                scheme=scheme,
                observations_count=len(group),
                total_taxable_base=total_base,
                total_retencion=total_ret,
            ),
        )
    perceptors = {row.perceptor_nif for row in rollups}
    return RetencionesAggregation(
        modelo=modelo,
        period=period,
        rollups=tuple(rollups),
        total_perceptors=len(perceptors),
        total_taxable_base=sum((row.total_taxable_base for row in rollups), Decimal("0")),
        total_retencion=sum((row.total_retencion for row in rollups), Decimal("0")),
    )


def aggregate_retenciones_111(
    observations: tuple[RetencionObservation, ...],
    *,
    period: Period,
    operation: PinnedAuthorityOperation | None = None,
) -> RetencionesAggregation:
    """Aggregate per (perceptor_nif, scheme) into a Modelo 111 payload.

    Pure function: identical observation input + period yields identical
    output. Rollups are sorted by (perceptor_nif, scheme.value) so two
    equal aggregations serialise to identical bytes.

    Returns a :class:`RetencionesAggregation`.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_retenciones_111(observations, period=period, operation=indexed_operation)
    return _aggregate_for_modelo(observations, modelo=Modelo("111").value, period=period, operation=operation)


def aggregate_retenciones_115(
    observations: tuple[RetencionObservation, ...],
    *,
    period: Period,
    operation: PinnedAuthorityOperation | None = None,
) -> RetencionesAggregation:
    """Aggregate Modelo 115 (retenciones sobre arrendamiento urbano).

    Only the schemes declared for this modelo by the registry are in scope.

    Returns a :class:`RetencionesAggregation` with per-perceptor rollups
    and grand totals for Modelo 115.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_retenciones_115(observations, period=period, operation=indexed_operation)
    return _aggregate_for_modelo(observations, modelo=Modelo("115").value, period=period, operation=operation)


def aggregate_retenciones_123(
    observations: tuple[RetencionObservation, ...],
    *,
    period: Period,
    operation: PinnedAuthorityOperation | None = None,
) -> RetencionesAggregation:
    """Aggregate Modelo 123 retenciones into a :class:`RetencionesAggregation`.

    Covers the capital-income schemes selected by the registry.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_retenciones_123(observations, period=period, operation=indexed_operation)
    return _aggregate_for_modelo(observations, modelo=Modelo("123").value, period=period, operation=operation)


def aggregate_retenciones_180(
    observations: tuple[RetencionObservation, ...],
    *,
    period: Period,
    operation: PinnedAuthorityOperation | None = None,
) -> RetencionesAggregation:
    """Aggregate Modelo 180 (resumen anual de retenciones sobre arrendamiento urbano).

    Shares the selected scheme catalogue with the corresponding quarterly
    model; the difference is the period scope (full year vs quarter) which the
    caller supplies. Callers should pass an annual period string
    (e.g. ``"2025"``) and feed in the union of the year's 115
    observations.

    Returns a :class:`RetencionesAggregation`.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_retenciones_180(observations, period=period, operation=indexed_operation)
    aggregation = _aggregate_for_modelo(
        observations,
        modelo=Modelo("180").value,
        period=period,
        operation=operation,
    )
    filtered = filter_observations_for_modelo(
        observations,
        modelo=Modelo("180").value,
        catalogue=_registry_retenciones_catalogue(
            period,
            modelo=Modelo("180").value,
            operation=operation,
        ).model_schemes,
        attribute_fn=lambda obs: obs.scheme,
        aggregator_label="Modelo 180 annual materializer",
    )
    if any(row.modelo_180_property is None for row in filtered):
        raise ValueError("Modelo 180 annual detail is incomplete")
    grouped: dict[tuple[object, ...], list[RetencionObservation]] = {}
    for row in filtered:
        detail = row.modelo_180_property
        if detail is None:
            raise AssertionError("complete Modelo 180 detail must be present")
        sign = "reimbursement" if row.taxable_base < 0 else "positive"
        key = (
            period.filing_year,
            row.perceptor_nif,
            detail.modality,
            detail.accrual_year,
            detail.identity,
            sign,
        )
        grouped.setdefault(key, []).append(row)
    type2_rows: list[Modelo180Type2Row] = []
    for _key, members in sorted(grouped.items(), key=lambda item: tuple(str(value) for value in item[0])):
        detail = members[0].modelo_180_property
        if detail is None:
            raise AssertionError("complete Modelo 180 detail must be present")
        if any(member.modelo_180_property != detail for member in members[1:]):
            raise ValueError("Modelo 180 property detail conflicts within one emitted row")
        names = {member.perceptor_name for member in members if member.perceptor_name}
        if len(names) > 1:
            raise ValueError("Modelo 180 recipient detail conflicts within one emitted row")
        type2_rows.append(
            Modelo180Type2Row(
                filing_year=period.filing_year,
                perceptor_nif=members[0].perceptor_nif,
                perceptor_name=next(iter(names), ""),
                property_detail=detail,
                observations_count=len(members),
                taxable_base=sum((member.taxable_base for member in members), Decimal("0")),
                retencion_amount=sum((member.retencion_amount for member in members), Decimal("0")),
            )
        )
    return RetencionesAggregation(
        modelo=aggregation.modelo,
        period=aggregation.period,
        rollups=aggregation.rollups,
        total_perceptors=aggregation.total_perceptors,
        total_taxable_base=aggregation.total_taxable_base,
        total_retencion=aggregation.total_retencion,
        type2_rows=tuple(type2_rows),
        type2_record_count=len(type2_rows),
    )


def aggregate_retenciones_190(
    observations: tuple[RetencionObservation, ...],
    *,
    period: Period,
    operation: PinnedAuthorityOperation | None = None,
) -> RetencionesAggregation:
    """Aggregate Modelo 190 (resumen anual de retenciones IRPF de Modelo 111).

    Shares the selected quarterly scheme catalogue widened over the annual period.

    Returns a :class:`RetencionesAggregation` with per-perceptor rollups
    and grand totals for the annual summary.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_retenciones_190(observations, period=period, operation=indexed_operation)
    return _aggregate_for_modelo(observations, modelo=Modelo("190").value, period=period, operation=operation)


def aggregate_retenciones_193(
    observations: tuple[RetencionObservation, ...],
    *,
    period: Period,
    operation: PinnedAuthorityOperation | None = None,
) -> RetencionesAggregation:
    """Aggregate Modelo 193 retenciones into a :class:`RetencionesAggregation`.

    Resumen anual de retenciones sobre capital mobiliario.
    Shares the 123 scheme catalogue.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_retenciones_193(observations, period=period, operation=indexed_operation)
    return _aggregate_for_modelo(observations, modelo=Modelo("193").value, period=period, operation=operation)


__all__ = [
    "Modelo180PropertyEvidence",
    "Modelo180StructuredAddress",
    "Modelo180Type2Row",
    "RetencionObservation",
    "RetencionPerceptorRollup",
    "RetencionesAggregation",
    "aggregate_retenciones_111",
    "aggregate_retenciones_115",
    "aggregate_retenciones_123",
    "aggregate_retenciones_180",
    "aggregate_retenciones_190",
    "aggregate_retenciones_193",
]
