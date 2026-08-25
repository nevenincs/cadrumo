"""Shared support for declaration export tests."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from functools import cache
from pathlib import Path

from ....core import (
    CasillaId,
    Modelo,
    PaymentElection,
    Period,
    PriorDomiciliationElection,
    RefundElection,
    ResultDisposition,
    validated_casilla_id,
)
from cadrumo.domain.calculations.registry.schema import ExportLayoutDefinition
from ....domain.modelos import CalculationRevisionAmendmentKind
from ....domain.submission import ModeloDraftStatus
from .. import (
    AmendmentEvidence,
    FilingElectionFacts,
    FilingProducerSnapshot,
    GeneralFilingProfileFacts,
    Modelo111ProfileFacts,
    ModeloOperatorProfile,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_draft,
    build_filing_producer_snapshot,
    build_runtime_schema_provider,
)
from ..runtime import RegistrySchemaAccessor

_HEX_DIGEST = "a" * 64
_PERIOD = Period.from_year_and_code(2026, "1T")
_EXPORT_PATH = Path("exports/m130-2026Q1.txt")
_OTHER_EXPORT_PATH = Path("exports/x.txt")
_SCHEMA_PROVIDER_CACHE: dict[tuple[int | None, str | None, tuple[str, ...]], RegistrySchemaAccessor] = {}


def _typed_producer_snapshot(*, complementaria: bool = False) -> FilingProducerSnapshot:
    amendment = (
        AmendmentEvidence(
            kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            m303_rectificativa_motive=None,
            original_aeat_receipt="1234567890123",
        )
        if complementaria
        else None
    )
    return build_filing_producer_snapshot(
        modelo=Modelo.M111,
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None,
            given_name="Ana",
            surnames="Prueba",
            full_name="Ana Prueba",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=Modelo111ProfileFacts(colegio_concertado=False),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.NEGATIVA,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=amendment,
        m303_filing_facts=None,
        refund_account=None,
        charge_account=None,
    )


def _typed_modelo_131_producer_snapshot() -> FilingProducerSnapshot:
    return build_filing_producer_snapshot(
        modelo=Modelo.M131,
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None,
            given_name="Ana",
            surnames="Prueba",
            full_name="Ana Prueba",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=GeneralFilingProfileFacts(),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.INGRESO,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        m303_filing_facts=None,
        refund_account=None,
        charge_account=None,
    )


_M111_RETENCIONES_TOTAL_CASILLA, _M111_RESULTADO_CASILLA = (
    validated_casilla_id("28", surface="test_export.casilla"),
    validated_casilla_id("30", surface="test_export.casilla"),
)
_M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03", surface="test_export.casilla")
_M111_TRABAJO_ESPECIE_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="test_export.casilla")
_M111_ACTIVIDAD_DINERARIA_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("09", surface="test_export.casilla")
_M111_ACTIVIDAD_ESPECIE_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("12", surface="test_export.casilla")
_M111_PREMIOS_DINERARIOS_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("15", surface="test_export.casilla")
_M111_PREMIOS_ESPECIE_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("18", surface="test_export.casilla")
_M111_FORESTAL_DINERARIO_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("21", surface="test_export.casilla")
_M111_FORESTAL_ESPECIE_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("24", surface="test_export.casilla")
_M111_IMAGEN_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("27", surface="test_export.casilla")
_M111_PREVIOUS_RESULT_CASILLA: CasillaId = validated_casilla_id("29", surface="test_export.casilla")
_M115_PERCEPTORES_CASILLA, _M115_BASE_CASILLA = (
    validated_casilla_id("01", surface="test_export.casilla"),
    validated_casilla_id("02", surface="test_export.casilla"),
)
_M115_RETENCIONES_CASILLA, _M115_PREVIOUS_RESULT_CASILLA = (
    validated_casilla_id("03", surface="test_export.casilla"),
    validated_casilla_id("04", surface="test_export.casilla"),
)
_M115_RESULTADO_CASILLA = validated_casilla_id("05", surface="test_export.casilla")
_M130_INGRESOS_CASILLA, _M130_GASTOS_CASILLA = (
    validated_casilla_id("01", surface="test_export.casilla"),
    validated_casilla_id("02", surface="test_export.casilla"),
)
_M130_PREVIOUS_PAYMENTS_CASILLA, _M130_RETENCIONES_CASILLA = (
    validated_casilla_id("05", surface="test_export.casilla"),
    validated_casilla_id("06", surface="test_export.casilla"),
)
_M130_AGRARIAN_VOLUME_CASILLA, _M130_AGRARIAN_WITHHELD_CASILLA = (
    validated_casilla_id("08", surface="test_export.casilla"),
    validated_casilla_id("10", surface="test_export.casilla"),
)
_M130_HOME_DEDUCTION_CASILLA, _M130_PRIOR_RETURN_RESULT_CASILLA = (
    validated_casilla_id("16", surface="test_export.casilla"),
    validated_casilla_id("18", surface="test_export.casilla"),
)
_M131_RENDIMIENTO_MODULOS_CASILLA, _M131_VOLUME_AGRARIO_CASILLA = (
    validated_casilla_id("03", surface="test_export.casilla"),
    validated_casilla_id("05", surface="test_export.casilla"),
)
_M123_PERCEPTORES_CASILLA, _M123_BASE_CASILLA = (
    validated_casilla_id("03", surface="test_export.casilla"),
    validated_casilla_id("06", surface="test_export.casilla"),
)
_M123_RETENCIONES_CASILLA, _M123_INGRESOS_CUENTA_CASILLA = (
    validated_casilla_id("09", surface="test_export.casilla"),
    validated_casilla_id("12", surface="test_export.casilla"),
)
_M123_RESULTADO_CASILLA = validated_casilla_id("14", surface="test_export.casilla")
_M123_DINERARIO_PERCEPTORES_CASILLA, _M123_ESPECIE_PERCEPTORES_CASILLA = (
    validated_casilla_id("01", surface="test_export.casilla"),
    validated_casilla_id("02", surface="test_export.casilla"),
)
_M123_DINERARIO_BASE_CASILLA, _M123_ESPECIE_BASE_CASILLA = (
    validated_casilla_id("04", surface="test_export.casilla"),
    validated_casilla_id("05", surface="test_export.casilla"),
)
_M123_DINERARIO_RETENCIONES_CASILLA, _M123_ESPECIE_RETENCIONES_CASILLA = (
    validated_casilla_id("07", surface="test_export.casilla"),
    validated_casilla_id("08", surface="test_export.casilla"),
)
_M123_PREVIOUS_RESULT_CASILLA, _M123_INGRESOS_CUENTA_INPUT_CASILLA = (
    validated_casilla_id("10", surface="test_export.casilla"),
    validated_casilla_id("11", surface="test_export.casilla"),
)
_M123_MINORACION_CASILLA = validated_casilla_id("13", surface="test_export.casilla")
_M123_2019_2023_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("01", surface="test_export.casilla")
_M123_2019_2023_BASE_CASILLA: CasillaId = validated_casilla_id("02", surface="test_export.casilla")
_M123_2019_2023_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03", surface="test_export.casilla")
_M123_2019_2023_PREVIOUS_RESULT_CASILLA: CasillaId = validated_casilla_id("04", surface="test_export.casilla")
_M123_2019_2023_INGRESOS_CUENTA_CASILLA: CasillaId = validated_casilla_id("05", surface="test_export.casilla")
_M123_2019_2023_TOTAL_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="test_export.casilla")
_M123_2019_2023_MINORACION_CASILLA: CasillaId = validated_casilla_id("07", surface="test_export.casilla")
_M123_2019_2023_RESULTADO_CASILLA: CasillaId = validated_casilla_id("08", surface="test_export.casilla")
_M131_HISTORICAL_01_CASILLA: CasillaId = validated_casilla_id("01", surface="test_export.casilla")
_M131_HISTORICAL_02_CASILLA: CasillaId = validated_casilla_id("02", surface="test_export.casilla")
_M131_HISTORICAL_03_CASILLA: CasillaId = validated_casilla_id("03", surface="test_export.casilla")
_M131_HISTORICAL_04_CASILLA: CasillaId = validated_casilla_id("04", surface="test_export.casilla")
_M131_HISTORICAL_05_CASILLA: CasillaId = validated_casilla_id("05", surface="test_export.casilla")
_M131_HISTORICAL_06_CASILLA: CasillaId = validated_casilla_id("06", surface="test_export.casilla")
_M131_HISTORICAL_07_CASILLA: CasillaId = validated_casilla_id("07", surface="test_export.casilla")
_M131_HISTORICAL_08_CASILLA: CasillaId = validated_casilla_id("08", surface="test_export.casilla")
_M131_HISTORICAL_09_CASILLA: CasillaId = validated_casilla_id("09", surface="test_export.casilla")
_M131_HISTORICAL_10_CASILLA: CasillaId = validated_casilla_id("10", surface="test_export.casilla")
_M131_HISTORICAL_11_CASILLA: CasillaId = validated_casilla_id("11", surface="test_export.casilla")
_M131_HISTORICAL_12_CASILLA: CasillaId = validated_casilla_id("12", surface="test_export.casilla")
_M131_HISTORICAL_13_CASILLA: CasillaId = validated_casilla_id("13", surface="test_export.casilla")
_M131_HISTORICAL_14_CASILLA: CasillaId = validated_casilla_id("14", surface="test_export.casilla")
_M131_HISTORICAL_15_CASILLA: CasillaId = validated_casilla_id("15", surface="test_export.casilla")
_M390_REPERCUTIDO_GENERAL_CASILLA = validated_casilla_id("iva.anual.repercutido.general", surface="test_export.casilla")
_M390_REPERCUTIDO_REDUCIDO_CASILLA = validated_casilla_id(
    "iva.anual.repercutido.reducido", surface="test_export.casilla"
)
_M390_REPERCUTIDO_SUPER_REDUCIDO_CASILLA = validated_casilla_id(
    "iva.anual.repercutido.super-reducido", surface="test_export.casilla"
)
# Rate-specific box-layer casillas. The tier casillas above are the rate-BLIND
# total layer and no longer reach an official box; these do, one per AEAT rate
# box. A draft populating a tier total while leaving its boxes empty declares a
# breakdown that does not account for its own total, which the export gate
# refuses -- so a coherent post-split fixture has to carry both layers.
#
# The reducido tier is deliberately split across TWO of its three boxes. What
# the gate reads is the SUM against the tier total; a fixture giving every tier
# exactly one box would let per-box exact equality read as the invariant, and it
# is not one.
_M390_REPERCUTIDO_TIPO_21_CUOTA_CASILLA = validated_casilla_id(
    "iva.anual.repercutido.tipo-21.cuota", surface="test_export.casilla"
)
_M390_REPERCUTIDO_TIPO_10_CUOTA_CASILLA = validated_casilla_id(
    "iva.anual.repercutido.tipo-10.cuota", surface="test_export.casilla"
)
_M390_REPERCUTIDO_TIPO_5_CUOTA_CASILLA = validated_casilla_id(
    "iva.anual.repercutido.tipo-5.cuota", surface="test_export.casilla"
)
_M390_REPERCUTIDO_TIPO_4_CUOTA_CASILLA = validated_casilla_id(
    "iva.anual.repercutido.tipo-4.cuota", surface="test_export.casilla"
)
_M390_SOPORTADO_INTERIORES_CASILLA = validated_casilla_id(
    "iva.anual.soportado.interiores", surface="test_export.casilla"
)
_M390_SOPORTADO_IMPORTACIONES_CASILLA = validated_casilla_id(
    "iva.anual.soportado.importaciones", surface="test_export.casilla"
)
_M390_AUTOREPERCUTIDO_INTRACOMUNITARIA_CASILLA = validated_casilla_id(
    "iva.anual.autorepercutido.intracomunitaria", surface="test_export.casilla"
)
_M390_RECARGO_GENERAL_CASILLA = validated_casilla_id(
    "iva.anual.repercutido.recargo.general", surface="test_export.casilla"
)
_M390_RECARGO_REDUCIDO_CASILLA = validated_casilla_id(
    "iva.anual.repercutido.recargo.reducido", surface="test_export.casilla"
)
_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA = validated_casilla_id(
    "iva.anual.compensacion-ultimo-periodo-97", surface="test_export.casilla"
)
_M390_COMPENSACION_GENERADA_EJERCICIO_CASILLA = validated_casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97", surface="test_export.casilla"
)


def _narrative() -> str:
    narrative: str = "filing.test_export.narrative"
    return narrative


def _schema_provider(
    *,
    filing_year: int | None = None,
    period: str | None = None,
    modelos: tuple[str, ...] = ("130",),
) -> RegistrySchemaAccessor:
    """Return a real registry schema provider, cached per period selector."""
    selected_modelos = tuple(sorted(modelos))
    key = (filing_year, period, selected_modelos)
    provider = _SCHEMA_PROVIDER_CACHE.get(key)
    if provider is None:
        typed_period = (
            Period.from_year_and_code(filing_year, period) if filing_year is not None and period is not None else None
        )
        provider = build_runtime_schema_provider(
            filing_year=filing_year,
            period=typed_period,
            modelos=selected_modelos,
        )
        _SCHEMA_PROVIDER_CACHE[key] = provider
    return provider


def _provider_without_export_layout(provider: RegistrySchemaAccessor, modelo: str) -> RegistrySchemaAccessor:
    subview = provider.get_subview(modelo)
    return RegistrySchemaAccessor(
        collections=provider.collections,
        snapshots=provider.snapshots,
        subviews={
            **provider.subviews,
            modelo: replace(subview, export_layout_ids=(), export_layouts=()),
        },
    )


def _provider_with_export_layouts(
    provider: RegistrySchemaAccessor,
    modelo: str,
    layouts: tuple[ExportLayoutDefinition, ...],
) -> RegistrySchemaAccessor:
    subview = provider.get_subview(modelo)
    return RegistrySchemaAccessor(
        collections=provider.collections,
        snapshots=provider.snapshots,
        subviews={
            **provider.subviews,
            modelo: replace(
                subview,
                export_layout_ids=tuple(layout.id for layout in layouts),
                export_layouts=layouts,
            ),
        },
    )


def _assert_missing_export_layout_refusal(message: str, modelo: str) -> None:
    assert f"modelo {modelo!r} local declaration export is unsupported" in message
    assert "registry snapshot has no complete export_layouts definition" in message
    assert "calculation, verification, and local filing surfaces may exist" in message.lower()
    assert "cannot produce an AEAT-compatible export file" in message
    assert "does not certify legal correctness" in message


@cache
def _approved_registry_draft():
    draft = build_draft(
        modelo="130",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("100"),
            _M130_GASTOS_CASILLA: Decimal("25"),
            _M130_PREVIOUS_PAYMENTS_CASILLA: Decimal("0"),
            _M130_RETENCIONES_CASILLA: Decimal("0"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
        },
        schema_provider=_schema_provider(),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def _approved_modelo_131_registry_draft():
    draft = build_draft(
        modelo="131",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            _M131_RENDIMIENTO_MODULOS_CASILLA: Decimal("1000"),
            _M131_VOLUME_AGRARIO_CASILLA: Decimal("500"),
            "modelo-131.page1.110-113.actividad-1-epigrafe": "722",
            "modelo-131.page1.114-130.actividad-1-rendimiento-neto": Decimal("1200.50"),
            "modelo-131.dpa.013-016.epigrafe-iae": ["722"],
            "modelo-131.dpa.031-032.vehiculos-afectos": {"1": "2"},
            "modelo-131.did.012-045.iban": "ES9121000418450200051332",
        },
        schema_provider=_schema_provider(filing_year=2026, period="1T", modelos=("131",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def _approved_modelo_131_registry_draft_without_direct_debit():
    draft = build_draft(
        modelo="131",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            _M131_RENDIMIENTO_MODULOS_CASILLA: Decimal("1000"),
            _M131_VOLUME_AGRARIO_CASILLA: Decimal("500"),
            "modelo-131.page1.110-113.actividad-1-epigrafe": "722",
            "modelo-131.page1.114-130.actividad-1-rendimiento-neto": Decimal("1200.50"),
            "modelo-131.dpa.013-016.epigrafe-iae": ["722"],
            "modelo-131.dpa.031-032.vehiculos-afectos": {"1": "2"},
        },
        schema_provider=_schema_provider(filing_year=2026, period="1T", modelos=("131",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def _approved_modelo_131_zero_payable_direct_debit_draft():
    draft = build_draft(
        modelo="131",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            _M131_RENDIMIENTO_MODULOS_CASILLA: Decimal("0"),
            _M131_VOLUME_AGRARIO_CASILLA: Decimal("0"),
            "modelo-131.did.012-045.iban": "ES9121000418450200051332",
        },
        schema_provider=_schema_provider(filing_year=2026, period="1T", modelos=("131",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def _approved_modelo_131_year_scoped_registry_draft(filing_year: int, binding_prefix: str):
    draft = build_draft(
        modelo="131",
        period=Period.from_year_and_code(filing_year, "1T"),
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            _M131_RENDIMIENTO_MODULOS_CASILLA: Decimal("1000"),
            _M131_VOLUME_AGRARIO_CASILLA: Decimal("500"),
            f"{binding_prefix}.page1.110-113.actividad-1-epigrafe": "722",
            f"{binding_prefix}.page1.114-130.actividad-1-rendimiento-neto": Decimal("1200.50"),
            f"{binding_prefix}.dpa.013-016.epigrafe-iae": ["722"],
            f"{binding_prefix}.dpa.031-032.vehiculos-afectos": {"1": "2"},
            f"{binding_prefix}.did.012-045.iban": "ES9121000418450200051332",
        },
        schema_provider=_schema_provider(filing_year=filing_year, period="1T", modelos=("131",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
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
            _M131_HISTORICAL_01_CASILLA: Decimal("1000"),
            _M131_HISTORICAL_02_CASILLA: Decimal("20"),
            _M131_HISTORICAL_03_CASILLA: Decimal("500"),
            _M131_HISTORICAL_05_CASILLA: Decimal("250"),
            _M131_HISTORICAL_08_CASILLA: Decimal("3"),
            _M131_HISTORICAL_09_CASILLA: Decimal("2"),
            "modelo-131-2019-2023-resultados-negativos-anteriores": Decimal("1"),
            _M131_HISTORICAL_12_CASILLA: Decimal("0.50"),
            _M131_HISTORICAL_14_CASILLA: Decimal("0.25"),
        },
        schema_provider=provider,
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def _approved_modelo_111_registry_draft():
    draft = build_draft(
        modelo="111",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("180.25"),
            _M111_TRABAJO_ESPECIE_RETENCIONES_CASILLA: Decimal("12.10"),
            _M111_ACTIVIDAD_DINERARIA_RETENCIONES_CASILLA: Decimal("300.00"),
            _M111_ACTIVIDAD_ESPECIE_RETENCIONES_CASILLA: Decimal("14.40"),
            _M111_PREMIOS_DINERARIOS_RETENCIONES_CASILLA: Decimal("25.00"),
            _M111_PREMIOS_ESPECIE_RETENCIONES_CASILLA: Decimal("0.50"),
            _M111_FORESTAL_DINERARIO_RETENCIONES_CASILLA: Decimal("7.00"),
            _M111_FORESTAL_ESPECIE_RETENCIONES_CASILLA: Decimal("8.00"),
            _M111_IMAGEN_RETENCIONES_CASILLA: Decimal("9.00"),
            _M111_PREVIOUS_RESULT_CASILLA: Decimal("40.00"),
        },
        schema_provider=_schema_provider(modelos=("111",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def _approved_modelo_115_registry_draft():
    draft = build_draft(
        modelo="115",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            _M115_PERCEPTORES_CASILLA: Decimal("1"),
            _M115_BASE_CASILLA: Decimal("1250.50"),
            _M115_PREVIOUS_RESULT_CASILLA: Decimal("10.00"),
        },
        schema_provider=_schema_provider(modelos=("115",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def _approved_modelo_123_registry_draft():
    draft = build_draft(
        modelo="123",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            _M123_DINERARIO_PERCEPTORES_CASILLA: Decimal("2"),
            _M123_ESPECIE_PERCEPTORES_CASILLA: Decimal("3"),
            _M123_DINERARIO_BASE_CASILLA: Decimal("1000.25"),
            _M123_ESPECIE_BASE_CASILLA: Decimal("200.75"),
            _M123_DINERARIO_RETENCIONES_CASILLA: Decimal("190.05"),
            _M123_ESPECIE_RETENCIONES_CASILLA: Decimal("38.14"),
            _M123_PREVIOUS_RESULT_CASILLA: Decimal("0"),
            _M123_INGRESOS_CUENTA_INPUT_CASILLA: Decimal("7.50"),
            _M123_MINORACION_CASILLA: Decimal("12.25"),
        },
        schema_provider=_schema_provider(modelos=("123",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
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
            _M123_2019_2023_PERCEPTORES_CASILLA: Decimal("5"),
            _M123_2019_2023_BASE_CASILLA: Decimal("1201.00"),
            _M123_2019_2023_RETENCIONES_CASILLA: Decimal("228.19"),
            _M123_2019_2023_PREVIOUS_RESULT_CASILLA: Decimal("0"),
            _M123_2019_2023_INGRESOS_CUENTA_CASILLA: Decimal("7.50"),
            _M123_2019_2023_MINORACION_CASILLA: Decimal("12.25"),
        },
        schema_provider=provider,
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def _approved_modelo_200_registry_draft():
    # A complete Modelo 200 (sociedades) draft: accounting profit 200 drives the
    # cuota chain, and 450 of Modelo 202 pagos fraccionados produces a negative
    # cuota diferencial. Every computed casilla in the calculation closure is
    # populated, so the completeness gate has a full result set to check.
    provider = _schema_provider(filing_year=2025, period="0A", modelos=("200",))
    draft = build_draft(
        modelo="200",
        period=Period.from_year_and_code(2025, "0A"),
        profile=ModeloOperatorProfile(
            tax_id="B12345674",
            display_name="Emilio Export Test SL",
        ),
        inputs={
            validated_casilla_id("00040", surface="_approved_modelo_200_registry_draft"): "0",
            validated_casilla_id("00501", surface="_approved_modelo_200_registry_draft"): Decimal("200.00"),
            validated_casilla_id("DP200014:01033", surface="_approved_modelo_200_registry_draft"): Decimal("0.00"),
            validated_casilla_id("DP200014:01034", surface="_approved_modelo_200_registry_draft"): Decimal("0.00"),
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
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def _approved_modelo_390_registry_draft():
    # Modelo 390 (IVA resumen anual): the ledger_iva_aggregation and
    # relation_prefill/previous_filing bindings behind these bound casillas
    # resolve to None with no ledger data or prior filings on this bare
    # schema provider, so build_draft falls through to the direct casilla
    # overrides below (mirrors the M130/M200 previous_filing/relation-bound
    # override precedent in this module).
    provider = _schema_provider(filing_year=2025, period="0A", modelos=("390",))
    draft = build_draft(
        modelo="390",
        period=Period.from_year_and_code(2025, "0A"),
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            _M390_REPERCUTIDO_GENERAL_CASILLA: Decimal("18000.00"),
            _M390_REPERCUTIDO_REDUCIDO_CASILLA: Decimal("2100.50"),
            _M390_REPERCUTIDO_SUPER_REDUCIDO_CASILLA: Decimal("420.00"),
            _M390_REPERCUTIDO_TIPO_21_CUOTA_CASILLA: Decimal("18000.00"),
            _M390_REPERCUTIDO_TIPO_10_CUOTA_CASILLA: Decimal("1600.50"),
            _M390_REPERCUTIDO_TIPO_5_CUOTA_CASILLA: Decimal("500.00"),
            _M390_REPERCUTIDO_TIPO_4_CUOTA_CASILLA: Decimal("420.00"),
            _M390_SOPORTADO_INTERIORES_CASILLA: Decimal("9800.25"),
            _M390_SOPORTADO_IMPORTACIONES_CASILLA: Decimal("650.00"),
            _M390_AUTOREPERCUTIDO_INTRACOMUNITARIA_CASILLA: Decimal("300.00"),
            _M390_RECARGO_GENERAL_CASILLA: Decimal("1248.00"),
            _M390_RECARGO_REDUCIDO_CASILLA: Decimal("624.00"),
            _M390_COMPENSACION_ULTIMO_PERIODO_CASILLA: Decimal("0.00"),
            _M390_COMPENSACION_GENERADA_EJERCICIO_CASILLA: Decimal("0.00"),
        },
        schema_provider=provider,
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


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
