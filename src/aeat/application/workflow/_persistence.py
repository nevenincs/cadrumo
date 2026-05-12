"""Encrypted persistence for WorkflowState."""

from __future__ import annotations

from collections.abc import Callable
from typing import Self

from ...adapters.persistence.storage.envelope._envelope import Envelope
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.classification import SensitivityClass
from ...core.config import Settings
from ...core.logging import get_logger
from ._models import WorkflowState, utc_now

_logger = get_logger(__name__)

_STATE_VERSION = 1
_STATE_NAMESPACE = "aeat.workflow"
_STATE_OBJECT_KEY = "state"


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
        envelope = Envelope[WorkflowState].model_validate_json(record.payload.decode("utf-8"))
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

    def save(self, state: WorkflowState) -> None:
        """Persist state in the encrypted database object store."""

        envelope = Envelope[WorkflowState](
            schema_version=_STATE_VERSION,
            written_at=utc_now(),
            classification=SensitivityClass.FINANCIAL,
            payload=state.model_copy(update={"updated_at": utc_now()}),
        )
        self._objects.save(
            namespace=_STATE_NAMESPACE,
            object_key=_STATE_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_STATE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _logger.debug("persisted workflow state to secure backend")

    def update(self, fn: Callable[[WorkflowState], WorkflowState]) -> WorkflowState:
        """Load, transform, save, and return the updated state."""

        state = self.load()
        updated = fn(state)
        self.save(updated)
        return updated


def workflow_state_repository(settings: Settings | None = None) -> WorkflowStateRepository:
    """Return the repository bound to the configured run-state directory."""

    return WorkflowStateRepository.from_settings(settings)
