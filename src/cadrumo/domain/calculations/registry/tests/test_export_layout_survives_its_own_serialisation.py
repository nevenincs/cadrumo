"""Every committed export layout must be readable from its own dump.

An :class:`ExportLayoutDefinition` is a persisted registry model: it is written,
read back, and reconstructed by every surface that copies a layout to adjust one
field. A model whose own ``model_dump()`` its validator rejects cannot do that,
and the failure is invisible until something actually tries -- which is how this
went unnoticed. Seven of the tree's eighty-six layouts were in that state:
Modelo 200's ``2024-y-siguientes`` and all six Modelo 303 revisions, every one of
them a layout carrying ``projection_ref`` fields.

The cause was an exact-type guard in the projection-reference compiler refusing
anything that is not literally ``str``. A ``StrEnum`` member is not, although its
value IS the wire primitive, and a python-mode dump emits members -- so a
reference could not survive its own serialisation. :mod:`cadrumo.core` carries
the unit proof for the narrowing and for the guards it did NOT loosen; this
module is the real-data half, because a compiler fix that satisfied a
constructed reference while some committed layout still failed would be a fix
proven against the wrong thing.

Asserted as STRICT EQUALITY rather than "does not raise": a validator that
stopped refusing while dropping a field would pass the weaker form.
"""

from __future__ import annotations

import pytest

from .. import ExportLayoutDefinition
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _committed_layouts() -> list[tuple[str, str, ExportLayoutDefinition]]:
    modelos, _catalogues = _committed_registry_tree()
    return [
        (modelo.id, revision_id, layout)
        for modelo in modelos
        for revision_id, revision in modelo.revisions.items()
        for layout in revision.export_layouts
    ]


def test_every_committed_export_layout_reconstructs_from_its_own_dump() -> None:
    layouts = _committed_layouts()
    assert layouts, "no export layout is committed, so this roundtrip proves nothing"

    failures: list[str] = []
    unequal: list[str] = []
    for modelo_id, revision_id, layout in layouts:
        try:
            restored = ExportLayoutDefinition.model_validate(layout.model_dump())
        except Exception as error:
            failures.append(f"{modelo_id}/{revision_id}: {type(error).__name__}")
            continue
        if restored != layout:
            unequal.append(f"{modelo_id}/{revision_id}")

    assert not failures, f"these layouts cannot be re-validated from their own dump: {failures}"
    assert not unequal, f"these layouts lost or changed a field across their own dump: {unequal}"


def test_the_roundtrip_actually_exercises_projection_references() -> None:
    """The population must still contain the shape that broke, or this is vacuous.

    Most layouts carry no projection field and would roundtrip under the old
    guard too. If projections leave the tree, this pair should be re-anchored on
    whatever typed value replaced them rather than left passing on the easy case.
    """
    with_projections = [
        f"{modelo_id}/{revision_id}"
        for modelo_id, revision_id, layout in _committed_layouts()
        if any(
            getattr(field, "projection_ref", None) is not None for record in layout.records for field in record.fields
        )
    ]
    assert with_projections, (
        "no committed layout declares a projection_ref, so the roundtrip above no "
        "longer covers the case it was written for"
    )


def test_a_dumped_layout_still_carries_typed_projection_members() -> None:
    """The dump must keep emitting enum members, which is what the guard tripped on.

    Were pydantic to start emitting plain strings in python mode, the roundtrip
    would pass for a reason unrelated to the narrowing, and this says so.
    """
    from enum import StrEnum

    for _modelo_id, _revision_id, layout in _committed_layouts():
        for record in layout.records:
            for field in record.fields:
                reference = getattr(field, "projection_ref", None)
                if reference is None:
                    continue
                dumped = reference.model_dump()
                if any(isinstance(value, StrEnum) for value in dumped.values()):
                    return
    pytest.fail(
        "no dumped projection reference emits a StrEnum member any more; the "
        "narrowing in compile_filing_projection_ref may now be unreachable"
    )
