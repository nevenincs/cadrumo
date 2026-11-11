"""The residency-gated modelos read the fiscal-residency category in three states.

The projection under test is the production one: a real
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord` goes through
:func:`projection_for_taxpayer` and the registry's own applicability
classifier. LIRPF art. 9 makes habitual residence in Spain the test for the
IRPF and TRLIRNR art. 2 makes its absence the test for the IRNR, so the
category selects the tax and with it the modelo family: the resident declares
Modelo 100 and the non-resident declares Modelo 210 instead.

While the setup binding catalogue defaulted the path to ``resident_irpf`` the
category was effectively two-state. Every profile carried the resident token
whether or not anybody had asked, so Modelo 210 was ruled out and the resident
declarations admitted for a taxpayer who had never answered.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.applicability import derive_modelo_applicability
from ....domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import latest_period_end
from ..projections import projection_for_taxpayer
from .payer_fact_record_support import (
    NON_RESIDENT_CATEGORY,
    NON_RESIDENT_ONLY_MODELO,
    RESIDENCY_DECIDED_MODELOS,
    RESIDENCY_PATH,
    RESIDENCY_UNREACHED_MODELOS,
    RESIDENT_CATEGORY,
    RESIDENT_ONLY_MODELO,
    residency_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _verdicts(
    operation: PinnedAuthorityOperation,
    *,
    token: str | None,
    modelos: tuple[str, ...] = RESIDENCY_DECIDED_MODELOS,
) -> dict[str, ApplicabilityVerdict]:
    record = residency_record(operation, token=token)
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())
    return {
        modelo: derive_modelo_applicability(
            profile, modelo, operation=operation, reference_date=latest_period_end()
        ).verdict
        for modelo in modelos
    }


def test_an_unanswered_residency_leaves_every_residency_decided_modelo_incomplete(
    operation: PinnedAuthorityOperation,
) -> None:
    """The defect this closes: the catalogue default admitted the resident family unasked."""
    assert _verdicts(operation, token=None) == dict.fromkeys(
        RESIDENCY_DECIDED_MODELOS,
        ApplicabilityVerdict.INCOMPLETE,
    )


def test_a_stated_residence_in_spain_admits_the_irpf_and_rules_the_irnr_out(
    operation: PinnedAuthorityOperation,
) -> None:
    verdicts = _verdicts(operation, token=RESIDENT_CATEGORY)

    assert verdicts[RESIDENT_ONLY_MODELO] is ApplicabilityVerdict.APPLICABLE
    assert verdicts[NON_RESIDENT_ONLY_MODELO] is ApplicabilityVerdict.NOT_APPLICABLE


def test_a_stated_non_residence_admits_the_irnr_and_rules_the_resident_declarations_out(
    operation: PinnedAuthorityOperation,
) -> None:
    verdicts = _verdicts(operation, token=NON_RESIDENT_CATEGORY)

    assert verdicts[NON_RESIDENT_ONLY_MODELO] is ApplicabilityVerdict.APPLICABLE
    assert {verdict for modelo, verdict in verdicts.items() if modelo != NON_RESIDENT_ONLY_MODELO} == {
        ApplicabilityVerdict.NOT_APPLICABLE
    }


@pytest.mark.parametrize("token", [None, RESIDENT_CATEGORY, NON_RESIDENT_CATEGORY])
def test_the_other_residency_naming_modelos_are_refused_on_an_earlier_axis(
    operation: PinnedAuthorityOperation,
    token: str | None,
) -> None:
    """The three assertions above are about residency, not about an axis that moved with it."""
    assert _verdicts(operation, token=token, modelos=RESIDENCY_UNREACHED_MODELOS) == dict.fromkeys(
        RESIDENCY_UNREACHED_MODELOS,
        ApplicabilityVerdict.NOT_APPLICABLE,
    )


def test_an_unanswered_record_carries_no_residency_fact_at_all(
    operation: PinnedAuthorityOperation,
) -> None:
    """The verdicts above must differ because the record differs, not the projection."""
    record = residency_record(operation, token=None)

    assert not [fact for fact in record.facts if fact.path == RESIDENCY_PATH]
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())
    assert profile.fiscal_residency is None


def test_the_incomplete_residency_verdict_states_the_taxpayer_model_is_undeclared(
    operation: PinnedAuthorityOperation,
) -> None:
    """An unanswered axis must not borrow the not-applicable reason, which asserts an answer."""
    record = residency_record(operation, token=None)
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())

    applicability = derive_modelo_applicability(
        profile, NON_RESIDENT_ONLY_MODELO, operation=operation, reference_date=latest_period_end()
    )

    assert applicability.verdict is ApplicabilityVerdict.INCOMPLETE
    assert applicability.failure is not None
    assert applicability.failure.facts["taxpayer_model_declared"] is False
    assert applicability.failure.facts["entity_type_declared"] is True
