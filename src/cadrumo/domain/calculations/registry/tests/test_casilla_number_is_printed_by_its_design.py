"""A casilla's box number is the key that binds it to its design field, where AEAT prints one.

Four registry revisions are waiting on a fixed-width layout, and authoring one
means deciding which design field each casilla occupies. The cheap way to decide
is by description similarity, which the grounding rule forbids as a route to box
identity. The sound way is AEAT's own printed box number: the diseño tags a field
``[920]`` and the casilla declares ``number = "920"``, and nothing is inferred.

MEASURED, so a future authoring tick knows which modelos that key actually
covers::

    modelo 840 / 2003-y-siguientes   108 digit-numbered casillas, 108 matched
    modelo 390 / 2021                  9                          9
    modelo 220 / 2024               1065                       1065
    modelo 036 / 2025-02-03-y-sig.   304                        286

Three are total. Modelo 036 is not, and the eighteen it misses are not scattered:
they are six sucesor groups of three. Its design tags ONLY the N.I.F. of each
group -- ``[920]``, ``[924]``, ``[928]``, ``[932]``, ``[936]``, ``[940]`` -- and
prints no number on that group's apellidos, percentage or cuota fields. The
registry numbers those three tagged+1, +2 and +3, uniformly across all six
groups.

THAT INFERENCE MAY WELL BE RIGHT, and this module does not claim otherwise. It
records that the numbers are NOT evidenced by the cited diseño, so an authoring
pass that uses the box number as its key must treat those eighteen differently
from the 286 the design actually prints -- and so that a later reader does not
discover the gap by writing a layout on top of it.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.record_design import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TAG = re.compile(r"\[(\d+)\]")

#: revision -> the design it cites, for the revisions waiting on a layout.
_AWAITING_LAYOUT = {
    ("840", "2003-y-siguientes"): "aeat-dr-840",
    ("390", "2021"): "aeat-dr-390-2021",
    ("220", "2024"): "aeat-dr-220-2024",
}

_MODELO_036 = ("036", "2025-02-03-y-siguientes", "aeat-dr-036-2025")

#: The one N.I.F. box AEAT prints per sucesor group on modelo 036's page 9.
_SUCESOR_TAGGED = frozenset({"920", "924", "928", "932", "936", "940"})


def _design_box_numbers(source_ref: str) -> frozenset[str]:
    _modelos, catalogues = _committed_registry_tree()
    design = extract_record_design(bundled_path() / catalogues.sources[source_ref].corpus_path)
    numbers: set[str] = set()
    for sheet in design.sheets:
        for field in sheet.fields:
            for text in (field.description, field.validation, field.content):
                if text:
                    numbers |= set(_TAG.findall(text))
    return frozenset(numbers)


def _numbered_casillas(modelo_id: str, revision_id: str):
    modelo = next(m for m in bundled_authority().modelos if m.id == modelo_id)
    revision = modelo.revisions[revision_id]
    return {c.number for c in revision.casillas if c.number and c.number.isdigit()}


@pytest.mark.parametrize(("target", "source_ref"), sorted(_AWAITING_LAYOUT.items()))
def test_every_numbered_casilla_is_printed_by_its_cited_design(target: tuple[str, str], source_ref: str) -> None:
    """The key, proved total on the modelos where it is total.

    If this ever fails, a layout authored on the box number would silently place
    a casilla by inference, which is what the grounding rule refuses.
    """
    modelo_id, revision_id = target
    numbered = _numbered_casillas(modelo_id, revision_id)
    printed = _design_box_numbers(source_ref)

    assert numbered, f"{modelo_id}/{revision_id} declares no digit-numbered casilla"
    missing = sorted(numbered - printed, key=int)

    assert not missing, f"{modelo_id}/{revision_id} declares box number(s) its design does not print: {missing[:12]}"


def test_modelo_036_misses_exactly_the_untagged_sucesor_fields() -> None:
    """The one exception, pinned as a shape rather than a tally.

    Every missing number is one, two or three above a number the design DOES
    print on a sucesor group, and every such base is a sucesor N.I.F. box. A
    missing number that fitted no group would be a different problem and fails
    here.
    """
    modelo_id, revision_id, source_ref = _MODELO_036
    numbered = _numbered_casillas(modelo_id, revision_id)
    printed = _design_box_numbers(source_ref)

    missing = sorted(numbered - printed, key=int)
    assert missing, "modelo 036 no longer infers any box number; this module is stale"

    assert printed >= _SUCESOR_TAGGED, sorted(_SUCESOR_TAGGED - printed)

    unexplained = [
        number for number in missing if not any(str(int(number) - offset) in _SUCESOR_TAGGED for offset in (1, 2, 3))
    ]
    assert not unexplained, f"these inferred box numbers sit beside no printed sucesor N.I.F. box: {unexplained}"


def test_the_inferred_numbers_are_all_sucesor_casillas() -> None:
    """The other half: the shape is a property of the casillas, not just the arithmetic."""
    modelo_id, revision_id, source_ref = _MODELO_036
    modelo = next(m for m in bundled_authority().modelos if m.id == modelo_id)
    revision = modelo.revisions[revision_id]
    printed = _design_box_numbers(source_ref)

    inferred = [c for c in revision.casillas if c.number and c.number.isdigit() and c.number not in printed]

    assert inferred
    for casilla in inferred:
        assert str(casilla.id).startswith("suc-"), str(casilla.id)
