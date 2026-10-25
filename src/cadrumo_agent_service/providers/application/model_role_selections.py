"""The person's model selection per role, and their guarded changes.

The service is bound to one profile's selections store, which keeps the record
in a capability of its own, apart from the provider records. It reads every
role in one answer and performs the person's acts:

* select a lane and model for one role, replacing that role's earlier choice;
* clear one role's selection;
* reset the record, readable or not, at the revision the caller read.

Every change carries the revision the caller read as its guard, is committed
with a compare-and-swap and is read back. A lane must be one the agent
reports; whether it is reachable is decided when a run asks for it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from pydantic import TypeAdapter, ValidationError

from cadrumo.core.model_catalogue import ModelRole
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.core.time.clock import now

from ..domain.catalog import ProviderCatalogEntry
from ..domain.record import (
    MODEL_ROLE_SELECTIONS_RECORD_SCHEMA_VERSION,
    ModelId,
    ModelRoleSelection,
    ModelRoleSelectionsRecord,
    new_settings_generation,
)
from .contracts import (
    ModelRoleSelectionEntry,
    ModelRoleSelectionsResult,
    ModelRoleSelectionsStatus,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    is_provider_settings_revision,
)
from .ports import (
    AbsentModelRoleSelections,
    ModelRoleSelectionsRead,
    ModelRoleSelectionsStore,
    ProviderCatalogSource,
    ProviderCatalogUnavailableError,
    StoredModelRoleSelections,
    StoreRefusal,
    UnreadableModelRoleSelections,
)


class ModelRoleSelectionsService:
    """Every role's selection and the person's guarded changes, for one admitted profile."""

    def __init__(
        self,
        *,
        store: ModelRoleSelectionsStore,
        catalog_source: ProviderCatalogSource,
        clock: Callable[[], datetime] = now,
    ) -> None:
        """Bind the service to one profile's selections store and the agent's catalog."""
        self._store = store
        self._catalog_source = catalog_source
        self._clock = clock

    def status(self) -> ModelRoleSelectionsResult:
        """Return every role and the person's selection for it, or a typed refusal."""
        read = self._store.read()
        if isinstance(read, StoreRefusal):
            return _refused(ProviderSettingsRefusalCode(read.code.value))
        return _selections_status(read)

    def select(self, role: str, *, lane: str, model: str, expected_revision: str) -> ModelRoleSelectionsResult:
        """Select ``lane`` and ``model`` for ``role``, replacing any earlier selection for that role only.

        The lane must be one the agent reports. Whether it is reachable is
        decided when a run asks for it, so a lane can be chosen before its
        credential is stored.
        """
        model_role = _model_role(role)
        if model_role is None or not _is_model_id(model):
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        entry = self._lane(lane)
        if isinstance(entry, ProviderSettingsRefusal):
            return entry
        current = self._current(expected_revision)
        if isinstance(current, ProviderSettingsRefusal):
            return current
        kept = tuple(selection for selection in current if selection.role is not model_role)
        chosen = ModelRoleSelection(role=model_role, lane=entry.id, model=model)
        return self._commit((*kept, chosen), expected_revision)

    def clear(self, role: str, *, expected_revision: str) -> ModelRoleSelectionsResult:
        """Remove the selection for ``role``, leaving every other role's selection as it is."""
        model_role = _model_role(role)
        if model_role is None:
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        current = self._current(expected_revision)
        if isinstance(current, ProviderSettingsRefusal):
            return current
        kept = tuple(selection for selection in current if selection.role is not model_role)
        return self._commit(kept, expected_revision)

    def reset(self, *, expected_revision: str) -> ModelRoleSelectionsResult:
        """Delete the selections record, readable or not, at the revision the caller read."""
        if not is_provider_settings_revision(expected_revision):
            return _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)
        refusal = self._store.delete(expected_revision=expected_revision)
        if refusal is not None:
            return _refused(ProviderSettingsRefusalCode(refusal.code.value))
        read = self._store.read()
        if not isinstance(read, AbsentModelRoleSelections):
            return _refused(ProviderSettingsRefusalCode.COMMITTED_READBACK_FAILED)
        return _selections_status(read)

    def _current(self, expected_revision: str) -> tuple[ModelRoleSelection, ...] | ProviderSettingsRefusal:
        """Read the readable selections and check the caller's guard against their revision."""
        if not is_provider_settings_revision(expected_revision):
            return _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)
        read = self._store.read()
        if isinstance(read, StoreRefusal):
            return _refused(ProviderSettingsRefusalCode(read.code.value))
        if isinstance(read, UnreadableModelRoleSelections):
            # Only a guarded reset may replace a record nobody can read.
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        if _selections_revision(read) != expected_revision:
            return _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)
        return read.record.selections if isinstance(read, StoredModelRoleSelections) else ()

    def _commit(self, selections: tuple[ModelRoleSelection, ...], expected_revision: str) -> ModelRoleSelectionsResult:
        order = {role: index for index, role in enumerate(ModelRole)}
        record = ModelRoleSelectionsRecord(
            schema_version=MODEL_ROLE_SELECTIONS_RECORD_SCHEMA_VERSION,
            selections=tuple(sorted(selections, key=lambda selection: order[selection.role])),
            generation=new_settings_generation(),
            updated_at=self._clock(),
        )
        refusal = self._store.write(record, expected_revision=expected_revision)
        if refusal is not None:
            return _refused(ProviderSettingsRefusalCode(refusal.code.value))
        read = self._store.read()
        if not isinstance(read, StoredModelRoleSelections) or read.record.generation != record.generation:
            return _refused(ProviderSettingsRefusalCode.COMMITTED_READBACK_FAILED)
        return _selections_status(read)

    def _lane(self, lane: str) -> ProviderCatalogEntry | ProviderSettingsRefusal:
        """Return the lane the agent reports under ``lane``, or the refusal that stopped the lookup."""
        try:
            entry = self._catalog_source.catalog().entry(lane)
        except ProviderCatalogUnavailableError:
            return _refused(ProviderSettingsRefusalCode.CATALOG_UNAVAILABLE)
        return _refused(ProviderSettingsRefusalCode.UNKNOWN) if entry is None else entry


def _model_role(role: str) -> ModelRole | None:
    try:
        return ModelRole(role)
    except ValueError:
        return None


def _is_model_id(model: str) -> bool:
    try:
        TypeAdapter(ModelId).validate_python(model)
    except ValidationError:
        return False
    return True


def _selections_revision(read: ModelRoleSelectionsRead) -> str | None:
    if isinstance(read, AbsentModelRoleSelections):
        return ABSENT_SECURE_OBJECT_REVISION_ID
    return read.revision


def _selections_status(read: ModelRoleSelectionsRead) -> ModelRoleSelectionsStatus:
    """Project a selections read onto every role, in role-vocabulary order."""
    if isinstance(read, UnreadableModelRoleSelections):
        return ModelRoleSelectionsStatus(unreadable=True, roles=(), revision=read.revision)
    record = read.record if isinstance(read, StoredModelRoleSelections) else None
    entries: list[ModelRoleSelectionEntry] = []
    for role in ModelRole:
        selection = record.selection(role) if record is not None else None
        entries.append(
            ModelRoleSelectionEntry(
                role=role,
                lane=selection.lane if selection is not None else None,
                model=selection.model if selection is not None else None,
            )
        )
    return ModelRoleSelectionsStatus(unreadable=False, roles=tuple(entries), revision=_selections_revision(read))


def _refused(code: ProviderSettingsRefusalCode) -> ProviderSettingsRefusal:
    return ProviderSettingsRefusal(code=code)


__all__ = ["ModelRoleSelectionsService"]
