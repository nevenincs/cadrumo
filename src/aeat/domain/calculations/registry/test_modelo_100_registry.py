"""Tests for the Modelo 100 registry foundation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

import pytest
from pydantic import AnyUrl

from aeat.core.paths import PROJECT_ROOT

from ._constructs import resolve_construct, resolve_revision_constructs
from ._errors import RegistrySnapshotError, RegistryValidationError
from ._export import resolve_export_layout
from ._export_parse import parse_export_payload
from ._formula_runtime import calculate_registry_snapshot
from ._loader import load_registry_tree
from ._remote_state_guard import (
    RemoteOperation,
    assert_remote_operation_allowed,
    remote_state_policy_from_cross_reference,
)
from ._schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ._snapshot import build_snapshot
from ._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _loaded_registry() -> tuple[dict[str, ModeloDefinition], RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    return {modelo.id: modelo for modelo in modelos}, catalogues


def test_modelo_100_revisions_match_record_design_manifest() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    manifest_path = PROJECT_ROOT / "corpus" / "aeat_official" / "disenos_registro" / "modelo_100" / "manifest.json"
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

    for year in years_with_complete_layout:
        revision = modelo.revisions[year]
        expected_sources = {
            f"aeat-dr-100-{year}-dictionary",
            f"aeat-dr-100-{year}-input-dictionary",
            f"aeat-dr-100-{year}-xsd",
        }

        assert expected_sources.issubset(revision.source_refs)
        assert expected_sources.issubset(catalogues.sources)
        assert revision.period_selector.years == (int(year),)
        assert revision.period_selector.periods == ("0A",)


def test_modelo_100_dependency_relations_resolve_against_registered_modelos() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)
    assert revision.relations

    for relation in revision.relations:
        source_modelo = modelos_by_id[relation.source_modelo]
        source_revisions = _select_source_revisions(source_modelo, relation.source_revision_selector)
        assert source_revisions, relation.id
        for source_revision in source_revisions:
            outputs = {casilla.id for casilla in source_revision.casillas}
            outputs.update(binding.id for binding in source_revision.bindings)
            for binding in source_revision.algorithm_bindings:
                outputs.update(binding.outputs.values())

            assert relation.source_output in outputs, relation.id
            assert set(relation.source_periods).issubset(source_revision.period_selector.periods), relation.id
        assert relation.target_binding in {binding.id for binding in revision.bindings}
        assert set(relation.target_periods).issubset(revision.period_selector.periods)


def test_modelo_100_constructs_include_dependency_and_source_evidence_members() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    source_foundation = snapshot.constructs["renta-source-foundation"]
    dependencies = snapshot.constructs["renta-dependent-modelos"]
    payments_retentions = snapshot.constructs["renta-payments-retentions"]
    observation_parsing = snapshot.constructs["renta-observation-parsing"]

    assert set(dependencies.bindings) == {binding.id for binding in snapshot.revision.bindings}
    assert set(dependencies.relations) == {relation.id for relation in snapshot.revision.relations}
    assert set(payments_retentions.bindings) == {binding.id for binding in snapshot.revision.bindings}
    assert set(payments_retentions.relations) == {relation.id for relation in snapshot.revision.relations}
    assert set(source_foundation.workbook_parity_refs) == set(snapshot.workbook_parity_refs)
    assert set(source_foundation.live_cross_references) == set(snapshot.live_cross_references)
    assert observation_parsing.live_cross_references == ("modelo-100-filed-declarations-read",)
    assert set(dependencies.dependency_classifications) == set(snapshot.dependency_classifications)
    assert set(payments_retentions.dependency_classifications) == set(snapshot.dependency_classifications)


def test_modelo_100_construct_reader_resolves_revision_member_objects() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    constructs = {construct.id: construct for construct in resolve_revision_constructs(revision)}
    dependencies = constructs["renta-dependent-modelos"]

    assert {member.id for member in dependencies.members_of_kind("binding")} == {
        binding.id for binding in revision.bindings
    }
    assert {member.id for member in dependencies.members_of_kind("relation")} == {
        relation.id for relation in revision.relations
    }
    for member in dependencies.members:
        assert cast(Any, member.value).id == member.id


def test_modelo_100_renta_section_constructs_classify_registered_relation_sources() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    relations_by_id = {relation.id: relation for relation in revision.relations}
    constructs = {construct.id: construct for construct in resolve_revision_constructs(revision)}
    source_modelos_by_construct = {
        construct_id: {
            relations_by_id[member.id].source_modelo for member in constructs[construct_id].members_of_kind("relation")
        }
        for construct_id in (
            "renta-work-income",
            "renta-real-estate-capital",
            "renta-movable-capital",
            "renta-economic-activities",
        )
    }

    assert source_modelos_by_construct == {
        "renta-work-income": {"111"},
        "renta-real-estate-capital": {"115", "180"},
        "renta-movable-capital": {"123"},
        "renta-economic-activities": {"130", "131"},
    }


def test_modelo_100_dependency_classifications_cover_registered_relation_sources() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    relations_by_source: dict[str, set[str]] = {}
    for relation in snapshot.revision.relations:
        relations_by_source.setdefault(relation.source_modelo, set()).add(relation.id)
    classifications_by_source = {
        classification.source_modelo: classification
        for classification in snapshot.revision.dependency_classifications
        if classification.treatment == "direct_annual_settlement"
    }

    assert set(classifications_by_source) == set(relations_by_source)
    for source_modelo, relation_ids in relations_by_source.items():
        classification = classifications_by_source[source_modelo]
        assert set(classification.relation_refs) == relation_ids
        assert "renta-dependent-modelos" in classification.target_constructs
        assert all(construct_id in snapshot.constructs for construct_id in classification.target_constructs)


def test_modelo_100_payments_on_account_calculate_from_registry_relations() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "0592": Decimal("1.00"),
            "0593": Decimal("2.00"),
            "0594": Decimal("3.00"),
            "0596": Decimal("4.00"),
            "0597": Decimal("5.00"),
            "0598": Decimal("6.00"),
            "0599": Decimal("7.00"),
            "0600": Decimal("8.00"),
            "0601": Decimal("9.00"),
            "0602": Decimal("10.00"),
            "0603": Decimal("11.00"),
            "0605": Decimal("12.00"),
            "0606": Decimal("13.00"),
        },
        date_context={},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("140.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("220.00"),
        },
    )
    entries = {entry.target: entry for entry in result.entries}

    assert result.values["0604"] == Decimal("360.00")
    assert result.values["0609"] == Decimal("451.00")
    assert entries["0604"].operand_refs == (
        "renta-2025-rel-130-pagos-fraccionados",
        "renta-2025-rel-131-pagos-fraccionados",
    )
    assert entries["0609"].operand_refs == (
        "0592",
        "0593",
        "0594",
        "0596",
        "0597",
        "0598",
        "0599",
        "0600",
        "0601",
        "0602",
        "0603",
        "0604",
        "0605",
        "0606",
    )


def test_modelo_100_direct_estimation_subtotals_calculate_from_registry() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "0171": Decimal("100.00"),
            "0172": Decimal("20.00"),
            "0173": Decimal("3.00"),
            "0174": Decimal("4.00"),
            "0175": Decimal("5.00"),
            "0176": Decimal("6.00"),
            "0177": Decimal("7.00"),
            "0178": Decimal("8.00"),
            "0179": Decimal("9.00"),
            "0181": Decimal("10.00"),
            "0182": Decimal("1.00"),
            "0183": Decimal("2.00"),
            "0184": Decimal("3.00"),
            "0185": Decimal("4.00"),
            "0186": Decimal("5.00"),
            "0187": Decimal("6.00"),
            "0188": Decimal("7.00"),
            "0189": Decimal("8.00"),
            "0190": Decimal("9.00"),
            "0191": Decimal("10.00"),
            "0192": Decimal("11.00"),
            "0193": Decimal("12.00"),
            "0194": Decimal("13.00"),
            "0195": Decimal("14.00"),
            "0196": Decimal("15.00"),
            "0197": Decimal("4.00"),
            "0198": Decimal("16.00"),
            "0199": Decimal("17.00"),
            "0200": Decimal("18.00"),
            "0202": Decimal("19.00"),
            "0203": Decimal("20.00"),
            "0205": Decimal("21.00"),
            "0206": Decimal("22.00"),
            "0208": Decimal("23.00"),
            "0214": Decimal("25.00"),
            "0215": Decimal("26.00"),
            "0216": Decimal("27.00"),
            "0217": Decimal("28.00"),
            "0219": Decimal("30.00"),
            "0222": Decimal("40.00"),
            "0227": Decimal("24.00"),
        },
        date_context={},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("0.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("0.00"),
        },
    )
    entries = {entry.target: entry for entry in result.entries}

    assert result.values["0180"] == Decimal("162.00")
    assert result.values["0218"] == Decimal("412.00")
    assert result.values["0220"] == Decimal("442.00")
    assert result.values["0221"] == Decimal("-250.00")
    assert result.values["0223"] == Decimal("452.00")
    assert entries["0218"].operand_refs == (
        "0181",
        "0182",
        "0183",
        "0184",
        "0185",
        "0186",
        "0187",
        "0188",
        "0189",
        "0190",
        "0191",
        "0192",
        "0193",
        "0194",
        "0195",
        "0196",
        "0197",
        "0198",
        "0199",
        "0200",
        "0202",
        "0203",
        "0205",
        "0206",
        "0208",
        "0227",
        "0214",
        "0215",
        "0216",
        "0217",
    )


def test_modelo_100_authenticated_filed_data_cross_reference_is_guarded_read_only() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    source = catalogues.sources["aeat-modelo-100-procedure"]
    source_text = (PROJECT_ROOT / source.corpus_path).read_text(encoding="utf-8")

    assert "Consulta de declaraciones presentadas" in source_text
    assert "Datos fiscales" in source_text

    for year in range(2020, 2026):
        snapshot = build_snapshot(
            modelos_by_id["100"],
            catalogues,
            source_root=PROJECT_ROOT,
            filing_year=year,
            period="0A",
        )
        cross_reference = snapshot.live_cross_references["modelo-100-filed-declarations-read"]
        policy = remote_state_policy_from_cross_reference(cross_reference)

        assert cross_reference.surface == "authenticated_read_surface"
        assert cross_reference.synthetic_data_allowed is False
        assert cross_reference.requires_authentication is True
        assert cross_reference.requires_aeat_authorization is True
        assert "aeat-modelo-100-procedure" in cross_reference.source_refs
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(
                kind="http",
                method="GET",
                url=AnyUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
            ),
        )
        with pytest.raises(RegistryValidationError, match="remote write method"):
            assert_remote_operation_allowed(
                policy,
                RemoteOperation(
                    kind="http",
                    method="POST",
                    url=AnyUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
                ),
            )


def test_modelo_100_xml_dictionary_layout_reads_official_casilla_paths() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2023, period="0A")
    resolved = resolve_export_layout(snapshot)
    payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<Renta>
  <DatosIdentificativos>
    <Declarante>
      <DPNIF_D>12345678Z</DPNIF_D>
    </Declarante>
  </DatosIdentificativos>
  <DatosEconomicos>
    <TomaDatosAmpliada>
      <RegEstimaDirecta>
        <ActividadEstDirecta>
          <E1INGRESO>1234.56</E1INGRESO>
        </ActividadEstDirecta>
      </RegEstimaDirecta>
      <Inmuebles>
        <Inmueble>
          <DisposicionTitulares>
            <C_RII>10.00</C_RII>
          </DisposicionTitulares>
        </Inmueble>
      </Inmuebles>
    </TomaDatosAmpliada>
    <Resultados>
      <InmueblesRes>
        <IRIM>10.00</IRIM>
      </InmueblesRes>
    </Resultados>
  </DatosEconomicos>
</Renta>
"""

    parsed = parse_export_payload(
        resolved.layout,
        payload,
        source_root=PROJECT_ROOT,
        sources=snapshot.sources,
    )

    assert {item.casilla_id: item.value for item in parsed.casillas} == {
        "0089": Decimal("10.00"),
        "0155": Decimal("10.00"),
        "0180": Decimal("1234.56"),
    }
    assert all(item.casilla_id != "01" for item in parsed.casillas)


def test_construct_reader_rejects_unknown_construct_id() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]

    with pytest.raises(RegistrySnapshotError, match="has no construct"):
        resolve_construct(revision, "missing-construct")


def test_validator_rejects_construct_member_outside_revision() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    construct = next(item for item in revision.constructs if item.id == "renta-dependent-modelos")
    mutated_construct = construct.model_copy(update={"relations": (*construct.relations, "missing-relation")})
    mutated_revision = revision.model_copy(
        update={
            "constructs": tuple(mutated_construct if item.id == construct.id else item for item in revision.constructs)
        }
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="references unknown relation"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(mutated_modelo)


def test_validator_rejects_dependency_classification_source_drift() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    classification = revision.dependency_classifications[0].model_copy(update={"source_modelo": "115"})
    mutated_revision = revision.model_copy(
        update={"dependency_classifications": (classification, *revision.dependency_classifications[1:])}
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="does not match relation"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(mutated_modelo)


def test_modelo_100_renta_web_open_cross_reference_is_read_only_simulator_evidence() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    cross_reference = next(item for item in revision.live_cross_references if item.id == "modelo-100-renta-web-open")
    source = catalogues.sources[cross_reference.source_refs[0]]
    source_text = (PROJECT_ROOT / source.corpus_path).read_text(encoding="utf-8")

    assert cross_reference.surface == "open_simulator"
    assert cross_reference.synthetic_data_allowed is True
    assert cross_reference.requires_authentication is False
    assert "presentation" in cross_reference.forbidden_actions
    assert "payment" in cross_reference.forbidden_actions
    assert "funciona como un simulador" in source_text
    assert "no permite la presentaci&oacute;n de la declaraci&oacute;n" in source_text


def _select_source_revisions(
    modelo: ModeloDefinition,
    selector: Mapping[str, str | int],
) -> tuple[ModeloRevision, ...]:
    year = selector.get("year")
    revision_id = selector.get("revision_id", selector.get("revision"))
    selected: list[ModeloRevision] = []
    for revision in modelo.revisions.values():
        if isinstance(revision_id, str) and revision.id != revision_id:
            continue
        if isinstance(year, int) and not revision.period_selector.includes_year(year):
            continue
        selected.append(revision)
    return tuple(selected)
