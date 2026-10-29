"""Enforce source ownership and model-specific calculation guards."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.irnr import M210GrossIncomeSourceMode
from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.record_row_membership import ClosedRecordRowSet
from ...domain.calculations.registry.binding_provider_registration import BINDING_PROVIDER_REGISTRATIONS
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ...domain.calculations.registry.ids import (
    BindingId,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.modelos.calculation_revision_m303_handoff import (
    M303RegimenSimplificadoAnnualSummaryHandoff,
)
from ...domain.modelos.row_models import ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit
from ._m210_agrupacion_renta import validate_m210_agrupacion_renta_rows_for_calculation
from .action_errors import (
    ModeloAggregationBindingError,
)
from .calculation_route import CALCULATION_ROUTE_ENROLLED_SOURCES
from .m303_regimen_simplificado_scope import (
    m303_regimen_simplificado_annual_summary_applies_to_profile,
    taxpayer_profile_for_work,
)
from .preconditions import build_modelo_precondition_failure
from .work_profile import ModeloWorkProfile

if TYPE_CHECKING:
    pass


def require_m303_regimen_simplificado_annual_summary_handoff(
    *,
    revision: ModeloRevision,
    profile: ModeloWorkProfile,
    handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None,
) -> None:
    """Keep the 303/4T annual handoff on its one mesh-owned arrival path.

    The antecedent is declaration AND applicability, never declaration alone.
    Boxes 74--83 ride on every Modelo 390 form, so every revision declares this
    family; requiring the handoff on that basis alone routed a regimen general
    filer through a regimen simplificado source it can never have. This still
    refuses a missing or unexpected handoff wherever the regime does reach the
    taxpayer, which is the arrival-path invariant it exists to hold.

    Takes ``revision`` as a :class:`ModeloRevision`.
    """
    declares_handoff = any(
        binding.source is BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY for binding in revision.bindings
    )
    expects_handoff = declares_handoff and m303_regimen_simplificado_annual_summary_applies_to_profile(
        taxpayer_profile_for_work(profile),
    )
    if expects_handoff == (handoff is not None):
        return
    raise ModeloAggregationBindingError(
        translated_message="errors.error.error_modelo_aggregation_binding",
        context={
            "reason": "m303_regimen_simplificado_annual_summary_handoff_required",
            "revision_id": revision.id,
            "declares_handoff": declares_handoff,
            "expects_handoff": expects_handoff,
        },
    )


def require_m303_regimen_simplificado_annual_summary_arrival_values(
    *,
    casilla_values: Mapping[CasillaId, Decimal],
    handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None,
) -> None:
    """Reject a target calculation whose engine output diverges from its carrier."""
    if handoff is None:
        return
    mismatches = tuple(
        casilla_id for casilla_id, value in handoff.values.items() if casilla_values.get(casilla_id) != value
    )
    if not mismatches:
        return
    raise ModeloAggregationBindingError(
        translated_message="errors.error.error_modelo_aggregation_binding",
        context={
            "reason": "m303_regimen_simplificado_annual_summary_arrival_mismatch",
            "casilla_ids": mismatches,
        },
    )


def assert_no_novel_source_kinds(revision: ModeloRevision) -> None:
    """Raise if any binding source kind is unknown to the live mesh (the boundary gate).

    A binding whose ``source`` is not in the executable resolver union would
    silently blank on every calculation, whether it produces a scalar or rows:
    row shape earns no exemption, and a kind passes only on executable
    ownership or its registered disposition. This gate converts a genuinely
    unrouted source into a loud
    :exc:`ModeloAggregationBindingError` at calculation time so a novel TOML
    source cannot compile into a silently-zero revision.

    The accepted set is:

    * ``CALCULATION_ROUTE_ENROLLED_SOURCES`` — executable resolver and
      intrinsic production-channel ownership.

    Args:
        revision: The :class:`ModeloRevision` whose binding source kinds are
            checked against the live source-mesh enrollment.

    Raises:
        ModeloAggregationBindingError: When a binding carries a source kind
            absent from executable production ownership and not registered as
            deferred or non-runtime. Deferred kinds are not refused here; they
            surface as ``deferred_binding_source`` diagnostics at resolution.
    """
    novel = sorted(
        {
            str(binding.source)
            for binding in revision.bindings
            if str(binding.source) not in CALCULATION_ROUTE_ENROLLED_SOURCES
            and _registered_disposition(binding.source) not in ("deferred", "non_runtime")
        },
    )
    if novel:
        raise ModeloAggregationBindingError(
            translated_message="application.modelo.errors.novel_source_kind_rejected",
            context={"novel_source_kinds": novel, "revision_id": revision.id},
        )


def _registered_disposition(source: BindingSourceKind) -> str | None:
    """Return the registered disposition for ``source``, or ``None`` when unregistered."""
    registration = BINDING_PROVIDER_REGISTRATIONS.get(source)
    return None if registration is None else registration.disposition


def _source_owned_binding_ids(
    revision: ModeloRevision, owned_sources: frozenset[BindingSourceKind]
) -> frozenset[BindingId]:
    return frozenset(binding.id for binding in revision.bindings if binding.source in owned_sources)


def _bound_casilla_ids_for_bindings(
    revision: ModeloRevision, binding_ids: frozenset[BindingId]
) -> frozenset[CasillaId]:
    return frozenset(
        casilla.id
        for casilla in revision.casillas
        if casilla.input_kind == InputKind.BOUND and binding_ids.intersection(bound_casilla_binding_ids(casilla))
    )


def reject_caller_overrides_of_source_bindings(
    *,
    revision: ModeloRevision,
    owned_sources: frozenset[BindingSourceKind],
    caller_binding_values: Mapping[BindingId, Decimal],
    caller_casilla_inputs: Mapping[CasillaId, Decimal],
    caller_enum_binding_values: Mapping[BindingId, str] | None = None,
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...] = (),
) -> None:
    """Refuse caller-supplied bindings or casilla inputs that collide with values bucket source resolvers own.

    Bucket-aggregation calculation derives source-owned binding values
    (and the casillas bound to them) from bucket substrate. Letting a
    caller override those silently would break calculation grounding:
    the persisted revision would no longer reflect the sources it claims
    to aggregate. Both collisions are rejected before any value reaches
    the engine.

    Takes ``revision`` as a :class:`ModeloRevision`.
    """
    # A closed table can populate positional manual-input bindings. Its actual
    # ownership therefore cannot be inferred from the binding's provider kind.
    # Keep all rows (including occupied ones) coupled to their source evidence
    # before the caller's enum channel is overlaid during preparation.
    protected_binding_ids = _source_owned_binding_ids(revision, owned_sources) | frozenset(
        binding_id for row_set in closed_record_row_sets for binding_id in row_set.binding_ids
    )
    rejected_bindings = sorted(
        (set(caller_binding_values) | set(caller_enum_binding_values or {})).intersection(protected_binding_ids),
    )
    if rejected_bindings:
        raise ModeloAggregationBindingError(
            translated_message="errors.error.error_modelo_aggregation_binding",
            context={"rejected_binding_ids": rejected_bindings},
            precondition_failure=build_modelo_precondition_failure(
                subject_leaf_key="modelo.work.calculate",
                condition_id="modelo.work.calculate.source_inputs.unowned",
                scenario_id="modelo.work.calculate.source_inputs.binding_override_rejected",
                evidence_id="modelo.work.calculate.source_inputs",
                evidence_values={
                    "rejected_binding_count": len(rejected_bindings),
                    "rejected_binding_ids": "|".join(rejected_bindings),
                },
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            ),
        )
    protected_casilla_ids = _bound_casilla_ids_for_bindings(revision, protected_binding_ids)
    rejected_casillas = sorted(set(caller_casilla_inputs).intersection(protected_casilla_ids))
    if rejected_casillas:
        raise ModeloAggregationBindingError(
            translated_message="application.modelo.errors.caller_casilla_source_binding_conflict",
            context={"casillas": rejected_casillas},
            precondition_failure=build_modelo_precondition_failure(
                subject_leaf_key="modelo.work.calculate",
                condition_id="modelo.work.calculate.source_inputs.unowned",
                scenario_id="modelo.work.calculate.source_inputs.casilla_override_rejected",
                evidence_id="modelo.work.calculate.source_inputs",
                evidence_values={
                    "rejected_casilla_count": len(rejected_casillas),
                    "rejected_casilla_ids": "|".join(rejected_casillas),
                },
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            ),
        )


def m210_gross_source_mode(
    work_unit: WorkUnit,
    mode: M210GrossIncomeSourceMode | None,
) -> M210GrossIncomeSourceMode | None:
    """Resolve the persisted M210 [5] authority without affecting other modelos."""
    if str(work_unit.modelo) == Modelo("210").value:
        return mode or M210GrossIncomeSourceMode.MANUAL
    if mode is M210GrossIncomeSourceMode.LEDGER:
        raise ModeloAggregationBindingError(
            translated_message="application.modelo.errors.m210_ledger_source_requires_modelo_210",
        )
    return None


def validate_m210_agrupacion_renta_detail_rows(
    work_unit: WorkUnit,
    detail_rows: tuple[ModeloDetailRow, ...],
    m210_official_tipo_renta_code: str | None,
) -> None:
    """Run M210 annual legal-evidence validation before formula evaluation."""
    validate_m210_agrupacion_renta_rows_for_calculation(
        work_unit=work_unit,
        detail_rows=detail_rows,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
    )
