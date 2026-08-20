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

This module adds the static counterpart: a per-verb CLI-versus-MCP *schema* parity
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

# Typer builds its command tree on a vendored copy of click, so the tree-walk
# types and the numeric/boolean ``ParamType`` classes this module tests against
# must come from ``typer._click`` rather than the top-level ``click`` package.
from typer._click.core import Command as ClickCommand
from typer._click.core import Context as ClickContext
from typer._click.core import Parameter as ClickParameter
from typer._click.types import BoolParamType, FloatParamType, IntParamType
from typer.main import get_command as typer_get_command

from cadrumo.core.config import DEV_TEST_DATABASE_PASSWORD
from cadrumo.core.json_contract import SCHEMA_REGISTRY
from cadrumo.entrypoints.cli import app as cli_app
from cadrumo.entrypoints.cli import command_schema_refs, is_exposable_command
from cadrumo.entrypoints.schema_surface import CLI_PATH_BY_SCHEMA_KEY
from cadrumo.tests import temporary_env

from .._call_runtime import tier_for, timeout_seconds
from .._inprocess import parse_cli_envelope, run_cli_in_process
from .._result_thinning import thin_output_schema
from .._tools import McpToolDescriptor, build_tool_descriptors
from .._transport import _run_inprocess_tool, _run_subprocess_tool

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _without_titles(schema: object) -> object:
    """Mirror the descriptor builder's removal of pydantic auto-generated titles."""
    if isinstance(schema, dict):
        return {key: _without_titles(value) for key, value in schema.items() if key != "title"}
    if isinstance(schema, list):
        return [_without_titles(item) for item in schema]
    return schema


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
    # ``registry.inspect`` is a read-only verb that needs no active profile, so both
    # transports emit a full success envelope with no environment-derived skew.
    subprocess_envelope, inprocess_envelope = _both_transports("registry.inspect", {})
    assert _canonical(subprocess_envelope) == _canonical(inprocess_envelope)
    assert inprocess_envelope["command"] == "registry.inspect"
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
        CADRUMO_SECRET_STORE_BACKEND="auto",  # noqa: S106 - env var name, not a credential
        CADRUMO_SECRET_STORE_DIR=str(tmp_path / "fallback-store"),
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


# --- per-verb CLI-versus-MCP schema-parity diff --------------------------------


def _cli_exposable_verbs() -> frozenset[str]:
    """Every operator verb the CLI surface exposes, from the live manifest.

    ``command_schema_refs`` is the CLI's own registry projection (the same source
    :func:`~cadrumo_harness.mcp._tools.build_tool_descriptors` reads); an operator
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


def _live_command_tree() -> dict[tuple[str, ...], tuple[ClickCommand, tuple[str, ...]]]:
    """Enumerate every command in the live ``aeat`` tree by its CLI path.

    Walks the whole materialised click tree breadth-first from the root, forcing
    each lazily-loaded subgroup exactly as real dispatch does. The mapping key
    normalises hyphens to underscores (so a schema key's ``iva_wallet`` segment
    finds the ``iva-wallet`` command); the value carries the command plus its
    real, un-normalised path tokens.

    This is a whole-tree enumeration, deliberately independent of the per-key
    resolution the MCP input-schema builder performs, so the two cannot agree by
    construction.
    """
    root = typer_get_command(cli_app)
    tree: dict[tuple[str, ...], tuple[ClickCommand, tuple[str, ...]]] = {}

    def walk(command: ClickCommand, context: ClickContext, prefix: tuple[str, ...]) -> None:
        lister = getattr(command, "list_commands", None)
        if lister is None:
            return
        getter = getattr(command, "get_command", None)
        if getter is None:
            return
        for name in lister(context):
            child = getter(context, name)
            if child is None:
                continue
            path = (*prefix, name)
            tree[tuple(token.replace("-", "_") for token in path)] = (child, path)
            walk(child, ClickContext(child, parent=context, info_name=name), path)

    walk(root, ClickContext(root, info_name=str(root.name)), ())
    return tree


def _cli_path_for_schema_key(command_key: str) -> tuple[str, ...]:
    """The normalised CLI path a result-schema key addresses.

    Schema keys are derived mechanically from their CLI path, with the exception
    mapping owned by :data:`CLI_PATH_BY_SCHEMA_KEY`; a key that carries neither
    root segment hangs off ``app``.
    """
    tokens = CLI_PATH_BY_SCHEMA_KEY.get(command_key) or tuple(command_key.split("."))
    if tokens[0] not in {"config", "app"}:
        tokens = ("app", *tokens)
    return tuple(token.replace("-", "_") for token in tokens)


def _declared_choices(parameter: ClickParameter) -> tuple[str, ...]:
    """The closed value set a click parameter declares, or empty.

    A ``click_type=Choice(...)`` passed through Typer is wrapped in a
    ``FuncParamType`` that hides ``.choices`` behind ``.func``, so both shapes are
    read.
    """
    raw = getattr(parameter.type, "choices", None)
    if raw is None:
        raw = getattr(getattr(parameter.type, "func", None), "choices", None)
    return tuple(str(choice) for choice in raw) if raw else ()


def _json_safe(value: object) -> object:
    """Render a click default the way a JSON document carries it."""
    if isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple | list):
        return [_json_safe(item) for item in value]
    return None


def _scalar_shape(parameter: ClickParameter, choices: tuple[str, ...]) -> dict[str, object]:
    """The JSON scalar a click parameter's own declared type projects onto.

    Narrows on the vendored click ``ParamType`` classes (``IntRange`` and
    ``FloatRange`` are subclasses of the integer and float types), which is a
    different mechanism from the builder's type-name inspection.
    """
    if bool(getattr(parameter, "is_flag", False)):
        return {"type": "boolean"}
    if choices:
        return {"type": "string", "enum": list(choices)}
    if isinstance(parameter.type, BoolParamType):
        return {"type": "boolean"}
    if isinstance(parameter.type, IntParamType):
        return {"type": "integer"}
    if isinstance(parameter.type, FloatParamType):
        return {"type": "number"}
    return {"type": "string"}


def _click_request_shape(command: ClickCommand) -> dict[str, object]:
    """The request contract one live CLI command declares.

    One property per operator-facing (non-hidden, named) click parameter, typed
    from that parameter's own declaration, arrayed when it repeats, carrying its
    default when an option declares one; plus the sorted required names. Help
    prose is deliberately excluded - it is localized and asserting it would bind
    the gate to generated text rather than structure.
    """
    properties: dict[str, object] = {}
    required: list[str] = []
    for parameter in command.params:
        name = parameter.name
        if name is None or getattr(parameter, "hidden", False):
            continue
        choices = _declared_choices(parameter)
        scalar = _scalar_shape(parameter, choices)
        schema: dict[str, object] = (
            {"type": "array", "items": scalar} if getattr(parameter, "multiple", False) else scalar
        )
        if getattr(parameter, "param_type_name", "") != "argument":
            default = _json_safe(parameter.default)
            if default is not None:
                schema["default"] = default
        properties[name] = schema
        if getattr(parameter, "required", False):
            required.append(name)
    return {"properties": properties, "required": sorted(required)}


def _without_prose(schema: object) -> object:
    """Drop the localized ``description`` from a property schema fragment."""
    if not isinstance(schema, dict):
        return schema
    stripped: dict[str, object] = {str(key): value for key, value in schema.items() if key != "description"}
    if "items" in stripped:
        stripped["items"] = _without_prose(stripped["items"])
    return stripped


def _advertised_request_shape(input_schema: dict[str, object]) -> dict[str, object]:
    """Read the same contract back off an advertised MCP input schema."""
    properties = input_schema["properties"]
    required = input_schema["required"]
    assert isinstance(properties, dict)
    assert isinstance(required, list)
    required_names = [name for name in required if isinstance(name, str)]
    assert len(required_names) == len(required), f"non-string entries in advertised 'required': {required!r}"
    return {
        "properties": {name: _without_prose(schema) for name, schema in properties.items()},
        "required": sorted(required_names),
    }


def _request_schema_mismatches(descriptors: dict[str, McpToolDescriptor]) -> list[str]:
    """Every verb whose advertised request schema forks from its live CLI command."""
    tree = _live_command_tree()
    mismatched: list[str] = []
    for key, descriptor in descriptors.items():
        command, real_path = tree[_cli_path_for_schema_key(key)]
        if tuple(descriptor.verb_schema.cli_path) != real_path:
            mismatched.append(key)
            continue
        if _click_request_shape(command) != _advertised_request_shape(descriptor.input_schema):
            mismatched.append(key)
    return mismatched


def test_request_schema_matches_the_live_cli_command_for_every_verb() -> None:
    # The MCP request schema per verb must describe exactly that verb's OWN live
    # CLI command. The expectation is derived independently: the whole click tree
    # is enumerated, each verb's command located by its schema key, and its
    # request contract read straight off the command's click parameter objects -
    # never from the MCP input-schema builder, whose output is the thing under
    # test. A parameter added to the CLI command but missing from the MCP schema,
    # a drifted type or enum, a hand-overridden input schema, or a verb resolved
    # to the wrong command all fail here for that verb.
    descriptors = _mcp_descriptors_by_key()
    assert _request_schema_mismatches(descriptors) == []
    # Non-vacuous: the diff is over real parameter surfaces, not empty schemas.
    assert sum(1 for descriptor in descriptors.values() if descriptor.input_schema["properties"]) >= 100
    for descriptor in descriptors.values():
        assert descriptor.input_schema["type"] == "object"
        assert descriptor.input_schema["additionalProperties"] is False


def test_request_schema_parity_detects_an_injected_descriptor_drift() -> None:
    # Discrimination proof: the parity check above is only worth its green if it
    # can go red. Inject each drift class into one real descriptor - an extra
    # property, a dropped property, a widened requiredness, a retyped parameter -
    # and assert the check names exactly that verb. A detector with no proof it
    # fires is the defect it claims to catch.
    descriptors = _mcp_descriptors_by_key()
    victim = "review.queue"
    baseline = descriptors[victim]
    properties = dict(baseline.input_schema["properties"])
    assert properties, "the injection victim must declare real parameters"
    required = list(baseline.input_schema["required"])
    dropped_name = next(name for name in properties if name not in required)

    added = {**baseline.input_schema, "properties": {**properties, "invented_flag": {"type": "boolean"}}}
    dropped = {**baseline.input_schema, "properties": {k: v for k, v in properties.items() if k != dropped_name}}
    over_required = {**baseline.input_schema, "required": [*required, dropped_name]}
    # An enum no CLI parameter can declare, so the retype is a drift whatever the
    # parameter's real declared type happens to be.
    retyped = {
        **baseline.input_schema,
        "properties": {**properties, dropped_name: {"type": "string", "enum": ["__not_a_cli_choice__"]}},
    }

    for drifted_schema in (added, dropped, over_required, retyped):
        drifted = dict(descriptors)
        drifted[victim] = baseline.model_copy(update={"input_schema": drifted_schema})
        assert _request_schema_mismatches(drifted) == [victim]

    # And a verb whose descriptor is left untouched stays clean, so the detector
    # is not simply failing everything.
    assert _request_schema_mismatches(descriptors) == []


def test_response_schema_embeds_the_cli_registered_result_model_for_every_verb() -> None:
    # The MCP response schema per verb must embed exactly the CLI-registered
    # result model inside the shared envelope. Diffing every advertised
    # descriptor's output schema against the CLI authority proves the response
    # surface cannot fork: a hand-authored MCP output schema, a divergent
    # thinning, or a stale result model for any verb fails here.
    descriptors = _mcp_descriptors_by_key()
    grounded = 0
    for key, descriptor in descriptors.items():
        branches = descriptor.output_schema["oneOf"]
        assert isinstance(branches, list) and len(branches) == 2
        success_branch, error_branch = branches
        assert isinstance(success_branch, dict)
        assert isinstance(error_branch, dict)
        success_properties = success_branch["properties"]
        error_properties = error_branch["properties"]
        assert isinstance(success_properties, dict)
        assert isinstance(error_properties, dict)
        assert success_properties["command"] == {"const": key, "type": "string"}
        assert success_properties["status"] == {"enum": ["success", "warning"], "type": "string"}
        assert error_properties["status"] == {"const": "error", "type": "string"}
        assert set(error_branch["required"]) == {
            "schema_version",
            "command",
            "active_profile",
            "status",
            "error",
            "notices",
        }
        schema = SCHEMA_REGISTRY.get(key)
        if schema is None:
            continue
        grounded += 1
        expected_result = thin_output_schema(key, schema.model_json_schema())
        expected_result.pop("$defs", None)
        # The descriptor drops pydantic's auto-generated ``title`` keys, so the
        # comparison strips them from the expectation too. Titles are a pure
        # function of the key they sit under and nothing reads them; what this
        # gate exists to pin is that the ADVERTISED result is the registered
        # model's own shape, which title removal does not alter.
        assert success_properties["result"] == _without_titles(expected_result)
    # Non-vacuous: a substantial share of verbs carry a real registered result
    # model, so the diff is not trivially the generic-object fallback everywhere.
    assert grounded >= 100


def test_advertised_response_schema_describes_the_real_cli_emitted_envelope() -> None:
    # Cross-surface runtime proof: the response schema the MCP surface advertises
    # for a verb must actually describe the envelope the CLI emits for it. Run a
    # read verb through the real CLI in-process and assert its emitted envelope
    # satisfies the MCP-advertised output schema's spine (every required key
    # present, the command const and status enum honoured).
    descriptor = _mcp_descriptors_by_key()["registry.inspect"]
    # ``contract`` is a read verb needing no active profile; the in-process
    # transport runs the real CLI pipeline and emits the genuine envelope.
    _, envelope = _both_transports("registry.inspect", {})
    output_schema = descriptor.output_schema
    branches = output_schema["oneOf"]
    assert isinstance(branches, list)
    success_branch = branches[0]
    assert isinstance(success_branch, dict)
    required = success_branch["required"]
    assert isinstance(required, list)
    for field in required:
        assert field in envelope, f"CLI envelope for 'registry.inspect' is missing MCP-advertised field {field!r}"
    properties = success_branch["properties"]
    assert isinstance(properties, dict)
    assert envelope["command"] == properties["command"]["const"]
    assert envelope["status"] in properties["status"]["enum"]
