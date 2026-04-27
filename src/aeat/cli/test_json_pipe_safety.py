"""Subprocess pipe-safety tests for the real ``aeat`` entrypoint."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ..config import PROJECT_ROOT
from ..deadlines import AutonomoProfile, IVARegime

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

_CLI_EXE = Path(sys.executable).with_name("aeat.exe" if os.name == "nt" else "aeat")
_JQ_EXE = shutil.which("jq")


def _prepare_workflow_env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    profile = AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")

    inputs_path = tmp_path / "inputs.json"
    inputs_path.write_text(json.dumps({"01": 12500, "02": 3500, "05": 400, "06": 0}), encoding="utf-8")

    env["AEAT_DEFAULT_PROFILE_PATH"] = str(profile_path)
    env["AEAT_WORKFLOW_DRAFT_INPUTS_PATH"] = str(inputs_path)
    env["AEAT_WORKFLOW_RUNS_DIR"] = str(tmp_path / "runs")
    env["AEAT_SUBMISSIONS_DIR"] = str(tmp_path / "submissions")
    env["AEAT_SUBMISSION_BROWSER_TRACE_DIR"] = str(tmp_path / "traces")
    return env


def _run_jq_pipeline(
    argv: list[str],
    jq_filter: str,
    *,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], str]:
    assert _JQ_EXE is not None, "jq must be installed for pipe-safety tests"
    producer = subprocess.Popen(  # noqa: S603
        [str(_CLI_EXE), *argv],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert producer.stdout is not None
    consumer = subprocess.run(  # noqa: S603
        [_JQ_EXE, "-r", jq_filter],
        cwd=PROJECT_ROOT,
        env=env,
        stdin=producer.stdout,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    producer.stdout.close()
    stderr = producer.stderr.read() if producer.stderr is not None else ""
    returncode = producer.wait()
    assert returncode == 0, stderr
    return consumer, stderr


def test_models_root_json_pipeline_survives_jq() -> None:
    """`aeat --json modelos show 303 | jq` should read clean stdout only."""

    consumer, stderr = _run_jq_pipeline(["--json", "modelos", "show", "303"], ".result.code")
    assert consumer.returncode == 0, consumer.stderr
    assert consumer.stdout.strip() == "303"
    assert stderr == ""


def test_portals_root_json_pipeline_survives_jq_with_non_ascii() -> None:
    """`aeat --json portals show ... | jq` should preserve UTF-8 text."""

    consumer, stderr = _run_jq_pipeline(["--json", "portals", "show", "portal_clave_idp_root"], ".result.label.hu")
    assert consumer.returncode == 0, consumer.stderr
    assert "Cl@ve" in consumer.stdout
    assert "közszolgálati" in consumer.stdout
    assert stderr == ""


def test_submission_root_json_pipeline_survives_jq() -> None:
    """`aeat --json submission check-nif ... | jq` should resolve the canonical value."""

    consumer, stderr = _run_jq_pipeline(["--json", "submission", "check-nif", "X1234567L"], ".result.canonical")
    assert consumer.returncode == 0, consumer.stderr
    assert consumer.stdout.strip() == "X1234567L"
    assert stderr == ""


def test_workflow_root_json_pipeline_survives_jq(tmp_path: Path) -> None:
    """`aeat --json workflow next --no-sync | jq` should remain pipe-safe."""

    consumer, stderr = _run_jq_pipeline(
        ["--json", "workflow", "next", "--no-sync"],
        ".result.final_stage",
        env=_prepare_workflow_env(tmp_path),
    )
    assert consumer.returncode == 0, consumer.stderr
    assert consumer.stdout.strip() == "ABORTED"
    assert stderr == ""


def test_json_output_reconfigures_stdout_to_utf8_under_cp1252(tmp_path: Path) -> None:
    """Machine mode should stay UTF-8 even when `PYTHONIOENCODING` asks for cp1252."""

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    result = subprocess.run(  # noqa: S603
        [str(_CLI_EXE), "--json", "portals", "show", "portal_clave_idp_root"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stderr == b""
    payload = json.loads(result.stdout.decode("utf-8"))
    assert payload["result"]["label"]["hu"].endswith("azonosító")
    assert payload["result"]["purpose_es"].startswith("Página raíz")


def test_json_failure_path_writes_only_stderr() -> None:
    """Invalid machine-mode commands must keep stdout empty and serialize stderr only."""

    result = subprocess.run(  # noqa: S603
        [str(_CLI_EXE), "--json", "submission", "check-nif", "X1234567Z"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["error"]["category"] == "REFUSED"


def test_filing_reconcile_json_failure_writes_only_stderr(tmp_path: Path) -> None:
    """`aeat --json filing reconcile ...` must keep failure prose off stdout."""

    env = dict(os.environ)
    env["AEAT_DRAFTS_DIR"] = str(tmp_path / "missing-drafts")
    result = subprocess.run(  # noqa: S603
        [str(_CLI_EXE), "--json", "filing", "reconcile", "missing-draft"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["error"]["category"] == "REFUSED"
    assert payload["error"]["context"]["drafts_dir"].endswith("missing-drafts")
