"""The person's local model list and the model they read documents with, and their guarded changes.

A local lane is a keyless one: the agent's catalogue admits a keyless lane only
at a loopback address, so it runs on this computer. Its model list is the
models cadrumo-agent's catalogue recommends for it, followed by the models the
person added by name, in the order added. The recommended models are the
catalogue's and are never stored; the added ones are this service's record,
kept in a record capability of its own, apart from the provider records.

The same record keeps the model the person selected in the agent's model
picker, on any lane the catalogue reports, local or not. Document reading runs
with that one model. It also keeps the local engine setting: which engine runs
models on this computer and where it runs them.

The service is bound to one profile's list store and performs the person's
acts:

* add a model to a local lane's list by name;
* remove a model the person added;
* store the model the person selected to read with;
* choose the local engine and its placement;
* reset the record, readable or not, at the revision the caller read.

Every change carries the revision the caller read as its guard, is committed
with a compare-and-swap and is read back. A name is only checked against the
catalogue's model id rule: whether the model exists is decided when it is
downloaded, and what it can read is what the catalogue states once the local
server holds it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from pydantic import TypeAdapter, ValidationError

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.core.time.clock import now

from ..domain.catalog import (
    BackgroundInput,
    LiveCatalogModel,
    ModelCapability,
    ProviderAuthKind,
    ProviderCatalog,
    ProviderCatalogEntry,
)
from ..domain.record import (
    DEFAULT_LOCAL_PLACEMENT,
    LOCAL_MODEL_LIST_MAX_MODELS,
    LOCAL_MODEL_LIST_RECORD_SCHEMA_VERSION,
    ListedModel,
    LocalEngine,
    LocalModelListRecord,
    LocalPlacement,
    ModelId,
    new_settings_generation,
)
from .contracts import (
    LocalEngineResult,
    LocalEngineStatus,
    LocalModelListEntry,
    LocalModelListResult,
    LocalModelListStatus,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ReadingSource,
    is_provider_settings_revision,
)
from .ports import (
    AbsentLocalModelList,
    LiveCatalogModels,
    LocalModelListRead,
    LocalModelListStore,
    ProviderCatalogSource,
    ProviderCatalogUnavailableError,
    StoredLocalModelList,
    StoreRefusal,
    UnreadableLocalModelList,
)


def serves_engine_lane(provider: str, engine: LocalEngine | None) -> bool:
    """Return whether a lane of the provider identity ``provider`` is served to a profile running ``engine``.

    Each local engine runs its models behind a keyless lane of its own
    identity. Only ``engine``'s lane is served; the other engine's is left out,
    not held back. ``None`` is an engine setting that cannot be read, which
    picks no engine: neither engine's lane is served. A lane of any other
    identity is served whatever the engine. The picker, the provider settings
    and the local model lists are all scoped by this one rule, so each lists
    the same lanes.
    """
    if provider not in _ENGINE_PROVIDERS:
        return True
    return engine is not None and provider == engine.value


_ENGINE_PROVIDERS: Final = frozenset(engine.value for engine in LocalEngine)
"""The provider identities a local engine's keyless lane is served under: each engine's own."""


def engine_lanes(
    catalog: ProviderCatalog, engine: Callable[[], LocalEngine | None]
) -> tuple[ProviderCatalogEntry, ...]:
    """Return the catalogue's lanes a profile running ``engine()`` is served, in catalogue order.

    ``engine`` is read once, and only when the catalogue reports a lane the
    rule could leave out, so a catalogue with no engine lane reads no record.
    """
    if all(serves_engine_lane(entry.provider, held) for entry in catalog.providers for held in LocalEngine):
        return catalog.providers
    selected = engine()
    return tuple(entry for entry in catalog.providers if serves_engine_lane(entry.provider, selected))


def local_lanes(catalog: ProviderCatalog, engine: Callable[[], LocalEngine | None]) -> tuple[ProviderCatalogEntry, ...]:
    """Return the keyless lanes, on this computer, a profile running ``engine()`` is served, in catalogue order."""
    return tuple(entry for entry in engine_lanes(catalog, engine) if entry.auth_kind is ProviderAuthKind.NONE)


def listed_models(entry: ProviderCatalogEntry, added: Iterable[str]) -> tuple[str, ...]:
    """Return ``entry``'s model list: its recommended models in the catalogue's order, then ``added``, each once."""
    return tuple(dict.fromkeys((*entry.recommended.values(), *added)))


@dataclass(frozen=True, slots=True)
class EffectiveReading:
    """The model documents are read with now, and where it comes from; ``model`` is ``None`` only for ``NONE``."""

    model: ListedModel | None
    source: ReadingSource


def effective_reading(
    *,
    record: LocalModelListRecord | None,
    catalog: ProviderCatalog,
    engine: LocalEngine | None,
    live_models: LiveCatalogModels,
    capability: ModelCapability = ModelCapability.TEXT,
) -> EffectiveReading:
    """Return the model a reading for ``capability`` runs with: the one rule every consumer of the selection shares.

    The person's stored choice wins while it is usable: its lane is one the
    ``engine`` is served, and, on a lane on this computer, the model is still
    on the lane's list and the live catalogue does not say the server lacks it.
    A choice on a lane the catalogue does not report, or on a lane that is not
    local, stays the choice: whether that lane can run is the run's answer.
    Otherwise the first installed model on the person's list stands in,
    searching the lanes on this computer in catalogue order: the lane's
    recommended model for ``capability`` when it is installed, else the first
    installed model in the lane's list order (recommended, then added), so a
    model taken off the list never returns as the stand-in. Only a model the live catalogue
    states installed stands in; an unknown state never does. With neither, no
    model is selected. The stand-in is an answer, never a stored record.
    """
    chosen = None if record is None else record.reading
    added = () if record is None else record.models
    if chosen is not None and _choice_is_usable(chosen, added, catalog, engine, live_models):
        return EffectiveReading(model=chosen, source=ReadingSource.CHOSEN)
    for entry in local_lanes(catalog, lambda: engine):
        stand_in = _first_installed(entry, added, live_models, capability)
        if stand_in is not None:
            return EffectiveReading(model=ListedModel(lane=entry.id, model=stand_in), source=ReadingSource.DEFAULT)
    return EffectiveReading(model=None, source=ReadingSource.NONE)


def _choice_is_usable(
    chosen: ListedModel,
    added: tuple[ListedModel, ...],
    catalog: ProviderCatalog,
    engine: LocalEngine | None,
    live_models: LiveCatalogModels,
) -> bool:
    entry = next((held for held in catalog.providers if held.id == chosen.lane), None)
    if entry is None:
        return True
    if not serves_engine_lane(entry.provider, engine):
        return False
    if entry.auth_kind is not ProviderAuthKind.NONE:
        return True
    if not _model_is_listed(entry, chosen.model, added):
        return False
    return _installed(entry, chosen.model, live_models) is not False


def _live_entries(entry: ProviderCatalogEntry, live_models: LiveCatalogModels) -> tuple[LiveCatalogModel, ...]:
    return live_models.lane_models(entry.provider, entry.transport.value) or ()


def _live_entry(entry: ProviderCatalogEntry, model: str, live_models: LiveCatalogModels) -> LiveCatalogModel | None:
    return next((held for held in _live_entries(entry, live_models) if held.id == model), None)


def _installed(entry: ProviderCatalogEntry, model: str, live_models: LiveCatalogModels) -> bool | None:
    """Return whether the live catalogue says the lane's server holds ``model``; ``None`` where it does not say."""
    live = _live_entry(entry, model, live_models)
    return None if live is None else live.installed


def _reads_for(held: LiveCatalogModel | None, capability: ModelCapability, *, reads_images: bool) -> bool:
    """Whether a model the local server reports can read for *capability*: installed, and seeing images for vision."""
    if held is None or held.installed is not True:
        return False
    return capability is not ModelCapability.VISION or (held.vision is True and reads_images)


def _first_installed(
    entry: ProviderCatalogEntry,
    added: tuple[ListedModel, ...],
    live_models: LiveCatalogModels,
    capability: ModelCapability,
) -> str | None:
    if not entry.background.runnable:
        return None
    live = {held.id: held for held in _live_entries(entry, live_models)}
    reads_images = BackgroundInput.IMAGE in entry.background.inputs
    eligible = [
        model
        for model in listed_models(entry, (held.model for held in added if held.lane == entry.id))
        if _reads_for(live.get(model), capability, reads_images=reads_images)
    ]
    preferred = entry.recommended.get(capability.value)
    if preferred in eligible:
        return preferred
    return eligible[0] if eligible else None


class LocalModelListService:
    """The models added to local lanes' lists and the person's guarded changes, for one admitted profile."""

    def __init__(
        self,
        *,
        store: LocalModelListStore,
        catalog_source: ProviderCatalogSource,
        live_models: LiveCatalogModels,
        default_engine: LocalEngine,
        clock: Callable[[], datetime] = now,
    ) -> None:
        """Bind the service to one profile's model list store and the agent's declared and live catalogues.

        ``default_engine`` is the engine a profile that chose none runs: the
        desktop derives it from what the package carries and hands it over at
        start, so no default engine is decided here. ``live_models`` tells
        which models the local server holds, which the reading model is
        decided from.
        """
        self._store = store
        self._catalog_source = catalog_source
        self._live_models = live_models
        self._default_engine = default_engine
        self._clock = clock

    def status(self) -> LocalModelListResult:
        """Return the added models, the model documents are read with and the local lanes, or a typed refusal."""
        read = self._store.read()
        if isinstance(read, StoreRefusal):
            return _refused(ProviderSettingsRefusalCode(read.code.value))
        return self._list_status(read)

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
        entry = next((held for held in local_lanes(catalog, self.selected_engine) if held.id == lane), None)
        if entry is None:
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        current = self._current(expected_revision)
        if isinstance(current, ProviderSettingsRefusal):
            return current
        record, read = current
        added = () if record is None else record.models
        if _model_is_listed(entry, model, added):
            return self._list_status(read)
        kept = _kept(added, catalog)
        if len(kept) >= LOCAL_MODEL_LIST_MAX_MODELS:
            return _refused(ProviderSettingsRefusalCode.MODEL_LIST_FULL)
        listed = (*kept, ListedModel(lane=entry.id, model=model))
        return self._list_answer(self._commit(listed, _reading_of(record), _setting_of(record), expected_revision))

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
        return self._list_answer(self._commit(kept, _reading_of(record), _setting_of(record), expected_revision))

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
        if not any(entry.id == lane for entry in engine_lanes(catalog, self.selected_engine)):
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        current = self._current(expected_revision)
        if isinstance(current, ProviderSettingsRefusal):
            return current
        record, read = current
        chosen = ListedModel(lane=lane, model=model)
        if _reading_of(record) == chosen:
            return self._list_status(read)
        added = () if record is None else record.models
        return self._list_answer(self._commit(_kept(added, catalog), chosen, _setting_of(record), expected_revision))

    def engine_status(self) -> LocalEngineResult:
        """Return the local engine setting, or a typed refusal."""
        read = self._store.read()
        if isinstance(read, StoreRefusal):
            return _refused(ProviderSettingsRefusalCode(read.code.value))
        return _engine_status(read, self._default_engine)

    def choose_engine(
        self, engine: LocalEngine, placement: LocalPlacement, *, expected_revision: str
    ) -> LocalEngineResult:
        """Store ``engine`` and ``placement`` as the local engine setting the person chose.

        The added models and the reading model are kept as stored. Storing
        the setting already stored answers it unchanged; storing the setting
        an unchosen record reads as makes it the person's choice, so a later
        default does not change it.
        """
        current = self._current(expected_revision)
        if isinstance(current, ProviderSettingsRefusal):
            return current
        record, read = current
        if _setting_of(record) == (engine, placement):
            return _engine_status(read, self._default_engine)
        added = () if record is None else record.models
        committed = self._commit(added, _reading_of(record), (engine, placement), expected_revision)
        if isinstance(committed, ProviderSettingsRefusal):
            return committed
        return _engine_status(committed, self._default_engine)

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
        return self._list_status(read)

    def selected_engine(self) -> LocalEngine | None:
        """Return the engine the profile runs: the person's choice, else the default.

        ``None`` when the record cannot be read or the store refuses: no engine
        is picked for a setting nobody can read.
        """
        status = self.engine_status()
        return status.engine if isinstance(status, LocalEngineStatus) else None

    def _list_status(self, read: LocalModelListRead) -> LocalModelListStatus:
        """Project a list read onto its added models, the model read with now and the local lanes.

        The catalogue is read once. Without it no lane is local and nothing
        tells which stored choice is usable, so the stored choice is served as
        it is.
        """
        catalog = self._catalog()
        record = read.record if isinstance(read, StoredLocalModelList) else None
        if isinstance(catalog, ProviderSettingsRefusal):
            stored = _reading_of(record)
            reading = EffectiveReading(
                model=stored, source=ReadingSource.NONE if stored is None else ReadingSource.CHOSEN
            )
            return _list_status(read, (), reading)
        engine = self.selected_engine()
        lanes = tuple(entry.id for entry in local_lanes(catalog, lambda: engine))
        reading = effective_reading(
            record=record, catalog=catalog, engine=engine, live_models=self._live_models.snapshot()
        )
        return _list_status(read, lanes, reading)

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
        self,
        models: tuple[ListedModel, ...],
        reading: ListedModel | None,
        setting: tuple[LocalEngine | None, LocalPlacement | None],
        expected_revision: str,
    ) -> StoredLocalModelList | ProviderSettingsRefusal:
        engine, placement = setting
        record = LocalModelListRecord(
            schema_version=LOCAL_MODEL_LIST_RECORD_SCHEMA_VERSION,
            models=models,
            reading=reading,
            engine=engine,
            placement=placement,
            generation=new_settings_generation(),
            updated_at=self._clock(),
        )
        refusal = self._store.write(record, expected_revision=expected_revision)
        if refusal is not None:
            return _refused(ProviderSettingsRefusalCode(refusal.code.value))
        read = self._store.read()
        if not isinstance(read, StoredLocalModelList) or read.record.generation != record.generation:
            return _refused(ProviderSettingsRefusalCode.COMMITTED_READBACK_FAILED)
        return read

    def _list_answer(self, committed: StoredLocalModelList | ProviderSettingsRefusal) -> LocalModelListResult:
        if isinstance(committed, ProviderSettingsRefusal):
            return committed
        return self._list_status(committed)


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


def _setting_of(record: LocalModelListRecord | None) -> tuple[LocalEngine | None, LocalPlacement | None]:
    """Return the local engine setting as the person chose it; ``None`` where none was chosen."""
    if record is None:
        return None, None
    return record.engine, record.placement


def _resolved(record: LocalModelListRecord | None, default_engine: LocalEngine) -> tuple[LocalEngine, LocalPlacement]:
    """Return the setting a profile runs under: the person's choice, else the defaults."""
    engine, placement = _setting_of(record)
    return (
        default_engine if engine is None else engine,
        DEFAULT_LOCAL_PLACEMENT if placement is None else placement,
    )


def _engine_status(read: LocalModelListRead, default_engine: LocalEngine) -> LocalEngineStatus:
    """Project a list read onto its local engine setting; an unreadable record names none."""
    if isinstance(read, UnreadableLocalModelList):
        return LocalEngineStatus(unreadable=True, chosen=False, engine=None, placement=None, revision=read.revision)
    record = read.record if isinstance(read, StoredLocalModelList) else None
    engine, placement = _resolved(record, default_engine)
    return LocalEngineStatus(
        unreadable=False,
        chosen=_setting_of(record)[0] is not None,
        engine=engine,
        placement=placement,
        revision=_list_revision(read),
    )


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


def _list_status(read: LocalModelListRead, lanes: tuple[str, ...], reading: EffectiveReading) -> LocalModelListStatus:
    """Project a list read onto its added models, in the order added, the model read with and the local lanes."""
    if isinstance(read, UnreadableLocalModelList):
        return LocalModelListStatus(
            unreadable=True,
            models=(),
            reading=None,
            reading_source=ReadingSource.NONE,
            local_lanes=lanes,
            revision=read.revision,
        )
    record = read.record if isinstance(read, StoredLocalModelList) else None
    models = () if record is None else record.models
    model = reading.model
    return LocalModelListStatus(
        unreadable=False,
        models=tuple(LocalModelListEntry(lane=held.lane, model=held.model) for held in models),
        reading=None if model is None else LocalModelListEntry(lane=model.lane, model=model.model),
        reading_source=reading.source,
        local_lanes=lanes,
        revision=_list_revision(read),
    )


def _refused(code: ProviderSettingsRefusalCode) -> ProviderSettingsRefusal:
    return ProviderSettingsRefusal(code=code)


__all__ = [
    "EffectiveReading",
    "LocalModelListService",
    "effective_reading",
    "engine_lanes",
    "listed_models",
    "local_lanes",
    "serves_engine_lane",
]
