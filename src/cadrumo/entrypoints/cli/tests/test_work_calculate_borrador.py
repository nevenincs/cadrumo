"""CLI surface tests for `aeat app modelo work calculate --borrador-snapshot-id`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ._modelo_work_ux_support import operator_profile_facts
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import native_cli_profile_scope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_PROFILE_LABEL = "Borrador missing work profile"


def _invoke_missing_work_unit(tmp_path: Path, *flags: str):
    """Reach the real worker metadata lookup under a fresh protected proof."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label=_PROFILE_LABEL, facts=operator_profile_facts())
        close_active_bucket_session()
        return invoke_cached_cli(
            [
                "--profile",
                _PROFILE_LABEL,
                "--profile-secrets-stdin",
                "app",
                "modelo",
                "work",
                "calculate",
                "no-such-work-unit-id",
                *flags,
            ],
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )


def test_work_calculate_help_exposes_borrador_snapshot_id_flag() -> None:
    """The `--borrador` flag is part of the command's advertised surface
    so operators can discover it via `--help`. The canonical option
    name is ``--borrador`` (matching the AEAT-side terminology)."""
    result = invoke_cached_cli(["app", "modelo", "work", "calculate", "--help"])
    assert result.exit_code == 0
    assert "--borrador" in result.output


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_work_calculate_refuses_unknown_work_unit_with_borrador_flag(tmp_path: Path) -> None:
    """Supplying `--borrador-snapshot-id` against a missing work-unit id
    surfaces as a clean BadParameter, not a traceback."""
    result = _invoke_missing_work_unit(tmp_path, "--borrador-snapshot-id", "some-snapshot-id")
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "runtime_unavailable" not in result.output.lower()


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_work_calculate_with_no_borrador_flag_remains_default_inert(tmp_path: Path) -> None:
    """Omitting `--borrador-snapshot-id` keeps the call inert against the
    borrador surface: the same unknown-work-unit refusal arrives without
    the flag because nothing exercises the borrador code path."""
    result = _invoke_missing_work_unit(tmp_path)
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    # Without the flag set, the refusal message must NOT mention the
    # borrador surface — the error originates from the work-unit lookup.
    output_lower = result.output.lower()
    assert "runtime_unavailable" not in output_lower
    assert "borrador" not in output_lower
