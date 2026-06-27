"""Withholding row-set binding helpers.

Use of :class:`ModeloRevision` for compliance.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG
from ....core.aggregation import BindingAggregationOp, RetencionClave, RowSetGroupingKind
from ._binding_aggregation import binding_aggregation_op
from ._binding_selector_utils import selector_as_dict as _selector_as_dict
from ._binding_selector_utils import unique_tuple, uppercase_alpha_code
from ._errors import RegistryValidationError
from ._ids import BindingId
from ._schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "WithholdingObservation",
    "WithholdingObservationRequirement",
    "resolve_withholding_binding_row_values",
    "resolve_withholding_binding_values",
    "validate_withholding_binding_selector_shape",
    "withholding_binding_requirements",
]

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
_WITHHOLDING_FACTS = frozenset(
    {"row_field", "perceptor_count", "percepcion_count", "percibido_sum", "retencion_sum"},
)
_WithholdingFact = Literal[
    "row_field",
    "perceptor_count",
    "percepcion_count",
    "percibido_sum",
    "retencion_sum",
]


class WithholdingObservation(BaseModel):
    """Per-perceptor retencion / ingreso-a-cuenta observation for modelo 190 / 193."""

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    perceptor_tax_id: str = Field(min_length=1, max_length=64)
    perceptor_legal_name: str = Field(default="", max_length=200)
    country_code: str = Field(default="ES", min_length=2, max_length=2)
    transaction_date: date
    clave: RetencionClave
    subclave: str = Field(default="", max_length=4, pattern=r"^[0-9]*$")
    percibido_dinerario: Decimal = Decimal("0")
    percibido_especie: Decimal = Decimal("0")
    retencion_practicada: Decimal = Decimal("0")
    ingreso_a_cuenta: Decimal = Decimal("0")

    _country_code_uppercase = field_validator("country_code")(uppercase_alpha_code("country_code"))

    @field_validator("clave", mode="before")
    @classmethod
    def _coerce_clave(cls, value: object) -> object:
        """Hydrate the raw clave token to its :class:`RetencionClave` member.

        The strict model config does not coerce ``str`` -> ``StrEnum``; the parser /
        loader supplies the raw uppercase token (``"A"``), lifted here to
        ``RetencionClave.A``. An unknown token (outside A-L, lowercase, or
        multi-char) raises -- the closed-set hardening that replaces the former
        uppercase-only check.
        """
        if isinstance(value, str) and not isinstance(value, RetencionClave):
            return RetencionClave(value)
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

    model_config = STRICT_FROZEN_CONFIG

    binding_ids: tuple[BindingId, ...] = Field(min_length=1)
    claves: tuple[RetencionClave, ...] = ()

    @field_validator("claves", mode="before")
    @classmethod
    def _coerce_claves(cls, value: object) -> object:
        """Hydrate each raw clave token to its :class:`RetencionClave` member (strict config)."""
        if isinstance(value, (tuple, list)):
            return tuple(
                RetencionClave(item) if isinstance(item, str) and not isinstance(item, RetencionClave) else item
                for item in value
            )
        return value

    _values_unique = field_validator("binding_ids", "claves")(unique_tuple("withholding requirement tuple"))


class _WithholdingSelector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    # Promoted from ``str`` to a typed Literal so the snapshot-build
    # shape gate rejects unknown fact values, mirroring the runtime
    # check the handler does against _WITHHOLDING_FACTS. Audit
    # selector-drift F2.
    fact: _WithholdingFact
    claves: tuple[str, ...] = ()
    row_field: _WithholdingRowField | None = None
    grouping: _WithholdingGrouping | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)


def _withholding_selector(binding: DataBindingDefinition) -> _WithholdingSelector:
    try:
        return _WithholdingSelector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed withholding selector") from exc


def validate_withholding_binding_selector_shape(binding: DataBindingDefinition) -> list[str]:
    """Validate withholding selector shape and fact/op invariants for snapshot build."""
    try:
        _WithholdingSelector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        return [
            f"binding {binding.id!r} (source={binding.source!r}) selector violates "
            f"{_WithholdingSelector.__name__}: {exc}",
        ]
    try:
        _validated_withholding_selector(binding)
    except RegistryValidationError as exc:
        return [f"binding {binding.id!r} (source={binding.source!r}) withholding invariants violated: {exc}"]
    return []


def _validated_withholding_selector(binding: DataBindingDefinition) -> _WithholdingSelector:
    selector = _withholding_selector(binding)
    if selector.fact not in _WITHHOLDING_FACTS:
        raise RegistryValidationError(f"binding {binding.id!r} declares unsupported withholding fact {selector.fact!r}")
    op = binding_aggregation_op(binding)
    if selector.fact in {"perceptor_count", "percepcion_count"} and op != BindingAggregationOp.COUNT_DISTINCT:
        raise RegistryValidationError(
            f"binding {binding.id!r} fact {selector.fact!r} requires aggregation op 'count_distinct'",
        )
    if selector.fact in {"percibido_sum", "retencion_sum"} and op != BindingAggregationOp.SUM:
        raise RegistryValidationError(f"binding {binding.id!r} fact {selector.fact!r} requires aggregation op 'sum'")
    if selector.fact == "row_field":
        if op != BindingAggregationOp.ROWS:
            raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
        if selector.row_field is None:
            raise RegistryValidationError(
                f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key",
            )
        if selector.grouping is None:
            raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'grouping' selector key")
    return selector


def withholding_binding_requirements(
    revision: ModeloRevision,
) -> tuple[WithholdingObservationRequirement, ...]:
    """Return :class:`WithholdingObservationRequirement` slices needed by ``revision``'s withholding bindings.

    Uses :class:`ModeloRevision` for binding introspection.
    """
    grouped: dict[tuple[str, ...], set[BindingId]] = {}
    for binding in revision.bindings:
        if binding.source != RowSetGroupingKind.WITHHOLDING:
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
) -> dict[BindingId, Decimal]:
    """Resolve scalar withholding-source bindings into Decimal aggregates.

    Use of :class:`ModeloRevision` for compliance.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != RowSetGroupingKind.WITHHOLDING:
            continue
        selector = _validated_withholding_selector(binding)
        if selector.fact == "row_field":
            continue
        scope_filtered = tuple(_filter_withholding_observations(available, selector))
        if selector.fact == "perceptor_count":
            resolved[binding.id] = Decimal(len({obs.perceptor_tax_id for obs in scope_filtered}))
        elif selector.fact == "percepcion_count":
            # Modelo 190 "número total de percepciones" = the count of DISTINCT
            # (perceptor, clave, subclave) type-2 records (AEAT Diseño de Registros),
            # NOT the distinct-NIF perceptor count: one perceptor paid under two
            # claves files two percepciones. Distinct on the full clave-bearing key.
            resolved[binding.id] = Decimal(
                len({(obs.perceptor_tax_id, obs.clave, obs.subclave) for obs in scope_filtered}),
            )
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
        else:  # pragma: no cover - guarded by validator
            raise RegistryValidationError(f"binding {binding.id!r} declares unsupported withholding fact")
    return resolved


def resolve_withholding_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[WithholdingObservation],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Resolve row-producer withholding bindings into per-row indexed values.

    Use of :class:`ModeloRevision` for compliance.
    """
    available = tuple(observations)
    resolved: dict[tuple[BindingId, int], Decimal | str] = {}
    cohorts: dict[
        tuple[_WithholdingGrouping, tuple[str, ...]],
        list[tuple[DataBindingDefinition, _WithholdingSelector]],
    ] = {}
    for binding in revision.bindings:
        if binding.source != RowSetGroupingKind.WITHHOLDING:
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
                        f"for grouping {grouping!r}",
                    )
                resolved[(binding.id, row_index)] = value
    return resolved


def _build_withholding_rows(
    grouping: _WithholdingGrouping,
    observations: tuple[WithholdingObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    """Group withholding observations into rows keyed by perceptor and optionally clave."""
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
