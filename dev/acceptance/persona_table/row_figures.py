"""The figures a return's one row per property holds, which the public calculation prints only as column totals.

A casilla of a repeated row group (a let property's rendimientos) is stored per row, not as one scalar, so
the calculation's casilla values cannot answer for it. Where the return holds exactly one row, that row's
figure is the casilla's figure; with several rows no single figure answers, so none is given and a stated
amount stays unmet instead of passing on one row. A row figure fills a casilla only where the public scalar
is zero or absent: a nonzero scalar that differs from the row figure is a conflict, never overridden.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from cadrumo.application.modelo.work_calculation_contracts import ModeloWorkCalculatePublicResultV3
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.renta_inmueble_bindings import renta_inmueble_columns
from cadrumo.domain.calculations.registry.schema_form_layouts import FormPlacementKind
from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports
from cadrumo.entrypoints.tests.persona_materialisation import PersonaWorld


def single_row_figures(
    row_binding_values: Mapping[str, Mapping[str, object]], target_casillas: Mapping[str, str]
) -> Mapping[str, str]:
    """The figure of each fed casilla held by exactly one row, by casilla id; unfed bindings are ignored."""
    figures: dict[str, str] = {}
    for binding_id, rows in row_binding_values.items():
        if binding_id not in target_casillas or len(rows) != 1:
            continue
        (value,) = rows.values()
        figures[target_casillas[binding_id]] = str(value)
    return figures


def _amount(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def merge_row_figures(scalars: Mapping[str, object], rows: Mapping[str, str]) -> tuple[dict[str, object], list[str]]:
    """The scalars with each row figure filled where the scalar is zero or absent, and every conflict as text.

    A conflict is a nonzero scalar that differs from the row figure of the same casilla; the scalar stays.
    """
    merged = dict(scalars)
    conflicts: list[str] = []
    for casilla, figure in rows.items():
        scalar = scalars.get(casilla)
        known = None if scalar is None else _amount(scalar)
        if scalar is None or known == 0:
            merged[casilla] = figure
        elif known != _amount(figure):
            conflicts.append(f"casilla {casilla} scalar {scalar} differs from its row figure {figure}")
    return merged, conflicts


def row_figures(world: PersonaWorld, calculated: ModeloWorkCalculatePublicResultV3) -> Mapping[str, str]:
    """The stored figure of each casilla a let-property column feeds, from the single row, by casilla id."""
    ports = build_calculation_action_ports(bucket_id=str(world.profile_id), operation=world.operation)
    stored = ports.calculation_repository.load().get(calculated.calculation_revision_id)
    if stored is None:
        return single_row_figures({}, {})
    revision = world.operation.revision(str(calculated.unit.modelo), calculated.unit.revision_id)
    fed = {binding.id: str(provider.target_casilla_id) for binding, provider in renta_inmueble_columns(revision)}
    return single_row_figures(stored.row_binding_values, fed)


def on_form_casillas(operation: PinnedAuthorityOperation, modelo: str, revision_id: str) -> frozenset[str] | None:
    """The casillas the revision places at an official position on its form, or ``None`` without a layout.

    The form layout declares for every casilla whether it is ``on_form``, an application ``working_figure`` the
    official form does not print, or ``unplaced``; only an ``on_form`` casilla is a box a surface can show.
    """
    layout = operation.form_layout(modelo, revision_id)
    if layout is None:
        return None
    return frozenset(
        str(placement.casilla_id) for placement in layout.placements if placement.kind is FormPlacementKind.ON_FORM
    )


def split_figures(
    figures: tuple[tuple[str, str], ...], on_form: frozenset[str] | None
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    """The ``figures`` on the form and, apart, those it does not place; all are on the form without a layout."""
    if on_form is None:
        return figures, ()
    shown = tuple(item for item in figures if item[0] in on_form)
    return shown, tuple(item for item in figures if item[0] not in on_form)


__all__ = ["merge_row_figures", "on_form_casillas", "row_figures", "single_row_figures", "split_figures"]
