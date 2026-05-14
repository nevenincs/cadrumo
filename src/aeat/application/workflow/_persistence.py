"""Encrypted persistence for workflow state and workflow runs."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Self

from pydantic import ValidationError

from ...adapters.persistence.storage.envelope._envelope import Envelope
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.classification import SensitivityClass
from ...core.config import Settings
from ...core.logging import get_logger
from ._errors import WorkflowError
from ._events import (
    WorkflowStateResetFingerprint,
    emit_workflow_state_reset,
)
from ._models import WorkflowResult, WorkflowState, utc_now

_logger = get_logger(__name__)

_STATE_VERSION = 1
_STATE_NAMESPACE = "aeat.workflow"
_STATE_OBJECT_KEY = "state"
_RUN_VERSION = 1
_RUN_NAMESPACE = "aeat.application.workflow.runs"


def _clear_output_language_cache() -> None:
    try:
        from ...core.i18n._render import clear_output_language_cache
    except Exception:  # pragma: no cover - cache invalidation must never block persistence
        _logger.debug("workflow persistence could not import i18n cache invalidator", exc_info=True)
        return
    clear_output_language_cache()


class WorkflowStateRepository:
    """Encrypted SQL object repository for :class:`WorkflowState`."""

    def __init__(self) -> None:
        self._objects = SecureObjectRepository()

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Self:
        del settings
        return cls()

    def load(self) -> WorkflowState:
        """Load state or return an empty payload when absent."""

        record = self._objects.load(
            _STATE_NAMESPACE,
            _STATE_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_STATE_VERSION,
        )
        if record is None:
            return WorkflowState()
        raw_payload = record.payload.decode("utf-8")
        try:
            envelope = Envelope[WorkflowState].model_validate_json(raw_payload)
        except ValidationError as exc:
            migrated = self._migrate_legacy_inline_profiles(raw_payload)
            if migrated is not None:
                self.save(migrated)
                return migrated
            raise WorkflowError(
                "Local configuration state could not be read.",
            ) from exc
        if envelope.classification is not SensitivityClass.FINANCIAL:
            raise ClassificationError(
                f"workflow state has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.FINANCIAL}",
            )
        if envelope.schema_version > _STATE_VERSION:
            raise EnvelopeVersionError(
                f"workflow state is at version {envelope.schema_version}; consumer supports up to {_STATE_VERSION}",
            )
        return envelope.payload

    def _migrate_legacy_inline_profiles(self, raw_payload: str) -> WorkflowState | None:
        """Move legacy inline profile values into profile buckets.

        Older workflow-state records stored profile values directly under
        ``payload.profiles.<name>``. Current state stores only bucket pointers
        there. This migration preserves recoverable values while preventing a
        pydantic validation traceback from crossing the CLI boundary.
        """

        try:
            envelope = json.loads(raw_payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(envelope, dict):
            return None
        if envelope.get("classification") != SensitivityClass.FINANCIAL.value:
            return None
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            return None
        profiles = payload.get("profiles")
        if not isinstance(profiles, dict):
            return None

        from ..profile._models import ProfileRecord
        from ..profile._repository import profile_bucket_id, profile_bucket_repository
        from ._utils import _normalise_key

        profile_repository = profile_bucket_repository()
        migrated_profiles: dict[str, dict[str, str]] = {}
        active_profile_map: dict[str, str] = {}
        saw_inline_profile = False
        for raw_name, raw_entry in profiles.items():
            if not isinstance(raw_name, str) or not isinstance(raw_entry, dict):
                return None
            if isinstance(raw_entry.get("bucket_id"), str):
                bucket_id = raw_entry["bucket_id"].strip()
                if not bucket_id:
                    return None
                migrated_profiles[raw_name] = {"bucket_id": bucket_id}
                active_profile_map[raw_name] = raw_name
                continue
            try:
                bucket_id = profile_bucket_id(raw_name)
            except ValueError:
                return None
            values = {
                _normalise_key(str(key)): str(value).strip()
                for key, value in raw_entry.items()
                if value is not None and str(value).strip()
            }
            profile_repository.save(ProfileRecord(name=bucket_id, values=values))
            migrated_profiles[bucket_id] = {"bucket_id": bucket_id}
            active_profile_map[raw_name] = bucket_id
            saw_inline_profile = True

        if not saw_inline_profile:
            return None
        migrated_payload = dict(payload)
        migrated_payload["profiles"] = migrated_profiles
        active_profile = migrated_payload.get("active_profile")
        if isinstance(active_profile, str):
            migrated_payload["active_profile"] = active_profile_map.get(active_profile, active_profile)
        return WorkflowState.model_validate_json(json.dumps(migrated_payload))

    def save(self, state: WorkflowState) -> None:
        """Persist state in the encrypted database object store."""

        try:
            payload = WorkflowState.model_validate({**state.__dict__, "updated_at": utc_now()})
        except ValueError as exc:
            raise WorkflowError(f"workflow state refused invalid payload: {exc}") from exc
        envelope = Envelope[WorkflowState](
            schema_version=_STATE_VERSION,
            written_at=utc_now(),
            classification=SensitivityClass.FINANCIAL,
            payload=payload,
        )
        self._objects.save(
            namespace=_STATE_NAMESPACE,
            object_key=_STATE_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_STATE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _clear_output_language_cache()
        _logger.debug("persisted workflow state to secure backend")

    def fingerprint_state(
        self,
        *,
        reason_class: str = "unreadable",
    ) -> WorkflowStateResetFingerprint:
        """Return a row-level fingerprint of the persisted state envelope.

        Reads row-level metadata only; never decrypts the payload. When
        no envelope is persisted the fingerprint records empty metadata
        and the supplied ``reason_class`` for the emitted event.
        """

        metadata = self._objects.peek_metadata(_STATE_NAMESPACE, _STATE_OBJECT_KEY)
        recovered_bucket_id: str | None = None
        try:
            state = self.load()
        except (WorkflowError, ClassificationError, EnvelopeVersionError, ValidationError):
            # The fingerprint path is the recovery route for an unreadable
            # envelope; surfacing the envelope failure here would defeat
            # the purpose. Fall back to row-level metadata only.
            state = None
        if state is not None:
            recovered_bucket_id = state.active_profile_bucket_id()
        if metadata is None:
            return WorkflowStateResetFingerprint(
                schema_version=None,
                written_at=None,
                byte_length=None,
                reason_class=reason_class,
                recovered_bucket_id=recovered_bucket_id,
            )
        return WorkflowStateResetFingerprint(
            schema_version=metadata.schema_version,
            written_at=metadata.written_at,
            byte_length=metadata.byte_length,
            reason_class=reason_class,
            recovered_bucket_id=recovered_bucket_id,
        )

    def reset_workflow_state(
        self,
        *,
        actor: str = "aeat.application.workflow",
        source: str = "aeat config repair reset-state",
        reason_class: str = "unreadable",
    ) -> WorkflowStateResetFingerprint:
        """Delete the workflow-state envelope and emit a reset event.

        The mutation is scoped to namespace ``aeat.workflow`` / key
        ``state``; no other namespace or row is touched. The
        ``workflow_state.reset`` bucket event is appended BEFORE the
        secure-object row is deleted so the worst-case failure mode
        leaves an audit entry with the data still present (an
        idempotent recoverable state) rather than the data discarded
        without a trail. The fingerprint never carries plaintext
        envelope content.
        """

        fingerprint = self.fingerprint_state(reason_class=reason_class)
        emit_workflow_state_reset(fingerprint=fingerprint, actor=actor, source=source)
        self._objects.delete(_STATE_NAMESPACE, _STATE_OBJECT_KEY)
        _clear_output_language_cache()
        _logger.info("workflow state envelope reset; recovery route fired by operator")
        return fingerprint

    def update(self, fn: Callable[[WorkflowState], WorkflowState]) -> WorkflowState:
        """Load, transform, save, and return the updated state."""

        state = self.load()
        updated = fn(state)
        self.save(updated)
        return updated


def workflow_state_repository(settings: Settings | None = None) -> WorkflowStateRepository:
    """Return the repository bound to the configured run-state directory."""

    return WorkflowStateRepository.from_settings(settings)


def reset_workflow_state(
    *,
    actor: str = "aeat.application.workflow",
    source: str = "aeat config repair reset-state",
    reason_class: str = "unreadable",
) -> WorkflowStateResetFingerprint:
    """Module-level helper around :meth:`WorkflowStateRepository.reset_workflow_state`."""

    return workflow_state_repository().reset_workflow_state(
        actor=actor,
        source=source,
        reason_class=reason_class,
    )


def fingerprint_workflow_state(*, reason_class: str = "unreadable") -> WorkflowStateResetFingerprint:
    """Module-level helper around :meth:`WorkflowStateRepository.fingerprint_state`."""

    return workflow_state_repository().fingerprint_state(reason_class=reason_class)


def _validate_run_id(run_id: str) -> str:
    if "/" in run_id or "\\" in run_id:
        raise WorkflowError("run_id must not contain path separators")
    trimmed = run_id.strip()
    if not trimmed:
        raise WorkflowError("run_id must not be blank")
    return trimmed


def save_run(result: WorkflowResult, *, runs_dir: Path | None = None) -> Path:
    """Persist one workflow result in the secure object backend.

    ``runs_dir`` remains part of the API as a logical marker path for callers
    and tests, but no plaintext run file is written there.
    """

    run_id = _validate_run_id(result.run_id)
    marker_dir = runs_dir or Settings().aeat_workflow_runs_dir
    envelope = Envelope[WorkflowResult](
        schema_version=_RUN_VERSION,
        written_at=utc_now(),
        classification=SensitivityClass.FINANCIAL,
        payload=result,
    )
    SecureObjectRepository().save(
        namespace=_RUN_NAMESPACE,
        object_key=run_id,
        classification=SensitivityClass.FINANCIAL,
        schema_version=_RUN_VERSION,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )
    return marker_dir / run_id


def load_run(run_id: str, *, runs_dir: Path | None = None) -> WorkflowResult:
    """Load one persisted workflow result from the secure backend."""

    del runs_dir
    safe_run_id = _validate_run_id(run_id)
    record = SecureObjectRepository().load(
        _RUN_NAMESPACE,
        safe_run_id,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=_RUN_VERSION,
    )
    if record is None:
        raise WorkflowError(f"workflow run not found: {safe_run_id}")
    envelope = Envelope[WorkflowResult].model_validate_json(record.payload.decode("utf-8"))
    if envelope.classification is not SensitivityClass.FINANCIAL:
        raise ClassificationError(
            f"workflow run has classification {envelope.classification}; "
            f"consumer expected {SensitivityClass.FINANCIAL}",
        )
    if envelope.schema_version > _RUN_VERSION:
        raise EnvelopeVersionError(
            f"workflow run is at version {envelope.schema_version}; consumer supports up to {_RUN_VERSION}",
        )
    return envelope.payload


def list_runs(*, runs_dir: Path | None = None, since: date | None = None) -> tuple[WorkflowResult, ...]:
    """List persisted workflow runs newest-first, optionally filtered by date."""

    del runs_dir
    records = SecureObjectRepository().list_records(
        _RUN_NAMESPACE,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=_RUN_VERSION,
    )
    runs: list[WorkflowResult] = []
    for record in records:
        envelope = Envelope[WorkflowResult].model_validate_json(record.payload.decode("utf-8"))
        result = envelope.payload
        if since is not None and result.started_at.date() < since:
            continue
        runs.append(result)
    runs.sort(key=lambda item: item.started_at, reverse=True)
    return tuple(runs)
