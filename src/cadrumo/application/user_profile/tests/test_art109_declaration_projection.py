"""Modelo 130 reads the Art. 109 RIRPF coverage fact in three states.

The projection under test is the production one: a real
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord` goes through
:func:`projection_for_taxpayer` and the registry's own applicability
classifier. RIRPF art. 109.1 exempts the taxpayer from pagos fraccionados when
at least 70 per cent of the previous year's activity income bore retención, so
a declared yes rules Modelo 130 out and a declared no leaves it due. A record
nobody answered must stay INCOMPLETE: a defaulted negative asserted an answer
the taxpayer never gave and made the obligation look settled.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.applicability import derive_modelo_applicability
from ....domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..projections import projection_for_taxpayer
from .payer_fact_record_support import ART109_GATED_MODELO, ART109_PATH, art109_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _verdict(operation: PinnedAuthorityOperation, *, answer: bool | None) -> ApplicabilityVerdict:
    record = art109_record(operation, answer=answer)
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())
    return derive_modelo_applicability(profile, ART109_GATED_MODELO, operation=operation).verdict


def test_an_unanswered_coverage_fact_leaves_modelo_130_incomplete(operation: PinnedAuthorityOperation) -> None:
    assert _verdict(operation, answer=None) is ApplicabilityVerdict.INCOMPLETE


def test_a_stated_no_leaves_the_pago_fraccionado_due(operation: PinnedAuthorityOperation) -> None:
    assert _verdict(operation, answer=False) is ApplicabilityVerdict.APPLICABLE


def test_a_stated_yes_applies_the_art109_exception(operation: PinnedAuthorityOperation) -> None:
    assert _verdict(operation, answer=True) is ApplicabilityVerdict.NOT_APPLICABLE


def test_an_unanswered_record_carries_no_coverage_fact_at_all(operation: PinnedAuthorityOperation) -> None:
    """The three verdicts above must differ because the record differs, not the projection."""
    record = art109_record(operation, answer=None)

    assert not [fact for fact in record.facts if fact.path == ART109_PATH]
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())
    assert profile.art109_activity_income_withholding_ge_70pct is None
