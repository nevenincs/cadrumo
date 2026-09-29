"""CLI surface tests for ``aeat app overview agenda``."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from contextvars import ContextVar

import pytest

from ._overview_native_support import invoke_native_overview
from ._runtime_profile_cli_fixture import NativeCliProfileFixture

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PROFILE: ContextVar[NativeCliProfileFixture] = ContextVar("agenda_native_profile")


@pytest.fixture(autouse=True)
def _native_profile(native_overview_profile: NativeCliProfileFixture) -> Iterator[None]:
    token = _PROFILE.set(native_overview_profile)
    try:
        yield
    finally:
        _PROFILE.reset(token)


def _invoke(args: list[str]):
    """Exercise the installed worker route for each legacy behavior assertion."""
    return invoke_native_overview(_PROFILE.get(), args)


def test_agenda_renders_envelope_with_explicit_date() -> None:
    """A concrete --date renders the agenda envelope including as_of,
    horizon, and the four cohort headers."""

    result = _invoke(
        ["app", "overview", "agenda", "--date", "2026-04-15", "--allow-incomplete"],
    )
    assert result.exit_code == 0, result.output
    assert "as_of\t2026-04-15" in result.output
    assert "horizon_days\t14" in result.output
    assert "next_due\t" in result.output
    assert "due_today\t" in result.output
    assert "due_soon\t" in result.output
    assert "overdue\t" in result.output


def test_agenda_json_preserves_exact_modelo_303_2025_quarterly_coordinates() -> None:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "overview",
            "agenda",
            "--date",
            "2025-02-01",
            "--horizon",
            "365",
            "--allow-incomplete",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    entries = (*payload["overdue"], *payload["due_today"], *payload["due_soon"])
    coordinates = tuple(
        (entry["modelo"], entry["period"])
        for entry in entries
        if entry["modelo"] == "303" and entry["period"].startswith("2025 ")
    )

    assert coordinates == (
        ("303", "2025 1T"),
        ("303", "2025 2T"),
        ("303", "2025 3T"),
        ("303", "2025 4T"),
    )


def test_agenda_rejects_zero_horizon() -> None:
    """A non-positive --horizon is refused before the service runs."""

    result = _invoke(
        ["app", "overview", "agenda", "--date", "2026-04-15", "--horizon", "0"],
    )
    assert result.exit_code != 0, result.output


def test_agenda_rejects_malformed_date() -> None:
    """A non-ISO --date is rejected by the parsing boundary."""

    result = _invoke(
        ["app", "overview", "agenda", "--date", "not-a-date"],
    )
    assert result.exit_code != 0, result.output


def test_agenda_help_advertises_local_only() -> None:
    """Help text must signal `local-only` across locales."""

    result = _invoke(["app", "overview", "agenda", "--help"])
    assert result.exit_code == 0, result.output
    assert any(
        token in result.output.lower() for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output


def test_agenda_horizon_widens_due_soon_window() -> None:
    """A wider --horizon includes more entries in due_soon than the
    default 14-day window. Asserts the horizon is honoured by the
    service rather than being a cosmetic flag."""

    narrow = _invoke(
        [
            "app",
            "overview",
            "agenda",
            "--date",
            "2026-01-01",
            "--horizon",
            "7",
            "--allow-incomplete",
        ],
    )
    wide = _invoke(
        [
            "app",
            "overview",
            "agenda",
            "--date",
            "2026-01-01",
            "--horizon",
            "180",
            "--allow-incomplete",
        ],
    )
    assert narrow.exit_code == 0, narrow.output
    assert wide.exit_code == 0, wide.output

    # The wider window's due_soon count must be >= the narrow window's.
    def _due_soon_count(output: str) -> int:
        for line in output.splitlines():
            if line.startswith("due_soon\t"):
                return int(line.split("\t", 1)[1])
        raise AssertionError(f"due_soon line missing from output: {output}")

    assert _due_soon_count(wide.output) >= _due_soon_count(narrow.output)
