"""Real-behaviour CLI tests for ``aeat config profile capabilities`` show/set.

Exercises the operator surface end to end against the real Typer app and real
persistence in an isolated storage root: setting a capability writes a profile
fact, and ``show`` resolves it back with its source. No mocks.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ....application.user_profile import CapabilitySource, profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core import ServiceCapability
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("00000000-0000-4000-8000-000000000000"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="00000000-0000-4000-8000-000000000000")
        )
        yield


def _show() -> dict[str, Any]:
    result = invoke_cached_cli(["--format", "json", "config", "profile", "capabilities", "show"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)["result"]["capabilities"]
    return {row["capability"]: row for row in rows}


def test_show_reports_every_capability_with_default_posture() -> None:
    rows = _show()
    assert set(rows) == {"cloud_evidence_upload", "llm_vision", "google_export"}
    # Defaults: cloud off (global), vision/google on (default).
    assert rows["cloud_evidence_upload"]["enabled"] is False
    assert rows["llm_vision"]["enabled"] is True
    assert rows["google_export"]["enabled"] is True


@pytest.mark.parametrize(
    ("capability", "source"),
    [("", CapabilitySource.DEFAULT), ("bogus", CapabilitySource.DEFAULT), (ServiceCapability.LLM_VISION, "bogus")],
)
def test_capability_payload_refuses_unknown_capability_or_source(
    capability: ServiceCapability | str,
    source: CapabilitySource | str,
) -> None:
    """The capability result uses the resolver's closed identifiers unchanged."""

    from .._config._capabilities_payloads import CapabilityRowPayload

    with pytest.raises(ValidationError):
        CapabilityRowPayload(capability=capability, enabled=True, source=source, reason="resolver result")


def test_set_disables_a_capability_and_show_reflects_it() -> None:
    setres = invoke_cached_cli(
        ["--format", "json", "config", "profile", "capabilities", "set", "llm_vision", "off"],
    )
    assert setres.exit_code == 0, setres.output
    payload = json.loads(setres.output)["result"]
    assert payload["capability"] == "llm_vision" and payload["enabled"] is False

    rows = _show()
    assert rows["llm_vision"]["enabled"] is False
    assert rows["llm_vision"]["source"] == "profile"


def test_config_check_reports_capabilities_and_dependencies() -> None:
    # Opt out of llm_vision so the report is deterministic regardless of whether a
    # real Ollama is running in the test environment (no opted-in dependency gap).
    off = invoke_cached_cli(["config", "profile", "capabilities", "set", "llm_vision", "off"])
    assert off.exit_code == 0, off.output

    result = invoke_cached_cli(["--format", "json", "config", "check"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["ok"] is True
    assert payload["issues"] == []
    caps = {c["capability"]: c for c in payload["capabilities"]}
    assert set(caps) == {"cloud_evidence_upload", "llm_vision", "google_export"}
    assert caps["llm_vision"]["enabled"] is False
    services = {d["service"] for d in payload["dependencies"]}
    assert "ollama-vision" in services
    assert "playwright-chromium" in services
    assert any(s.startswith("llm-provider:") for s in services)
    # The doctor reports every capability-gated optional extra's importability.
    assert {"extra:google", "extra:browser", "extra:anthropic"} <= services


def test_config_check_flags_opted_in_capability_with_missing_dependency() -> None:
    # llm_vision is on by default; point Ollama at a closed port so the dependency
    # is reliably unavailable. The doctor must surface the gap and exit non-zero.
    with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
        result = invoke_cached_cli(["--format", "json", "config", "check"])
    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)["result"]
    assert payload["ok"] is False
    assert any("llm_vision is on" in issue for issue in payload["issues"])


@pytest.mark.parametrize(
    "argv",
    [
        ["config", "google", "sync", "calc", "export", "--modelo", "303", "--period", "1T", "--year", "2025"],
        ["config", "google", "sync", "calc", "verify", "--modelo", "303", "--period", "1T", "--year", "2025"],
        ["config", "google", "sync", "push"],
        ["config", "google", "sync", "probe", "--no-read-only"],
    ],
    ids=["calc-export", "calc-verify", "push", "probe-write"],
)
def test_every_google_write_verb_refuses_when_google_export_disabled(argv: list[str]) -> None:
    """Every Google-write CLI leaf is gated on google_export, not just `export`.

    With the capability off, each Drive/Sheets
    write verb refuses with the capability message *before* any Google call.
    """
    off = invoke_cached_cli(["config", "profile", "capabilities", "set", "google_export", "off"])
    assert off.exit_code == 0, off.output

    result = invoke_cached_cli(argv)
    assert result.exit_code != 0, result.output
    combined = result.output + str(result.exception or "")
    assert "Google export is disabled" in combined, combined


def test_set_enables_cloud_upload_via_profile_opt_in() -> None:
    setres = invoke_cached_cli(
        ["config", "profile", "capabilities", "set", "cloud_evidence_upload", "on"],
    )
    assert setres.exit_code == 0, setres.output
    rows = _show()
    assert rows["cloud_evidence_upload"]["enabled"] is True
    assert rows["cloud_evidence_upload"]["source"] == "profile"
