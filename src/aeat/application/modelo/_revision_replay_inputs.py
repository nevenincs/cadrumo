"""Build filing replay inputs from a persisted calculation revision.

:func:`revision_filing_replay_inputs` converts a filed or verified
:class:`CalculationRevision` plus its
:class:`~aeat.domain.modelos._work_unit.WorkUnit` into the flat Modelo-input map
the filing runtime accepts. Stored operator inputs, binding overrides, and
relation overrides are replayed directly; calculated informational casillas are
recovered from the :class:`~aeat.domain.calculations.registry.RegistrySnapshot`
only when the snapshot is still loadable. When a workflow
:class:`TaxpayerProfile` is available, profile applicability can also synthesize
explicit zeroes for relation slots whose source modelo is
:class:`~aeat.domain.calculations.registry.ApplicabilityVerdict`
``NOT_APPLICABLE``.
"""

from __future__ import annotations

from decimal import Decimal

from ...core import Modelo
from ...core.resources import resources
from ...domain import filing as filing_domain
from ...domain._identifiers import canonical_decimal_string
from ...domain.calculations.registry import (
    ApplicabilityVerdict,
    BindingId,
    InputKind,
    RegistrySnapshot,
    RegistrySnapshotError,
    RelationId,
    derive_modelo_applicability,
)
from ...domain.deadlines import TaxpayerProfile
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._row_models import Modelo349OperadorRow
from ...domain.modelos._work_unit import WorkUnit

_ZERO_DECIMAL_TEXT = canonical_decimal_string(Decimal("0"))
_M349_OPERADOR_ROW_BINDINGS: dict[BindingId, str] = {
    "iva-349-operador-row-codigo-pais": "codigo_pais",
    "iva-349-operador-row-nif": "nif_comunitario",
    "iva-349-operador-row-apellidos": "razon_social",
    "iva-349-operador-row-clave": "clave_operacion",
    "iva-349-operador-row-base": "importe",
}


def revision_filing_replay_inputs(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    workflow_profile: TaxpayerProfile | None = None,
) -> filing_domain.ModeloInputs:
    """Return replayable filing inputs for one :class:`CalculationRevision`.

    See also :class:`TaxpayerProfile` for the optional profile applicability
    context used by relation-zero synthesis.
    """
    snapshot = _snapshot_for_work_unit(work_unit)
    return {
        **_informational_casilla_replay_inputs(revision=revision, snapshot=snapshot),
        **dict(revision.input_values_by_casilla_id),
        **dict(revision.binding_overrides),
        **_m349_detail_row_replay_inputs(revision=revision, work_unit=work_unit),
        **_not_applicable_relation_zero_inputs(
            snapshot=snapshot,
            workflow_profile=workflow_profile,
            existing_relation_ids=frozenset(revision.relation_overrides),
        ),
        **dict(revision.relation_overrides),
    }


def _m349_detail_row_replay_inputs(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
) -> dict[BindingId, dict[str, filing_domain.ModeloInputScalar]]:
    if str(work_unit.modelo) != Modelo.M349.value:
        return {}
    rows = tuple(row for row in revision.detail_rows if isinstance(row, Modelo349OperadorRow))
    if not rows:
        return {}
    return {
        binding_id: {str(index): getattr(row, attr) for index, row in enumerate(rows, start=1)}
        for binding_id, attr in _M349_OPERADOR_ROW_BINDINGS.items()
    }


def _snapshot_for_work_unit(work_unit: WorkUnit) -> RegistrySnapshot | None:
    try:
        return resources().modelos.authority.snapshot(
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
    if snapshot is None:
        return {}
    return {
        casilla.id: canonical_decimal_string(revision.casilla_values[casilla.id])
        for casilla in snapshot.revision.casillas
        if casilla.input_kind == InputKind.INFORMATIONAL and casilla.id in revision.casilla_values
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
    active_relation_ids = frozenset(
        relation.id
        for relation in snapshot.revision.relations
        if not relation.target_periods or snapshot.period in relation.target_periods
    )
    values: dict[RelationId, str] = {}
    for classification in snapshot.revision.dependency_classifications:
        if not classification.conditional_on_economic_activity:
            continue
        try:
            applicability = derive_modelo_applicability(workflow_profile, classification.source_modelo)
        except (TypeError, ValueError):
            continue
        if applicability.verdict is not ApplicabilityVerdict.NOT_APPLICABLE:
            continue
        for relation_id in classification.relation_refs:
            if relation_id in existing_relation_ids or relation_id not in active_relation_ids:
                continue
            values[relation_id] = _ZERO_DECIMAL_TEXT
    return dict(sorted(values.items()))


__all__ = ["revision_filing_replay_inputs"]
