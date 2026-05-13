"""Tests for the typed declaration-calculate summary surface."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...core.i18n import Translatable as tr  # noqa: N813
from ...domain.filing import (
    FilingDraft,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingValidationFinding,
)
from . import (
    DeclarationCalculateNextAction,
    summarise_calculation,
)
from .testing import build_registry_filing_draft

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _hint() -> str:
    return "filing.test_calculate.hint"


def _finding_message(code: str) -> tr:
    return tr(f"filing.test_calculate.finding_{code}")


def _make_draft(
    *,
    status: FilingDraftStatus,
    findings: tuple[FilingValidationFinding, ...] = (),
    modelo: str = "130",
    period: str = "2026Q1",
) -> FilingDraft:
    draft = build_registry_filing_draft(
        modelo=modelo,
        period=period,
        profile_tax_id="12345678Z",
        casilla_values={
            "01": Decimal("12500.00"),
            "02": Decimal("3500.00"),
            "05": Decimal("250"),
            "06": Decimal("100"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "15": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        status=status,
    )
    return draft.model_copy(
        update={
            "status": status,
            "findings": findings,
            "updated_at": datetime(2026, 5, 3, tzinfo=UTC),
        }
    )


def _finding(severity: FilingFindingSeverity, code: str) -> FilingValidationFinding:
    return FilingValidationFinding(
        casilla_id=None,
        severity=severity,
        code=code,
        message=_finding_message(code),
    )


def test_clean_validated_draft_routes_to_review() -> None:
    draft = _make_draft(status=FilingDraftStatus.VALIDATED)
    summary = summarise_calculation(draft)
    assert summary.next_action is DeclarationCalculateNextAction.REVIEW
    assert summary.blocker_count == 0
    assert summary.warning_count == 0
    assert summary.info_count == 0


def test_ready_to_submit_clean_draft_routes_to_approve() -> None:
    draft = _make_draft(status=FilingDraftStatus.READY_TO_SUBMIT)
    summary = summarise_calculation(draft)
    assert summary.next_action is DeclarationCalculateNextAction.APPROVE


def test_approved_draft_routes_to_export() -> None:
    draft = _make_draft(status=FilingDraftStatus.APPROVED)
    summary = summarise_calculation(draft)
    assert summary.next_action is DeclarationCalculateNextAction.EXPORT


def test_approval_stale_routes_to_refresh_approval() -> None:
    draft = _make_draft(status=FilingDraftStatus.APPROVAL_STALE)
    summary = summarise_calculation(draft)
    assert summary.next_action is DeclarationCalculateNextAction.REFRESH_APPROVAL


def test_submitted_status_routes_to_amend() -> None:
    draft = _make_draft(status=FilingDraftStatus.SUBMITTED)
    summary = summarise_calculation(draft)
    assert summary.next_action is DeclarationCalculateNextAction.AMEND


def test_any_status_with_error_routes_to_resolve_blockers() -> None:
    draft = _make_draft(
        status=FilingDraftStatus.APPROVED,
        findings=(_finding(FilingFindingSeverity.ERROR, "casilla-required-missing"),),
    )
    summary = summarise_calculation(draft, repair_hints=(_hint(),))
    assert summary.next_action is DeclarationCalculateNextAction.RESOLVE_BLOCKERS
    assert summary.blocker_count == 1
    assert summary.repair_hints == (_hint(),)


def test_summary_counts_findings_by_severity() -> None:
    draft = _make_draft(
        status=FilingDraftStatus.VALIDATED,
        findings=(
            _finding(FilingFindingSeverity.INFO, "i-1"),
            _finding(FilingFindingSeverity.WARNING, "w-1"),
            _finding(FilingFindingSeverity.WARNING, "w-2"),
        ),
    )
    summary = summarise_calculation(draft)
    assert summary.info_count == 1
    assert summary.warning_count == 2
    assert summary.blocker_count == 0
    assert summary.next_action is DeclarationCalculateNextAction.REVIEW


def test_repair_hints_required_for_resolve_blockers() -> None:
    draft = _make_draft(
        status=FilingDraftStatus.VALIDATED,
        findings=(_finding(FilingFindingSeverity.ERROR, "blocker"),),
    )
    with pytest.raises(ValueError, match=r"repair_hints"):
        summarise_calculation(draft, repair_hints=())


def test_repair_hints_rejected_outside_resolve_blockers() -> None:
    draft = _make_draft(status=FilingDraftStatus.VALIDATED)
    with pytest.raises(ValueError, match=r"repair_hints"):
        summarise_calculation(draft, repair_hints=(_hint(),))


def test_summary_is_frozen() -> None:
    draft = _make_draft(status=FilingDraftStatus.VALIDATED)
    summary = summarise_calculation(draft)
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        summary.blocker_count = 99  # type: ignore[misc]


def test_calculated_at_defaults_to_draft_updated_at() -> None:
    draft = _make_draft(status=FilingDraftStatus.VALIDATED)
    summary = summarise_calculation(draft)
    assert summary.calculated_at == draft.updated_at
