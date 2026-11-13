"""The row statements of a carry that a statement on another column of the same source supersedes.

A carry once stated on one column may now be stated on others: a let
property's pending expenses were one total before they were stated per
origin year. The new statement replaces the old one on its row, and the
revision an edit records keeps that history.
"""

from __future__ import annotations

from collections.abc import MutableMapping

from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ...domain.modelos.calculation_revision_operator_layer import ATTESTED_ZERO, RowCarryAttestation
from .edit_models import ModeloEditBindingAddressV1

type RowAttestations = MutableMapping[tuple[BindingId, str], RowCarryAttestation]


def is_row_stated(revision: ModeloRevision, binding_id: BindingId) -> bool:
    """Whether the carry of ``binding_id`` is stated row by row."""
    family = next((item.absence_attestation for item in revision.bindings if item.id == binding_id), None)
    return family is not None and family.row_grain


def withdraw_superseded_row_statements(
    row_attestations: RowAttestations, revision: ModeloRevision, address: ModeloEditBindingAddressV1
) -> None:
    """Drop the row's statements on a column of the same source that no longer takes one.

    A withdrawn statement that nothing was pending still says so of every
    column that now takes the statement, so it is restated there as absence
    where the row states nothing yet; an amount cannot be split, so it is
    withdrawn and those columns stay unstated.
    """
    bindings = {binding.id: binding for binding in revision.bindings}
    stated = bindings[address.binding_id]
    for binding_id, row in tuple(row_attestations):
        if row != address.row_identity or is_row_stated(revision, binding_id):
            continue
        stale = bindings.get(binding_id)
        if stale is not None and stale.source is not stated.source:
            continue
        withdrawn = row_attestations.pop((binding_id, row))
        if stale is not None and withdrawn.stated_amount == 0:
            _restate_absence_on_columns(row_attestations, revision, stated, row)


def _restate_absence_on_columns(
    row_attestations: RowAttestations, revision: ModeloRevision, stated: BindingDefinition, row: str
) -> None:
    """State absence on the row for each column that takes the same statement as ``stated``."""
    for column in revision.bindings:
        if column.source is stated.source and column.absence_attestation is stated.absence_attestation:
            row_attestations.setdefault(
                (column.id, row),
                RowCarryAttestation(binding_id=column.id, source_row_identity=row, amount=ATTESTED_ZERO, absent=True),
            )
