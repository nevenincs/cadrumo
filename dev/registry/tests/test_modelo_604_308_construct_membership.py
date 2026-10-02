"""Modelo 604 2024 and Modelo 308 2019 constructs gather every member their edition declares.

Each edition declares one construct for the whole return. Its member lists must
name every casilla the edition's record design lays out and every deadline
window, application link, export layout and parity anchor the edition carries,
so a member added to the edition without joining the construct is caught here.
"""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_revision_members import ConstructDefinition

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Construct member list and the edition family whose member ids it must cover.
_MEMBER_FAMILIES = (
    ("casilla_ids", "casillas"),
    ("application_links", "application_links"),
    ("deadline_windows", "deadline_windows"),
    ("export_layouts", "export_layouts"),
    ("workbook_parity_refs", "workbook_parity_refs"),
    ("filing_schedules", "filing_schedules"),
    ("live_cross_references", "live_cross_references"),
)


def _missing_members(revision: ModeloRevision, construct: ConstructDefinition) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for attribute, family in _MEMBER_FAMILIES:
        declared = [str(member.id) for member in getattr(revision, family)]
        joined = set(getattr(construct, attribute))
        absent = [member_id for member_id in declared if member_id not in joined]
        if absent:
            missing[attribute] = absent
    return missing


def _sole_construct(modelo_id: str, revision_id: str) -> tuple[ModeloRevision, ConstructDefinition]:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", modelo_id))
    revision = modelo.revisions[revision_id]
    (construct,) = revision.constructs
    return revision, construct


@pytest.mark.parametrize(
    ("modelo_id", "revision_id"),
    [("604", "2024-y-siguientes"), ("308", "2019-y-siguientes")],
)
def test_the_return_construct_joins_every_member_of_its_edition(modelo_id: str, revision_id: str) -> None:
    revision, construct = _sole_construct(modelo_id, revision_id)

    assert revision.casillas, "the edition must declare the casillas its record design lays out"
    assert _missing_members(revision, construct) == {}


def test_a_member_left_out_of_the_construct_is_reported() -> None:
    revision, construct = _sole_construct("604", "2024-y-siguientes")
    windows = construct.deadline_windows
    truncated = construct.model_copy(update={"deadline_windows": windows[1:], "export_layouts": ()})

    assert _missing_members(revision, truncated) == {
        "deadline_windows": [str(windows[0])],
        "export_layouts": [str(layout.id) for layout in revision.export_layouts],
    }
