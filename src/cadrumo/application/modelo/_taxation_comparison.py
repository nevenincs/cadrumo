"""Conjunta vs. individual taxation comparison for Modelo 100 (IRPF).

Runs the registry engine twice -- once with ``declaration_type=2``
(tributación conjunta, Art. 82-84 LIRPF) and once with
``declaration_type=1`` (tributación individual) -- over identical
casilla inputs and profile bindings, then surfaces the cuota
differential so married couples can pick the lower-tax regime.

This is a pure, ephemeral operation: no work unit is required and no
revision is persisted. The caller supplies all inputs explicitly via a
:class:`RegistrySnapshot`; the registry
formula engine evaluates both paths and returns a typed
:class:`TaxationComparisonResult`.

Scope honesty: the individual run reuses the *single* input set assembled for
the unidad familiar and only flips ``declaration_type`` to 1, so it faithfully
models a **single-earner** household. It does not compute two separate spouse
returns; a genuine two-earner individual comparison requires a per-spouse
income axis that does not yet exist. Every result therefore carries
``individual_branch_single_earner_only`` and an
``individual_branch_caveat`` so no surface presents the individual figure as
authoritative for a two-earner couple.

The comparison is snapshot-grounded. It resolves the result casillas by their
declared semantic roles, refuses ambiguous role matches before choosing a
``CasillaId``, and requires the
revision's ``profile-declaration-type`` binding so the stored profile value can
be replaced independently for each run.

:func:`compare_taxation_for_work_unit` is the high-level entry point for CLI
use: it resolves the registry snapshot and profile bindings from an existing
work unit, deliberately excludes the stored declaration-type value, and delegates
to :func:`compare_taxation_modes`.

See Also:
    :mod:`~cadrumo.application.modelo._semantic_role_resolution`:
        Provides the canonical semantic-role-to-casilla resolver and ambiguity
        refusal used for the cuota resultante and cuota diferencial roles.
    :mod:`~cadrumo.application.modelo._binding_resolution`:
        Supplies the profile-bound values used by the work-unit entry point.
    :mod:`~cadrumo.application.modelo.work_addressing`:
        Resolves natural or exact work addresses before CLI comparison.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import CoreError
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period as _Period
from ...domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ._semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_semantic_role,
)
from .work_addressing import (
    ModeloWorkResolution,
    ModeloWorkSelectorRequest,
    select_modelo_work_resolution,
)

# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

_DECLARATION_TYPE_BINDING_SUFFIX = "profile-declaration-type"
_CUOTA_RESULTANTE_ROLE = "irpf_cuota_resultante_autoliquidacion"  # casilla 0595
_RESULTADO_ROLE = "irpf_cuota_diferencial"  # casilla 0610


def _select_taxation_work_unit(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> ModeloWorkResolution:
    """Resolve one taxation target from the caller-captured work catalogue."""
    return select_modelo_work_resolution(request, catalogue=catalogue, bucket_id=bucket_id)


#: Honesty scope caveat for the individual filing branch. The individual run
#: reuses the *single* input set assembled for the unidad familiar and merely
#: flips ``declaration_type`` to 1, so it faithfully models only a **single-earner**
#: household. It does NOT compute two separate spouse returns (each on that
#: spouse's own income); a genuine two-earner individual comparison requires a
#: per-spouse income attribution axis that does not yet exist. Surfacing this
#: statement keeps the comparator from presenting an unfaithful two-earner figure
#: as authoritative.
INDIVIDUAL_BRANCH_SINGLE_EARNER_CAVEAT = (
    "The individual-mode figure is a single-return computation over the unidad "
    "familiar's combined inputs and is faithful only for a single-earner household. "
    "It does not model two separate spouse returns (each taxed on that spouse's own "
    "income); for a genuine two-earner couple the individual comparison is not yet "
    "available, pending a per-spouse income axis. Treat the individual figure as "
    "directional, not authoritative, for two-earner households."
)


class TaxationRecommendation(StrEnum):
    """Recommended filing mode based on the computed cuota differential.

    The enum reports the lower-tax path after applying the materiality threshold,
    or ``INDIFFERENT`` when the two calculated results differ by less than one
    euro.
    """

    CONJUNTA = "conjunta"
    INDIVIDUAL = "individual"
    INDIFFERENT = "indifferent"


class TaxationComparisonResult(BaseModel):
    """Typed result of a conjunta-vs-individual comparison run.

    All cuota amounts are in euros (``Decimal`` rounded to 2dp by
    the registry formula engine).  Positive values are amounts
    to pay (a ingresar); negative values are amounts to refund
    (a devolver).

    ``*_cuota_resultante`` carries the Modelo 100 cuota resultante de la
    autoliquidación semantic role, while ``*_resultado`` carries the cuota
    diferencial/result role used to compute ``delta_resultado`` and the
    recommendation.
    """

    model_config = STRICT_FROZEN_CONFIG

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

    # Honesty scope: the individual branch reuses the unidad familiar's single
    # input set, so it is faithful only for a single-earner household.
    # ``individual_branch_single_earner_only`` is always True today; a genuine
    # two-earner individual comparison (two separate spouse returns) requires a
    # per-spouse income axis that does not yet exist. ``individual_branch_caveat``
    # carries the operator-facing disclosure so no surface presents the
    # individual figure as authoritative for a two-earner couple.
    individual_branch_single_earner_only: bool = True
    individual_branch_caveat: str = INDIVIDUAL_BRANCH_SINGLE_EARNER_CAVEAT


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _casilla_by_semantic_role(snapshot: RegistrySnapshot, role: str) -> CasillaId | None:
    """Return the unique casilla id for ``role`` or ``None`` when absent.

    Ambiguous matches are promoted to :class:`TaxationComparisonError` so the
    comparison never silently chooses among duplicated semantic roles.
    """
    try:
        return casilla_id_for_unique_semantic_role(snapshot, role)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise TaxationComparisonError(str(exc)) from exc


def _declaration_type_binding_id(snapshot: RegistrySnapshot) -> BindingId | None:
    """Return the binding id for ``profile-declaration-type`` in this revision.

    The suffix match preserves the revision-authored binding namespace while
    locating the declaration-type input that the comparison injects as ``1`` or
    ``2`` for each run.
    """
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
    inputs: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal],
    enum_binding_values: Mapping[BindingId, str],
    relation_values: Mapping[RelationId, Decimal] | None = None,
    date_binding_values: Mapping[BindingId, date] | None = None,
    date_context: Mapping[str, date] | None = None,
) -> TaxationComparisonResult:
    """Run the registry engine for conjunta and individual, then diff the results.

    The function is pure and does not read, create, or persist work units. It
    requires the caller to provide a loaded
    :class:`RegistrySnapshot`, casilla inputs,
    and already-resolved profile bindings. It then injects ``declaration_type``
    separately for the conjunta and individual runs and compares the calculated
    cuota diferencial/result casilla.

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

    Returns:
        A :class:`TaxationComparisonResult` with both run outcomes, the signed
        ``individual - conjunta`` delta, and the recommendation after the one-euro
        materiality threshold.

    The caller must supply all profile-sourced bindings (CCAA, birth date, etc.)
    that the revision needs, except ``declaration_type``: this function injects
    ``declaration_type=2`` for the conjunta run and ``declaration_type=1`` for
    the individual run automatically.

    Raises :class:`TaxationComparisonError` when the revision does not
    declare a ``declaration_type`` binding or lacks the cuota casillas
    required to build the differential. Ambiguous semantic-role casillas are also
    refused through the same error type.
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

    def _run(declaration_type: Literal[1, 2]) -> Mapping[CasillaId, Decimal]:
        merged_bindings = {**binding_values, decl_binding: Decimal(declaration_type)}
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context=resolved_date_ctx,
            binding_values=merged_bindings,
            enum_binding_values=enum_binding_values,
            relation_values=resolved_relations,
            date_binding_values=resolved_dates or None,
            # The individual/joint cuota differential is an IRPF comparison, so
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
    """Raised when a conjunta-vs-individual comparison cannot be performed.

    Covers unsupported revisions, missing declaration-type bindings, missing
    result casillas, and ambiguous semantic-role resolution.
    """


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

    Returns:
        A :class:`TaxationComparisonResult` with the conjunta and individual
        calculation outcomes.

    Raises :class:`TaxationComparisonError` when the work unit's modelo
    does not support the comparison (e.g. not Modelo 100).
    Raises :class:`~cadrumo.application.modelo._action_errors.WorkUnitNotFoundError`
    when ``work_unit_id`` does not exist in the active bucket.

    See Also:
        :func:`compare_taxation_modes`:
            Performs the pure snapshot comparison after this function resolves
            work-unit state.
    """
    from ...domain.calculations.registry.authority import bundled_authority
    from ...domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
    from ...domain.calculations.registry.errors import RegistrySnapshotError
    from ..aggregation import CalculationSourceContext, ProfileSourceResolver
    from ._action_errors import WorkUnitNotFoundError
    from ._binding_resolution import resolve_declaration_period_inputs
    from .work_addressing import ModeloWorkSelectorState, resolve_modelo_work_bucket

    request = ModeloWorkSelectorRequest(work_unit_id=work_unit_id)
    bucket_id = resolve_modelo_work_bucket(request)
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository

    catalogue = WorkUnitCatalogueRepository(bucket_id=bucket_id).load()
    resolution = _select_taxation_work_unit(
        request,
        catalogue=catalogue,
        bucket_id=bucket_id,
    )
    if resolution.state is ModeloWorkSelectorState.ABSENT or resolution.work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    work_unit = resolution.work_unit

    try:
        authority = bundled_authority()
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

    from ...domain.period import calculation_filing_date

    period_date = calculation_filing_date(work_unit.period)

    # Build resolved inputs the same way calculate_modelo_revision does,
    # using zero casilla overrides (the work unit has no explicit inputs here —
    # the comparison uses pure profile bindings).
    # ``compare_taxation_modes`` is Modelo 100 only, and no Modelo 100 revision
    # declares a ``filing_period`` semantic role, so the text channel of this
    # projection is empty here; only the Decimal ``filing_year`` role applies.
    declaration_inputs = resolve_declaration_period_inputs(
        snapshot.revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    ).casilla_inputs
    bound_inputs = resolve_available_bound_inputs_by_casilla_id(
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

    Args:
        address: The :class:`~cadrumo.application.modelo.work_addressing.ModeloWorkAddress`
            selected by CLI work-address parsing.

    Returns:
        A :class:`TaxationComparisonResult` for the resolved work unit.
    """
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from .work_addressing import (
        ModeloWorkAddress,
        ModeloWorkSelectorRequest,
        resolve_modelo_work_address_unit,
        resolve_modelo_work_bucket,
    )

    if not isinstance(address, ModeloWorkAddress):
        raise TypeError(f"expected ModeloWorkAddress, got {type(address).__name__}")
    bucket_id = address.bucket_id or resolve_modelo_work_bucket(ModeloWorkSelectorRequest())
    work_unit = resolve_modelo_work_address_unit(
        address,
        catalogue=WorkUnitCatalogueRepository(bucket_id=bucket_id).load(),
        bucket_id=bucket_id,
    )
    return compare_taxation_for_work_unit(work_unit.work_unit_id)
