"""The listed export fields are held red while they carry another page's casilla identity."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.export_parse_models import ParsedExportFieldValue

from ..export_carriers import KNOWN_FOREIGN_CARRIERS, cross_page_reuse_mismatches, foreign_carrier_mismatches

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_EDITION = "m200-edition"


def _field(cell: str, casilla: str | None) -> ParsedExportFieldValue:
    page = cell.partition(".")[0]
    return ParsedExportFieldValue.model_validate(
        {
            "record_id": f"m200-{page}",
            "field_id": f"{_EDITION}.{cell}",
            "casilla_id": casilla,
            "raw": "0",
            "value": "0",
            "source_locator": cell,
        }
    )


def test_each_listed_field_carrying_the_named_casilla_is_reported_with_its_owner() -> None:
    parsed = [_field(item.cell, item.casilla) for item in KNOWN_FOREIGN_CARRIERS]
    found = foreign_carrier_mismatches("200", parsed)
    assert found == [
        "DP200032 f92 carries casilla DP200010:00524 of DP200010 f80",
        "DP200043 f54 carries casilla DP200010:00524 of DP200010 f80",
        "DP200043 f55 carries casilla DP200010:00525 of DP200010 f81",
        "DP200043 f56 carries casilla DP200010:00526 of DP200010 f82",
    ]


def test_the_owner_cell_and_a_listed_cell_with_its_own_identity_are_not_reported() -> None:
    parsed = [
        _field("dp200010.f0080", "DP200010:00524"),
        _field("dp200032.f0092", "DP200032:00524"),
        _field("dp200043.f0054", None),
        _field("dp200043.f0055", "DP200010:00524"),
        _field("dp200043.f0056", "DP200043:00526"),
    ]
    assert foreign_carrier_mismatches("200", parsed) == []


def test_another_modelo_is_not_held_to_the_listed_cells() -> None:
    parsed = [_field("dp200032.f0092", "DP200010:00524")]
    assert foreign_carrier_mismatches("303", parsed) == []


_UNADJUDICATED = ["00524"]


def test_an_identity_the_registry_leaves_unadjudicated_and_bound_on_two_pages_is_counted_once() -> None:
    parsed = [
        _field("dp200032.f0092", "00524"),
        _field("dp200043.f0054", "00524"),
        _field("dp200010.f0001", "00001"),
        _field("dp200010.f0002", "00001"),
        _field("dp200012.f0004", None),
    ]
    assert cross_page_reuse_mismatches(_UNADJUDICATED, parsed) == [
        "1 casilla identities are bound on more than one page (first 00524), not declared as repeats by the registry"
    ]


def test_a_repeat_the_registry_declares_is_not_reported() -> None:
    parsed = [_field("dp200010.f0080", "00524"), _field("dp200032.f0092", "00524")]
    assert cross_page_reuse_mismatches([], parsed) == []


def test_an_unadjudicated_identity_written_on_one_page_only_is_not_reported() -> None:
    parsed = [_field("dp200010.f0080", "00524"), _field("dp200010.f0081", "00524")]
    assert cross_page_reuse_mismatches(_UNADJUDICATED, parsed) == []
