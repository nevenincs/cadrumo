"""A filing handoff admits its Modelo 130 period by the rule every frontend's period goes through."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest

from cadrumo.application.actividad_asset.activity_asset_contracts import ActivityAssetFilingHandoffRequest
from cadrumo.application.actividad_asset.activity_asset_executors import activity_asset_executors_refusal
from cadrumo.application.modelo.registry_discovery import declared_modelo_period_tokens
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.period import Period, PeriodError
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.form_codes import form_for_role
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ENVELOPE = filing_year_envelope()
_YEARS = tuple(range(_ENVELOPE.floor, _ENVELOPE.horizon + 1))

_PERIOD_CODES = ("0A", "1P", "2P", "3P", "4P", "01", "07", "12", "1T", "2T", "3T", "4T")
"""Codes the period type names; the registry decides which of them the Modelo 130 declares."""


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _request(tax_year: int, token: str) -> ActivityAssetFilingHandoffRequest:
    return ActivityAssetFilingHandoffRequest(profile_id=uuid4(), tax_year=tax_year, m130_period=token)


def _declared(operation: PinnedAuthorityOperation) -> tuple[str, ...]:
    declared = declared_modelo_period_tokens(
        form_for_role("renta.direct_instalment", authority=operation), operation=operation
    )
    assert declared, "the registry declares the Modelo 130 periods"
    return declared


def _undeclared_periods(tax_year: int, declared: tuple[str, ...]) -> tuple[str, ...]:
    """The codes that make a period of the year but that the Modelo 130 does not declare."""

    def is_period(code: str) -> bool:
        try:
            Period.from_year_and_code(tax_year, code)
        except PeriodError:
            return False
        return True

    return tuple(code for code in _PERIOD_CODES if is_period(code) and code not in declared)


@pytest.mark.parametrize("tax_year", _YEARS)
def test_a_period_the_modelo_130_does_not_declare_is_refused_naming_the_declared_ones(
    tax_year: int, operation: PinnedAuthorityOperation
) -> None:
    declared = _declared(operation)
    undeclared = _undeclared_periods(tax_year, declared)
    assert undeclared, "some period code is no Modelo 130 period"

    for token in undeclared:
        with pytest.raises(ActividadAssetValidationError, match="m130_period_not_declared") as refused:
            _request(tax_year, token).requested_period(operation=operation)
        refusal = activity_asset_executors_refusal(refused.value, OutputLanguage("en"))
        assert refusal is not None
        assert refusal.reason_facts == {"field": "m130_period", "tokens": ", ".join(declared)}
        assert refusal.refusal_words is not None
        assert all(code in refusal.refusal_words for code in declared)


@pytest.mark.parametrize("tax_year", _YEARS)
def test_every_declared_modelo_130_period_is_admitted(tax_year: int, operation: PinnedAuthorityOperation) -> None:
    for token in _declared(operation):
        admitted = _request(tax_year, token.lower()).requested_period(operation=operation)
        assert admitted == Period.from_year_and_code(tax_year, token)


def test_a_code_that_is_no_period_keeps_its_own_reason(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(ActividadAssetValidationError, match="m130_period_invalid"):
        _request(_ENVELOPE.horizon, "9T").requested_period(operation=operation)
