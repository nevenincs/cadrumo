"""Shared calculation helpers for modelo application actions.

The helpers load mutable :class:`~WorkUnit` records, resolve
their law-determined
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`, and project engine,
imported, or amended values into
:class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation` provenance rows.
Amendment helpers reuse the baseline
:class:`~CalculationRevision` where a corrected casilla was
not overridden, and rebuild overridden rows from the selected snapshot so
legal/source grounding is never silently erased.

See Also:
    :mod:`cadrumo.application.modelo.calculation_actions`:
        Uses these helpers before registry-engine execution and persistence.
    :mod:`cadrumo.application.modelo.amendment_actions`:
        Reuses amendment observation projection for corrected filing records.
    :func:`cadrumo.domain.calculations.registry.authority.bundled_indexed_authority`:
        Leases the packaged indexed registry generation for snapshot resolution.
    :class:`~cadrumo.domain.calculations.registry.formula_runtime.RegistryCalculationResult`:
        Registry-engine result whose values and formula entries are projected
        into typed observations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.period import Period
from ...domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ...domain.calculations.registry.binding_value_contract import BindingValueChannel
from ...domain.calculations.registry.bindings import CasillaObservation, resolve_available_bound_inputs_by_casilla_id
from ...domain.calculations.registry.casilla_membership import casillas_by_id, text_family_casilla_ids
from ...domain.calculations.registry.formula_runtime import (
    RegistryCalculationEntry,
    RegistryCalculationResult,
    calculate_registry_snapshot,
)
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.observation_fold import fold_pagos_fraccionados_ingresados
from ...domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ...domain.calculations.registry.result_casillas import canonical_result_amount, result_disposition_casilla_ids
from ...domain.calculations.registry.schema import FormulaDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.identifiers import canonical_decimal_string
from ...domain.modelos.calculation_binding_values import persisted_boolean_binding_value
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from ...domain.modelos.filing_record import FilingDeclarationKind
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from .action_errors import (
    CalculationRegistryUnavailableError,
    CasillaProvenanceMissingError,
    WorkUnitRevisionDivergenceError,
)
from .registry_helpers import absent_authority_file
from .work_lifecycle import ActiveWorkUnitUse, require_active_work_unit


def load_work_unit_for_calculation(
    work_units: WorkUnitCatalogue,
    *,
    work_unit_id: str,
    repository_bucket_id: str | None = None,
) -> WorkUnit:
    """Delegate calculation target state/addressability to the canonical lifecycle guard."""
    return require_active_work_unit(
        work_units,
        work_unit_id=work_unit_id,
        repository_bucket_id=repository_bucket_id,
        use=ActiveWorkUnitUse.CALCULATE,
    )


def assert_snapshot_matches_work_unit_revision(
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    *,
    period: Period | None = None,
) -> None:
    """Raise when the :class:`RegistrySnapshot` revision diverges from the pinned one.

    ``snapshot``'s revision must equal the revision ``work_unit`` was pinned to.

    This is the single home for the D1 calc-time assertion's message and
    exception type: the law-determined revision must equal the revision the
    work unit was created against, or :exc:`WorkUnitRevisionDivergenceError`
    directs the operator to re-create the work unit. Divergence is possible
    only when the registry's law-mapping was corrected after the work unit was
    created, or for units persisted before the strengthened creation gate.

    ``period`` names the AEAT natural-key coordinates the message reports;
    most callers resolve ``snapshot`` from ``work_unit.period`` and can omit
    it. A caller that resolves ``snapshot`` from a different, caller-supplied
    period (see
    :func:`cadrumo.application.modelo.result_disposition_resolution.result_disposition_values_for_revision`,
    which threads the export path's period through for the Modelo 303
    refund-election decision) passes that period so the message names the
    coordinates the snapshot was actually resolved against.

    See Also:
        :func:`cadrumo.application.modelo.work_addressing.law_selected_revision_for_work_target`:
            Performs the create-time counterpart of this revision identity
            assertion.
        :class:`cadrumo.application.modelo.action_errors.WorkUnitRevisionDivergenceError`:
            Refusal raised when the pinned revision no longer matches the
            law-determined snapshot.
    """
    if snapshot.revision.id == work_unit.revision_id:
        return
    resolved_period = period if period is not None else work_unit.period
    raise WorkUnitRevisionDivergenceError(
        translated_message="application.modelo.errors.work_unit_revision_divergence",
        # The context keys ARE the message template's placeholder names. They
        # had drifted -- the catalogue asks for work_unit_id, work_unit_revision
        # and law_revision -- so the rendered refusal showed those three
        # placeholders literally and named NEITHER revision nor the work unit,
        # which is precisely the guidance an operator needs to re-create it.
        context={
            "work_unit_id": work_unit.work_unit_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": resolved_period.registry_token,
            "work_unit_revision": work_unit.revision_id,
            "law_revision": snapshot.revision.id,
        },
    )


def resolve_registry_snapshot_for_work_unit(
    work_unit: WorkUnit,
    *,
    grade: RegistryAuthorityGrade | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> RegistrySnapshot:
    """Resolve and return the :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.

    Without a ``grade`` the snapshot is read as a consumer that calculates or
    reports on the work unit would read it: filing grade for an authored year,
    calculation grade for a year carried across from another edition.

    After resolution the snapshot's revision id is asserted equal to the work
    unit's pinned ``revision_id`` via :func:`assert_snapshot_matches_work_unit_revision`
    (a calc-time assertion).

    The :class:`~WorkUnit` ``revision_id`` is never passed
    into the snapshot resolution call; it is only compared against the
    law-determined resolver answer.

    See Also:
        :func:`cadrumo.application.modelo.work_addressing.law_selected_revision_for_work_target`:
            Performs the create-time counterpart of this revision identity
            assertion.
        :class:`cadrumo.application.modelo.action_errors.WorkUnitRevisionDivergenceError`:
            Refusal raised when the pinned revision no longer matches the
            law-determined snapshot.
    """
    from ...domain.calculations.registry.errors import RegistrySnapshotError

    if operation is not None:
        try:
            snapshot = (
                operation.reading_snapshot(
                    work_unit.modelo,
                    filing_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                )
                if grade is None
                else operation.snapshot(
                    work_unit.modelo,
                    filing_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                    grade=grade,
                )
            )
        except RegistrySnapshotError as exc:
            raise CalculationRegistryUnavailableError(
                translated_message="application.modelo.errors.calculation_registry_snapshot_unresolved",
                context={
                    "modelo": work_unit.modelo,
                    "filing_year": work_unit.filing_year,
                    "period": work_unit.period.registry_token,
                },
            ) from exc
        assert_snapshot_matches_work_unit_revision(work_unit, snapshot)
        return snapshot
    try:
        with bundled_indexed_authority().operation() as indexed_operation:
            return resolve_registry_snapshot_for_work_unit(
                work_unit,
                grade=grade,
                operation=indexed_operation,
            )
    except FileNotFoundError as exc:
        raise CalculationRegistryUnavailableError(
            translated_message="application.modelo.errors.calculation_registry_root_missing",
            context={"missing_path": absent_authority_file(exc)},
        ) from exc


def build_typed_observations(
    *,
    engine_result: RegistryCalculationResult,
    snapshot: RegistrySnapshot,
) -> tuple[CasillaObservation, ...]:
    """Build :class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation` rows.

    The engine result is already the canonical grounded envelope, including
    text-family casillas that do not appear in its Decimal-only ``values``
    projection. This boundary verifies every observation still belongs to the
    selected registry revision, then preserves the envelope unchanged. Any
    observation without a registry casilla definition raises
    :class:`cadrumo.application.modelo.action_errors.CasillaProvenanceMissingError` through
    :func:`cadrumo.application.modelo.calculation_helpers.casilla_observation_for`
    rather than emitting an ungrounded row.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
    """
    revision_casillas_by_id = casillas_by_id(snapshot.revision)
    unknown = tuple(
        observation.casilla_id
        for observation in engine_result.observations
        if observation.casilla_id not in revision_casillas_by_id
    )
    if unknown:
        raise CasillaProvenanceMissingError(
            translated_message="errors.error.error_modelo_casilla_provenance_missing",
            context={"casilla_id": unknown[0], "origin": "engine_result"},
        )
    return engine_result.observations


def external_filing_observations(
    *,
    casilla_values: Mapping[CasillaId, Decimal],
    snapshot: RegistrySnapshot,
) -> tuple[CasillaObservation, ...]:
    """Build :class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation` rows for imports.

    The :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot` supplies the
    provenance for imported values that have no
    :class:`~cadrumo.domain.calculations.registry.formula_runtime.RegistryCalculationEntry`
    in the current process. This keeps imported AEAT baselines on the same
    typed-observation contract as locally calculated revisions.

    See Also:
        :func:`cadrumo.application.modelo.external_import_actions.import_external_filing_evidence`:
            Persists the external-evidence baseline that consumes these rows.
    """
    revision_casillas_by_id = casillas_by_id(snapshot.revision)
    return tuple(
        casilla_observation_for(
            casilla_id=casilla_id,
            value=value,
            entry=None,
            registry_casilla=revision_casillas_by_id.get(casilla_id),
        )
        for casilla_id, value in casilla_values.items()
    )


def casilla_observation_for(
    *,
    casilla_id: CasillaId,
    value: Decimal,
    entry: RegistryCalculationEntry | None,
    registry_casilla: CasillaDefinition | None,
) -> CasillaObservation:
    """Project one casilla into a typed observation with full provenance.

    Formula entries contribute formula id, operand lineage, and legal/source
    refs. Non-formula casillas use the
    :class:`~cadrumo.domain.calculations.registry.schema_surfaces.CasillaDefinition` selected by
    the :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`. A missing
    definition is a hard provenance error because emitting a
    :class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation` without
    ``legal_refs`` and ``source_refs`` would erase legal grounding.
    """
    if entry is not None:
        return CasillaObservation(
            casilla_id=casilla_id,
            value=value,
            formula_id=entry.formula_id,
            op=entry.op,
            operand_refs=entry.operand_refs,
            operand_casilla_refs=entry.operand_casilla_refs,
            operand_values=entry.operand_values,
            legal_refs=entry.legal_refs,
            source_refs=entry.source_refs,
        )
    if registry_casilla is None:
        raise CasillaProvenanceMissingError(
            translated_message="errors.error.error_modelo_casilla_provenance_missing",
            context={"casilla_id": casilla_id, "origin": "engine_result"},
        )
    return CasillaObservation(
        casilla_id=casilla_id,
        value=value,
        formula_id=None,
        operand_refs=(),
        operand_casilla_refs=(),
        operand_values=(),
        legal_refs=registry_casilla.legal_refs,
        source_refs=registry_casilla.source_refs,
    )


@dataclass(frozen=True, slots=True)
class AmendmentCalculation:
    """Corrected values and their saved replay channels, before any lifecycle writes."""

    casilla_values: dict[CasillaId, Decimal]
    observations: tuple[CasillaObservation, ...]
    input_values_by_casilla_id: dict[CasillaId, str]
    binding_overrides: dict[BindingId, str]
    operator_layer: CalculationOperatorLayer | None


def amendment_prior_paid_values(
    *,
    baseline_revision: CalculationRevision,
    snapshot: RegistrySnapshot,
    amendment_kind: FilingDeclarationKind,
) -> dict[CasillaId, Decimal]:
    """Carry one confirmed period's accumulated payments, never its corrected snapshots' sum.

    Args:
        baseline_revision: The :class:`CalculationRevision` the correction starts from.
        snapshot: The :class:`RegistrySnapshot` pinned for the corrected declaration.
        amendment_kind: Which correction is being filed; only a complementaria carries payments.
    """
    if amendment_kind is not FilingDeclarationKind.COMPLEMENTARIA:
        return {}
    prior_paid_casillas = tuple(
        casilla for casilla in snapshot.revision.casillas if casilla.complementaria_only is not None
    )
    if not prior_paid_casillas:
        return {}
    result_ids = result_disposition_casilla_ids(snapshot.modelo.id)
    if result_ids is None:
        return {}
    result = canonical_result_amount(
        snapshot.modelo.id,
        {key: value for key, value in baseline_revision.casilla_values.items() if key in result_ids},
    )
    if result is None:
        return {}
    return {
        casilla.id: fold_pagos_fraccionados_ingresados(
            ((result, baseline_revision.casilla_values.get(casilla.id, Decimal("0"))),),
            subject=f"{snapshot.modelo.id} amendment",
        )
        for casilla in prior_paid_casillas
    }


def calculate_amendment(
    *,
    source_revision: CalculationRevision,
    overrides: Mapping[CasillaId, Decimal],
    prior_paid_values: Mapping[CasillaId, Decimal],
    snapshot: RegistrySnapshot,
    binding_overrides: Mapping[BindingId, str] | None = None,
) -> AmendmentCalculation:
    """Re-evaluate affected saved formula outputs with the canonical expression runtime.

    Imported replay maps contain observed outputs as well as inputs. Only the
    separate operator layer proves that a saved formula target was explicitly
    authored. Unaffected figures remain the filed declaration's facts; this
    path never pulls today's ledger or profile into a historical correction.

    Args:
        source_revision: The :class:`CalculationRevision` being corrected.
        overrides: Operator-authored casilla amounts replacing the filed ones.
        prior_paid_values: Confirmed prior payments carried into the correction.
        snapshot: The :class:`RegistrySnapshot` that supplies the formulas and bindings.
        binding_overrides: Explicit binding values the corrected declaration states beside
            those the filing recorded, such as the estimación directa modality a figure
            reached by the correction depends on. A historical correction never reads
            today's profile, so a binding the filing did not record stays unresolved
            unless it is named here.
    """
    _reject_prior_paid_conflicts(overrides, prior_paid_values)
    formulas = {formula.target_casilla_id: formula for formula in snapshot.revision.formulas}
    authored = _amendment_authored_inputs(source_revision, formulas, overrides)
    bindings = _amendment_bindings(source_revision, snapshot, overrides, binding_overrides)
    result, inputs, text_inputs = _recalculate_amendment(
        source_revision=source_revision,
        snapshot=snapshot,
        overrides=overrides,
        prior_paid_values=prior_paid_values,
        authored=authored,
        bindings=bindings,
        stated_bound_inputs=_stated_bound_inputs(snapshot, binding_overrides or {}),
        formulas=formulas,
    )
    recalculated = {observation.casilla_id: observation for observation in result.observations}
    values = {
        key: observation.value for key, observation in recalculated.items() if isinstance(observation.value, Decimal)
    }
    observations = amendment_observations(
        corrected_values=values,
        overrides={**overrides, **prior_paid_values},
        baseline_revision=source_revision,
        snapshot=snapshot,
    )
    replay_inputs = {key: canonical_decimal_string(value) for key, value in inputs.items()}
    replay_inputs.update(text_inputs)
    return AmendmentCalculation(
        casilla_values=values,
        observations=tuple(recalculated.get(observation.casilla_id, observation) for observation in observations),
        input_values_by_casilla_id=replay_inputs,
        binding_overrides=bindings,
        operator_layer=_amendment_operator_layer(source_revision.operator_layer, authored),
    )


def _reject_prior_paid_conflicts(
    overrides: Mapping[CasillaId, Decimal],
    prior_paid_values: Mapping[CasillaId, Decimal],
) -> None:
    """Refuse an operator amount that contradicts a confirmed prior payment for the same casilla."""
    for key, value in prior_paid_values.items():
        if key in overrides and overrides[key] != value:
            raise ValueError(f"amendment override conflicts with confirmed prior-paid value for {key!r}")


def _amendment_authored_inputs(
    source_revision: CalculationRevision,
    formulas: Mapping[CasillaId, FormulaDefinition],
    overrides: Mapping[CasillaId, Decimal],
) -> dict[CasillaId, str]:
    """Return the operator-authored casilla amounts the correction carries forward."""
    layer = source_revision.operator_layer
    authored = dict(layer.decimal_casilla_inputs) if layer is not None else {}
    if layer is None and source_revision.amendment_identity is not None:
        authored.update(_legacy_amendment_formula_corrections(source_revision, formulas))
    authored.update({key: canonical_decimal_string(value) for key, value in overrides.items()})
    return authored


def _legacy_amendment_formula_corrections(
    source_revision: CalculationRevision,
    formulas: Mapping[CasillaId, FormulaDefinition],
) -> dict[CasillaId, str]:
    """Recover explicit formula corrections from an older amendment's baseline replay map.

    Older amendments retained the baseline replay map. A changed formula value
    whose lineage was removed records an explicit correction; an identical
    imported scalar remains an observation, not an override.
    """
    corrections: dict[CasillaId, str] = {}
    for observation in source_revision.observations:
        if observation.formula_id is not None or observation.casilla_id not in formulas:
            continue
        raw = source_revision.input_values_by_casilla_id.get(observation.casilla_id)
        if isinstance(observation.value, Decimal) and (raw is None or Decimal(raw) != observation.value):
            corrections[observation.casilla_id] = canonical_decimal_string(observation.value)
    return corrections


def _amendment_bindings(
    source_revision: CalculationRevision,
    snapshot: RegistrySnapshot,
    overrides: Mapping[CasillaId, Decimal],
    binding_overrides: Mapping[BindingId, str] | None,
) -> dict[BindingId, str]:
    """Merge recorded and stated bindings; an overridden singly-bound casilla restates its binding."""
    bindings: dict[BindingId, str] = {**source_revision.binding_overrides, **(binding_overrides or {})}
    for casilla in snapshot.revision.casillas:
        binding_ids = bound_casilla_binding_ids(casilla)
        if casilla.id in overrides and len(binding_ids) == 1:
            bindings[binding_ids[0]] = canonical_decimal_string(overrides[casilla.id])
    return bindings


def _stated_bound_inputs(
    snapshot: RegistrySnapshot,
    binding_overrides: Mapping[BindingId, str],
) -> dict[CasillaId, Decimal]:
    """Lift the numeric bindings the correction states onto their bound casillas, as calculation does.

    A bound casilla fed by a ledger or profile source reads its value from the
    input channel, so without this lift a stated binding would leave the filed
    or replayed figure standing in its casilla.
    """
    decimal_bindings, _enum, _dates, _boolean = _amendment_binding_channels(snapshot, binding_overrides)
    return resolve_available_bound_inputs_by_casilla_id(snapshot.revision, decimal_bindings)


def _recalculate_amendment(
    *,
    source_revision: CalculationRevision,
    snapshot: RegistrySnapshot,
    overrides: Mapping[CasillaId, Decimal],
    prior_paid_values: Mapping[CasillaId, Decimal],
    authored: Mapping[CasillaId, str],
    bindings: Mapping[BindingId, str],
    stated_bound_inputs: Mapping[CasillaId, Decimal],
    formulas: Mapping[CasillaId, FormulaDefinition],
) -> tuple[RegistryCalculationResult, dict[CasillaId, Decimal], dict[CasillaId, str]]:
    """Run the registry engine over the corrected inputs; return its result and the replayed inputs.

    A casilla a stated binding feeds is a corrected figure like an operator
    override: it ranks below the operator's own casilla corrections and its
    dependents are recalculated.
    """
    decimal_bindings, enum_bindings, date_bindings, boolean_bindings = _amendment_binding_channels(snapshot, bindings)
    text_ids = text_family_casilla_ids(snapshot.revision.casillas)
    inputs = _amendment_numeric_inputs(
        source_revision, formulas, text_ids, {**stated_bound_inputs, **overrides, **prior_paid_values}
    )
    text_inputs = {key: raw for key, raw in source_revision.input_values_by_casilla_id.items() if key in text_ids}
    resolved_binding_ids = {*decimal_bindings, *enum_bindings, *date_bindings, *boolean_bindings}
    missing_binding_ids = tuple(
        binding.id for binding in snapshot.revision.bindings if binding.id not in resolved_binding_ids
    )
    relation_ids = {
        binding.id for binding, _ in relation_prefill_bindings_for_period(snapshot.revision, period=snapshot.period)
    }
    formula_overrides = _amendment_formula_overrides(source_revision, authored, formulas)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={},
        binding_values=decimal_bindings,
        enum_binding_values=enum_bindings,
        date_binding_values=date_bindings,
        boolean_binding_values=boolean_bindings,
        relation_values={key: Decimal(raw) for key, raw in source_revision.relation_overrides.items()},
        unresolved_binding_ids=missing_binding_ids,
        unresolved_relation_ids=tuple(binding_id for binding_id in missing_binding_ids if binding_id in relation_ids),
        unresolved_observation_backed_casilla_ids=_unresolved_observation_backed_casilla_ids(
            snapshot, inputs, missing_binding_ids
        ),
        text_inputs=text_inputs,
        formula_overrides=formula_overrides,
        retained_formula_observations=_retained_formula_observations(source_revision, formulas, formula_overrides),
        recalculate_from_casilla_ids=frozenset({*stated_bound_inputs, *overrides, *prior_paid_values}),
        recalculate_from_binding_ids=_changed_binding_ids(bindings, source_revision.binding_overrides),
    )
    return result, inputs, text_inputs


def _amendment_numeric_inputs(
    source_revision: CalculationRevision,
    formulas: Mapping[CasillaId, FormulaDefinition],
    text_ids: frozenset[CasillaId],
    corrected: Mapping[CasillaId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Layer saved replay inputs, filed values and corrected amounts for each non-formula numeric casilla."""
    inputs = {
        key: Decimal(raw)
        for key, raw in source_revision.input_values_by_casilla_id.items()
        if key not in formulas and key not in text_ids
    }
    inputs.update(
        {
            key: value
            for key, value in source_revision.casilla_values.items()
            if key not in formulas and key not in text_ids
        }
    )
    inputs.update({key: value for key, value in corrected.items() if key not in formulas})
    return inputs


def _amendment_formula_overrides(
    source_revision: CalculationRevision,
    authored: Mapping[CasillaId, str],
    formulas: Mapping[CasillaId, FormulaDefinition],
) -> dict[CasillaId, CasillaObservation]:
    """Pin every explicitly authored formula target, keeping that formula's legal and source grounding."""
    formula_overrides = {
        observation.casilla_id: observation
        for observation in source_revision.observations
        if observation.casilla_id in authored and observation.casilla_id in formulas and observation.formula_id is None
    }
    for key, value in authored.items():
        if key in formulas:
            formula = formulas[key]
            formula_overrides[key] = CasillaObservation(
                casilla_id=key,
                value=Decimal(value),
                formula_id=formula.id,
                op=formula.expression.op or "value",
                legal_refs=formula.legal_refs,
                source_refs=formula.source_refs,
            )
    return formula_overrides


def _retained_formula_observations(
    source_revision: CalculationRevision,
    formulas: Mapping[CasillaId, FormulaDefinition],
    formula_overrides: Mapping[CasillaId, CasillaObservation],
) -> dict[CasillaId, CasillaObservation]:
    """Return the saved formula observations the correction keeps unless a dependency changes."""
    return {
        observation.casilla_id: observation
        for observation in source_revision.observations
        if observation.casilla_id in formulas and observation.casilla_id not in formula_overrides
    }


def _unresolved_observation_backed_casilla_ids(
    snapshot: RegistrySnapshot,
    inputs: Mapping[CasillaId, Decimal],
    missing_binding_ids: tuple[BindingId, ...],
) -> frozenset[CasillaId]:
    """Return the casillas without an input whose binding the correction cannot resolve."""
    return frozenset(
        casilla.id
        for casilla in snapshot.revision.casillas
        if casilla.id not in inputs and set(bound_casilla_binding_ids(casilla)).intersection(missing_binding_ids)
    )


def _changed_binding_ids(
    bindings: Mapping[BindingId, str],
    recorded: Mapping[BindingId, str],
) -> frozenset[BindingId]:
    """Return the bindings whose corrected value differs from the one the filing recorded."""
    return frozenset(key for key in set(bindings) | set(recorded) if bindings.get(key) != recorded.get(key))


def _amendment_operator_layer(
    layer: CalculationOperatorLayer | None,
    authored: Mapping[CasillaId, str],
) -> CalculationOperatorLayer:
    """Carry the correction's authored amounts beside the source's other operator-layer channels."""
    return CalculationOperatorLayer(
        decimal_casilla_inputs=dict(authored),
        text_casilla_inputs=layer.text_casilla_inputs if layer is not None else {},
        binding_overrides=layer.binding_overrides if layer is not None else {},
        attested_binding_ids=layer.attested_binding_ids if layer is not None else (),
        value_attestations=layer.value_attestations if layer is not None else {},
        income_family_entry_digests=layer.income_family_entry_digests if layer is not None else {},
    )


def _amendment_binding_channels(
    snapshot: RegistrySnapshot,
    bindings: Mapping[BindingId, str],
) -> tuple[dict[BindingId, Decimal], dict[BindingId, str], dict[BindingId, date], dict[BindingId, bool]]:
    decimal: dict[BindingId, Decimal] = {}
    enum: dict[BindingId, str] = {}
    dates: dict[BindingId, date] = {}
    boolean: dict[BindingId, bool] = {}
    for binding in snapshot.revision.bindings:
        raw = bindings.get(binding.id)
        if raw is None:
            continue
        channel = binding.value.channel
        if channel in {BindingValueChannel.TEXT, BindingValueChannel.ENUM}:
            enum[binding.id] = raw
        elif channel is BindingValueChannel.DATE:
            dates[binding.id] = date.fromisoformat(raw)
        elif channel is BindingValueChannel.BOOLEAN and (truth := persisted_boolean_binding_value(raw)) is not None:
            boolean[binding.id] = truth
        else:
            decimal[binding.id] = Decimal(raw)
    return decimal, enum, dates, boolean


def amendment_observations(
    *,
    corrected_values: Mapping[CasillaId, Decimal],
    overrides: Mapping[CasillaId, Decimal],
    baseline_revision: CalculationRevision,
    snapshot: RegistrySnapshot,
) -> tuple[CasillaObservation, ...]:
    """Build amendment :class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation` rows.

    The baseline :class:`~CalculationRevision` contributes
    unchanged observations for casillas the amendment did not override. Newly
    overridden casillas are rebuilt from the
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot` so the persisted
    amendment revision carries legal/source provenance even when the imported
    baseline had sparse observation rows. A corrected casilla absent from the
    snapshot raises :class:`cadrumo.application.modelo.action_errors.CasillaProvenanceMissingError`.

    See Also:
        :func:`cadrumo.application.modelo.amendment_actions.amend_modelo_revision`:
            Uses these rows for the corrected amendment revision.
    """
    revision_casillas_by_id = casillas_by_id(snapshot.revision)
    baseline_by_id = {obs.casilla_id: obs for obs in baseline_revision.observations}
    observations: list[CasillaObservation] = []
    for casilla_id, value in corrected_values.items():
        if casilla_id not in overrides:
            carried = baseline_by_id.get(casilla_id)
            if carried is not None and carried.value == value:
                observations.append(carried)
                continue
        registry_casilla = revision_casillas_by_id.get(casilla_id)
        if registry_casilla is None:
            raise CasillaProvenanceMissingError(
                translated_message="errors.error.error_modelo_casilla_provenance_missing",
                context={"casilla_id": casilla_id, "origin": "amendment_corrected_values"},
            )
        observations.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                formula_id=None,
                operand_refs=(),
                operand_casilla_refs=(),
                operand_values=(),
                legal_refs=registry_casilla.legal_refs,
                source_refs=registry_casilla.source_refs,
            ),
        )
    return tuple(observations)


__all__ = [
    "AmendmentCalculation",
    "WorkUnitRevisionDivergenceError",
    "amendment_observations",
    "amendment_prior_paid_values",
    "assert_snapshot_matches_work_unit_revision",
    "build_typed_observations",
    "calculate_amendment",
    "casilla_observation_for",
    "external_filing_observations",
    "load_work_unit_for_calculation",
    "resolve_registry_snapshot_for_work_unit",
]
