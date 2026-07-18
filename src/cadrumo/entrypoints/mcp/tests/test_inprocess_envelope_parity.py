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

P06.S19 adds the static counterpart: a per-verb CLI-versus-MCP *schema* parity
diff. The runtime tests above prove one verb's ENVELOPE is identical across
transports; the schema tests below prove every operator verb's advertised
REQUEST and RESPONSE schema on the MCP surface is exactly the schema the CLI
surface declares - the request schema projected from the live CLI command's own
click parameters, and the response schema embedding the CLI-registered result
model inside the shared envelope. The verb set is enumerated from the live
operator-surface manifest, so a newly-mounted verb is covered automatically, and
each assertion is a genuine value diff that fails if the MCP surface forks from
the CLI authority for any verb.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from ....core.config import DEV_TEST_DATABASE_PASSWORD
from ....core.json_contract import ENVELOPE_SCHEMA_VERSION, SCHEMA_REGISTRY
from ....tests import temporary_env
from ...cli import command_schema_refs
from .._call_runtime import tier_for, timeout_seconds
from .._dispatch import is_exposable_command
from .._inprocess import parse_cli_envelope, run_cli_in_process
from .._input_schema import build_verb_input_schemas
from .._result_thinning import thin_output_schema
from .._tools import McpToolDescriptor, build_tool_descriptors
from .._transport import _run_inprocess_tool, _run_subprocess_tool

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


# --- P06.S19: per-verb CLI-versus-MCP schema-parity diff -----------------------


def _cli_exposable_verbs() -> frozenset[str]:
    """Every operator verb the CLI surface exposes, from the live manifest.

    ``command_schema_refs`` is the CLI's own registry projection (the same source
    :func:`~entrypoints.mcp._tools.build_tool_descriptors` reads); an operator
    verb is one that survives the exposability filter, so the set auto-grows when
    a verb is mounted.
    """
    return frozenset(ref.command for ref in command_schema_refs() if is_exposable_command(ref.command))


def _mcp_descriptors_by_key() -> dict[str, McpToolDescriptor]:
    return {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}


def test_operator_verb_set_is_identical_across_the_cli_and_mcp_surfaces() -> None:
    # A verb exposed on the CLI but absent from the MCP surface (or vice versa) is
    # a surface fork: an operator that can drive it from a terminal but not the
    # agent transport, or an advertised tool with no CLI command behind it.
    cli_verbs = _cli_exposable_verbs()
    mcp_verbs = frozenset(_mcp_descriptors_by_key())
    assert cli_verbs == mcp_verbs
    # Non-vacuous: the surface is the real ~200+ verb command tree, not empty.
    assert len(mcp_verbs) >= 200


def test_request_schema_matches_the_live_cli_command_for_every_verb() -> None:
    # The MCP request schema per verb must be exactly the schema projected from
    # that verb's OWN live CLI click parameters. Rebuilding the projection from
    # the live command tree and diffing it against every advertised descriptor
    # proves the request surface cannot drift between the two: a parameter added
    # to the CLI command but missing from the MCP schema (or an overridden MCP
    # input schema) fails here for that verb.
    descriptors = _mcp_descriptors_by_key()
    cli_request_schemas = build_verb_input_schemas(tuple(descriptors))
    mismatched: list[str] = []
    for key, descriptor in descriptors.items():
        cli_schema = cli_request_schemas[key].json_schema()
        if descriptor.input_schema != cli_schema:
            mismatched.append(key)
    assert mismatched == []


def _expected_response_schema(command_key: str) -> dict[str, object]:
    """The response schema the CLI surface authorises for one verb.

    The CLI emits the command's registered :class:`OutputSchema` (from
    :data:`SCHEMA_REGISTRY`) inside the shared envelope; a verb with no
    registered result model advertises the generic object. This mirrors the CLI
    authority independently of the MCP tool builder, so the diff is a genuine
    cross-surface check rather than a re-derivation of the same function.
    """
    schema = SCHEMA_REGISTRY.get(command_key)
    if schema is None:
        return {"type": "object"}
    result_schema = thin_output_schema(command_key, schema.model_json_schema())
    definitions = result_schema.pop("$defs", {})
    return {
        "$defs": definitions,
        "type": "object",
        "properties": {
            "schema_version": {"const": ENVELOPE_SCHEMA_VERSION, "type": "string"},
            "command": {"const": command_key, "type": "string"},
            "active_profile": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "status": {"enum": ["success", "warning"], "type": "string"},
            "result": result_schema,
            "notices": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"enum": ["info", "warning"], "type": "string"},
                        "code": {"minLength": 1, "type": "string"},
                        "message": {"minLength": 1, "type": "string"},
                        "suggestion": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "context": {
                            "anyOf": [
                                {"type": "object", "additionalProperties": {"type": "string"}},
                                {"type": "null"},
                            ],
                        },
                    },
                    "required": ["severity", "code", "message", "suggestion", "context"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["schema_version", "command", "active_profile", "status", "result", "notices"],
        "additionalProperties": False,
    }


def test_response_schema_embeds_the_cli_registered_result_model_for_every_verb() -> None:
    # The MCP response schema per verb must embed exactly the CLI-registered
    # result model inside the shared envelope. Diffing every advertised
    # descriptor's output schema against the CLI authority proves the response
    # surface cannot fork: a hand-authored MCP output schema, a divergent
    # thinning, or a stale result model for any verb fails here.
    descriptors = _mcp_descriptors_by_key()
    grounded = 0
    mismatched: list[str] = []
    for key, descriptor in descriptors.items():
        if SCHEMA_REGISTRY.get(key) is not None:
            grounded += 1
        if descriptor.output_schema != _expected_response_schema(key):
            mismatched.append(key)
    assert mismatched == []
    # Non-vacuous: a substantial share of verbs carry a real registered result
    # model, so the diff is not trivially the generic-object fallback everywhere.
    assert grounded >= 100


def test_advertised_response_schema_describes_the_real_cli_emitted_envelope() -> None:
    # Cross-surface runtime proof: the response schema the MCP surface advertises
    # for a verb must actually describe the envelope the CLI emits for it. Run a
    # read verb through the real CLI in-process and assert its emitted envelope
    # satisfies the MCP-advertised output schema's spine (every required key
    # present, the command const and status enum honoured).
    descriptor = _mcp_descriptors_by_key()["contract"]
    # ``contract`` is a read verb needing no active profile; the in-process
    # transport runs the real CLI pipeline and emits the genuine envelope.
    _, envelope = _both_transports("contract", {})
    output_schema = descriptor.output_schema
    required = output_schema["required"]
    assert isinstance(required, list)
    for field in required:
        assert field in envelope, f"CLI envelope for 'contract' is missing MCP-advertised field {field!r}"
    assert envelope["command"] == output_schema["properties"]["command"]["const"]
    assert envelope["status"] in output_schema["properties"]["status"]["enum"]
