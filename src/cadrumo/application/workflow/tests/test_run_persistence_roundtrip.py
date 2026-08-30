"""Strict roundtrip across the encrypted workflow-runs boundary.

``save_run`` / ``load_run`` persist :class:`WorkflowResult` records at
``SensitivityClass.FINANCIAL`` under the ``cadrumo.application.workflow.runs``
namespace.

Anti-tautology discipline: final_stage flipped to ABORTED so
``aborted_reason`` must be populated (the model_validator enforces
the pairing). Two WorkflowStep entries cover the steps tuple. A
``resumed_from`` run-id is set to exercise the optional resume-chain
field.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import (
    WORKFLOW_RUN_NAMESPACE,
    ClassificationError,
    Envelope,
    EnvelopeVersionError,
    SensitivityClass,
)
from ....core import (
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    Modelo,
    NoRecoveryOutcome,
    StorageCategory,
    storage_path,
)
from ....core.period import Period
from ....core.config import override_settings
from ....core.errors.hierarchy import SiteHealthState
from ....core.external_constants import OutputLanguage
from ....domain.deadlines.models import ObligationStatus
from ....domain.submission import ModeloDraftStatus
from ....tests.secure_sql import isolated_runtime_profile
from ...operator_actions import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
)
from ..errors import WorkflowError
from ..persistence import WorkflowRunRepository, load_run, save_run
from ..run_models import (
    SiteHealthAlert,
    WorkflowAbortReason,
    WorkflowDeadlineContextDetails,
    WorkflowDeadlineRecoveryFacts,
    WorkflowDraftNotReadyDetails,
    WorkflowFailureDetails,
    WorkflowObligationFacts,
    WorkflowResult,
    WorkflowSiteHealthFacts,
    WorkflowStage,
    WorkflowStep,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RUN_ENDED_AT = datetime(2026, 5, 25, 14, 0, 0, tzinfo=UTC)
_RUN_STARTED_AT = _RUN_ENDED_AT - timedelta(minutes=10)
_SECOND_STEP_STARTED_AT = _RUN_ENDED_AT - timedelta(minutes=9)
_MUTATED_RUN_WRITTEN_AT = datetime(2026, 5, 25, 14, 5, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")


def _draft_not_ready_verdict() -> PreconditionVerdict:
    """Canonical typed refusal persisted on the terminal workflow step."""
    return PreconditionVerdict(
        failed_condition_id="workflow.draft.ready",
        evidence=(
            ConditionEvidence(
                condition_id="workflow.draft.ready",
                evidence_id="workflow.draft.status",
                provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                values={"draft_id": "d" * 64, "draft_status": "BORRADOR"},
            ),
        ),
        action=ActionReference(action_id="operator.modelo.verification_report.list"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="calculation_revision_id",
                status=ActionArgumentStatus.MISSING,
            ),
        ),
        missing_argument_names=("calculation_revision_id",),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def _populated_run() -> WorkflowResult:
    """WorkflowResult with non-default values on every defaultable field."""

    return WorkflowResult(
        run_id="r" * 16,
        started_at=_RUN_STARTED_AT,
        ended_at=_RUN_ENDED_AT,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=WorkflowAbortReason.DEADLINE_PASSED,
        obligation=WorkflowObligationFacts(
            modelo=Modelo.M303,
            period=_PERIOD,
            opens_on=date(2025, 4, 1),
            closes_on=date(2025, 4, 20),
            payment_cutoff_on=date(2025, 4, 15),
            status=ObligationStatus.OVERDUE,
            boe_references=("ley-58-2003:art-27.2",),
            recovery=WorkflowDeadlineRecoveryFacts(
                still_filable=True,
                recargo_band_id="completed_months_2",
                min_completed_months=2,
                max_completed_months=2,
                surcharge_pct=Decimal("3.00"),
                interest_applies=False,
                legal_ref="ley-58-2003:art-27.2",
            ),
        ),
        draft_id="d" * 64,
        submission_id=None,
        steps=(
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=_RUN_STARTED_AT,
                ended_at=_SECOND_STEP_STARTED_AT,
                success=True,
                summary_locale_key="application.workflow.steps.profile_loaded",
                details=WorkflowDeadlineContextDetails(
                    kind="deadline_context",
                    modelo=Modelo.M303,
                    period=_PERIOD,
                    opens_on=date(2025, 4, 1),
                    closes_on=date(2025, 4, 20),
                ),
            ),
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=_SECOND_STEP_STARTED_AT,
                ended_at=_RUN_ENDED_AT,
                success=False,
                summary_locale_key="application.workflow.steps.draft_not_ready",
                details=WorkflowDraftNotReadyDetails(
                    kind="draft_not_ready",
                    draft_id="d" * 64,
                    draft_status=ModeloDraftStatus.BORRADOR,
                    blocking_finding_codes=("modelo.required_binding", "modelo.schema_mismatch"),
                ),
                precondition_verdict=_draft_not_ready_verdict(),
            ),
        ),
        summary_locale_key="application.workflow.results.aborted",
        summary_details=WorkflowDeadlineContextDetails(
            kind="deadline_context",
            modelo=Modelo.M303,
            period=_PERIOD,
            closes_on=date(2025, 4, 20),
        ),
        resumed_from="p" * 16,
    )


def _operationally_aborted_run() -> WorkflowResult:
    """An operational abort with the resumable closed operator-decision verdict."""
    terminal_verdict = PreconditionVerdict(
        failed_condition_id="workflow.execution.completed",
        evidence=(
            ConditionEvidence(
                condition_id="workflow.execution.completed",
                evidence_id="workflow.execution.error_code",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values={"error_code": "workflow.runtime.failure"},
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
    return WorkflowResult(
        run_id="o" * 16,
        started_at=_RUN_STARTED_AT,
        ended_at=_RUN_ENDED_AT,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=WorkflowAbortReason.UNHANDLED_EXCEPTION,
        steps=(
            WorkflowStep(
                stage=WorkflowStage.RUNNING_PREFLIGHT,
                started_at=_RUN_STARTED_AT,
                ended_at=_RUN_ENDED_AT,
                success=False,
                summary_locale_key="application.workflow.steps.workflow_failure",
                details=WorkflowFailureDetails(
                    kind="workflow_failure",
                    error_code="workflow.runtime.failure",
                ),
                precondition_verdict=terminal_verdict,
            ),
        ),
        summary_locale_key="application.workflow.results.aborted",
        summary_details=WorkflowFailureDetails(
            kind="workflow_failure",
            error_code="workflow.runtime.failure",
        ),
    )


def _workflow_run_v2_envelope_bytes(
    result: WorkflowResult,
    *,
    schema_version: int,
    classification: SensitivityClass,
) -> bytes:
    """Return committed v2 bytes carrying the retired domain deadline shape."""
    envelope = Envelope[WorkflowResult](
        schema_version=schema_version,
        written_at=_MUTATED_RUN_WRITTEN_AT,
        classification=classification,
        payload=result,
    )
    legacy = json.loads(envelope.model_dump_json())
    payload = legacy["payload"]
    obligation = payload["obligation"]
    assert obligation is not None
    obligation["applies_because"] = "Source-language applicability explanation"
    recovery = obligation["recovery"]
    assert recovery is not None
    recovery["recargo_band"] = {
        "id": recovery.pop("recargo_band_id"),
        "min_completed_months": recovery.pop("min_completed_months"),
        "max_completed_months": recovery.pop("max_completed_months"),
        "surcharge_pct": recovery.pop("surcharge_pct"),
        "interest_applies": recovery.pop("interest_applies"),
        "legal_ref": recovery.pop("legal_ref"),
    }
    recovery["next_command"] = "aeat app modelo work calculate WORK_UNIT_ID"
    return json.dumps(legacy).encode("utf-8")


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
        # details (retyped from dict[str, str] to the
        # WorkflowStepDetails envelope), and the optional
        # resumed_from chain pointer.
        assert loaded.final_stage is WorkflowStage.ABORTED
        assert loaded.aborted_reason is WorkflowAbortReason.DEADLINE_PASSED
        assert loaded.resumed_from == "p" * 16
        assert len(loaded.steps) == 2
        assert loaded.steps[1].success is False
        # The v3 run record preserves typed facts and the canonical
        # precondition verdict without persisting rendered prose.
        details = loaded.steps[1].details
        assert details is not None
        assert details.kind == "draft_not_ready"
        assert details.draft_id == "d" * 64
        assert details.draft_status is ModeloDraftStatus.BORRADOR
        assert details.blocking_finding_codes == ("modelo.required_binding", "modelo.schema_mismatch")
        assert loaded.steps[1].precondition_verdict == _draft_not_ready_verdict()
        assert loaded.summary_locale_key == "application.workflow.results.aborted"
        assert WORKFLOW_RUN_NAMESPACE.schema_version == 3


def test_site_health_projection_survives_encrypted_roundtrip_without_source_evidence(
    tmp_path: Path,
) -> None:
    """Only stable site-health facts survive workflow-run persistence."""
    original = _operationally_aborted_run()
    expected_status = WorkflowSiteHealthFacts(
        alert_code="workflow.site.rate_limited",
        state=SiteHealthState.RATE_LIMITED,
        observed_at=_RUN_ENDED_AT,
        http_status=429,
        retry_after_seconds=30,
        detected_marker_count=2,
    )
    failed_step = original.steps[0].model_copy(
        update={
            "summary_locale_key": "application.workflow.steps.site_unavailable",
            "site_health_alert": SiteHealthAlert(
                stage=WorkflowStage.RUNNING_PREFLIGHT,
                status=expected_status,
                run_id=original.run_id,
            ),
        },
    )
    original = original.model_copy(
        update={
            "aborted_reason": WorkflowAbortReason.SITE_UNAVAILABLE,
            "steps": (failed_step,),
        },
    )

    with isolated_runtime_profile(tmp_path=tmp_path):
        save_run(original)
        loaded = load_run(original.run_id)

    alert = loaded.steps[0].site_health_alert
    assert alert is not None
    assert alert.status == expected_status
    assert set(alert.status.model_dump()) == {
        "alert_code",
        "state",
        "observed_at",
        "http_status",
        "retry_after_seconds",
        "detected_marker_count",
    }


def test_workflow_run_serialization_is_output_language_invariant() -> None:
    """Persisted locale keys and typed facts have one digest in every locale."""
    digests: set[str] = set()
    for language in OutputLanguage:
        with override_settings(cadrumo_output_language=language):
            payload = _populated_run().model_dump_json().encode("utf-8")
        digests.add(hashlib.sha256(payload).hexdigest())

    assert len(digests) == 1


def test_workflow_run_persists_only_to_the_secure_database_object(
    tmp_path: Path,
) -> None:
    """A saved run never reaches the plaintext ``workflow-runs`` directory.

    :data:`StorageCategory.WORKFLOW_RUNS` names
    ``application/workflow/_persistence.py`` as its consumer, not
    the deleted rotation sweep -- but that module's own ``save_run`` docstring states
    why: "``runs_dir`` remains part of the API as a logical marker path for
    callers and tests, but no plaintext run file is written there." The
    Path ``WorkflowRunRepository.save`` returns is a caller-facing marker
    built from that settings field, never something the method itself
    writes to; the only real write goes to the encrypted secure-object
    backend. The master-key rotation sweep used to list
    ``cadrumo_workflow_runs_dir`` as a plan entry (a re-encryption target the
    directory could hold), which is why the category shares the architecture
    of the categories that sweep was the ONLY consumer of, despite declaring a
    different one; those siblings are now declared dormant, and this one is
    not, because ``_persistence.py`` really does consume it. This proves the claim directly, mirroring
    ``test_put_file_reads_source_but_persists_only_secure_database_object``
    for the attachments store. The assertion routes through
    :func:`storage_path` rather than a literal so a future taxonomy
    subpath move is tracked automatically instead of silently passing
    vacuously against a stale path.
    """

    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _populated_run()
        save_run(original)

        assert load_run(original.run_id) == original
        assert not storage_path(StorageCategory.WORKFLOW_RUNS).exists()


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

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        objects = profile.repository
        original = _populated_run()
        save_run(original)

        # Sanity: the run is loadable through the runtime repository.
        loaded = objects.load(
            WORKFLOW_RUN_NAMESPACE.namespace,
            original.run_id,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=WORKFLOW_RUN_NAMESPACE.schema_version,
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
            namespace=WORKFLOW_RUN_NAMESPACE.namespace,
            object_key=original.run_id,
            classification=SensitivityClass.FINANCIAL,
            schema_version=WORKFLOW_RUN_NAMESPACE.schema_version,
            written_at=_MUTATED_RUN_WRITTEN_AT,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        # load_run must trip the ABORTED ↔ aborted_reason invariant.
        with pytest.raises(ValidationError):
            load_run(original.run_id)


def test_operationally_aborted_run_roundtrips_with_resumable_no_recovery_verdict(tmp_path: Path) -> None:
    """Operational aborts preserve the explicit non-terminal operator decision."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _operationally_aborted_run()
        save_run(original)

        loaded = load_run(original.run_id)
        assert loaded == original
        assert loaded.steps[-1].precondition_verdict is not None
        assert loaded.steps[-1].precondition_verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_workflow_run_v2_is_refused_before_locale_neutral_v3_hydration(tmp_path: Path) -> None:
    """A committed v2 run is refused before its language-bearing obligation hydrates."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        original = _populated_run()
        repository = WorkflowRunRepository(objects=profile.repository)
        old_version = 2
        payload = _workflow_run_v2_envelope_bytes(
            original,
            schema_version=old_version,
            classification=WORKFLOW_RUN_NAMESPACE.sensitivity,
        )
        with pytest.raises(ValidationError):
            Envelope[WorkflowResult].model_validate_json(payload)
        profile.repository.save(
            namespace=WORKFLOW_RUN_NAMESPACE.namespace,
            object_key=original.run_id,
            classification=WORKFLOW_RUN_NAMESPACE.sensitivity,
            # The registered write boundary correctly refuses an outer v2 row.
            # Persist a current outer row whose decrypted inner envelope claims
            # v2 so the production workflow loader's exact-version check is
            # exercised directly rather than short-circuited by the substrate.
            schema_version=WORKFLOW_RUN_NAMESPACE.schema_version,
            written_at=_MUTATED_RUN_WRITTEN_AT,
            payload=payload,
        )

        with pytest.raises(EnvelopeVersionError, match=r"requires 3"):
            repository.load(original.run_id)
        with pytest.raises(EnvelopeVersionError, match=r"requires 3"):
            repository.list()


def test_workflow_run_inner_classification_is_refused_before_v3_hydration(tmp_path: Path) -> None:
    """A wrong inner classification never reaches the typed workflow-result reader."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        original = _populated_run()
        repository = WorkflowRunRepository(objects=profile.repository)
        payload = _workflow_run_v2_envelope_bytes(
            original,
            schema_version=WORKFLOW_RUN_NAMESPACE.schema_version,
            classification=SensitivityClass.OPERATIONAL,
        )
        with pytest.raises(ValidationError):
            Envelope[WorkflowResult].model_validate_json(payload)
        profile.repository.save(
            namespace=WORKFLOW_RUN_NAMESPACE.namespace,
            object_key=original.run_id,
            classification=WORKFLOW_RUN_NAMESPACE.sensitivity,
            schema_version=WORKFLOW_RUN_NAMESPACE.schema_version,
            written_at=_MUTATED_RUN_WRITTEN_AT,
            payload=payload,
        )

        with pytest.raises(ClassificationError):
            repository.load(original.run_id)
        with pytest.raises(ClassificationError):
            repository.list()


class TestRunOwnsItsRow:
    """A run is returned only from the key its own id derives.

    ``save`` files each run under its own ``run_id``, so the secure-object key
    IS the run's durable identity -- nothing else in the row asserts it. The
    read paths validated envelope class and version only, so a valid run B
    re-encrypted under A's key was returned by ``load(A)`` and enumerated by
    ``list()`` under A's key with no typed mismatch. Resume and history readers
    consume exactly those results.
    """

    _RUN_A = "a" * 16
    _RUN_B = "b" * 16

    def _run(self, run_id: str) -> WorkflowResult:
        return _populated_run().model_copy(update={"run_id": run_id, "resumed_from": None})

    def _rekey(self, repo: WorkflowRunRepository, *, payload_run_id: str, under_key: str) -> None:
        """Write run ``payload_run_id``'s genuine envelope under a foreign key."""
        envelope = Envelope[WorkflowResult](
            schema_version=WORKFLOW_RUN_NAMESPACE.schema_version,
            written_at=_MUTATED_RUN_WRITTEN_AT,
            classification=WORKFLOW_RUN_NAMESPACE.sensitivity,
            payload=self._run(payload_run_id),
        )
        repo._objects.save(
            namespace=WORKFLOW_RUN_NAMESPACE.namespace,
            object_key=under_key,
            classification=WORKFLOW_RUN_NAMESPACE.sensitivity,
            schema_version=WORKFLOW_RUN_NAMESPACE.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def test_load_refuses_a_foreign_run_under_the_requested_key(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path):
            repo = WorkflowRunRepository()
            self._rekey(repo, payload_run_id=self._RUN_B, under_key=self._RUN_A)

            with pytest.raises(WorkflowError):
                repo.load(self._RUN_A)

    def test_list_refuses_a_foreign_run_rather_than_enumerating_it(self, tmp_path: Path) -> None:
        """Enumeration is the wider door: it has no requested key to compare."""
        with isolated_runtime_profile(tmp_path=tmp_path):
            repo = WorkflowRunRepository()
            self._rekey(repo, payload_run_id=self._RUN_B, under_key=self._RUN_A)

            with pytest.raises(WorkflowError):
                repo.list()

    def test_a_run_stored_under_its_own_id_still_loads_and_lists(self, tmp_path: Path) -> None:
        """Anti-tautology: the refusals discriminate rather than always-refusing."""
        with isolated_runtime_profile(tmp_path=tmp_path):
            repo = WorkflowRunRepository()
            run = self._run(self._RUN_A)
            repo.save(run)

            assert repo.load(self._RUN_A) == run
            assert [item.run_id for item in repo.list()] == [self._RUN_A]

    def test_two_genuine_runs_both_survive(self, tmp_path: Path) -> None:
        """The guard must not collapse or reject distinct, correctly-keyed runs."""
        with isolated_runtime_profile(tmp_path=tmp_path):
            repo = WorkflowRunRepository()
            repo.save(self._run(self._RUN_A))
            repo.save(self._run(self._RUN_B))

            assert {item.run_id for item in repo.list()} == {self._RUN_A, self._RUN_B}
            assert repo.load(self._RUN_B).run_id == self._RUN_B
