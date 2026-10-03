"""Profile search matches the way every other search does: without case or accents."""

from __future__ import annotations

import pytest

from .....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from .....domain.user_profile.values import ProfileSetupState
from ..overview import ProfileManagerScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = "00000000-0000-4000-8000-0000000000a1"


def _field(path: str, label: str, value: str | None) -> ProfileFieldView:
    return ProfileFieldView(path=path, label=label, value=value, masked=False, required=False)


def _overview() -> tuple[ProfileOverview, ProfileSectionView]:
    section = ProfileSectionView(
        key="domicilio",
        title="Domicilio fiscal",
        summary="Dónde recibes las notificaciones",
        repeatable=False,
        fields=(
            _field("domicilio.municipio", "Municipio", "Málaga"),
            _field("domicilio.provincia", "Provincia", "Sevilla"),
        ),
    )
    overview = ProfileOverview(
        profile_id=_PROFILE,
        record_revision=1,
        content_digest="a" * 64,
        label="Profile",
        setup_state=ProfileSetupState.COMPLETE,
        sections=(section,),
    )
    return overview, section


def _visible_paths(query: str) -> set[str]:
    overview, section = _overview()
    screen = ProfileManagerScreen(overview, persist=lambda *_args: overview)
    screen._query = query
    return {field.path for field in screen._visible_fields(overview, section)}


@pytest.mark.parametrize("query", ["Málaga", "malaga", "MALAGA", "mAlAgA", "  malaga  "])
def test_a_row_is_found_by_its_value_whatever_the_accent_or_case_typed(query: str) -> None:
    assert _visible_paths(query) == {"domicilio.municipio"}


@pytest.mark.parametrize("query", ["donde recibes", "DÓNDE", "domicilio", "FISCAL"])
def test_a_search_naming_the_section_keeps_all_of_its_rows(query: str) -> None:
    assert _visible_paths(query) == {"domicilio.municipio", "domicilio.provincia"}


def test_a_search_that_matches_nothing_keeps_no_row() -> None:
    assert _visible_paths("zzqx") == set()
