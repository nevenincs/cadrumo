"""The person's local model list and the model they read documents with, and their guarded changes.

A local lane is a keyless one: the agent's catalogue admits a keyless lane only
at a loopback address, so it runs on this computer. Its model list is the
models cadrumo-agent's catalogue recommends for it, followed by the models the
person added by name, in the order added. The recommended models are the
catalogue's and are never stored; the added ones are this service's record,
kept in a record capability of its own, apart from the provider records.

The same record keeps the model the person selected in the agent's model
picker, on any lane the catalogue reports, local or not. Document reading runs
with that one model.

The service is bound to one profile's list store and performs the person's
acts:

* add a model to a local lane's list by name;
* remove a model the person added;
* store the model the person selected to read with;
* reset the record, readable or not, at the revision the caller read.

Every change carries the revision the caller read as its guard, is committed
with a compare-and-swap and is read back. A name is only checked against the
catalogue's model id rule: whether the model exists is decided when it is
downloaded, and what it can read is what the catalogue states once the local
server holds it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime

from pydantic import TypeAdapter, ValidationError

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.core.time.clock import now

from ..domain.catalog import ProviderAuthKind, ProviderCatalog, ProviderCatalogEntry
from ..domain.record import (
    LOCAL_MODEL_LIST_MAX_MODELS,
    LOCAL_MODEL_LIST_RECORD_SCHEMA_VERSION,
    ListedModel,
    LocalModelListRecord,
    ModelId,
    new_settings_generation,
)
from .contracts import (
    LocalModelListEntry,
    LocalModelListResult,
    LocalModelListStatus,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    is_provider_settings_revision,
)
from .ports import (
    AbsentLocalModelList,
    LocalModelListRead,
    LocalModelListStore,
    ProviderCatalogSource,
    ProviderCatalogUnavailableError,
    StoredLocalModelList,
    StoreRefusal,
    UnreadableLocalModelList,
)


def local_lanes(catalog: ProviderCatalog) -> tuple[ProviderCatalogEntry, ...]:
    """Return the catalogue's keyless lanes, the ones on this computer, in catalogue order."""
    return tuple(entry for entry in catalog.providers if entry.auth_kind is ProviderAuthKind.NONE)


def listed_models(entry: ProviderCatalogEntry, added: Iterable[str]) -> tuple[str, ...]:
    """Return ``entry``'s model list: its recommended models in the catalogue's order, then ``added``, each once."""
    return tuple(dict.fromkeys((*entry.recommended.values(), *added)))


class LocalModelListService:
    """The models added to local lanes' lists and the person's guarded changes, for one admitted profile."""

    def __init__(
        self,
        *,
        store: LocalModelListStore,
        catalog_source: ProviderCatalogSource,
        clock: Callable[[], datetime] = now,
    ) -> None:
        """Bind the service to one profile's model list store and the agent's declared catalog."""
        self._store = store
        self._catalog_source = catalog_source
        self._clock = clock

    def status(self) -> LocalModelListResult:
        """Return the added models, the reading model and the local lanes, or a typed refusal."""
        read = self._store.read()
        if isinstance(read, StoreRefusal):
            return _refused(ProviderSettingsRefusalCode(read.code.value))
        return _list_status(read, self._local_lane_ids())

    def add(self, lane: str, *, model: str, expected_revision: str) -> LocalModelListResult:
        """Add ``model`` to the list of the local lane ``lane``.

        A model the lane's list already holds, recommended or added, is left
        where it is and the list is answered unchanged.
        """
        if not _is_model_id(model):
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        catalog = self._catalog()
        if isinstance(catalog, ProviderSettingsRefusal):
            return catalog
        entry = next((held for held in local_lanes(catalog) if held.id == lane), None)
        if entry is None:
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        current = self._current(expected_revision)
        if isinstance(current, ProviderSettingsRefusal):
            return current
        record, read = current
        added = () if record is None else record.models
        if _model_is_listed(entry, model, added):
            return _list_status(read, self._local_lane_ids())
        kept = _kept(added, catalog)
        if len(kept) >= LOCAL_MODEL_LIST_MAX_MODELS:
            return _refused(ProviderSettingsRefusalCode.MODEL_LIST_FULL)
        return self._commit((*kept, ListedModel(lane=entry.id, model=model)), _reading_of(record), expected_revision)

    def remove(self, lane: str, *, model: str, expected_revision: str) -> LocalModelListResult:
        """Remove ``model``, which the person added to ``lane``'s list; a recommended model stays listed."""
        catalog = self._catalog()
        if isinstance(catalog, ProviderSettingsRefusal):
            return catalog
        current = self._current(expected_revision)
        if isinstance(current, ProviderSettingsRefusal):
            return current
        record, _read = current
        added = () if record is None else record.models
        if not any(held.lane == lane and held.model == model for held in added):
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        kept = tuple(held for held in _kept(added, catalog) if (held.lane, held.model) != (lane, model))
        return self._commit(kept, _reading_of(record), expected_revision)

    def choose_reading(self, lane: str, *, model: str, expected_revision: str) -> LocalModelListResult:
        """Store ``model`` on ``lane`` as the model documents are read with.

        The lane must be one the catalogue reports; whether the model can read
        a given document is decided when a reading runs. Storing the model
        already stored answers the record unchanged.
        """
        if not _is_model_id(model):
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        catalog = self._catalog()
        if isinstance(catalog, ProviderSettingsRefusal):
            return catalog
        if not any(entry.id == lane for entry in catalog.providers):
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        current = self._current(expected_revision)
        if isinstance(current, ProviderSettingsRefusal):
            return current
        record, read = current
        chosen = ListedModel(lane=lane, model=model)
        if _reading_of(record) == chosen:
            return _list_status(read, self._local_lane_ids())
        added = () if record is None else record.models
        return self._commit(_kept(added, catalog), chosen, expected_revision)

    def reset(self, *, expected_revision: str) -> LocalModelListResult:
        """Delete the model list record, readable or not, at the revision the caller read."""
        if not is_provider_settings_revision(expected_revision):
            return _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)
        refusal = self._store.delete(expected_revision=expected_revision)
        if refusal is not None:
            return _refused(ProviderSettingsRefusalCode(refusal.code.value))
        read = self._store.read()
        if not isinstance(read, AbsentLocalModelList):
            return _refused(ProviderSettingsRefusalCode.COMMITTED_READBACK_FAILED)
        return _list_status(read, self._local_lane_ids())

    def _local_lane_ids(self) -> tuple[str, ...]:
        """Return the catalogue's local lane ids; none when the catalogue cannot be read."""
        catalog = self._catalog()
        if isinstance(catalog, ProviderSettingsRefusal):
            return ()
        return tuple(entry.id for entry in local_lanes(catalog))

    def _catalog(self) -> ProviderCatalog | ProviderSettingsRefusal:
        try:
            return self._catalog_source.catalog()
        except ProviderCatalogUnavailableError:
            return _refused(ProviderSettingsRefusalCode.CATALOG_UNAVAILABLE)

    def _current(
        self, expected_revision: str
    ) -> tuple[LocalModelListRecord | None, LocalModelListRead] | ProviderSettingsRefusal:
        """Read the readable list and check the caller's guard against its revision."""
        if not is_provider_settings_revision(expected_revision):
            return _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)
        read = self._store.read()
        if isinstance(read, StoreRefusal):
            return _refused(ProviderSettingsRefusalCode(read.code.value))
        if isinstance(read, UnreadableLocalModelList):
            # Only a guarded reset may replace a record nobody can read.
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        if _list_revision(read) != expected_revision:
            return _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)
        return (read.record if isinstance(read, StoredLocalModelList) else None), read

    def _commit(
        self, models: tuple[ListedModel, ...], reading: ListedModel | None, expected_revision: str
    ) -> LocalModelListResult:
        record = LocalModelListRecord(
            schema_version=LOCAL_MODEL_LIST_RECORD_SCHEMA_VERSION,
            models=models,
            reading=reading,
            generation=new_settings_generation(),
            updated_at=self._clock(),
        )
        refusal = self._store.write(record, expected_revision=expected_revision)
        if refusal is not None:
            return _refused(ProviderSettingsRefusalCode(refusal.code.value))
        read = self._store.read()
        if not isinstance(read, StoredLocalModelList) or read.record.generation != record.generation:
            return _refused(ProviderSettingsRefusalCode.COMMITTED_READBACK_FAILED)
        return _list_status(read, self._local_lane_ids())


def _model_is_listed(entry: ProviderCatalogEntry, model: str, added: tuple[ListedModel, ...]) -> bool:
    return model in listed_models(entry, (held.model for held in added if held.lane == entry.id))


def _kept(added: Iterable[ListedModel], catalog: ProviderCatalog) -> tuple[ListedModel, ...]:
    """Return the added models a write keeps: every one except those on a lane the catalogue reports as not local.

    A lane the catalogue does not report now keeps its models, since a later
    catalogue may report it again.
    """
    reported = {entry.id: entry.auth_kind is ProviderAuthKind.NONE for entry in catalog.providers}
    return tuple(held for held in added if reported.get(held.lane, True))


def _reading_of(record: LocalModelListRecord | None) -> ListedModel | None:
    return None if record is None else record.reading


def _is_model_id(model: str) -> bool:
    try:
        TypeAdapter(ModelId).validate_python(model)
    except ValidationError:
        return False
    return True


def _list_revision(read: LocalModelListRead) -> str:
    if isinstance(read, AbsentLocalModelList):
        return ABSENT_SECURE_OBJECT_REVISION_ID
    return read.revision


def _list_status(read: LocalModelListRead, lanes: tuple[str, ...]) -> LocalModelListStatus:
    """Project a list read onto its added models, in the order added, the model read with and the local lanes."""
    if isinstance(read, UnreadableLocalModelList):
        return LocalModelListStatus(unreadable=True, models=(), reading=None, local_lanes=lanes, revision=read.revision)
    record = read.record if isinstance(read, StoredLocalModelList) else None
    models = () if record is None else record.models
    reading = _reading_of(record)
    return LocalModelListStatus(
        unreadable=False,
        models=tuple(LocalModelListEntry(lane=held.lane, model=held.model) for held in models),
        reading=None if reading is None else LocalModelListEntry(lane=reading.lane, model=reading.model),
        local_lanes=lanes,
        revision=_list_revision(read),
    )


def _refused(code: ProviderSettingsRefusalCode) -> ProviderSettingsRefusal:
    return ProviderSettingsRefusal(code=code)


__all__ = ["LocalModelListService", "listed_models", "local_lanes"]
