"""Shared support for declaration export tests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from functools import cache

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.field_origin import FieldOrigin
from ....core.modelo import Modelo
from ....core.payment_election import PaymentElection
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.binding_targets import revision_bindings_by_id
from ....domain.calculations.registry.binding_value_contract import BindingValueChannel
from ....domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from ....domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    revision_last_exercise,
)
from ....domain.filing.protocols import ModeloInputValue
from ....domain.modelos.filing_record import FilingDeclarationKind
from ....domain.submission.models import ModeloDraftStatus
from ..draft_construction import build_draft
from ..producer_snapshot import (
    AmendmentEvidence,
    FilingElectionFacts,
    FilingProducerSnapshot,
    GeneralFilingProfileFacts,
    Modelo111ProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from ..runtime import ModeloOperatorProfile, RegistrySchemaAccessor, build_runtime_schema_provider

EXPORT_PERIOD = Period.from_year_and_code(filing_year_envelope().horizon, "1T")
#: The last exercise of the oldest Modelo 131 edition, the closed design whose record layout the historical casillas follow.
MODELO_131_HISTORICAL_YEAR = revision_last_exercise("131", str(authored_revisions("131")[0].id))
_SCHEMA_PROVIDER_CACHE: dict[tuple[int, str, tuple[str, ...]], RegistrySchemaAccessor] = {}


def typed_producer_snapshot(*, complementaria: bool = False) -> FilingProducerSnapshot:
    amendment = (
        AmendmentEvidence(
            kind=FilingDeclarationKind.COMPLEMENTARIA,
            m303_rectificativa_motive=None,
            original_aeat_receipt="1234567890123",
        )
        if complementaria
        else None
    )
    return build_filing_producer_snapshot(
        modelo=Modelo("111"),
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None,
            given_name="Ana",
            surnames="Prueba",
            full_name="Ana Prueba",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=Modelo111ProfileFacts(colegio_concertado=False, colegio_concertado_origin=FieldOrigin.OPERATOR),
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


def filer_with_nothing_else(
    provider: RegistrySchemaAccessor, extra_facts: Mapping[str, ModeloInputValue] | None = None
) -> dict[str, ModeloInputValue]:
    """State every fact the Modelo 100 revision reads as absent, for a Madrid filer, plus any ``extra_facts``."""
    inputs: dict[str, ModeloInputValue] = {
        "renta-profile-tax-residence-ccaa": "madrid",
        "renta-profile-taxpayer-birth-date": "1975-06-15",
        **(extra_facts or {}),
    }
    for binding_id, binding in revision_bindings_by_id(provider.get_snapshot("100").revision).items():
        if binding.value.channel in {BindingValueChannel.DECIMAL, BindingValueChannel.INTEGER}:
            inputs[str(binding_id)] = Decimal("0")
        elif binding.value.channel is BindingValueChannel.BOOLEAN:
            inputs[str(binding_id)] = False
    inputs["renta-profile-declaration-type"] = Decimal("1")
    inputs["renta-modelo-100-estimacion-directa-es-normal"] = True
    return inputs


def _general_ingreso_producer_snapshot(modelo: str) -> FilingProducerSnapshot:
    """Producer facts for a general-profile ingreso filing by the standard test taxpayer."""
    return build_filing_producer_snapshot(
        modelo=Modelo(modelo),
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


def typed_modelo_131_producer_snapshot() -> FilingProducerSnapshot:
    return _general_ingreso_producer_snapshot("131")


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
_M130_INGRESOS_CASILLA, _M130_GASTOS_PREVIOS_CASILLA = (
    validated_casilla_id("01", surface="test_export.casilla"),
    validated_casilla_id("gastos-deducibles-previos", surface="test_export.casilla"),
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


def _narrative() -> str:
    narrative: str = "filing.test_export.narrative"
    return narrative


def export_schema_provider(
    *,
    filing_year: int,
    period: str,
    modelos: tuple[str, ...] = ("130",),
) -> RegistrySchemaAccessor:
    """Return a real registry schema provider, cached per period selector."""
    selected_modelos = tuple(sorted(modelos))
    key = (filing_year, period, selected_modelos)
    provider = _SCHEMA_PROVIDER_CACHE.get(key)
    if provider is None:
        typed_period = Period.from_year_and_code(filing_year, period)
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
def approved_registry_draft():
    draft = build_draft(
        modelo="130",
        period=EXPORT_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("100"),
            _M130_GASTOS_PREVIOS_CASILLA: Decimal("25"),
            "modelo-130-estimacion-directa-modalidad": "directa_normal",
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
        schema_provider=export_schema_provider(filing_year=EXPORT_PERIOD.filing_year, period="1T"),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def approved_modelo_131_historical_registry_draft():
    provider = export_schema_provider(filing_year=MODELO_131_HISTORICAL_YEAR, period="4T", modelos=("131",))
    draft = build_draft(
        modelo="131",
        period=Period.from_year_and_code(MODELO_131_HISTORICAL_YEAR, "4T"),
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
            "modelo-131-resultados-negativos-anteriores": Decimal("1"),
            _M131_HISTORICAL_12_CASILLA: Decimal("0.50"),
            _M131_HISTORICAL_14_CASILLA: Decimal("0.25"),
        },
        schema_provider=provider,
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def approved_modelo_111_registry_draft():
    draft = build_draft(
        modelo="111",
        period=EXPORT_PERIOD,
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
        schema_provider=export_schema_provider(filing_year=EXPORT_PERIOD.filing_year, period="1T", modelos=("111",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def _approved_modelo_115_registry_draft():
    draft = build_draft(
        modelo="115",
        period=EXPORT_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            _M115_PERCEPTORES_CASILLA: Decimal("1"),
            _M115_BASE_CASILLA: Decimal("1250.50"),
            _M115_PREVIOUS_RESULT_CASILLA: Decimal("10.00"),
        },
        schema_provider=export_schema_provider(filing_year=EXPORT_PERIOD.filing_year, period="1T", modelos=("115",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


@cache
def _approved_modelo_123_registry_draft():
    draft = build_draft(
        modelo="123",
        period=EXPORT_PERIOD,
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
        schema_provider=export_schema_provider(filing_year=EXPORT_PERIOD.filing_year, period="1T", modelos=("123",)),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _record_wire_length(record: ExportRecordDefinition) -> int:
    return max((field.offset or 0) + (field.length or 0) - 1 for field in record.fields)


def _line_ending_length(line_ending: str) -> int:
    return {"crlf": 2, "lf": 1}.get(line_ending, 0)


def _next_record_cursor(cursor: int, record: ExportRecordDefinition, record_length: int) -> int:
    return cursor + record_length + _line_ending_length(record.line_ending)


def _field_slice_in_record(record: ExportRecordDefinition, field_id: str, cursor: int) -> slice:
    field: ExportFieldDefinition = next(item for item in record.fields if item.id == field_id)
    if field.offset is None or field.length is None:
        raise AssertionError(f"export field {field.id!r} does not declare a fixed slice")
    start = cursor + field.offset - 1
    return slice(start, start + field.length)


def _field_slice(layout: ExportLayoutDefinition, record_id: str, field_id: str) -> slice:
    cursor = 0
    for record in sorted(layout.records, key=lambda item: item.order):
        record_length = _record_wire_length(record)
        if record.id == record_id:
            return _field_slice_in_record(record, field_id, cursor)
        cursor = _next_record_cursor(cursor, record, record_length)
    raise AssertionError(f"export record {record_id!r} not found")


def m151_producer_snapshot() -> FilingProducerSnapshot:
    """Producer facts for the Modelo 151 export coordinate."""
    return _general_ingreso_producer_snapshot("151")


@cache
def modelo_151_export_coordinate_draft():
    """A Modelo 151 draft at the annual coordinate whose layout carries a filing envelope.

    Deliberately built from no inputs and left in its constructed status. The
    payload-acceptance surface this supports re-hashes emitted bytes against
    recorded acceptance evidence and never reads the draft; the draft exists
    because the proof entry refuses a coordinate its draft does not match. Giving
    it contrived values would suggest a completeness this fixture does not have
    and does not need.
    """
    filing_year = filing_year_envelope().horizon
    return build_draft(
        modelo="151",
        period=Period.from_year_and_code(filing_year, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Emilio Export Test"),
        inputs={},
        schema_provider=export_schema_provider(filing_year=filing_year, period="0A", modelos=("151",)),
    )
