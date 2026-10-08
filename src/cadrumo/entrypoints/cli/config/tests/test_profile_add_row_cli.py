"""Real CLI coverage for the schema-owned repeatable profile-row door."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile

from .....adapters.persistence.storage.tests.profile_storage_root_fixture import profile_storage_root_fixture
from .....core.config import load_settings
from .....tests.cli_envelope import unwrap_schema_envelope
from ...tests.cli_runner import invoke_cached_cli
from .isolated_storage_fixture import CREDENTIAL_INPUT, native_profile_view_server, profile_persisted_facts
from .isolated_storage_fixture import live_cli_profile as live_cli_profile
from .isolated_storage_fixture import native_cli_profile_view as native_cli_profile_view

__all__ = ["profile_storage_root_fixture"]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def _native_row_cli(*args: str, label: str, passphrase: str = CREDENTIAL_INPUT) -> Result:
    """Supply the selected profile's password on the verified native channel."""
    return invoke_cached_cli(
        ("--format", "json", "--profile", label, "--profile-secrets-stdin", "config", "profile", *args),
        input=json.dumps({"profile_passphrase": passphrase}),
    )


def _show_values() -> dict[str, str]:
    """Read the actual encrypted record for this row-mutation oracle."""
    return profile_persisted_facts()


def test_profile_add_row_persists_an_activities_row_and_rejects_bad_values_without_writes(
    profile_storage_root: Path,
) -> None:
    """The root CLI reaches the application row door, and parser refusals are no-ops."""
    register_cli_profile(
        label="row-cli-operator",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Row CLI",
            "identity.surnames": "Operator",
            # Setup owns the unindexed activity row; the add-row command must
            # reserve slot zero and allocate the next explicit row at one.
            "activities.description": "Existing activity",
        },
        log_in=False,
    )

    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    with native_profile_view_server(profile_storage_root):
        success = _native_row_cli(
            "add-row",
            "activities",
            "--value",
            "description=Second activity",
            label="row-cli-operator",
            passphrase=passphrase,
        )
        assert success.exit_code == 0, success.output
        payload = unwrap_schema_envelope(success.output)
        # UUIDs are identity-sensitive; the success renderer redacts this result
        # field while the encrypted record read below proves the exact row.
        assert payload["profile_id"] == "<profile-id>"
        assert payload["section"] == "activities"
        assert payload["row_index"] == 1

        success_values = _show_values()
        assert success_values["activities.1.description"] == "Second activity"

        invalid = _native_row_cli(
            "add-row",
            "activities",
            "--value",
            "not-a-field-assignment",
            label="row-cli-operator",
            passphrase=passphrase,
        )
        assert invalid.exit_code != 0, invalid.output

        duplicate = _native_row_cli(
            "add-row",
            "activities",
            "--value",
            "description=would-be-first",
            "--value",
            "description=would-be-duplicate",
            label="row-cli-operator",
            passphrase=passphrase,
        )
        assert duplicate.exit_code != 0, duplicate.output

    assert _show_values() == success_values


@pytest.mark.usefixtures("native_cli_profile_view")
def test_a_mistyped_field_and_an_all_blank_row_are_refused_apart() -> None:
    """Each refusal must name the mistake the operator actually made.

    Reproduction: ``add-row activities --value descripcion=Taller`` was refused
    as a row with no populated field. Undeclared keys were dropped before the
    blank check, so an operator who had filled a field was told they had not,
    and the mistyped key was never named. A row that really is blank
    (``--value description=``) must still be refused, as a different mistake.
    """
    before = profile_persisted_facts()

    mistyped = _native_row_cli("add-row", "activities", "--value", "descripcion=Taller", label="Editor")
    blank = _native_row_cli("add-row", "activities", "--value", "description=", label="Editor")

    assert mistyped.exit_code == 2, mistyped.output
    assert blank.exit_code == 2, blank.output
    mistyped_context = json.loads(mistyped.stderr)["error"]["context"]
    blank_context = json.loads(blank.stderr)["error"]["context"]
    assert mistyped_context["unknown"] == "descripcion"
    assert "unknown" not in blank_context
    assert profile_persisted_facts() == before


@pytest.mark.usefixtures("native_cli_profile_view")
def test_row_edit_clear_remove_and_missing_row_are_atomic_and_survive_reopen() -> None:
    """All row verbs share stable identity, explicit clears, and durable outcomes."""
    added = _native_row_cli("add-row", "activities", "--value", "description=First", label="Editor")
    assert added.exit_code == 0, added.output
    row = str(json.loads(added.stdout)["result"]["row_index"])

    edited = _native_row_cli("edit-row", "activities", row, "--value", "description=Changed", label="Editor")
    assert edited.exit_code == 0, edited.output
    assert json.loads(edited.stdout)["result"]["changed"] is True
    assert profile_persisted_facts()[f"activities.{row}.description"] == "Changed"

    no_op = _native_row_cli("edit-row", "activities", row, "--value", "description=Changed", label="Editor")
    assert no_op.exit_code == 0, no_op.output
    assert json.loads(no_op.stdout)["result"]["changed"] is False

    cleared = _native_row_cli("edit-row", "activities", row, "--clear", "description", label="Editor")
    assert cleared.exit_code == 0, cleared.output
    assert f"activities.{row}.description" not in profile_persisted_facts()

    missing = _native_row_cli("remove-row", "activities", row, label="Editor")
    assert missing.exit_code == 2, missing.output
    assert json.loads(missing.stderr)["error"]["context"]["operation_id"]

    replacement = _native_row_cli("add-row", "activities", "--value", "description=Replacement", label="Editor")
    replacement_row = str(json.loads(replacement.stdout)["result"]["row_index"])
    assert int(replacement_row) > int(row)
    removed = _native_row_cli("remove-row", "activities", replacement_row, label="Editor")
    assert removed.exit_code == 0, removed.output
    assert f"activities.{replacement_row}.description" not in profile_persisted_facts()
