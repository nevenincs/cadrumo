"""Shared support for declaration export tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ....core import Period
from ....domain.calculations.registry import (
    CasillaId,
    ExportLayoutDefinition,
    validated_casilla_id,
)
from ....domain.filing import ModeloDraft
from ....domain.submission import ModeloDraftStatus
from .. import (
    ModeloOperatorProfile,
    build_draft,
    build_runtime_schema_provider,
    export_draft,
)
from .._export_parity import boe_representable_casilla_ids
from ..runtime import RegistrySchemaAccessor

_HEX_DIGEST = "a" * 64
_PERIOD = Period.from_year_and_code(2026, "1T")
_EXPORT_PATH = Path("exports/m130-2026Q1.txt")
_OTHER_EXPORT_PATH = Path("exports/x.txt")
_SCHEMA_PROVIDER_CACHE: dict[tuple[int | None, str | None, tuple[str, ...]], RegistrySchemaAccessor] = {}


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test_export.casilla")
    except ValueError as exc:
        raise AssertionError(f"filing export test casilla key {value!r} is not a canonical casilla.id") from exc


_M111_RETENCIONES_TOTAL_CASILLA, _M111_RESULTADO_CASILLA = _casilla_id("28"), _casilla_id("30")
_M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: CasillaId = _casilla_id("03")
_M111_TRABAJO_ESPECIE_RETENCIONES_CASILLA: CasillaId = _casilla_id("06")
_M111_ACTIVIDAD_DINERARIA_RETENCIONES_CASILLA: CasillaId = _casilla_id("09")
_M111_ACTIVIDAD_ESPECIE_RETENCIONES_CASILLA: CasillaId = _casilla_id("12")
_M111_PREMIOS_DINERARIOS_RETENCIONES_CASILLA: CasillaId = _casilla_id("15")
_M111_PREMIOS_ESPECIE_RETENCIONES_CASILLA: CasillaId = _casilla_id("18")
_M111_FORESTAL_DINERARIO_RETENCIONES_CASILLA: CasillaId = _casilla_id("21")
_M111_FORESTAL_ESPECIE_RETENCIONES_CASILLA: CasillaId = _casilla_id("24")
_M111_IMAGEN_RETENCIONES_CASILLA: CasillaId = _casilla_id("27")
_M111_PREVIOUS_RESULT_CASILLA: CasillaId = _casilla_id("29")
_M115_PERCEPTORES_CASILLA, _M115_BASE_CASILLA = _casilla_id("01"), _casilla_id("02")
_M115_RETENCIONES_CASILLA, _M115_PREVIOUS_RESULT_CASILLA = _casilla_id("03"), _casilla_id("04")
_M115_RESULTADO_CASILLA = _casilla_id("05")
_M130_INGRESOS_CASILLA, _M130_GASTOS_CASILLA = _casilla_id("01"), _casilla_id("02")
_M130_PREVIOUS_PAYMENTS_CASILLA, _M130_RETENCIONES_CASILLA = _casilla_id("05"), _casilla_id("06")
_M130_AGRARIAN_VOLUME_CASILLA, _M130_AGRARIAN_WITHHELD_CASILLA = _casilla_id("08"), _casilla_id("10")
_M130_HOME_DEDUCTION_CASILLA, _M130_PRIOR_RETURN_RESULT_CASILLA = _casilla_id("16"), _casilla_id("18")
_M131_RENDIMIENTO_MODULOS_CASILLA, _M131_VOLUME_AGRARIO_CASILLA = _casilla_id("03"), _casilla_id("05")
_M123_PERCEPTORES_CASILLA, _M123_BASE_CASILLA = _casilla_id("03"), _casilla_id("06")
_M123_RETENCIONES_CASILLA, _M123_INGRESOS_CUENTA_CASILLA = _casilla_id("09"), _casilla_id("12")
_M123_RESULTADO_CASILLA = _casilla_id("14")
_M123_DINERARIO_PERCEPTORES_CASILLA, _M123_ESPECIE_PERCEPTORES_CASILLA = _casilla_id("01"), _casilla_id("02")
_M123_DINERARIO_BASE_CASILLA, _M123_ESPECIE_BASE_CASILLA = _casilla_id("04"), _casilla_id("05")
_M123_DINERARIO_RETENCIONES_CASILLA, _M123_ESPECIE_RETENCIONES_CASILLA = _casilla_id("07"), _casilla_id("08")
_M123_PREVIOUS_RESULT_CASILLA, _M123_INGRESOS_CUENTA_INPUT_CASILLA = _casilla_id("10"), _casilla_id("11")
_M123_MINORACION_CASILLA = _casilla_id("13")
_M123_2019_2023_PERCEPTORES_CASILLA: CasillaId = _casilla_id("01")
_M123_2019_2023_BASE_CASILLA: CasillaId = _casilla_id("02")
_M123_2019_2023_RETENCIONES_CASILLA: CasillaId = _casilla_id("03")
_M123_2019_2023_PREVIOUS_RESULT_CASILLA: CasillaId = _casilla_id("04")
_M123_2019_2023_INGRESOS_CUENTA_CASILLA: CasillaId = _casilla_id("05")
_M123_2019_2023_TOTAL_RETENCIONES_CASILLA: CasillaId = _casilla_id("06")
_M123_2019_2023_MINORACION_CASILLA: CasillaId = _casilla_id("07")
_M123_2019_2023_RESULTADO_CASILLA: CasillaId = _casilla_id("08")
_M131_HISTORICAL_01_CASILLA: CasillaId = _casilla_id("01")
_M131_HISTORICAL_02_CASILLA: CasillaId = _casilla_id("02")
_M131_HISTORICAL_03_CASILLA: CasillaId = _casilla_id("03")
_M131_HISTORICAL_04_CASILLA: CasillaId = _casilla_id("04")
_M131_HISTORICAL_05_CASILLA: CasillaId = _casilla_id("05")
_M131_HISTORICAL_06_CASILLA: CasillaId = _casilla_id("06")
_M131_HISTORICAL_07_CASILLA: CasillaId = _casilla_id("07")
_M131_HISTORICAL_08_CASILLA: CasillaId = _casilla_id("08")
_M131_HISTORICAL_09_CASILLA: CasillaId = _casilla_id("09")
_M131_HISTORICAL_10_CASILLA: CasillaId = _casilla_id("10")
_M131_HISTORICAL_11_CASILLA: CasillaId = _casilla_id("11")
_M131_HISTORICAL_12_CASILLA: CasillaId = _casilla_id("12")
_M131_HISTORICAL_13_CASILLA: CasillaId = _casilla_id("13")
_M131_HISTORICAL_14_CASILLA: CasillaId = _casilla_id("14")
_M131_HISTORICAL_15_CASILLA: CasillaId = _casilla_id("15")
_M390_REPERCUTIDO_GENERAL_CASILLA = _casilla_id("iva.anual.repercutido.general")
_M390_REPERCUTIDO_REDUCIDO_CASILLA = _casilla_id("iva.anual.repercutido.reducido")
_M390_REPERCUTIDO_SUPER_REDUCIDO_CASILLA = _casilla_id("iva.anual.repercutido.super-reducido")
_M390_SOPORTADO_INTERIORES_CASILLA = _casilla_id("iva.anual.soportado.interiores")
_M390_SOPORTADO_IMPORTACIONES_CASILLA = _casilla_id("iva.anual.soportado.importaciones")
_M390_AUTOREPERCUTIDO_INTRACOMUNITARIA_CASILLA = _casilla_id("iva.anual.autorepercutido.intracomunitaria")
_M390_RECARGO_GENERAL_CASILLA = _casilla_id("iva.anual.repercutido.recargo.general")
_M390_RECARGO_REDUCIDO_CASILLA = _casilla_id("iva.anual.repercutido.recargo.reducido")
_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA = _casilla_id("iva.anual.compensacion-ultimo-periodo-97")
_M390_COMPENSACION_GENERADA_EJERCICIO_CASILLA = _casilla_id("iva.anual.compensacion-generada-ejercicio-no-97")


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


@dataclass(frozen=True)
class _RequiredSetPartition:
    """Registry-derived partition of a revision's manifest-and-representable casillas.

    Each manifest casilla the official record files a slot for falls into exactly
    one of three classes, read straight off the registry ``CasillaSchema``:

    - ``calculation_results`` -- declares a formula, so its value is produced by the
      calculation and a blank slot means the calculation did not run.
    - ``schema_required_inputs`` -- declares no formula but carries the registry
      ``required`` flag, so the taxpayer must supply it and a blank slot is an
      omission, not a zero.
    - ``optional_inputs`` -- declares neither, so a blank slot is a valid zero
      (retenciones, prior payments, deductions the taxpayer may legitimately not
      have).

    The first two classes are the required set a complete fichero-BOE must carry.

    This partition is the INDEPENDENT ORACLE for that required set: it reads
    ``formula`` and ``required`` off the :class:`CasillaCollection` directly and
    MUST NOT be rewritten to delegate to ``required_applicable_casilla_ids``. The
    duplicated predicate is deliberate. A test that derives its expectation from
    the function under test cannot detect a change in that function's semantics --
    it can only detect that the function was called. Collapsing the two onto one
    derivation once let a relaxed predicate drop a schema-required, formula-less
    casilla out of the pre-write completeness gate while every filing test stayed
    green, which is exactly the structurally-thin ``.boe`` the gate exists to
    refuse. Keeping the classes separate here also makes each clause of the
    production predicate independently pinnable, so a per-clause relaxation names
    the class it broke rather than failing on an opaque set difference.

    Representability is deliberately NOT mirrored: it is supplied by the production
    ``boe_representable_casilla_ids`` derivation, whose disposition-suppression
    behaviour carries its own dedicated coverage. Only the required-set predicate is
    duplicated here, because only that predicate is the subject under pin.
    """

    modelo: str
    calculation_results: frozenset[CasillaId]
    schema_required_inputs: frozenset[CasillaId]
    optional_inputs: frozenset[CasillaId]

    @property
    def required_applicable(self) -> frozenset[CasillaId]:
        """Return the casillas a complete fichero-BOE must carry a value for."""
        return self.calculation_results | self.schema_required_inputs


def _required_set_partition(
    *,
    modelo: str,
    provider: RegistrySchemaAccessor,
    layout: ExportLayoutDefinition,
    headers: dict[str, str],
) -> _RequiredSetPartition:
    """Classify a revision's manifest-and-representable casillas from the registry.

    Args:
        modelo: Modelo code whose completeness manifest and casilla collection
            supply the classification facts.
        provider: Real registry schema accessor for the pinned revision.
        layout: Fixed-width export layout whose filed slots bound the classification.
        headers: Export headers selecting this filing's disposition, which decide
            which records (and therefore which slots) are suppressed.

    Returns:
        The :class:`_RequiredSetPartition` oracle for this modelo and revision.
    """
    subview = provider.get_subview(modelo)
    manifest = subview.completeness_manifest
    assert manifest is not None, f"modelo {modelo} must declare a completeness manifest to ground the required-set pin"
    representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=provider)
    collection = provider.get_collection(modelo)

    calculation_results: set[CasillaId] = set()
    schema_required_inputs: set[CasillaId] = set()
    optional_inputs: set[CasillaId] = set()
    for entry in manifest.casillas:
        casilla_id = entry.casilla_id
        if casilla_id not in representable:
            continue
        schema = collection.get(casilla_id)
        if schema is None:
            continue
        if schema.formula is not None:
            calculation_results.add(casilla_id)
        elif schema.required:
            schema_required_inputs.add(casilla_id)
        else:
            optional_inputs.add(casilla_id)

    return _RequiredSetPartition(
        modelo=modelo,
        calculation_results=frozenset(calculation_results),
        schema_required_inputs=frozenset(schema_required_inputs),
        optional_inputs=frozenset(optional_inputs),
    )


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


def _modelo_130_export_headers() -> dict[str, str]:
    return {
        "declaration_type": "I",
        "surnames": "EXPORT TEST",
        "name": "ANA",
        "program_version": "A001",
        "presenter_nif": "A12345678",
    }


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


def _modelo_111_export_headers() -> dict[str, str]:
    return {
        "declaration_type": "I",
        "surnames": "EXPORT TEST",
        "name": "ANA",
        "program_version": "A001",
        "presenter_nif": "A12345678",
    }


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


def _modelo_115_export_headers() -> dict[str, str]:
    return {
        "declaration_type": "I",
        "legal_name": "EXPORT TEST",
        "first_name": "ANA",
        "program_version": "A001",
        "presenter_tax_id": "A12345678",
    }


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


def _modelo_123_export_headers() -> dict[str, str]:
    return {
        "declaration_type": "I",
        "legal_name": "EXPORT TEST",
        "program_version": "A001",
        "presenter_tax_id": "A12345678",
    }


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


def _modelo_123_2019_export_headers() -> dict[str, str]:
    return {
        "declaration_type": "I",
        "surnames": "EXPORT TEST",
        "name": "ANA",
        "program_version": "A001",
        "presenter_tax_id": "A12345678",
    }


@cache
def _approved_modelo_200_registry_draft():
    # A complete Modelo 200 (sociedades) draft: accounting profit 200 drives the
    # cuota chain, and 450 of Modelo 202 pagos fraccionados produces a negative
    # cuota diferencial. Every computed casilla in the calculation closure is
    # populated, so the completeness gate has a full result set to check.
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("200",))
    draft = build_draft(
        modelo="200",
        period=Period.from_year_and_code(2024, "0A"),
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


def _modelo_200_export_headers() -> dict[str, str]:
    return {
        "declaration_type": "D",
        "surnames": "EMILIO EXPORT TEST SL",
        "name": "EMILIO EXPORT TEST SL",
        "program_version": "A001",
        "presenter_nif": "B12345674",
    }


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


def _modelo_390_export_headers() -> dict[str, str]:
    return {
        "declaration_type": "I",
        "surnames": "EXPORT TEST",
        "name": "ANA",
        "program_version": "A001",
        "presenter_nif": "12345678Z",
    }


def _real_export_payload(
    *,
    draft: ModeloDraft,
    provider: RegistrySchemaAccessor,
    headers: dict[str, str],
    output_name: str,
) -> bytes:
    with TemporaryDirectory() as directory:
        output = Path(directory) / output_name
        export_draft(
            draft,
            output_path=output,
            headers=headers,
            schema_provider=provider,
        )
        return output.read_bytes()


@cache
def _modelo_130_export_payload() -> bytes:
    return _real_export_payload(
        draft=_approved_registry_draft(),
        provider=_schema_provider(),
        headers=_modelo_130_export_headers(),
        output_name="modelo-130.txt",
    )


@cache
def _modelo_111_export_payload() -> bytes:
    return _real_export_payload(
        draft=_approved_modelo_111_registry_draft(),
        provider=_schema_provider(modelos=("111",)),
        headers=_modelo_111_export_headers(),
        output_name="modelo-111.txt",
    )


@cache
def _modelo_115_export_payload() -> bytes:
    return _real_export_payload(
        draft=_approved_modelo_115_registry_draft(),
        provider=_schema_provider(modelos=("115",)),
        headers=_modelo_115_export_headers(),
        output_name="modelo-115.txt",
    )


@cache
def _modelo_123_export_payload() -> bytes:
    return _real_export_payload(
        draft=_approved_modelo_123_registry_draft(),
        provider=_schema_provider(modelos=("123",)),
        headers=_modelo_123_export_headers(),
        output_name="modelo-123.txt",
    )


@cache
def _modelo_123_2019_export_payload() -> bytes:
    return _real_export_payload(
        draft=_approved_modelo_123_2019_registry_draft(),
        provider=_schema_provider(filing_year=2023, period="4T", modelos=("123",)),
        headers=_modelo_123_2019_export_headers(),
        output_name="modelo-123-2023.txt",
    )


@dataclass(frozen=True)
class _ExportVerifyMatchCase:
    output_name: str
    draft_factory: Callable[[], ModeloDraft]
    payload_factory: Callable[[], bytes]
    modelos: tuple[str, ...]
    filing_year: int | None = None
    period: str | None = None


_EXPORT_VERIFY_MATCH_CASES = (
    pytest.param(
        _ExportVerifyMatchCase(
            output_name="modelo-130.txt",
            draft_factory=_approved_registry_draft,
            payload_factory=_modelo_130_export_payload,
            modelos=("130",),
        ),
        id="modelo-130",
    ),
    pytest.param(
        _ExportVerifyMatchCase(
            output_name="modelo-111.txt",
            draft_factory=_approved_modelo_111_registry_draft,
            payload_factory=_modelo_111_export_payload,
            modelos=("111",),
        ),
        id="modelo-111",
    ),
    pytest.param(
        _ExportVerifyMatchCase(
            output_name="modelo-115.txt",
            draft_factory=_approved_modelo_115_registry_draft,
            payload_factory=_modelo_115_export_payload,
            modelos=("115",),
        ),
        id="modelo-115",
    ),
    pytest.param(
        _ExportVerifyMatchCase(
            output_name="modelo-123.txt",
            draft_factory=_approved_modelo_123_registry_draft,
            payload_factory=_modelo_123_export_payload,
            modelos=("123",),
        ),
        id="modelo-123",
    ),
    pytest.param(
        _ExportVerifyMatchCase(
            output_name="modelo-123-2023.txt",
            draft_factory=_approved_modelo_123_2019_registry_draft,
            payload_factory=_modelo_123_2019_export_payload,
            modelos=("123",),
            filing_year=2023,
            period="4T",
        ),
        id="modelo-123-2019-layout",
    ),
)


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
