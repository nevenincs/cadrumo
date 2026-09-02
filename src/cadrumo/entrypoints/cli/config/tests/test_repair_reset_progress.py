"""CLI tests for ``aeat config repair reset-progress``."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from .....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from .....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from .....application.workflow.persistence import workflow_state_repository
from .....application.workflow.state_models import WorkflowState
from .....domain.buckets.event import BucketEventType
from .....tests.cli_runner import invoke_cached_cli
from .....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from .....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SEEDED_PROGRESS_AT = datetime(2026, 3, 11, 7, 45, 13, tzinfo=UTC)
"""A stamp no default construction produces, so the seeded row is distinguishable."""


def _seed_workflow_state() -> None:
    """Create an active profile and save the progress row this verb discards.

    The progress row is written HERE rather than left to profile creation.
    Creation used to leave one behind as a side effect of the scripted setup
    flow, and these cases relied on that; the credential door that replaced it
    writes no workflow state, which is correct -- a profile that was just
    created has no interrupted command to resume. Relying on the side effect
    left the subject of every case below absent, so ``reset-progress`` was
    previewing nothing and reporting it accurately.
    """

    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Test",
            "identity.surnames": "Operator",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "identity.tax_id": "00000000T",
            "activities.description": "Servicios",
        },
    )
    # A non-default state, so a save-drops-field regression cannot hide behind
    # a row that is indistinguishable from the empty one the reader returns
    # when nothing is stored.
    workflow_state_repository().save(WorkflowState(updated_at=_SEEDED_PROGRESS_AT))


def _row_exists() -> bool:
    return secure_object_repository_for_active_bucket().exists("cadrumo.workflow", "state")


def _assert_operator_text_avoids_storage_terms(output: str) -> None:
    lowered = output.lower()
    forbidden_terms = ("workflow state", "workflow-state", "envelope", "fingerprint", "bucket")
    for term in forbidden_terms:
        assert term not in lowered


def _normalise_help_text(output: str) -> str:
    return " ".join(output.split())


def test_reset_progress_help_uses_operator_progress_wording() -> None:
    result = invoke_cached_cli(["config", "repair", "reset-progress", "--help"])

    assert result.exit_code == 0, result.output
    normalised = _normalise_help_text(result.output)
    assert (
        "saved interrupted-command progress" in normalised
        or "progreso guardado de un comando interrumpido" in normalised
    )
    _assert_operator_text_avoids_storage_terms(result.output)


def test_reset_progress_text_output_uses_operator_labels_not_storage_labels() -> None:
    _seed_workflow_state()

    result = invoke_cached_cli(["config", "repair", "reset-progress", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "progress_schema_version\t1" in result.output
    assert "stored_bytes\t" in result.output
    assert "read_status\treadable" in result.output
    _assert_operator_text_avoids_storage_terms(result.output)


def test_reset_progress_dry_run_returns_fingerprint_without_deleting_row() -> None:
    _seed_workflow_state()

    result = invoke_cached_cli(["--format", "json", "config", "repair", "reset-progress", "--dry-run"])

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "config.repair.reset_progress"
    payload = envelope["result"]
    assert payload["dry_run"] is True
    fingerprint = payload["fingerprint"]
    assert fingerprint["schema_version"] == 1
    assert fingerprint["byte_length"] is not None and fingerprint["byte_length"] > 0
    # A freshly-seeded, healthy workflow-state envelope must classify as
    # ``readable`` — the dry-run preview must not slander a sound
    # envelope as ``unreadable``.
    assert fingerprint["reason_class"] == "readable"
    assert _row_exists()


def test_reset_progress_without_yes_or_dry_run_raises_refusal_and_keeps_row() -> None:
    _seed_workflow_state()

    result = invoke_cached_cli(["config", "repair", "reset-progress"])

    assert result.exit_code != 0
    assert _row_exists()


def test_reset_progress_with_yes_deletes_row_emits_event_and_reload_is_empty() -> None:
    _seed_workflow_state()
    history_before = len(BucketEventHistoryRepository().load().events)

    result = invoke_cached_cli(["--format", "json", "config", "repair", "reset-progress", "--yes"])

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "config.repair.reset_progress"
    payload = envelope["result"]
    assert payload["dry_run"] is False
    # The seeded envelope is healthy, so the reset fingerprint records
    # ``readable`` — the operator reset a sound envelope deliberately,
    # not because it was corrupt.
    assert payload["fingerprint"]["reason_class"] == "readable"

    assert not _row_exists()

    catalogue = BucketEventHistoryRepository().load()
    reset_events = [
        event for event in catalogue.events.values() if event.event_type is BucketEventType.WORKFLOW_STATE_RESET
    ]
    assert len(reset_events) == 1
    assert len(catalogue.events) == history_before + 1

    reloaded = workflow_state_repository().load()
    fresh = WorkflowState()
    assert reloaded.model_dump(exclude={"updated_at"}) == fresh.model_dump(exclude={"updated_at"})


def test_retired_reset_state_verb_no_longer_resolves() -> None:
    """The pre-D1 ``reset-state`` verb is a hard rename, not an alias.

    Per the D1 operator-surface policy the retired spelling must fail to
    resolve at the click tree — no shim, no deprecation path. A click
    "No such command" exit guards against a silent re-introduction.
    """

    result = invoke_cached_cli(["config", "repair", "reset-state", "--dry-run"])

    assert result.exit_code != 0
    assert "No such command" in result.output or "reset-state" in result.output
