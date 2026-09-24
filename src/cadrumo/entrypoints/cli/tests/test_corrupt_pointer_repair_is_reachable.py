"""The command a corrupt pointer's refusal recommends can run while the pointer is corrupt.

A corrupt active-profile pointer refuses every command before parsing, because
startup composes settings from it, and the refusal recommends
``aeat config repair profile``. That command declares that it repairs the
pointer, so it alone reads a corrupt record as no selection and reaches its
own health check, which still sees the corruption. These run the real console
entry point in a fresh interpreter with no settings override, since an
override would skip the very read that made the command unreachable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process

from ....core.bucket_pointer import pointer_path
from ....tests.inventory import REPO_ROOT
from ..command_spec import CommandNodeKind, CommandSpec
from ..command_specs import COMMAND_GRAPH
from .subprocess_cli import as_text_completed_process

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CORRUPT_POINTER = b"not = valid = toml"


def _run(storage_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith(("AEAT_", "PYTEST_"))}
    env.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
    )
    return as_text_completed_process(
        run_audited_process(
            [
                sys.executable,
                "-c",
                "import sys; from cadrumo.entrypoints.cli.main import main; sys.argv = ['aeat', *sys.argv[1:]]; main()",
                "--format",
                "json",
                *args,
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=180.0,
        ),
    )


@pytest.fixture
def corrupt_root(tmp_path: Path) -> Path:
    root = tmp_path / "state"
    root.mkdir()
    pointer_path(root).write_bytes(_CORRUPT_POINTER)
    return root


def test_the_repair_command_reaches_its_health_check_and_reports_the_pointer_repairable(corrupt_root: Path) -> None:
    probed = _run(corrupt_root, "config", "repair", "profile")

    assert probed.returncode == 0, probed.stdout + probed.stderr
    document = json.loads(probed.stdout)
    assert document["command"] == "config.repair.profile"
    before = document["result"]["before"]
    assert (before["status"], before["repairable_by_clearing_pointer"]) == ("pointer_unreadable", True)
    assert before["precondition_action"]["action"]["action_id"] == "operator.profile.repair_active_pointer"
    assert document["result"]["dry_run"] is True
    assert pointer_path(corrupt_root).read_bytes() == _CORRUPT_POINTER


def test_the_confirmed_clear_refuses_for_manual_recovery_and_leaves_the_record(corrupt_root: Path) -> None:
    cleared = _run(corrupt_root, "config", "repair", "profile", "--clear-active", "--yes")

    assert cleared.returncode != 0
    assert cleared.stdout == ""
    error = json.loads(cleared.stderr)["error"]
    assert error["code"] == "REFUSED_ACTIVE_PROFILE_POINTER_MANUAL_RECOVERY"
    assert error["context"]["path"] == str(pointer_path(corrupt_root))
    assert "Traceback" not in cleared.stderr
    assert pointer_path(corrupt_root).read_bytes() == _CORRUPT_POINTER


def test_a_command_that_does_not_declare_the_repair_is_still_refused(corrupt_root: Path) -> None:
    """Detector teeth: the relaxation follows the declaration, not the corruption."""
    listed = _run(corrupt_root, "config", "profile", "list")

    assert listed.returncode != 0
    assert json.loads(listed.stderr)["error"]["code"] == "INTEGRITY_ACTIVE_PROFILE_POINTER"


@pytest.mark.parametrize(
    "arguments",
    [
        ("config", "repair", "profile"),
        ("--format", "json", "config", "repair", "profile", "--clear-active", "--yes"),
        ("--format=json", "config", "repair", "profile", "--profile", "someone"),
    ],
    ids=["bare", "root-option-and-flags", "inline-root-option-and-valued-option"],
)
def test_the_invocation_resolves_to_the_declaring_leaf_before_parsing(arguments: tuple[str, ...]) -> None:
    resolved = COMMAND_GRAPH.resolve_invocation(arguments)

    assert resolved is not None
    assert resolved.key == "config_repair_profile"
    assert resolved.repairs_active_profile_pointer is True


@pytest.mark.parametrize(
    "arguments",
    [
        ("config", "repair"),
        ("--not-an-option", "config", "repair", "profile"),
        ("config", "nope", "profile"),
        ("--", "config", "repair", "profile"),
        (),
    ],
    ids=["group", "undeclared-option", "unknown-token", "end-of-options", "empty"],
)
def test_an_unreadable_or_partial_invocation_names_no_leaf(arguments: tuple[str, ...]) -> None:
    assert COMMAND_GRAPH.resolve_invocation(arguments) is None


def test_only_a_leaf_can_declare_the_pointer_repair() -> None:
    group = COMMAND_GRAPH.resolve_path(("aeat", "config", "repair"))
    assert group.kind is CommandNodeKind.GROUP

    with pytest.raises(ValueError, match="only an executable leaf"):
        CommandSpec(
            group.key,
            group.parent_key,
            group.token,
            kind=group.kind,
            help_key=group.help_key,
            short_help_key=group.short_help_key,
            invocation=group.invocation,
            parameters=group.parameters,
            policy=group.policy,
            handler=group.handler,
            result_schema=group.result_schema,
            repairs_active_profile_pointer=True,
        )
