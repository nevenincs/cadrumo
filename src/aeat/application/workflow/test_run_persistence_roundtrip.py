"""Strict roundtrip across the encrypted workflow-runs boundary.

``save_run`` / ``load_run`` persist :class:`WorkflowResult` records at
``SensitivityClass.FINANCIAL`` under the ``aeat.application.workflow.runs``
namespace. Flagged as untested in the persistence-boundary identity
audit.

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

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ._models import (
    WorkflowAbortReason,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
)
from ._persistence import load_run, save_run

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


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
                details={"modelo": "303", "period": "2025Q1", "closes_on": "2025-04-20"},
            ),
        ),
        summary="run aborted: deadline for 303/2025Q1 passed",
        resumed_from="p" * 16,
    )


def test_workflow_run_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A WorkflowResult saved via save_run loads back strictly equal."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "workflow-run-roundtrip.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)

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
        assert details.get("period") == "2025Q1"
        assert details.get("closes_on") == "2025-04-20"
    finally:
        engine.dispose()
        override_master_key_provider(None)
