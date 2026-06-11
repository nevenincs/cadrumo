"""Strict roundtrip across the encrypted workflow-runs boundary.

``save_run`` / ``load_run`` persist :class:`WorkflowResult` records at
``SensitivityClass.FINANCIAL`` under the ``aeat.application.workflow.runs``
namespace.

Anti-tautology discipline: final_stage flipped to ABORTED so
``aborted_reason`` must be populated (the model_validator enforces
the pairing). Two WorkflowStep entries cover the steps tuple. A
``resumed_from`` run-id is set to exercise the optional resume-chain
field.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....tests.secure_sql import isolated_runtime_profile
from .._models import (
    WorkflowAbortReason,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
)
from .._persistence import load_run, save_run

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _populated_run() -> WorkflowResult:
    """WorkflowResult with non-default values on every defaultable field."""

    now = datetime.now(UTC).replace(microsecond=0)
    return WorkflowResult(
        run_id="r" * 16,
        started_at=now - timedelta(minutes=10),
        ended_at=now,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=WorkflowAbortReason.DEADLINE_PASSED,
        obligation=None,
        draft_id="d" * 64,
        submission_id=None,
        steps=(
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=now - timedelta(minutes=10),
                ended_at=now - timedelta(minutes=9),
                success=True,
                summary="loaded active profile from secure storage",
                details={"profile": "active"},
            ),
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=now - timedelta(minutes=9),
                ended_at=now,
                success=False,
                summary="deadline passed for current obligation",
                details={"modelo": "303", "period": "2025 1T", "closes_on": "2025-04-20"},
            ),
        ),
        summary="run aborted: deadline for 303/2025 1T passed",
        resumed_from="p" * 16,
    )


def test_workflow_run_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A WorkflowResult saved via save_run loads back strictly equal."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _populated_run()
        save_run(original)
        loaded = load_run(original.run_id)

        assert loaded == original
        # Per-field witnesses: enum identity (final_stage,
        # aborted_reason), tuple-of-steps surface with per-step
        # details (which were retyped from dict[str, str] to the
        # WorkflowStepDetails envelope earlier this campaign), and
        # the optional resumed_from chain pointer.
        assert loaded.final_stage is WorkflowStage.ABORTED
        assert loaded.aborted_reason is WorkflowAbortReason.DEADLINE_PASSED
        assert loaded.resumed_from == "p" * 16
        assert len(loaded.steps) == 2
        assert loaded.steps[1].success is False
        # WorkflowStepDetails accepts arbitrary string-keyed
        # diagnostics via extra="allow"; the round-trip must
        # preserve all three details keys on the second step.
        details = loaded.steps[1].details
        assert details is not None
        assert details.get("modelo") == "303"
        assert details.get("period") == "2025 1T"
        assert details.get("closes_on") == "2025-04-20"


def test_workflow_run_aborted_reason_drift_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: ABORTED ↔ aborted_reason invariant holds post-persistence.

    :class:`WorkflowResult` enforces that ABORTED final_stage MUST
    carry a non-None ``aborted_reason``. A persisted ABORTED run
    whose aborted_reason is silently cleared post-save would let an
    unjustified abort masquerade as a normal completion on replay.

    Persists via :func:`save_run`, uses :class:`SecureObjectRepository`
    public API to load the encrypted record, surgically clears
    ``aborted_reason`` in the JSON envelope payload, re-saves through
    the same Repository, and asserts :func:`load_run` rejects via
    the model_validator's stage ↔ reason pairing.

    Going through the Repository public API exercises the same
    encrypted-object boundary the production load path reads.
    """

    import json as _json

    from ....adapters.persistence.storage import SensitivityClass
    from .._persistence import _RUN_NAMESPACE, _RUN_VERSION

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        objects = profile.repository
        original = _populated_run()
        save_run(original)

        # Sanity: the run is loadable through the runtime repository.
        loaded = objects.load(
            _RUN_NAMESPACE,
            original.run_id,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_RUN_VERSION,
        )
        assert loaded is not None, (
            "save_run did not persist via the runtime repository — re-check "
            "storage route wiring before treating the proof result as meaningful"
        )

        # Decrypt, mutate, re-encrypt — through the public API.
        envelope = _json.loads(loaded.payload.decode("utf-8"))
        payload = envelope["payload"]
        assert payload.get("aborted_reason"), (
            "fixture must persist ABORTED final_stage with a populated "
            "aborted_reason for this proof test to be meaningful"
        )
        payload["aborted_reason"] = None
        envelope["payload"] = payload
        objects.save(
            namespace=_RUN_NAMESPACE,
            object_key=original.run_id,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_RUN_VERSION,
            written_at=datetime.now(UTC),
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        # load_run must trip the ABORTED ↔ aborted_reason invariant.
        with pytest.raises(ValidationError):
            load_run(original.run_id)
