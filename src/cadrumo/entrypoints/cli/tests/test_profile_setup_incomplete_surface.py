"""The overview calendar names a mid-setup profile instead of dropping it.

A profile is born INCOMPLETE at registration and reaches COMPLETE only at the
setup-commit compare-and-swap, so a bucket whose setup was never committed is
what registration alone produces.  That is the stimulus here: no artefact is
staged on disk and no retired member is written, because the incomplete state
is a record state rather than a directory shape.

``overview calendar --all-profiles`` classifies the active profile by that
state.  A mid-setup profile carries no calendar, and the surface says so on
its own marker line while excluding it from the calendar-bearing count --
reporting it but still counting it would let a profile with no calendar
inflate coverage, and dropping it silently would hide a profile the operator
started and has not finished.

The retired-custody refusal this module once asserted is a different subject
and lives in its own module.  Both shared this one on the since-invalid
premise that staging a retired plaintext manifest was how an uncommitted
bucket was produced; it is not, and it never reaches this classifier -- the
discovery guard refuses first.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage

__all__ = ["isolated_profile_storage"]
from ._profile_lifecycle_support import create_profile_via_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The machine line naming a profile the calendar cannot project.
_SETUP_INCOMPLETE_MARKER = "profile_setup_incomplete\t"

_CALENDAR = (
    "app",
    "overview",
    "calendar",
    "--from",
    "2026-01-01",
    "--to",
    "2026-03-31",
    "--all-profiles",
    "--allow-incomplete",
)


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _setup_incomplete_rows(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith(_SETUP_INCOMPLETE_MARKER)]


def test_overview_calendar_names_an_uncommitted_profile_and_does_not_count_it() -> None:
    """A profile whose setup was never committed is named, and counted nowhere."""
    create_profile_via_cli("onboarding", complete=False)

    result = _invoke(_CALENDAR)

    assert result.exit_code == 0, result.output
    # Matched by marker and label rather than by bucket id: the id is redacted
    # on this surface, so an assertion carrying the registered id never matches.
    rows = _setup_incomplete_rows(result.output)
    assert len(rows) == 1, result.output
    assert rows[0].endswith("\tonboarding"), result.output
    assert "profiles\t0" in result.output, result.output


def test_overview_calendar_counts_a_committed_profile_and_names_no_incomplete_row() -> None:
    """Anti-tautology: the same surface on a committed profile carries neither half.

    Without this case the companion above passes on a surface that emits the
    marker unconditionally, or on one that counts nothing at all.
    """
    create_profile_via_cli("filer")

    result = _invoke(_CALENDAR)

    assert result.exit_code == 0, result.output
    assert _setup_incomplete_rows(result.output) == [], result.output
    assert "profiles\t1" in result.output, result.output
