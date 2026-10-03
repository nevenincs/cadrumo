"""Shared indexes for one canonical Modelo work-form projection."""

from __future__ import annotations

import re
from typing import Final

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.export_field_casilla import (
    export_field_casilla_id,
    layout_fields_in_emission_order,
)
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from .caller_context import caller_context_of
from .edit_models import (
    ModeloEditNonWritableBindingOverrideSurfaceEntryV1,
    ModeloEditNonWritableScalarSurfaceEntryV1,
    ModeloEditPermittedSurfaceEntryV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from .required_inputs import filer_required_casilla_ids
from .work_form_localization import render_box_locator_patterns
from .work_review import ModeloWorkReview, ModeloWorkReviewCasilla

_FILED_STATES: Final[frozenset[CalculationRevisionState]] = frozenset(
    {CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO}
)

"""The lifecycle states of a calculation recorded as filed."""


def _review_indexes(
    review: ModeloWorkReview,
) -> tuple[dict[str, ModeloWorkReviewCasilla], dict[str, set[str]]]:
    rows = {str(row.casilla_id): row for row in review.casillas}
    fed_casillas: dict[str, set[str]] = {}
    for row in review.casillas:
        refs = (
            *(str(origin.binding_id) for origin in row.concrete_bindings),
            *(() if row.concrete_formula is None else (str(ref) for ref in row.concrete_formula.operand_refs)),
        )
        for ref in refs:
            fed_casillas.setdefault(ref, set()).add(str(row.casilla_id))
    return rows, fed_casillas


def _registry_indexes(
    snapshot: RegistrySnapshot,
) -> tuple[dict[str, CasillaDefinition], dict[str, BindingDefinition], dict[str, str]]:
    casillas = {str(item.id): item for item in snapshot.revision.casillas}
    bindings = {str(item.id): item for item in snapshot.revision.bindings}
    casilla_by_binding: dict[str, str] = {}
    for casilla in snapshot.revision.casillas:
        for binding_id in (casilla.binding, *casilla.alternate_bindings):
            if binding_id is not None:
                casilla_by_binding.setdefault(str(binding_id), str(casilla.id))
    return casillas, bindings, casilla_by_binding


def _surface_index(
    permitted_surface: tuple[ModeloEditPermittedSurfaceEntryV1, ...] | None, *, filed: bool
) -> dict[tuple[str, str], ModeloEditPermittedSurfaceEntryV1] | None:
    if permitted_surface is None or filed:
        return None
    return {_surface_key(entry): entry for entry in permitted_surface}


def _aeat_data_binding_ids(revision: CalculationRevision | None) -> frozenset[str]:
    if revision is None or caller_context_of(revision).borrador_snapshot_id is None:
        return frozenset[str]()
    return frozenset(str(item) for item in revision.bindings_sourced_from_borrador)


def _export_position_index(
    snapshot: RegistrySnapshot, bindings: dict[str, BindingDefinition]
) -> dict[tuple[str, int], set[str]]:
    casillas_by_export_position: dict[tuple[str, int], set[str]] = {}
    for export_layout in snapshot.revision.export_layouts:
        for record, field in layout_fields_in_emission_order(export_layout):
            target = export_field_casilla_id(record, field, bindings=bindings)
            if target is not None and field.offset is not None:
                for coordinate in (str(record.id), record.record_type):
                    casillas_by_export_position.setdefault((coordinate, field.offset), set()).add(str(target))
    return casillas_by_export_position


def _export_decimal_index(snapshot: RegistrySnapshot, bindings: dict[str, BindingDefinition]) -> dict[str, int]:
    decimals: dict[str, int] = {}
    for layout in snapshot.revision.export_layouts:
        for record, field in layout_fields_in_emission_order(layout):
            target = export_field_casilla_id(record, field, bindings=bindings)
            if target is not None and field.decimals is not None:
                decimals.setdefault(str(target), field.decimals)
    return decimals


class WorkFormContext:
    """Everything one form build reads, indexed once."""

    def export_decimals(self, casilla_id: str) -> int | None:
        """The implied decimals of the export field that emits one casilla, read once per form."""
        if self._export_decimals is None:
            self._export_decimals = _export_decimal_index(self.snapshot, self.bindings)
        return self._export_decimals.get(casilla_id)

    @property
    def box_locators(self) -> tuple[re.Pattern[str], ...]:
        """The modelo's box-locator help sentences, rendered once per form."""
        if self._box_locators is None:
            self._box_locators = render_box_locator_patterns(str(self.snapshot.modelo.id))
        return self._box_locators

    def __init__(
        self,
        *,
        review: ModeloWorkReview,
        snapshot: RegistrySnapshot,
        revision: CalculationRevision | None,
        permitted_surface: tuple[ModeloEditPermittedSurfaceEntryV1, ...] | None,
        entered_casilla_ids: frozenset[CasillaId] | None,
        overridden_binding_ids: frozenset[BindingId] | None,
        language: OutputLanguage,
        unworked_casilla_ids: frozenset[str] = frozenset(),
    ) -> None:
        """Index one work review and its pinned revision for repeated form lookups."""
        self.review = review
        self.unworked = unworked_casilla_ids
        self.language = language
        self.revision = revision
        self.rows, self.fed_casillas = _review_indexes(review)
        self.casillas, self.bindings, self.casilla_by_binding = _registry_indexes(snapshot)
        self.snapshot = snapshot
        self._export_decimals: dict[str, int] | None = None
        self._box_locators: tuple[re.Pattern[str], ...] | None = None
        self.required: frozenset[str] = frozenset(str(item) for item in filer_required_casilla_ids(snapshot.revision))
        self.filed = review.lifecycle_state in _FILED_STATES
        self.surface = _surface_index(permitted_surface, filed=self.filed)
        self.aeat_data_bindings = _aeat_data_binding_ids(revision)
        self.entered = entered_casilla_ids
        self.overridden = overridden_binding_ids
        self.cleared: frozenset[str] = frozenset(
            () if revision is None else (str(item) for item in revision.cleared_casilla_ids)
        )
        self.placed_boxes: dict[str, str] = {}
        self.casillas_by_export_position = _export_position_index(snapshot, self.bindings)


def _surface_key(entry: ModeloEditPermittedSurfaceEntryV1) -> tuple[str, str]:
    if isinstance(entry, (ModeloEditWritableScalarSurfaceEntryV1, ModeloEditNonWritableScalarSurfaceEntryV1)):
        return ("casilla", str(entry.casilla_id))
    if isinstance(
        entry, (ModeloEditWritableBindingOverrideSurfaceEntryV1, ModeloEditNonWritableBindingOverrideSurfaceEntryV1)
    ):
        return ("binding", str(entry.binding_id))
    return (entry.kind, "")
