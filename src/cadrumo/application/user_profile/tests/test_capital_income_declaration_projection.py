"""The eight capital-income retención modelos read their payer fact in three states.

The projection under test is the production one: a real
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord` goes through
:func:`projection_for_taxpayer` and the registry's own applicability
classifier. LIRPF art. 25 defines the rendimientos del capital mobiliario and
art. 99 with RIRPF art. 90 and art. 108 fix the retención and its periodic
declaration, so a declared yes makes Modelos 117, 123, 126, 128, 187, 188, 193
and 194 applicable and a declared no rules them out. While the fact was a
plain ``bool`` defaulting to ``False`` the stored negative was
indistinguishable from an unanswered question, so a taxpayer who had answered
no got the same INCOMPLETE verdict as one who had never been asked.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.applicability import derive_modelo_applicability
from ....domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import latest_period_end
from ..projections import projection_for_taxpayer
from .payer_fact_record_support import CAPITAL_GATED_MODELOS, CAPITAL_PATH, capital_income_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _verdicts(operation: PinnedAuthorityOperation, *, answer: bool | None) -> dict[str, ApplicabilityVerdict]:
    record = capital_income_record(operation, answer=answer)
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())
    return {
        modelo: derive_modelo_applicability(
            profile, modelo, operation=operation, reference_date=latest_period_end()
        ).verdict
        for modelo in CAPITAL_GATED_MODELOS
    }


def test_an_unanswered_capital_income_fact_leaves_every_gated_modelo_incomplete(
    operation: PinnedAuthorityOperation,
) -> None:
    assert _verdicts(operation, answer=None) == dict.fromkeys(
        CAPITAL_GATED_MODELOS,
        ApplicabilityVerdict.INCOMPLETE,
    )


def test_a_stated_no_rules_every_gated_modelo_out(operation: PinnedAuthorityOperation) -> None:
    """The defect this closes: a stated no used to read as unanswered and kept all eight incomplete."""
    assert _verdicts(operation, answer=False) == dict.fromkeys(
        CAPITAL_GATED_MODELOS,
        ApplicabilityVerdict.NOT_APPLICABLE,
    )


def test_a_stated_yes_makes_every_gated_modelo_applicable(operation: PinnedAuthorityOperation) -> None:
    assert _verdicts(operation, answer=True) == dict.fromkeys(
        CAPITAL_GATED_MODELOS,
        ApplicabilityVerdict.APPLICABLE,
    )


def test_an_unanswered_record_carries_no_capital_income_fact_at_all(
    operation: PinnedAuthorityOperation,
) -> None:
    """The three verdicts above must differ because the record differs, not the projection."""
    record = capital_income_record(operation, answer=None)

    assert not [fact for fact in record.facts if fact.path == CAPITAL_PATH]
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())
    assert profile.pays_capital_income_with_retencion is None
