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


def _entries() -> dict[str, str]:
    payload = compiled_bundled_authority().catalogues.facts.facts["form-row-codes"].variants[0].payload
    return {entry.key: entry.value for entry in payload.entries}


def _all_field_values(name: str) -> dict[str, set[int]]:
    revisions = bundled_path("registry", "aeat", "modelos", "303", "revisions")
    pattern = re.compile(rf"^{name} = (\d+)", re.MULTILINE)
    found: dict[str, set[int]] = {}
    for revision in revisions.iterdir():
        values = {
            int(match)
            for path in revision.rglob("*.toml")
            if "regimen" in path.name
            for match in pattern.findall(path.read_text(encoding="utf-8"))
        }
        if values:
            found[revision.name] = values
    return found


def test_the_sub_indices_are_what_the_later_editions_declare() -> None:
    declared = _all_field_values("sub_index")

    assert declared
    assert all(
        values == {int(code) for code in _entries()["m303.dp30302.sub_indices"].split(",")}
        for values in declared.values()
    )


def test_the_module_rows_are_what_every_edition_declares() -> None:
    declared = _all_field_values("module_order")

    assert declared
    assert {max(values) for values in declared.values()} == {int(_entries()["m303.orden.modules_per_activity"])}


def test_a_page_holds_the_activities_every_edition_declares_and_the_pages_make_the_limit() -> None:
    entries = _entries()
    declared = _declared_slots_by_revision("m303_regimen_simplificado_activity")

    assert set(declared.values()) == {int(entries["m303.dp30302.activities_per_record"])}
    assert int(entries["m303.dp30302.activities_per_record"]) * int(entries["m303.dp30302.records"]) == int(
        entries["m303.dp30302.activities_per_kind"]
    )


def test_the_epigraph_digits_fill_the_field_the_record_declares() -> None:
    entries = _entries()
    revisions = bundled_path("registry", "aeat", "modelos", "303", "revisions")
    field = re.compile(r'length = (\d+)(?:(?!\[\[).)*?field = "iae_epigrafe"', re.DOTALL)
    lengths = {
        int(match)
        for revision in revisions.iterdir()
        for path in revision.rglob("*regimen*.toml")
        for match in field.findall(path.read_text(encoding="utf-8"))
    }

    assert lengths == {
        int(entries["m303.dp30302.iae_whole_digits"]) + int(entries["m303.dp30302.iae_fractional_digits"])
    }
