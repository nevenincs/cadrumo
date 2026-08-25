"""Hard-cutover tests for retired persisted export-account paths.

Filing accounts are transient typed inputs to the filing producer snapshot.
They are deliberately not user-profile facts: accepting a persisted
``filing_export.*`` vocabulary would recreate a second account authority.
"""

from __future__ import annotations

import pytest

from cadrumo.application.user_profile.validation import ProfileValidationService

from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RETIRED_FILING_EXPORT_FACTS = (
    UserProfileFact(path="filing_export.iban", value="ES9121000418450200051332"),
    UserProfileFact(path="filing_export.charge_iban", value="ES7921000813610123456789"),
    UserProfileFact(path="filing_export.swift_bic", value="CHASUS33XXX"),
    UserProfileFact(path="filing_export.bank_name", value="Refund Only Bank"),
    UserProfileFact(path="filing_export.bank_address", value="Refund Street 1"),
    UserProfileFact(path="filing_export.bank_city", value="New York"),
    UserProfileFact(path="filing_export.bank_country_code", value="US"),
)


def test_retired_filing_export_account_paths_are_absent_and_refused() -> None:
    """The real profile schema and validation boundary reject every old path."""
    schema = load_user_profile_schema()
    retired_paths = {fact.path for fact in _RETIRED_FILING_EXPORT_FACTS}

    assert retired_paths.isdisjoint(schema.field_paths)

    report = ProfileValidationService(schema=schema).validate_facts(
        "11111111-1111-4111-8111-111111111111",
        _RETIRED_FILING_EXPORT_FACTS,
    )
    unknown_paths = {issue.path for issue in report.issues if issue.code == "unknown_field"}

    assert unknown_paths == retired_paths
