"""CLI modelo period token tests."""

from __future__ import annotations

import pytest

from ._modelo_work_ux_support import operator_profile_facts
from .cli_runner import invoke_cached_cli
from .modelo_profile_seed import ProfileSeeder, seed_profile

__all__ = ["seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# --- Period-token confusion: --year and --period are composed ---


def test_work_create_year_repeated_into_period_explains_composition(seed_profile: ProfileSeeder) -> None:
    """``--year 2024 --period 2024`` is refused with a clear composition hint.

    The disaster-recovery testimony flagged the M100 annual confusion:
    repeating the filing year into ``--period`` composed internally to
    ``2024-2024`` and was refused with an opaque registry message. The
    error must instead explain that ``--year`` and ``--period`` are
    composed separately and enumerate the modelo's valid period tokens.
    """

    seed_profile(label="operator", facts=operator_profile_facts())
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
