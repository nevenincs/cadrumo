"""A sandbox that fails keeps its logs: its runtime and worker records survive the sandbox's removal."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from cadrumo.core.logging import default_log_file_path, flush_logging
from cadrumo.tests.env_scope import derived_storage_settings
from dev._paths import TEMP_ROOT

from ..checks import _with_notes
from ..errors import SequenceExecutionError
from ..runner import _logs_retained_on_failure, _retained_logs_root
from ..sandbox import _isolated_diagnostic_log

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_failure_retention_uses_worktree_scratch_instead_of_product_storage(tmp_path: Path) -> None:
    with derived_storage_settings(tmp_path / "operator-storage"):
        retained = _retained_logs_root()

    assert retained == TEMP_ROOT / "failed-sandboxes"
    assert not (tmp_path / "operator-storage").exists()


def test_each_sandbox_rebinds_logging_to_its_canonical_storage_root(tmp_path: Path) -> None:
    paths: list[Path] = []
    for name in ("first", "second"):
        with derived_storage_settings(tmp_path / name), _isolated_diagnostic_log():
            path = default_log_file_path()
            logging.getLogger("cadrumo.docs.sequence").warning("sequence-log-%s", name)
            assert flush_logging()
            paths.append(path)

    assert paths[0].is_relative_to(tmp_path / "first")
    assert paths[1].is_relative_to(tmp_path / "second")
    assert "sequence-log-first" in paths[0].read_text(encoding="utf-8")
    assert "sequence-log-second" not in paths[0].read_text(encoding="utf-8")
    assert "sequence-log-second" in paths[1].read_text(encoding="utf-8")
    assert "sequence-log-first" not in paths[1].read_text(encoding="utf-8")


def _sandbox(root: Path) -> Path:
    log = root / "storage" / "logs" / "pid-1" / "cadrumo.log"
    log.parent.mkdir(parents=True)
    log.write_text("profile_worker_task_failed\n", encoding="utf-8")
    return root


def test_a_failing_sandbox_keeps_every_log_directory_and_names_where(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path / "sandbox")
    retained = tmp_path / "retained"

    with (
        pytest.raises(SequenceExecutionError) as failed,
        _logs_retained_on_failure(sandbox, retained, "how-to/page"),
    ):
        raise SequenceExecutionError("sequence", "frame exited 2")

    (kept,) = retained.iterdir()
    assert kept.name.startswith("how-to_page-")
    assert (kept / "storage" / "logs" / "pid-1" / "cadrumo.log").read_text(encoding="utf-8") == (
        "profile_worker_task_failed\n"
    )
    assert _with_notes(failed.value).endswith(f"\n  sandbox logs retained at {kept}")


def test_a_passing_sandbox_keeps_nothing(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path / "sandbox")
    retained = tmp_path / "retained"

    with _logs_retained_on_failure(sandbox, retained, "how-to/page"):
        pass

    assert not retained.exists()
