"""The supervised call runtime bounds and terminates a hung CLI call.

Proves the contract with REAL subprocesses (no
mocks): a fast command completes and reports its output; a command that exceeds
its tier ceiling is terminated - promptly, not waited out - and reports
``timed_out``; a process that spawns a child is killed as a tree, not left with a
stranded grandchild; and the timeout tier is derived from the command
annotations. The localized refusal envelope is asserted through the real ``tr``
catalogue.
"""

from __future__ import annotations

import sys
import time

import pytest

from .._call_runtime import (
    CallTier,
    SupervisedResult,
    run_supervised,
    tier_for,
    timeout_seconds,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _typed_error_envelope(envelope: dict[str, object]) -> dict[str, object]:
    """Return the validated error payload as a string-keyed mapping."""
    error = envelope["error"]
    if not isinstance(error, dict) or not all(isinstance(key, str) for key in error):
        raise AssertionError("validated error envelope must carry a string-keyed error object")
    return {key: value for key, value in error.items() if isinstance(key, str)}


def test_tier_is_derived_from_annotations() -> None:
    assert tier_for(read_only=True, open_world=False) is CallTier.READ
    assert tier_for(read_only=False, open_world=False) is CallTier.MUTATE
    # Open-world (AEAT sede) always gets the live tier, read or write.
    assert tier_for(read_only=True, open_world=True) is CallTier.LIVE
    assert tier_for(read_only=False, open_world=True) is CallTier.LIVE
    # The live ceiling is the most generous (a portal pull runs for minutes).
    assert timeout_seconds(CallTier.LIVE) > timeout_seconds(CallTier.MUTATE) > timeout_seconds(CallTier.READ)


def test_mutate_ceiling_has_headroom_beyond_the_observed_cold_client_cutoff() -> None:
    # An installed Claude Desktop MCPB run reached 121.366 seconds before the
    # former 120-second server ceiling killed modelo.work.create. Keep the
    # local-mutation tier at the next established oracle ceiling rather than
    # barely clearing one observed machine.
    assert timeout_seconds(CallTier.MUTATE) == 180.0


def test_a_fast_command_completes_without_timing_out() -> None:
    result = run_supervised(
        [sys.executable, "-c", "print('ok')"],
        timeout_s=30.0,
        encoding="utf-8",
    )
    assert isinstance(result, SupervisedResult)
    assert result.executable == sys.executable
    assert result.timed_out is False
    assert result.returncode == 0
    assert result.stdout.strip() == "ok"


def test_a_hung_command_is_terminated_promptly_not_waited_out() -> None:
    started = time.monotonic()
    result = run_supervised(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        timeout_s=1.0,
        encoding="utf-8",
    )
    elapsed = time.monotonic() - started
    assert result.timed_out is True
    # The call returned in seconds, not the 60s the child would have slept: proof
    # the process was killed at the ceiling rather than run to completion.
    assert elapsed < 20.0


def test_a_child_spawning_process_is_killed_as_a_tree() -> None:
    # The parent spawns a long-sleeping grandchild then sleeps itself; on timeout
    # the whole tree must be signalled. We assert the call returns promptly (the
    # tree was terminated) rather than blocking on the grandchild.
    script = (
        "import subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "time.sleep(60)"
    )
    started = time.monotonic()
    result = run_supervised([sys.executable, "-c", script], timeout_s=1.0, encoding="utf-8")
    elapsed = time.monotonic() - started
    assert result.timed_out is True
    assert elapsed < 20.0


def test_timeout_refusal_is_localized_and_names_the_tier() -> None:
    from cadrumo.core.json_contract import ENVELOPE_SCHEMA_VERSION, validate_registered_envelope_document

    from .._transport import _cli_resolution_refusal_envelope, _timeout_refusal_envelope

    envelope = _timeout_refusal_envelope(command_key="app.live.expedientes.pull", tier=CallTier.LIVE, timeout_s=420.0)
    validated = validate_registered_envelope_document(envelope)
    assert validated == envelope
    assert validated["schema_version"] == ENVELOPE_SCHEMA_VERSION
    assert validated["command"] == "app.live.expedientes.pull"
    assert validated["status"] == "error"
    error = _typed_error_envelope(validated)
    assert error["code"] == "mcp.transport.timeout"
    assert error["context"] == {"tier": "live", "timeout_seconds": "420", "timed_out": "true"}
    refusal = error["message"]
    assert isinstance(refusal, str)
    # The refusal names the command, the tier, and the ceiling.
    assert "app.live.expedientes.pull" in refusal
    assert "live" in refusal
    assert "420" in refusal

    installation = _cli_resolution_refusal_envelope(
        command_key="registry.inspect",
        error=FileNotFoundError("Installed Cadrumo CLI executable is missing"),
    )
    validated_installation = validate_registered_envelope_document(installation)
    assert validated_installation == installation
    assert validated_installation["command"] == "registry.inspect"
    installation_error = _typed_error_envelope(validated_installation)
    assert installation_error["code"] == "mcp.transport.installation_incomplete"
    assert installation_error["context"] == {"installation_incomplete": "true"}


def test_serving_limiter_is_a_settings_sized_singleton() -> None:
    from .._call_runtime import serving_capacity_limiter
    from .._settings import load_mcp_settings

    limiter = serving_capacity_limiter()
    # The explicit cap is the settings value, not the anyio default of 40.
    assert limiter.total_tokens == load_mcp_settings().cadrumo_mcp_serving_concurrency
    assert limiter.total_tokens != 40
    # One limiter lives for the whole server session; repeated calls reuse it.
    assert serving_capacity_limiter() is limiter


def test_serving_limiter_caps_concurrent_off_loop_dispatch() -> None:
    import threading
    from functools import partial

    import anyio
    from anyio.to_thread import run_sync

    from .._call_runtime import serving_capacity_limiter

    limiter = serving_capacity_limiter()
    cap = int(limiter.total_tokens)
    lock = threading.Lock()
    live = 0
    observed_peak = 0

    def _busy() -> None:
        nonlocal live, observed_peak
        with lock:
            live += 1
            observed_peak = max(observed_peak, live)
        # Hold the slot long enough that more than ``cap`` tasks would overlap if
        # the limiter did not bound them.
        time.sleep(0.15)
        with lock:
            live -= 1

    async def _drive() -> None:
        async with anyio.create_task_group() as group:
            for _ in range(cap * 3):
                group.start_soon(partial(run_sync, _busy, limiter=limiter))

    anyio.run(_drive)
    # The cap binds: never more than ``cap`` ran at once, and with three times the
    # cap queued the limit was actually reached (not merely never exceeded).
    assert observed_peak == cap


_TRANSPORT_ERROR_CONTEXT_CONTRACT: dict[str, frozenset[str]] = {
    "mcp.transport.timeout": frozenset({"tier", "timeout_seconds", "timed_out"}),
    "mcp.transport.installation_incomplete": frozenset({"installation_incomplete"}),
}
"""Every context key each transport refusal may carry, keyed by error code.

The MCP transport has no writer-level redaction the way the CLI does, so this
document leaves the process exactly as built. That is affordable only while its
context is transport-level -- how the call was dispatched, never what it was
about -- and nothing but this gate keeps it that way.
"""


def _transport_error_context_keys() -> dict[str, frozenset[str]]:
    """Return each ``_transport_error_envelope`` call's code and context keys.

    Read from the source rather than by calling the builders, so a THIRD caller
    added later is seen too -- exercising the two known ones would keep passing
    while a new refusal quietly widened the surface.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "_transport.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    found: dict[str, frozenset[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", "") != "_transport_error_envelope":
            continue
        keywords = {kw.arg: kw.value for kw in node.keywords}
        code_node, context_node = keywords.get("code"), keywords.get("context")
        assert isinstance(code_node, ast.Constant), f"code must be a literal, got {ast.dump(code_node or ast.Pass())}"
        assert isinstance(context_node, ast.Dict), "context must be a dict literal so its keys are auditable here"
        keys: set[str] = set()
        for key in context_node.keys:
            assert isinstance(key, ast.Constant) and isinstance(key.value, str), "context keys must be string literals"
            keys.add(key.value)
        found[str(code_node.value)] = frozenset(keys)
    return found


def test_transport_error_context_keys_stay_transport_level() -> None:
    """Widening the un-redacted MCP error surface must red rather than pass.

    This document is emitted without redaction, and it is safe because its
    context carries a tier name, an integer and two flags -- nothing operator- or
    taxpayer-derived. That is a property of today's content, not a constraint, so
    this gate makes it one: adding a key fails here, and the author meets the
    contract at the moment they would otherwise silently widen the surface.
    """
    found = _transport_error_context_keys()

    # Anti-vacuity floor: a rename or refactor that empties the scan would make
    # every assertion below trivially true, which is the failure mode a gate of
    # this shape dies of.
    assert len(found) == len(_TRANSPORT_ERROR_CONTEXT_CONTRACT), (
        f"expected {len(_TRANSPORT_ERROR_CONTEXT_CONTRACT)} _transport_error_envelope call sites, found "
        f"{len(found)}: {sorted(found)}. A new refusal must declare its context keys in the contract above."
    )
    assert found == _TRANSPORT_ERROR_CONTEXT_CONTRACT, (
        "MCP transport refusal context keys drifted from the declared contract. This surface is emitted "
        "WITHOUT redaction, so a new key carrying operator- or taxpayer-derived data is a disclosure, not a "
        f"documentation lapse. Found {found}, declared {_TRANSPORT_ERROR_CONTEXT_CONTRACT}."
    )


def test_cli_resolution_refusal_does_not_leak_the_installation_path() -> None:
    """The refusal reports the exception class and errno, never the failing path.

    An ``OSError`` renders the path it failed on, and an installation path
    carries the account name of whoever installed it -- the only content on this
    surface that varies with the machine. The operator reads this through an
    agent and cannot act on the path anyway.
    """
    from .._transport import _cli_resolution_refusal_envelope

    error = OSError(2, "No such file or directory", r"C:\Users\a-real-person\AppData\cadrumo\aeat.exe")
    document = _cli_resolution_refusal_envelope(command_key="app.modelo.calculate", error=error)

    raw_section = document["error"]
    assert isinstance(raw_section, dict)
    error_section: dict[str, object] = {str(key): value for key, value in raw_section.items()}
    message = str(error_section["message"])
    assert "a-real-person" not in message, "the refusal must not echo the installation path"
    assert "AppData" not in message, "nor any component of it"
    # Python resolves OSError(2, ...) to FileNotFoundError, so the reported class
    # is the specific subclass rather than the base -- which is the more useful
    # half of the diagnostic, and the reason this asserts the actual class rather
    # than a name assumed from the constructor.
    assert type(error).__name__ in message, "but it must still say which failure class it was"
    assert "errno 2" in message, "and give the errno a reader can act on"
