"""Real-behavior coverage for the warm in-process CLI runtime.

Exercises :mod:`cadrumo_harness.mcp._inprocess` against the real ``aeat`` Typer app,
the real registry and real filesystem state. The compiled-cache directory is
isolated so a user's pre-existing development cache cannot become test authority.
The runtime's contract is that it runs the genuine CLI pipeline in-process and
returns a completed run whose captured stdout parses to the same JSON envelope
the subprocess transport would emit; the byte-for-byte parity against the
subprocess transport itself is proven separately in
``test_inprocess_envelope_parity.py``.
"""

from __future__ import annotations

import json

import pytest

from .._call_runtime import CallTier
from .._inprocess import (
    CompletedCliRun,
    dispatch_verb_in_process,
    parse_cli_envelope,
    run_cli_in_process,
    tier_runs_in_process,
)
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _fresh_registry_cache(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Run the real bundled registry against a fresh canonical compiled cache."""
    from cadrumo.core.config import reset_settings_cache
    from cadrumo.domain.calculations.registry import clear_fingerprint_cache
    from cadrumo.domain.calculations.registry._authority import _load_authority
    from cadrumo.domain.calculations.registry._loader import _load_registry_tree_cached

    monkeypatch.setenv("CADRUMO_REGISTRY_DISK_CACHE_DIR", str(tmp_path / "registry-cache"))
    reset_settings_cache()
    clear_fingerprint_cache()
    _load_registry_tree_cached.cache_clear()
    _load_authority.cache_clear()  # type: ignore[attr-defined]
    yield
    _load_authority.cache_clear()  # type: ignore[attr-defined]
    _load_registry_tree_cached.cache_clear()
    clear_fingerprint_cache()
    reset_settings_cache()


def test_live_tier_stays_on_subprocess_other_tiers_run_in_process() -> None:
    assert tier_runs_in_process(CallTier.READ) is True
    assert tier_runs_in_process(CallTier.MUTATE) is True
    # The AEAT-sede / open-world family keeps its supervised subprocess for the
    # process-tree kill and the operator progress sink.
    assert tier_runs_in_process(CallTier.LIVE) is False


def test_run_cli_in_process_emits_a_read_only_success_envelope() -> None:
    # ``app registry inspect`` is a read-only verb that needs no active profile,
    # so it
    # exercises the whole in-process pipeline - root callback, verb body, and the
    # shared envelope emitter - without touching encrypted bucket state.
    run = run_cli_in_process(["--format", "json", "app", "registry", "inspect"], acquire_timeout_s=30.0)
    assert run is not None
    assert run.returncode == 0
    envelope, is_error = parse_cli_envelope(run)
    assert is_error is False
    assert envelope["command"] == "registry.inspect"
    assert envelope["status"] in {"success", "warning"}
    assert "result" in envelope
    # Nothing may have leaked onto the captured stderr on a clean read.
    assert run.stderr.strip() == ""


def test_dispatch_verb_in_process_reconstructs_the_argv_from_the_schema() -> None:
    descriptor = next(
        candidate for candidate in build_tool_descriptors() if candidate.command_key == "registry.inspect"
    )
    run = dispatch_verb_in_process(descriptor.verb_schema, {}, acquire_timeout_s=30.0)
    assert run is not None
    envelope, is_error = parse_cli_envelope(run)
    assert is_error is False
    assert envelope["command"] == "registry.inspect"


def test_parse_cli_envelope_rejects_obsolete_success_envelope_version() -> None:
    run = CompletedCliRun(
        stdout='{"schema_version": "1", "command": "registry.inspect", "status": "success", "result": {}, "notices": []}',
        stderr="",
        returncode=0,
    )
    envelope, is_error = parse_cli_envelope(run)
    assert is_error is True
    assert envelope["status"] == "error"
    assert "schema_version" in str(envelope["raw"])


def test_parse_cli_envelope_reads_error_document_from_stderr() -> None:
    run = CompletedCliRun(
        stdout="",
        stderr=(
            '{"schema_version":"2","command":"modelo.export","active_profile":null,'
            '"status":"error","error":{"code":"REFUSED_TEST","category":"refused",'
            '"message":"refused","action":null,"retryable":false,"runbook_id":null,'
            '"context":null,"trace_id":null},"notices":[]}'
        ),
        returncode=2,
    )
    envelope, is_error = parse_cli_envelope(run)
    assert is_error is True
    assert envelope["command"] == "modelo.export"


@pytest.mark.parametrize(
    "body",
    (
        '{"schema_version":"2","command":"registry.inspect","status":"success","result":{},"notices":[]}',
        '{"schema_version":"2","command":"registry.inspect","active_profile":null,"status":"unknown","result":{},"notices":[]}',
    ),
    ids=("missing-envelope-spine", "unknown-status"),
)
def test_parse_cli_envelope_rejects_malformed_success_documents(body: str) -> None:
    run = CompletedCliRun(stdout=body, stderr="", returncode=0)

    envelope, is_error = parse_cli_envelope(run)

    assert is_error is True
    assert envelope["status"] == "error"


def test_parse_cli_envelope_rejects_a_real_registered_result_with_wrong_shape() -> None:
    """The MCP parser cannot admit a result shape the CLI graph rejects."""
    run = run_cli_in_process(["--format", "json", "app", "registry", "inspect"], acquire_timeout_s=30.0)
    assert run is not None
    document = json.loads(run.stdout)
    document["result"] = []

    envelope, is_error = parse_cli_envelope(
        CompletedCliRun(stdout=json.dumps(document), stderr="", returncode=0),
    )

    assert is_error is True
    assert envelope["status"] == "error"


def test_parse_cli_envelope_non_zero_exit_marks_error_even_on_success_body() -> None:
    run = CompletedCliRun(
        stdout='{"status": "success"}',
        stderr="",
        returncode=1,
    )
    _, is_error = parse_cli_envelope(run)
    assert is_error is True


def test_parse_cli_envelope_non_json_body_becomes_a_typed_error() -> None:
    run = CompletedCliRun(stdout="Traceback (most recent call last): boom", stderr="", returncode=1)
    envelope, is_error = parse_cli_envelope(run)
    assert is_error is True
    assert envelope["status"] == "error"
    assert "boom" in str(envelope["raw"])
