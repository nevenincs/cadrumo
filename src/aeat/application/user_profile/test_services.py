"""Tests for user-profile validation and preflight services."""

from __future__ import annotations

from ...core.errors import BaseSeverity
import pytest

from ...core.resources import resources
from ...domain.user_profile import (
    UserProfileFact,
    UserProfileRecord,
)
from . import (
    ProfilePreflightService,
    ProfileValidationService,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(scope="module")
def schema():
    return resources().user_profile_schema.singleton


def test_validation_rejects_unknown_field_path(schema) -> None:
    svc = ProfileValidationService(schema=schema)
    report = svc.validate_facts("operator", [UserProfileFact(path="identity.does_not_exist", value="x")])
    codes = {issue.code for issue in report.issues}
    assert "unknown_field" in codes


def test_validation_reports_missing_required_fields(schema) -> None:
    svc = ProfileValidationService(schema=schema)
    report = svc.validate_facts("operator", [])
    required_misses = [
        issue
        for issue in report.issues
        if issue.code == "required_field_missing" and issue.severity is BaseSeverity.ERROR
    ]
    assert len(required_misses) >= 1


def test_validation_accepts_known_field(schema) -> None:
    svc = ProfileValidationService(schema=schema)
    report = svc.validate_facts("operator", [UserProfileFact(path="identity.tax_id", value="12345678Z")])
    assert not any(issue.code == "unknown_field" for issue in report.issues)


def test_preflight_returns_ready_when_no_modelo_selectors_match(schema) -> None:
    svc = ProfilePreflightService(schema=schema)
    record = UserProfileRecord(
        profile_id="operator",
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    report = svc.report(
        record=record,
        modelo="100",
        revision_id="2024-y-siguientes",
        filing_year=2024,
        period="0A",
    )
    assert report.ready is True
    assert report.missing == ()


def test_preflight_carries_request_fields_through(schema) -> None:
    svc = ProfileValidationService(schema=schema)  # warm domain
    pre = ProfilePreflightService(schema=schema)
    record = UserProfileRecord(profile_id="operator", display_name="Operator", facts=())
    report = pre.report(
        record=record,
        modelo="303",
        revision_id="rev-2024",
        filing_year=2024,
        period="1T",
    )
    assert report.profile_id == "operator"
    assert report.modelo == "303"
    assert report.revision_id == "rev-2024"
    assert report.filing_year == 2024
    assert report.period == "1T"
    del svc