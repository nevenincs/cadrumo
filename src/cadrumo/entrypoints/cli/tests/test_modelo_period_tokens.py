"""CLI modelo period token tests."""

from __future__ import annotations

import pytest
import typer

from ....tests.cli_runner import invoke_cached_cli
from ._modelo_fixtures import active_cli_profile_fixture

__all__ = ["active_cli_profile_fixture"]

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

    from .._modelo_behavior_support import resolve_year_period

    normalized = resolve_year_period(2026, period)
    assert normalized.filing_year == 2026
    assert normalized.registry_token == expected_normalized, (
        f"period {period!r} normalized to {normalized.registry_token!r}, expected {expected_normalized!r}"
    )


def test_optional_cli_period_requires_year() -> None:
    """A supplied ``--period`` must not be dropped when ``--year`` is absent."""

    from .._modelo_behavior_support import resolve_optional_cli_period

    with pytest.raises(typer.BadParameter) as raised:
        resolve_optional_cli_period(year=None, period="1T", modelo="130")

    assert "--year" in str(raised.value)
    assert "1T" in str(raised.value)


# --- Period-token confusion: --year and --period are composed ---


def test_work_create_year_repeated_into_period_explains_composition(_active_cli_profile: None) -> None:
    """``--year 2024 --period 2024`` is refused with a clear composition hint.

    The disaster-recovery testimony flagged the M100 annual confusion:
    repeating the filing year into ``--period`` composed internally to
    ``2024-2024`` and was refused with an opaque registry message. The
    error must instead explain that ``--year`` and ``--period`` are
    composed separately and enumerate the modelo's valid period tokens.
    """

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "100",
            "--year",
            "2024",
            "--period",
            "2024",
            "--revision",
            "2024",
        ],
    )

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    flat = result.output.replace("\n", " ")
    # The opaque internal composition must not surface verbatim.
    assert "2024-2024" not in flat
    # The error explains the year + period composition.
    assert "--year" in flat and "--period" in flat
    # M100 is annual-only: the valid token 0A must be surfaced.
    assert "0A" in flat


def test_period_token_error_enumerates_modelo_specific_tokens() -> None:
    """The period-token error lists the registry-declared tokens for the modelo.

    Modelo 100 is annual (``0A`` only); the helper must ground the
    valid-token set in the registry's declared periods rather than a
    generic shape hint.
    """

    from .._modelo_behavior_support import _declared_period_tokens

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


@pytest.mark.parametrize(
    "modelo,bad_period,expected_token",
    [
        ("100", "INVALID", "0A"),
        ("303", "99", "1T"),
    ],
)
def test_describe_invalid_period_enumerates_modelo_tokens(modelo: str, bad_period: str, expected_token: str) -> None:
    """``modelo describe --period INVALID`` lists the modelo's valid tokens.

    A malformed bare ``--period`` previously surfaced only the generic
    ``period must be YYYY...`` registry shape hint. The error now names
    the registry-declared period tokens for the modelo.
    """

    result = invoke_cached_cli(["app", "modelo", "describe", modelo, "--period", bad_period])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    flat = result.output.replace("\n", " ")
    assert expected_token in flat, f"expected token {expected_token!r} not enumerated: {result.output}"


def test_describe_unknown_modelo_keeps_its_own_error() -> None:
    """An unknown modelo with a period flag keeps the unknown-modelo error.

    The period-token enrichment must not mask a genuine unknown-modelo
    refusal as a period-token problem.
    """

    result = invoke_cached_cli(["app", "modelo", "describe", "999", "--period", "0A"])

    assert result.exit_code != 0, result.output
    flat = result.output.replace("\n", " ").lower()
    assert "999" in flat
    # The error is about the modelo, not the (valid) period token.
    assert "period token" not in flat
