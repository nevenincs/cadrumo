"""A Modelo 202 page 01 consigns its liquidation modality and foral normativa as the designs define them.

Every supported year is enumerated from the registry envelope and its own
edition's page 01 layout is read from the published authority. The two slots
are resolved by the export's producer view, carried through the real snapshot
builder and producer resolver, and rendered by the real fixed-width field
renderer. The expected bytes are written from the designs: Nota 11 of the 2025
design (Nota 4 of 2023) gives "A" for the LIS art. 40.2 modality and "B" for
the art. 40.3 one; Nota 9 of 2025 (Nota 2 of 2019 and 2023) gives the blank
"Sin contenido" to a contribuyente under the common normativa. The art. 40.3
threshold is read from the governed fact for each year, never restated.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.external_constants import OutputLanguage
from ....core.filing_producer_key import FilingProducerKey
from ....core.modelo import Modelo
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.applicability_modelo202 import (
    modelo_202_incn_threshold_decimal,
    resolve_modelo_202_art_40_3_incn_threshold,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.cnae_classification import required_cnae_classification
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
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
from ..export_periodo_impositivo import PeriodoImpositivo, periodo_impositivo_from_facts
from .incn_periodo_anterior_support import nothing_held

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_K = FilingProducerKey
_YEARS = filing_year_envelope().years
_PERIOD = "1P"
_MODALIDAD = _K.M202_MODALIDAD_LIQUIDACION
_FORAL = _K.M202_NORMATIVA_TERRITORIO_FORAL
_SLOTS = frozenset({_MODALIDAD, _FORAL})
_ENTITY_TYPE_PATH = "taxpayer_type.entity_type"
_INCN_PATH = "taxpayer_type.incn_prior_12_months"
_ELECTION_PATH = "taxpayer_type.pago_fraccionado_art_40_3_elected"
_NAVIERAS_PATH = "taxpayer_type.regimen_entidades_navieras_tonelaje"
_SCOPE_PATH = "tax_residence.jurisdiction_scope"
_COMMON = "common_regime"
_FORAL_SCOPE = "foral_unsupported"

_PAGE_01_BY_YEAR: dict[int, tuple[ExportRecordDefinition, ...]] = {}


@pytest.fixture
def page_01(operation: PinnedAuthorityOperation) -> Mapping[int, tuple[ExportRecordDefinition, ...]]:
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


def _filing_date(year: int) -> date:
    return calculation_filing_date(Period.from_year_and_code(year, _PERIOD))


def _threshold(operation: PinnedAuthorityOperation, year: int) -> Decimal:
    """The governed art. 40.3 turnover threshold of the instalment's ejercicio."""
    return modelo_202_incn_threshold_decimal(
        resolve_modelo_202_art_40_3_incn_threshold(effective_date=date(year, 12, 31), authority=operation)
    )


def _periodo(year: int) -> PeriodoImpositivo:
    on = instalment_period_in_progress_date(Period.from_year_and_code(year, _PERIOD))
    assert on is not None
    return periodo_impositivo_from_facts(
        modelo="202",
        on=on,
        profile_values={
            "taxpayer_type.cierre_ejercicio_dia": "31",
            "taxpayer_type.cierre_ejercicio_mes": "12",
            "taxpayer_type.fecha_constitucion": date(year - 5, 1, 1).isoformat(),
        },
    )


def _stated(turnover: Decimal | None, **overrides: str) -> dict[str, str]:
    """A sociedad under the common normativa stating the turnover that decides its modality."""
    values = {_ENTITY_TYPE_PATH: "legal_entity", _SCOPE_PATH: _COMMON, _NAVIERAS_PATH: "false"}
    if turnover is not None:
        values[_INCN_PATH] = str(turnover)
    return {**values, **overrides}


def _cited(records: tuple[ExportRecordDefinition, ...]) -> frozenset[FilingProducerKey]:
    cited = frozenset(
        field.producer_key for record in records for field in record.fields if field.producer_key is not None
    )
    # Every edition's page 01 carries both slots; only they are resolved here, so no rate is read.
    assert cited >= _SLOTS
    return _SLOTS


def _resolve(
    records: tuple[ExportRecordDefinition, ...],
    year: int,
    values: Mapping[str, str],
    *,
    operation: PinnedAuthorityOperation,
    elected: bool | None,
) -> dict[FilingProducerKey, object]:
    turnover = values.get(_INCN_PATH)
    model_profile = modelo_202_producer_profile(
        workflow_profile=TaxpayerProfile(
            tax_id=TAXPAYER_TAX_ID,
            iva_regime=IVARegime("GENERAL"),
            incn_prior_12_months=None if turnover is None else Decimal(turnover),
        ),
        profile_values={
            "taxpayer_type.principal_cnae_classification": required_cnae_classification(
                effective_date=_filing_date(year), authority=operation
            ),
            **values,
        },
        cited_producer_keys=_cited(records),
        effective_date=_filing_date(year),
        periodo=_periodo(year),
        filing_year=year,
        art_40_3_elected=elected,
        operation=operation,
        incn_periodo_anterior=nothing_held(operation, _periodo(year).start.year),
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


def _render(
    records: tuple[ExportRecordDefinition, ...],
    year: int,
    values: Mapping[str, str],
    *,
    operation: PinnedAuthorityOperation,
    elected: bool | None,
) -> dict[FilingProducerKey, str]:
    headers = _resolve(records, year, values, operation=operation, elected=elected)
    rendered: dict[FilingProducerKey, str] = {}
    for record in records:
        for field in record.fields:
            if field.producer_key in _SLOTS:
                rendered[field.producer_key] = format_field(field, header_field_value(field, headers), record=record)
    return rendered


def _slot(records: tuple[ExportRecordDefinition, ...], key: FilingProducerKey) -> ExportFieldDefinition:
    (field,) = (field for record in records for field in record.fields if field.producer_key is key)
    return field


def _refusal(
    records: tuple[ExportRecordDefinition, ...],
    year: int,
    values: Mapping[str, str],
    *,
    operation: PinnedAuthorityOperation,
    elected: bool | None,
) -> tuple[FilingProducerSnapshotError, Exception]:
    with pytest.raises(FilingProducerSnapshotError) as refused:
        _resolve(records, year, values, operation=operation, elected=elected)
    command = ModeloExportCommand(calculation_revision_id="a" * 64, output_path=Path("unused.txt"), actor="operator")
    return refused.value, _producer_facts_refusal(command, refused.value)


def _assert_door(failure: Exception, path: str) -> None:
    assert isinstance(failure, ModeloProfileReadinessError)
    step = error_next_step(failure, OutputLanguage.EN)
    assert isinstance(step, OperationOpenProfileFieldStepV1)
    assert step.path == path


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize(
    ("above_threshold", "elected", "modalidad"),
    [
        # Above the threshold art. 40.3 is mandatory whatever the declaración censal says.
        (True, None, "B"),
        (True, False, "B"),
        # Below it the election decides: elected is art. 40.3, not elected art. 40.2.
        (False, True, "B"),
        (False, False, "A"),
    ],
)
def test_the_modality_slot_consigns_the_modality_in_force(
    year: int,
    above_threshold: bool,
    elected: bool | None,
    modalidad: str,
    operation: PinnedAuthorityOperation,
    page_01: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    threshold = _threshold(operation, year)
    turnover = threshold + Decimal("0.01") if above_threshold else threshold

    rendered = _render(page_01[year], year, _stated(turnover), operation=operation, elected=elected)

    assert _slot(page_01[year], _MODALIDAD).length == 1
    assert rendered[_MODALIDAD] == modalidad


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("elected", [None, False, True])
def test_the_navieras_tonelaje_regime_makes_art_40_3_mandatory_below_the_threshold(
    year: int,
    elected: bool | None,
    operation: PinnedAuthorityOperation,
    page_01: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    """The instructions oblige the regime's entities to art. 40.3 whatever the election says."""
    values = _stated(_threshold(operation, year), **{_NAVIERAS_PATH: "true"})

    rendered = _render(page_01[year], year, values, operation=operation, elected=elected)

    assert rendered[_MODALIDAD] == "B"


@pytest.mark.parametrize("year", _YEARS)
def test_a_naviera_without_a_stated_turnover_refuses_with_the_turnover_door(
    year: int,
    operation: PinnedAuthorityOperation,
    page_01: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    values = _stated(None, **{_NAVIERAS_PATH: "true"})

    error, failure = _refusal(page_01[year], year, values, operation=operation, elected=None)

    assert error.context is not None
    assert str(error.context["missing_profile_paths"]).split(", ") == [_INCN_PATH]
    _assert_door(failure, _INCN_PATH)


@pytest.mark.parametrize("year", _YEARS)
def test_an_unstated_navieras_regime_below_the_threshold_leaves_the_modality_unknown_with_its_door(
    year: int,
    operation: PinnedAuthorityOperation,
    page_01: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    values = _stated(_threshold(operation, year))
    del values[_NAVIERAS_PATH]

    error, failure = _refusal(page_01[year], year, values, operation=operation, elected=True)

    assert error.context is not None
    assert str(error.context["missing_profile_paths"]).split(", ") == [_NAVIERAS_PATH]
    _assert_door(failure, _NAVIERAS_PATH)


@pytest.mark.parametrize("year", _YEARS)
def test_an_unstated_navieras_regime_above_the_threshold_does_not_matter(
    year: int,
    operation: PinnedAuthorityOperation,
    page_01: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    values = _stated(_threshold(operation, year) + Decimal("0.01"))
    del values[_NAVIERAS_PATH]

    rendered = _render(page_01[year], year, values, operation=operation, elected=None)

    assert rendered[_MODALIDAD] == "B"


@pytest.mark.parametrize("year", _YEARS)
def test_an_unstated_election_below_the_threshold_refuses_with_the_door_to_state_it_never_a_blank(
    year: int,
    operation: PinnedAuthorityOperation,
    page_01: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    error, failure = _refusal(
        page_01[year], year, _stated(_threshold(operation, year)), operation=operation, elected=None
    )

    assert error.context is not None
    assert str(error.context["missing_profile_paths"]).split(", ") == [_ELECTION_PATH]
    _assert_door(failure, _ELECTION_PATH)


@pytest.mark.parametrize("year", _YEARS)
def test_an_unstated_turnover_leaves_the_modality_unknown_and_refuses_naming_it(
    year: int,
    operation: PinnedAuthorityOperation,
    page_01: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    error, failure = _refusal(page_01[year], year, _stated(None), operation=operation, elected=False)

    assert error.context is not None
    assert str(error.context["missing_profile_paths"]).split(", ") == [_INCN_PATH]
    _assert_door(failure, _INCN_PATH)


@pytest.mark.parametrize("year", _YEARS)
def test_a_contribuyente_under_the_common_normativa_writes_the_designs_blank(
    year: int,
    operation: PinnedAuthorityOperation,
    page_01: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    rendered = _render(page_01[year], year, _stated(_threshold(operation, year)), operation=operation, elected=False)

    assert rendered[_FORAL] == " "


@pytest.mark.parametrize("year", _YEARS)
def test_an_unstated_territory_refuses_with_the_door_to_state_it_never_assumed_common(
    year: int,
    operation: PinnedAuthorityOperation,
    page_01: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    values = _stated(_threshold(operation, year), **{_SCOPE_PATH: ""})

    error, failure = _refusal(page_01[year], year, values, operation=operation, elected=False)

    assert error.context is not None
    assert str(error.context["missing_profile_paths"]).split(", ") == [_SCOPE_PATH]
    _assert_door(failure, _SCOPE_PATH)


@pytest.mark.parametrize("year", _YEARS)
def test_a_foral_territory_that_names_no_territory_refuses_rather_than_declare_the_common_normativa(
    year: int,
    operation: PinnedAuthorityOperation,
    page_01: Mapping[int, tuple[ExportRecordDefinition, ...]],
) -> None:
    values = _stated(_threshold(operation, year), **{_SCOPE_PATH: _FORAL_SCOPE})

    with pytest.raises(FilingProducerSnapshotError) as refused:
        _resolve(page_01[year], year, values, operation=operation, elected=False)

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "m202_foral_territory_unstated"
    assert refused.value.context["profile_path"] == _SCOPE_PATH
    verdict = nested_terminal_precondition_verdict(refused.value)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
