"""Build filing replay inputs from a persisted calculation revision.

:func:`revision_filing_replay_inputs` converts a filed or verified
:class:`CalculationRevision` plus its
:class:`~domain.modelos.work_unit.WorkUnit` into the flat Modelo-input map
the filing runtime accepts. Stored operator inputs, binding overrides, and
relation overrides are replayed directly; calculated informational casillas are
recovered from the :class:`~domain.calculations.registry.RegistrySnapshot`
only when the snapshot is still loadable. When a workflow
:class:`TaxpayerProfile` is available, profile applicability can also synthesize
explicit zeroes for relation slots whose source modelo is
:class:`~domain.calculations.registry.ApplicabilityVerdict`
``NOT_APPLICABLE``.

This is not a recalculation path. It rehydrates the persisted replay surface the
filing renderer needs: manual casilla inputs, binding channels, relation values,
calculated informational casillas, and Modelo 349 detail-row bindings.
Source-mesh row binding values are replayed as nested
``binding_id -> row-index -> scalar`` maps so repeating-record coordinates
survive draft/export replay without synthetic binding ids.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.aggregation import OBSERVATION_BACKED_BINDING_SOURCE_KINDS
from ...core.casilla_id import CasillaId
from ...core.modelo import Modelo
from ...domain.calculations.registry.applicability import (
    ApplicabilityVerdict,
    derive_modelo_applicability,
)
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.manual_input_selector import ManualInputProvider
from ...domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.filing.protocols import ModeloInputs, ModeloInputScalar
from ...domain.identifiers import canonical_decimal_string
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.m232_row_materialisation import m232_related_party_row_casilla_values
from ...domain.modelos.row_models import (
    Modelo232VinculadaRow,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
    m349_nif_number_for_export,
)
from ...domain.modelos.work_unit import WorkUnit

_ZERO_DECIMAL_TEXT = canonical_decimal_string(Decimal("0"))
_M349_OPERADOR_ROW_BINDINGS: dict[BindingId, str] = {
    "iva-349-operador-row-codigo-pais": "codigo_pais",
    "iva-349-operador-row-nif": "nif_comunitario",
    "iva-349-operador-row-apellidos": "razon_social",
    "iva-349-operador-row-clave": "clave_operacion",
    "iva-349-operador-row-base": "importe",
}
_M349_RECTIFICACION_ROW_BINDINGS: dict[BindingId, str] = {
    "iva-349-rectificacion-row-codigo-pais": "codigo_pais",
    "iva-349-rectificacion-row-nif": "nif_comunitario",
    "iva-349-rectificacion-row-apellidos": "razon_social",
    "iva-349-rectificacion-row-clave": "clave_operacion",
    "iva-349-rectificacion-row-ejercicio": "ejercicio",
    "iva-349-rectificacion-row-periodo": "periodo",
    "iva-349-rectificacion-row-base-rectificada": "base_rectificada",
    "iva-349-rectificacion-row-base-anterior": "base_anterior",
}


def revision_filing_replay_inputs(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    workflow_profile: TaxpayerProfile | None = None,
) -> ModeloInputs:
    """Return replayable filing inputs for one :class:`CalculationRevision`.

    The returned flat map is ordered by merge precedence: calculated
    informational casillas first, persisted manual casillas and binding
    overrides, Modelo 349 detail-row bindings, synthesized not-applicable
    relation zeroes, and finally persisted relation overrides. A stored relation
    override therefore always wins over a synthesized zero.

    See also :class:`TaxpayerProfile` for the optional profile applicability
    context used by relation-zero synthesis. No engine formulas are rerun here.
    """
    snapshot = _snapshot_for_work_unit(work_unit)
    bound_binding_replay_inputs = _observation_backed_bound_binding_replay_inputs(
        revision=revision,
        snapshot=snapshot,
    )
    return {
        **_informational_casilla_replay_inputs(revision=revision, snapshot=snapshot),
        **_casilla_replay_inputs(
            revision=revision,
            snapshot=snapshot,
            bound_binding_replay_inputs=bound_binding_replay_inputs,
        ),
        **bound_binding_replay_inputs,
        **dict(revision.binding_overrides),
        **dict(revision.row_binding_values),
        **_m349_detail_row_replay_inputs(revision=revision, work_unit=work_unit),
        **_m232_detail_row_replay_inputs(revision=revision, work_unit=work_unit),
        **_not_applicable_relation_zero_inputs(
            snapshot=snapshot,
            workflow_profile=workflow_profile,
            existing_relation_ids=frozenset(revision.relation_overrides),
        ),
        **dict(revision.relation_overrides),
    }


def _casilla_replay_inputs(
    *,
    revision: CalculationRevision,
    snapshot: RegistrySnapshot | None,
    bound_binding_replay_inputs: dict[BindingId, str],
) -> dict[str, str]:
    """Return stored casilla inputs, excluding migrated observation-backed bound projections."""
    if snapshot is None:
        return dict(revision.input_values_by_casilla_id)
    migrated_bound_casillas = _observation_backed_bound_casillas_with_replay_binding(
        snapshot=snapshot,
        binding_ids=frozenset(bound_binding_replay_inputs) | frozenset(revision.binding_overrides),
    )
    if not migrated_bound_casillas:
        return dict(revision.input_values_by_casilla_id)
    return {
        casilla_id: value
        for casilla_id, value in revision.input_values_by_casilla_id.items()
        if casilla_id not in migrated_bound_casillas
    }


def _observation_backed_bound_binding_replay_inputs(
    *,
    revision: CalculationRevision,
    snapshot: RegistrySnapshot | None,
) -> dict[BindingId, str]:
    """Recover missing binding replay values for observation-backed bound casillas.

    Some persisted revisions carry the bound-casilla projection in
    ``input_values_by_casilla_id`` but lack the matching binding value in
    ``binding_overrides``. The registry guard is correct to reject that shape.
    During filing replay, recover the binding entry from the persisted casilla
    projection when the registry gives a single safe binding target.
    """
    if snapshot is None:
        return {}
    bindings_by_id = {binding.id: binding for binding in snapshot.revision.bindings}
    recovered: dict[BindingId, str] = {}
    existing_binding_ids = frozenset(revision.binding_overrides)
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind != InputKind.BOUND:
            continue
        raw_value = _bound_casilla_replay_value(revision, casilla.id)
        if raw_value is None:
            continue
        binding_ids = bound_casilla_binding_ids(casilla)
        if existing_binding_ids.intersection(binding_ids):
            continue
        if not _has_observation_backed_binding(binding_ids, bindings_by_id):
            continue
        replay_binding_id = _replay_binding_id_for_bound_casilla(casilla, bindings_by_id)
        if replay_binding_id is None:
            continue
        recovered[replay_binding_id] = raw_value
    return dict(sorted(recovered.items()))


def _bound_casilla_replay_value(revision: CalculationRevision, casilla_id: CasillaId) -> str | None:
    raw_input = revision.input_values_by_casilla_id.get(casilla_id)
    if raw_input is not None:
        return raw_input
    verified_value = revision.casilla_values.get(casilla_id)
    if verified_value is None:
        return None
    return canonical_decimal_string(verified_value)


def _observation_backed_bound_casillas_with_replay_binding(
    *,
    snapshot: RegistrySnapshot,
    binding_ids: frozenset[BindingId],
) -> frozenset[str]:
    bindings_by_id = {binding.id: binding for binding in snapshot.revision.bindings}
    migrated: set[str] = set()
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind != InputKind.BOUND:
            continue
        casilla_binding_ids = bound_casilla_binding_ids(casilla)
        if not binding_ids.intersection(casilla_binding_ids):
            continue
        if _has_observation_backed_binding(casilla_binding_ids, bindings_by_id):
            migrated.add(casilla.id)
    return frozenset(migrated)


def _has_observation_backed_binding(
    binding_ids: tuple[BindingId, ...],
    bindings_by_id: dict[BindingId, BindingDefinition],
) -> bool:
    return any(
        (binding := bindings_by_id.get(binding_id)) is not None
        and binding.source in OBSERVATION_BACKED_BINDING_SOURCE_KINDS
        for binding_id in binding_ids
    )


def _replay_binding_id_for_bound_casilla(
    casilla: CasillaDefinition,
    bindings_by_id: dict[BindingId, BindingDefinition],
) -> BindingId | None:
    binding_ids = bound_casilla_binding_ids(casilla)
    manual_casilla_bindings = tuple(
        binding.id
        for binding_id in binding_ids
        if (binding := bindings_by_id.get(binding_id)) is not None
        and isinstance(binding.provider, ManualInputProvider)
        and binding.provider.casilla_id == casilla.id
    )
    if manual_casilla_bindings:
        return manual_casilla_bindings[0]
    if casilla.binding in bindings_by_id:
        return casilla.binding
    return next((binding_id for binding_id in binding_ids if binding_id in bindings_by_id), None)


def _m349_detail_row_replay_inputs(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
) -> dict[BindingId, dict[str, ModeloInputScalar]]:
    """Project persisted Modelo 349 detail rows into indexed binding maps.

    The filing runtime accepts repeating-row values as ``binding_id -> row-index
    -> scalar``. Stored row values are the durable row source; the EU IVA NIF
    subfield is normalized with the same export helper used by the row model so
    replay does not duplicate country-prefix logic.
    """
    if str(work_unit.modelo) != Modelo.M349.value:
        return {}
    operador_rows = tuple(row for row in revision.detail_rows if isinstance(row, Modelo349OperadorRow))
    rectification_rows = tuple(row for row in revision.detail_rows if isinstance(row, Modelo349RectificacionRow))
    if not operador_rows and not rectification_rows:
        return {}
    return {
        **_m349_row_binding_replay_inputs(operador_rows, _M349_OPERADOR_ROW_BINDINGS),
        **_m349_row_binding_replay_inputs(rectification_rows, _M349_RECTIFICACION_ROW_BINDINGS),
    }


def _m349_row_binding_value(
    row: Modelo349OperadorRow | Modelo349RectificacionRow,
    attr: str,
) -> ModeloInputScalar:
    if attr == "nif_comunitario":
        return m349_nif_number_for_export(row.nif_comunitario, row.codigo_pais)
    return getattr(row, attr)


def _m349_row_binding_replay_inputs(
    rows: tuple[Modelo349OperadorRow | Modelo349RectificacionRow, ...],
    binding_attributes: dict[BindingId, str],
) -> dict[BindingId, dict[str, ModeloInputScalar]]:
    replay_inputs: dict[BindingId, dict[str, ModeloInputScalar]] = {}
    for binding_id, attr in binding_attributes.items():
        values = {str(index): _m349_row_binding_value(row, attr) for index, row in enumerate(rows, start=1)}
        if values:
            replay_inputs[binding_id] = values
    return replay_inputs


def _m232_detail_row_replay_inputs(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
) -> dict[CasillaId, ModeloInputScalar]:
    """Project persisted Modelo 232 related-party rows into positional casillas.

    M232 declares its related parties as five positional row slots rather than a
    repeating-record binding family, so replay rehydrates them as ordinary
    casilla inputs (``vinculada-1-nif`` … ``vinculada-5-importe``) instead of the
    indexed ``binding_id -> row-index`` maps Modelo 349 uses.

    The row-to-casilla mapping comes from the domain authority
    :func:`~domain.modelos.m232_related_party_row_casilla_values`, the same one
    the observation materialiser reads, so a persisted row cannot reach one
    surface and silently vanish from the other -- which is exactly what happened
    while replay had no M232 branch at all: valid operator-supplied rows stayed
    in encrypted storage and produced no replay inputs, losing them during export
    or filing reconstruction.

    Money values are rendered through the canonical decimal string so the
    replayed scalar matches what every other numeric replay input carries.
    """
    if str(work_unit.modelo) != Modelo.M232.value:
        return {}
    rows = tuple(row for row in revision.detail_rows if isinstance(row, Modelo232VinculadaRow))
    if not rows:
        return {}
    return {
        casilla_id: canonical_decimal_string(value) if isinstance(value, Decimal) else value
        for casilla_id, value in m232_related_party_row_casilla_values(rows).items()
    }


def _snapshot_for_work_unit(work_unit: WorkUnit) -> RegistrySnapshot | None:
    """Return the law-determined registry snapshot for ``work_unit``, if loadable."""
    try:
        return bundled_authority().snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except RegistrySnapshotError:
        return None


def _informational_casilla_replay_inputs(
    *,
    revision: CalculationRevision,
    snapshot: RegistrySnapshot | None,
) -> dict[str, str]:
    """Return non-formula informational casillas that the filing renderer needs as inputs."""
    if snapshot is None:
        return {}
    formula_targets = frozenset(formula.target_casilla_id for formula in snapshot.revision.formulas)
    return {
        casilla.id: canonical_decimal_string(revision.casilla_values[casilla.id])
        for casilla in snapshot.revision.casillas
        if casilla.input_kind == InputKind.INFORMATIONAL
        and casilla.id not in formula_targets
        and casilla.id in revision.casilla_values
    }


def _not_applicable_relation_zero_inputs(
    *,
    snapshot: RegistrySnapshot | None,
    workflow_profile: TaxpayerProfile | None,
    existing_relation_ids: frozenset[RelationId],
) -> dict[RelationId, str]:
    """Return explicit zeroes for profile-proven not-applicable relation slots.

    This is intentionally narrower than "missing relation defaults to zero": it
    only considers dependency classifications already marked conditional on
    economic activity, and it only zeroes relations whose source modelo the
    canonical applicability table positively reports as ``NOT_APPLICABLE`` for
    the workflow profile. Suffered-retention relations are not conditional and
    therefore remain operator/certificate supplied.
    """
    if snapshot is None or workflow_profile is None:
        return {}
    active_relation_ids = _active_relation_ids(snapshot)
    values = {
        relation_id: _ZERO_DECIMAL_TEXT
        for classification in snapshot.revision.dependency_classifications
        for relation_id in _not_applicable_relation_zero_ids(
            conditional_on_economic_activity=classification.conditional_on_economic_activity,
            source_modelo=classification.source_modelo,
            relation_refs=classification.relation_refs,
            workflow_profile=workflow_profile,
            active_relation_ids=active_relation_ids,
            existing_relation_ids=existing_relation_ids,
        )
    }
    return dict(sorted(values.items()))


def _active_relation_ids(snapshot: RegistrySnapshot) -> frozenset[RelationId]:
    return frozenset(
        relation.id
        for relation in snapshot.revision.relations
        if not relation.target_periods or snapshot.period in relation.target_periods
    )


def _not_applicable_relation_zero_ids(
    *,
    conditional_on_economic_activity: bool,
    source_modelo: str,
    relation_refs: tuple[RelationId, ...],
    workflow_profile: TaxpayerProfile,
    active_relation_ids: frozenset[RelationId],
    existing_relation_ids: frozenset[RelationId],
) -> tuple[RelationId, ...]:
    if not conditional_on_economic_activity:
        return ()
    try:
        applicability = derive_modelo_applicability(workflow_profile, source_modelo)
    except (TypeError, ValueError):
        return ()
    if applicability.verdict is not ApplicabilityVerdict.NOT_APPLICABLE:
        return ()
    return tuple(
        relation_id
        for relation_id in relation_refs
        if relation_id not in existing_relation_ids and relation_id in active_relation_ids
    )


__all__ = ["revision_filing_replay_inputs"]
