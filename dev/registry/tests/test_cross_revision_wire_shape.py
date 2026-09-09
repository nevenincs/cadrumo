"""The cross-period wire-shape diagnostic detects a change and reports its reach."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..analysis.cross_revision_wire_shape import (
    cross_revision_wire_shape_transitions,
    identity_is_comparable_across_revisions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _write_revision(root: Path, modelo: str, revision: str, fields: tuple[dict[str, object], ...]) -> None:
    export = root / modelo / "revisions" / revision / "export"
    export.mkdir(parents=True)
    derivations = [
        {"field": field, "parser_field": {"aeat_type": field.pop("aeat_type", "Num")}} for field in map(dict, fields)
    ]
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
    assert transitions[0].export_field_id == "modelo-999-page-01-cuota"
    assert transitions[0].earlier_revision == "2025"
    assert transitions[0].later_revision == "2026"


def test_an_unchanged_field_is_not_reported(tmp_path: Path) -> None:
    """Agreement is reported as nothing, so the screen cannot fire on stability."""
    field = {"id": "modelo-999-page-01-cuota", "data_type": "money", "length": 17, "signed": True, "decimals": None}
    _write_revision(tmp_path, "999", "2025", (dict(field),))
    _write_revision(tmp_path, "999", "2026", (dict(field),))

    assert not tuple(cross_revision_wire_shape_transitions(tmp_path))


def test_a_change_the_official_column_accounts_for_is_marked_as_such(tmp_path: Path) -> None:
    """A design that moved is a different thing from a design that stayed silent."""
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

    assert transition.official_type_changed


def test_a_positionally_numbered_identity_is_not_compared() -> None:
    """An ordinal assigned per render does not name the same slot twice.

    Joining on it lifted the compared population from 1,628 to 5,223 and
    manufactured 745 transitions that are overwhelmingly renumbering. That is a
    coordinate join, and this corpus has already produced one confident number
    that way which proved to be noise.
    """
    assert identity_is_comparable_across_revisions("modelo-390-page-01-declared-representante")
    assert not identity_is_comparable_across_revisions("m151-2015.did.f006")
    assert not identity_is_comparable_across_revisions("m303-2024.pagina02.f011")
