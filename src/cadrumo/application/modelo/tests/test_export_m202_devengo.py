"""A Modelo 202 page 01 writes the start of the período impositivo the instalment is on account of.

The devengo's "fecha de inicio del período impositivo" (ddmmaaaa) of every
Modelo 202 record design is the entity's período impositivo, not the
instalment's: the período impositivo is the ejercicio económico (LIS art.
27.1), a pago fraccionado is on account of the período in progress the day
before its payment period opens (LIS art. 40), and the payment periods are the
first twenty days of April, October and December (LIS art. 40.1). The first
período impositivo starts on the constitution date.

Every supported year is enumerated from the registry envelope. The value runs
through the real resolver, the real producer snapshot and the real draft field
producer and fixed-width codec of the selected edition's own page 01 slot.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.external_constants import OutputLanguage
from ....core.filing_producer_key import FilingProducerKey
from ....core.modelo import Modelo
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.cnae_classification import required_cnae_classification
from ....domain.calculations.registry.export_semantics import ExportDraftAttribute
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.filing.errors import FilingExportDesignIntegrityError
from ....domain.filing.schema import ModeloDraft, registry_schema_version
from ....domain.period import calculation_filing_date, instalment_period_in_progress_date
from ....domain.submission.models import ModeloDraftStatus
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...filing.draft_construction import build_draft
from ...filing.export import render_filing_layout
from ...filing.export_producer import filing_producer_values
from ...filing.producer_snapshot import (
    FilingProducerSnapshot,
    FilingProducerSnapshotError,
    Modelo202ProducerProfile,
    build_filing_producer_snapshot,
)
from ...filing.record_field_renderer import DRAFT_VALUE_PRODUCERS, format_field
from ...filing.runtime import ModeloOperatorProfile, build_runtime_schema_provider
from ...filing.tests.producer_snapshot_support import (
    TAXPAYER_TAX_ID,
    elections,
    producer_snapshot_presenter,
    taxpayer_identity,
)
from ...operations.next_step import OperationOpenProfileFieldStepV1, error_next_step
from ..action_errors import ModeloProfileReadinessError
from ..export_accounts import _producer_facts_refusal
from ..export_contracts import ModeloExportCommand
from ..export_m202_profile import modelo_202_producer_profile
from ..export_periodo_impositivo import (
    CIERRE_EJERCICIO_DIA_PATH,
    CIERRE_EJERCICIO_MES_PATH,
    FECHA_CONSTITUCION_PATH,
    periodo_impositivo_from_facts,
    periodo_impositivo_start_from_facts,
)
from .incn_periodo_anterior_support import nothing_held

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEARS = filing_year_envelope().years
#: LIS art. 40.1: the instalments are paid in the first twenty days of April, October and December.
_PAYMENT_MONTH = {"1P": 4, "2P": 10, "3P": 12}
_INSTALMENTS = tuple(_PAYMENT_MONTH)
_PROFILE_EDIT_ACTION = "operator.profile.edit"
#: Any instant: a draft's timestamps take no part in the devengo.
_STAMPED = datetime.fromtimestamp(0, tz=UTC)

_RECORDS_BY_YEAR: dict[int, tuple[ExportRecordDefinition, ...]] = {}


@pytest.fixture
def records_by_year(operation: PinnedAuthorityOperation) -> Mapping[int, tuple[ExportRecordDefinition, ...]]:
    """Each supported year's 202 layout records, read once inside the test's pinned authority scope."""
    for year in _YEARS:
        if year not in _RECORDS_BY_YEAR:
            provider = build_runtime_schema_provider(
                filing_year=year,
                period=Period.from_year_and_code(year, "1P"),
                modelos=("202",),
                operation=operation,
            )
            _RECORDS_BY_YEAR[year] = tuple(
                record for layout in provider.get_subview("202").export_layouts for record in layout.records
            )
    return _RECORDS_BY_YEAR


def _devengo_slot(records: tuple[ExportRecordDefinition, ...]) -> tuple[ExportRecordDefinition, ExportFieldDefinition]:
    slots = [
        (record, field)
        for record in records
        for field in record.fields
        if field.draft_attribute is ExportDraftAttribute.PERIOD_START_DATE
    ]
    assert len(slots) == 1, slots
    return slots[0]


def _stated(*, closing: tuple[int, int], constitution: date) -> dict[str, str]:
    day, month = closing
    return {
        CIERRE_EJERCICIO_DIA_PATH: str(day),
        CIERRE_EJERCICIO_MES_PATH: str(month),
        FECHA_CONSTITUCION_PATH: constitution.isoformat(),
    }


def _draft(period: Period) -> ModeloDraft:
    return ModeloDraft(
        draft_id="devengo-proof",
        modelo="202",
        period=period,
        profile_tax_id=TAXPAYER_TAX_ID,
        subject_tax_id=TAXPAYER_TAX_ID,
        snapshot_ref=RegistrySnapshotRef(
            modelo="202", revision_id="unused", modelo_year=period.filing_year, period=period.registry_token
        ),
        status=ModeloDraftStatus.APROBADO,
        values=(),
        created_at=_STAMPED,
        updated_at=_STAMPED,
        schema_version=registry_schema_version(modelo="202", revision_id="unused"),
    )


def _snapshot(start: date | None) -> FilingProducerSnapshot:
    return build_filing_producer_snapshot(
        modelo=Modelo("202"),
        taxpayer_tax_id=TAXPAYER_TAX_ID,
        taxpayer_identity=taxpayer_identity(),
        presenter=producer_snapshot_presenter(),
        model_profile=Modelo202ProducerProfile(
            taxpayer_profile=TaxpayerProfile(tax_id=TAXPAYER_TAX_ID, iva_regime=IVARegime("GENERAL")),
            activities=(),
        ),
        elections=elections(ResultDisposition.INGRESO),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
        periodo_impositivo_start=start,
    )


def _rendered_devengo(records: tuple[ExportRecordDefinition, ...], period: Period, values: Mapping[str, str]) -> str:
    on = instalment_period_in_progress_date(period)
    assert on is not None
    start = periodo_impositivo_start_from_facts(modelo="202", on=on, profile_values=values)
    record, field = _devengo_slot(records)
    assert field.draft_attribute is not None
    value = DRAFT_VALUE_PRODUCERS[field.draft_attribute](_draft(period), _snapshot(start))
    return format_field(field, value, record=record)


def _ddmmaaaa(day: date) -> str:
    return f"{day.day:02d}{day.month:02d}{day.year:04d}"


def _refusal(period: Period, values: Mapping[str, str]) -> Exception:
    on = instalment_period_in_progress_date(period)
    assert on is not None
    with pytest.raises(FilingProducerSnapshotError) as refused:
        periodo_impositivo_start_from_facts(modelo="202", on=on, profile_values=values)
    return _producer_facts_refusal(
        ModeloExportCommand(calculation_revision_id="a" * 64, output_path=Path("unused.txt"), actor="operator"),
        refused.value,
    )


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("instalment", _INSTALMENTS)
def test_a_calendar_ejercicio_writes_the_first_of_january_of_the_instalments_year(
    year: int, instalment: str, records_by_year: Mapping[int, tuple[ExportRecordDefinition, ...]]
) -> None:
    period = Period.from_year_and_code(year, instalment)
    values = _stated(closing=(31, 12), constitution=date(year - 3, 3, 15))

    assert _rendered_devengo(records_by_year[year], period, values) == _ddmmaaaa(date(year, 1, 1))


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("instalment", _INSTALMENTS)
def test_an_ejercicio_closing_on_30_june_writes_the_first_of_july_in_progress(
    year: int, instalment: str, records_by_year: Mapping[int, tuple[ExportRecordDefinition, ...]]
) -> None:
    period = Period.from_year_and_code(year, instalment)
    values = _stated(closing=(30, 6), constitution=date(year - 3, 3, 15))
    # The período in progress the day before the payment month: the one that began 1 July
    # of this year once that day is past, else the one that began 1 July a year earlier.
    day_before = date(year, _PAYMENT_MONTH[instalment], 1) - timedelta(days=1)
    expected = date(year, 7, 1) if day_before >= date(year, 7, 1) else date(year - 1, 7, 1)

    assert _rendered_devengo(records_by_year[year], period, values) == _ddmmaaaa(expected)


@pytest.mark.parametrize("year", _YEARS)
def test_the_first_periodo_after_constitution_starts_on_the_constitution_date(
    year: int, records_by_year: Mapping[int, tuple[ExportRecordDefinition, ...]]
) -> None:
    constitution = date(year, 2, 10)
    values = _stated(closing=(31, 12), constitution=constitution)

    for instalment in _INSTALMENTS:
        period = Period.from_year_and_code(year, instalment)
        assert _rendered_devengo(records_by_year[year], period, values) == _ddmmaaaa(constitution)


@pytest.mark.parametrize("year", _YEARS)
def test_without_the_ejercicio_closing_or_constitution_the_export_refuses_with_the_door(year: int) -> None:
    failure = _refusal(Period.from_year_and_code(year, "1P"), {})

    assert isinstance(failure, ModeloProfileReadinessError)
    assert failure.context is not None
    assert str(failure.context["missing_profile_paths"]).split(", ") == [
        CIERRE_EJERCICIO_DIA_PATH,
        CIERRE_EJERCICIO_MES_PATH,
        FECHA_CONSTITUCION_PATH,
    ]
    step = error_next_step(failure, OutputLanguage.EN)
    assert isinstance(step, OperationOpenProfileFieldStepV1)
    assert step.path == CIERRE_EJERCICIO_DIA_PATH
    verdict = nested_terminal_precondition_verdict(failure)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == _PROFILE_EDIT_ACTION


def test_a_closing_day_the_month_never_has_names_both_halves() -> None:
    year = _YEARS[-1]
    values = _stated(closing=(31, 4), constitution=date(year - 3, 3, 15))

    failure = _refusal(Period.from_year_and_code(year, "1P"), values)

    assert isinstance(failure, ModeloProfileReadinessError)
    assert failure.context is not None
    assert str(failure.context["missing_profile_paths"]).split(", ") == [
        CIERRE_EJERCICIO_DIA_PATH,
        CIERRE_EJERCICIO_MES_PATH,
    ]


def test_an_entity_constituted_after_the_instalments_day_is_refused_at_its_constitution_date() -> None:
    year = _YEARS[-1]
    values = _stated(closing=(31, 12), constitution=date(year, 5, 1))

    failure = _refusal(Period.from_year_and_code(year, "1P"), values)

    step = error_next_step(failure, OutputLanguage.EN)
    assert isinstance(step, OperationOpenProfileFieldStepV1)
    assert step.path == FECHA_CONSTITUCION_PATH


def test_an_instalment_rendered_without_its_resolved_periodo_is_an_assembly_fault(
    records_by_year: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    year = _YEARS[-1]
    record, field = _devengo_slot(records_by_year[year])
    assert field.draft_attribute is not None
    del record

    with pytest.raises(FilingExportDesignIntegrityError):
        DRAFT_VALUE_PRODUCERS[field.draft_attribute](_draft(Period.from_year_and_code(year, "1P")), _snapshot(None))


#: A sociedad that states every page 01 fact and applies none of the datos adicionales regimes.
_PAGE_01_FACTS: Mapping[str, str] = {
    "taxpayer_type.principal_cnae": "6201",
    "taxpayer_type.regimen_ley_49_2002": "false",
    "taxpayer_type.regimen_socimi": "false",
    "taxpayer_type.regimen_entidad_capital_riesgo": "false",
    "taxpayer_type.regimen_entidades_navieras_tonelaje": "false",
    "taxpayer_type.erd_tipo_gravamen_especifico": "false",
    "taxpayer_type.cooperativa_fiscalmente_protegida": "false",
    "taxpayer_type.marca_instrumental": "false",
    "taxpayer_type.entity_type": "legal_entity",
    "taxpayer_type.incn_prior_12_months": "500000",
    "tax_residence.jurisdiction_scope": "common_regime",
}
#: The 1P instalment's own inputs: an art. 40.2 instalment with a zero base.
_INSTALMENT_INPUTS: Mapping[str, Decimal] = {
    "01": Decimal("0"),
    "modelo-202-pagos-fraccionados-anteriores": Decimal("0"),
    "modelo-202-incn-prior-12-months": Decimal("500000"),
    "modelo-202-cuota-base-ejercicio-anterior": Decimal("0"),
}


def _publishes_rates(operation: PinnedAuthorityOperation, year: int) -> bool:
    """Whether the Modelo 200 edition of the year publishes the LIS art. 29 rates page 01 consigns."""
    snapshot = operation.snapshot("200", filing_year=year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY)
    return any(parameter.id == "is.modelo-200.tipo-gravamen-general" for parameter in snapshot.revision.parameters)


@pytest.mark.parametrize("year", _YEARS)
def test_a_sociedad_stating_every_page_01_fact_exports_its_1p_instalment(
    year: int, operation: PinnedAuthorityOperation
) -> None:
    period = Period.from_year_and_code(year, "1P")
    provider = build_runtime_schema_provider(filing_year=year, period=period, modelos=("202",), operation=operation)
    layout = provider.get_subview("202").export_layouts[0]
    cited = frozenset(
        field.producer_key for record in layout.records for field in record.fields if field.producer_key is not None
    )
    draft = build_draft(
        modelo="202",
        period=period,
        profile=ModeloOperatorProfile(tax_id=TAXPAYER_TAX_ID, display_name="Sociedad devengo"),
        inputs=dict(_INSTALMENT_INPUTS),
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    on = instalment_period_in_progress_date(period, authority=operation)
    assert on is not None
    periodo = periodo_impositivo_from_facts(
        modelo="202", on=on, profile_values=_stated(closing=(31, 12), constitution=date(year - 3, 3, 15))
    )

    def producer_profile() -> Modelo202ProducerProfile:
        return modelo_202_producer_profile(
            workflow_profile=TaxpayerProfile(
                tax_id=TAXPAYER_TAX_ID, iva_regime=IVARegime("GENERAL"), incn_prior_12_months=Decimal("500000")
            ),
            profile_values={
                **_PAGE_01_FACTS,
                "taxpayer_type.principal_cnae_classification": required_cnae_classification(
                    effective_date=calculation_filing_date(period, authority=operation), authority=operation
                ),
            },
            cited_producer_keys=cited,
            effective_date=calculation_filing_date(period, authority=operation),
            periodo=periodo,
            filing_year=year,
            art_40_3_elected=False,
            operation=operation,
            incn_periodo_anterior=nothing_held(operation, periodo.start.year),
        )

    if not _publishes_rates(operation, year):
        # Page 01 consigns rates this year's Modelo 200 edition does not publish: nothing is written.
        with pytest.raises(FilingProducerSnapshotError, match="tipo de gravamen"):
            producer_profile()
        return
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("202"),
        taxpayer_tax_id=TAXPAYER_TAX_ID,
        taxpayer_identity=taxpayer_identity(),
        presenter=producer_snapshot_presenter(),
        model_profile=producer_profile(),
        elections=elections(ResultDisposition.INGRESO),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
        periodo_impositivo_start=periodo.start,
    )

    payload = render_filing_layout(
        layout,
        registry_snapshot=provider.get_snapshot("202"),
        draft=draft,
        headers=filing_producer_values(snapshot),
        producer_snapshot=snapshot,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
    )

    record, field = _devengo_slot(tuple(layout.records))
    del record
    assert field.offset is not None
    text = payload.decode("iso-8859-1")
    assert text[field.offset - 1 : field.offset - 1 + 8] == _ddmmaaaa(date(year, 1, 1))
    # Below the art. 40.3 threshold without the election: the art. 40.2 modality "A" (Nota 11),
    # and the common normativa's blank (Nota 9).
    slots = {
        key: field
        for record in layout.records
        for field in record.fields
        if (key := field.producer_key)
        in {FilingProducerKey.M202_MODALIDAD_LIQUIDACION, FilingProducerKey.M202_NORMATIVA_TERRITORIO_FORAL}
    }
    assert len(slots) == 2, slots
    for key, expected in (
        (FilingProducerKey.M202_MODALIDAD_LIQUIDACION, "A"),
        (FilingProducerKey.M202_NORMATIVA_TERRITORIO_FORAL, " "),
    ):
        offset = slots[key].offset
        assert offset is not None
        assert text[offset - 1] == expected, (year, key)
