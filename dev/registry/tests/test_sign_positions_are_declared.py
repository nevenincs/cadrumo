"""A money field starting on a design SIGNO position declares its sign byte.

The screen reads SIGNO subdivisions from each revision's pinned record-design
text. A shipped money field starting on one must declare ``sign_position``,
or a non-negative amount writes a digit where the design reserves a space or
an 'N'.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority

from ..analysis.sign_position_coverage import (
    design_sign_positions,
    screen_authority,
    sign_positions_in_design_text,
    undeclared_sign_positions,
    unreadable_designs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_no_money_field_starts_on_an_undeclared_design_sign_position() -> None:
    undeclared = screen_authority(bundled_authority())

    assert not undeclared, "money fields on a design SIGNO position without sign_position:\n" + "\n".join(
        f"{item.subject} {item.field_id} @{item.offset}" for item in undeclared
    )


def test_every_pinned_design_of_an_exporting_revision_is_read() -> None:
    """A design the screen cannot read would pass its revision on unseen evidence."""
    assert unreadable_designs(bundled_authority()) == ()


def test_every_declared_sign_position_is_printed_by_its_own_design() -> None:
    """The converse: a reserved sign byte needs the design's own SIGNO subdivision.

    It also shows the empty result above means covered, not unseen: every
    declared field is found at a position the screen reads from the design.
    """
    authority = bundled_authority()
    declared = 0
    ungrounded: list[str] = []
    for modelo in authority.modelos:
        for revision in modelo.revisions.values():
            positions = design_sign_positions(authority, revision)
            for layout in revision.export_layouts:
                for record in layout.records:
                    for field in record.fields:
                        if field.sign_position is None:
                            continue
                        declared += 1
                        if field.offset not in positions:
                            ungrounded.append(f"{modelo.id}/{revision.id} {field.id} @{field.offset}")

    assert declared, "no field declares sign_position, so the screen above proves nothing"
    assert not ungrounded, "sign_position declared without a design SIGNO position:\n" + "\n".join(ungrounded)


def test_design_text_positions_are_read_from_each_printed_subdivision() -> None:
    text = (
        "145 SIGNO: campo alfabetico que se cumplimentara ...\n"
        "146- 167 IMPORTE: Campo numerico ...\n"
        "176. SIGNO: Campo alfabetico: se consignara siempre una 'N'\n"
        'campo "SIGNO DE LA VALORACION" (posicion 108 del registro de tipo 2)\n'
    )

    assert sign_positions_in_design_text(text) == frozenset({145, 176})


def test_a_planted_money_field_on_a_sign_position_is_reported_and_others_are_not() -> None:
    fields = [
        ("undeclared-amount", 145, "money", None),
        ("declared-amount", 176, "money", "blank_or_n"),
        ("text-on-sign-offset", 145, "text", None),
        ("amount-elsewhere", 200, "money", None),
    ]

    assert undeclared_sign_positions(fields, frozenset({145, 176})) == [("undeclared-amount", 145)]
