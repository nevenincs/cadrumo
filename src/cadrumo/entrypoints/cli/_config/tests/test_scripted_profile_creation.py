"""Real-behaviour tests for non-interactive ``config profile create``.

The scripted arm of ``create`` had no creation path: it fell through to the
setup flow, whose ``create`` mode refuses because the flow is not a creation
authority. These drive the real verb against a real storage root, through the
real registration door, and assert a real encrypted profile exists afterwards.
No mocks, no stubs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.i18n import tr
from .....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "a-sufficiently-long-operator-passphrase"  # noqa: S105 - synthetic test credential


def _storage_overrides(tmp_path: Path, *, passphrase: str | None) -> dict[str, object]:
    return {
        "cadrumo_local_storage_root": tmp_path / "cadrumo-storage",
        "cadrumo_secret_passphrase": passphrase,
    }


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
        created = invoke_cached_cli(("--format", "json", "config", "profile", "create", "Scripted Operator", "--quiet"))

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
                "--entity-type",
                "natural_person",
                "--tax-id",
                "12345678Z",
                "--name",
                "Flagged",
                "--surnames",
                "Operator",
            ),
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
                "--tax-residence-ccaa",
                "pais_vasco",
            ),
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
        created = invoke_cached_cli(("--format", "json", "config", "profile", "create", "No Terminal", "--quiet"))

    assert created.exit_code == 0, created.output
    document = json.loads(created.stdout)
    codes = [notice["code"] for notice in document["notices"]]
    assert "PROFILE_RECOVERY_NOT_ENROLLED" in codes
    # The envelope must never be the transport for recovery material, whether
    # or not a wrapper was minted.
    assert "mnemonic" not in created.stdout.lower()


def test_scripted_create_refuses_when_no_passphrase_channel_is_available(tmp_path: Path) -> None:
    """With no console and no configured secret, creation refuses rather than inventing one.

    The refusal is the whole protection: a profile created under a passphrase
    the operator never chose is unopenable by them and indistinguishable from
    one they did choose.
    """
    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        result = invoke_cached_cli(("config", "profile", "create", "No Channel", "--quiet"))

        assert result.exit_code != 0

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_scripted_create_localizes_a_typed_password_refusal_without_leaking(tmp_path: Path) -> None:
    """The machine credential channel reaches the same prospective refusal as the TUI."""
    candidate = "a" * 14
    with override_settings(**_storage_overrides(tmp_path, passphrase=candidate)):
        refused = invoke_cached_cli(("--format", "json", "config", "profile", "create", "Boundary Refusal", "--quiet"))
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


def test_scripted_create_refuses_a_blank_name(tmp_path: Path) -> None:
    """A blank subject is refused before any credential is consumed."""
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        result = invoke_cached_cli(("config", "profile", "create", "   ", "--quiet"))

        assert result.exit_code != 0

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_scripted_create_is_refused_for_a_duplicate_label(tmp_path: Path) -> None:
    """The second create under one label refuses and leaves the first intact."""
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        first = invoke_cached_cli(("config", "profile", "create", "Only One", "--quiet"))
        assert first.exit_code == 0, first.output

        second = invoke_cached_cli(("config", "profile", "create", "Only One", "--quiet"))
        assert second.exit_code != 0

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    profiles = json.loads(listed.stdout)["result"]["profiles"]
    assert [profile["name"] for profile in profiles] == ["Only One"]
