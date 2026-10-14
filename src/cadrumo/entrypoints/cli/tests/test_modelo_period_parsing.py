"""Modelo period parser preserves registry-declared token rules."""

from __future__ import annotations

import pytest
import typer

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "period,expected_normalized",
    [
        ("1T", "1T"),
        ("1t", "1T"),
        ("4T", "4T"),
        ("0A", "0A"),
        ("0a", "0A"),
        ("1P", "1P"),
    ],
)
def test_work_create_accepts_core_period_tokens(period: str, expected_normalized: str) -> None:
    """Valid AEAT period tokens are resolved to core ``Period`` values."""

    from cadrumo.entrypoints.cli._modelo_behavior_support import resolve_year_period

    normalized = resolve_year_period(2026, period)
    assert normalized.filing_year == 2026
    assert normalized.registry_token == expected_normalized, (
        f"period {period!r} normalized to {normalized.registry_token!r}, expected {expected_normalized!r}"
    )


def test_optional_cli_period_requires_year() -> None:
    """A supplied ``--period`` must not be dropped when ``--year`` is absent."""

    from cadrumo.entrypoints.cli._modelo_behavior_support import resolve_optional_cli_period

    with pytest.raises(typer.BadParameter) as raised:
        resolve_optional_cli_period(year=None, period="1T", modelo="130")

    assert "--year" in str(raised.value)
    assert "1T" in str(raised.value)


def test_period_token_error_enumerates_modelo_specific_tokens() -> None:
    """The period-token error lists the registry-declared tokens for the modelo.

    Modelo 100 is annual (``0A`` only); the helper must ground the
    valid-token set in the registry's declared periods rather than a
    generic shape hint.
    """

    from cadrumo.entrypoints.cli._modelo_behavior_support import _declared_period_tokens

    annual = _declared_period_tokens("100")
    assert annual == ("0A",), f"M100 declared periods: {annual!r}"

    quarterly = _declared_period_tokens("303")
    # M303 now also declares monthly periods alongside quarterly tokens; assert
    # that the quarterly markers are present rather than asserting an exact tuple.
    assert "1T" in quarterly and "2T" in quarterly, f"M303 declared periods: {quarterly!r}"

    # Unknown / unspecified modelo yields an empty tuple so the caller
    # falls back to the generic period-shape hint.
    assert _declared_period_tokens(None) == ()
    assert _declared_period_tokens("999") == ()
