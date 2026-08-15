"""Real-behavior tests for the single-target ``config profile delete`` verb.

Every assertion here is about POST-STATE, not merely about an exit code. A test
that only asserted a non-zero exit against this verb would pass on click's
unknown-command refusal and would therefore stay green if the verb were
unregistered again, which is exactly the failure mode this suite exists to make
impossible: the confirmed run asserts the profile is GONE from the listing, and
the preflight asserts it is STILL THERE.

The verb is destructive, so every test drives it against the isolated CLI
backend's temporary storage root and never the operator's default store.
"""

from __future__ import annotations

import json

import pytest
from click.testing import Result

from .....tests.cli_runner import invoke_cached_cli
from .....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from .....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _register(label: str, tax_id: str) -> str:
    """Register one live profile through the credential-only creation door."""
    return register_cli_profile(
        label=label,
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Test",
            "identity.surnames": "Operator",
            "identity.tax_id": tax_id,
            "activities.description": "Servicios",
            "iva.regime": "GENERAL",
        },
    )


def _registered_labels() -> set[str]:
    """Read the live profile listing back through the operator's own verb."""
    result = invoke_cached_cli(["config", "profile", "list", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    return {row["name"] for row in payload["result"]["profiles"]}


def _delete(label: str, *, confirm: bool) -> Result:
    argv = ["config", "profile", "delete", label, "--format", "json"]
    if confirm:
        argv.insert(4, "--yes")
    return invoke_cached_cli(argv)


def _two_profiles() -> tuple[str, str]:
    """Register a delete target and a second profile that takes the session.

    Registration selects the profile it creates, so the SECOND registration is
    what leaves the first one non-active and therefore deletable. A single
    profile cannot exercise the success path at all, which is itself part of
    this verb's contract rather than a fixture inconvenience.
    """
    _register("doomed", "00000001R")
    _register("survivor", "00000002W")
    return "doomed", "survivor"


def test_preflight_reports_the_target_and_destroys_nothing() -> None:
    """Without ``--yes`` the verb observes the target and leaves it on disk."""
    target, _ = _two_profiles()

    result = _delete(target, confirm=False)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["display_name"] == target
    assert payload["deleted"] is False
    assert payload["completed_at"] is None
    # The observation is real, not a placeholder: the fingerprint counts files
    # the capsule actually holds, so a preflight that never reached the
    # assessment could not populate it.
    assert payload["fingerprint"]["file_count"] >= 1
    assert target in _registered_labels()


def test_confirmed_delete_destroys_the_named_profile_only() -> None:
    """``--yes`` destroys the named capsule and leaves every other one intact."""
    target, survivor = _two_profiles()

    result = _delete(target, confirm=True)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["deleted"] is True
    assert payload["completed_at"] is not None
    remaining = _registered_labels()
    assert target not in remaining
    assert survivor in remaining


def test_deleting_the_active_profile_is_refused_and_the_profile_survives() -> None:
    """The capsule a live session is bound to is refused, not destroyed."""
    _, active = _two_profiles()

    result = _delete(active, confirm=True)

    assert result.exit_code != 0, result.output
    assert active in _registered_labels()


def test_unknown_profile_is_refused_by_name() -> None:
    """A label naming no live profile refuses rather than deleting something else."""
    target, survivor = _two_profiles()

    result = _delete("no-such-profile", confirm=True)

    assert result.exit_code != 0, result.output
    assert _registered_labels() == {target, survivor}


def test_preflight_then_confirm_report_the_same_observation() -> None:
    """The two postures share one schema, so a caller can diff them field for field."""
    target, _ = _two_profiles()

    preflight = json.loads(_delete(target, confirm=False).output)["result"]
    confirmed = json.loads(_delete(target, confirm=True).output)["result"]

    assert preflight["profile_id"] == confirmed["profile_id"]
    assert preflight["fingerprint"] == confirmed["fingerprint"]
    assert preflight["retained_record_count"] == confirmed["retained_record_count"]
    assert (preflight["deleted"], confirmed["deleted"]) == (False, True)
