"""A sociedad's Modelo 202 page 01 renders the entity facts it states and the rates the law sets.

Every supported year is enumerated from the registry envelope. For each, the
selected edition's own layout is read from the published authority, the export
resolves the producer view from the profile facts that layout cites, the real
snapshot builder and producer resolver run, and each page 01 slot is rendered
through the real fixed-width field renderer. The expected bytes are written from
the official designs: an "X o blanco" mark is X when the fact holds, the
"superior a 6.000.000 euros" mark compares the twelve-month turnover, and the
turnover band is "0" No consta below 10 M, "1" from 10 to 20 M, "2" from 20 to
60 M and "3" from 60 M.

The tipo de gravamen is never stated: the stated régimen marks select the LIS
art. 29 lane and the Modelo 200 edition of the período's ejercicio publishes
its rates, consigned as two digits joined with "/" (2025 design Nota 10). The
expected rates are read here straight from those published parameters for the
período's first day, so a test follows the registry rather than a year table.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from itertools import pairwise
from pathlib import Path

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.errors.error_codes import resolve_error_message
from ....core.external_constants import OutputLanguage
from ....core.filing_producer_key import FilingProducerKey
from ....core.modelo import Modelo
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.cnae_classification import (
    cnae_classification_names,
    required_cnae_classification,
)
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ....domain.calculations.registry.schema_formula import ParameterDefinition
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.period import calculation_filing_date, instalment_period_in_progress_date
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...filing.export_producer import filing_producer_values
from ...filing.producer_snapshot import FilingProducerSnapshotError, build_filing_producer_snapshot
from ...filing.record_field_renderer import format_field, header_field_value
from ...filing.runtime import build_runtime_schema_provider
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
from ..export_m202_tipo_gravamen import GovernedRates, RegimenMarks, tipo_gravamen_rates
from ..export_periodo_impositivo import PeriodoImpositivo, periodo_impositivo_from_facts
from ..incn_periodo_anterior import IncnPeriodoAnteriorReader
from .incn_periodo_anterior_support import held_return, nothing_held, reads_preceding_turnover

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_K = FilingProducerKey
_YEARS = filing_year_envelope().years
_PERIOD = "1P"
_LOCALES = ("es", "ca", "en", "hu")
_PROFILE_EDIT_ACTION = "operator.profile.edit"
_CNAE_PATH = "taxpayer_type.principal_cnae"
_CLASSIFICATION_PATH = "taxpayer_type.principal_cnae_classification"
_INCN_PATH = "taxpayer_type.incn_prior_12_months"
_PRIOR_PERIODO_TURNOVER_KEY = "application.filing.export.errors.m202_prior_periodo_turnover_unreadable"
_PRIOR_PERIODO_TURNOVER_DISAGREES_KEY = "application.filing.export.errors.m202_prior_periodo_turnover_disagrees"
_COOPERATIVA_PATH = "taxpayer_type.cooperativa_fiscalmente_protegida"
_ERD_PATH = "taxpayer_type.erd_tipo_gravamen_especifico"
_TIPO_FACT = "tipo_gravamen_impuesto_sociedades"

_GENERAL = "is.modelo-200.tipo-gravamen-general"
_NEW_ENTITY = "is.modelo-200.tipo-gravamen-new-entity-first-2-years"
_COOPERATIVE = "is.modelo-200.tipo-gravamen-cooperative-protected"
_NON_PROFIT = "is.modelo-200.tipo-gravamen-non-profit-special-regime"
_ERD = "is.modelo-200.tipo-gravamen-erd-art101"
_MICRO_SCALE = "is.modelo-200.tipo-gravamen-pyme"
_MICRO_THRESHOLD = "is.modelo-200.incn-umbral-microempresa"
_CORE_RATE_PARAMETERS = (_GENERAL, _NEW_ENTITY, _COOPERATIVE, _NON_PROFIT)
_LANE_PARAMETERS = (_ERD, _MICRO_SCALE, _MICRO_THRESHOLD)
_RATE_PARAMETERS = (*_CORE_RATE_PARAMETERS, *_LANE_PARAMETERS)

#: A sociedad under a venture-capital régimen and none of the other datos adicionales.
_STATED: Mapping[str, str] = {
    _CNAE_PATH: "6201",
    "taxpayer_type.regimen_ley_49_2002": "false",
    "taxpayer_type.regimen_socimi": "false",
    "taxpayer_type.regimen_entidad_capital_riesgo": "true",
    "taxpayer_type.regimen_entidades_navieras_tonelaje": "false",
    _ERD_PATH: "false",
    _COOPERATIVA_PATH: "false",
    "taxpayer_type.marca_instrumental": "false",
    "taxpayer_type.entity_type": "legal_entity",
    "tax_residence.jurisdiction_scope": "common_regime",
}
_TURNOVER = Decimal("15000000")
_MICRO_TURNOVER = Decimal("500000")
_ERD_TURNOVER = Decimal("5000000")

#: The bytes each stated page 01 slot takes for the stated sociedad, by the designs' contents column.
_EXPECTED_BY_KEY: Mapping[FilingProducerKey, str] = {
    _K.M202_CNAE_ACTIVIDAD_PRINCIPAL: "6201",
    _K.M202_REGIMEN_LEY_49_2002_SIN_FINES_LUCRATIVOS: " ",
    _K.M202_REGIMEN_LEY_11_2009_SOCIMI: " ",
    _K.M202_REGIMEN_ENTIDAD_CAPITAL_RIESGO: "X",
    _K.M202_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE: " ",
    _K.M202_REGIMEN_ARTICULO_101_LIS_REDUCIDA_DIMENSION: " ",
    _K.M202_CIFRA_NEGOCIOS_DOCE_MESES_UMBRAL: "X",
    _K.M202_COOPERATIVA_FISCALMENTE_PROTEGIDA: " ",
    _K.M202_MARCA_INSTRUMENTAL: " ",
    _K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL: " ",
    _K.M202_MULTIPLES_TIPOS_IMPOSITIVOS: " ",
    _K.M202_COOPERATIVA_O_MULTIPLES_TIPOS: "0",
    _K.M202_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO: "1",
}
_RENDERED_KEYS = frozenset({*_EXPECTED_BY_KEY, _K.M202_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES})


_PAGE_01_BY_YEAR: dict[int, tuple[ExportRecordDefinition, ...]] = {}


@pytest.fixture
def page_01_fields(operation: PinnedAuthorityOperation) -> Mapping[int, tuple[ExportRecordDefinition, ...]]:
    """Each supported year's 202 layout records, read once inside the test's pinned authority scope."""
    for year in _YEARS:
        if year not in _PAGE_01_BY_YEAR:
            provider = build_runtime_schema_provider(
                filing_year=year,
                period=Period.from_year_and_code(year, _PERIOD),
                modelos=("202",),
                operation=operation,
            )
            _PAGE_01_BY_YEAR[year] = tuple(
                record for layout in provider.get_subview("202").export_layouts for record in layout.records
            )
    return _PAGE_01_BY_YEAR


def _published_rates(operation: PinnedAuthorityOperation, year: int) -> Mapping[str, ParameterDefinition]:
    snapshot = operation.snapshot("200", filing_year=year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY)
    return {parameter.id: parameter for parameter in snapshot.revision.parameters}


def _years_with_rates(operation: PinnedAuthorityOperation) -> tuple[int, ...]:
    """The supported years whose Modelo 200 edition publishes every rate the lanes read."""
    return tuple(year for year in _YEARS if set(_RATE_PARAMETERS) <= _published_rates(operation, year).keys())


def _years_with_core_rates(operation: PinnedAuthorityOperation) -> tuple[int, ...]:
    """The supported years whose Modelo 200 edition publishes the rates every edition carries."""
    return tuple(year for year in _YEARS if set(_CORE_RATE_PARAMETERS) <= _published_rates(operation, year).keys())


def _rate(operation: PinnedAuthorityOperation, year: int, parameter_id: str) -> str:
    """The two-digit percentage the parameter publishes for the período starting on 1 January."""
    start = date(year, 1, 1)
    (value,) = (
        value.value
        for value in _published_rates(operation, year)[parameter_id].values
        if value.valid_from <= start and (value.valid_to is None or start <= value.valid_to)
    )
    return f"{int(value):02d}"


def _micro_scale(operation: PinnedAuthorityOperation, year: int) -> tuple[str, ...]:
    start = date(year, 1, 1)
    rows = sorted(
        (
            row
            for row in _published_rates(operation, year)[_MICRO_SCALE].brackets
            if row.valid_from <= start and (row.valid_to is None or start <= row.valid_to)
        ),
        key=lambda row: row.lower_bound,
    )
    return tuple(dict.fromkeys(f"{int(row.marginal_rate * 100):02d}" for row in rows))


def _filing_date(year: int) -> date:
    return calculation_filing_date(Period.from_year_and_code(year, _PERIOD))


def _required_classification(operation: PinnedAuthorityOperation, year: int) -> str:
    return required_cnae_classification(effective_date=_filing_date(year), authority=operation)


def _cited(records: tuple[ExportRecordDefinition, ...]) -> frozenset[FilingProducerKey]:
    return frozenset(
        field.producer_key for record in records for field in record.fields if field.producer_key is not None
    )


def _sociedad(turnover: Decimal | None = _TURNOVER) -> TaxpayerProfile:
    return TaxpayerProfile(tax_id=TAXPAYER_TAX_ID, iva_regime=IVARegime("GENERAL"), incn_prior_12_months=turnover)


def _periodo(year: int, *, constitution: date | None = None) -> PeriodoImpositivo:
    """The calendar período the year's 1P instalment is on account of, for an entity constituted long before."""
    on = instalment_period_in_progress_date(Period.from_year_and_code(year, _PERIOD))
    assert on is not None
    return periodo_impositivo_from_facts(
        modelo="202",
        on=on,
        profile_values={
            "taxpayer_type.cierre_ejercicio_dia": "31",
            "taxpayer_type.cierre_ejercicio_mes": "12",
            "taxpayer_type.fecha_constitucion": (constitution or date(year - 5, 1, 1)).isoformat(),
        },
    )


def _resolve(
    records: tuple[ExportRecordDefinition, ...],
    year: int,
    values: Mapping[str, str],
    *,
    operation: PinnedAuthorityOperation,
    turnover: Decimal | None = _TURNOVER,
    periodo: PeriodoImpositivo | None = None,
    held: Decimal | None = None,
) -> dict[FilingProducerKey, object]:
    # The CNAE is stated in the classification the year requires unless a test states another,
    # and the twelve-month turnover the workflow profile carries is the one the profile states.
    stated = {
        _CLASSIFICATION_PATH: _required_classification(operation, year),
        **({} if turnover is None else {_INCN_PATH: str(turnover)}),
        **values,
    }
    periodo = periodo or _periodo(year)
    # Nothing is held of the preceding período unless a test holds its Modelo 200.
    reader: IncnPeriodoAnteriorReader = (
        nothing_held(operation, periodo.start.year)
        if held is None
        else held_return(operation, periodo.start.year, held)
    )
    model_profile = modelo_202_producer_profile(
        workflow_profile=_sociedad(turnover),
        profile_values=stated,
        cited_producer_keys=_cited(records),
        effective_date=_filing_date(year),
        periodo=periodo,
        filing_year=year,
        art_40_3_elected=False,
        operation=operation,
        incn_periodo_anterior=reader,
    )
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("202"),
        taxpayer_tax_id=TAXPAYER_TAX_ID,
        taxpayer_identity=taxpayer_identity(),
        presenter=producer_snapshot_presenter(),
        model_profile=model_profile,
        elections=elections(ResultDisposition.INGRESO),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )
    return filing_producer_values(snapshot)


def _rendered(
    records: tuple[ExportRecordDefinition, ...], headers: Mapping[FilingProducerKey, object]
) -> dict[FilingProducerKey, tuple[ExportFieldDefinition, str]]:
    rendered: dict[FilingProducerKey, tuple[ExportFieldDefinition, str]] = {}
    for record in records:
        for field in record.fields:
            key = field.producer_key
            if key is not None and key in _RENDERED_KEYS:
                rendered[key] = (field, format_field(field, header_field_value(field, headers), record=record))
    return rendered


def _tipo(rendered: Mapping[FilingProducerKey, tuple[ExportFieldDefinition, str]]) -> str:
    return rendered[_K.M202_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES][1].rstrip()


def _render(
    operation: PinnedAuthorityOperation,
    records: tuple[ExportRecordDefinition, ...],
    year: int,
    values: Mapping[str, str],
    *,
    turnover: Decimal | None = _TURNOVER,
    periodo: PeriodoImpositivo | None = None,
    held: Decimal | None = None,
) -> dict[FilingProducerKey, tuple[ExportFieldDefinition, str]]:
    headers = _resolve(records, year, values, operation=operation, turnover=turnover, periodo=periodo, held=held)
    return _rendered(records, headers)


def _refusal(
    records: tuple[ExportRecordDefinition, ...],
    year: int,
    values: Mapping[str, str],
    operation: PinnedAuthorityOperation,
) -> Exception:
    with pytest.raises(FilingProducerSnapshotError) as refused:
        _resolve(records, year, values, operation=operation)
    return _producer_facts_refusal(
        ModeloExportCommand(calculation_revision_id="a" * 64, output_path=Path("unused.txt"), actor="operator"),
        refused.value,
    )


def _assert_terminal_rate_refusal(error: FilingProducerSnapshotError) -> None:
    assert error.context is not None
    assert error.context["fact"] == _TIPO_FACT
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


@pytest.fixture
def rate_years(operation: PinnedAuthorityOperation) -> tuple[int, ...]:
    years = _years_with_rates(operation)
    assert years, "no supported year's Modelo 200 edition publishes the LIS art. 29 rates"
    return years


def test_a_sociedad_fills_page_01_with_its_stated_facts_and_the_general_rate(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    for year in rate_years:
        records = page_01_fields[year]
        rendered = _render(operation, records, year, _STATED)

        assert _K.M202_CNAE_ACTIVIDAD_PRINCIPAL in rendered
        assert set(rendered) == _cited(records) & _RENDERED_KEYS
        for key, (field, text) in rendered.items():
            if key is _K.M202_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES:
                assert field.length is not None, field.id
                assert text == _rate(operation, year, _GENERAL).ljust(field.length), field.id
            else:
                assert text == _EXPECTED_BY_KEY[key], (year, field.id)


def test_a_microempresa_consigns_the_scale_and_marks_the_prior_turnover(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    for year in rate_years:
        rendered = _render(operation, page_01_fields[year], year, _STATED, turnover=_MICRO_TURNOVER)

        assert _tipo(rendered) == "/".join(_micro_scale(operation, year)), year
        if _K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL in rendered:
            assert rendered[_K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL][1] == "X"
        if _K.M202_MULTIPLES_TIPOS_IMPOSITIVOS in rendered:
            # The microempresa has its own key, so its two tranches are not "otras entidades".
            assert rendered[_K.M202_MULTIPLES_TIPOS_IMPOSITIVOS][1] == " "
        if _K.M202_COOPERATIVA_O_MULTIPLES_TIPOS in rendered:
            assert rendered[_K.M202_COOPERATIVA_O_MULTIPLES_TIPOS][1] == "0"


def test_a_reducida_dimension_entity_applying_its_rate_consigns_it(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    for year in rate_years:
        values = {**_STATED, _ERD_PATH: "true"}
        rendered = _render(operation, page_01_fields[year], year, values, turnover=_ERD_TURNOVER)

        assert _tipo(rendered) == _rate(operation, year, _ERD), year
        assert rendered[_K.M202_REGIMEN_ARTICULO_101_LIS_REDUCIDA_DIMENSION][1] == "X"


@pytest.mark.parametrize(
    ("path", "parameter_id"),
    [
        ("taxpayer_type.regimen_ley_49_2002", _NON_PROFIT),
        ("taxpayer_type.new_entity_first_two_profit_periods", _NEW_ENTITY),
    ],
)
def test_a_special_regimen_consigns_its_own_rate_even_below_the_microempresa_threshold(
    path: str,
    parameter_id: str,
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    for year in rate_years:
        values = {**_STATED, path: "true"}
        rendered = _render(operation, page_01_fields[year], year, values, turnover=_MICRO_TURNOVER)

        assert _tipo(rendered) == _rate(operation, year, parameter_id), year


def test_a_cooperativa_consigns_its_protected_rate_before_the_rate_of_its_other_results(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    for year in rate_years:
        values = {**_STATED, _COOPERATIVA_PATH: "true"}
        rendered = _render(operation, page_01_fields[year], year, values)

        expected = f"{_rate(operation, year, _COOPERATIVE)}/{_rate(operation, year, _GENERAL)}"
        assert _tipo(rendered) == expected, year
        if _K.M202_COOPERATIVA_O_MULTIPLES_TIPOS in rendered:
            assert rendered[_K.M202_COOPERATIVA_O_MULTIPLES_TIPOS][1] == "1"
        if _K.M202_MULTIPLES_TIPOS_IMPOSITIVOS in rendered:
            # The cooperativa has its own key, so its two rates are not "otras entidades".
            assert rendered[_K.M202_MULTIPLES_TIPOS_IMPOSITIVOS][1] == " "


def test_a_cooperativa_microempresa_is_consigned_only_on_a_single_rate_scale(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    values = {**_STATED, _COOPERATIVA_PATH: "true"}
    for year in rate_years:
        records = page_01_fields[year]
        scale = _micro_scale(operation, year)
        if len(scale) == 1:
            rendered = _render(operation, records, year, values, turnover=_MICRO_TURNOVER)
            assert _tipo(rendered) == f"{_rate(operation, year, _COOPERATIVE)}/{scale[0]}", year
        else:
            with pytest.raises(FilingProducerSnapshotError) as refused:
                _resolve(records, year, values, operation=operation, turnover=_MICRO_TURNOVER)
            _assert_terminal_rate_refusal(refused.value)


@pytest.mark.parametrize("path", ["taxpayer_type.regimen_socimi", "taxpayer_type.regimen_entidades_navieras_tonelaje"])
def test_a_regimen_whose_rates_are_not_published_refuses_terminally_never_a_guessed_rate(
    path: str,
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    year = rate_years[-1]

    with pytest.raises(FilingProducerSnapshotError) as refused:
        _resolve(page_01_fields[year], year, {**_STATED, path: "true"}, operation=operation)

    _assert_terminal_rate_refusal(refused.value)


def test_a_year_whose_modelo_200_edition_publishes_no_rates_refuses_terminally(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    core_years = _years_with_core_rates(operation)
    for year in (year for year in _YEARS if year not in core_years):
        with pytest.raises(FilingProducerSnapshotError) as refused:
            _resolve(page_01_fields[year], year, _STATED, operation=operation)
        _assert_terminal_rate_refusal(refused.value)


def test_a_lane_the_edition_does_not_publish_is_absent_and_the_entity_applies_the_general_rate(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    # Before Ley 31/2022 there was no microempresa scale and an art. 101 entity paid the general
    # rate; an edition without those lanes must never borrow a later edition's 23 % or threshold.
    lane_less = [
        year
        for year in _years_with_core_rates(operation)
        if not set(_LANE_PARAMETERS) <= _published_rates(operation, year).keys()
    ]
    for year in lane_less:
        published = _published_rates(operation, year).keys()
        general = _rate(operation, year, _GENERAL)
        if _MICRO_SCALE not in published or _MICRO_THRESHOLD not in published:
            micro = _render(operation, page_01_fields[year], year, _STATED, turnover=_MICRO_TURNOVER)
            assert _tipo(micro) == general, year
            if _K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL in micro:
                assert micro[_K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL][1] == " "
        if _ERD not in published:
            erd = _render(operation, page_01_fields[year], year, {**_STATED, _ERD_PATH: "true"}, turnover=_ERD_TURNOVER)
            assert _tipo(erd) == general, year
            assert erd[_K.M202_REGIMEN_ARTICULO_101_LIS_REDUCIDA_DIMENSION][1] == "X"


def test_rates_without_the_microempresa_and_erd_lanes_give_no_threshold_and_the_general_rate(
    operation: PinnedAuthorityOperation,
    rate_years: tuple[int, ...],
) -> None:
    # The pre-2023 law as an edition publishes it: the rates every edition carries and no lane parameters.
    for year in rate_years:
        core = {key: value for key, value in _published_rates(operation, year).items() if key not in _LANE_PARAMETERS}
        rates = GovernedRates(on=date(year, 1, 1), parameters=core)
        erd = RegimenMarks(
            ley_49_2002=False,
            socimi=False,
            navieras_tonelaje=False,
            new_entity_first_two_profit_periods=False,
            erd_tipo_especifico=True,
            cooperativa_protegida=False,
        )

        assert rates.microempresa_threshold() is None, year
        (applied,) = tipo_gravamen_rates(marks=erd, microempresa=False, rates=rates)
        assert f"{int(applied):02d}" == _rate(operation, year, _GENERAL), year


def test_a_first_periodo_has_no_preceding_turnover_so_it_is_no_microempresa(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    for year in rate_years:
        periodo = _periodo(year, constitution=date(year, 1, 1))
        assert periodo.prior_start is None
        rendered = _render(operation, page_01_fields[year], year, _STATED, turnover=_MICRO_TURNOVER, periodo=periodo)

        assert _tipo(rendered) == _rate(operation, year, _GENERAL), year
        if _K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL in rendered:
            assert rendered[_K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL][1] == " "


def test_a_shorter_preceding_periodo_with_nothing_held_or_stated_refuses_because_its_turnover_is_its_own(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    for year in rate_years:
        records = page_01_fields[year]
        # Constituted mid-way through the year before, so that first período lasted under twelve months.
        periodo = _periodo(year, constitution=date(year - 1, 7, 1))
        assert periodo.prior_start == date(year - 1, 7, 1)
        assert not periodo.prior_lasted_twelve_months

        # The stated twelve-month turnover is not that período's, so it never selects the scale.
        with pytest.raises(FilingProducerSnapshotError) as refused:
            _resolve(records, year, _STATED, operation=operation, turnover=_MICRO_TURNOVER, periodo=periodo)
        cause = refused.value
        assert cause.translated_message == _PRIOR_PERIODO_TURNOVER_KEY, year
        assert cause.context is not None
        assert "profile_path" not in cause.context

        failure = _producer_facts_refusal(
            ModeloExportCommand(calculation_revision_id="a" * 64, output_path=Path("unused.txt"), actor="operator"),
            cause,
        )
        assert isinstance(failure, ModeloProfileReadinessError)
        verdict = nested_terminal_precondition_verdict(failure)
        assert verdict is not None
        assert verdict.action is None
        assert error_next_step(failure, OutputLanguage.EN) is None
        english = resolve_error_message(failure, locale="en")
        assert "less than twelve months" in english
        assert "Modelo 200" in english
        for locale in _LOCALES:
            message = resolve_error_message(failure, locale=locale)
            assert "200" in message, locale
            assert "%{" not in message, locale


def test_a_shorter_preceding_periodo_takes_its_turnover_from_its_held_modelo_200(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    for year in rate_years:
        periodo = _periodo(year, constitution=date(year - 1, 7, 1))
        if not reads_preceding_turnover(operation, periodo.start.year):
            continue
        # The stated twelve-month turnover is the general one; the held short período's own is below the threshold.
        rendered = _render(
            operation, page_01_fields[year], year, _STATED, turnover=_TURNOVER, periodo=periodo, held=_MICRO_TURNOVER
        )

        assert _tipo(rendered) == "/".join(_micro_scale(operation, year)), year


def test_a_held_return_disagreeing_with_the_stated_twelve_month_turnover_refuses_with_both(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    checked = 0
    for year in rate_years:
        periodo = _periodo(year)
        assert periodo.prior_lasted_twelve_months
        if not reads_preceding_turnover(operation, periodo.start.year):
            continue
        with pytest.raises(FilingProducerSnapshotError) as refused:
            _resolve(
                page_01_fields[year],
                year,
                _STATED,
                operation=operation,
                turnover=_TURNOVER,
                periodo=periodo,
                held=_MICRO_TURNOVER,
            )
        cause = refused.value
        checked += 1

        # Neither figure is taken over the other: the refusal carries both.
        assert cause.translated_message == _PRIOR_PERIODO_TURNOVER_DISAGREES_KEY, year
        assert cause.context is not None
        assert cause.context["held_value"] == str(_MICRO_TURNOVER), year
        assert cause.context["stated_value"] == str(_TURNOVER), year
        failure = _producer_facts_refusal(
            ModeloExportCommand(calculation_revision_id="a" * 64, output_path=Path("unused.txt"), actor="operator"),
            cause,
        )
        for locale in _LOCALES:
            message = resolve_error_message(failure, locale=locale)
            assert "%{" not in message, locale
    assert checked


def test_a_held_return_agreeing_with_the_stated_twelve_month_turnover_selects_the_scale(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    for year in rate_years:
        if not reads_preceding_turnover(operation, _periodo(year).start.year):
            continue
        rendered = _render(
            operation, page_01_fields[year], year, _STATED, turnover=_MICRO_TURNOVER, held=_MICRO_TURNOVER
        )

        assert _tipo(rendered) == "/".join(_micro_scale(operation, year)), year


@pytest.mark.parametrize("year", _YEARS)
def test_without_a_principal_cnae_the_export_refuses_with_the_door_to_state_it(
    year: int,
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    unstated = {path: value for path, value in _STATED.items() if path != _CNAE_PATH}

    failure = _refusal(page_01_fields[year], year, unstated, operation)

    assert isinstance(failure, ModeloProfileReadinessError)
    verdict = nested_terminal_precondition_verdict(failure)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == _PROFILE_EDIT_ACTION
    assert verdict.evidence[0].values["missing_fields"] == _CNAE_PATH
    step = error_next_step(failure, OutputLanguage.EN)
    assert isinstance(step, OperationOpenProfileFieldStepV1)
    assert step.path == _CNAE_PATH
    for locale in _LOCALES:
        message = resolve_error_message(failure, locale=locale)
        assert _CNAE_PATH in message
        assert "%{" not in message


@pytest.mark.parametrize("cnae", ["620", "62011", "62A1"])
def test_a_principal_cnae_that_is_not_four_digits_is_refused_as_unstated(
    cnae: str,
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    year = _YEARS[-1]

    failure = _refusal(page_01_fields[year], year, {**_STATED, _CNAE_PATH: cnae}, operation)

    step = error_next_step(failure, OutputLanguage.EN)
    assert isinstance(step, OperationOpenProfileFieldStepV1)
    assert step.path == _CNAE_PATH


@pytest.mark.parametrize("year", _YEARS)
def test_an_unstated_mark_and_turnover_are_refused_and_named_never_written_as_blank(
    year: int,
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    unstated = {path: value for path, value in _STATED.items() if path != "taxpayer_type.marca_instrumental"}

    with pytest.raises(FilingProducerSnapshotError) as refused:
        _resolve(page_01_fields[year], year, unstated, operation=operation, turnover=None)

    assert refused.value.context is not None
    missing = str(refused.value.context["missing_profile_paths"]).split(", ")
    assert "taxpayer_type.marca_instrumental" in missing
    assert _INCN_PATH in missing


@pytest.mark.parametrize("year", _YEARS)
def test_an_unstated_regimen_mark_is_refused_before_any_rate_is_read(
    year: int,
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    unstated = {path: value for path, value in _STATED.items() if path != _COOPERATIVA_PATH}

    with pytest.raises(FilingProducerSnapshotError) as refused:
        _resolve(page_01_fields[year], year, unstated, operation=operation)

    assert refused.value.context is not None
    assert _COOPERATIVA_PATH in str(refused.value.context["missing_profile_paths"]).split(", ")


@pytest.mark.parametrize(
    ("turnover", "above_six_million", "band"),
    [
        (Decimal("6000000"), " ", "0"),
        (Decimal("6000000.01"), "X", "0"),
        (Decimal("9999999.99"), "X", "0"),
        (Decimal("10000000"), "X", "1"),
        (Decimal("19999999.99"), "X", "1"),
        (Decimal("20000000"), "X", "2"),
        (Decimal("59999999.99"), "X", "2"),
        (Decimal("60000000"), "X", "3"),
    ],
)
def test_the_turnover_mark_and_band_follow_the_designs_bounds(
    turnover: Decimal,
    above_six_million: str,
    band: str,
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
    rate_years: tuple[int, ...],
) -> None:
    for year in rate_years:
        rendered = _render(operation, page_01_fields[year], year, _STATED, turnover=turnover)
        assert rendered[_K.M202_CIFRA_NEGOCIOS_DOCE_MESES_UMBRAL][1] == above_six_million
        assert rendered[_K.M202_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO][1] == band


def _classification_changes(operation: PinnedAuthorityOperation) -> tuple[tuple[int, int], ...]:
    """Each pair of consecutive supported years whose ejercicios require different classifications."""
    return tuple(
        (earlier, later)
        for earlier, later in pairwise(_YEARS)
        if _required_classification(operation, earlier) != _required_classification(operation, later)
    )


def test_each_ejercicio_consigns_the_code_stated_in_the_classification_it_requires(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    changes = _classification_changes(operation)
    assert changes, "the envelope holds no change of CNAE classification to prove"
    names = cnae_classification_names(authority=operation)
    for earlier, later in changes:
        for year in (earlier, later):
            required = _required_classification(operation, year)
            assert required in names
            headers = _resolve(
                page_01_fields[year], year, {**_STATED, _CLASSIFICATION_PATH: required}, operation=operation
            )
            assert headers[_K.M202_CNAE_ACTIVIDAD_PRINCIPAL] == "6201", year


def test_a_code_stated_in_the_earlier_classification_is_refused_naming_the_one_the_ejercicio_requires(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    names = cnae_classification_names(authority=operation)
    for earlier, later in _classification_changes(operation):
        required_name = names[_required_classification(operation, later)]
        values = {**_STATED, _CLASSIFICATION_PATH: _required_classification(operation, earlier)}

        failure = _refusal(page_01_fields[later], later, values, operation)

        assert isinstance(failure, ModeloProfileReadinessError)
        assert failure.context is not None
        assert failure.context["required_cnae_classification"] == required_name
        assert str(failure.context["missing_profile_paths"]).split(", ") == [_CLASSIFICATION_PATH]
        step = error_next_step(failure, OutputLanguage.EN)
        assert isinstance(step, OperationOpenProfileFieldStepV1)
        assert step.path == _CLASSIFICATION_PATH
        for locale in _LOCALES:
            assert required_name in resolve_error_message(failure, locale=locale)


def test_an_unstated_classification_is_refused_and_never_assumed(
    operation: PinnedAuthorityOperation,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    year = _YEARS[-1]

    with pytest.raises(FilingProducerSnapshotError) as refused:
        _resolve(page_01_fields[year], year, {**_STATED, _CLASSIFICATION_PATH: ""}, operation=operation)

    assert refused.value.context is not None
    assert refused.value.context["profile_path"] == _CLASSIFICATION_PATH
