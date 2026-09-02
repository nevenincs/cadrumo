"""Real proofs that a requested destination starts and returns an outcome.

The module is EXECUTED as its own process here, never imported, because that
is the only shape a sibling entrypoint can use: it may not import this
package, so it spawns the module-execution surface and reads a file back. An
import-based assertion cannot see that crossing at all.

The self-test invocation is what makes a headless proof honest here: it
mounts the real destination host, settles it, and leaves exactly as a
cancelling operator would, so what is observed is a started session rather
than a resolved import.

Nothing asserts on rendered prose. The prose is locale data read from the same
catalogue the app reads, so asserting it would prove only that one file was
consulted twice.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ...full_screen_session_protocol import (
    DESTINATION_OPTION,
    OUTCOME_FILE_OPTION,
    SELF_TEST_FLAG,
    WORK_UNIT_ID_OPTION,
    FullScreenDestination,
    FullScreenOutcomeKind,
    parse_outcome,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MODULE = "cadrumo.entrypoints.tui"
_STARTUP_GRACE_SECONDS = 90.0
_REPO_ROOT = Path(__file__).parents[5]


def _run_module(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    """Execute the module as a real process with the given session arguments."""
    return subprocess.run(  # noqa: S603 - fixed argv, no shell, repo-local module
        [sys.executable, "-m", _MODULE, *arguments],
        cwd=_REPO_ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=_STARTUP_GRACE_SECONDS,
    )


def _select_arguments(outcome_file: Path) -> list[str]:
    """The picker destination, self-tested, recording into ``outcome_file``."""
    return [
        DESTINATION_OPTION,
        FullScreenDestination.MODELO_WORK_SELECT.value,
        OUTCOME_FILE_OPTION,
        str(outcome_file),
        SELF_TEST_FLAG,
    ]


def test_a_requested_destination_starts_and_records_its_outcome(tmp_path: Path) -> None:
    """The picker destination runs to completion and reports how it ended.

    This is the whole crossing in one case: arguments in, a real host mounted
    and dismissed, an outcome record out, and a clean exit status. A
    cancellation is the honest outcome for a session no operator chose from,
    and it is reported as a cancellation rather than as an empty selection.
    """
    outcome_file = tmp_path / "outcome.json"

    completed = _run_module(*_select_arguments(outcome_file))
    rendered = (completed.stdout + completed.stderr).decode("utf-8", errors="replace")

    assert completed.returncode == 0, rendered[:2000]
    assert "Traceback (most recent call last)" not in rendered, rendered[:2000]
    assert outcome_file.exists(), f"the session left no outcome record:\n{rendered[:2000]}"

    outcome = parse_outcome(outcome_file.read_text(encoding="utf-8"))

    assert outcome.kind is FullScreenOutcomeKind.CANCELLED
    assert outcome.work_unit_id is None


def test_a_session_child_carries_no_cli_module(tmp_path: Path) -> None:
    """A destination request must not drag a sibling entrypoint into the process.

    The requesting entrypoint reaches this surface by executing it, so the
    started session's import graph must still contain no CLI module even
    though a CLI command is what asked for the destination. The shared session
    protocol is what both sides read, and it belongs to neither of them.
    """
    outcome_file = tmp_path / "outcome.json"
    probe = (
        "import json, sys\n"
        f"from {_MODULE}.__main__ import run\n"
        f"run({_select_arguments(outcome_file)!r})\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith('cadrumo.entrypoints.'))))\n"
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and literal probe
        [sys.executable, "-c", probe],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=_STARTUP_GRACE_SECONDS,
    )

    imported = set(json.loads(completed.stdout.splitlines()[-1]))
    cli_modules = sorted(name for name in imported if name.startswith("cadrumo.entrypoints.cli"))

    assert f"{_MODULE}.destination_session" in imported, f"the request never reached a destination: {sorted(imported)}"
    assert not cli_modules, f"opening a destination pulled in CLI internals: {cli_modules}"


@pytest.mark.parametrize(
    "extra_arguments",
    [
        (),
        (WORK_UNIT_ID_OPTION, "not-a-work-unit-id"),
    ],
    ids=["no-subject", "malformed-subject"],
)
def test_a_destination_without_a_usable_subject_fails_closed(tmp_path: Path, extra_arguments: tuple[str, ...]) -> None:
    """A refused request leaves no record, so nothing can read it as a result.

    An outcome written on refusal would let a request the child never
    understood arrive at the requester as a completed session.
    """
    outcome_file = tmp_path / "outcome.json"

    completed = _run_module(
        DESTINATION_OPTION,
        FullScreenDestination.MODELO_WORK_REVIEW.value,
        OUTCOME_FILE_OPTION,
        str(outcome_file),
        *extra_arguments,
    )

    assert completed.returncode != 0, (completed.stdout + completed.stderr).decode("utf-8", errors="replace")[:2000]
    assert not outcome_file.exists()


def test_an_unknown_destination_token_is_refused(tmp_path: Path) -> None:
    """The destination set is closed, so an unlisted token opens nothing."""
    outcome_file = tmp_path / "outcome.json"

    completed = _run_module(DESTINATION_OPTION, "modelo.work.invented", OUTCOME_FILE_OPTION, str(outcome_file))

    assert completed.returncode != 0
    assert not outcome_file.exists()
