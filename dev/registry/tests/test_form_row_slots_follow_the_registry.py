"""The row counts domain models read must be the rows each Modelo 303 revision declares."""

from __future__ import annotations

import re

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROJECTED_ROW = re.compile(r'projection_kind = "(?P<kind>\w+)"\s+slot = (?P<slot>\d+)')


def _declared_slots_by_revision(kind: str) -> dict[str, int]:
    revisions = bundled_path("registry", "aeat", "modelos", "303", "revisions")
    declared: dict[str, int] = {}
    for revision in revisions.iterdir():
        slots = [
            int(match["slot"])
            for path in revision.rglob("*.toml")
            for match in _PROJECTED_ROW.finditer(path.read_text(encoding="utf-8"))
            if match["kind"] == kind
        ]
        if slots:
            declared[revision.name] = max(slots)
    return declared


@pytest.mark.parametrize(
    ("key", "kind"),
    [
        ("m303.differentiated.row_slots", "m303_differentiated_deduction"),
        ("m303.prorrata.activity_slots", "m303_prorrata_activity"),
        ("m303.exonerado_390.activity_slots", "m303_exonerado_390_activity"),
    ],
)
def test_the_row_count_fact_is_what_every_revision_declares(key: str, kind: str) -> None:
    payload = compiled_bundled_authority().catalogues.facts.facts["form-row-codes"].variants[0].payload
    entries = {entry.key: entry.value for entry in payload.entries}

    declared = _declared_slots_by_revision(kind)

    assert declared
    assert set(declared.values()) == {int(entries[key])}
