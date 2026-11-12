"""Verify the Modelo 100 compensation of pending negative general bases against LIRPF art. 50.3.

Art. 50.3 lets a negative base liquidable general be compensated only against
the positive base liquidable general of the four following years, and "La
compensación deberá efectuarse en la cuantía máxima que permita cada uno de los
ejercicios siguientes". Anexo C keeps one row per origin year: the fourth year
back (stock 1380, applied 1381), the third (1382, 1383), the second (1385,
1386) and the previous year (1388, 1389). Each origin year expires after four
years, so the positive base is consumed oldest row first, and each applied
amount is fixed: the lesser of its stock and the positive base the older rows
leave. Casilla 0501 is the sum of the applied amounts.

Each case runs the real calculation and the real verification over encrypted
profile storage for every supported Modelo 100 revision, and reads only the
findings of the Art. 50.3 gates. The expected maxima are derived here from the
statutory rule and the calculated base, not read back from the registry
formulas. An unknown stock stops the calculation, so it never reaches a gate.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    supported_authored_exercises,
    supported_exercises_with_projection,
)
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.operation_shared import resolve_active_workflow_profile
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....application.modelo.work_addressing import law_selected_revision_for_work_target
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_missing_input import ModeloWorkMissingInputError
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.identity.hex_ids import WorkUnitId
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.ids import BindingId, RelationId
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...adapter_composition_work_ports import build_work_lifecycle_ports
from .file_flow_test_support import calculation_ports_for_test
from .general_iva_profile_facts_support import renta_single_taxpayer_facts
from .observation_seeding_support import save_stamped_observation
from .work_income_support import record_work_income

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODELO = "100"
_PERIOD = "0A"
#: Every supported Renta exercise, the projected one past the newest authored edition included: each calculates.
_SUPPORTED_FILING_YEARS = supported_exercises_with_projection(_MODELO)
#: The exercises an authored edition governs. Only their verification runs the Art. 50.3 gates: a projected year's
#: verification refuses the filing claim before any of them, which its own verification test covers.
_VERIFIED_FILING_YEARS = supported_authored_exercises(_MODELO)
#: The verified exercises whose prior return is itself a supported one.
_YEARS_WITH_SUPPORTED_PRIOR = _VERIFIED_FILING_YEARS[1:]
_PROFILE_ID = "10010000-0000-4100-8100-000000000503"
_CLOCK = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)

_NOT_AT_MAXIMUM_KEY = "application.modelo.findings.application_not_required_maximum"

_COMPENSATION: CasillaId = validated_casilla_id("0501")
_BASE_IMPONIBLE_GENERAL: CasillaId = validated_casilla_id("0435")
_BASE_LIQUIDABLE_GENERAL: CasillaId = validated_casilla_id("0500")
#: Retribuciones dinerarias, importe íntegro: this unit's only income.
_DEFAULT_WORK_INCOME = Decimal("40000.00")
_TAXPAYER_TAX_ID = "12345678Z"


@dataclass(frozen=True)
class _OriginRow:
    """One Anexo C origin row: its stock, its applied amount and what carries it."""

    name: str
    stock: CasillaId
    applied: CasillaId
    remainder: CasillaId | None
    stock_binding: BindingId
    prior_source: CasillaId


#: Oldest first, the order art. 50.3 consumes them in.
_ROWS: tuple[_OriginRow, ...] = (
    _OriginRow(
        "em4",
        validated_casilla_id("1380"),
        validated_casilla_id("1381"),
        None,
        "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
        validated_casilla_id("1384"),
    ),
    _OriginRow(
        "em3",
        validated_casilla_id("1382"),
        validated_casilla_id("1383"),
        validated_casilla_id("1384"),
        "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
        validated_casilla_id("1387"),
    ),
    _OriginRow(
        "em2",
        validated_casilla_id("1385"),
        validated_casilla_id("1386"),
        validated_casilla_id("1387"),
        "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
        validated_casilla_id("1390"),
    ),
    _OriginRow(
        "em1",
        validated_casilla_id("1388"),
        validated_casilla_id("1389"),
        validated_casilla_id("1390"),
        "renta-base-liquidable-negativa-general-anterior",
        validated_casilla_id("1391"),
    ),
)
_ROW_BY_NAME = {row.name: row for row in _ROWS}


def _stock_predicate_id(year: int, row: _OriginRow) -> str:
    return f"modelo-100-{year}-compensacion-base-neg-general-{row.name}-no-excede-stock"


def _maximum_predicate_id(year: int, row: _OriginRow) -> str:
    return f"modelo-100-{year}-compensacion-base-neg-general-{row.name}-cuantia-maxima"


def _seed_profile(filing_year: int, *, work_income: Decimal = _DEFAULT_WORK_INCOME) -> None:
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value=_TAXPAYER_TAX_ID),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="trabajo"),
                *renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)),
            ),
            without=("irpf.estimation_regime", "activities.", "censo.activity_start_date"),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)
    # The 0596 withholding and the work income come only from the payer register: one certificate,
    # which withheld nothing, states the work income (none at all for a zero).
    with bundled_indexed_authority().operation() as operation:
        record_work_income(
            operation=operation, taxpayer_tax_id=_TAXPAYER_TAX_ID, filing_year=filing_year, gross=work_income
        )


def _seed_prior_return(filing_year: int, carried: Mapping[CasillaId, Decimal]) -> None:
    """Record the prior return's Anexo C remainders, which open this year's rows."""
    save_stamped_observation(
        CalculationObservationRepository(),
        registry_grounded_modelo_observation(
            modelo=_MODELO,
            filing_year=filing_year - 1,
            period=_PERIOD,
            casilla_values=dict(carried),
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )


def _operator_zeros(filing_year: int) -> tuple[dict[BindingId, Decimal], dict[RelationId, Decimal]]:
    """Zero every operator-owned channel except the withholding register and the prior-year carries."""
    snapshot = published_authority_operation().reading_snapshot(_MODELO, filing_year=filing_year, period=_PERIOD)
    binding_values = {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.source != "profile"
        and binding.source not in BUCKET_AGGREGATION_LOCK_SOURCES
        and binding.provider.kind not in {"retencion_soportada", "previous_filing"}
    }
    relation_values = {
        binding.id: Decimal("0")
        for binding, _provider in relation_prefill_bindings_for_period(snapshot.revision, period=snapshot.period)
    }
    return binding_values, relation_values


def _stated_stocks(**stocks: str) -> dict[BindingId, Decimal]:
    """The pending stocks the operator states by hand, by origin row name."""
    return {_ROW_BY_NAME[name].stock_binding: Decimal(amount) for name, amount in stocks.items()}


def _create_work_unit(filing_year: int) -> WorkUnitId:
    period = Period.from_year_and_code(filing_year, _PERIOD)
    with bundled_indexed_authority().operation() as operation:
        work_unit = create_work_unit(
            bucket_id=_PROFILE_ID,
            modelo=_MODELO,
            filing_year=filing_year,
            period=period,
            revision_id=law_selected_revision_for_work_target(
                modelo=_MODELO, filing_year=filing_year, period=period, operation=operation
            ),
            ports=build_work_lifecycle_ports(bucket_id=_PROFILE_ID),
            operation=operation,
            clock=_CLOCK,
        )
    return work_unit.work_unit_id


def _calculate(
    filing_year: int,
    work_unit_id: WorkUnitId,
    *,
    applied: Mapping[str, Decimal],
    stated_stocks: Mapping[BindingId, Decimal],
) -> CalculationRevision:
    binding_values, relation_values = _operator_zeros(filing_year)
    binding_values.update(stated_stocks)
    casilla_inputs: dict[CasillaId, Decimal] = {}
    casilla_inputs.update({_ROW_BY_NAME[name].applied: amount for name, amount in applied.items()})
    with calculation_ports_for_test(
        bucket_id=_PROFILE_ID,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        bucket_event_repository=BucketEventHistoryRepository(),
    ) as ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_id,
            actor=_PROFILE_ID,
            casilla_inputs=casilla_inputs,
            binding_values=binding_values,
            relation_values=relation_values,
            ports=ports,
            clock=_CLOCK,
        ).revision


def _art_50_3_findings(filing_year: int, revision: CalculationRevision) -> dict[str, ModeloVerificationFinding]:
    """Verify the revision and return the Art. 50.3 gates' findings by predicate id."""
    gate_ids = {
        predicate_id
        for row in _ROWS
        for predicate_id in (_stock_predicate_id(filing_year, row), _maximum_predicate_id(filing_year, row))
    }
    with bundled_indexed_authority().operation() as operation:
        report = verify_modelo_revision_with_preconditions(
            str(revision.calculation_revision_id),
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            operator_scope_ports=build_operator_scope_ports(),
            actor="art-50-3-verification",
            workflow_profile=resolve_active_workflow_profile(operation),
            verification_repositories=build_test_verification_repository_bundle(),
            clock=_CLOCK,
            operation=operation,
        ).report
    findings: dict[str, ModeloVerificationFinding] = {}
    for finding in report.findings:
        predicate_id = finding.message_facts.get("predicate_id")
        if predicate_id in gate_ids:
            assert finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
            assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
            assert "ley-35-2006:art-50" in finding.legal_refs
            findings[str(predicate_id)] = finding
    if findings:
        assert report.granted_verificado_completo is False
    return findings


def _statutory_maxima(revision: CalculationRevision, stocks: Mapping[str, Decimal]) -> dict[str, Decimal]:
    """Art. 50.3, oldest row first: each row takes the lesser of its stock and the base still left."""
    values = revision.casilla_values
    # 0500 is the base liquidable general before the compensation 0501.
    left = max(Decimal("0"), values[_BASE_LIQUIDABLE_GENERAL])
    maxima: dict[str, Decimal] = {}
    for row in _ROWS:
        maxima[row.name] = min(stocks[row.name], left)
        left -= maxima[row.name]
    return maxima


def _assert_not_at_maximum(
    finding: ModeloVerificationFinding,
    *,
    filing_year: int,
    row: _OriginRow,
    applied: Decimal,
    maximum: Decimal,
) -> None:
    assert finding.casilla_id == row.applied
    assert finding.message_locale_key == _NOT_AT_MAXIMUM_KEY
    assert dict(finding.message_facts) == {
        "predicate_id": _maximum_predicate_id(filing_year, row),
        "box": row.applied,
        "casilla_value": applied,
        "computed_value": maximum,
    }


_EVERY_ROW_STOCKED = {
    "em4": Decimal("1000.00"),
    "em3": Decimal("2000.00"),
    "em2": Decimal("3000.00"),
    "em1": Decimal("4000.00"),
}
_EVERY_ROW_STATED = _stated_stocks(em4="1000.00", em3="2000.00", em2="3000.00", em1="4000.00")
_NO_STOCK_STATED = _stated_stocks(em4="0", em3="0", em2="0", em1="0")
_REMAINDER_EM3: CasillaId = validated_casilla_id("1384")
_REMAINDER_EM2: CasillaId = validated_casilla_id("1387")
_REMAINDER_EM1: CasillaId = validated_casilla_id("1390")


@pytest.mark.parametrize("filing_year", _VERIFIED_FILING_YEARS)
def test_every_origin_row_applied_at_its_maximum_passes_and_sums_into_0501(tmp_path: Path, filing_year: int) -> None:
    """A base larger than every stock absorbs them all; 0501 is their sum and nothing remains."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile(filing_year)
        revision = _calculate(
            filing_year,
            _create_work_unit(filing_year),
            applied=_EVERY_ROW_STOCKED,
            stated_stocks=_EVERY_ROW_STATED,
        )
        findings = _art_50_3_findings(filing_year, revision)

    assert _statutory_maxima(revision, _EVERY_ROW_STOCKED) == _EVERY_ROW_STOCKED
    values = revision.casilla_values
    assert values[_COMPENSATION] == Decimal("10000.00")
    for row in _ROWS:
        assert values[row.stock] == _EVERY_ROW_STOCKED[row.name]
    assert values[_REMAINDER_EM3] == values[_REMAINDER_EM2] == values[_REMAINDER_EM1] == Decimal("0")
    assert findings == {}


@pytest.mark.parametrize("filing_year", _VERIFIED_FILING_YEARS)
def test_a_small_base_is_consumed_oldest_row_first(tmp_path: Path, filing_year: int) -> None:
    """Stocks above the base: the older rows take it all, and the younger rows' maximum is zero."""
    stocks = {
        "em4": Decimal("5000.00"),
        "em3": Decimal("30000.00"),
        "em2": Decimal("7000.00"),
        "em1": Decimal("8000.00"),
    }
    stated = _stated_stocks(em4="5000.00", em3="30000.00", em2="7000.00", em1="8000.00")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile(filing_year, work_income=Decimal("20000.00"))
        work_unit_id = _create_work_unit(filing_year)
        probe = _calculate(filing_year, work_unit_id, applied={}, stated_stocks=stated)
        maxima = _statutory_maxima(probe, stocks)
        exact = _calculate(filing_year, work_unit_id, applied=maxima, stated_stocks=stated)
        exact_findings = _art_50_3_findings(filing_year, exact)
        # Applying the youngest row instead of the oldest is refused on both rows.
        youngest_first = {"em1": stocks["em4"], "em3": maxima["em3"]}
        swapped = _calculate(filing_year, work_unit_id, applied=youngest_first, stated_stocks=stated)
        swapped_findings = _art_50_3_findings(filing_year, swapped)

    assert maxima["em4"] == stocks["em4"]
    assert Decimal("0") < maxima["em3"] < stocks["em3"]
    assert maxima["em2"] == maxima["em1"] == Decimal("0")
    assert exact_findings == {}
    values = exact.casilla_values
    assert values[_COMPENSATION] == maxima["em4"] + maxima["em3"]
    assert values[_REMAINDER_EM3] == stocks["em3"] - maxima["em3"]
    assert values[_REMAINDER_EM2] == stocks["em2"]
    assert values[_REMAINDER_EM1] == stocks["em1"]

    em4, em1 = _ROW_BY_NAME["em4"], _ROW_BY_NAME["em1"]
    assert set(swapped_findings) == {_maximum_predicate_id(filing_year, em4), _maximum_predicate_id(filing_year, em1)}
    _assert_not_at_maximum(
        swapped_findings[_maximum_predicate_id(filing_year, em4)],
        filing_year=filing_year,
        row=em4,
        applied=Decimal("0"),
        maximum=maxima["em4"],
    )
    _assert_not_at_maximum(
        swapped_findings[_maximum_predicate_id(filing_year, em1)],
        filing_year=filing_year,
        row=em1,
        applied=stocks["em4"],
        maximum=Decimal("0"),
    )


@pytest.mark.parametrize("filing_year", _VERIFIED_FILING_YEARS)
@pytest.mark.parametrize(
    ("applied", "stock_refused"),
    (
        pytest.param(Decimal("1500.00"), False, id="under-application"),
        pytest.param(Decimal("2500.00"), True, id="over-application"),
    ),
)
def test_an_application_other_than_the_row_maximum_is_refused(
    tmp_path: Path,
    filing_year: int,
    applied: Decimal,
    stock_refused: bool,
) -> None:
    """With 2,000 pending in the third year back and a larger base, art. 50.3 requires exactly 2,000."""
    em3 = _ROW_BY_NAME["em3"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile(filing_year)
        revision = _calculate(
            filing_year,
            _create_work_unit(filing_year),
            applied={"em4": Decimal("1000.00"), "em3": applied, "em2": Decimal("3000.00"), "em1": Decimal("4000.00")},
            stated_stocks=_EVERY_ROW_STATED,
        )
        findings = _art_50_3_findings(filing_year, revision)

    expected = {_maximum_predicate_id(filing_year, em3)}
    if stock_refused:
        expected.add(_stock_predicate_id(filing_year, em3))
    assert set(findings) == expected
    _assert_not_at_maximum(
        findings[_maximum_predicate_id(filing_year, em3)],
        filing_year=filing_year,
        row=em3,
        applied=applied,
        maximum=Decimal("2000.00"),
    )


@pytest.mark.parametrize("filing_year", _VERIFIED_FILING_YEARS)
def test_a_positive_application_with_no_positive_base_is_refused(tmp_path: Path, filing_year: int) -> None:
    """Art. 50.3 compensates only against a positive base, so a zero base admits nothing on any row."""
    em4 = _ROW_BY_NAME["em4"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile(filing_year, work_income=Decimal("0"))
        work_unit_id = _create_work_unit(filing_year)
        refused = _calculate(
            filing_year,
            work_unit_id,
            applied={"em4": Decimal("500.00")},
            stated_stocks=_EVERY_ROW_STATED,
        )
        refused_findings = _art_50_3_findings(filing_year, refused)
        nothing = _calculate(filing_year, work_unit_id, applied={}, stated_stocks=_EVERY_ROW_STATED)
        nothing_findings = _art_50_3_findings(filing_year, nothing)

    assert refused.casilla_values[_BASE_IMPONIBLE_GENERAL] <= Decimal("0")
    assert _statutory_maxima(refused, _EVERY_ROW_STOCKED) == dict.fromkeys(_EVERY_ROW_STOCKED, Decimal("0"))
    assert set(refused_findings) == {_maximum_predicate_id(filing_year, em4)}
    _assert_not_at_maximum(
        refused_findings[_maximum_predicate_id(filing_year, em4)],
        filing_year=filing_year,
        row=em4,
        applied=Decimal("500.00"),
        maximum=Decimal("0"),
    )
    assert nothing_findings == {}
    assert nothing.casilla_values[_REMAINDER_EM1] == _EVERY_ROW_STOCKED["em1"]


@pytest.mark.parametrize("filing_year", _VERIFIED_FILING_YEARS)
def test_a_positive_application_against_a_proven_zero_stock_is_refused(tmp_path: Path, filing_year: int) -> None:
    """A stated zero stock leaves nothing to compensate, so 500 applied from it fails both of its gates."""
    em2 = _ROW_BY_NAME["em2"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile(filing_year)
        work_unit_id = _create_work_unit(filing_year)
        refused = _calculate(
            filing_year,
            work_unit_id,
            applied={"em2": Decimal("500.00")},
            stated_stocks=_NO_STOCK_STATED,
        )
        refused_findings = _art_50_3_findings(filing_year, refused)
        nothing = _calculate(filing_year, work_unit_id, applied={}, stated_stocks=_NO_STOCK_STATED)
        nothing_findings = _art_50_3_findings(filing_year, nothing)

    assert refused.casilla_values[_COMPENSATION] == Decimal("500.00")
    assert set(refused_findings) == {_stock_predicate_id(filing_year, em2), _maximum_predicate_id(filing_year, em2)}
    _assert_not_at_maximum(
        refused_findings[_maximum_predicate_id(filing_year, em2)],
        filing_year=filing_year,
        row=em2,
        applied=Decimal("500.00"),
        maximum=Decimal("0"),
    )
    assert nothing_findings == {}


@pytest.mark.parametrize("filing_year", _SUPPORTED_FILING_YEARS)
@pytest.mark.parametrize("unknown", [row.name for row in _ROWS])
def test_an_unknown_stock_of_any_row_stops_the_calculation(tmp_path: Path, filing_year: int, unknown: str) -> None:
    """With no prior return and that row's stock not stated, the stock is unknown and is never read as zero."""
    unknown_binding = _ROW_BY_NAME[unknown].stock_binding
    stated = {binding: amount for binding, amount in _NO_STOCK_STATED.items() if binding != unknown_binding}
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile(filing_year)
        work_unit_id = _create_work_unit(filing_year)
        with pytest.raises(ModeloWorkMissingInputError) as refused:
            _calculate(filing_year, work_unit_id, applied={}, stated_stocks=stated)

    assert refused.value.binding_id == unknown_binding


@pytest.mark.parametrize("filing_year", _YEARS_WITH_SUPPORTED_PRIOR)
def test_the_prior_return_opens_each_row_one_year_older(tmp_path: Path, filing_year: int) -> None:
    """The prior 1384, 1387, 1390 and 1391 open this year's 1380, 1382, 1385 and 1388."""
    amounts = (Decimal("100.00"), Decimal("200.00"), Decimal("300.00"), Decimal("400.00"))
    carried = {row.prior_source: amount for row, amount in zip(_ROWS, amounts, strict=True)}
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile(filing_year)
        _seed_prior_return(filing_year, carried)
        revision = _calculate(
            filing_year,
            _create_work_unit(filing_year),
            applied={row.name: amount for row, amount in zip(_ROWS, amounts, strict=True)},
            stated_stocks={},
        )
        findings = _art_50_3_findings(filing_year, revision)

    for row in _ROWS:
        assert revision.casilla_values[row.stock] == carried[row.prior_source]
    assert revision.casilla_values[_COMPENSATION] == Decimal("1000.00")
    assert findings == {}
