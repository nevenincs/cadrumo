"""Parity and referential integrity tests for shared Modelo locale keys."""

from __future__ import annotations

import pytest

from ..authority import bundled_authority
from ..schema import ModeloDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelos_by_id() -> dict[str, ModeloDefinition]:
    return {modelo.id: modelo for modelo in bundled_authority().modelos}


def test_complete_registry_tree_locales_compile_and_validate_cleanly() -> None:
    """Every derived Modelo key resolves through the shared catalogues."""
    modelos_by_id = _modelos_by_id()
    assert modelos_by_id, "No modelos loaded from registry"

    # Verify that M130 has our translations loaded
    m130 = modelos_by_id["130"]
    revision = m130.revisions["2019-y-siguientes"]
    casilla_01 = next(c for c in revision.casillas if c.id == "01")

    # Assert labels loaded correctly for all three locales
    assert casilla_01.get_label("en") == "Income"
    assert casilla_01.get_label("ca") == "Ingressos"
    assert casilla_01.get_label("hu") == "Bevételek"

    # Assert help text loaded correctly
    assert casilla_01.get_help("en") == "Total cumulative business income for the tax year."
    assert casilla_01.get_help("ca") == "Ingressos acumulats de l'activitat econòmica."
    assert casilla_01.get_help("hu") == "Az adóévben elért összesített vállalkozási bevétel."

    # Verify Modelo 100 (revision 2024)
    m100 = modelos_by_id["100"]
    rev100 = m100.revisions["2024"]
    casilla_100_01 = next(c for c in rev100.casillas if c.id == "0001")
    assert casilla_100_01.get_label("en") == "Taxpayer obtaining yield"
    assert casilla_100_01.get_label("ca") == "Contribuent que obté els rendiments"
    assert casilla_100_01.get_label("hu") == "Jövedelmet megszerző adózó"
    assert casilla_100_01.get_help("en") == "Selector for the taxpayer obtaining the business yield."

    # Verify Modelo 200 (revision 2024)
    m200 = modelos_by_id["200"]
    rev200 = m200.revisions["2024"]
    casilla_200_01 = next(c for c in rev200.casillas if c.id == "00001")
    assert casilla_200_01.get_label("en") == "Non-profit entity under special tax regime Title II Law 49/2002"
    assert casilla_200_01.get_label("ca") == (
        "Entitat sense ànim de lucre acollida al règim fiscal Títol II Llei 49/2002"
    )
    assert casilla_200_01.get_label("hu") == (
        "Nonprofit szervezet a 49/2002. törvény II. címe szerinti különleges adórendszerben"
    )
    assert casilla_200_01.get_help("en") == (
        "Flag indicating if the entity is non-profit and subject to the Title II regime of Law 49/2002."
    )

    # Verify Modelo 303's 2023 revision.
    m303 = modelos_by_id["303"]
    rev303 = m303.revisions["2023"]
    casilla_303_gen = next(c for c in rev303.casillas if c.id == "iva.repercutido.general")
    assert casilla_303_gen.get_label("en") == "Output VAT amount at the standard rate (21%)"
    assert casilla_303_gen.get_label("ca") == "Quota IVA repercutit al tipus general (21%)"
    assert casilla_303_gen.get_label("hu") == "Felszámított ÁFA összeg általános kulccsal (21%)"
    assert casilla_303_gen.get_help("en") == "Total output VAT calculated at the standard 21% rate."


def test_modelo_130_all_casillas_have_shared_localized_labels_and_help() -> None:
    """Modelo 130 is the complete small-model exemplar for shared translations."""
    m130 = _modelos_by_id()["130"]
    revision = m130.revisions["2019-y-siguientes"]
    assert len(revision.casillas) == 20

    for casilla in revision.casillas:
        for locale in ("en", "ca", "hu"):
            assert casilla.get_label(locale) != casilla.label, (casilla.id, locale)
            assert casilla.get_help(locale), (casilla.id, locale)
