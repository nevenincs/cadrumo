"""Real-behaviour tests for non-interactive ``config profile create``.

The scripted arm of ``create`` had no creation path: it fell through to the
setup flow, whose ``create`` mode refuses because the flow is not a creation
authority. These drive the real verb against a real storage root, through the
real registration door, and assert a real encrypted profile exists afterwards.
No mocks, no stubs.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from .....core.config import override_settings
from .....core.i18n import tr
from .....tests.cli_runner import invoke_cached_cli
from ... import _command_specs
from ..._command_spec import ArgumentSpec, CommandSpecGraph
from ..._verb_input_schema import build_verb_input_schemas

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "a-sufficiently-long-operator-passphrase"  # noqa: S105 - synthetic test credential


def _storage_overrides(tmp_path: Path, *, passphrase: str | None) -> dict[str, object]:
    return {
        "cadrumo_local_storage_root": tmp_path / "cadrumo-storage",
        "cadrumo_secret_passphrase": passphrase,
    }


def _creation_payload(passphrase: str = _PASSPHRASE) -> str:
    return json.dumps({"passphrase": passphrase, "passphrase_confirmation": passphrase})


def _invoke_create_with_recovery(
    arguments: tuple[str, ...],
    *,
    input: str | None = None,
    verification_transform=lambda payload: payload,
):
    """Drive the real two-pipe handoff while the in-process CLI is running."""
    handoff_reader, handoff_writer = os.pipe()
    verification_reader, verification_writer = os.pipe()
    observed: list[bytes] = []

    def supervise() -> None:
        payload = bytearray()
        try:
            while chunk := os.read(handoff_reader, 8193 - len(payload)):
                payload.extend(chunk)
            if payload:
                observed.append(bytes(payload))
                response = verification_transform(bytes(payload))
                os.write(verification_writer, response)
        finally:
            payload[:] = b"\x00" * len(payload)
            for descriptor in (handoff_reader, verification_writer):
                with suppress(OSError):
                    os.close(descriptor)

    supervisor = threading.Thread(target=supervise, daemon=True)
    supervisor.start()
    try:
        result = invoke_cached_cli(
            (
                *arguments,
                "--recovery-handoff-fd",
                str(handoff_writer),
                "--recovery-verification-fd",
                str(verification_reader),
            ),
            input=input,
        )
    finally:
        for descriptor in (handoff_writer, verification_reader):
            with suppress(OSError):
                os.close(descriptor)
        supervisor.join(timeout=5)
    assert not supervisor.is_alive()
    return result, observed


def _fact_values(document: dict[str, object]) -> dict[str, str]:
    """Project a ``config profile show`` envelope into a path -> value mapping."""
    result = document["result"]
    assert isinstance(result, dict)
    facts = result["facts"]
    assert isinstance(facts, list)
    return {str(fact["path"]): str(fact["value"]) for fact in facts}


def test_scripted_create_registers_a_real_profile(tmp_path: Path) -> None:
    """``create NAME --quiet`` brings a real, listable profile into existence."""
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        created, handoff = _invoke_create_with_recovery(
            ("--format", "json", "config", "profile", "create", "Scripted Operator", "--quiet", "--secrets-stdin"),
            input=_creation_payload(),
        )

        assert created.exit_code == 0, created.output
        assert len(handoff) == 1
        document = json.loads(created.stdout)
        assert document["result"]["profile_name"] == "Scripted Operator"
        assert document["result"]["status"] == "created"

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert listed.exit_code == 0, listed.output
    profiles = json.loads(listed.stdout)["result"]["profiles"]
    assert [profile["name"] for profile in profiles] == ["Scripted Operator"]
    assert profiles[0]["active"] is True
    # The bucket identifier is the profile UUID, and it reaches the operator
    # surface through the envelope's redaction funnel rather than raw.
    assert profiles[0]["bucket_id"] == "<bucket-id>"


def test_scripted_create_persists_the_field_flags_it_was_given(tmp_path: Path) -> None:
    """``create NAME --quiet --tax-id ...`` stores the facts, it does not drop them.

    The flagged form used to be routed back to the setup flow, which refuses
    ``create`` before it validates anything, so this invocation could not
    succeed at all. Asserting the values are READABLE afterwards is the point:
    a create that returned success while silently discarding the operator's
    facts would be the worse failure, and it is the one the old routing was
    written to avoid.
    """
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        created, _handoff = _invoke_create_with_recovery(
            (
                "--format",
                "json",
                "config",
                "profile",
                "create",
                "Flagged Operator",
                "--quiet",
                "--secrets-stdin",
                "--entity-type",
                "natural_person",
                "--tax-id",
                "12345678Z",
                "--name",
                "Flagged",
                "--surnames",
                "Operator",
            ),
            input=_creation_payload(),
        )

        assert created.exit_code == 0, created.output
        assert json.loads(created.stdout)["result"]["status"] == "created"

        shown = invoke_cached_cli(
            ("--format", "json", "--profile-secrets-stdin", "config", "profile", "show"),
            input=json.dumps({"profile_passphrase": _PASSPHRASE}),
        )

    # `show` reports a non-zero code for an INCOMPLETE profile, which this one
    # deliberately is -- a profile is born incomplete and the operator fills in
    # the rest afterwards. The envelope is still a success document, and it is
    # the facts inside it that this case is about.
    document = json.loads(shown.stdout)
    # Explicit root authentication is process-local without a usable system
    # keyring, so the shared envelope truthfully elevates its notice to warning.
    assert document["status"] == "warning", shown.output
    values = _fact_values(document)
    assert values.get("identity.name") == "Flagged"
    assert values.get("identity.surnames") == "Operator"
    assert values.get("taxpayer_type.entity_type") == "natural_person"
    # The tax identifier survives the write and is disclosed only through the
    # envelope's redaction funnel, never as the operator typed it.
    redacted_tax_id = values.get("identity.tax_id", "")
    assert redacted_tax_id.startswith("sha256:"), redacted_tax_id
    assert "12345678Z" not in shown.stdout


def test_scripted_create_refuses_a_foral_ccaa_flag_without_creating_a_profile(tmp_path: Path) -> None:
    """A refused flag costs the operator no profile, so there is nothing to undo.

    What this locks is the ORDERING, not the foral rule itself -- the rule is
    the tax-region validator's and is exercised where it lives. Here the value
    is that the projection runs BEFORE the passphrase is resolved and before
    the create transaction opens, so a refused flag leaves no capsule behind.
    Move the projection after registration and this case reds on the profile
    the run would strand.
    """
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        refused, _handoff = _invoke_create_with_recovery(
            (
                "--format",
                "json",
                "config",
                "profile",
                "create",
                "Foral Operator",
                "--quiet",
                "--secrets-stdin",
                "--tax-residence-ccaa",
                "pais_vasco",
            ),
            input=_creation_payload(),
        )

        assert refused.exit_code != 0, refused.output
        # The error document is the stderr envelope, per the shared CLI contract.
        assert json.loads(refused.stderr)["error"]["code"] == "REFUSED_PROFILE_FORAL_REGIME"

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_a_scripted_profile_enrolls_recovery_without_leaking_it_to_normal_output(tmp_path: Path) -> None:
    """The machine lane proves possession before creation and emits no words."""
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        created, handoff = _invoke_create_with_recovery(
            ("--format", "json", "config", "profile", "create", "No Terminal", "--quiet", "--secrets-stdin"),
            input=_creation_payload(),
        )

    assert created.exit_code == 0, created.output
    document = json.loads(created.stdout)
    codes = [notice["code"] for notice in document["notices"]]
    assert "PROFILE_RECOVERY_ENROLLED" in codes
    assert len(handoff) == 1
    phrase = json.loads(handoff[0])["recovery_mnemonic"]
    assert len(phrase.split()) == 24
    assert phrase not in created.stdout + created.stderr
    assert "mnemonic" not in created.stdout.lower()


def test_headless_create_without_recovery_descriptors_refuses_without_mutation(tmp_path: Path) -> None:
    """A valid passphrase cannot buy a permanently password-only profile."""
    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        refused = invoke_cached_cli(
            ("--format", "json", "config", "profile", "create", "No Recovery Pipe", "--quiet", "--secrets-stdin"),
            input=_creation_payload(),
        )
        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert refused.exit_code != 0
    assert json.loads(refused.stderr)["error"]["message"] == tr(
        "cli.config.profile.create_recovery_channel_absent"
    )
    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_headless_create_refuses_a_wrong_possession_proof_without_publication(tmp_path: Path) -> None:
    """The capsule is not published merely because the phrase was delivered."""

    def wrong_phrase(payload: bytes) -> bytes:
        document = json.loads(payload)
        words = str(document["recovery_mnemonic"]).split()
        words[0], words[1] = words[1], words[0]
        document["recovery_mnemonic"] = " ".join(words)
        return json.dumps(document).encode()

    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        refused, handoff = _invoke_create_with_recovery(
            ("--format", "json", "config", "profile", "create", "Wrong Proof", "--quiet", "--secrets-stdin"),
            input=_creation_payload(),
            verification_transform=wrong_phrase,
        )
        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert refused.exit_code != 0
    assert len(handoff) == 1
    phrase = json.loads(handoff[0])["recovery_mnemonic"]
    assert phrase not in refused.stdout + refused.stderr
    assert json.loads(listed.stdout)["result"]["profiles"] == []


@pytest.mark.parametrize(
    "proof",
    (
        b"not-json",
        b'{"recovery_mnemonic":"one","recovery_mnemonic":"two"}',
        b'{"recovery_mnemonic":"one","extra":"no"}',
        b'{"missing":"recovery_mnemonic"}',
        b"\xff\xfe",
        b'{"recovery_mnemonic":"' + b"x" * 9000 + b'"}',
    ),
)
def test_headless_recovery_proof_parser_refuses_without_publication(tmp_path: Path, proof: bytes) -> None:
    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        refused, _handoff = _invoke_create_with_recovery(
            ("config", "profile", "create", "Bad Recovery Proof", "--quiet", "--secrets-stdin"),
            input=_creation_payload(),
            verification_transform=lambda _payload: proof,
        )
        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))
    assert refused.exit_code != 0
    assert json.loads(listed.stdout)["result"]["profiles"] == []


@pytest.mark.parametrize(
    ("extra", "message_key"),
    (
        (("--recovery-handoff-fd", "9"), "cli.config.profile.create_recovery_descriptor_pair_required"),
        (("--recovery-verification-fd", "9"), "cli.config.profile.create_recovery_descriptor_pair_required"),
        (("--recovery-handoff-fd", "-1", "--recovery-verification-fd", "9"), "cli.config.profile.create_recovery_descriptor_reserved"),
        (("--recovery-handoff-fd", "1", "--recovery-verification-fd", "9"), "cli.config.profile.create_recovery_descriptor_reserved"),
        (("--recovery-handoff-fd", "9", "--recovery-verification-fd", "9"), "cli.config.profile.create_recovery_descriptor_collision"),
    ),
)
def test_recovery_descriptor_preflight_refuses_before_creation(
    tmp_path: Path, extra: tuple[str, ...], message_key: str
) -> None:
    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        refused = invoke_cached_cli(
            ("--format", "json", "config", "profile", "create", "Bad Descriptors", "--quiet", "--secrets-stdin", *extra),
            input=_creation_payload(),
        )
        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))
    assert refused.exit_code != 0
    assert json.loads(refused.stderr)["error"]["message"] == tr(message_key)
    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_unwritable_handoff_closes_both_recovery_descriptors_without_publication(tmp_path: Path) -> None:
    handoff_reader, handoff_writer = os.pipe()
    verification_reader, verification_writer = os.pipe()
    os.close(handoff_writer)
    os.close(verification_writer)
    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        refused = invoke_cached_cli(
            (
                "config", "profile", "create", "Unwritable Handoff", "--quiet", "--secrets-stdin",
                "--recovery-handoff-fd", str(handoff_reader),
                "--recovery-verification-fd", str(verification_reader),
            ),
            input=_creation_payload(),
        )
        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))
    assert refused.exit_code != 0
    for descriptor in (handoff_reader, verification_reader):
        with pytest.raises(OSError):
            os.fstat(descriptor)
    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_scripted_create_ignores_configured_passphrase_without_an_explicit_channel(tmp_path: Path) -> None:
    """A configured secret is not an implicit CLI channel.

    The refusal is the whole protection: a profile created under a passphrase
    the operator never chose is unopenable by them and indistinguishable from
    one they did choose.
    """
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        result = invoke_cached_cli(("config", "profile", "create", "No Channel", "--quiet"))

        assert result.exit_code != 0

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_lazy_scripted_create_accepts_and_closes_the_canonical_descriptor_channel(tmp_path: Path) -> None:
    reader, writer = os.pipe()
    os.write(writer, _creation_payload().encode())
    os.close(writer)

    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        created, _handoff = _invoke_create_with_recovery(
            (
                "--format",
                "json",
                "config",
                "profile",
                "create",
                "Descriptor Operator",
                "--quiet",
                "--secrets-fd",
                str(reader),
            ),
        )
        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert created.exit_code == 0, created.output
    assert json.loads(created.stdout)["result"]["profile_name"] == "Descriptor Operator"
    with pytest.raises(OSError):
        os.fstat(reader)
    assert [profile["name"] for profile in json.loads(listed.stdout)["result"]["profiles"]] == ["Descriptor Operator"]


def test_lazy_scripted_create_refuses_two_channels_before_read_or_mutation(tmp_path: Path) -> None:
    payload = _creation_payload().encode()
    reader, writer = os.pipe()
    os.write(writer, payload)
    os.close(writer)

    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        refused, _handoff = _invoke_create_with_recovery(
            (
                "config",
                "profile",
                "create",
                "Conflicted Operator",
                "--quiet",
                "--secrets-stdin",
                "--secrets-fd",
                str(reader),
            ),
            input=_creation_payload(),
        )
        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert refused.exit_code != 0
    assert os.read(reader, len(payload) + 1) == payload
    os.close(reader)
    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_scripted_create_localizes_a_typed_password_refusal_without_leaking(tmp_path: Path) -> None:
    """The machine credential channel reaches the same prospective refusal as the TUI."""
    candidate = "a" * 7
    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        refused, _handoff = _invoke_create_with_recovery(
            ("--format", "json", "config", "profile", "create", "Boundary Refusal", "--quiet", "--secrets-stdin"),
            input=json.dumps({"passphrase": candidate, "passphrase_confirmation": candidate}),
        )
        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    combined = refused.stdout + refused.stderr
    assert refused.exit_code != 0
    assert combined
    document = json.loads(refused.stderr)
    assert set(document) == {"active_profile", "command", "error", "notices", "schema_version", "status"}
    assert document["command"] == "config.profile.create"
    assert document["status"] == "error"
    assert document["notices"] == []
    error = document["error"]
    assert set(error) == {
        "action",
        "category",
        "code",
        "context",
        "message",
        "retryable",
        "runbook_id",
        "trace_id",
    }
    assert error["category"] == "REFUSED"
    assert error["code"] == "REFUSED_PROFILE_REGISTRATION"
    assert error["action"] is None
    assert error["retryable"] is False
    assert error["runbook_id"] is None
    assert error["context"] == {
        "minimum_scalars": "8",
        "reason": "too_few_scalars",
        "scalar_count": "7",
        "utf8_byte_count": "7",
    }
    assert error["message"] == tr(
        "application.user_profile.errors.profile_password_too_few_scalars",
        minimum_scalars=8,
        reason="too_few_scalars",
        scalar_count=7,
        utf8_byte_count=7,
    )
    assert "password_refusal" not in error["context"]
    assert "ProspectiveProfilePasswordRefusal" not in combined
    assert "profile_password_too_few_scalars" not in combined
    assert "profile password must contain 8 to 256 Unicode scalars" not in combined
    assert "Traceback" not in combined
    assert "INTERNAL" not in combined.upper()
    assert candidate not in combined
    assert json.loads(listed.stdout)["result"]["profiles"] == []


@pytest.mark.parametrize(
    "payload",
    (
        "not-json",
        json.dumps({"passphrase": _PASSPHRASE}),
        json.dumps({"passphrase": _PASSPHRASE, "passphrase_confirmation": _PASSPHRASE, "extra": "forbidden"}),
        json.dumps({"passphrase": "x" * 9000, "passphrase_confirmation": "x" * 9000}),
    ),
)
def test_scripted_create_rejects_malformed_secret_stdin_without_echo(tmp_path: Path, payload: str) -> None:
    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        refused = invoke_cached_cli(
            ("config", "profile", "create", "Malformed Secret", "--quiet", "--secrets-stdin"),
            input=payload,
        )
        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert refused.exit_code != 0
    combined = refused.stdout + refused.stderr
    assert _PASSPHRASE not in combined
    assert "x" * 9000 not in combined
    assert "Traceback" not in combined
    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_scripted_create_rejects_mismatched_confirmation_without_echo(tmp_path: Path) -> None:
    confirmation = "distinctive-confirmation-value"
    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        refused = invoke_cached_cli(
            ("config", "profile", "create", "Mismatch", "--quiet", "--secrets-stdin"),
            input=json.dumps({"passphrase": _PASSPHRASE, "passphrase_confirmation": confirmation}),
        )
        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))
    combined = refused.stdout + refused.stderr
    assert refused.exit_code != 0
    assert _PASSPHRASE not in combined
    assert confirmation not in combined
    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_lazy_create_help_declares_exactly_one_canonical_machine_secret_option_pair() -> None:
    help_result = invoke_cached_cli(("config", "profile", "create", "--help"))
    assert help_result.exit_code == 0, help_result.output
    assert help_result.output.count("--secrets-stdin") == 1
    assert help_result.output.count("--secrets-fd") == 1
    assert help_result.output.count("--recovery-handoff-fd") == 1
    assert help_result.output.count("--recovery-verification-fd") == 1
    schema = build_verb_input_schemas(("config.profile.create",))["config.profile.create"]
    parameters = [parameter for parameter in schema.parameters if parameter.name == "secrets_stdin"]
    assert len(parameters) == 1
    assert parameters[0].cli_flag == "--secrets-stdin"
    descriptor_parameters = [parameter for parameter in schema.parameters if parameter.name == "secrets_fd"]
    assert len(descriptor_parameters) == 1
    assert descriptor_parameters[0].cli_flag == "--secrets-fd"
    recovery_parameters = {
        parameter.name: parameter.cli_flag
        for parameter in schema.parameters
        if parameter.name in {"recovery_handoff_fd", "recovery_verification_fd"}
    }
    assert recovery_parameters == {
        "recovery_handoff_fd": "--recovery-handoff-fd",
        "recovery_verification_fd": "--recovery-verification-fd",
    }
    contract = schema.recovery_handoff_contract
    assert contract is not None
    assert contract.required_together is True
    assert contract.json_fields == ("recovery_mnemonic",)
    assert contract.maximum_bytes == 8192
    assert contract.reserved_descriptors == (0, 1, 2)
    assert contract.descriptors_must_differ is True
    assert contract.collides_with == ("--secrets-fd",)
    assert contract.handoff_direction == "write"
    assert contract.verification_direction == "read"


def test_recovery_schema_projects_changed_command_graph_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = _command_specs.COMMAND_GRAPH
    create = graph.by_key()["config_profile_create"]
    assert create.recovery_handoff is not None
    changed = replace(
        create,
        recovery_handoff=replace(create.recovery_handoff, maximum_bytes=4096),
    )
    monkeypatch.setattr(
        _command_specs,
        "COMMAND_GRAPH",
        CommandSpecGraph(tuple(changed if spec.key == create.key else spec for spec in graph.specs)),
    )

    schema = build_verb_input_schemas(("config.profile.create",))["config.profile.create"]

    assert schema.recovery_handoff_contract is not None
    assert schema.recovery_handoff_contract.maximum_bytes == 4096


def test_recovery_descriptor_parameters_refuse_missing_or_stale_declaration() -> None:
    create = _command_specs.COMMAND_GRAPH.by_key()["config_profile_create"]
    assert create.recovery_handoff is not None
    with pytest.raises(ValueError, match="require a recovery handoff spec"):
        replace(create, recovery_handoff=None)
    with pytest.raises(ValueError, match="references a missing command parameter"):
        replace(
            create,
            recovery_handoff=replace(create.recovery_handoff, handoff_parameter="stale_handoff_fd"),
        )


@pytest.mark.parametrize(
    ("field", "direction"),
    (("handoff_direction", "read"), ("verification_direction", "write"), ("handoff_direction", "sideways")),
)
def test_recovery_handoff_refuses_invalid_runtime_directions(field: str, direction: str) -> None:
    create = _command_specs.COMMAND_GRAPH.by_key()["config_profile_create"]
    assert create.recovery_handoff is not None
    with pytest.raises(ValueError, match="directions must be write then read"):
        replace(create.recovery_handoff, **{field: cast(Any, direction)})


def test_recovery_handoff_refuses_integer_argument_in_place_of_descriptor_option() -> None:
    create = _command_specs.COMMAND_GRAPH.by_key()["config_profile_create"]
    handoff = next(parameter for parameter in create.parameters if parameter.name == "recovery_handoff_fd")
    argument = ArgumentSpec(
        name=handoff.name,
        value=handoff.value,
        default=handoff.default,
        help_key=handoff.help_key,
    )
    parameters = tuple(argument if parameter is handoff else parameter for parameter in create.parameters)

    with pytest.raises(ValueError, match="must be command options"):
        replace(create, parameters=parameters)


def test_scripted_create_refuses_a_blank_name(tmp_path: Path) -> None:
    """A blank subject is refused before any credential is consumed."""
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        result = invoke_cached_cli(
            ("config", "profile", "create", "   ", "--quiet", "--secrets-stdin"),
            input=_creation_payload(),
        )

        assert result.exit_code != 0

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_scripted_create_is_refused_for_a_duplicate_label(tmp_path: Path) -> None:
    """Text success renders normally; a retry refuses without a second mutation."""
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        first, _handoff = _invoke_create_with_recovery(
            ("config", "profile", "create", "Only One", "--quiet", "--secrets-stdin"),
            input=_creation_payload(),
        )
        assert first.exit_code == 0, first.output

        second, _handoff = _invoke_create_with_recovery(
            ("config", "profile", "create", "Only One", "--quiet", "--secrets-stdin"),
            input=_creation_payload(),
        )
        assert second.exit_code != 0

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    profiles = json.loads(listed.stdout)["result"]["profiles"]
    assert [profile["name"] for profile in profiles] == ["Only One"]
