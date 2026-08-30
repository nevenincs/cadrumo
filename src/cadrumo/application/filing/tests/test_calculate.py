"""Tests for the typed declaration-calculate summary surface."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.operator_action_enums import ActionConditionality, NoRecoveryOutcome
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.severity import BaseSeverity
from ....core.i18n import Translatable as tr
from ....domain.filing.schema import ModeloDraft, ModeloValidationFinding
from ....domain.submission import ModeloDraftStatus
from ....tests.filing import build_registry_filing_draft
from .. import summarise_calculation
from ..errors import FilingPreconditionCondition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Q1_2026 = Period.from_year_and_code(2026, "1T")
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_PAGOS_PREVIOS_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_PAGOS_PREVIOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")


def _finding_message(code: str) -> tr:
    return tr(f"filing.test_calculate.finding_{code}")


def _make_draft(
    *,
    status: ModeloDraftStatus,
    findings: tuple[ModeloValidationFinding, ...] = (),
    modelo: str = "130",
    period: Period = _Q1_2026,
) -> ModeloDraft:
    draft = build_registry_filing_draft(
        modelo=modelo,
        period=period,
        profile_tax_id="12345678Z",
        casilla_values={
            _M130_INGRESOS_CASILLA: Decimal("12500.00"),
            _M130_GASTOS_CASILLA: Decimal("3500.00"),
            _M130_PAGOS_PREVIOS_CASILLA: Decimal("250"),
            _M130_RETENCIONES_CASILLA: Decimal("100"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
        },
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        status=status,
    )
    return draft.model_copy(
        update={
            "status": status,
            "findings": findings,
            "updated_at": datetime(2026, 5, 3, tzinfo=UTC),
        },
    )


def _finding(severity: BaseSeverity, code: str) -> ModeloValidationFinding:
    return ModeloValidationFinding(
        casilla_id=None,
        severity=severity,
        code=code,
        message=_finding_message(code),
    )


def test_clean_validated_draft_carries_no_fabricated_continuation() -> None:
    draft = _make_draft(status=ModeloDraftStatus.VALIDADO)
    summary = summarise_calculation(draft)
    assert summary.blocker_count == 0
    assert summary.warning_count == 0
    assert summary.info_count == 0
    assert summary.precondition_verdict is None


def test_summary_carries_typed_period_not_combined_string() -> None:
    period = Period.from_year_and_code(2026, "1T")
    draft = _make_draft(status=ModeloDraftStatus.VALIDADO).model_copy(update={"period": period})
    summary = summarise_calculation(draft)
    assert summary.period == period
    assert summary.model_dump()["period"] == {"filing_year": 2026, "code": "1T"}
    assert summary.model_dump(mode="json")["period"] == {"filing_year": 2026, "code": "1T"}


@pytest.mark.parametrize(
    "status",
    (
        ModeloDraftStatus.LISTO_PARA_PRESENTAR,
        ModeloDraftStatus.APROBADO,
        ModeloDraftStatus.APROBACION_CADUCADA,
        ModeloDraftStatus.PRESENTADA,
    ),
    ids=("ready-to-submit", "approved", "approval-stale", "submitted"),
)
def test_clean_draft_lifecycle_status_does_not_invent_an_action(status: ModeloDraftStatus) -> None:
    draft = _make_draft(status=status)
    summary = summarise_calculation(draft)
    assert summary.status is status
    assert summary.precondition_verdict is None


def test_any_status_with_error_carries_a_typed_terminal_blocker_condition() -> None:
    draft = _make_draft(
        status=ModeloDraftStatus.APROBADO,
        findings=(_finding(BaseSeverity.ERROR, "casilla-required-missing"),),
    )
    summary = summarise_calculation(draft)
    assert summary.blocker_count == 1
    verdict = summary.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == FilingPreconditionCondition.CALCULATION_FINDINGS_CLEAR.value
    assert verdict.action is None
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values == {
        "draft_id": draft.draft_id,
        "modelo": draft.modelo,
        "period": draft.period.registry_token,
        "filing_year": draft.period.filing_year,
        "blocker_count": 1,
    }


def test_summary_counts_findings_by_severity() -> None:
    draft = _make_draft(
        status=ModeloDraftStatus.VALIDADO,
        findings=(
            _finding(BaseSeverity.INFO, "i-1"),
            _finding(BaseSeverity.WARNING, "w-1"),
            _finding(BaseSeverity.WARNING, "w-2"),
        ),
    )
    summary = summarise_calculation(draft)
    assert summary.info_count == 1
    assert summary.warning_count == 2
    assert summary.blocker_count == 0
    assert summary.precondition_verdict is None


def test_summary_is_frozen() -> None:
    draft = _make_draft(status=ModeloDraftStatus.VALIDADO)
    summary = summarise_calculation(draft)
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        summary.blocker_count = 99


def test_calculated_at_defaults_to_draft_updated_at() -> None:
    draft = _make_draft(status=ModeloDraftStatus.VALIDADO)
    summary = summarise_calculation(draft)
    assert summary.calculated_at == draft.updated_at
    assert summary.calculated_at.tzinfo is UTC


@pytest.mark.parametrize(
    "calculated_at",
    (
        datetime(2026, 5, 3),
        datetime(2026, 5, 3, 1, tzinfo=timezone(timedelta(hours=1))),
    ),
    ids=("naive", "non-utc"),
)
def test_summary_refuses_non_utc_calculated_at(calculated_at: datetime) -> None:
    """Calculation summaries cannot carry an ambiguous rendering timestamp."""

    draft = _make_draft(status=ModeloDraftStatus.VALIDADO)
    with pytest.raises(ValidationError, match="datetime must be"):
        summarise_calculation(draft, calculated_at=calculated_at)
