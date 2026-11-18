"""A period token is admitted for a modelo only when it is a period that modelo's registry declares."""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..period_admission import ModeloPeriodAdmissionOutcome, admit_modelo_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_OUTCOME = ModeloPeriodAdmissionOutcome


@pytest.mark.parametrize(
    ("modelo", "token", "code"),
    [("130", "2T", "2T"), ("130", " 2t ", "2T"), ("303", "07", "07"), ("100", "0A", "0A")],
)
def test_a_declared_period_is_admitted_as_its_typed_period(
    authority_operation: PinnedAuthorityOperation, modelo: str, token: str, code: str
) -> None:
    admission = admit_modelo_period(modelo, _YEAR, token, operation=authority_operation)

    assert admission.outcome is _OUTCOME.ADMITTED
    assert admission.period == Period.from_year_and_code(_YEAR, code)


@pytest.mark.parametrize("token", ["0A", "1P", "07"])
def test_a_period_the_modelo_does_not_declare_is_refused_with_the_declared_tokens(
    authority_operation: PinnedAuthorityOperation, token: str
) -> None:
    admission = admit_modelo_period("130", _YEAR, token, operation=authority_operation)

    assert admission.outcome is _OUTCOME.NOT_DECLARED
    assert admission.period is None
    assert admission.declared_tokens == ("1T", "2T", "3T", "4T")


def test_a_token_that_is_no_period_is_refused_even_when_the_registry_declares_it(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    admission = admit_modelo_period("036", _YEAR, "alta", operation=authority_operation)

    assert admission.outcome is _OUTCOME.NOT_A_PERIOD
    assert admission.period is None
    assert admission.refusal_locale_key is None
    assert "alta" in admission.declared_tokens


def test_a_token_that_is_no_period_for_a_modelo_with_periods_is_refused(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    admission = admit_modelo_period("130", _YEAR, "5T", operation=authority_operation)

    assert admission.outcome is _OUTCOME.NOT_A_PERIOD
    assert admission.declared_tokens == ("1T", "2T", "3T", "4T")


@pytest.mark.parametrize("token", ["EVENT-1", "event-2", " EVENT-12 "])
def test_a_concrete_event_is_admitted_where_the_registry_declares_the_event_selector(
    authority_operation: PinnedAuthorityOperation, token: str
) -> None:
    admission = admit_modelo_period("210", _YEAR, token, operation=authority_operation)

    assert "EVENT-N" in admission.declared_tokens
    assert admission.outcome is _OUTCOME.ADMITTED
    assert admission.period == Period.from_year_and_code(_YEAR, token.strip().upper())


def test_the_event_selector_itself_is_no_period(authority_operation: PinnedAuthorityOperation) -> None:
    admission = admit_modelo_period("210", _YEAR, "EVENT-N", operation=authority_operation)

    assert admission.outcome is _OUTCOME.NOT_A_PERIOD
    assert admission.period is None
