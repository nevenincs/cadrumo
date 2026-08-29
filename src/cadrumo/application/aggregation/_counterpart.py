"""Modelo 347/349 counterpart aggregation for informativa declarations.

Used by :mod:`~application.aggregation._service`, the per-modelo
aggregation service. This is an operator preview surface, not the live
calculation source mesh: standalone ``CounterpartObservation`` rows are
operator-supplied, while calculation uses enrolled repository-backed sources.

Modelo 347 covers annual operations with third parties whose total exceeds the
declaration floor. Modelo 349 covers intra-EU operations by member-state
operation kind. Both aggregate per ``(source_kind, counterparty_nif,
operation_kind)`` using the counterpart subset of the canonical source-kind
taxonomy, then expose helpers such as :func:`declarable_counterparty_nifs_347`
for consumers that need the 347 threshold decision.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType

from pydantic import BaseModel, Field, InstanceOf, field_validator, model_validator

from ...core import M347_THRESHOLD_EUR, STRICT_FROZEN_CONFIG, FilingPeriodCode, Modelo, Period
from ...core.aggregation import (
    CounterpartSourceKind,
    OperationKind347,
    OperationKind349,
    counterpart_source_kind,
)
from ...core.country_code import CountryCodeAlpha2
from ...core.parsing import IsoDateString
from ._grouping import assert_rollup_totals_match, filter_observations_for_modelo, group_and_collect_names


def _validate_source_kind(value: str) -> CounterpartSourceKind:
    return counterpart_source_kind(value)


_CANONICAL_OPERATION_KINDS: frozenset[str] = frozenset(kind.value for kind in (*OperationKind347, *OperationKind349))


def _validate_operation_kind(value: str) -> str:
    """Refuse an ``operation_kind`` outside the declared 347/349 clave vocabulary.

    Bounding this field by non-blankness alone made an unrecognised token
    *silently declarable-invisible* rather than refused. The aggregator routes
    each observation to its modelo by testing ``operation_kind`` against that
    modelo's clave set (:func:`~._grouping.filter_observations_for_modelo`), so
    a token in neither set matches neither pass and is dropped from the rollup —
    while the aggregation's own totals still reconcile, because they are summed
    from the surviving rollups. A capitalisation slip on a real above-threshold
    operation therefore produced a Modelo 347 preview reporting zero
    counterparties and a zero base, with no error and no notice.

    The cross-modelo filtering itself is correct and stays: a 349 clave passed
    to the 347 pass *should* be skipped. Only a token belonging to neither
    vocabulary is a defect, and refusing it here — at the operator JSON
    boundary, where the provenance to explain the refusal still exists — is
    what separates the two cases.
    """
    if value not in _CANONICAL_OPERATION_KINDS:
        accepted = ", ".join(sorted(_CANONICAL_OPERATION_KINDS))
        raise ValueError(f"operation_kind must be a declared 347/349 clave, got {value!r}; accepted: {accepted}")
    return value


def _validate_country(value: str, *, field_name: str) -> str:
    if len(value) != 2 or any(char < "A" or char > "Z" for char in value):
        raise ValueError(f"{field_name} must be uppercase ISO-3166 alpha-2, got {value!r}")
    return value


class _CounterpartBoundaryModel(BaseModel):
    """Shared Pydantic boundary validation for counterpart records."""

    model_config = STRICT_FROZEN_CONFIG

    @field_validator("source_kind", mode="before", check_fields=False)
    @classmethod
    def _source_kind_is_canonical(cls, value: object) -> CounterpartSourceKind:
        if not isinstance(value, str):
            raise ValueError("source_kind must be a string")
        return _validate_source_kind(value)

    @field_validator("operation_kind", check_fields=False)
    @classmethod
    def _operation_kind_is_canonical(cls, value: str) -> str:
        return _validate_operation_kind(value)

    @field_validator("counterparty_country", check_fields=False)
    @classmethod
    def _country_is_uppercase(cls, value: str) -> str:
        return _validate_country(value, field_name="counterparty_country")


class CounterpartObservation(_CounterpartBoundaryModel):
    """One typed observation for a 347 or 349 aggregator pass.

    This model is the operator boundary: ``aeat app modelo aggregate`` validates
    each ``--counterpart-observation`` JSON object directly against it, so
    whatever it admits reaches the preview rollups unchecked.

    ``accrued_on`` and ``operation_period`` are therefore admitted by the same
    authorities the rest of the system uses. Bounding them by string length
    alone let an impossible calendar date (``2026-99-99`` and ``2026-02-30`` are
    both ten characters) and an arbitrary period token into a rollup the
    operator reads as a preview of a real declaration, while the adjacent
    registry counterpart binding types the same concepts as a
    :class:`~datetime.date` and a registry period code.
    """

    source_kind: CounterpartSourceKind
    source_object_id: str = Field(min_length=1)
    counterparty_nif: str = Field(min_length=1, max_length=20)
    counterparty_name: str = Field(default="", max_length=200)
    # Required, and deliberately not defaulted to Spain. This is an operator
    # boundary, so a default is an INFERENCE about a fact the operator did not
    # state -- and it was the one inference the Modelo 349 readiness rule turns
    # on. That rule asks for a GROI check when the country is Spain and a
    # NIF-IVA check when it is not, so a row omitting the country was read as
    # domestic and the NIF-IVA verification an intra-community counterparty
    # must pass was never required of it. The declaration is the recapitulativa
    # de operaciones INTRACOMUNITARIAS, where a Spanish counterparty is the one
    # thing the row cannot be.
    #
    # Refusing is right rather than admitting an absent value, because every
    # consumer here has to branch on the country: an optional field would move
    # the same guess into each of them, and the shape of the mistake would
    # survive the fix.
    counterparty_country: CountryCodeAlpha2
    operation_kind: str = Field(min_length=1)
    operation_period: FilingPeriodCode
    taxable_base: Decimal = Field(ge=Decimal("0"))
    invoice_total: Decimal = Field(ge=Decimal("0"))
    accrued_on: IsoDateString = Field(min_length=10, max_length=10)
    groi_verified: bool = False
    nif_iva_verified: bool = False


class CounterpartRollup(_CounterpartBoundaryModel):
    """One (source_kind, counterparty_nif, operation_kind) rollup row."""

    source_kind: CounterpartSourceKind
    counterparty_nif: str = Field(min_length=1, max_length=20)
    counterparty_name: str = Field(default="", max_length=200)
    counterparty_country: CountryCodeAlpha2
    operation_kind: str = Field(min_length=1)
    observations_count: int = Field(ge=0)
    total_taxable_base: Decimal = Field(ge=Decimal("0"))
    total_invoice_total: Decimal = Field(ge=Decimal("0"))
    requires_groi_check: bool = False
    requires_nif_iva_check: bool = False
    groi_ready: bool = True
    nif_iva_ready: bool = True
    declarable_readiness_satisfied: bool = True


class CounterpartAggregation(BaseModel):
    """347 / 349 counterpart aggregation output."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1)
    period: InstanceOf[Period]
    rollups: tuple[CounterpartRollup, ...] = Field(default_factory=tuple)
    total_counterparties: int = Field(ge=0)
    total_taxable_base: Decimal = Field(ge=Decimal("0"))
    total_invoice_total: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def _totals_match_rollups(self) -> CounterpartAggregation:
        assert_rollup_totals_match(
            self.rollups,
            checks=(
                ("total_taxable_base", self.total_taxable_base, lambda row: row.total_taxable_base),
                ("total_invoice_total", self.total_invoice_total, lambda row: row.total_invoice_total),
            ),
        )
        unique_counterparties = {row.counterparty_nif for row in self.rollups}
        if len(unique_counterparties) != self.total_counterparties:
            raise ValueError(
                f"total_counterparties {self.total_counterparties} != distinct NIFs {len(unique_counterparties)}",
            )
        return self


_MODELO_347_KINDS: frozenset[str] = frozenset(k.value for k in OperationKind347)
_MODELO_349_KINDS: frozenset[str] = frozenset(k.value for k in OperationKind349)
_MODELO_KIND_CATALOGUE: dict[str, frozenset[str]] = {
    Modelo.M347.value: _MODELO_347_KINDS,
    Modelo.M349.value: _MODELO_349_KINDS,
}
COUNTERPART_MODELO_KIND_CATALOGUE: Mapping[str, frozenset[str]] = MappingProxyType(_MODELO_KIND_CATALOGUE)


def _aggregate_for_modelo(
    observations: tuple[CounterpartObservation, ...],
    *,
    modelo: str,
    period: Period,
) -> CounterpartAggregation:
    filtered = filter_observations_for_modelo(
        observations,
        modelo=modelo,
        catalogue=_MODELO_KIND_CATALOGUE,
        attribute_fn=lambda obs: obs.operation_kind,
        aggregator_label="counterpart aggregator",
    )
    grouped, names = group_and_collect_names(
        filtered,
        group_key_fn=lambda obs: (obs.source_kind, obs.counterparty_nif, obs.operation_kind),
        identity_key_fn=lambda obs: (obs.source_kind, obs.counterparty_nif),
        name_fn=lambda obs: obs.counterparty_name,
    )
    rollups: list[CounterpartRollup] = []
    for (source_kind, nif, op_kind), group in sorted(grouped.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        total_base = sum((g.taxable_base for g in group), Decimal("0"))
        total_invoice = sum((g.invoice_total for g in group), Decimal("0"))
        country = _single_counterparty_country(
            observations=tuple(group),
            source_kind=source_kind,
            counterparty_nif=nif,
            operation_kind=op_kind,
        )
        readiness = _counterpart_readiness_for_modelo(modelo=modelo, country=country, observations=tuple(group))
        rollups.append(
            CounterpartRollup(
                source_kind=source_kind,
                counterparty_nif=nif,
                counterparty_name=names.get((source_kind, nif), ""),
                counterparty_country=country,
                operation_kind=op_kind,
                observations_count=len(group),
                total_taxable_base=total_base,
                total_invoice_total=total_invoice,
                **readiness,
            ),
        )
    counterparties = {row.counterparty_nif for row in rollups}
    return CounterpartAggregation(
        modelo=modelo,
        period=period,
        rollups=tuple(rollups),
        total_counterparties=len(counterparties),
        total_taxable_base=sum((row.total_taxable_base for row in rollups), Decimal("0")),
        total_invoice_total=sum((row.total_invoice_total for row in rollups), Decimal("0")),
    )


def _single_counterparty_country(
    *,
    observations: tuple[CounterpartObservation, ...],
    source_kind: str,
    counterparty_nif: str,
    operation_kind: str,
) -> str:
    countries = frozenset(observation.counterparty_country for observation in observations)
    if len(countries) != 1:
        raise ValueError(
            "conflicting counterparty_country values for counterpart aggregation cohort "
            f"source_kind={source_kind!r}, counterparty_nif={counterparty_nif!r}, "
            f"operation_kind={operation_kind!r}: {sorted(countries)!r}",
        )
    return next(iter(countries))


def aggregate_counterpart_347(
    observations: tuple[CounterpartObservation, ...],
    *,
    period: Period,
) -> CounterpartAggregation:
    """Aggregate Modelo 347 (operaciones con terceros, annual).

    Filters to 347 operation kinds. Threshold gating (the €3,005.06
    declaration floor) belongs to the modelo binding consumer; this
    aggregator returns raw per-counterparty totals.

    Returns a :class:`CounterpartAggregation`.
    """
    return _aggregate_for_modelo(observations, modelo=Modelo.M347.value, period=period)


def aggregate_counterpart_349(
    observations: tuple[CounterpartObservation, ...],
    *,
    period: Period,
) -> CounterpartAggregation:
    """Aggregate Modelo 349 (operaciones intracomunitarias).

    Filters to 349 intracomunitarias operation kinds. Rollups carry
    the additional NIF-IVA / GROI readiness gates: Spanish
    counterparties require GROI readiness and non-Spanish
    counterparties require NIF-IVA readiness.

    Returns a :class:`CounterpartAggregation` with rollups sorted by
    ``(source_kind, counterparty_nif, operation_kind)``.
    """
    return _aggregate_for_modelo(observations, modelo=Modelo.M349.value, period=period)


def _counterpart_readiness_for_modelo(
    *,
    modelo: str,
    country: str,
    observations: tuple[CounterpartObservation, ...],
) -> dict[str, bool]:
    if modelo != Modelo.M349.value:
        return {
            "requires_groi_check": False,
            "requires_nif_iva_check": False,
            "groi_ready": True,
            "nif_iva_ready": True,
            "declarable_readiness_satisfied": True,
        }
    requires_groi = country == "ES"
    requires_nif_iva = country != "ES"
    groi_ready = (not requires_groi) or all(obs.groi_verified for obs in observations)
    nif_iva_ready = (not requires_nif_iva) or all(obs.nif_iva_verified for obs in observations)
    return {
        "requires_groi_check": requires_groi,
        "requires_nif_iva_check": requires_nif_iva,
        "groi_ready": groi_ready,
        "nif_iva_ready": nif_iva_ready,
        "declarable_readiness_satisfied": groi_ready and nif_iva_ready,
    }


def declarable_counterparty_nifs_347(aggregation: CounterpartAggregation) -> frozenset[str]:
    """Return counterparties whose full Modelo 347 total exceeds the declaration floor."""
    totals: dict[str, Decimal] = {}
    for rollup in aggregation.rollups:
        totals[rollup.counterparty_nif] = totals.get(rollup.counterparty_nif, Decimal("0")) + rollup.total_invoice_total
    return frozenset(nif for nif, total in totals.items() if total > M347_THRESHOLD_EUR)


def declarable_for_347(aggregation: CounterpartAggregation, *, counterparty_nif: str) -> bool:
    """Return True iff a counterparty exceeds the 347 declaration floor across all cohorts."""
    return counterparty_nif in declarable_counterparty_nifs_347(aggregation)


__all__ = [
    "COUNTERPART_MODELO_KIND_CATALOGUE",
    "CounterpartAggregation",
    "CounterpartObservation",
    "CounterpartRollup",
    "OperationKind347",
    "OperationKind349",
    "aggregate_counterpart_347",
    "aggregate_counterpart_349",
    "declarable_counterparty_nifs_347",
    "declarable_for_347",
]
