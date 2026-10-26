"""The cross-period wire-shape diagnostic detects a change and reports its reach."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..analysis.cross_revision_wire_shape import cross_revision_wire_shape_transitions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _write_revision(root: Path, modelo: str, revision: str, fields: tuple[dict[str, object], ...]) -> None:
    export = root / modelo / "revisions" / revision / "export"
    export.mkdir(parents=True)
    derivations = []
    for original in fields:
        field = dict(original)
        casilla = field.pop("casilla_id", "17")
        derivations.append(
            {
                "field": field,
                "parser_field": {
                    "aeat_type": field.pop("aeat_type", "Num"),
                    "content": field.pop("content", "3 enteros y 2 decimales"),
                },
                "semantic_entry": {"casilla_id": casilla},
            },
        )
    (export / "_generation.provenance.json").write_text(
        json.dumps({"field_derivations": derivations}),
        encoding="utf-8",
    )


def test_a_planted_wire_shape_change_is_reported(tmp_path: Path) -> None:
    """A field that changes shape between revisions is a suspect, and is named."""
    stable = {"id": "modelo-999-page-01-cuota", "data_type": "money", "length": 17, "signed": True, "decimals": None}
    moved = {**stable, "signed": False, "data_type": "decimal", "decimals": 2}
    _write_revision(tmp_path, "999", "2025", (dict(stable),))
    _write_revision(tmp_path, "999", "2026", (dict(moved),))

    transitions = tuple(cross_revision_wire_shape_transitions(tmp_path))

    assert len(transitions) == 1
    assert transitions[0].casilla_id == "17"
    assert transitions[0].earlier_revision == "2025"
    assert transitions[0].later_revision == "2026"


def test_an_unchanged_field_is_not_reported(tmp_path: Path) -> None:
    """Agreement is reported as nothing, so the screen cannot fire on stability."""
    field = {"id": "modelo-999-page-01-cuota", "data_type": "money", "length": 17, "signed": True, "decimals": None}
    _write_revision(tmp_path, "999", "2025", (dict(field),))
    _write_revision(tmp_path, "999", "2026", (dict(field),))

    assert not tuple(cross_revision_wire_shape_transitions(tmp_path))


def test_a_change_the_design_accounts_for_is_marked_as_such(tmp_path: Path) -> None:
    """A design that moved is a different thing from a design that stayed silent.

    The design states shape TWICE - the type column and the content cell - and
    comparing only the type column called one real transition unexplained that
    the design accounts for plainly: a rate whose content moved from a scaled
    decimal to an enumeration of permitted digit strings, while its type column
    said Num throughout.
    """
    earlier = {
        "id": "modelo-999-page-01-cuota",
        "data_type": "decimal",
        "length": 17,
        "signed": False,
        "decimals": 2,
        "aeat_type": "Num",
    }
    later = {**earlier, "data_type": "money", "signed": True, "decimals": None, "aeat_type": "N"}
    _write_revision(tmp_path, "999", "2025", (dict(earlier),))
    _write_revision(tmp_path, "999", "2026", (dict(later),))

    transition = next(iter(cross_revision_wire_shape_transitions(tmp_path)))

    assert transition.official_statement_changed


def test_a_field_carrying_no_casilla_is_not_compared(tmp_path: Path) -> None:
    """The casilla number is the identity; a slot that carries none has none.

    Fillers, headers and literals occupy the record without standing for a
    casilla, so there is nothing to follow across revisions and comparing them
    positionally would be a coordinate join.
    """
    field = {"id": "modelo-999-page-01-filler", "data_type": "text", "length": 3, "signed": False, "decimals": None}
    _write_revision(tmp_path, "999", "2025", ({**field, "casilla_id": None},))
    _write_revision(tmp_path, "999", "2026", ({**field, "casilla_id": None, "length": 9},))

    assert not tuple(cross_revision_wire_shape_transitions(tmp_path))
