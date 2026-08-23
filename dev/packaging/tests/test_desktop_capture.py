"""Real-behavior tests for the Claude Desktop capture harness logic.

Every seam that does not require a launched Claude Desktop is exercised against
real files and real parsing: profile seeding + isolation, MCP-log telemetry
extraction (including the result-success gate), the bounded fail-closed retry
loop (driven by a scripted attempt callable), the seeded-secret leak scan, and
the Appx package parse. The real launched-app CDP drive is the integration
surface and is not covered here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .. import desktop_capture as dc

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_seed_auth_state_copies_only_curated_paths_and_isolates(tmp_path: Path) -> None:
    """Seeding copies the curated auth set and nothing else crosses over."""
    source = tmp_path / "source-profile"
    _write(source / "config.json", '{"oauth:tokenCacheV2": "djEwSECRETTOKENVALUE_padding_padding_padding"}')
    _write(source / "Local State", "local-state-bytes")
    _write(source / "Network" / "Cookies", "cookie-bytes")
    _write(source / "Local Storage" / "leveldb" / "000001.log", "ls-bytes")
    # State that MUST NOT be seeded (prior conversations / caches / other extensions):
    _write(source / "conversations.db", "PRIOR CONVERSATION HISTORY")
    _write(source / "Claude Extensions" / "some.other.ext" / "manifest.json", "{}")

    target = tmp_path / "isolated"
    seeded = dc.seed_auth_state(source, target)

    assert "config.json" in seeded
    assert (target / "config.json").exists()
    assert (target / "Local State").exists()
    assert (target / "Network" / "Cookies").exists()
    assert (target / "Local Storage" / "leveldb" / "000001.log").exists()
    # The clean-environment guarantee: nothing outside the curated set crosses over.
    assert not (target / "conversations.db").exists()
    assert not (target / "Claude Extensions").exists()


def test_seed_auth_state_refuses_nested_target(tmp_path: Path) -> None:
    """A target inside the source profile is refused (no self-nesting)."""
    source = tmp_path / "profile"
    _write(source / "config.json", "{}")
    with pytest.raises(dc.DesktopCaptureError, match="independent"):
        dc.seed_auth_state(source, source / "child")


def test_seed_auth_state_refuses_without_config(tmp_path: Path) -> None:
    """A source profile with no config.json cannot seed session auth."""
    source = tmp_path / "profile"
    _write(source / "Local State", "x")
    with pytest.raises(dc.DesktopCaptureError, match=r"config\.json"):
        dc.seed_auth_state(source, tmp_path / "iso")


def test_seed_extension_provisions_single_extension(tmp_path: Path) -> None:
    """The extension payload and its settings record land under the isolated profile."""
    ext_source = tmp_path / "ext" / "local.mcpb.cadrumo"
    _write(ext_source / "manifest.json", '{"version": "0.2.1"}')
    _write(ext_source / "src" / "server.py", "print('server')")
    target = tmp_path / "iso"
    target.mkdir()

    dest = dc.seed_extension(target, ext_source, settings_json='{"isEnabled": true}')

    assert dest == target / "Claude Extensions" / "local.mcpb.cadrumo"
    assert (dest / "src" / "server.py").exists()
    settings = target / "Claude Extensions Settings" / "local.mcpb.cadrumo.json"
    assert json.loads(settings.read_text(encoding="utf-8"))["isEnabled"] is True


def test_parse_mcp_server_log_extracts_real_transport_call() -> None:
    """A telemetry JSON line with a genuine transport is a real served call."""
    log = "\n".join(
        [
            "[info] Server started and connected successfully",
            "not json at all",
            json.dumps({"transport": "subprocess", "executable": "C:/env/aeat.exe", "tool": "cadrumo_whoami"}),
            "[info] trailing line",
        ],
    )
    observation = dc.parse_mcp_server_log(log)
    assert observation.connected is True
    assert observation.served_by_real_transport is True
    assert observation.calls[0].tool_name == "cadrumo_whoami"
    assert observation.calls[0].transport == "subprocess"


def test_parse_mcp_server_log_no_call_is_not_served() -> None:
    """A connected server with zero telemetry calls proves no tool call."""
    observation = dc.parse_mcp_server_log("[info] Successfully connected\n[info] waiting")
    assert observation.connected is True
    assert observation.served_by_real_transport is False
    assert observation.calls == ()


def test_parse_mcp_server_log_ignores_bad_transport_value() -> None:
    """An unknown transport token is not a genuine served call."""
    observation = dc.parse_mcp_server_log(json.dumps({"transport": "bogus", "executable": ""}))
    assert observation.served_by_real_transport is False


def test_errored_call_is_dispatched_but_not_successful() -> None:
    """A dispatched call whose RESULT errored must not count as a success.

    This is the gate the prior smoke lacked: connected+dispatched recorded
    "passed" even when the tool result was an error.
    """
    log = json.dumps({"transport": "inprocess", "executable": "x", "is_error": True, "tool": "cadrumo_whoami"})
    observation = dc.parse_mcp_server_log(log)
    assert observation.served_by_real_transport is True  # it WAS dispatched
    assert observation.successful_calls == ()  # but it did NOT succeed


def test_error_status_call_is_not_successful() -> None:
    """An error-like status string disqualifies the call even without is_error."""
    log = json.dumps({"transport": "subprocess", "executable": "x", "status": "error"})
    observation = dc.parse_mcp_server_log(log)
    assert observation.successful_calls == ()


def test_clean_call_is_successful() -> None:
    """A genuinely served call with a clean result counts as a success."""
    log = json.dumps({"transport": "subprocess", "executable": "x", "is_error": False, "status": "ok"})
    observation = dc.parse_mcp_server_log(log)
    assert len(observation.successful_calls) == 1


def test_capture_with_retries_succeeds_on_second_attempt() -> None:
    """The loop retries a no-tool-call attempt and stops at the first success."""

    def perform(index: int) -> dc.AttemptLog:
        ok = index == 2  # the model does not tool-call on attempt 1
        return dc.AttemptLog(attempt=index, ok=ok, detail=f"attempt {index}")

    result = dc.capture_with_retries(perform, attempts=3)
    assert result.ok is True
    assert len(result.attempts) == 2  # stops at the first success


def test_capture_with_retries_exhausts_fail_closed() -> None:
    """Exhaustion returns a non-ok result carrying every attempt's diagnostics."""

    def perform(index: int) -> dc.AttemptLog:
        return dc.AttemptLog(attempt=index, ok=False, detail="no tool call")

    result = dc.capture_with_retries(perform, attempts=3)
    assert result.ok is False
    assert len(result.attempts) == 3


def test_capture_with_retries_logs_raised_transient_attempt() -> None:
    """A transient app-state failure is logged as a failed attempt and retried."""

    def perform(index: int) -> dc.AttemptLog:
        if index == 1:
            raise dc.DesktopCaptureError("CDP connect failed")
        return dc.AttemptLog(attempt=index, ok=True, detail="ok")

    result = dc.capture_with_retries(perform, attempts=3)
    assert result.ok is True
    assert "attempt raised" in result.attempts[0].detail


def test_capture_with_retries_propagates_a_harness_defect() -> None:
    """A programming error is NOT retried, so it cannot read as model flakiness.

    The complement of the transient case above: retrying a deterministic bug
    would burn further app launches and record it in the evidence indistinguishably
    from a model that declined to tool-call. It must surface on attempt one.
    """
    calls: list[int] = []

    def perform(index: int) -> dc.AttemptLog:
        calls.append(index)
        raise AttributeError("'McpLogObservation' object has no attribute 'successful_call'")

    with pytest.raises(AttributeError):
        dc.capture_with_retries(perform, attempts=3)
    assert calls == [1], "a harness defect must not be retried"


def test_collect_seed_secrets_and_leak_scan_refuses(tmp_path: Path) -> None:
    """A retained artifact carrying a seeded secret is deleted and refused."""
    secret = "djEw" + "S" * 40
    config = _write(tmp_path / "profile" / "config.json", json.dumps({"oauth:tokenCacheV2": secret, "locale": "en"}))
    secrets = dc.collect_seed_secrets(config)
    assert secret in secrets
    assert "en" not in secrets  # short values are not secrets

    logs = tmp_path / "logs"
    leaking = _write(logs / "attempt.log", f"debug dump ... token={secret} ...")
    _write(logs / "clean.log", "no secret here")
    with pytest.raises(dc.DesktopCaptureError, match="leaked"):
        dc.scan_for_secret_leak(logs, secrets)
    assert not leaking.exists()  # the leaking file is deleted


def test_leak_scan_passes_clean_tree(tmp_path: Path) -> None:
    """A clean artifact tree passes the leak scan untouched."""
    logs = tmp_path / "logs"
    _write(logs / "attempt.log", "connected=True successful=1")
    dc.scan_for_secret_leak(logs, ("djEw" + "S" * 40,))  # no raise


def test_parse_appx_package_builds_executable() -> None:
    """The Appx record parse resolves the FullTrust executable and AUMID."""
    document = {
        "Version": "1.22209.3.0",
        "InstallLocation": "C:/Program Files/WindowsApps/Claude_1.22209.3.0_x64__pzs8sxrjxfjjc",
        "PackageFamilyName": "Claude_pzs8sxrjxfjjc",
    }
    package = dc.parse_appx_package(document, state_dir=Path("C:/state"))
    assert package.version == "1.22209.3.0"
    assert package.aumid == "Claude_pzs8sxrjxfjjc!Claude"
    assert package.executable.name == "Claude.exe"


def test_parse_appx_package_refuses_wrong_family() -> None:
    """A foreign package family is refused rather than silently driven."""
    with pytest.raises(dc.DesktopCaptureError, match="family"):
        dc.parse_appx_package(
            {"Version": "1.0", "InstallLocation": "C:/x", "PackageFamilyName": "Other_abc"},
            state_dir=Path("C:/state"),
        )


def test_extract_target_value_matches_separator_variants() -> None:
    """The grounded value matches across thousands-separator conventions."""
    assert dc.extract_target_value("The cuota is 23000.00 euros", target_value="23000.00")
    assert dc.extract_target_value("resultado: 23,000.00", target_value="23000.00")
    assert dc.extract_target_value("importe 23.000,00 EUR", target_value="23000.00")
    assert dc.extract_target_value("importe 23 000,00 EUR", target_value="23000.00")
    assert not dc.extract_target_value("nothing relevant here", target_value="23000.00")


def test_extract_target_value_refuses_larger_or_embedded_numeric_replies() -> None:
    """A capture proves the exact requested value, never a larger or embedded digit sequence."""
    target_value = "23000.00"

    assert not dc.extract_target_value("importe 123000.00 EUR", target_value=target_value)
    assert not dc.extract_target_value("importe 1,230,000.00 EUR", target_value=target_value)
    assert not dc.extract_target_value("x23000.00y", target_value=target_value)


def test_extract_target_value_refuses_distinct_values_with_the_same_digit_sequence() -> None:
    """Punctuation removal must not make different numeric values satisfy the oracle."""
    target_value = "23000.00"

    assert not dc.extract_target_value("importe 2300000 EUR", target_value=target_value)
    assert not dc.extract_target_value("importe 2300.000 EUR", target_value=target_value)
    assert not dc.extract_target_value("importe 2,300,000 EUR", target_value=target_value)
    assert not dc.extract_target_value("importe 2 3000 EUR", target_value=target_value)
