"""CLI-versus-MCP envelope parity across the subprocess and in-process transports.

D4 moves local verbs from a per-call ``aeat`` subprocess to a warm in-process
runtime. The load-bearing constraint is that the transport change may not fork
the result shape: the JSON envelope a client receives must be byte-identical
whichever transport served it. This oracle runs the SAME verb with the SAME
arguments through both real transports - a genuine ``aeat`` subprocess
(:func:`_run_subprocess_tool`) and the warm in-process runtime
(:func:`_run_inprocess_tool`) - and asserts the emitted envelopes are
byte-for-byte identical after canonical JSON serialisation.

There are no mocks: both transports run the real CLI pipeline against the real
registry and real filesystem state. A success envelope (a read verb that needs
no active profile) and a refusal envelope (a verb that refuses with no active
profile, emitted through the error boundary onto stderr) are both checked, so
parity holds on both the stdout success document and the stderr error document.

The Cadrumo envelope carries no per-run fields (its ``error`` document's
``trace_id`` is null, not a per-call token), so the whole envelope is compared;
were a legitimately per-run field ever introduced, it would be excluded here by
name with a stated reason rather than the comparison being loosened.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from ....core.config import DEV_TEST_DATABASE_PASSWORD
from ....tests import temporary_env
from .._call_runtime import tier_for, timeout_seconds
from .._inprocess import parse_cli_envelope, run_cli_in_process
from .._server import _run_inprocess_tool, _run_subprocess_tool
from .._tools import McpToolDescriptor, build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _descriptor(command_key: str) -> McpToolDescriptor:
    return next(candidate for candidate in build_tool_descriptors() if candidate.command_key == command_key)


def _canonical(envelope: dict[str, object]) -> str:
    return json.dumps(envelope, sort_keys=True, ensure_ascii=False)


def _both_transports(command_key: str, arguments: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    """Run one verb through the subprocess and the in-process transports."""
    descriptor = _descriptor(command_key)
    tier = tier_for(
        read_only=descriptor.annotations.read_only_hint,
        open_world=descriptor.annotations.open_world_hint,
    )
    subprocess_outcome = _run_subprocess_tool(descriptor, arguments)
    inprocess_outcome = _run_inprocess_tool(
        descriptor,
        arguments,
        tier=tier,
        timeout_s=timeout_seconds(tier),
        acquire_timeout_s=30.0,
    )
    assert inprocess_outcome is not None, "warm capture should be free in a single-threaded parity run"
    return subprocess_outcome.envelope, inprocess_outcome.envelope


def test_read_verb_success_envelope_is_byte_identical_across_transports() -> None:
    # ``contract`` is a read-only verb that needs no active profile, so both
    # transports emit a full success envelope with no environment-derived skew.
    subprocess_envelope, inprocess_envelope = _both_transports("contract", {})
    assert _canonical(subprocess_envelope) == _canonical(inprocess_envelope)
    assert inprocess_envelope["command"] == "contract"
    assert inprocess_envelope["status"] in {"success", "warning"}


def test_refusal_envelope_is_byte_identical_across_transports() -> None:
    # ``review.queue`` needs an active profile; with none it refuses through the
    # CLI error boundary, which renders the JSON error document to stderr. Both
    # transports parse that same stderr document, so the error envelope must match
    # byte-for-byte too.
    subprocess_envelope, inprocess_envelope = _both_transports("review.queue", {})
    assert subprocess_envelope["status"] == "error"
    assert inprocess_envelope["status"] == "error"
    assert _canonical(subprocess_envelope) == _canonical(inprocess_envelope)


@contextmanager
def _provisioned_profile_env(tmp_path: Path) -> Iterator[None]:
    """Provision a real encrypted profile under an env-isolated storage root."""
    with temporary_env(
        CADRUMO_LOCAL_STORAGE_ROOT=str(tmp_path / "storage"),
        CADRUMO_SECRET_STORE_BACKEND="file",  # noqa: S106 - env var name, not a credential
        CADRUMO_SECRET_STORE_DIR=str(tmp_path / "secrets"),
        CADRUMO_SECRET_PASSPHRASE=DEV_TEST_DATABASE_PASSWORD,
    ):
        created = run_cli_in_process(
            [
                "--format", "json", "config", "profile", "create", "operator",
                "--quiet", "--accept-defaults",
                "--entity-type", "natural_person",
                "--irpf-income-categories", "actividad_economica",
                "--tax-id", "12345678Z",
                "--name", "Operator",
                "--surnames", "Parity",
                "--activity", "design",
            ],
            acquire_timeout_s=30.0,
        )  # fmt: skip
        assert created is not None
        _, is_error = parse_cli_envelope(created)
        assert not is_error
        yield


def test_storage_touching_verb_envelope_is_byte_identical_across_transports(tmp_path: Path) -> None:
    # With a real encrypted profile active, ``review.queue`` opens a bucket session
    # and reads encrypted state on BOTH transports. The two envelopes must still be
    # byte-identical - the parity guarantee the warm-vs-subprocess degradation
    # fallback and the idle-lock custody both rely on for the storage path.
    with _provisioned_profile_env(tmp_path):
        subprocess_envelope, inprocess_envelope = _both_transports("review.queue", {})
    assert subprocess_envelope["status"] == "success"
    assert subprocess_envelope["active_profile"] == "operator"
    assert _canonical(subprocess_envelope) == _canonical(inprocess_envelope)
