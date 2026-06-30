"""Unit tests for the typed declaration-export / declaration-verify surface."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

import pytest
from defusedxml import ElementTree as DefusedElementTree
from pydantic import ValidationError

from ....core import Period
from ....core.resources import bundled_path
from ....domain.calculations.registry import (
    CasillaFieldKind,
    CasillaId,
    RegistrySnapshotRef,
    RegistryValidationError,
    parse_export_payload,
    validated_casilla_id,
)
from ....domain.filing import (
    FilingExportError,
    ModeloCasillaProvenance,
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
)
from ....domain.submission import ModeloDraftStatus
from .. import (
    DeclaracionExportFormat,
    DeclaracionExportResult,
    DeclaracionVerifyResult,
    DeclaracionVerifyVerdict,
    ModeloOperatorProfile,
    build_draft,
    export_draft,
    verify_export,
)
from ._export_support import (
    _EXPORT_PATH,
    _EXPORT_VERIFY_MATCH_CASES,
    _HEX_DIGEST,
    _M111_RESULTADO_CASILLA,
    _M111_RETENCIONES_TOTAL_CASILLA,
    _M115_BASE_CASILLA,
    _M115_PERCEPTORES_CASILLA,
    _M115_PREVIOUS_RESULT_CASILLA,
    _M115_RESULTADO_CASILLA,
    _M115_RETENCIONES_CASILLA,
    _M123_2019_2023_BASE_CASILLA,
    _M123_2019_2023_INGRESOS_CUENTA_CASILLA,
    _M123_2019_2023_MINORACION_CASILLA,
    _M123_2019_2023_PERCEPTORES_CASILLA,
    _M123_2019_2023_PREVIOUS_RESULT_CASILLA,
    _M123_2019_2023_RESULTADO_CASILLA,
    _M123_2019_2023_RETENCIONES_CASILLA,
    _M123_2019_2023_TOTAL_RETENCIONES_CASILLA,
    _M123_BASE_CASILLA,
    _M123_INGRESOS_CUENTA_CASILLA,
    _M123_PERCEPTORES_CASILLA,
    _M123_RESULTADO_CASILLA,
    _M123_RETENCIONES_CASILLA,
    _M131_HISTORICAL_01_CASILLA,
    _M131_HISTORICAL_02_CASILLA,
    _M131_HISTORICAL_03_CASILLA,
    _M131_HISTORICAL_04_CASILLA,
    _M131_HISTORICAL_05_CASILLA,
    _M131_HISTORICAL_06_CASILLA,
    _M131_HISTORICAL_07_CASILLA,
    _M131_HISTORICAL_08_CASILLA,
    _M131_HISTORICAL_09_CASILLA,
    _M131_HISTORICAL_10_CASILLA,
    _M131_HISTORICAL_11_CASILLA,
    _M131_HISTORICAL_12_CASILLA,
    _M131_HISTORICAL_13_CASILLA,
    _M131_HISTORICAL_14_CASILLA,
    _M131_HISTORICAL_15_CASILLA,
    _OTHER_EXPORT_PATH,
    _PERIOD,
    _approved_modelo_111_registry_draft,
    _approved_modelo_115_registry_draft,
    _approved_modelo_123_2019_registry_draft,
    _approved_modelo_123_registry_draft,
    _approved_modelo_131_historical_registry_draft,
    _approved_modelo_131_registry_draft,
    _approved_modelo_131_registry_draft_without_direct_debit,
    _approved_modelo_131_year_scoped_registry_draft,
    _approved_modelo_131_zero_payable_direct_debit_draft,
    _approved_registry_draft,
    _assert_missing_export_layout_refusal,
    _ExportVerifyMatchCase,
    _field_slice,
    _modelo_111_export_headers,
    _modelo_111_export_payload,
    _modelo_115_export_headers,
    _modelo_123_2019_export_headers,
    _modelo_123_export_headers,
    _modelo_130_export_headers,
    _modelo_130_export_payload,
    _narrative,
    _provider_without_export_layout,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M200_RESULTADO_CONTABLE_CASILLA: CasillaId = validated_casilla_id(
    "00501",
    surface="_M200_RESULTADO_CONTABLE_CASILLA",
)
_M200_CORRECCIONES_AUMENTO_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:01033",
    surface="_M200_CORRECCIONES_AUMENTO_CASILLA",
)
_M200_CORRECCIONES_DISMINUCION_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:01034",
    surface="_M200_CORRECCIONES_DISMINUCION_CASILLA",
)
_M200_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id(
    "DP200014B:00611",
    surface="_M200_CUOTA_DIFERENCIAL_CASILLA",
)
_M200_GRUPO_FISCAL_CASILLA: CasillaId = validated_casilla_id(
    "00040",
    surface="_M200_GRUPO_FISCAL_CASILLA",
)


def test_build_draft_populates_registry_casilla_provenance() -> None:
    draft = _approved_registry_draft()
    collection = _schema_provider().get_collection(draft.modelo)
    registry_provenance = {
        casilla.casilla_id: (tuple(casilla.legal_refs), tuple(casilla.source_refs))
        for casilla in collection.all()
        if casilla.legal_refs and casilla.source_refs
    }
    draft_provenance = {entry.casilla_id: entry for entry in draft.casilla_provenance}

    assert registry_provenance
    assert set(registry_provenance).issubset(draft_provenance)
    for casilla_id, (legal_refs, source_refs) in registry_provenance.items():
        assert draft_provenance[casilla_id].legal_refs == legal_refs
        assert draft_provenance[casilla_id].source_refs == source_refs


def test_format_enum_carries_cli_values() -> None:
    assert DeclaracionExportFormat.FICHERO_BOE.value == "fichero-boe"
    assert DeclaracionExportFormat.XML_DICTIONARY.value == "xml-dictionary"


def test_verdict_enum_orders_match_drift_missing() -> None:
    assert {item.value for item in DeclaracionVerifyVerdict} == {"match", "drift", "missing"}


def test_export_result_round_trips_canonical_fields() -> None:
    receipt = DeclaracionExportResult(
        draft_id="d-130-2026Q1",
        modelo="130",
        period=_PERIOD,
        format=DeclaracionExportFormat.FICHERO_BOE,
        output_path=_EXPORT_PATH,
        byte_size=512,
        file_sha256=_HEX_DIGEST,
        exported_at=datetime(2026, 5, 3, tzinfo=UTC),
        narrative=_narrative(),
    )
    assert receipt.draft_id == "d-130-2026Q1"
    assert receipt.format is DeclaracionExportFormat.FICHERO_BOE
    assert receipt.output_path == _EXPORT_PATH
    assert receipt.byte_size == 512
    assert receipt.file_sha256 == _HEX_DIGEST
    assert receipt.narrative
    assert receipt.period == _PERIOD
    assert receipt.model_dump(mode="json")["period"] == {"filing_year": 2026, "code": "1T"}


def test_export_result_rejects_uppercase_digest() -> None:
    with pytest.raises(ValueError, match=r"file_sha256|hex|lowercase"):
        DeclaracionExportResult(
            draft_id="d",
            modelo="130",
            period=_PERIOD,
            format=DeclaracionExportFormat.FICHERO_BOE,
            output_path=_OTHER_EXPORT_PATH,
            byte_size=1,
            file_sha256="A" * 64,
            exported_at=datetime(2026, 5, 3, tzinfo=UTC),
            narrative=_narrative(),
        )


def test_export_result_rejects_non_hex_digest() -> None:
    with pytest.raises(ValueError, match=r"file_sha256|hex"):
        DeclaracionExportResult(
            draft_id="d",
            modelo="130",
            period=_PERIOD,
            format=DeclaracionExportFormat.FICHERO_BOE,
            output_path=_OTHER_EXPORT_PATH,
            byte_size=1,
            file_sha256="z" * 64,
            exported_at=datetime(2026, 5, 3, tzinfo=UTC),
            narrative=_narrative(),
        )


def test_export_result_is_frozen() -> None:
    receipt = DeclaracionExportResult(
        draft_id="d",
        modelo="130",
        period=_PERIOD,
        format=DeclaracionExportFormat.FICHERO_BOE,
        output_path=_OTHER_EXPORT_PATH,
        byte_size=0,
        file_sha256=_HEX_DIGEST,
        exported_at=datetime(2026, 5, 3, tzinfo=UTC),
        narrative=_narrative(),
    )
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        receipt.byte_size = 1


def test_verify_result_match_carries_no_mismatched_casilla_ids() -> None:
    verdict = DeclaracionVerifyResult(
        draft_id="d-130-2026Q1",
        file_path=_EXPORT_PATH,
        verdict=DeclaracionVerifyVerdict.MATCH,
        mismatched_casilla_ids=(),
        file_sha256=_HEX_DIGEST,
        verified_at=datetime(2026, 5, 3, tzinfo=UTC),
        narrative=_narrative(),
    )
    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert verdict.mismatched_casilla_ids == ()


def test_verify_result_drift_lists_mismatched_casilla_ids() -> None:
    verdict = DeclaracionVerifyResult(
        draft_id="d",
        file_path=_OTHER_EXPORT_PATH,
        verdict=DeclaracionVerifyVerdict.DRIFT,
        mismatched_casilla_ids=("01", "07"),
        file_sha256=None,
        verified_at=datetime(2026, 5, 3, tzinfo=UTC),
        narrative=_narrative(),
    )
    assert verdict.mismatched_casilla_ids == ("01", "07")
    assert verdict.file_sha256 is None


def test_verify_result_rejects_legacy_casilla_list_keys() -> None:
    with pytest.raises(ValidationError) as raised:
        DeclaracionVerifyResult.model_validate(
            {
                "draft_id": "d",
                "file_path": _OTHER_EXPORT_PATH,
                "verdict": DeclaracionVerifyVerdict.DRIFT,
                "mismatched_casillas": ("01",),
                "unchecked_casillas": ("07",),
                "verified_at": datetime(2026, 5, 3, tzinfo=UTC),
                "narrative": _narrative(),
            },
        )

    message = str(raised.value)
    assert "mismatched_casillas" in message
    assert "unchecked_casillas" in message


def test_verify_result_rejects_blank_casilla_ids() -> None:
    with pytest.raises(ValueError, match=r"casilla|empty|at least 1 character"):
        DeclaracionVerifyResult(
            draft_id="d",
            file_path=_OTHER_EXPORT_PATH,
            verdict=DeclaracionVerifyVerdict.DRIFT,
            mismatched_casilla_ids=("", "07"),
            verified_at=datetime(2026, 5, 3, tzinfo=UTC),
            narrative=_narrative(),
        )


def test_verify_result_rejects_padded_casilla_ids() -> None:
    with pytest.raises(ValueError, match=r"casilla|whitespace|leading|trailing"):
        DeclaracionVerifyResult(
            draft_id="d",
            file_path=_OTHER_EXPORT_PATH,
            verdict=DeclaracionVerifyVerdict.DRIFT,
            mismatched_casilla_ids=(" 01 ",),
            verified_at=datetime(2026, 5, 3, tzinfo=UTC),
            narrative=_narrative(),
        )


def test_verify_result_rejects_short_digest() -> None:
    with pytest.raises(ValueError, match=r"file_sha256|hex|length"):
        DeclaracionVerifyResult(
            draft_id="d",
            file_path=_OTHER_EXPORT_PATH,
            verdict=DeclaracionVerifyVerdict.MATCH,
            file_sha256="abc",
            verified_at=datetime(2026, 5, 3, tzinfo=UTC),
            narrative=_narrative(),
        )


def test_export_writes_modelo_130_registry_layout(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    output = tmp_path / "modelo-130.txt"
    provider = _schema_provider()

    receipt = export_draft(
        draft,
        output_path=output,
        headers=_modelo_130_export_headers(),
        schema_provider=provider,
    )

    payload = output.read_bytes()
    parsed = parse_export_payload(provider.get_subview(draft.modelo).export_layouts[0], payload)
    exported_values = {entry.casilla_id: entry.value for entry in parsed.casillas if entry.casilla_id is not None}
    draft_values = {entry.casilla_id: entry.value for entry in draft.values}

    assert receipt.byte_size == len(payload)
    assert receipt.file_sha256
    assert receipt.period == draft.period
    assert receipt.model_dump(mode="json")["period"] == {"filing_year": 2026, "code": "1T"}
    assert receipt.casilla_provenance
    comparable = {
        casilla_id: Decimal(str(expected))
        for casilla_id, expected in draft_values.items()
        if casilla_id in exported_values and expected is not None
    }
    assert comparable
    assert all(exported_values[casilla_id] == expected for casilla_id, expected in comparable.items())
    exported_provenance = {entry.casilla_id: entry for entry in receipt.casilla_provenance}
    draft_provenance = {entry.casilla_id: entry for entry in draft.casilla_provenance}
    assert set(exported_values).issubset(exported_provenance)
    assert all(exported_provenance[casilla_id] == draft_provenance[casilla_id] for casilla_id in exported_values)


def _approved_modelo_100_xml_dictionary_draft() -> ModeloDraft:
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    collection = provider.get_collection("100")
    now = datetime.now(UTC).replace(microsecond=0)
    values = (
        ModeloValue(
            casilla_id="0003",
            value=Decimal("12000.25"),
            kind=ModeloValueKind.LITERAL,
            source="test registry value",
        ),
        ModeloValue(
            casilla_id="0596",
            value=Decimal("1500.50"),
            kind=ModeloValueKind.INHERITED,
            source="test observed withholding",
        ),
        ModeloValue(
            casilla_id="0604",
            value=Decimal("325.75"),
            kind=ModeloValueKind.COMPUTED,
            source="test relation fold",
        ),
        ModeloValue(
            casilla_id="0609",
            value=Decimal("1826.25"),
            kind=ModeloValueKind.COMPUTED,
            source="test total payments",
        ),
        ModeloValue(
            casilla_id="0610",
            value=Decimal("-12.34"),
            kind=ModeloValueKind.COMPUTED,
            source="test cuota diferencial",
        ),
    )
    provenance_by_id = {
        casilla.casilla_id: ModeloCasillaProvenance(
            casilla_id=casilla.casilla_id,
            formula_id=casilla.formula,
            legal_refs=casilla.legal_refs,
            source_refs=casilla.source_refs,
        )
        for casilla in collection.all()
    }
    return ModeloDraft(
        draft_id="modelo-100-xml-dictionary-test",
        modelo="100",
        period=Period.from_year_and_code(2024, "0A"),
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(
            modelo="100",
            revision_id="2024",
            modelo_year=2024,
            period="0A",
        ),
        status=ModeloDraftStatus.APROBADO,
        values=values,
        binding_values=(),
        casilla_provenance=tuple(provenance_by_id[value.casilla_id] for value in values),
        findings=(),
        created_at=now,
        updated_at=now,
        schema_version=collection.schema_version,
    )


def _official_modelo_100_2024_dictionary_paths() -> dict[str, str]:
    dictionary = bundled_path(
        "corpus",
        "aeat_official",
        "disenos_registro",
        "modelo_100",
        "files",
        "08-100-diccionario-declaracion-individual-ejercicio-2024-actualizado-29-01-2026-393-kb-otros-fi.properties",
    )
    paths: dict[str, str] = {}
    for line in dictionary.read_text(encoding="cp1252").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        _field, _, payload = line.partition("=")
        parts = payload.split("][")
        if len(parts) < 3:
            continue
        path = parts[0].lstrip("[")
        casilla = parts[2].rstrip("]")
        if casilla.isdigit():
            paths[casilla] = path
    return paths


def _xml_value(root: ElementTree.Element[str], absolute_path: str) -> str:
    current = root
    for index, part in enumerate(part for part in absolute_path.strip("/").split("/") if part):
        if index == 0 and part == root.tag:
            continue
        match = next((child for child in current if child.tag == part), None)
        assert match is not None, f"missing XML dictionary path {absolute_path!r}"
        current = match
    assert current.text is not None
    return current.text


def test_export_writes_modelo_100_xml_dictionary_layout(tmp_path: Path) -> None:
    draft = _approved_modelo_100_xml_dictionary_draft()
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    output = tmp_path / "modelo-100-2024.xml"

    receipt = export_draft(
        draft,
        output_path=output,
        headers={"surnames": "MARTA BLANK", "name": "STATE"},
        schema_provider=provider,
    )

    payload = output.read_bytes()
    layout = provider.get_subview("100").export_layouts[0]
    root = DefusedElementTree.fromstring(payload)
    official_paths = _official_modelo_100_2024_dictionary_paths()
    parsed = parse_export_payload(layout, payload, source_root=provider.source_root, sources=provider.sources)
    parsed_values = {entry.casilla_id: entry.value for entry in parsed.casillas if entry.casilla_id is not None}

    assert receipt.format is DeclaracionExportFormat.XML_DICTIONARY
    assert receipt.byte_size == len(payload)
    assert root.tag == "Declaracion"
    assert root.attrib["modelo"] == "100"
    assert root.attrib["ejercicio"] == "2024"
    assert root.attrib["periodo"] == "0A"
    assert root.attrib["versionxsd"] in _official_modelo_100_2024_xsd_versions()
    assert root.attrib["{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation"].endswith(
        "Renta2024.xsd",
    )
    assert _xml_value(root, official_paths["0003"]) == "12000.25"
    assert _xml_value(root, official_paths["0596"]) == "1500.50"
    assert _xml_value(root, official_paths["0604"]) == "325.75"
    assert _xml_value(root, official_paths["0609"]) == "1826.25"
    assert _xml_value(root, official_paths["0610"]) == "-12.34"
    assert parsed_values["0003"] == Decimal("12000.25")
    assert parsed_values["0596"] == Decimal("1500.50")
    assert parsed_values["0604"] == Decimal("325.75")
    assert parsed_values["0609"] == Decimal("1826.25")
    assert parsed_values["0610"] == Decimal("-12.34")
    assert verify_export(draft, file_path=output, schema_provider=provider).verdict is DeclaracionVerifyVerdict.MATCH


def _official_modelo_100_2024_xsd_versions() -> set[str]:
    xsd = bundled_path(
        "corpus",
        "aeat_official",
        "disenos_registro",
        "modelo_100",
        "files",
        "29-100-esquema-xsd-ejercicio-2024-actualizado-19-01-2026-747-kb-ejecutable.xsd",
    )
    root = DefusedElementTree.parse(xsd).getroot()
    versions: set[str] = set()
    for simple_type in root.iter("{http://www.w3.org/2001/XMLSchema}simpleType"):
        if simple_type.attrib.get("name") != "tipo_VersionXSD":
            continue
        versions.update(
            enumeration.attrib["value"]
            for enumeration in simple_type.iter("{http://www.w3.org/2001/XMLSchema}enumeration")
        )
    assert versions
    assert any(
        element.attrib.get("name") == "Declaracion"
        for element in root.iter("{http://www.w3.org/2001/XMLSchema}element")
    )
    return versions


def test_export_and_verify_build_model_scoped_provider_when_omitted(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    output = tmp_path / "modelo-130.txt"

    receipt = export_draft(
        draft,
        output_path=output,
        headers=_modelo_130_export_headers(),
    )
    verdict = verify_export(draft, file_path=output)

    assert receipt.modelo == "130"
    assert receipt.byte_size == len(output.read_bytes())
    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH


def test_export_refuses_modelo_without_registry_layout(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    provider = _provider_without_export_layout(_schema_provider(), draft.modelo)
    output = tmp_path / "modelo-130.txt"

    with pytest.raises(FilingExportError) as exc_info:
        export_draft(
            draft,
            output_path=output,
            headers=_modelo_130_export_headers(),
            schema_provider=provider,
        )
    _assert_missing_export_layout_refusal(str(exc_info.value), draft.modelo)
    assert not output.exists()


def test_verify_reports_missing_for_modelo_without_registry_layout(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    provider = _provider_without_export_layout(_schema_provider(), draft.modelo)
    exported = tmp_path / "modelo-130.txt"
    exported.write_bytes(b"layout-less payload")

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    assert verdict.verdict is DeclaracionVerifyVerdict.MISSING
    assert verdict.narrative == "filing.export.missing_registry_layout"
    assert verdict.file_sha256 is not None
    assert verdict.mismatched_casilla_ids == ()


def test_export_writes_modelo_131_binding_derived_layout(tmp_path: Path) -> None:
    draft = _approved_modelo_131_registry_draft()
    output = tmp_path / "modelo-131.txt"
    provider = _schema_provider(filing_year=2026, period="1T", modelos=("131",))

    receipt = export_draft(
        draft,
        output_path=output,
        headers={"declaration_type": "I"},
        schema_provider=provider,
    )

    payload = output.read_bytes()
    parsed = parse_export_payload(provider.get_subview(draft.modelo).export_layouts[0], payload)
    values = {(entry.record_id, entry.binding_id): entry.value for entry in parsed.fields if entry.binding_id}

    assert receipt.modelo == "131"
    assert receipt.byte_size == len(payload)
    assert values[("modelo-131-page-01", "modelo-131.page1.110-113.actividad-1-epigrafe")] == "722"
    assert values[("modelo-131-page-01", "modelo-131.page1.114-130.actividad-1-rendimiento-neto")] == Decimal("1200.50")
    assert values[("modelo-131-dpa", "modelo-131.dpa.013-016.epigrafe-iae")] == "722"
    assert values[("modelo-131-dpa", "modelo-131.dpa.031-032.vehiculos-afectos")] == Decimal("2")
    assert values[("modelo-131-did", "modelo-131.did.012-045.iban")] == "ES9121000418450200051332"


def test_export_writes_modelo_131_historical_flat_layout(tmp_path: Path) -> None:
    draft = _approved_modelo_131_historical_registry_draft()
    output = tmp_path / "modelo-131-2023.txt"
    provider = _schema_provider(filing_year=2023, period="4T", modelos=("131",))

    receipt = export_draft(
        draft,
        output_path=output,
        headers={"declaration_type": "I"},
        schema_provider=provider,
    )

    payload = output.read_bytes()
    parsed = parse_export_payload(provider.get_subview(draft.modelo).export_layouts[0], payload)
    exported_values = {entry.casilla_id: entry.value for entry in parsed.casillas}

    assert receipt.modelo == "131"
    assert receipt.byte_size == len(payload)
    assert exported_values == {
        _M131_HISTORICAL_01_CASILLA: Decimal("1000.00"),
        _M131_HISTORICAL_02_CASILLA: Decimal("20.00"),
        _M131_HISTORICAL_03_CASILLA: Decimal("500.00"),
        _M131_HISTORICAL_04_CASILLA: Decimal("10.00"),
        _M131_HISTORICAL_05_CASILLA: Decimal("250.00"),
        _M131_HISTORICAL_06_CASILLA: Decimal("5.00"),
        _M131_HISTORICAL_07_CASILLA: Decimal("35.00"),
        _M131_HISTORICAL_08_CASILLA: Decimal("3.00"),
        _M131_HISTORICAL_09_CASILLA: Decimal("2.00"),
        _M131_HISTORICAL_10_CASILLA: Decimal("30.00"),
        _M131_HISTORICAL_11_CASILLA: Decimal("1.00"),
        _M131_HISTORICAL_12_CASILLA: Decimal("0.50"),
        _M131_HISTORICAL_13_CASILLA: Decimal("28.50"),
        _M131_HISTORICAL_14_CASILLA: Decimal("0.25"),
        _M131_HISTORICAL_15_CASILLA: Decimal("28.25"),
    }


@pytest.mark.parametrize(("filing_year", "binding_prefix"), ((2024, "modelo-131-2024"), (2025, "modelo-131-2025")))
def test_export_writes_modelo_131_year_scoped_binding_layouts(
    tmp_path: Path,
    filing_year: int,
    binding_prefix: str,
) -> None:
    draft = _approved_modelo_131_year_scoped_registry_draft(filing_year, binding_prefix)
    output = tmp_path / f"modelo-131-{filing_year}.txt"
    provider = _schema_provider(filing_year=filing_year, period="1T", modelos=("131",))

    receipt = export_draft(
        draft,
        output_path=output,
        headers={"declaration_type": "I"},
        schema_provider=provider,
    )

    payload = output.read_bytes()
    parsed = parse_export_payload(provider.get_subview(draft.modelo).export_layouts[0], payload)
    values = {entry.binding_id: entry.value for entry in parsed.fields if entry.binding_id}

    assert receipt.modelo == "131"
    assert receipt.byte_size == len(payload)
    assert values[f"{binding_prefix}.page1.110-113.actividad-1-epigrafe"] == "722"
    assert values[f"{binding_prefix}.page1.114-130.actividad-1-rendimiento-neto"] == Decimal("1200.50")
    assert values[f"{binding_prefix}.dpa.013-016.epigrafe-iae"] == "722"
    assert values[f"{binding_prefix}.dpa.031-032.vehiculos-afectos"] == Decimal("2")
    assert values[f"{binding_prefix}.did.012-045.iban"] == "ES9121000418450200051332"


def test_export_omits_modelo_131_direct_debit_record_without_iban(tmp_path: Path) -> None:
    draft = _approved_modelo_131_registry_draft_without_direct_debit()
    output = tmp_path / "modelo-131.txt"
    provider = _schema_provider(filing_year=2026, period="1T", modelos=("131",))

    export_draft(
        draft,
        output_path=output,
        headers={"declaration_type": "I"},
        schema_provider=provider,
    )

    parsed = parse_export_payload(provider.get_subview(draft.modelo).export_layouts[0], output.read_bytes())

    assert not any(entry.record_id == "modelo-131-did" for entry in parsed.fields)


def test_export_rejects_modelo_131_direct_debit_without_positive_payable(tmp_path: Path) -> None:
    draft = _approved_modelo_131_zero_payable_direct_debit_draft()

    with pytest.raises(ValueError, match="requires positive casilla '15'"):
        export_draft(
            draft,
            output_path=tmp_path / "modelo-131.txt",
            headers={"declaration_type": "I"},
            schema_provider=_schema_provider(filing_year=2026, period="1T", modelos=("131",)),
        )


def test_export_writes_signed_positive_money_with_blank_sign_slot(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    output = tmp_path / "modelo-130.txt"
    provider = _schema_provider()

    export_draft(
        draft,
        output_path=output,
        headers=_modelo_130_export_headers(),
        schema_provider=provider,
    )
    layout = provider.get_subview(draft.modelo).export_layouts[0]
    payload = output.read_bytes()
    field_slice = _field_slice(layout, "modelo-130-page-01", "modelo-130-casilla-03")
    rendered = payload[field_slice].decode("latin-1")

    assert rendered[0] == " "
    assert rendered[1:] == "7500".zfill(len(rendered) - 1)
    assert parse_export_payload(layout, payload).casillas


def test_export_writes_modelo_200_negative_cuota_diferencial_as_signed_money(tmp_path: Path) -> None:
    """A verified-clean M200 negative cuota diferencial must reach fichero bytes.

    The 2025 Diseño de Registro for page 14B publishes casilla 00611 as
    type ``N`` (numeric signed), position 711, length 17. This test drives
    the real M200 registry calculation through ``build_draft``: accounting
    profit 200 produces cuota 46, and 450 of Modelo 202 pagos fraccionados
    produces ``DP200014B:00611 = -404.00``. Export must render that amount
    with the signed-money ``N`` marker in the first byte, then parse back
    through the registry layout.
    """
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("200",))
    draft = build_draft(
        modelo="200",
        period=Period.from_year_and_code(2024, "0A"),
        profile=ModeloOperatorProfile(
            tax_id="B12345674",
            display_name="Emilio Export Test SL",
        ),
        inputs={
            _M200_GRUPO_FISCAL_CASILLA: Decimal("0"),
            _M200_RESULTADO_CONTABLE_CASILLA: Decimal("200.00"),
            _M200_CORRECCIONES_AUMENTO_CASILLA: Decimal("0.00"),
            _M200_CORRECCIONES_DISMINUCION_CASILLA: Decimal("0.00"),
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("500000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-profile-legal-entity-form": "sl",
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-rel-202-pagos-fraccionados": Decimal("450"),
            "modelo-200-2024-rel-202-pagos-fraccionados-40-2": Decimal("0"),
        },
        schema_provider=provider,
    )
    assert draft.findings == ()
    approved = draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})
    output = tmp_path / "modelo-200.txt"

    export_draft(
        approved,
        output_path=output,
        headers={
            "declaration_type": "D",
            "surnames": "EMILIO EXPORT TEST SL",
            "name": "EMILIO EXPORT TEST SL",
            "program_version": "A001",
            "presenter_nif": "B12345674",
        },
        schema_provider=provider,
    )

    payload = output.read_bytes()
    layout = provider.get_subview(approved.modelo).export_layouts[0]
    parsed = parse_export_payload(layout, payload)
    exported_values = {entry.casilla_id: entry.value for entry in parsed.casillas if entry.casilla_id is not None}
    field_slice = _field_slice(layout, "modelo-200-page-014b", "modelo-200-page-014b-casilla-00611")
    rendered = payload[field_slice].decode("latin-1")

    assert exported_values[_M200_CUOTA_DIFERENCIAL_CASILLA] == Decimal("-404.00")
    assert rendered == "N" + "40400".zfill(16)
    assert verify_export(approved, file_path=output, schema_provider=provider).verdict is DeclaracionVerifyVerdict.MATCH


def test_export_writes_modelo_111_registry_layout(tmp_path: Path) -> None:
    draft = _approved_modelo_111_registry_draft()
    output = tmp_path / "modelo-111.txt"
    provider = _schema_provider(modelos=("111",))

    receipt = export_draft(
        draft,
        output_path=output,
        headers=_modelo_111_export_headers(),
        schema_provider=provider,
    )

    payload = output.read_bytes()
    parsed = parse_export_payload(provider.get_subview(draft.modelo).export_layouts[0], payload)
    exported_values = {entry.casilla_id: entry.value for entry in parsed.casillas}
    layout = provider.get_subview(draft.modelo).export_layouts[0]
    record_28 = next(
        record for record in layout.records if any(field.id == "modelo-111-casilla-28" for field in record.fields)
    )
    record_30 = next(
        record for record in layout.records if any(field.id == "modelo-111-casilla-30" for field in record.fields)
    )

    assert receipt.modelo == "111"
    assert receipt.byte_size == len(payload)
    assert exported_values[_M111_RETENCIONES_TOTAL_CASILLA] == Decimal("556.25")
    assert exported_values[_M111_RESULTADO_CASILLA] == Decimal("516.25")
    assert payload[_field_slice(layout, record_28.id, "modelo-111-casilla-28")] == b"00000000000055625"
    assert payload[_field_slice(layout, record_30.id, "modelo-111-casilla-30")] == b"00000000000051625"
    assert (
        payload[_field_slice(layout, "modelo-111-envelope-footer", "modelo-111-envelope-close")]
        == b"</T111020261T0000>"
    )


def test_export_writes_modelo_115_registry_layout(tmp_path: Path) -> None:
    draft = _approved_modelo_115_registry_draft()
    output = tmp_path / "modelo-115.txt"
    provider = _schema_provider(modelos=("115",))

    receipt = export_draft(
        draft,
        output_path=output,
        headers=_modelo_115_export_headers(),
        schema_provider=provider,
    )

    payload = output.read_bytes()
    parsed = parse_export_payload(provider.get_subview(draft.modelo).export_layouts[0], payload)
    exported_values = {entry.casilla_id: entry.value for entry in parsed.casillas}

    assert receipt.modelo == "115"
    assert receipt.byte_size == len(payload)
    assert exported_values == {
        _M115_PERCEPTORES_CASILLA: Decimal("1"),
        _M115_BASE_CASILLA: Decimal("1250.50"),
        _M115_RETENCIONES_CASILLA: Decimal("237.60"),
        _M115_PREVIOUS_RESULT_CASILLA: Decimal("10.00"),
        _M115_RESULTADO_CASILLA: Decimal("227.60"),
    }


def test_export_writes_modelo_123_registry_layout(tmp_path: Path) -> None:
    draft = _approved_modelo_123_registry_draft()
    output = tmp_path / "modelo-123.txt"
    provider = _schema_provider(modelos=("123",))

    receipt = export_draft(
        draft,
        output_path=output,
        headers=_modelo_123_export_headers(),
        schema_provider=provider,
    )

    payload = output.read_bytes()
    parsed = parse_export_payload(provider.get_subview(draft.modelo).export_layouts[0], payload)
    exported_values = {entry.casilla_id: entry.value for entry in parsed.casillas}

    assert receipt.modelo == "123"
    assert receipt.byte_size == len(payload)
    assert exported_values[_M123_PERCEPTORES_CASILLA] == Decimal("5")
    assert exported_values[_M123_BASE_CASILLA] == Decimal("1201.00")
    assert exported_values[_M123_RETENCIONES_CASILLA] == Decimal("228.19")
    assert exported_values[_M123_INGRESOS_CUENTA_CASILLA] == Decimal("235.69")
    assert exported_values[_M123_RESULTADO_CASILLA] == Decimal("223.44")


def test_export_writes_modelo_123_2019_registry_layout(tmp_path: Path) -> None:
    draft = _approved_modelo_123_2019_registry_draft()
    output = tmp_path / "modelo-123-2023.txt"
    provider = _schema_provider(filing_year=2023, period="4T", modelos=("123",))

    receipt = export_draft(
        draft,
        output_path=output,
        headers=_modelo_123_2019_export_headers(),
        schema_provider=provider,
    )

    payload = output.read_bytes()
    parsed = parse_export_payload(provider.get_subview(draft.modelo).export_layouts[0], payload)
    exported_values = {entry.casilla_id: entry.value for entry in parsed.casillas}

    assert receipt.modelo == "123"
    assert receipt.byte_size == len(payload)
    assert exported_values == {
        _M123_2019_2023_PERCEPTORES_CASILLA: Decimal("5"),
        _M123_2019_2023_BASE_CASILLA: Decimal("1201.00"),
        _M123_2019_2023_RETENCIONES_CASILLA: Decimal("228.19"),
        _M123_2019_2023_PREVIOUS_RESULT_CASILLA: Decimal("0.00"),
        _M123_2019_2023_INGRESOS_CUENTA_CASILLA: Decimal("7.50"),
        _M123_2019_2023_TOTAL_RETENCIONES_CASILLA: Decimal("235.69"),
        _M123_2019_2023_MINORACION_CASILLA: Decimal("12.25"),
        _M123_2019_2023_RESULTADO_CASILLA: Decimal("223.44"),
    }


def test_export_requires_declared_header_values(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    with pytest.raises(ValueError, match="declaration_type"):
        export_draft(
            draft,
            output_path=tmp_path / "modelo-130.txt",
            headers={"surnames": "EXPORT TEST", "name": "ANA"},
            schema_provider=_schema_provider(),
        )


@pytest.mark.parametrize(
    ("headers", "missing_header"),
    (
        (
            {"declaration_type": "", "surnames": "EXPORT TEST", "name": "ANA"},
            "declaration_type",
        ),
        (
            {"declaration_type": "I", "surnames": "", "name": "ANA"},
            "surnames",
        ),
        (
            {"declaration_type": "I", "surnames": "EXPORT TEST", "name": " "},
            "name",
        ),
    ),
    ids=("declaration-type", "surnames", "name"),
)
def test_export_rejects_blank_required_header_values(
    tmp_path: Path,
    headers: dict[str, str],
    missing_header: str,
) -> None:
    draft = _approved_registry_draft()
    with pytest.raises(ValueError, match=missing_header):
        export_draft(
            draft,
            output_path=tmp_path / "modelo-130.txt",
            headers=headers,
            schema_provider=_schema_provider(),
        )


def test_verify_reports_unchecked_reserved_or_derived_casillas(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    exported = tmp_path / "modelo-130.txt"
    provider = _schema_provider()
    exported.write_bytes(_modelo_130_export_payload())

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert verdict.mismatched_casilla_ids == ()
    assert verdict.unchecked_casilla_ids == ("saldo-negativo-fin-periodo",)


@pytest.mark.parametrize("case", _EXPORT_VERIFY_MATCH_CASES)
def test_verify_matches_exported_registry_layouts(tmp_path: Path, case: _ExportVerifyMatchCase) -> None:
    draft = case.draft_factory()
    exported = tmp_path / case.output_name
    provider = _schema_provider(filing_year=case.filing_year, period=case.period, modelos=case.modelos)
    exported.write_bytes(case.payload_factory())

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert verdict.file_sha256 is not None
    assert verdict.mismatched_casilla_ids == ()


def test_verify_reports_missing_for_malformed_export_payload(tmp_path: Path) -> None:
    draft = _approved_modelo_111_registry_draft()
    exported = tmp_path / "modelo-111.txt"
    provider = _schema_provider(modelos=("111",))
    exported.write_bytes(_modelo_111_export_payload()[:20])

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    assert verdict.verdict is DeclaracionVerifyVerdict.MISSING
    assert verdict.mismatched_casilla_ids == ()


def test_verify_reports_casilla_drift_for_modelo_130_layout(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    provider = _schema_provider()
    exported = tmp_path / "modelo-130.txt"
    exported.write_bytes(_modelo_130_export_payload())
    layout = provider.get_subview(draft.modelo).export_layouts[0]
    casilla_values = {entry.casilla_id: Decimal(str(entry.value)) for entry in draft.values}
    record, field = next(
        (record, field)
        for record in sorted(layout.records, key=lambda item: item.order)
        for field in record.fields
        if field.kind == CasillaFieldKind.CASILLA
        and field.casilla_id in casilla_values
        and casilla_values[field.casilla_id] != Decimal("0.01")
        and field.length is not None
    )
    payload = bytearray(exported.read_bytes())
    field_slice = _field_slice(layout, record.id, field.id)
    field_length = field.length
    assert field_length is not None
    payload[field_slice] = ("0" * (field_length - 1) + "1").encode("ascii")
    exported.write_bytes(payload)

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    assert verdict.verdict is DeclaracionVerifyVerdict.DRIFT
    field_casilla = field.casilla_id
    assert field_casilla is not None
    assert verdict.mismatched_casilla_ids == (field_casilla,)
    draft_provenance = {entry.casilla_id: entry for entry in draft.casilla_provenance}
    assert verdict.mismatched_casilla_provenance == (draft_provenance[field_casilla],)
    assert verdict.mismatched_casilla_provenance[0].legal_refs
    assert verdict.mismatched_casilla_provenance[0].source_refs


def test_export_payload_parser_rejects_layout_literal_drift(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    provider = _schema_provider()
    exported = tmp_path / "modelo-130.txt"
    exported.write_bytes(_modelo_130_export_payload())
    layout = provider.get_subview(draft.modelo).export_layouts[0]
    record, field = next(
        (record, field)
        for record in sorted(layout.records, key=lambda item: item.order)
        for field in record.fields
        if field.kind == CasillaFieldKind.LITERAL
    )
    payload = bytearray(exported.read_bytes())
    field_slice = _field_slice(layout, record.id, field.id)
    payload[field_slice.start] = ord("?")

    with pytest.raises(RegistryValidationError, match="literal field"):
        parse_export_payload(layout, bytes(payload))
