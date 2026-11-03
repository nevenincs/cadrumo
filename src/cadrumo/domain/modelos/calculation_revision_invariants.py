"""Cross-field invariants of a saved calculation revision.

Each check reads the whole revision and raises :class:`ModeloValidationError`
at the first inconsistency, so the revision model's validator can run them in a
fixed order and refuse the first one that fails.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from ...core.identity.hex_ids import CalculationRevisionId
from ..calculations.record_row_membership import validate_closed_record_row_sets
from ..calculations.row_casilla import DirectRowMaterializationProvenance, RowCasillaKey
from ..calculations.row_source_identity import RowBindingKey
from .calculation_revision_identity import outputs_for_hash_from_mapping, outputs_for_hash_from_observations
from .errors import ModeloValidationError
from .filing_record import FilingDeclarationKind

if TYPE_CHECKING:
    from .calculation_revision import CalculationRevision


def validate_revision_identity(revision: CalculationRevision, derived: CalculationRevisionId) -> None:
    """Refuse a revision whose stored id differs from the id derived from its inputs."""
    if derived != revision.calculation_revision_id:
        raise ModeloValidationError(
            f"calculation_revision_id {revision.calculation_revision_id!r} does not match "
            f"the derived id {derived!r} for work_unit_id={revision.work_unit_id!r}",
        )


def validate_annual_summary_handoff_target(revision: CalculationRevision) -> None:
    """Refuse an annual-summary handoff aimed at another revision or disagreeing with its outputs."""
    handoff = revision.m303_regimen_simplificado_annual_summary_handoff
    if handoff is None:
        return
    if handoff.target_calculation_revision_id != revision.calculation_revision_id:
        raise ModeloValidationError(
            "M303 simplified annual-summary handoff target calculation revision id must equal its containing revision",
        )
    missing_outputs = tuple(casilla_id for casilla_id in handoff.values if casilla_id not in revision.casilla_values)
    if missing_outputs:
        raise ModeloValidationError(
            "M303 simplified annual-summary handoff target revision is missing its "
            f"Modelo 390 outputs: {missing_outputs!r}",
        )
    mismatched_outputs = tuple(
        casilla_id for casilla_id in handoff.values if revision.casilla_values[casilla_id] != handoff.values[casilla_id]
    )
    if mismatched_outputs:
        raise ModeloValidationError(
            "M303 simplified annual-summary handoff values disagree with the target "
            f"Modelo 390 outputs: {mismatched_outputs!r}",
        )


def _validate_replay_channel_overlap(
    left_name: str,
    left_values: Mapping[str, object],
    right_name: str,
    right_values: Mapping[str, object],
) -> None:
    overlapping_ids = sorted(set(left_values).intersection(right_values))
    if overlapping_ids:
        raise ModeloValidationError(
            "calculation revision replay ids must be channel-unique; "
            f"ids appear in both {left_name} and {right_name}: {overlapping_ids!r}",
        )


def validate_replay_channels(revision: CalculationRevision) -> None:
    """Refuse a replay id that appears in more than one of the override and row-value channels."""
    _validate_replay_channel_overlap(
        "binding_overrides",
        revision.binding_overrides,
        "relation_overrides",
        revision.relation_overrides,
    )
    _validate_replay_channel_overlap(
        "binding_overrides",
        revision.binding_overrides,
        "row_binding_values",
        revision.row_binding_values,
    )
    _validate_replay_channel_overlap(
        "row_binding_values",
        revision.row_binding_values,
        "relation_overrides",
        revision.relation_overrides,
    )


def validate_operator_layer(revision: CalculationRevision) -> None:
    """Keep an operator value and an explicit clear of the same casilla mutually exclusive."""
    layer = revision.operator_layer
    if layer is None:
        return
    both = sorted(layer.casilla_ids().intersection(revision.cleared_casilla_ids))
    if both:
        raise ModeloValidationError(
            f"calculation revision operator layer sets casillas it also records as cleared: {both!r}",
        )


def validate_observation_projection(revision: CalculationRevision) -> None:
    """Refuse casilla values that lack observations or disagree with the observations' projection."""
    if revision.casilla_values and not revision.observations:
        raise ModeloValidationError(
            "calculation revision with casilla_values must carry typed observations; "
            "pass CasillaObservation rows as the canonical source so legal_refs, "
            "source_refs, and formula provenance survive the domain boundary.",
        )
    if revision.observations:
        projected = outputs_for_hash_from_observations(revision.observations)
        persisted = outputs_for_hash_from_mapping(revision.casilla_values)
        if projected != persisted:
            raise ModeloValidationError(
                "casilla_values is inconsistent with the typed observations envelope: "
                f"observations project to {projected!r} but casilla_values is {persisted!r}. "
                "Both fields must encode the same per-casilla outputs; pass observations "
                "as the canonical source and let casilla_values mirror its projection.",
            )


def validate_amendment_metadata(revision: CalculationRevision) -> None:
    """Refuse an amendment identity without a reason, or a reason without an identity."""
    if (revision.amendment_identity is None) != (revision.amendment_reason is None):
        raise ModeloValidationError(
            "amendment_identity and amendment_reason must be set together or both be None",
        )


def validate_secure_revision_context(
    revision: CalculationRevision,
    validation_context: Mapping[str, object] | None,
) -> None:
    """Refuse a secure-storage revision that omits a required row materialization field."""
    if (
        validation_context is not None
        and validation_context.get("secure_calculation_revision") is True
        and not {"row_source_identities", "row_casilla_values", "row_casilla_provenance"}.issubset(
            revision.model_fields_set,
        )
    ):
        raise ModeloValidationError("secure calculation revision is missing required row materialization fields")


def _source_decimal_for_row_casilla(
    revision: CalculationRevision,
    provenance: DirectRowMaterializationProvenance,
) -> Decimal | None:
    source_value = revision.row_binding_values.get(provenance.source_binding_id, {}).get(
        str(provenance.source_row_index),
    )
    try:
        return Decimal(source_value) if source_value is not None else None
    except Exception as exc:
        raise ModeloValidationError("row casilla provenance source value is not decimal") from exc


def _validate_row_casilla_coordinate(
    revision: CalculationRevision,
    key: RowCasillaKey,
    provenance: DirectRowMaterializationProvenance,
    source_coordinates: set[RowBindingKey],
) -> None:
    if key[1] != provenance.source_row_index:
        raise ModeloValidationError("row casilla index must match its direct source row index")
    source_key = (provenance.source_binding_id, provenance.source_row_index)
    if source_key in source_coordinates:
        raise ModeloValidationError("one source row cannot materialize more than one row casilla")
    source_coordinates.add(source_key)
    source_identity = revision.row_source_identities.get(source_key)
    if source_identity is None:
        raise ModeloValidationError("row casilla provenance source coordinate has no row source identity")
    if source_identity != provenance.source_identity:
        raise ModeloValidationError("row casilla provenance source identity does not match its source row")
    source_decimal = _source_decimal_for_row_casilla(revision, provenance)
    if source_decimal != revision.row_casilla_values[key]:
        raise ModeloValidationError("row casilla value does not match its source row value")


def validate_row_materialization(revision: CalculationRevision) -> None:
    """Refuse closed record rows, row identities or row casillas that disagree with their source rows."""
    try:
        validate_closed_record_row_sets(
            revision.closed_record_row_sets,
            supplied_binding_ids=set(revision.binding_overrides) | set(revision.row_binding_values),
        )
    except ValueError as exc:
        raise ModeloValidationError("closed record rows disagree with saved binding values or scope") from exc
    if any(
        row_set.work_unit_id != revision.work_unit_id or row_set.registry_snapshot_ref != revision.registry_snapshot_ref
        for row_set in revision.closed_record_row_sets
    ):
        raise ModeloValidationError("closed record rows do not belong to the calculation revision")
    row_value_keys = {
        (binding_id, int(row_index)) for binding_id, rows in revision.row_binding_values.items() for row_index in rows
    }
    if not set(revision.row_source_identities).issubset(row_value_keys):
        raise ModeloValidationError("row source identity coordinate has no row binding value")
    if set(revision.row_casilla_values) != set(revision.row_casilla_provenance):
        raise ModeloValidationError("row casilla values and provenance must have exactly matching coordinates")
    source_coordinates: set[RowBindingKey] = set()
    for key, provenance in revision.row_casilla_provenance.items():
        _validate_row_casilla_coordinate(revision, key, provenance, source_coordinates)


def validate_lifecycle_order(revision: CalculationRevision) -> None:
    """Refuse a revision updated before it was created."""
    if revision.updated_at < revision.created_at:
        raise ModeloValidationError(
            f"updated_at {revision.updated_at.isoformat()} precedes created_at {revision.created_at.isoformat()}",
        )


def _aggregate_context_from_validation_context(
    validation_context: Mapping[str, object] | None,
) -> object:
    if validation_context is None:
        return None
    typed_context = TypeAdapter(dict[str, object]).validate_python(validation_context)
    from .calculation_revision_aggregate import CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY

    return typed_context.get(CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY)


def validate_rectificativa_aggregate_context(
    revision: CalculationRevision,
    validation_context: Mapping[str, object] | None,
) -> None:
    """Refuse a rectificativa revision that is not validated against its aggregate context."""
    if (
        revision.amendment_identity is None
        or revision.amendment_identity.kind is not FilingDeclarationKind.RECTIFICATIVA
    ):
        return
    from .calculation_revision_aggregate import (
        CalculationRevisionAggregateContext,
        validate_calculation_revision_aggregate,
    )

    raw_context = _aggregate_context_from_validation_context(validation_context)
    if not isinstance(raw_context, CalculationRevisionAggregateContext):
        raise ModeloValidationError(
            "rectificativa calculation revision requires context-bound aggregate validation",
        )
    validate_calculation_revision_aggregate(revision, context=raw_context)
