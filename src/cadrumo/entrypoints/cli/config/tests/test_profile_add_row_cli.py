"""Real CLI coverage for the schema-owned repeatable profile-row door."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile

from .....adapters.persistence.storage.tests.profile_storage_root_fixture import profile_storage_root_fixture
from .....tests.cli_envelope import unwrap_schema_envelope
from ...main import app as root_app
from ...tests.cli_runner import invoke_typer_app
from .isolated_storage_fixture import live_cli_profile as live_cli_profile
from .isolated_storage_fixture import profile_cli, profile_facts

__all__ = ["profile_storage_root_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]


def _show_values() -> dict[str, str]:
    """Read the persisted facts back through the public profile-show door."""
    shown = invoke_typer_app(root_app, ["--format", "json", "config", "profile", "view"])
    assert shown.exit_code == 0, shown.output
    payload = unwrap_schema_envelope(shown.output)
    facts = payload["facts"]
    assert isinstance(facts, list)
    return {item["path"]: item["value"] for item in facts}


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

    success = invoke_typer_app(
        root_app,
        [
            "--format",
            "json",
            "config",
            "profile",
            "add-row",
            "activities",
            "--value",
            "description=Second activity",
        ],
    )
    assert success.exit_code == 0, success.output
    payload = unwrap_schema_envelope(success.output)
    # UUIDs are identity-sensitive; the success renderer redacts this result
    # field while the public profile-show read below proves the exact row.
    assert payload["profile_id"] == "<profile-id>"
    assert payload["section"] == "activities"
    assert payload["row_index"] == 1

    success_values = _show_values()
    assert success_values["activities.1.description"] == "Second activity"

    invalid = invoke_typer_app(
        root_app,
        [
            "config",
            "profile",
            "add-row",
            "activities",
            "--value",
            "not-a-field-assignment",
        ],
    )
    assert invalid.exit_code != 0, invalid.output

    duplicate = invoke_typer_app(
        root_app,
        [
            "config",
            "profile",
            "add-row",
            "activities",
            "--value",
            "description=would-be-first",
            "--value",
            "description=would-be-duplicate",
        ],
    )
    assert duplicate.exit_code != 0, duplicate.output

    assert _show_values() == success_values


@pytest.mark.usefixtures("live_cli_profile")
def test_a_mistyped_field_and_an_all_blank_row_are_refused_apart() -> None:
    """Each refusal must name the mistake the operator actually made.

    Reproduction: ``add-row activities --value descripcion=Taller`` was refused
    as a row with no populated field. Undeclared keys were dropped before the
    blank check, so an operator who had filled a field was told they had not,
    and the mistyped key was never named. A row that really is blank
    (``--value description=``) must still be refused, as a different mistake.
    """
    before = profile_facts()

    mistyped = profile_cli("add-row", "activities", "--value", "descripcion=Taller")
    blank = profile_cli("add-row", "activities", "--value", "description=")

    assert mistyped.exit_code == 2, mistyped.output
    assert blank.exit_code == 2, blank.output
    mistyped_context = json.loads(mistyped.stderr)["error"]["context"]
    blank_context = json.loads(blank.stderr)["error"]["context"]
    assert mistyped_context["unknown"] == "descripcion"
    assert "unknown" not in blank_context
    assert profile_facts() == before


@pytest.mark.usefixtures("live_cli_profile")
def test_row_edit_clear_remove_and_missing_row_are_atomic_and_survive_reopen() -> None:
    """All row verbs share stable identity, explicit clears, and durable outcomes."""
    added = profile_cli("add-row", "activities", "--value", "description=First")
    assert added.exit_code == 0, added.output
    row = str(json.loads(added.stdout)["result"]["row_index"])

    edited = profile_cli("edit-row", "activities", row, "--value", "description=Changed")
    assert edited.exit_code == 0, edited.output
    assert json.loads(edited.stdout)["result"]["changed"] is True
    assert profile_facts()[f"activities.{row}.description"] == "Changed"

    no_op = profile_cli("edit-row", "activities", row, "--value", "description=Changed")
    assert no_op.exit_code == 0, no_op.output
    assert json.loads(no_op.stdout)["result"]["changed"] is False

    cleared = profile_cli("edit-row", "activities", row, "--clear", "description")
    assert cleared.exit_code == 0, cleared.output
    assert f"activities.{row}.description" not in profile_facts()

    missing = profile_cli("remove-row", "activities", row)
    assert missing.exit_code == 2, missing.output
    assert json.loads(missing.stderr)["error"]["context"] == {"row": row, "section": "activities"}

    replacement = profile_cli("add-row", "activities", "--value", "description=Replacement")
    replacement_row = str(json.loads(replacement.stdout)["result"]["row_index"])
    assert int(replacement_row) > int(row)
    removed = profile_cli("remove-row", "activities", replacement_row)
    assert removed.exit_code == 0, removed.output
    assert f"activities.{replacement_row}.description" not in profile_facts()
