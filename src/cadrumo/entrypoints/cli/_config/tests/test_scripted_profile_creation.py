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
from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.i18n import tr
from .....tests.cli_runner import invoke_cached_cli
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
        created = invoke_cached_cli(
            ("--format", "json", "config", "profile", "create", "Scripted Operator", "--quiet", "--secrets-stdin"),
            input=_creation_payload(),
        )

        assert created.exit_code == 0, created.output
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
        created = invoke_cached_cli(
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

        shown = invoke_cached_cli(("--format", "json", "config", "profile", "show"))

    # `show` reports a non-zero code for an INCOMPLETE profile, which this one
    # deliberately is -- a profile is born incomplete and the operator fills in
    # the rest afterwards. The envelope is still a success document, and it is
    # the facts inside it that this case is about.
    document = json.loads(shown.stdout)
    assert document["status"] == "success", shown.output
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
        refused = invoke_cached_cli(
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


def test_a_scripted_profile_warns_that_recovery_was_not_enrolled(tmp_path: Path) -> None:
    """A run with no terminal enrolls no recovery, and SAYS so.

    Recovery can only be installed while the capsule is being published, so an
    operator who is not told at creation is never told at all -- they would
    hold a profile whose passphrase is the single point of failure and believe
    otherwise. The warning is the whole protection, and the 24 words must not
    appear anywhere in the machine output.
    """
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        created = invoke_cached_cli(
            ("--format", "json", "config", "profile", "create", "No Terminal", "--quiet", "--secrets-stdin"),
            input=_creation_payload(),
        )

    assert created.exit_code == 0, created.output
    document = json.loads(created.stdout)
    codes = [notice["code"] for notice in document["notices"]]
    assert "PROFILE_RECOVERY_NOT_ENROLLED" in codes
    # The envelope must never be the transport for recovery material, whether
    # or not a wrapper was minted.
    assert "mnemonic" not in created.stdout.lower()


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
        created = invoke_cached_cli(
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
        refused = invoke_cached_cli(
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
    candidate = "a" * 14
    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        refused = invoke_cached_cli(
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
        "minimum_scalars": "15",
        "reason": "too_few_scalars",
        "scalar_count": "14",
        "utf8_byte_count": "14",
    }
    assert error["message"] == tr(
        "application.user_profile.errors.profile_password_too_few_scalars",
        minimum_scalars=15,
        reason="too_few_scalars",
        scalar_count=14,
        utf8_byte_count=14,
    )
    assert "password_refusal" not in error["context"]
    assert "ProspectiveProfilePasswordRefusal" not in combined
    assert "profile_password_too_few_scalars" not in combined
    assert "profile password must contain 15 to 256 Unicode scalars" not in combined
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
    schema = build_verb_input_schemas(("config.profile.create",))["config.profile.create"]
    parameters = [parameter for parameter in schema.parameters if parameter.name == "secrets_stdin"]
    assert len(parameters) == 1
    assert parameters[0].cli_flag == "--secrets-stdin"
    descriptor_parameters = [parameter for parameter in schema.parameters if parameter.name == "secrets_fd"]
    assert len(descriptor_parameters) == 1
    assert descriptor_parameters[0].cli_flag == "--secrets-fd"


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
    """The second create under one label refuses and leaves the first intact."""
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        first = invoke_cached_cli(
            ("config", "profile", "create", "Only One", "--quiet", "--secrets-stdin"),
            input=_creation_payload(),
        )
        assert first.exit_code == 0, first.output

        second = invoke_cached_cli(
            ("config", "profile", "create", "Only One", "--quiet", "--secrets-stdin"),
            input=_creation_payload(),
        )
        assert second.exit_code != 0

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    profiles = json.loads(listed.stdout)["result"]["profiles"]
    assert [profile["name"] for profile in profiles] == ["Only One"]
