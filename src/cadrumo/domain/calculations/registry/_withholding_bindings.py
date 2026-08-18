"""Withholding row-set binding helpers.

Withholding-source bindings declared on a :class:`ModeloRevision` are resolved
from per-perceptor withholding observations into scalar values or row outputs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from ....core import STRICT_FROZEN_CONFIG
from ....core.aggregation import BindingAggregationOp, BindingSourceKind, RetencionClave
from ....core.identity import TaxIdIdentityToken
from ._binding_aggregation import binding_aggregation_op
from ._binding_selector_utils import (
    BindingExportDataType,
    optional_uppercase_alpha_code,
    unique_tuple,
)
from ._binding_selector_utils import (
    selector_as_dict as _selector_as_dict,
)
from ._errors import RegistryValidationError
from ._ids import BindingId
from ._schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "WithholdingClaveBreakdown",
    "WithholdingObservation",
    "WithholdingObservationRequirement",
    "WithholdingTotalsParity",
    "aggregate_withholding_by_clave",
    "compute_withholding_totals_parity",
    "resolve_withholding_binding_row_values",
    "resolve_withholding_binding_values",
    "validate_withholding_binding_selector_shape",
    "withholding_binding_requirements",
]

_WithholdingRowField = Literal[
    "perceptor_tax_id",
    "perceptor_legal_name",
    "country_code",
    "province_code",
    "territorial_deduction_clave",
    "perceptor_birth_year",
    "perceptor_situacion_familiar",
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
_CLAVE_TOKEN_SEQUENCE_ADAPTER: TypeAdapter[list[object] | tuple[object, ...]] = TypeAdapter(
    list[object] | tuple[object, ...], config=ConfigDict(strict=True)
)


class WithholdingObservation(BaseModel):
    """Per-perceptor retencion / ingreso-a-cuenta observation for modelo 190 / 193.

    ``perceptor_tax_id`` is normalised to its canonical identity token on
    construction, so the identity the clave/subclave aggregations count is the
    identity the encrypted percepciones store keys by. Holding the raw
    declaration here split the two: the repository trimmed and uppercased the
    tax ID before hashing it into the object key, so two canonically-equal
    declarations were counted as two distinct percepciones while sharing one
    stored row, and the later write overwrote the earlier evidence.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    perceptor_tax_id: TaxIdIdentityToken = Field(min_length=1, max_length=64)
    perceptor_legal_name: str = Field(default="", max_length=200)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    """The party's country, or ``None`` when the source stated none.

    Nullable rather than defaulted to ``ES``, because these forms carry the
    NON-RESIDENT population by construction -- a perceptor on a withholding
    form is routinely foreign, and an attribution member can be -- so a
    default silently declares a foreign party Spanish on a filing surface.

    Absence propagates as an ABSENT KEY in the built row rather than as a
    value, so a binding that needs the country refuses with the shipped
    not-produced error naming itself. That is the visible failure the silent
    default replaced."""
    transaction_date: date
    clave: RetencionClave
    subclave: str = Field(default="", max_length=4, pattern=r"^[0-9]*$")
    percibido_dinerario: Decimal = Decimal("0")
    percibido_especie: Decimal = Decimal("0")
    retencion_practicada: Decimal = Decimal("0")
    ingreso_a_cuenta: Decimal = Decimal("0")
    province_code: str | None = Field(default=None, pattern=r"^\d{2}$")
    """Perceptor domicilio province code (01-52, 53 La Palma), or 98 for a Spanish IRPF
    contributor resident abroad, per the Modelo 190 record design's own list.

    Nullable rather than defaulted: the design's 98 special case makes a default
    province a fabricated residence. Absence propagates as an ABSENT KEY in the
    built row, so a binding that needs the province refuses with the shipped
    not-produced error naming itself."""
    territorial_deduction_clave: int | None = Field(default=None, ge=0, le=2)
    """Modelo 190 CEUTA O MELILLA clave: 1 when the payer applied the art. 68.4
    deduction for Ceuta/Melilla rentas, 2 for the Isla de La Palma exceptional
    deduction, 0 otherwise. A retention-rate determination fact the payer's own
    data carries; never derived from the province code."""
    perceptor_birth_year: int | None = Field(default=None, ge=1900, le=2100)
    """Perceptor birth year, only declared by the design for claves A, B (subclaves
    01, 03, 04, 99) and C."""
    perceptor_situacion_familiar: int | None = Field(default=None, ge=1, le=3)
    """Perceptor family-situation clave (1-3) per the design's own relation, only
    declared for claves A, B (subclaves 01, 03, 04, 99) and C."""

    _country_code_uppercase = field_validator("country_code")(optional_uppercase_alpha_code("country_code"))

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
        try:
            tokens = _CLAVE_TOKEN_SEQUENCE_ADAPTER.validate_python(value)
        except ValidationError:
            return value
        return tuple(
            RetencionClave(item) if isinstance(item, str) and not isinstance(item, RetencionClave) else item
            for item in tokens
        )

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
    data_type: BindingExportDataType | None = None
    """Scalar type of the value this row field contributes to the export.

    The same fact ``BindingRowExportSelector.data_type`` carries; declared here
    so the selector model admits the key, since a source-family selector is
    validated whole against its own strict model. Optional while the families
    adopt it.
    """


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

    The :class:`ModeloRevision` is introspected for withholding bindings and
    grouped by the clave filters their selectors declare.
    """
    grouped: dict[tuple[RetencionClave, ...], set[BindingId]] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.WITHHOLDING:
            continue
        selector = _validated_withholding_selector(binding)
        key = tuple(sorted(RetencionClave(clave) for clave in selector.claves))
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


def distinct_percepcion_keys(
    observations: Iterable[WithholdingObservation],
) -> set[tuple[str, RetencionClave, str]]:
    """Return the distinct ``(perceptor, clave, subclave)`` percepción keys.

    Modelo 190's "número total de percepciones" counts DISTINCT type-2
    "registro de perceptor" records (AEAT Diseño de Registros), not distinct
    NIFs: one perceptor paid under two claves files two percepciones. The key is
    therefore clave-bearing.

    Shared so the bound ``percepcion_count`` fact and the per-clave breakdown
    count the same thing. Grouping by clave and keying on ``(perceptor,
    subclave)`` yields the same per-clave counts as this key does across a
    scope, which is why the breakdown can build on it.
    """
    return {(obs.perceptor_tax_id, obs.clave, obs.subclave) for obs in observations}


def percibido_total(observations: Iterable[WithholdingObservation]) -> Decimal:
    """Sum percibido dinerario plus percibido en especie.

    Shared by the bound ``percibido_sum`` fact and the per-clave breakdown so
    a change to what counts as percibido reaches both.
    """
    return sum((obs.percibido_dinerario + obs.percibido_especie for obs in observations), Decimal("0"))


def retencion_total(observations: Iterable[WithholdingObservation]) -> Decimal:
    """Sum retención practicada plus ingreso a cuenta.

    Shared by the bound ``retencion_sum`` fact and the per-clave breakdown so
    a change to what counts as retenido reaches both.
    """
    return sum((obs.retencion_practicada + obs.ingreso_a_cuenta for obs in observations), Decimal("0"))


def resolve_withholding_binding_values(
    revision: ModeloRevision,
    observations: Iterable[WithholdingObservation],
) -> dict[BindingId, Decimal]:
    """Resolve scalar withholding-source bindings into Decimal aggregates.

    The :class:`ModeloRevision` contributes scalar withholding bindings; row
    producer bindings are handled by ``resolve_withholding_binding_row_values``.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.WITHHOLDING:
            continue
        selector = _validated_withholding_selector(binding)
        if selector.fact == "row_field":
            continue
        scope_filtered = tuple(_filter_withholding_observations(available, selector))
        if selector.fact == "perceptor_count":
            resolved[binding.id] = Decimal(len({obs.perceptor_tax_id for obs in scope_filtered}))
        elif selector.fact == "percepcion_count":
            resolved[binding.id] = Decimal(len(distinct_percepcion_keys(scope_filtered)))
        elif selector.fact == "percibido_sum":
            resolved[binding.id] = percibido_total(scope_filtered)
        elif selector.fact == "retencion_sum":
            resolved[binding.id] = retencion_total(scope_filtered)
        else:  # pragma: no cover - guarded by validator
            raise RegistryValidationError(f"binding {binding.id!r} declares unsupported withholding fact")
    return resolved


def resolve_withholding_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[WithholdingObservation],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Resolve row-producer withholding bindings into per-row indexed values.

    The :class:`ModeloRevision` contributes row-field withholding bindings,
    which are grouped into deterministic per-row output slots.
    """
    available = tuple(observations)
    resolved: dict[tuple[BindingId, int], Decimal | str] = {}
    cohorts: dict[
        tuple[_WithholdingGrouping, tuple[str, ...]],
        list[tuple[DataBindingDefinition, _WithholdingSelector]],
    ] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.WITHHOLDING:
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


_DATOS_ADICIONALES_CLAVES: frozenset[str] = frozenset({"A", "C"})
_DATOS_ADICIONALES_B_SUBCLAVES: frozenset[str] = frozenset({"01", "03", "04", "99"})


def _declares_datos_adicionales(clave: RetencionClave, subclave: str) -> bool:
    """True for the claves the Modelo 190 design's 153-254 block applies to.

    The design names ``A``, ``B -subclaves 01, 03, 04 y 99-``, and ``C`` for the
    birth-year and family-situation positions specifically.
    """
    if str(clave) in _DATOS_ADICIONALES_CLAVES:
        return True
    return str(clave) == "B" and subclave in _DATOS_ADICIONALES_B_SUBCLAVES


def _require_consistent_identity_facts(
    bucket: Mapping[str, Decimal | str],
    observation: WithholdingObservation,
    *,
    fields: tuple[str, ...],
) -> None:
    """Refuse a cohort whose later observation contradicts an earlier identity fact.

    Amounts accumulate, but a perceptor has ONE province, one birth year and one
    family situation; two observations disagreeing on one of them is a finding
    the resolver must surface rather than silently keep the first value.
    """
    for field in fields:
        stored = bucket.get(field)
        incoming = getattr(observation, field)
        if stored is None or incoming is None:
            continue
        if field in ("perceptor_birth_year", "perceptor_situacion_familiar"):
            stored = str(stored)
            incoming = str(incoming)
        if stored != incoming:
            raise RegistryValidationError(
                f"withholding rows for perceptor {observation.perceptor_tax_id!r} disagree on "
                f"{field!r}: {stored!r} vs {incoming!r}",
            )


def _build_withholding_rows(
    grouping: _WithholdingGrouping,
    observations: tuple[WithholdingObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    """Group withholding observations into rows keyed by perceptor and optionally clave."""
    accum: dict[tuple[str | None, str, str, str], dict[str, Decimal | str]] = {}
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
        # An unknown country is an ABSENT KEY rather than a value. The payload
        # carries decimals and strings, and a binding reading a field this row
        # did not produce already refuses with an error naming itself -- so the
        # absence surfaces as that refusal instead of as a silent "ES".
        identity: dict[str, Decimal | str] = {
            "perceptor_tax_id": observation.perceptor_tax_id,
            "perceptor_legal_name": observation.perceptor_legal_name,
            "clave": row_clave,
            "subclave": row_subclave,
            "percibido_dinerario": Decimal("0"),
            "percibido_especie": Decimal("0"),
            "retencion_practicada": Decimal("0"),
            "ingreso_a_cuenta": Decimal("0"),
        }
        if observation.country_code is not None:
            identity["country_code"] = observation.country_code
        if observation.province_code is not None:
            identity["province_code"] = observation.province_code
        if observation.territorial_deduction_clave is not None:
            identity["territorial_deduction_clave"] = observation.territorial_deduction_clave
        if _declares_datos_adicionales(observation.clave, observation.subclave):
            # The design only asks for these facts on the listed claves; for any
            # other row the design's own no-content is the correct value, not an
            # absence.
            identity["perceptor_birth_year"] = observation.perceptor_birth_year if observation.perceptor_birth_year is not None else "0000"
            identity["perceptor_situacion_familiar"] = (
                observation.perceptor_situacion_familiar if observation.perceptor_situacion_familiar is not None else "0"
            )
        else:
            identity["perceptor_birth_year"] = "0000"
            identity["perceptor_situacion_familiar"] = "0"
        bucket = accum.setdefault(key, identity)
        _require_consistent_identity_facts(
            bucket,
            observation,
            fields=(
                "province_code",
                "territorial_deduction_clave",
                "perceptor_birth_year",
                "perceptor_situacion_familiar",
            ),
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


class WithholdingClaveBreakdown(BaseModel):
    """One per-clave row of the Modelo 190 retención reconciliation breakdown.

    Groups the per-perceptor-clave withholding detail (the AEAT Diseño de
    Registros type-2 records) by ``clave de percepción`` and carries that clave's
    distinct percepción count and percibido / retención magnitudes. The figures
    reuse the scalar withholding-fact arithmetic
    (:func:`resolve_withholding_binding_values`): ``percepcion_count`` is the
    distinct ``(perceptor, clave, subclave)`` count, ``percibido_total`` is
    ``percibido_dinerario + percibido_especie``, and ``retencion_total`` is
    ``retencion_practicada + ingreso_a_cuenta``. It is a projection of the same
    store the percepciones-count resolver reads, so the operator can reconcile
    the annual Modelo 190 totals against the individual Modelo 111 quarterly
    filings clave by clave.
    """

    model_config = STRICT_FROZEN_CONFIG

    clave: RetencionClave
    percepcion_count: int = Field(ge=0)
    percibido_total: Decimal = Field(ge=Decimal("0"))
    retencion_total: Decimal = Field(ge=Decimal("0"))


def aggregate_withholding_by_clave(
    observations: Iterable[WithholdingObservation],
) -> tuple[WithholdingClaveBreakdown, ...]:
    """Project withholding observations into :class:`WithholdingClaveBreakdown` rows.

    Pure function: identical observations in any order yield the same tuple,
    sorted by ``clave``. No new aggregation is introduced — each magnitude is
    produced by the same :func:`distinct_percepcion_keys` /
    :func:`percibido_total` / :func:`retencion_total` helper that
    :func:`resolve_withholding_binding_values` uses for the corresponding bound
    fact, so the breakdown cannot drift from the facts that feed the
    calculation. The clave is the grouping axis here and part of the key there;
    grouping first and counting the clave-bearing key within each group gives
    the same per-clave totals.

    That sentence used to be a claim rather than a guarantee: this function
    re-implemented all three formulas inline. An operator reconciles the annual
    Modelo 190 against the four quarterly Modelo 111 filings from this
    breakdown, so a formula changed in the resolver alone would have shown up
    as a reconciliation mismatch with nothing pointing at the cause.
    """
    by_clave: dict[RetencionClave, list[WithholdingObservation]] = {}
    for observation in observations:
        by_clave.setdefault(observation.clave, []).append(observation)
    return tuple(
        WithholdingClaveBreakdown(
            clave=clave,
            percepcion_count=len(distinct_percepcion_keys(group)),
            percibido_total=percibido_total(group),
            retencion_total=retencion_total(group),
        )
        for clave, group in sorted(by_clave.items())
    )


class WithholdingTotalsParity(BaseModel):
    """Totals-parity verdict between per-perceptor withholding rows and the Modelo 190 resumen-anual summary casillas.

    Modelo 190's summary casillas (``decl.percepciones-total``,
    ``decl.retenciones-total``) are computed by SUMMING the taxpayer's four
    Modelo 111 quarterly filings (``source = "relation_prefill"``,
    ``op = "sum"`` over casillas ``02/05/08/.../26`` and ``28`` respectively) —
    an entirely INDEPENDENT source from the per-perceptor-clave
    :class:`WithholdingObservation` detail (the AEAT Diseño de Registros type-2
    "registro de perceptor" rows, ``source = "withholding"``) that materialises
    the ``modelo-190-perceptor-row-*`` bindings and the distinct-percepción
    count. Nothing in the registry cross-checks that the two sources agree.

    This model is the pure comparison result of that cross-check: the sum of
    every persisted perceptor's ``percibido_dinerario + percibido_especie``
    against the resolved ``decl.percepciones-total`` value, and the sum of
    every persisted perceptor's ``retencion_practicada + ingreso_a_cuenta``
    against the resolved ``decl.retenciones-total`` value. ``is_consistent``
    is ``True`` only when both deltas are within ``tolerance`` — a divergence
    on either side surfaces as a loud, actionable finding
    (``no-silent-under-declaration``), never a silent pass.
    """

    model_config = STRICT_FROZEN_CONFIG

    percepciones_row_total: Decimal = Field(ge=Decimal("0"))
    percepciones_summary_total: Decimal = Field(ge=Decimal("0"))
    percepciones_delta: Decimal
    retenciones_row_total: Decimal = Field(ge=Decimal("0"))
    retenciones_summary_total: Decimal = Field(ge=Decimal("0"))
    retenciones_delta: Decimal
    row_count: int = Field(ge=0)
    tolerance: Decimal = Field(ge=Decimal("0"))
    is_consistent: bool


def compute_withholding_totals_parity(
    observations: Iterable[WithholdingObservation],
    *,
    percepciones_summary_total: Decimal,
    retenciones_summary_total: Decimal,
    tolerance: Decimal = Decimal("0"),
) -> WithholdingTotalsParity:
    """Cross-check summed per-perceptor withholding rows against the resolved Modelo 190 summary casillas.

    Args:
        observations: The persisted per-perceptor-clave
            :class:`WithholdingObservation` rows (the AEAT Diseño de Registros
            type-2 "registro de perceptor" detail).
        percepciones_summary_total: The resolved value of casilla
            ``decl.percepciones-total`` (the M111-relation-derived summary
            total), typically read from
            ``revision.casilla_values["decl.percepciones-total"]``.
        retenciones_summary_total: The resolved value of casilla
            ``decl.retenciones-total``, typically read from
            ``revision.casilla_values["decl.retenciones-total"]``.
        tolerance: Maximum absolute delta (EUR) that does not surface a
            divergence. THE REGISTRY IS THE AUTHORITY FOR THIS VALUE and
            publishes it per revision: resolve it with
            ``snapshot.verification_policy().tolerance`` and pass it. The
            default is exact equality rather than a cent, because Modelo 190's
            own 2025 revision publishes exact equality (``0.00``) -- a
            hardcoded cent here would silently absorb a genuine one-cent
            under-declaration on exactly the modelo this function is named
            for.

    Returns:
        A :class:`WithholdingTotalsParity` verdict. ``is_consistent`` is
        ``False`` whenever either summed total diverges from its
        corresponding summary casilla by more than ``tolerance`` — a missing
        or dropped perceptor row under-declares the row-level total below the
        summary casilla and must surface as a divergence, never silently
        collapse into ``is_consistent=True``.
    """
    rows = tuple(observations)
    percepciones_row_total = sum(
        (row.percibido_dinerario + row.percibido_especie for row in rows),
        Decimal("0"),
    )
    retenciones_row_total = sum(
        (row.retencion_practicada + row.ingreso_a_cuenta for row in rows),
        Decimal("0"),
    )
    percepciones_delta = percepciones_row_total - percepciones_summary_total
    retenciones_delta = retenciones_row_total - retenciones_summary_total
    is_consistent = abs(percepciones_delta) <= tolerance and abs(retenciones_delta) <= tolerance
    return WithholdingTotalsParity(
        percepciones_row_total=percepciones_row_total,
        percepciones_summary_total=percepciones_summary_total,
        percepciones_delta=percepciones_delta,
        retenciones_row_total=retenciones_row_total,
        retenciones_summary_total=retenciones_summary_total,
        retenciones_delta=retenciones_delta,
        row_count=len(rows),
        tolerance=tolerance,
        is_consistent=is_consistent,
    )


WithholdingSelector = _WithholdingSelector
