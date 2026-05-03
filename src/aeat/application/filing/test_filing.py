"""Application filing API tests at the registry hard-cut boundary."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ...domain.transactions import TransactionCatalogue
from . import (
    FilingBuilderError,
    FilingDraft,
    FilingDraftError,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingValidationFinding,
    FilingValidator,
    FilingValue,
    FilingValueKind,
    approve_draft,
    build_draft,
    compute_draft_id,
    iter_findings,
    refresh_review_status,
    validate_draft,
)
from .testing import (
    SyntheticDeadlineChecker,
    SyntheticDeadlineStatus,
    SyntheticProfile,
    default_schema_provider,
    synthesize_filing_draft,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> SyntheticProfile:
    return SyntheticProfile(
        tax_id="12345678Z",
        display_name="Registry boundary test",
        applicable_modelos=("130",),
    )


def _draft() -> FilingDraft:
    return synthesize_filing_draft(
        modelo="130",
        period="2026Q1",
        casilla_values={"01": Decimal("12500.00"), "02": Decimal("3500.00")},
        status=FilingDraftStatus.DRAFT,
        profile_tax_id="12345678Z",
    )


def test_build_draft_requires_validated_registry_snapshot() -> None:
    with pytest.raises(FilingBuilderError, match="validated registry snapshot"):
        build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs={"01": Decimal("12500.00")},
            schema_provider=default_schema_provider(),
        )


def test_validate_draft_preserves_id_without_builder_dispatch() -> None:
    draft = _draft()
    refreshed = validate_draft(draft, schema_provider=default_schema_provider())
    assert refreshed.draft_id == draft.draft_id


def test_compute_draft_id_excludes_findings_and_status() -> None:
    draft = _draft()
    recomputed = compute_draft_id(
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        schema_version=draft.schema_version,
        values=draft.values,
    )
    assert recomputed == draft.draft_id


def test_iter_findings_threshold() -> None:
    finding_error = FilingValidationFinding(
        casilla_id=None,
        severity=FilingFindingSeverity.ERROR,
        code="x",
        message={"en": "x"},
    )
    finding_info = FilingValidationFinding(
        casilla_id=None,
        severity=FilingFindingSeverity.INFO,
        code="y",
        message={"en": "y"},
    )
    draft = _draft().model_copy(update={"findings": (finding_error, finding_info)})
    warnings_or_errors = list(iter_findings(draft, severity_at_least="WARNING"))
    assert finding_error in warnings_or_errors
    assert finding_info not in warnings_or_errors
    assert finding_info in list(iter_findings(draft, severity_at_least="INFO"))
    with pytest.raises(FilingBuilderError):
        list(iter_findings(draft, severity_at_least="HUGE"))


def test_validator_still_checks_real_schema_records() -> None:
    draft = _draft().model_copy(
        update={
            "values": (
                FilingValue(
                    casilla_id="01",
                    value=Decimal("-1"),
                    kind=FilingValueKind.LITERAL,
                    source="test",
                    formula_trace=None,
                ),
                FilingValue(
                    casilla_id="02",
                    value=Decimal("3500.00"),
                    kind=FilingValueKind.LITERAL,
                    source="test",
                    formula_trace=None,
                ),
            )
        }
    )
    validator = FilingValidator(schema_provider=default_schema_provider())
    findings = validator.validate(draft)
    assert any(f.code == "casilla-out-of-range" and f.casilla_id == "01" for f in findings)


def test_approve_requires_registry_snapshot() -> None:
    with pytest.raises(FilingDraftError, match="validated registry snapshot"):
        approve_draft(
            _draft(),
            approved_by="kent",
            schema_provider=default_schema_provider(),
            transaction_catalogue=TransactionCatalogue(),
        )


def test_refresh_review_status_preserves_submitted_status_but_clears_stale_approval() -> None:
    draft = _draft().model_copy(
        update={
            "status": FilingDraftStatus.SUBMITTED,
            "approved_at": datetime(2026, 4, 18, 8, 0, tzinfo=UTC),
            "approved_by": "kent",
            "review_checksum": "a" * 64,
            "approval_basis": None,
        }
    )
    refreshed = refresh_review_status(
        draft,
        schema_provider=default_schema_provider(),
        transaction_catalogue=TransactionCatalogue(),
    )
    assert refreshed.status is FilingDraftStatus.SUBMITTED
    assert refreshed.approved_at is None
    assert refreshed.approved_by is None
    assert refreshed.review_checksum is None


def test_deadline_validator_still_reports_overdue_status() -> None:
    findings = FilingValidator(
        schema_provider=default_schema_provider(),
        deadline_checker=SyntheticDeadlineChecker(
            status=SyntheticDeadlineStatus(
                due_date=date(2026, 4, 20),
                is_overdue=True,
            )
        ),
    ).validate(_draft())
    assert any(f.code == "filing-deadline-missed" for f in findings)
