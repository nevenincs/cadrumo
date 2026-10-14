"""A sandbox whose frames fail keeps its logs: its runtime and worker records survive the teardown."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ..checks import _with_notes
from ..errors import SequenceExecutionError
from ..runner import SequenceSandbox, _logs_retained_on_failure

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _sandbox(root: Path) -> SequenceSandbox:
    log = root / "logs" / "pid-1" / "cadrumo.log"
    log.parent.mkdir(parents=True)
    log.write_text("profile_worker_task_failed\n", encoding="utf-8")
    return SequenceSandbox(
        storage_root=root, workdir=root, profile_id="synthetic", frozen_instant=datetime(2026, 1, 1, tzinfo=UTC)
    )


def test_a_failing_sequence_keeps_its_sandbox_logs_and_names_where(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path / "sandbox")
    retained = tmp_path / "retained"

    with (
        pytest.raises(SequenceExecutionError) as failed,
        _logs_retained_on_failure(sandbox, retained, "how-to/page"),
    ):
        raise SequenceExecutionError("sequence", "frame exited 2")

    (kept,) = retained.iterdir()
    assert kept.name.startswith("how-to_page-")
    assert (kept / "pid-1" / "cadrumo.log").read_text(encoding="utf-8") == "profile_worker_task_failed\n"
    assert _with_notes(failed.value).endswith(f"\n  sandbox logs retained at {kept}")


def test_a_passing_sequence_keeps_nothing(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path / "sandbox")
    retained = tmp_path / "retained"

    with _logs_retained_on_failure(sandbox, retained, "how-to/page"):
        pass

    assert not retained.exists()
