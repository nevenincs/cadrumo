"""Modelo 360's typed producer facts refuse what DR360 and Orden EHA/789/2010 do not admit.

Every refusal here would otherwise reach the wire: as a mislabelled country, a modificación
without the solicitud it modifies, an establishment code that contradicts its own ámbito, or
an identifier too short for the full-width digit slot DR360 prints.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from ..producer_snapshot_m360 import (
    M360AmbitoEstablecimiento,
    M360CausaPresentacion,
    M360DelegacionCanariasCeutaMelilla,
    M360HaciendaForal,
    M360NivelCalidadDatos,
    M360TitularEnCalidadDe,
    Modelo360ApartadoCorreos,
    Modelo360CuentaTitularFacts,
    Modelo360DireccionExtranjero,
    Modelo360DomicilioEspana,
    Modelo360EstablecimientoFacts,
    Modelo360ProfileFacts,
    Modelo360SolicitanteFacts,
    Modelo360SolicitudFacts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _solicitud(
    *,
    pais_destino: str = "DE",
    causa: M360CausaPresentacion = M360CausaPresentacion.INICIAL,
    numero_registro: str | None = None,
    prorrata: bool | None = None,
) -> Modelo360SolicitudFacts:
    return Modelo360SolicitudFacts(
        nivel_calidad_datos=M360NivelCalidadDatos.MEDIA,
        pais_destino=pais_destino,
        causa_presentacion=causa,
        numero_registro_declaracion_anterior=numero_registro,
        comunicacion_prorrata_definitiva=prorrata,
    )


def _establecimiento(ambito: M360AmbitoEstablecimiento) -> Modelo360EstablecimientoFacts:
    return Modelo360EstablecimientoFacts(
        ambito=ambito,
        hacienda_foral=M360HaciendaForal.BIZKAIA if ambito is M360AmbitoEstablecimiento.HACIENDA_FORAL else None,
        delegacion_canarias_ceuta_melilla=(
            M360DelegacionCanariasCeutaMelilla.CEUTA
            if ambito is M360AmbitoEstablecimiento.CANARIAS_CEUTA_MELILLA
            else None
        ),
    )


def _profile(
    *,
    solicitud: Modelo360SolicitudFacts | None = None,
    ambito: M360AmbitoEstablecimiento = M360AmbitoEstablecimiento.TERRITORIO_COMUN,
    en_calidad_de: M360TitularEnCalidadDe = M360TitularEnCalidadDe.SOLICITANTE,
) -> Modelo360ProfileFacts:
    return Modelo360ProfileFacts(
        solicitud=solicitud or _solicitud(),
        solicitante=Modelo360SolicitanteFacts(email="solicitante@example.es", establecimiento=_establecimiento(ambito)),
        cuenta=Modelo360CuentaTitularFacts(titular_nombre="TITULAR", titular_en_calidad_de=en_calidad_de, divisa="EUR"),
    )


def test_a_modificacion_names_the_solicitud_it_modifies() -> None:
    """DR360 Nota 4: causa "1" requires campo 10."""
    with pytest.raises(ValidationError, match="registro number of the solicitud it modifies"):
        _solicitud(causa=M360CausaPresentacion.MODIFICACION)
    assert (
        _solicitud(
            causa=M360CausaPresentacion.MODIFICACION, numero_registro="3600000000001ABC"
        ).numero_registro_declaracion_anterior
        == "3600000000001ABC"
    )


def test_an_initial_solicitud_carries_no_earlier_registro_number() -> None:
    with pytest.raises(ValidationError, match="carries no earlier registro number"):
        _solicitud(numero_registro="3600000000001ABC")


def test_the_prorrata_communication_rides_only_a_modificacion() -> None:
    """DR360 Nota 5 lists campo 9 = "1" beside causa " " or "1", never beside "0"."""
    with pytest.raises(ValidationError, match="Nota 5"):
        _solicitud(prorrata=True)
    assert _solicitud(prorrata=False).comunicacion_prorrata_definitiva is False


@pytest.mark.parametrize("code", ["GR", "gr", "GRC", "E"])
def test_a_country_outside_the_design_alphabet_is_refused(code: str) -> None:
    """DR360 Nota 3: two upper-case ISO letters, and Greece is ``EL``."""
    with pytest.raises(ValidationError):
        _solicitud(pais_destino=code)
    with pytest.raises(ValidationError):
        Modelo360DireccionExtranjero(country_code=code)


@pytest.mark.parametrize(
    "ambito", [M360AmbitoEstablecimiento.TERRITORIO_COMUN, M360AmbitoEstablecimiento.HACIENDA_FORAL]
)
def test_a_solicitante_established_in_the_territorio_cannot_address_spain(ambito: M360AmbitoEstablecimiento) -> None:
    """Orden EHA/789/2010 art. 1.2: VAT borne in the Community "con excepción de las realizadas en dicho territorio"."""
    with pytest.raises(ValidationError, match="never in Spain"):
        _profile(solicitud=_solicitud(pais_destino="ES"), ambito=ambito)


def test_a_canarias_ceuta_or_melilla_solicitante_may_address_spain() -> None:
    """Orden EHA/789/2010 art. 1.2, second paragraph."""
    profile = _profile(solicitud=_solicitud(pais_destino="ES"), ambito=M360AmbitoEstablecimiento.CANARIAS_CEUTA_MELILLA)
    assert profile.solicitud.pais_destino == "ES"


def test_establishment_codes_follow_their_ambito() -> None:
    """DR360 Notas 6-8: a foral or delegación code exists exactly where the solicitante is established."""
    with pytest.raises(ValidationError, match="hacienda foral"):
        Modelo360EstablecimientoFacts(ambito=M360AmbitoEstablecimiento.HACIENDA_FORAL)
    with pytest.raises(ValidationError, match="hacienda foral"):
        Modelo360EstablecimientoFacts(
            ambito=M360AmbitoEstablecimiento.TERRITORIO_COMUN, hacienda_foral=M360HaciendaForal.ALAVA
        )
    with pytest.raises(ValidationError, match="delegacion"):
        Modelo360EstablecimientoFacts(ambito=M360AmbitoEstablecimiento.CANARIAS_CEUTA_MELILLA)
    with pytest.raises(ValidationError, match="delegacion"):
        Modelo360EstablecimientoFacts(
            ambito=M360AmbitoEstablecimiento.HACIENDA_FORAL,
            hacienda_foral=M360HaciendaForal.NAVARRA,
            delegacion_canarias_ceuta_melilla=M360DelegacionCanariasCeutaMelilla.MELILLA,
        )


def test_only_the_territorio_comun_reads_established() -> None:
    """DR360 Nota 6: foral and Canarias/Ceuta/Melilla solicitantes write "0"."""
    assert {
        ambito: _establecimiento(ambito).establecido_en_territorio_de_aplicacion for ambito in M360AmbitoEstablecimiento
    } == {
        M360AmbitoEstablecimiento.TERRITORIO_COMUN: True,
        M360AmbitoEstablecimiento.HACIENDA_FORAL: False,
        M360AmbitoEstablecimiento.CANARIAS_CEUTA_MELILLA: False,
    }


def test_an_account_held_by_the_representante_needs_one() -> None:
    """DR360 campo 114 "R" names a representante the solicitud must declare."""
    with pytest.raises(ValidationError, match="declared representante"):
        _profile(en_calidad_de=M360TitularEnCalidadDe.REPRESENTANTE)


@pytest.mark.parametrize(
    ("build", "value"),
    [
        (lambda value: Modelo360DomicilioEspana(numero_casa=value), "12"),
        (lambda value: Modelo360DomicilioEspana(codigo_postal=value), "3100"),
        (lambda value: Modelo360ApartadoCorreos(numero=value), "123456789"),
        (lambda value: Modelo360DomicilioEspana(provincia=value), "NAV"),
        (lambda value: Modelo360DomicilioEspana(tipo_via=value), "AVENIDA"),
    ],
    ids=["numero-casa-short", "codigo-postal-short", "apartado-short", "provincia-wide", "tipo-via-wide"],
)
def test_a_value_that_does_not_fit_its_design_slot_is_refused(build: Callable[[str], object], value: str) -> None:
    """Num slots take every digit; An slots take no more than their width."""
    with pytest.raises(ValidationError):
        build(value)


@pytest.mark.parametrize("email", ["sin-arroba.example.es", "dos@@example.es", "con espacio@example.es", ""])
def test_a_malformed_email_is_refused(email: str) -> None:
    """DR360 campo 14 is obligatorio; a blank or malformed address is not one."""
    with pytest.raises(ValidationError):
        Modelo360SolicitanteFacts(
            email=email, establecimiento=_establecimiento(M360AmbitoEstablecimiento.TERRITORIO_COMUN)
        )


def test_a_blank_optional_value_is_absent_not_an_empty_string() -> None:
    """Absent is ``None``; a whitespace string would render as a value nobody declared."""
    with pytest.raises(ValidationError):
        Modelo360SolicitanteFacts(
            email="solicitante@example.es",
            phone="   ",
            establecimiento=_establecimiento(M360AmbitoEstablecimiento.TERRITORIO_COMUN),
        )


@pytest.mark.parametrize("divisa", ["eur", "EURO", ""])
def test_the_account_currency_is_an_iso_4217_code(divisa: str) -> None:
    with pytest.raises(ValidationError):
        Modelo360CuentaTitularFacts(
            titular_nombre="TITULAR", titular_en_calidad_de=M360TitularEnCalidadDe.SOLICITANTE, divisa=divisa
        )


def test_the_account_holder_fits_campo_113() -> None:
    """DR360 campo 113 is 25 positions."""
    with pytest.raises(ValidationError):
        Modelo360CuentaTitularFacts(
            titular_nombre="X" * 26, titular_en_calidad_de=M360TitularEnCalidadDe.SOLICITANTE, divisa="EUR"
        )
