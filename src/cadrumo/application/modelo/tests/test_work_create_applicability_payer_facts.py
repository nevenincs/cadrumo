"""The work-create applicability guard must not refuse an unanswered payer fact.

``modelo_work_create_applicability_refusal`` blocks creation on a
``NOT_APPLICABLE`` verdict. The withholding and intracommunity payer facts are
three-state, so a profile record that carries no answer at all leaves the
verdict INCOMPLETE and the guard must let the work unit be created for every
modelo those facts gate; only a stored ``false`` is the operator's own no,
which does block it.

The record is a real :func:`create_user_profile_record` value under the pinned
authority schema, shared with the projection test that owns it, and the guard
is the one the create operation calls.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...user_profile.tests.payer_fact_record_support import PAYER_FACT_GATED_MODELOS, payer_fact_record
from ..work_create_policy import modelo_work_create_applicability_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("modelo", PAYER_FACT_GATED_MODELOS)
def test_an_unanswered_payer_fact_does_not_refuse_work_creation(
    modelo: str,
    operation: PinnedAuthorityOperation,
) -> None:
    refusal = modelo_work_create_applicability_refusal(
        modelo,
        filing_year=filing_year_envelope().horizon,
        allow_not_applicable=False,
        record=payer_fact_record(operation, answer=None),
        operation=operation,
    )

    assert refusal is None


@pytest.mark.parametrize("modelo", PAYER_FACT_GATED_MODELOS)
def test_a_stated_no_refuses_work_creation(modelo: str, operation: PinnedAuthorityOperation) -> None:
    refusal = modelo_work_create_applicability_refusal(
        modelo,
        filing_year=filing_year_envelope().horizon,
        allow_not_applicable=False,
        record=payer_fact_record(operation, answer=False),
        operation=operation,
    )

    assert refusal is not None
    assert refusal.modelo == modelo
