"""CLI surface tests for `aeat app modelo work calculate --borrador-snapshot-id`."""

from __future__ import annotations

import pytest

from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_work_calculate_help_exposes_borrador_snapshot_id_flag() -> None:
    """The `--borrador` flag is part of the command's advertised surface
    so operators can discover it via `--help`. The canonical option
    name is ``--borrador`` (matching the AEAT-side terminology)."""
    result = invoke_cached_cli(["app", "modelo", "work", "calculate", "--help"])
    assert result.exit_code == 0
    assert "--borrador" in result.output


def test_work_calculate_refuses_unknown_work_unit_with_borrador_flag() -> None:
    """Supplying `--borrador-snapshot-id` against a missing work-unit id
    surfaces as a clean BadParameter, not a traceback."""
    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "calculate",
            "no-such-work-unit-id",
            "--borrador-snapshot-id",
            "some-snapshot-id",
        ],
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_work_calculate_with_no_borrador_flag_remains_default_inert() -> None:
    """Omitting `--borrador-snapshot-id` keeps the call inert against the
    borrador surface: the same unknown-work-unit refusal arrives without
    the flag because nothing exercises the borrador code path."""
    result = invoke_cached_cli(
        ["app", "modelo", "work", "calculate", "no-such-work-unit-id"],
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    # Without the flag set, the refusal message must NOT mention the
    # borrador surface — the error originates from the work-unit lookup.
    output_lower = result.output.lower()
    assert "borrador" not in output_lower
