"""Real CLI coverage for the schema-owned repeatable profile-row door."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....tests.cli_envelope import unwrap_schema_envelope
from .....tests.cli_runner import invoke_typer_app
from .....tests.profile_storage_root_fixture import profile_storage_root_fixture
from .....tests.user_profile import register_cli_profile
from ... import app as root_app

__all__ = ["profile_storage_root_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]


def _show_values() -> dict[str, str]:
    """Read the persisted facts back through the public profile-show door."""
    shown = invoke_typer_app(root_app, ["--format", "json", "config", "profile", "show"])
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
