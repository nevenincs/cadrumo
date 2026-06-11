"""Conjunta vs. individual taxation comparison for Modelo 100 (IRPF).

Runs the registry engine twice — once with ``declaration_type=2``
(tributación conjunta, Art. 82-84 LIRPF) and once with
``declaration_type=1`` (tributación individual) — over identical
casilla inputs and profile bindings, then surfaces the cuota
differential so married couples can pick the lower-tax regime.

This is a **pure, ephemeral** operation: no work unit is required
and no revision is persisted. The caller supplies all inputs
explicitly via a :class:`RegistrySnapshot`; the registry formula engine
evaluates both paths and returns a typed :class:`TaxationComparisonResult`.

:func:`compare_taxation_for_work_unit` is the high-level entry point
for CLI use: it resolves the registry snapshot and profile bindings
from an existing work unit and delegates to :func:`compare_taxation_modes`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ...core import Modelo
from ...core import Period as _Period
from ...core.errors import CoreError
from ...domain.calculations.registry import (
    RegistrySnapshot,
    calculate_registry_snapshot,
)

# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

_DECLARATION_TYPE_BINDING_SUFFIX = "profile-declaration-type"
_CUOTA_RESULTANTE_ROLE = "irpf_cuota_resultante_autoliquidacion"  # casilla 0595
_RESULTADO_ROLE = "irpf_cuota_diferencial"  # casilla 0610


class TaxationRecommendation(StrEnum):
    """Recommended filing mode based on the computed cuota differential."""

    CONJUNTA = "conjunta"
    INDIVIDUAL = "individual"
    INDIFFERENT = "indifferent"


class TaxationComparisonResult(BaseModel):
    """Typed result of a conjunta-vs-individual comparison run.

    All cuota amounts are in euros (``Decimal`` rounded to 2dp by
    the registry formula engine).  Positive values are amounts
    to pay (a ingresar); negative values are amounts to refund
    (a devolver).
    """

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    filing_year: int
    modelo: str = Modelo.M100.value
    revision: str

    # Cuota resultante autoliquidación (casilla 0595) for each path.
    conjunta_cuota_resultante: Decimal
    individual_cuota_resultante: Decimal

    # Cuota diferencial / resultado (casilla 0610) for each path.
    conjunta_resultado: Decimal
    individual_resultado: Decimal

    # individual - conjunta: positive -> conjunta is cheaper.
    delta_resultado: Decimal

    recommendation: TaxationRecommendation
    recommendation_reason: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _casilla_by_semantic_role(snapshot: RegistrySnapshot, role: str) -> str | None:
    """Return the casilla id with ``semantic_role == role``, or ``None``."""
    for casilla in snapshot.revision.casillas:
        if casilla.semantic_role == role:
            return casilla.id
    return None


def _declaration_type_binding_id(snapshot: RegistrySnapshot) -> str | None:
    """Return the binding id for ``profile-declaration-type`` in this revision."""
    suffix = _DECLARATION_TYPE_BINDING_SUFFIX
    for binding in snapshot.revision.bindings:
        if binding.id.endswith(suffix):
            return binding.id
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compare_taxation_modes(
    snapshot: RegistrySnapshot,
    *,
    inputs: Mapping[str, Decimal],
    binding_values: Mapping[str, Decimal],
    enum_binding_values: Mapping[str, str],
    relation_values: Mapping[str, Decimal] | None = None,
    date_binding_values: Mapping[str, date] | None = None,
    date_context: Mapping[str, date] | None = None,
) -> TaxationComparisonResult:
    """Run the registry engine for conjunta and individual, then diff the results.

    Returns a :class:`TaxationComparisonResult`.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose revision is executed for both
            conjunta and individual taxation modes.
        inputs: Casilla input values shared across both runs.
        binding_values: Pre-resolved Decimal binding values; must include all
            profile-sourced bindings except ``declaration_type``.
        enum_binding_values: Pre-resolved string enum binding values.
        relation_values: Optional cross-revision aggregation values.
        date_binding_values: Optional date-typed binding values.
        date_context: Optional date context for temporal casilla resolution.

    The caller must supply all profile-sourced bindings (CCAA, birth
    date, etc.) that the revision needs, *except* ``declaration_type``:
    this function injects ``declaration_type=2`` for the conjunta run
    and ``declaration_type=1`` for the individual run automatically.

    Raises :class:`TaxationComparisonError` when the revision does not
    declare a ``declaration_type`` binding or lacks the cuota casillas
    required to build the differential.
    """
    decl_binding = _declaration_type_binding_id(snapshot)
    if decl_binding is None:
        raise TaxationComparisonError(
            f"revision {snapshot.revision.id!r} of modelo "
            f"{snapshot.modelo.id!r} does not declare a "
            f"'{_DECLARATION_TYPE_BINDING_SUFFIX}' binding; "
            "conjunta-vs-individual comparison is not available for this modelo",
        )

    cuota_casilla = _casilla_by_semantic_role(snapshot, _CUOTA_RESULTANTE_ROLE)
    resultado_casilla = _casilla_by_semantic_role(snapshot, _RESULTADO_ROLE)
    if cuota_casilla is None or resultado_casilla is None:
        raise TaxationComparisonError(
            f"revision {snapshot.revision.id!r} is missing expected "
            f"casilla roles '{_CUOTA_RESULTANTE_ROLE}' or "
            f"'{_RESULTADO_ROLE}'; cannot build cuota differential",
        )

    resolved_relations = dict(relation_values or {})
    resolved_dates = dict(date_binding_values or {})
    resolved_date_ctx: dict[str, date] = dict(date_context or {})

    def _run(declaration_type: Literal[1, 2]) -> Mapping[str, Decimal]:
        merged_bindings = {**binding_values, decl_binding: Decimal(declaration_type)}
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context=resolved_date_ctx,
            binding_values=merged_bindings,
            enum_binding_values=enum_binding_values,
            relation_values=resolved_relations,
            date_binding_values=resolved_dates or None,
        )
        return result.values

    conjunta_values = _run(2)
    individual_values = _run(1)

    conjunta_cuota = conjunta_values.get(cuota_casilla, Decimal("0"))
    individual_cuota = individual_values.get(cuota_casilla, Decimal("0"))
    conjunta_resultado = conjunta_values.get(resultado_casilla, Decimal("0"))
    individual_resultado = individual_values.get(resultado_casilla, Decimal("0"))

    # delta > 0 → conjunta is cheaper (individual is more expensive)
    delta = individual_resultado - conjunta_resultado

    threshold = Decimal("1")  # differences below €1 are treated as indifferent
    if delta > threshold:
        recommendation = TaxationRecommendation.CONJUNTA
        reason = (
            f"conjunta saves {delta:.2f} € (resultado conjunta {conjunta_resultado:.2f} € "
            f"vs individual {individual_resultado:.2f} €)"
        )
    elif delta < -threshold:
        recommendation = TaxationRecommendation.INDIVIDUAL
        reason = (
            f"individual saves {-delta:.2f} € (resultado individual {individual_resultado:.2f} € "
            f"vs conjunta {conjunta_resultado:.2f} €)"
        )
    else:
        recommendation = TaxationRecommendation.INDIFFERENT
        reason = f"difference is {delta:.2f} € (below the €1 materiality threshold); either filing mode is acceptable"

    return TaxationComparisonResult(
        filing_year=snapshot.filing_year,
        modelo=snapshot.modelo.id,
        revision=snapshot.revision.id,
        conjunta_cuota_resultante=conjunta_cuota,
        individual_cuota_resultante=individual_cuota,
        conjunta_resultado=conjunta_resultado,
        individual_resultado=individual_resultado,
        delta_resultado=delta,
        recommendation=recommendation,
        recommendation_reason=reason,
    )


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------


class TaxationComparisonError(CoreError):
    """Raised when a conjunta-vs-individual comparison cannot be performed."""


# ---------------------------------------------------------------------------
# Work-unit entry point (CLI convenience)
# ---------------------------------------------------------------------------


def compare_taxation_for_work_unit(work_unit_id: str) -> TaxationComparisonResult:
    """Run conjunta-vs-individual comparison for an existing Modelo 100 work unit.

    Resolves the registry snapshot and all profile-sourced bindings
    from the stored work unit, then delegates to
    :func:`compare_taxation_modes`. The ``declaration_type`` binding is
    injected by the comparison engine; the stored profile value is
    intentionally ignored so both paths are always evaluated.

    Returns a :class:`TaxationComparisonResult` with the conjunta and
    individual calculation outcomes.

    Raises :class:`TaxationComparisonError` when the work unit's modelo
    does not support the comparison (e.g. not Modelo 100).
    Raises :class:`~aeat.application.modelo._action_errors.WorkUnitNotFoundError`
    when ``work_unit_id`` does not exist in the active bucket.
    """
    from ...domain.calculations.registry import RegistrySnapshotError
    from ...domain.modelos._repository import WorkUnitCatalogueRepository
    from ..aggregation import CalculationSourceContext, ProfileSourceResolver
    from ._action_errors import WorkUnitNotFoundError
    from ._binding_resolution import (
        _resolve_declaration_period_inputs,
        resolve_bound_casilla_inputs_for_available_bindings,
    )
    from ._registry_resources import authority_via_resources as _authority_via_resources

    wu_repo = WorkUnitCatalogueRepository()
    work_units = wu_repo.load()
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(f"work unit {work_unit_id!r} not found; check 'aeat app modelo work list'")

    try:
        authority = _authority_via_resources()
        snapshot = authority.snapshot(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except (FileNotFoundError, RegistrySnapshotError) as exc:
        raise TaxationComparisonError(
            f"registry snapshot unavailable for trabajo unit {work_unit_id!r}: {exc}",
        ) from exc

    # Resolve profile bindings — exclude declaration_type so the comparison
    # engine can inject 1 or 2 independently for each run.
    decl_binding = _declaration_type_binding_id(snapshot)
    resolution = ProfileSourceResolver(
        caller_binding_ids=({decl_binding} if decl_binding else set()),
        registry_snapshot=snapshot,
    ).resolve(
        CalculationSourceContext(
            bucket_id=work_unit.bucket_id,
            modelo=snapshot.modelo.id,
            filing_year=snapshot.filing_year,
            period=_Period.from_year_and_code(snapshot.filing_year, snapshot.period),
            revision=snapshot.revision,
        ),
    )

    from ...domain.period import period_end_date

    period_date = period_end_date(
        filing_year=work_unit.filing_year,
        registry_period=work_unit.period.registry_token,
    )

    # Build resolved inputs the same way calculate_modelo_revision does,
    # using zero casilla overrides (the work unit has no explicit inputs here —
    # the comparison uses pure profile bindings).
    declaration_inputs = _resolve_declaration_period_inputs(
        snapshot.revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    bound_inputs = resolve_bound_casilla_inputs_for_available_bindings(
        snapshot.revision,
        resolution.binding_values,
    )
    resolved_inputs = dict(sorted({**declaration_inputs, **bound_inputs}.items()))

    return compare_taxation_modes(
        snapshot,
        inputs=resolved_inputs,
        binding_values=resolution.binding_values,
        enum_binding_values=resolution.enum_binding_values,
        relation_values={},
        date_binding_values=resolution.date_binding_values or None,
        date_context={"filing_period": period_date},
    )


def compare_taxation_for_work_address(address: object) -> TaxationComparisonResult:
    """Run conjunta-vs-individual comparison for a natural or exact work address.

    Returns a :class:`TaxationComparisonResult`.
    """
    from ._work_addressing import ModeloWorkAddress, resolve_modelo_work_address_unit

    if not isinstance(address, ModeloWorkAddress):
        raise TypeError(f"expected ModeloWorkAddress, got {type(address).__name__}")
    work_unit = resolve_modelo_work_address_unit(address)
    return compare_taxation_for_work_unit(work_unit.work_unit_id)
