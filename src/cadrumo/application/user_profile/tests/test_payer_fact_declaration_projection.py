"""Every modelo the withholding and intracommunity payer facts gate reads three states.

The projection under test is the production one: a real
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord` goes through
:func:`projection_for_taxpayer` and the registry's own applicability
classifier. A record that carries no answer must leave each gated modelo
INCOMPLETE, a record that answers no must make it NOT_APPLICABLE, and a record
that answers yes must make it APPLICABLE. Modelos 111, 115, 180, 190, 216, 296
and 349 are all asserted, because they share these four facts and a defaulted
negative refused every one of them for a taxpayer nobody asked.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.applicability import derive_modelo_applicability
from ....domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..projections import projection_for_taxpayer
from .payer_fact_record_support import PAYER_FACT_GATED_MODELOS, PAYER_FACT_PATHS, payer_fact_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _verdict(operation: PinnedAuthorityOperation, modelo: str, *, answer: bool | None) -> ApplicabilityVerdict:
    record = payer_fact_record(operation, answer=answer)
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())
    return derive_modelo_applicability(profile, modelo, operation=operation).verdict


@pytest.mark.parametrize("modelo", PAYER_FACT_GATED_MODELOS)
def test_an_unanswered_payer_fact_leaves_the_modelo_incomplete(
    modelo: str,
    operation: PinnedAuthorityOperation,
) -> None:
    assert _verdict(operation, modelo, answer=None) is ApplicabilityVerdict.INCOMPLETE


@pytest.mark.parametrize("modelo", PAYER_FACT_GATED_MODELOS)
def test_a_stated_no_makes_the_modelo_not_applicable(
    modelo: str,
    operation: PinnedAuthorityOperation,
) -> None:
    assert _verdict(operation, modelo, answer=False) is ApplicabilityVerdict.NOT_APPLICABLE


@pytest.mark.parametrize("modelo", PAYER_FACT_GATED_MODELOS)
def test_a_stated_yes_makes_the_modelo_applicable(
    modelo: str,
    operation: PinnedAuthorityOperation,
) -> None:
    assert _verdict(operation, modelo, answer=True) is ApplicabilityVerdict.APPLICABLE


def test_an_unanswered_record_carries_no_payer_fact_at_all(operation: PinnedAuthorityOperation) -> None:
    """The three verdicts above must differ because the record differs, not the projection."""
    record = payer_fact_record(operation, answer=None)

    assert not [fact for fact in record.facts if fact.path in PAYER_FACT_PATHS]
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())
    assert profile.has_employees is None
    assert profile.pays_professionals_with_retencion is None
    assert profile.pays_rent_with_retencion is None
    assert profile.does_intracomunitario is None
