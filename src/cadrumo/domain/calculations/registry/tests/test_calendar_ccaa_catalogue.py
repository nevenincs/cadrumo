"""Tax-residence to deadline-calendar territory relation in the published catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ..calendar_ccaa_catalogue import _catalogue, _resolve_entries, resolve_calendar_ccaa_catalogue
from ..ccaa_catalogue import resolve_ccaa_catalogue
from ..errors import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EFFECTIVE = date(2026, 4, 1)

# ISO 3166-2:ES subdivision codes of the fifteen common-regime communities,
# written out independently of the registry so the relation is checked against
# the standard rather than against itself.
_ISO_3166_2_ES = {
    "andalucia": "ES-AN",
    "aragon": "ES-AR",
    "asturias": "ES-AS",
    "baleares": "ES-IB",
    "canarias": "ES-CN",
    "cantabria": "ES-CB",
    "castilla_la_mancha": "ES-CM",
    "castilla_y_leon": "ES-CL",
    "cataluna": "ES-CT",
    "comunidad_valenciana": "ES-VC",
    "extremadura": "ES-EX",
    "galicia": "ES-GA",
    "la_rioja": "ES-RI",
    "madrid": "ES-MD",
    "murcia": "ES-MC",
}


def _published_entries() -> dict[str, str]:
    with bundled_indexed_authority().operation() as operation:
        return dict(_resolve_entries(effective_date=_EFFECTIVE, authority=operation))


def test_every_declared_tax_residence_relates_to_its_iso_territory() -> None:
    with bundled_indexed_authority().operation() as operation:
        residences = resolve_ccaa_catalogue(effective_date=_EFFECTIVE, authority=operation).choices
        calendar = resolve_calendar_ccaa_catalogue(effective_date=_EFFECTIVE, authority=operation)

    assert {str(token) for token in residences} == set(_ISO_3166_2_ES)
    related = {str(token): str(calendar.territory_for_tax_residence(str(token))) for token in residences}
    assert related == _ISO_3166_2_ES


def test_names_that_differ_between_vocabularies_still_relate() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = resolve_calendar_ccaa_catalogue(effective_date=_EFFECTIVE, authority=operation)

    assert calendar.definition(calendar.territory_for_tax_residence("baleares")).member_name == "ILLES_BALEARS"
    assert calendar.definition(calendar.territory_for_tax_residence("comunidad_valenciana")).member_name == "VALENCIA"


def test_unknown_tax_residence_is_refused_rather_than_mapped() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = resolve_calendar_ccaa_catalogue(effective_date=_EFFECTIVE, authority=operation)

    with pytest.raises(RegistryValidationError):
        calendar.territory_for_tax_residence("navarra")


def _without(entries: Mapping[str, str], key: str) -> dict[str, str]:
    return {name: value for name, value in entries.items() if name != key}


def test_published_entries_project_cleanly() -> None:
    assert len(_catalogue(_published_entries()).tax_residence_territories) == len(_ISO_3166_2_ES)


def test_incomplete_relation_is_rejected() -> None:
    entries = _without(_published_entries(), "calendar_ccaa.relation.tax_residence.murcia")

    with pytest.raises(RegistryValidationError, match="common-regime count"):
        _catalogue(entries)


def test_relation_to_an_autonomous_city_is_rejected() -> None:
    entries = _published_entries() | {"calendar_ccaa.relation.tax_residence.murcia": "ES-CE"}

    with pytest.raises(RegistryValidationError, match="not a declared autonomous community"):
        _catalogue(entries)


def test_two_residences_on_one_territory_are_rejected() -> None:
    entries = _published_entries() | {"calendar_ccaa.relation.tax_residence.murcia": "ES-MD"}

    with pytest.raises(RegistryValidationError, match="two residences"):
        _catalogue(entries)
