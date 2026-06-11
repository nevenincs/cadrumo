"""Unit tests for the typed declaration-export / declaration-verify surface."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core import Period
from ....domain.calculations.registry import ExportLayoutDefinition, RegistryValidationError, parse_export_payload
from ....domain.filing import FilingExportError
from ....domain.submission import ModeloDraftStatus
from .. import (
    DeclaracionExportFormat,
    DeclaracionExportResult,
    DeclaracionVerifyResult,
    DeclaracionVerifyVerdict,
    ModeloOperatorProfile,
    build_draft,
    build_runtime_schema_provider,
    export_draft,
    verify_export,
)
from ..runtime import RegistrySchemaProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_HEX_DIGEST = "a" * 64
_PERIOD = Period.from_year_and_code(2026, "1T")
_EXPORT_PATH = Path("exports/m130-2026Q1.txt")
_OTHER_EXPORT_PATH = Path("exports/x.txt")
_SCHEMA_PROVIDER_CACHE: dict[tuple[int | None, str | None, tuple[str, ...]], RegistrySchemaProvider] = {}


def _narrative() -> str:
    narrative: str = "filing.test_export.narrative"
    return narrative


def _schema_provider(
    *,
    filing_year: int | None = None,
    period: str | None = None,
    modelos: tuple[str, ...] = ("130",),
) -> RegistrySchemaProvider:
    """Return a real registry schema provider, cached per period selector."""
    selected_modelos = tuple(sorted(modelos))
    key = (filing_year, period, selected_modelos)
    provider = _SCHEMA_PROVIDER_CACHE.get(key)
    if provider is None:
        typed_period = (
            Period.from_year_and_code(filing_year, period)
            if filing_year is not None and period is not None
            else None
        )
        provider = build_runtime_schema_provider(
            filing_year=filing_year,
            period=typed_period,
            modelos=selected_modelos,
        )
        _SCHEMA_PROVIDER_CACHE[key] = provider
    return provider


def _provider_without_export_layout(provider: RegistrySchemaProvider, modelo: str) -> RegistrySchemaProvider:
    subview = provider.get_subview(modelo)
    return RegistrySchemaProvider(
        collections=provider.collections,
        subviews={
            **provider.subviews,
            modelo: replace(subview, export_layout_ids=(), export_layouts=()),
        },
    )


def _approved_registry_draft():
    draft = build_draft(
        modelo="130",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            "01": Decimal("100"),
            "02": Decimal("25"),
            "05": Decimal("0"),
            "06": Decimal("0"),
            "08": Decimal("0"),
            "10": Decimal("0"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        schema_provider=_schema_provider(),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def test_build_draft_populates_registry_casilla_provenance() -> None:
    draft = _approved_registry_draft()
    collection = _schema_provider().get_collection(draft.modelo)
    registry_provenance = {
        casilla.id: (tuple(casilla.legal_refs), tuple(casilla.source_refs))
        for casilla in collection.all()
        if casilla.legal_refs and casilla.source_refs
    }
    draft_provenance = {entry.casilla_id: entry for entry in draft.casilla_provenance}

    assert registry_provenance
    assert set(registry_provenance).issubset(draft_provenance)
    for casilla_id, (legal_refs, source_refs) in registry_provenance.items():
        assert draft_provenance[casilla_id].legal_refs == legal_refs
        assert draft_provenance[casilla_id].source_refs == source_refs


def _modelo_130_export_headers() -> dict[str, str]:
    return {
        "declaration_type": "I",
        "surnames": "EXPORT TEST",
        "name": "ANA",
        "program_version": "A001",
        "presenter_nif": "A12345678",
    }


def _approved_modelo_131_registry_draft():
    draft = build_draft(
        modelo="131",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            "03": Decimal("1000"),
            "05": Decimal("500"),
            "modelo-131.page1.110-113.actividad-1-epigrafe": "722",
            "modelo-131.page1.114-130.actividad-1-rendimiento-neto": Decimal("1200.50"),
            "modelo-131.dpa.013-016.epigrafe-iae": ["722"],
            "modelo-131.dpa.031-032.vehiculos-afectos": {"1": "2"},
            "modelo-131.did.012-045.iban": "ES9121000418450200051332",
        },
        schema_provider=_schema_provider(filing_year=2026, period="1T", modelos=("131",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _approved_modelo_131_registry_draft_without_direct_debit():
    draft = build_draft(
        modelo="131",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            "03": Decimal("1000"),
            "05": Decimal("500"),
            "modelo-131.page1.110-113.actividad-1-epigrafe": "722",
            "modelo-131.page1.114-130.actividad-1-rendimiento-neto": Decimal("1200.50"),
            "modelo-131.dpa.013-016.epigrafe-iae": ["722"],
            "modelo-131.dpa.031-032.vehiculos-afectos": {"1": "2"},
        },
        schema_provider=_schema_provider(filing_year=2026, period="1T", modelos=("131",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _approved_modelo_131_zero_payable_direct_debit_draft():
    draft = build_draft(
        modelo="131",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            "03": Decimal("0"),
            "05": Decimal("0"),
            "modelo-131.did.012-045.iban": "ES9121000418450200051332",
        },
        schema_provider=_schema_provider(filing_year=2026, period="1T", modelos=("131",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _approved_modelo_131_year_scoped_registry_draft(filing_year: int, binding_prefix: str):
    draft = build_draft(
        modelo="131",
        period=Period.from_year_and_code(filing_year, "1T"),
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            "03": Decimal("1000"),
            "05": Decimal("500"),
            f"{binding_prefix}.page1.110-113.actividad-1-epigrafe": "722",
            f"{binding_prefix}.page1.114-130.actividad-1-rendimiento-neto": Decimal("1200.50"),
            f"{binding_prefix}.dpa.013-016.epigrafe-iae": ["722"],
            f"{binding_prefix}.dpa.031-032.vehiculos-afectos": {"1": "2"},
            f"{binding_prefix}.did.012-045.iban": "ES9121000418450200051332",
        },
        schema_provider=_schema_provider(filing_year=filing_year, period="1T", modelos=("131",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _approved_modelo_131_historical_registry_draft():
    provider = _schema_provider(filing_year=2023, period="4T", modelos=("131",))
    draft = build_draft(
        modelo="131",
        period=Period.from_year_and_code(2023, "4T"),
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            "01": Decimal("1000"),
            "02": Decimal("20"),
            "03": Decimal("500"),
            "05": Decimal("250"),
            "08": Decimal("3"),
            "09": Decimal("2"),
            "modelo-131-2019-2023-resultados-negativos-anteriores": Decimal("1"),
            "12": Decimal("0.50"),
            "14": Decimal("0.25"),
        },
        schema_provider=provider,
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _approved_modelo_111_registry_draft():
    draft = build_draft(
        modelo="111",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            "03": Decimal("180.25"),
            "06": Decimal("12.10"),
            "09": Decimal("300.00"),
            "12": Decimal("14.40"),
            "15": Decimal("25.00"),
            "18": Decimal("0.50"),
            "21": Decimal("7.00"),
            "24": Decimal("8.00"),
            "27": Decimal("9.00"),
            "29": Decimal("40.00"),
        },
        schema_provider=_schema_provider(modelos=("111",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _modelo_111_export_headers() -> dict[str, str]:
    return {
        "declaration_type": "I",
        "surnames": "EXPORT TEST",
        "name": "ANA",
        "program_version": "A001",
        "presenter_nif": "A12345678",
    }


def _approved_modelo_115_registry_draft():
    draft = build_draft(
        modelo="115",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            "01": Decimal("1"),
            "02": Decimal("1250.50"),
            "04": Decimal("10.00"),
        },
        schema_provider=_schema_provider(modelos=("115",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _modelo_115_export_headers() -> dict[str, str]:
    return {
        "declaration_type": "I",
        "legal_name": "EXPORT TEST",
        "first_name": "ANA",
        "program_version": "A001",
        "presenter_tax_id": "A12345678",
    }


def _approved_modelo_123_registry_draft():
    draft = build_draft(
        modelo="123",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            "01": Decimal("2"),
            "02": Decimal("3"),
            "04": Decimal("1000.25"),
            "05": Decimal("200.75"),
            "07": Decimal("190.05"),
            "08": Decimal("38.14"),
            "10": Decimal("0"),
            "11": Decimal("7.50"),
            "13": Decimal("12.25"),
        },
        schema_provider=_schema_provider(modelos=("123",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _modelo_123_export_headers() -> dict[str, str]:
    return {
        "declaration_type": "I",
        "legal_name": "EXPORT TEST",
        "program_version": "A001",
        "presenter_tax_id": "A12345678",
    }


def _approved_modelo_123_2019_registry_draft():
    provider = _schema_provider(filing_year=2023, period="4T", modelos=("123",))
    draft = build_draft(
        modelo="123",
        period=Period.from_year_and_code(2023, "4T"),
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            "01-legacy": Decimal("5"),
            "02-legacy": Decimal("1201.00"),
            "03-legacy": Decimal("228.19"),
            "04-legacy": Decimal("0"),
            "05-legacy": Decimal("7.50"),
            "07-legacy": Decimal("12.25"),
        },
        schema_provider=provider,
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _modelo_123_2019_export_headers() -> dict[str, str]:
    return {
        "declaration_type": "I",
        "surnames": "EXPORT TEST",
        "name": "ANA",
        "program_version": "A001",
        "presenter_tax_id": "A12345678",
    }


def test_format_enum_carries_cli_values() -> None:
    assert DeclaracionExportFormat.FICHERO_BOE.value == "fichero-boe"


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


def test_verify_result_match_carries_no_mismatched_casillas() -> None:
    verdict = DeclaracionVerifyResult(
        draft_id="d-130-2026Q1",
        file_path=_EXPORT_PATH,
        verdict=DeclaracionVerifyVerdict.MATCH,
        mismatched_casillas=(),
        file_sha256=_HEX_DIGEST,
        verified_at=datetime(2026, 5, 3, tzinfo=UTC),
        narrative=_narrative(),
    )
    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert verdict.mismatched_casillas == ()


def test_verify_result_drift_lists_mismatched_casillas() -> None:
    verdict = DeclaracionVerifyResult(
        draft_id="d",
        file_path=_OTHER_EXPORT_PATH,
        verdict=DeclaracionVerifyVerdict.DRIFT,
        mismatched_casillas=("01", "07"),
        file_sha256=None,
        verified_at=datetime(2026, 5, 3, tzinfo=UTC),
        narrative=_narrative(),
    )
    assert verdict.mismatched_casillas == ("01", "07")
    assert verdict.file_sha256 is None


def test_verify_result_rejects_blank_casilla_ids() -> None:
    with pytest.raises(ValueError, match=r"casilla|empty|at least 1 character"):
        DeclaracionVerifyResult(
            draft_id="d",
            file_path=_OTHER_EXPORT_PATH,
            verdict=DeclaracionVerifyVerdict.DRIFT,
            mismatched_casillas=("", "07"),
            verified_at=datetime(2026, 5, 3, tzinfo=UTC),
            narrative=_narrative(),
        )


def test_verify_result_rejects_padded_casilla_ids() -> None:
    with pytest.raises(ValueError, match=r"casilla|whitespace|leading|trailing"):
        DeclaracionVerifyResult(
            draft_id="d",
            file_path=_OTHER_EXPORT_PATH,
            verdict=DeclaracionVerifyVerdict.DRIFT,
            mismatched_casillas=(" 01 ",),
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

    with pytest.raises(FilingExportError, match="declares no export layout"):
        export_draft(
            draft,
            output_path=output,
            headers=_modelo_130_export_headers(),
            schema_provider=provider,
        )

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
    assert verdict.mismatched_casillas == ()


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
        "01": Decimal("1000.00"),
        "02": Decimal("20.00"),
        "03": Decimal("500.00"),
        "04": Decimal("10.00"),
        "05": Decimal("250.00"),
        "06": Decimal("5.00"),
        "07": Decimal("35.00"),
        "08": Decimal("3.00"),
        "09": Decimal("2.00"),
        "10": Decimal("30.00"),
        "11": Decimal("1.00"),
        "12": Decimal("0.50"),
        "13": Decimal("28.50"),
        "14": Decimal("0.25"),
        "15": Decimal("28.25"),
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
    assert exported_values["28"] == Decimal("556.25")
    assert exported_values["30"] == Decimal("516.25")
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
        "01": Decimal("1"),
        "02": Decimal("1250.50"),
        "03": Decimal("237.60"),
        "04": Decimal("10.00"),
        "05": Decimal("227.60"),
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
    assert exported_values["03"] == Decimal("5")
    assert exported_values["06"] == Decimal("1201.00")
    assert exported_values["09"] == Decimal("228.19")
    assert exported_values["12"] == Decimal("235.69")
    assert exported_values["14"] == Decimal("223.44")


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
        "01-legacy": Decimal("5"),
        "02-legacy": Decimal("1201.00"),
        "03-legacy": Decimal("228.19"),
        "04-legacy": Decimal("0.00"),
        "05-legacy": Decimal("7.50"),
        "06-legacy": Decimal("235.69"),
        "07-legacy": Decimal("12.25"),
        "08-legacy": Decimal("223.44"),
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


def test_verify_matches_exported_modelo_130_layout(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    exported = tmp_path / "modelo-130.txt"
    export_draft(
        draft,
        output_path=exported,
        headers=_modelo_130_export_headers(),
        schema_provider=_schema_provider(),
    )

    verdict = verify_export(draft, file_path=exported, schema_provider=_schema_provider())

    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert verdict.file_sha256 is not None
    assert verdict.mismatched_casillas == ()


def test_verify_reports_unchecked_reserved_or_derived_casillas(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    exported = tmp_path / "modelo-130.txt"
    provider = _schema_provider()
    export_draft(
        draft,
        output_path=exported,
        headers=_modelo_130_export_headers(),
        schema_provider=provider,
    )

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert verdict.mismatched_casillas == ()
    assert verdict.unchecked_casillas == ("saldo-negativo-fin-periodo",)


def test_verify_matches_exported_modelo_111_layout(tmp_path: Path) -> None:
    draft = _approved_modelo_111_registry_draft()
    exported = tmp_path / "modelo-111.txt"
    provider = _schema_provider(modelos=("111",))
    export_draft(
        draft,
        output_path=exported,
        headers=_modelo_111_export_headers(),
        schema_provider=provider,
    )

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert verdict.file_sha256 is not None
    assert verdict.mismatched_casillas == ()


def test_verify_matches_exported_modelo_115_layout(tmp_path: Path) -> None:
    draft = _approved_modelo_115_registry_draft()
    exported = tmp_path / "modelo-115.txt"
    provider = _schema_provider(modelos=("115",))
    export_draft(
        draft,
        output_path=exported,
        headers=_modelo_115_export_headers(),
        schema_provider=provider,
    )

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert verdict.file_sha256 is not None
    assert verdict.mismatched_casillas == ()


def test_verify_matches_exported_modelo_123_layout(tmp_path: Path) -> None:
    draft = _approved_modelo_123_registry_draft()
    exported = tmp_path / "modelo-123.txt"
    provider = _schema_provider(modelos=("123",))
    export_draft(
        draft,
        output_path=exported,
        headers=_modelo_123_export_headers(),
        schema_provider=provider,
    )

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert verdict.file_sha256 is not None
    assert verdict.mismatched_casillas == ()


def test_verify_matches_exported_modelo_123_2019_layout(tmp_path: Path) -> None:
    draft = _approved_modelo_123_2019_registry_draft()
    exported = tmp_path / "modelo-123-2023.txt"
    provider = _schema_provider(filing_year=2023, period="4T", modelos=("123",))
    export_draft(
        draft,
        output_path=exported,
        headers=_modelo_123_2019_export_headers(),
        schema_provider=provider,
    )

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert verdict.file_sha256 is not None
    assert verdict.mismatched_casillas == ()


def test_verify_reports_missing_for_malformed_export_payload(tmp_path: Path) -> None:
    draft = _approved_modelo_111_registry_draft()
    exported = tmp_path / "modelo-111.txt"
    provider = _schema_provider(modelos=("111",))
    export_draft(
        draft,
        output_path=exported,
        headers=_modelo_111_export_headers(),
        schema_provider=provider,
    )
    exported.write_bytes(exported.read_bytes()[:20])

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    assert verdict.verdict is DeclaracionVerifyVerdict.MISSING
    assert verdict.mismatched_casillas == ()


def test_verify_reports_casilla_drift_for_modelo_130_layout(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    provider = _schema_provider()
    exported = tmp_path / "modelo-130.txt"
    export_draft(
        draft,
        output_path=exported,
        headers=_modelo_130_export_headers(),
        schema_provider=provider,
    )
    layout = provider.get_subview(draft.modelo).export_layouts[0]
    casilla_values = {entry.casilla_id: Decimal(str(entry.value)) for entry in draft.values}
    record, field = next(
        (record, field)
        for record in sorted(layout.records, key=lambda item: item.order)
        for field in record.fields
        if field.kind == "casilla"
        and field.casilla in casilla_values
        and casilla_values[field.casilla] != Decimal("0.01")
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
    field_casilla = field.casilla
    assert field_casilla is not None
    assert verdict.mismatched_casillas == (field_casilla,)
    draft_provenance = {entry.casilla_id: entry for entry in draft.casilla_provenance}
    assert verdict.mismatched_casilla_provenance == (draft_provenance[field_casilla],)
    assert verdict.mismatched_casilla_provenance[0].legal_refs
    assert verdict.mismatched_casilla_provenance[0].source_refs


def test_export_payload_parser_rejects_layout_literal_drift(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    provider = _schema_provider()
    exported = tmp_path / "modelo-130.txt"
    export_draft(
        draft,
        output_path=exported,
        headers=_modelo_130_export_headers(),
        schema_provider=provider,
    )
    layout = provider.get_subview(draft.modelo).export_layouts[0]
    record, field = next(
        (record, field)
        for record in sorted(layout.records, key=lambda item: item.order)
        for field in record.fields
        if field.kind == "literal"
    )
    payload = bytearray(exported.read_bytes())
    field_slice = _field_slice(layout, record.id, field.id)
    payload[field_slice.start] = ord("?")

    with pytest.raises(RegistryValidationError, match="literal field"):
        parse_export_payload(layout, bytes(payload))


def _field_slice(layout: ExportLayoutDefinition, record_id: str, field_id: str) -> slice:
    cursor = 0
    for record in sorted(layout.records, key=lambda item: item.order):
        record_length = max((field.offset or 0) + (field.length or 0) - 1 for field in record.fields)
        if record.id == record_id:
            field = next(item for item in record.fields if item.id == field_id)
            if field.offset is None or field.length is None:
                raise AssertionError(f"export field {field.id!r} does not declare a fixed slice")
            start = cursor + field.offset - 1
            return slice(start, start + field.length)
        cursor += record_length
        if record.line_ending == "crlf":
            cursor += 2
        elif record.line_ending == "lf":
            cursor += 1
    raise AssertionError(f"export record {record_id!r} not found")


def _approved_modelo_303_registry_draft():
    """An approved modelo-303 draft built from the live registry snapshot.

    Modelo 303 (IVA quarterly self-assessment) is filed through the AEAT
    web form; its registry revision declares no fichero-BOE "importar
    datos" export layout. This makes it the real fixture for the
    no-layout export paths.
    """

    provider = _schema_provider(modelos=("303",))
    draft = build_draft(
        modelo="303",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def test_export_rejects_modelo_without_registry_export_layout(tmp_path: Path) -> None:
    """A modelo whose registry revision declares no export layout is refused.

    ``export_draft`` reaches for ``subview.export_layouts[0]``. A modelo
    with no layout must be refused with a typed ``FilingExportError``
    naming the gap — never crash with an ``IndexError`` off the empty
    layout tuple. The export layout is stripped via
    ``_provider_without_export_layout`` to exercise this path for a
    modelo that otherwise carries a layout.
    """

    draft = _approved_modelo_303_registry_draft()
    provider = _provider_without_export_layout(_schema_provider(modelos=("303",)), "303")
    with pytest.raises(FilingExportError, match="no export layout"):
        export_draft(
            draft,
            output_path=tmp_path / "modelo-303.txt",
            headers={"declaration_type": "I"},
            schema_provider=provider,
        )


def test_verify_reports_missing_for_modelo_without_registry_export_layout(tmp_path: Path) -> None:
    """``verify_export`` reports MISSING for a modelo with no export layout.

    With no layout to parse the file against, the verifier cannot
    compute a casilla diff. It must surface a closed ``MISSING`` verdict
    carrying the ``missing_registry_layout`` narrative rather than
    raising or fabricating a ``MATCH``. The export layout is stripped via
    ``_provider_without_export_layout`` to exercise this path for a
    modelo that otherwise carries a layout.
    """

    draft = _approved_modelo_303_registry_draft()
    provider = _provider_without_export_layout(_schema_provider(modelos=("303",)), "303")
    verdict = verify_export(
        draft,
        file_path=tmp_path / "modelo-303.txt",
        schema_provider=provider,
    )

    assert verdict.verdict is DeclaracionVerifyVerdict.MISSING
    assert verdict.narrative == "filing.export.missing_registry_layout"
    assert verdict.mismatched_casillas == ()


def test_verify_reports_unchecked_casillas_outside_the_parsed_set(tmp_path: Path) -> None:
    """verify_export surfaces draft casillas the export parser never re-reads.

    The modelo-130 draft carries casillas the fichero-BOE layout does not
    expose as deserialised currency fields (``saldo-negativo-fin-periodo``
    is a registry-named carry-forward casilla, not a numbered wire slot).
    A ``MATCH`` verdict must not silently imply full coverage: those
    casillas belong in ``unchecked_casillas``. This asserts the coverage
    contract — unchecked casillas are real draft casillas, are disjoint
    from both the parser-confirmed (``casilla_provenance``) set and the
    ``mismatched_casillas`` set, and the known carry-forward casilla is
    reported.
    """

    draft = _approved_registry_draft()
    provider = _schema_provider()
    exported = tmp_path / "modelo-130.txt"
    export_draft(
        draft,
        output_path=exported,
        headers=_modelo_130_export_headers(),
        schema_provider=provider,
    )

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    draft_casillas = {value.casilla_id for value in draft.values}
    confirmed = {entry.casilla_id for entry in verdict.casilla_provenance}
    unchecked = set(verdict.unchecked_casillas)

    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert unchecked, "modelo 130 has a non-currency casilla the layout never re-reads"
    assert unchecked <= draft_casillas
    assert unchecked.isdisjoint(confirmed)
    assert unchecked.isdisjoint(set(verdict.mismatched_casillas))
    # The registry carry-forward casilla is the concrete unchecked entry.
    assert "saldo-negativo-fin-periodo" in unchecked
