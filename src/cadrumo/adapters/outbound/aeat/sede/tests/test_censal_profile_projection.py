"""Census consulta pages, parsed by the real readers, projected onto profile paths."""

from __future__ import annotations

from datetime import date

import pytest

from ......application.user_profile.censal_observation import CensalObservation
from ......application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS, censal_facts_from_read
from ......domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ......tests.aeat_literal_fixtures import aeat_url
from ......tests.inventory import FIXTURES_DIR
from ..censal_datos import parse_censal_datos
from ..censal_tables import parse_censal_table
from .censal_consultation_fixtures import ACTIVITIES_HTML, ACTIVITY_START

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_CONSULTA = FIXTURES_DIR / "aeat-sede" / "censal-datos-mdcacceso.html"
_ACTIVITY_COLUMNS = ("Sección", "Epígrafe", "Denominación", "Estado", "F.Inicio", "F.Baja", "Locales", "Num.Ref.")


def _consulta(*activity_pages: str) -> CensalObservation:
    observation = parse_censal_datos(_CONSULTA.read_text(encoding="utf-8"), source_url=aeat_url("sede", "/censo"))
    consultations = tuple(
        parse_censal_table(page, kind="actividades", source_url=aeat_url("sede", "/actividades"))
        for page in activity_pages
    )
    return observation.model_copy(update={"consultations": consultations})


def _activities(*rows: tuple[str, str]) -> str:
    """One activities page whose rows carry the given (F.Inicio, F.Baja)."""
    body = "".join(
        "<tr>"
        + "".join(
            f"<td>{value}</td>"
            for value in ("Profesional", "999", "ACTIVIDAD SINTÉTICA", "Alta", start, end, "", f"SYNTHETIC-{index}")
        )
        + "</tr>"
        for index, (start, end) in enumerate(rows)
    )
    headers = "".join(f"<th>{column}</th>" for column in _ACTIVITY_COLUMNS)
    return f"<h1>Relación de Actividades</h1><table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>"


def _text(day: date) -> str:
    """A day as the census consultation prints it."""
    return day.strftime("%d/%m/%Y")


def _projected(observation: CensalObservation) -> dict[str, object]:
    """Projected values as the review shows them: dates typed, the rest as text."""
    return {
        fact.path: fact.value if isinstance(fact.value, date) else str(fact.value)
        for fact in censal_facts_from_read(observation)
    }


def test_every_census_fact_the_consulta_renders_becomes_a_reviewable_profile_value() -> None:
    projected = _projected(_consulta(ACTIVITIES_HTML))

    # Values read off the synthetic page by hand: Municipio "28079 - MADRID",
    # Administración "28600 - OFICINA EJEMPLO", one activity begun 01/01/2024.
    assert projected == {
        "contact.fiscal_address": "CALLE NOMBRE VIA EJEMPLO NUM 1 7 9, 28001 MADRID MADRID",
        "contact.postcode": "28001",
        "contact.fiscal_address_cadastral_reference": "0000001AA0000A0001AA",
        "contact.fiscal_address_province_code": "28",
        "contact.fiscal_address_municipality_code": "28079",
        "contact.fiscal_address_municipality_name": "MADRID",
        "censo.aeat_delegacion_code": "28",
        "censo.aeat_administracion_code": "600",
        "censo.aeat_administracion_name": "OFICINA EJEMPLO",
        "censo.activity_start_date": ACTIVITY_START,
    }
    assert tuple(projected) == tuple(path for path in CENSAL_ADOPTABLE_PATHS if path in projected)
    assert {fact.source for fact in censal_facts_from_read(_consulta(ACTIVITIES_HTML))} == {"aeat_censo_read"}


def test_without_an_activities_consultation_the_activity_dates_stay_unknown() -> None:
    projected = _projected(_consulta())

    assert "censo.activity_start_date" not in projected
    assert "censo.activity_end_date" not in projected
    assert projected["censo.aeat_administracion_code"] == "600"


def test_activity_end_is_stated_only_when_every_activity_has_ceased() -> None:
    envelope = filing_year_envelope()
    first_start, first_end = date(envelope.floor, 3, 1), date(envelope.floor, 12, 31)
    second_start, last_end = date(envelope.floor, 6, 15), date(envelope.horizon, 9, 30)
    open_one = _projected(_consulta(_activities((_text(first_start), _text(first_end)), (_text(second_start), ""))))
    all_ceased = _projected(
        _consulta(_activities((_text(first_start), _text(first_end)), (_text(second_start), _text(last_end))))
    )

    assert open_one["censo.activity_start_date"] == first_start
    assert "censo.activity_end_date" not in open_one
    assert all_ceased["censo.activity_start_date"] == first_start
    assert all_ceased["censo.activity_end_date"] == last_end


def test_an_unreadable_activity_start_leaves_the_dates_unknown_rather_than_later() -> None:
    projected = _projected(
        _consulta(_activities((_text(date(filing_year_envelope().floor, 3, 1)), ""), ("sin fecha", "")))
    )

    assert "censo.activity_start_date" not in projected
    assert "censo.activity_end_date" not in projected


@pytest.mark.parametrize(
    ("municipio", "administracion"),
    [
        ("MADRID", "OFICINA EJEMPLO"),
        ("00000 - SIN CONSTAR", "2860 - OFICINA EJEMPLO"),
        ("2807 - MADRID", "286000 - OFICINA EJEMPLO"),
    ],
)
def test_a_value_without_its_official_code_shape_is_not_split(municipio: str, administracion: str) -> None:
    observation = _consulta()
    observation = observation.model_copy(
        update={
            "domicilio_fiscal": observation.domicilio_fiscal.model_copy(update={"municipio": municipio}),
            "identity": observation.identity.model_copy(update={"administracion_domicilio_fiscal": administracion}),
        }
    )

    projected = _projected(observation)

    assert "contact.fiscal_address_province_code" not in projected
    assert "contact.fiscal_address_municipality_code" not in projected
    assert "censo.aeat_delegacion_code" not in projected
    assert "censo.aeat_administracion_code" not in projected


def test_the_combined_name_and_any_email_are_not_projected() -> None:
    projected = _projected(_consulta(ACTIVITIES_HTML))

    assert not any(path.startswith("identity.") for path in projected)
