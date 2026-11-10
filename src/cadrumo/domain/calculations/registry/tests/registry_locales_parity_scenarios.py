"""Scenario bodies for test_registry_locales_parity, called by its authored-source and published-authority tests."""

from __future__ import annotations

from ..schema import ModeloDefinition, ModeloRevision
from .authored_editions import authored_revisions, open_ended_revision


def _newest_revision(modelos_by_id: dict[str, ModeloDefinition], modelo_id: str) -> ModeloRevision:
    """Return the newest authored revision of one modelo, which the shared translations must cover."""
    return modelos_by_id[modelo_id].revisions[str(authored_revisions(modelo_id)[-1].id)]


def check_complete_registry_tree_locales_compile_and_validate_cleanly(
    modelos_by_id: dict[str, ModeloDefinition],
) -> None:
    """Every derived Modelo key resolves through the shared catalogues."""
    assert modelos_by_id, "No modelos loaded from registry"

    # Verify that M130 has our translations loaded
    m130 = modelos_by_id["130"]
    revision = m130.revisions[str(open_ended_revision("130").id)]
    casilla_01 = next(c for c in revision.casillas if c.id == "01")

    # Assert labels loaded correctly for all three locales
    assert casilla_01.get_label("en") == "Income"
    assert casilla_01.get_label("ca") == "Ingressos"
    assert casilla_01.get_label("hu") == "Bevételek"

    # Assert help text loaded correctly
    assert casilla_01.get_help("en") == "Total cumulative business income for the tax year."
    assert casilla_01.get_help("ca") == "Ingressos acumulats de l'activitat econòmica."
    assert casilla_01.get_help("hu") == "Az adóévben elért összesített vállalkozási bevétel."

    # Verify Modelo 100 (newest revision)
    rev100 = _newest_revision(modelos_by_id, "100")
    casilla_100_01 = next(c for c in rev100.casillas if c.id == "0001")
    assert casilla_100_01.get_label("en") == "Taxpayer who obtains the income"
    assert casilla_100_01.get_label("ca") == "Contribuent que obté els rendiments"
    assert casilla_100_01.get_label("hu") == "A jövedelmet szerző adózó"
    # Only one authored edition carries this casilla's help text, so the help assertion covers every
    # edition that has any and demands that at least one does.
    helped = {
        str(revision.id): casilla.get_help("en")
        for revision in modelos_by_id["100"].revisions.values()
        for casilla in revision.casillas
        if casilla.id == "0001" and casilla.get_help("en")
    }
    assert helped, "no authored Modelo 100 edition carries the help text of casilla 0001"
    assert set(helped.values()) == {"Selector for the taxpayer obtaining the business yield."}

    # Verify Modelo 200 (newest revision)
    rev200 = _newest_revision(modelos_by_id, "200")
    casilla_200_01 = next(c for c in rev200.casillas if c.id == "00001")
    assert casilla_200_01.get_label("en") == "Non-profit entity under special tax regime Title II Law 49/2002 [00001]"
    assert casilla_200_01.get_label("ca") == (
        "Entitat sense ànim de lucre acollida al règim fiscal Títol II Llei 49/2002 [00001]"
    )
    assert casilla_200_01.get_label("hu") == (
        "Nonprofit szervezet a 49/2002. törvény II. címe szerinti különleges adórendszerben [00001]"
    )
    assert casilla_200_01.get_help("en") == (
        "Flag indicating if the entity is non-profit and subject to the Title II regime of Law 49/2002 [00001]."
    )

    # Verify Modelo 303's newest revision.
    rev303 = _newest_revision(modelos_by_id, "303")
    casilla_303_gen = next(c for c in rev303.casillas if c.id == "iva.repercutido.general")
    assert casilla_303_gen.get_label("en") == "Output VAT amount at the standard rate (21%)"
    assert casilla_303_gen.get_label("ca") == "Quota IVA repercutit al tipus general (21%)"
    assert casilla_303_gen.get_label("hu") == "Felszámított ÁFA összeg általános kulccsal (21%)"
    assert casilla_303_gen.get_help("en") == "Total output VAT calculated at the standard 21% rate."


def check_modelo_130_all_casillas_have_shared_localized_labels_and_help(
    modelos_by_id: dict[str, ModeloDefinition],
) -> None:
    """Modelo 130 is the complete small-model exemplar for shared translations."""
    m130 = modelos_by_id["130"]
    revision = m130.revisions[str(open_ended_revision("130").id)]
    assert revision.casillas, "the revision declares no casilla; the checks below would be vacuous"

    for casilla in revision.casillas:
        for locale in ("en", "ca", "hu"):
            assert casilla.get_label(locale) != casilla.label, (casilla.id, locale)
            assert bool(casilla.get_help(locale)), (casilla.id, locale)
