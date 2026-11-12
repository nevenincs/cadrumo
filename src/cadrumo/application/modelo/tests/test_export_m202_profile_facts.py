"""A sociedad's Modelo 202 page 01 renders the entity facts it states, and refuses with the door to state a missing one.

Every supported year is enumerated from the registry envelope. For each, the
selected edition's own layout is read from the published authority, the export
resolves the producer view from the profile facts that layout cites, the real
snapshot builder and producer resolver run, and each page 01 slot is rendered
through the real fixed-width field renderer. The expected bytes are written from
the official designs: an "X o blanco" mark is X when the fact holds, the
"superior a 6.000.000 euros" mark compares the twelve-month turnover, and the
turnover band is "0" No consta below 10 M, "1" from 10 to 20 M, "2" from 20 to
60 M and "3" from 60 M.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.errors.error_codes import resolve_error_message
from ....core.external_constants import OutputLanguage
from ....core.filing_producer_key import FilingProducerKey
from ....core.modelo import Modelo
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.period import calculation_filing_date
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

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_K = FilingProducerKey
_YEARS = filing_year_envelope().years
_PERIOD = "1P"
_LOCALES = ("es", "ca", "en", "hu")
_PROFILE_EDIT_ACTION = "operator.profile.edit"
_CNAE_PATH = "taxpayer_type.principal_cnae"
_INCN_PATH = "taxpayer_type.incn_prior_12_months"
_PRIOR_PERIOD_PATH = "taxpayer_type.incn_periodo_anterior_inferior_1m"

#: A sociedad that applies the tonnage régimen and none of the other datos adicionales.
_STATED: Mapping[str, str] = {
    _CNAE_PATH: "6201",
    "taxpayer_type.regimen_ley_49_2002": "false",
    "taxpayer_type.regimen_socimi": "false",
    "taxpayer_type.regimen_entidad_capital_riesgo": "false",
    "taxpayer_type.regimen_entidades_navieras_tonelaje": "true",
    "taxpayer_type.erd_tipo_gravamen_especifico": "false",
    "taxpayer_type.cooperativa_fiscalmente_protegida": "false",
    "taxpayer_type.marca_instrumental": "false",
    _PRIOR_PERIOD_PATH: "false",
    "taxpayer_type.multiples_tipos_impositivos": "false",
    "taxpayer_type.tipo_gravamen_is": "25",
}
_TURNOVER = Decimal("15000000")

#: The bytes each page 01 slot takes for the stated sociedad, by the designs' contents column.
_EXPECTED_BY_KEY: Mapping[FilingProducerKey, str] = {
    _K.M202_CNAE_ACTIVIDAD_PRINCIPAL: "6201",
    _K.M202_REGIMEN_LEY_49_2002_SIN_FINES_LUCRATIVOS: " ",
    _K.M202_REGIMEN_LEY_11_2009_SOCIMI: " ",
    _K.M202_REGIMEN_ENTIDAD_CAPITAL_RIESGO: " ",
    _K.M202_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE: "X",
    _K.M202_REGIMEN_ARTICULO_101_LIS_REDUCIDA_DIMENSION: " ",
    _K.M202_CIFRA_NEGOCIOS_DOCE_MESES_UMBRAL: "X",
    _K.M202_COOPERATIVA_FISCALMENTE_PROTEGIDA: " ",
    _K.M202_MARCA_INSTRUMENTAL: " ",
    _K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL: " ",
    _K.M202_MULTIPLES_TIPOS_IMPOSITIVOS: " ",
    _K.M202_COOPERATIVA_O_MULTIPLES_TIPOS: "0",
    _K.M202_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO: "1",
}


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


def _cited(records: tuple[ExportRecordDefinition, ...]) -> frozenset[FilingProducerKey]:
    return frozenset(
        field.producer_key for record in records for field in record.fields if field.producer_key is not None
    )


def _sociedad(turnover: Decimal | None = _TURNOVER) -> TaxpayerProfile:
    return TaxpayerProfile(tax_id=TAXPAYER_TAX_ID, iva_regime=IVARegime("GENERAL"), incn_prior_12_months=turnover)


def _resolve(
    records: tuple[ExportRecordDefinition, ...],
    year: int,
    values: Mapping[str, str],
    *,
    turnover: Decimal | None = _TURNOVER,
) -> dict[FilingProducerKey, object]:
    model_profile = modelo_202_producer_profile(
        workflow_profile=_sociedad(turnover),
        profile_values=values,
        cited_producer_keys=_cited(records),
        effective_date=calculation_filing_date(Period.from_year_and_code(year, _PERIOD)),
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
            if key is not None and (key in _EXPECTED_BY_KEY or key is _K.M202_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES):
                rendered[key] = (field, format_field(field, header_field_value(field, headers), record=record))
    return rendered


def _refusal(records: tuple[ExportRecordDefinition, ...], year: int, values: Mapping[str, str]) -> Exception:
    with pytest.raises(FilingProducerSnapshotError) as refused:
        _resolve(records, year, values)
    return _producer_facts_refusal(
        ModeloExportCommand(calculation_revision_id="a" * 64, output_path=Path("unused.txt"), actor="operator"),
        refused.value,
    )


@pytest.mark.parametrize("year", _YEARS)
def test_a_sociedad_that_states_its_facts_fills_page_01_as_the_design_writes_them(
    year: int, page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]]
) -> None:
    records = page_01_fields[year]
    rendered = _rendered(records, _resolve(records, year, _STATED))

    cited_expected = _cited(records) & (_EXPECTED_BY_KEY.keys() | {_K.M202_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES})
    assert _K.M202_CNAE_ACTIVIDAD_PRINCIPAL in cited_expected
    assert set(rendered) == cited_expected
    for key, (field, text) in rendered.items():
        if key is _K.M202_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES:
            assert field.length is not None, field.id
            assert text == "25".ljust(field.length), field.id
        else:
            assert text == _EXPECTED_BY_KEY[key], field.id


@pytest.mark.parametrize("year", _YEARS)
def test_without_a_principal_cnae_the_export_refuses_with_the_door_to_state_it(
    year: int, page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]]
) -> None:
    unstated = {path: value for path, value in _STATED.items() if path != _CNAE_PATH}

    failure = _refusal(page_01_fields[year], year, unstated)

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
    cnae: str, page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]]
) -> None:
    year = _YEARS[-1]

    failure = _refusal(page_01_fields[year], year, {**_STATED, _CNAE_PATH: cnae})

    step = error_next_step(failure, OutputLanguage.EN)
    assert isinstance(step, OperationOpenProfileFieldStepV1)
    assert step.path == _CNAE_PATH


@pytest.mark.parametrize("year", _YEARS)
def test_an_unstated_mark_and_turnover_are_refused_and_named_never_written_as_blank(
    year: int, page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]]
) -> None:
    records = page_01_fields[year]
    unstated = {path: value for path, value in _STATED.items() if path != "taxpayer_type.marca_instrumental"}

    with pytest.raises(FilingProducerSnapshotError) as refused:
        _resolve(records, year, unstated, turnover=None)

    assert refused.value.context is not None
    missing = str(refused.value.context["missing_profile_paths"]).split(", ")
    assert "taxpayer_type.marca_instrumental" in missing
    assert _INCN_PATH in missing


@pytest.mark.parametrize("year", _YEARS)
def test_a_fact_the_years_design_has_no_position_for_is_never_asked(
    year: int, page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]]
) -> None:
    records = page_01_fields[year]
    unstated = {path: value for path, value in _STATED.items() if path != _PRIOR_PERIOD_PATH}

    if _K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL in _cited(records):
        with pytest.raises(FilingProducerSnapshotError, match=_PRIOR_PERIOD_PATH):
            _resolve(records, year, unstated)
    else:
        assert _resolve(records, year, unstated)[_K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL] is None


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
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    for year in _YEARS:
        records = page_01_fields[year]
        rendered = _rendered(records, _resolve(records, year, _STATED, turnover=turnover))
        assert rendered[_K.M202_CIFRA_NEGOCIOS_DOCE_MESES_UMBRAL][1] == above_six_million
        assert rendered[_K.M202_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO][1] == band


@pytest.mark.parametrize(
    ("cooperativa", "multiples", "key"),
    [("true", "false", "1"), ("true", "true", "1"), ("false", "true", "2"), ("false", "false", "0")],
)
def test_the_combined_cooperativa_key_of_the_earlier_designs_reads_both_marks(
    cooperativa: str,
    multiples: str,
    key: str,
    page_01_fields: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    combined_years = [year for year in _YEARS if _K.M202_COOPERATIVA_O_MULTIPLES_TIPOS in _cited(page_01_fields[year])]
    values = {
        **_STATED,
        "taxpayer_type.cooperativa_fiscalmente_protegida": cooperativa,
        "taxpayer_type.multiples_tipos_impositivos": multiples,
    }
    for year in combined_years:
        records = page_01_fields[year]
        rendered = _rendered(records, _resolve(records, year, values))
        assert rendered[_K.M202_COOPERATIVA_O_MULTIPLES_TIPOS][1] == key
