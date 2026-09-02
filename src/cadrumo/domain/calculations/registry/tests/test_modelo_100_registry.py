"""Tests for the Modelo 100 registry foundation."""

from __future__ import annotations

import json

import pytest

from .._validate_relation_periods import select_relation_source_revisions
from ._modelo_100_registry_support import _loaded_registry, _registry_validator, _source_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_100_revisions_match_record_design_manifest() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    manifest_path = _source_root() / "corpus" / "aeat_official" / "disenos_registro" / "modelo_100" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    years_with_complete_layout = set[str]()
    for year in range(2020, 2026):
        artefact_names = {
            item["original_filename"]
            for item in manifest["artefacts"]
            if f"_{year}" in item["original_filename"] or f"{year}.xsd" in item["original_filename"]
        }
        assert {
            f"diccionarioXSD_{year}.properties",
            f"diccionarioDlgXSD_{year}.properties",
            f"Renta{year}.xsd",
        }.issubset(artefact_names)
        years_with_complete_layout.add(str(year))

    assert set(modelo.revisions) == years_with_complete_layout

    for year_str in years_with_complete_layout:
        revision = modelo.revisions[year_str]
        expected_sources = {
            f"aeat-dr-100-{year_str}-dictionary",
            f"aeat-dr-100-{year_str}-input-dictionary",
            f"aeat-dr-100-{year_str}-xsd",
        }

        assert expected_sources.issubset(revision.source_refs)
        assert expected_sources.issubset(catalogues.sources)
        assert revision.period_selector.years == (int(year_str),)
        assert revision.period_selector.periods == ("0A",)


def test_modelo_100_dependency_relations_resolve_against_registered_modelos() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]

    _registry_validator().validate_modelo(modelo)
    assert revision.relations

    for relation in revision.relations:
        source_modelo = modelos_by_id[relation.source_modelo]
        source_revisions, selector_failures = select_relation_source_revisions(
            source_modelo,
            relation.source_revision_selector,
        )
        assert not selector_failures, relation.id
        assert source_revisions, relation.id
        for source_revision in source_revisions:
            outputs = {casilla.id for casilla in source_revision.casillas}
            assert relation.source_casilla_id in outputs, relation.id
            assert set(relation.source_periods).issubset(source_revision.period_selector.periods), relation.id
        assert relation.target_binding in {binding.id for binding in revision.bindings}
        assert set(relation.target_periods).issubset(revision.period_selector.periods)


def test_modelo_100_rental_landlord_foreign_nif_flags_have_specific_role() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]

    for year in range(2020, 2026):
        revision = modelo.revisions[str(year)]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        for casilla_id, referenced_nif_id in (("0716", "0715"), ("0718", "0717")):
            casilla = casillas_by_id[casilla_id]

            assert tuple(casilla.section)[-1] == "deduccion_alquiler_res"
            assert casilla.data_type == "boolean"
            assert casilla.semantic_role == "irpf_deduccion_alquiler_arrendador_nif_extranjero_flag"
            assert f"[{referenced_nif_id}]" in casilla.label

    assert all(
        casilla.semantic_role != "irpf_anexo_a_nif_extranjero_flag"
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    )


def test_modelo_100_cadastral_construction_ratios_are_decimal_roles() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]

    for year in range(2020, 2026):
        revision = modelo.revisions[str(year)]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        for casilla_id in ("0125", "0140"):
            casilla = casillas_by_id[casilla_id]

            assert tuple(casilla.section) == ("toma_datos_ampliada", "inmuebles", "inmueble")
            assert casilla.data_type == "decimal"
            assert casilla.semantic_role == "irpf_inmueble_ratio_construccion_catastral"
            assert "valor catastral" in casilla.label.lower()
            assert "100" in casilla.label

    assert all(
        casilla.semantic_role != "irpf_inmueble_pct_valor_catastral_construccion"
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    )


def _official_dictionary_type(year: int, *, field_id: str) -> str:
    """Return the type code AEAT's bundled dictionary declares for ``field_id``.

    Resolves the dictionary through the registry's own source catalogue rather
    than a filename written here, so the reader follows AEAT's artefact wherever
    the corpus places it.
    """
    _modelos_by_id, catalogues = _loaded_registry()
    source = catalogues.sources[f"aeat-dr-100-{year}-dictionary"]
    text = (_source_root() / source.corpus_path).read_text(encoding="iso-8859-1")
    for line in text.splitlines():
        name, separator, remainder = line.partition("=[")
        if not separator or name != field_id:
            continue
        return remainder.split("][", 1)[1].split("]", 1)[0]
    pytest.fail(f"bundled Modelo 100 {year} dictionary declares no field {field_id!r}")
    return ""


def test_modelo_100_business_lease_casilla_counts_days_not_a_yes_or_no() -> None:
    """Casilla 0082 holds a day count, which its official label does not say.

    AEAT prints it as "Bien inmueble objeto de arrendamiento de negocio", with no
    mention of days, and the registry once read that as a yes/no marker. The label
    is a print instruction under a column header its sibling carries in full: the
    adjacent 0080 reads "Número de días en que ha tenido este uso: Bien inmueble
    afecto a actividades económicas", and every ``C_DIAS*`` row under Inmueble --
    0076, 0079, 0080, 0082, 0085, 0088, 0101, 0122, 0137 -- is typed ``P030`` by
    the dictionary and ``tipo_Integer1a366`` by the XSD.

    The Manual de Renta states it outright for this box, identically in the 2024
    and 2025 editions: "Sin embargo, si se trata de un bien inmueble objeto de
    arrendamiento de negocio, se indicará el número de días en que ha tenido este
    uso en la casilla [0082]."

    Declared as a boolean it filed a one-day lease for any taxpayer who had one,
    because the renderer resolves a Python ``bool`` to ``"1"`` before it consults
    the declared type at all. The expectation below is read from the bundled
    dictionary rather than written here, so this passes only while the registry
    agrees with AEAT.
    """
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]

    for year in range(2020, 2026):
        revision = modelo.revisions[str(year)]
        casilla = next(casilla for casilla in revision.casillas if casilla.id == "0082")
        official_type = _official_dictionary_type(year, field_id="C_DIASAN")

        assert official_type == "P030", f"{year}: AEAT no longer types C_DIASAN as an integer"
        assert tuple(casilla.section) == ("toma_datos_ampliada", "inmuebles", "inmueble")
        assert casilla.data_type == "integer"
        assert casilla.semantic_role == "irpf_inmueble_dias_arrendamiento_negocio"
        assert casilla.label == "Bien inmueble objeto de arrendamiento de negocio"


def test_the_day_count_oracle_rejects_a_type_code_that_is_not_an_integer() -> None:
    """The dictionary reader discriminates, so the assertion above means something.

    ``C_DIASAN`` shares its ``P030`` code with every other day count under
    Inmueble, while a neighbouring euro amount carries a two-decimal code. If the
    reader returned the same answer for both, the check above would be vacuous.
    """
    assert _official_dictionary_type(2024, field_id="C_DIASAN") == "P030"
    assert _official_dictionary_type(2024, field_id="C_DIASAE") == "P030"
    assert _official_dictionary_type(2024, field_id="USOAE") == "LGC"
    assert _official_dictionary_type(2024, field_id="PC") != "P030"


def test_modelo_100_immovable_gain_cadastral_reference_roles_match_source_blocks() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    main_roles = {
        "1819": "irpf_ganancia_inmueble_referencia_catastral_1",
        "1820": "irpf_ganancia_inmueble_referencia_catastral_2",
        "1821": "irpf_ganancia_inmueble_referencia_catastral_3",
    }
    c1_roles = {
        "1883": "irpf_ganancia_inmueble_anexo_c1_referencia_catastral_1",
        "1884": "irpf_ganancia_inmueble_anexo_c1_referencia_catastral_2",
        "1885": "irpf_ganancia_inmueble_anexo_c1_referencia_catastral_3",
    }

    for year in range(2022, 2026):
        revision = modelo.revisions[str(year)]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        year_source_refs = {
            f"aeat-dr-100-{year}-dictionary",
            f"aeat-dr-100-{year}-xsd",
        }

        for slot, (casilla_id, semantic_role) in enumerate(main_roles.items(), start=1):
            casilla = casillas_by_id[casilla_id]

            assert tuple(casilla.section) == ("toma_datos_ampliada", "gp_otros_inmuebles", "elemento_inmueble")
            assert casilla.data_type == "text"
            assert casilla.semantic_role == semantic_role
            assert casilla.label == f"Referencia catastral {slot}"
            assert year_source_refs.issubset(casilla.source_refs)

        for slot, (casilla_id, semantic_role) in enumerate(c1_roles.items(), start=1):
            casilla = casillas_by_id[casilla_id]

            assert tuple(casilla.section) == ("toma_datos_ampliada", "gp_otros_inmuebles", "elemento_inmueble")
            assert casilla.data_type == "text"
            assert casilla.semantic_role == semantic_role
            assert casilla.label == f"Referencia castastral {slot}"
            assert year_source_refs.issubset(casilla.source_refs)

    revision_2025 = modelo.revisions["2025"]
    casillas_2025 = {casilla.id: casilla for casilla in revision_2025.casillas}

    assert casillas_2025["0413"].semantic_role == "irpf_ganancia_inmueble_referencia_catastral_4"
    assert casillas_2025["0413"].label == "Referencia catastral 4"
    assert casillas_2025["2243"].semantic_role == "irpf_ganancia_inmueble_anexo_c1_referencia_catastral_4"
    assert casillas_2025["2243"].label == "Referencia castastral 4"

    legacy_roles = {
        "irpf_ganancia_inmueble_catastral_2",
        "irpf_ganancia_inmueble_catastral_3",
        "irpf_ganancia_inmueble_catastral_4",
        "irpf_ganancia_inmueble_catastral_1_b",
        "irpf_ganancia_inmueble_catastral_2_b",
        "irpf_ganancia_inmueble_catastral_3_b",
        "irpf_ganancia_inmueble_catastral_4_b",
    }
    assert not any(
        casilla.semantic_role in legacy_roles for revision in modelo.revisions.values() for casilla in revision.casillas
    )


def test_modelo_100_regularization_refunds_use_noun_role() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]

    for year in range(2020, 2026):
        revision = modelo.revisions[str(year)]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        expected_casilla_ids = ("0677", "0682") if year <= 2023 else ("0677",)

        for casilla_id in expected_casilla_ids:
            casilla = casillas_by_id[casilla_id]

            assert tuple(casilla.section) == ("resultados", "regularizacion_res")
            assert casilla.semantic_role == "irpf_regularizacion_devolucion_autoliquidaciones_anteriores"
            assert "devoluci" in casilla.label.lower()
            assert str(year) in casilla.label

    assert all(
        casilla.semantic_role != "irpf_regularizacion_autoliquidaciones_anteriores_devolver"
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    )
