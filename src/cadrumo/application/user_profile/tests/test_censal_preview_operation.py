"""Censal preview projection rules."""

import pytest

from cadrumo.application.user_profile.censal_preview_operation import _unchanged_preview_facts
from cadrumo.application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS, CENSO_SOURCE_TAG, CensalReconciliation
from cadrumo.domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_fiscal_identity_is_not_reported_as_unchanged() -> None:
    """The ownership identity is not a field the reconciliation decides."""
    assert "identity.tax_id" not in CENSAL_ADOPTABLE_PATHS
    adoptable_path = next(iter(sorted(CENSAL_ADOPTABLE_PATHS)))
    projected = (
        UserProfileFact(path="identity.tax_id", value="12345678Z", source=CENSO_SOURCE_TAG),
        UserProfileFact(path=adoptable_path, value="corroborated", source=CENSO_SOURCE_TAG),
    )

    unchanged = _unchanged_preview_facts(projected, CensalReconciliation())

    assert {row.path for row in unchanged} == {adoptable_path}
