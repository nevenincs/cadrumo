"""Deadline-calendar territory catalogue in the published authority."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ..calendar_ccaa_catalogue import ENTRIES_FACT, catalogue, resolve_calendar_ccaa_catalogue
from ..errors import RegistryValidationError
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EFFECTIVE = date(filing_year_envelope().horizon, 4, 1)

# ISO 3166-2:ES subdivision codes of the fifteen common-regime communities, the
# two foral communities and the two autonomous cities, written out independently
# of the registry so the catalogue is checked against the standard.
_ISO_3166_2_ES = (
    "ES-AN",
    "ES-AR",
    "ES-AS",
    "ES-IB",
    "ES-CN",
    "ES-CB",
    "ES-CM",
    "ES-CL",
    "ES-CT",
    "ES-EX",
    "ES-GA",
    "ES-RI",
    "ES-MD",
    "ES-MC",
    "ES-NC",
    "ES-PV",
    "ES-VC",
    "ES-CE",
    "ES-ML",
)


def _published_entries() -> dict[str, str]:
    with bundled_indexed_authority().operation() as operation:
        return dict(ENTRIES_FACT.resolve_scoped_entries(effective_date=_EFFECTIVE, authority=operation))


def test_catalogue_declares_every_iso_territory_in_order() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = resolve_calendar_ccaa_catalogue(effective_date=_EFFECTIVE, authority=operation)

    assert tuple(str(token) for token in calendar.choices) == _ISO_3166_2_ES


def test_member_names_that_differ_from_the_tax_residence_vocabulary_project() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = resolve_calendar_ccaa_catalogue(effective_date=_EFFECTIVE, authority=operation)

    assert calendar.definition("ES-IB").member_name == "ILLES_BALEARS"
    assert calendar.definition("ES-VC").member_name == "VALENCIA"
    assert calendar.definition("ES-CE").territory_kind == "autonomous_city"
    assert calendar.definition("ES-NC").territory_kind == "foral_territory"


def test_undeclared_territory_code_is_refused() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = resolve_calendar_ccaa_catalogue(effective_date=_EFFECTIVE, authority=operation)

    with pytest.raises(RegistryValidationError):
        calendar.require("ES-XX")


def _with(entries: Mapping[str, str], key: str, value: str) -> dict[str, str]:
    return {**entries, key: value}


def test_published_entries_project_cleanly() -> None:
    assert len(catalogue(_published_entries()).definitions) == len(_ISO_3166_2_ES)


def test_territory_count_that_disagrees_with_the_order_is_rejected() -> None:
    entries = _with(_published_entries(), "calendar_ccaa.relation.calendar_territory_count", "18")

    with pytest.raises(RegistryValidationError, match="does not match"):
        catalogue(entries)
