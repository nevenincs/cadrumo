"""The copied current fixture remains a real isolated native-worker entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from cadrumo.tests.audited_process import run_audited_process
from dev._paths import REPO_ROOT

from ..modelo_runtime_benchmark import copy_instrumented_worker

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


@pytest.mark.parametrize("profile", (False, True), ids=("timing-only", "first-decode-profile"))
def test_current_copied_fixture_reaches_its_real_isolated_argument_parser(tmp_path: Path, profile: bool) -> None:
    child = copy_instrumented_worker(tmp_path, profile_first_decode=profile)
    result = run_audited_process(
        [sys.executable, "-I", str(child), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=None,
    )

    assert result.returncode == 0, result.stderr
    assert isinstance(result.stdout, str)
    assert "--storage-root" in result.stdout
    assert "--worker-id" in result.stdout
    assert "--parent-pid" in result.stdout


def test_contained_process_retains_live_schema_counts_without_scope_teardown(tmp_path: Path) -> None:
    # The real native owner may contain its worker without exiting composition.
    # Leave this actual observer scope abruptly after coarse completions; no
    # native business fixture or substituted calculation implementation is used.
    script = "\n".join(
        [
            "import os, sys",
            "from pathlib import Path",
            "from pydantic import BaseModel",
            "from cadrumo.core.models import STRICT_FROZEN_CONFIG",
            "from cadrumo.application.operations import registry_schema_validation as schema",
            "from dev.ci.modelo_runtime_benchmark import RuntimeBenchmarkRecorder, observe_runtime_boundaries",
            "class Contract(BaseModel):",
            "    model_config = STRICT_FROZEN_CONFIG",
            "    count: int",
            "recorder = RuntimeBenchmarkRecorder(Path(sys.argv[1]), role='worker')",
            "with observe_runtime_boundaries(recorder):",
            "    for boundary in ('catalogue.load', 'catalogue.load_revisioned', 'modelo.calculate', 'modelo.export'):",
            "        with recorder.measure(boundary):",
            "            schema.strict_model_json_schema(Contract)",
            "    os._exit(0)",
        ]
    )
    result = run_audited_process(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=None,
    )

    assert result.returncode == 0, result.stderr
    metrics = tuple(tmp_path.glob("worker-*.jsonl"))
    assert len(metrics) == 1
    records = [TypeAdapter(dict[str, object]).validate_json(line) for line in metrics[0].read_bytes().splitlines()]
    snapshots = [row for row in records if row["event"] == "aggregate"]
    assert len(snapshots) == 4
    counts: list[int] = []
    for snapshot in snapshots:
        assert snapshot["semantics"] == "cumulative"
        boundaries = TypeAdapter(dict[str, dict[str, float | int]]).validate_python(snapshot["boundaries"])
        count = boundaries["operations.strict_schema"]["calls"]
        assert isinstance(count, int)
        counts.append(count)
    assert counts == [1, 2, 3, 4]
    assert records[-1]["event"] == "aggregate"
