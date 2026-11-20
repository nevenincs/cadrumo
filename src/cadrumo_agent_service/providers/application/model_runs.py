"""Which lane and model answer a tax model run, and the run itself, for one admitted profile.

A tax worker's model run names its role, and may name its task kind, and never
a lane or a model. A run naming a task kind the person set a lane, model and
effort for runs with that setting, and nothing stands in for it: a setting
whose lane the profile's engine does not serve refuses ``lane_unavailable``,
a local model since taken off its lane's list refuses ``no_selection``, and
one the live catalogue says the server lacks refuses ``model_not_installed``.
Every other run runs with the one model documents are read with: the model the person
selected in the agent's model picker, which the desktop stores in the person's
model record, on any lane, local or not, while it is still usable; otherwise
the first installed local model. That choice is made by
:func:`effective_reading`, the same rule that answers the window which model is
selected. A role needs a capability: the vision role reads images, so it needs a
lane whose background runs take images and a model the lane's current entries
mark vision; every other role reads text, which every model does. Current
entries are the lane's declared ones and, while the agent runs, its live ones.

No model but that one stands in. No selected model and no installed local
model refuses ``no_selection``. A stored local choice the person has since
taken off its lane's list, or the live catalogue says the server lacks, is no
longer a choice, so the installed default stands in, else ``no_selection``.
A selected model the role cannot use because it is not stated to read images
refuses ``model_cannot_read_images``; one a local server does not hold, though
the live catalogue does not say so, is refused by the agent when the run
starts, and that refusal passes through unchanged; a lane that is not
reported, turned on, signed in or runnable refuses with its answer or
``lane_unavailable``. An unreadable
record says nothing about any model, so every role refuses
``lane_unavailable``. Whether a lane takes an attachment,
and which run options it honours, is what the ready agent's live catalog
reports for background requests, never inferred from its transport. Effort is
honoured only where the lane states it and the run's model offers a level; a
task setting's effort is sent only when the lane honours effort and its model
lists that level, else the run is refused ``option_not_supported`` before
anything is sent. One
lookup, and one run, reads the live catalog once: its entries, media and
options come from that one snapshot, which no later lookup or run reuses.
Whether a lane reads off-host is the catalogue entry's typed declaration,
carried with the lane: a run on such a lane needs the consent the tax side
bound to it.

The run goes to cadrumo-agent as a background request through
:class:`BackgroundRunGateway`. No secret leaves this service with the answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Protocol

from cadrumo.core.model_roles import ModelRole
from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunMediaKind,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunTaskKind,
    model_run_media_kind,
)

from ..domain.catalog import (
    BackgroundInput,
    BackgroundOption,
    CatalogModelFacts,
    EffortLevel,
    ModelCapability,
    ProviderCatalog,
    ProviderCatalogEntry,
    ProviderConsumer,
)
from ..domain.record import ListedModel, LocalEngine, LocalModelListRecord, TaskModel
from .lane_entries import current_lane_entries
from .local_model_list import TaskModelUsability, effective_reading, task_model_usability
from .ports import (
    LiveCatalogModels,
    LocalModelListRead,
    LocalModelListStore,
    ProviderCatalogSource,
    ProviderCatalogUnavailableError,
    StoredLocalModelList,
    StoreRefusal,
    StoreRefusalCode,
    UnreadableLocalModelList,
)
from .resolution import (
    ProviderCredentialResolver,
    ProviderCredentialUnavailable,
    ProviderCredentialUnavailableReason,
)

ROLE_CAPABILITIES: Final[Mapping[ModelRole, ModelCapability]] = MappingProxyType(
    {
        ModelRole.VISION_TRANSCRIPTION: ModelCapability.VISION,
        ModelRole.TEXT_EXTRACTION: ModelCapability.TEXT,
        ModelRole.COLUMN_ROLE_MAPPING: ModelCapability.TEXT,
        ModelRole.SUPPLY_NATURE_PROPOSAL: ModelCapability.TEXT,
    }
)
"""The capability each role's runs need: only vision transcription reads images."""

_SIGNED_OUT: dict[ProviderCredentialUnavailableReason, ModelRunRefusalCode] = {
    ProviderCredentialUnavailableReason.NOT_SIGNED_IN: ModelRunRefusalCode.NOT_SIGNED_IN,
    ProviderCredentialUnavailableReason.PROFILE_LOCKED: ModelRunRefusalCode.PROFILE_LOCKED,
}

_STORE_SIGNED_OUT: dict[StoreRefusalCode, ModelRunRefusalCode] = {
    StoreRefusalCode.NOT_SIGNED_IN: ModelRunRefusalCode.NOT_SIGNED_IN,
    StoreRefusalCode.PROFILE_LOCKED: ModelRunRefusalCode.PROFILE_LOCKED,
}


class BackgroundRunGateway(Protocol):
    """cadrumo-agent's background runs: tool-less, outside the conversation listing, readable by id."""

    def run(
        self,
        *,
        lane: ModelRunLane,
        body: ModelRunBody,
        deadline_seconds: int,
        options: tuple[BackgroundOption, ...],
        effort: EffortLevel | None,
    ) -> ModelRunOutput | ModelRunRefusal:
        """Run ``body`` on ``lane``, sending only the run ``options`` it honours; refuse with one closed code.

        ``effort`` is the run's agent effort. It is sent only when ``options``
        holds ``effort``; otherwise the run is refused before anything is sent,
        because a lane that ignored it would answer at another effort.
        """
        ...


class ModelRunService:
    """Resolve a role to the person's selected model and its lane, and run requests on it, for one profile."""

    def __init__(
        self,
        *,
        model_list: LocalModelListStore,
        resolver: ProviderCredentialResolver,
        catalog_source: ProviderCatalogSource,
        live_models: LiveCatalogModels,
        selected_engine: Callable[[], LocalEngine | None],
        gateway: BackgroundRunGateway,
    ) -> None:
        """Bind the service to the profile's model list, resolver, the agent's catalogs and the run gateway.

        ``selected_engine`` answers which local engine the profile runs, which
        decides the local lanes a default reading model may come from.
        """
        self._model_list = model_list
        self._selected_engine = selected_engine
        self._resolver = resolver
        self._catalog_source = catalog_source
        self._live_models = live_models
        self._gateway = gateway

    def lookup(self, role: str, *, task_kind: ModelRunTaskKind | None = None) -> ModelRunLane | ModelRunRefusal:
        """Return the lane and model ``role`` doing ``task_kind`` resolves to now; nothing in the answer is secret."""
        resolved = self._lookup(role, task_kind, self._lane_answers())
        return resolved if isinstance(resolved, ModelRunRefusal) else resolved.lane

    def _lookup(
        self, role: str, task_kind: ModelRunTaskKind | None, lanes: _LaneAnswers
    ) -> _Resolution | ModelRunRefusal:
        try:
            model_role = ModelRole(role)
        except ValueError:
            # Not a missing model: pointing the person at the picker would hide the caller's defect.
            return ModelRunRefusal(code=ModelRunRefusalCode.UNKNOWN_ROLE)
        read = self._read_list()
        if isinstance(read, ModelRunRefusal):
            return read
        return self._resolve(model_role, task_kind, read, lanes, self._selected_engine())

    def _read_list(self) -> LocalModelListRead | ModelRunRefusal:
        read = self._model_list.read()
        if isinstance(read, StoreRefusal):
            return ModelRunRefusal(code=_STORE_SIGNED_OUT.get(read.code, ModelRunRefusalCode.LANE_UNAVAILABLE))
        return read

    def _lane_answers(self) -> _LaneAnswers:
        return _LaneAnswers(
            catalog_source=self._catalog_source,
            live_models=self._live_models,
            resolver=self._resolver,
        )

    @staticmethod
    def _resolve(
        model_role: ModelRole,
        task_kind: ModelRunTaskKind | None,
        read: LocalModelListRead,
        lanes: _LaneAnswers,
        engine: LocalEngine | None,
    ) -> _Resolution | ModelRunRefusal:
        """Return the lane the role runs on, with the task setting's effort, or the refusal."""
        if isinstance(read, UnreadableLocalModelList):
            # An unreadable record says nothing about any model, so no role reads as served or unserved.
            return ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        record = read.record if isinstance(read, StoredLocalModelList) else None
        capability = ROLE_CAPABILITIES[model_role]
        task = None if record is None or task_kind is None else record.task(task_kind.value)
        if task is not None and record is not None:
            return lanes.resolve_task(capability, task, record.models, engine)
        lane = lanes.resolve(capability, record, engine)
        return lane if isinstance(lane, ModelRunRefusal) else _Resolution(lane=lane, effort=None)

    def run(self, header: ModelRunHeader, body: ModelRunBody) -> ModelRunOutput | ModelRunRefusal:
        """Run one request on the lane its role resolves to now.

        A run on a lane that reads off-host is refused unless it carries
        consent, and a run carrying consent is refused when that lane is not
        the one the consent was recorded for. The lane is resolved again here,
        so a selection changed since the tax side's lookup cannot carry a run
        recorded as on-host to a lane that leaves this computer. An attachment
        the lane's catalog entry says it does not take is refused before
        anything is sent.
        """
        lanes = self._lane_answers()
        resolved = self._lookup(header.role, header.task_kind, lanes)
        if isinstance(resolved, ModelRunRefusal):
            return resolved
        lane = resolved.lane
        if not header.consent_admits(lane):
            return ModelRunRefusal(code=ModelRunRefusalCode.CONSENT_MISSING)
        if lane.accepted_media is not None:
            for attachment in body.attachments:
                if model_run_media_kind(attachment.media_type) not in lane.accepted_media:
                    return ModelRunRefusal(code=ModelRunRefusalCode.INPUT_NOT_SUPPORTED)
        if resolved.effort is not None and not lanes.offers_effort(lane, resolved.effort):
            # A lane that ignored the effort would answer at another one, so nothing is sent.
            return ModelRunRefusal(code=ModelRunRefusalCode.OPTION_NOT_SUPPORTED)
        return self._gateway.run(
            lane=lane,
            body=body,
            deadline_seconds=header.deadline_seconds,
            options=lanes.honoured_options(lane),
            effort=resolved.effort,
        )


@dataclass(frozen=True, slots=True)
class _Resolution:
    """The lane a run resolves to, and the effort its task setting names; ``None`` names none."""

    lane: ModelRunLane
    effort: EffortLevel | None


_TASK_REFUSALS: Final[Mapping[TaskModelUsability, ModelRunRefusalCode]] = MappingProxyType(
    {
        TaskModelUsability.LANE_NOT_SERVED: ModelRunRefusalCode.LANE_UNAVAILABLE,
        TaskModelUsability.NOT_LISTED: ModelRunRefusalCode.NO_SELECTION,
        TaskModelUsability.NOT_INSTALLED: ModelRunRefusalCode.MODEL_NOT_INSTALLED,
    }
)
"""How a task setting that cannot run now is refused; nothing stands in for it."""


type _DecidedLane = tuple[tuple[ModelRunMediaKind, ...] | None, tuple[CatalogModelFacts, ...]]
"""A lane decided once: the media its background runs accept, and its current entries."""


class _LaneAnswers:
    """The selected lane's availability, accepted media and current entries, decided at most once per record read.

    The lane is decided from one snapshot of the live catalogue, taken here and
    read when first needed, which also answers a run's reply options.

    Availability is decided by resolving the lane's credential, because a
    provider record is only readable whole; for a keyless lane it is whether
    the person turned the lane on. The resolution is dropped as soon as it is
    judged, so no secret outlives the decision or reaches an answer.
    """

    def __init__(
        self,
        *,
        catalog_source: ProviderCatalogSource,
        live_models: LiveCatalogModels,
        resolver: ProviderCredentialResolver,
    ) -> None:
        self._catalog_source = catalog_source
        self._live_models = live_models.snapshot()
        self._resolver = resolver
        self._catalog: ProviderCatalog | ModelRunRefusal | None = None
        self._lanes: dict[str, _DecidedLane | ModelRunRefusal] = {}

    def resolve(
        self, capability: ModelCapability, record: LocalModelListRecord | None, engine: LocalEngine | None
    ) -> ModelRunLane | ModelRunRefusal:
        """Return the lane of the model documents are read with when it can serve ``capability``, or the refusal."""
        catalog = self._read_catalog()
        if isinstance(catalog, ModelRunRefusal):
            return catalog
        selected = effective_reading(
            record=record, catalog=catalog, engine=engine, live_models=self._live_models, capability=capability
        ).model
        if selected is None:
            return ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)
        reading = selected
        entry = next((held for held in catalog.providers if held.id == reading.lane), None)
        if entry is None:
            return ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        decided = self._decided(entry)
        if isinstance(decided, ModelRunRefusal):
            return decided
        accepted, entries = decided
        return _selected_model_lane(entry, accepted, entries, reading, capability)

    def resolve_task(
        self,
        capability: ModelCapability,
        task: TaskModel,
        added: tuple[ListedModel, ...],
        engine: LocalEngine | None,
    ) -> _Resolution | ModelRunRefusal:
        """Return the lane of the model the person set for a task kind, with its effort, or the refusal."""
        catalog = self._read_catalog()
        if isinstance(catalog, ModelRunRefusal):
            return catalog
        entry = next((held for held in catalog.providers if held.id == task.lane), None)
        if entry is None:
            return ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        chosen = ListedModel(lane=task.lane, model=task.model)
        usability = task_model_usability(chosen, added, entry, engine, self._live_models)
        if usability is not TaskModelUsability.USABLE:
            return ModelRunRefusal(code=_TASK_REFUSALS[usability])
        decided = self._decided(entry)
        if isinstance(decided, ModelRunRefusal):
            return decided
        accepted, entries = decided
        lane = _selected_model_lane(entry, accepted, entries, chosen, capability)
        return lane if isinstance(lane, ModelRunRefusal) else _Resolution(lane=lane, effort=task.effort)

    def offers_effort(self, lane: ModelRunLane, effort: EffortLevel) -> bool:
        """Return whether ``lane`` honours effort, from the same snapshot, and lists ``effort`` for its model."""
        background = self._live_models.lane_background(lane.provider_id, lane.transport)
        if background is None or BackgroundOption.EFFORT not in background.options:
            return False
        return effort in background.model_efforts.get(lane.model, ())

    def _decided(self, entry: ProviderCatalogEntry) -> _DecidedLane | ModelRunRefusal:
        decided = self._lanes.get(entry.id)
        if decided is None:
            decided = self._lanes[entry.id] = self._decide(entry)
        return decided

    def _decide(self, entry: ProviderCatalogEntry) -> _DecidedLane | ModelRunRefusal:
        resolution = self._resolver.resolve(entry.id, ProviderConsumer.ASSISTANT)
        if isinstance(resolution, ProviderCredentialUnavailable):
            return ModelRunRefusal(code=_SIGNED_OUT.get(resolution.reason, ModelRunRefusalCode.LANE_UNAVAILABLE))
        del resolution
        background = self._live_models.lane_background(entry.provider, entry.transport.value)
        accepted = None if background is None else background.accepted_media
        return accepted, current_lane_entries(entry, self._live_models)

    def honoured_options(self, lane: ModelRunLane) -> tuple[BackgroundOption, ...]:
        """Return the run options ``lane`` honours, from the same snapshot; none when the snapshot does not say.

        Effort is honoured only where the lane states it and the snapshot
        states effort levels for the lane's model: a model without one takes
        no effort, whatever its lane can send.
        """
        background = self._live_models.lane_background(lane.provider_id, lane.transport)
        if background is None:
            return ()
        offers_effort = bool(background.model_efforts.get(lane.model))
        return tuple(option for option in background.options if option is not BackgroundOption.EFFORT or offers_effort)

    def _read_catalog(self) -> ProviderCatalog | ModelRunRefusal:
        if self._catalog is None:
            try:
                self._catalog = self._catalog_source.catalog()
            except ProviderCatalogUnavailableError:
                self._catalog = ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        return self._catalog


def _selected_model_lane(
    entry: ProviderCatalogEntry,
    accepted: tuple[ModelRunMediaKind, ...] | None,
    entries: tuple[CatalogModelFacts, ...],
    reading: ListedModel,
    capability: ModelCapability,
) -> ModelRunLane | ModelRunRefusal:
    background = entry.background
    if not background.runnable:
        return ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
    facts = next((held for held in entries if held.id == reading.model), None)
    if capability is ModelCapability.VISION and (
        BackgroundInput.IMAGE not in background.inputs or facts is None or facts.vision is not True
    ):
        return ModelRunRefusal(code=ModelRunRefusalCode.MODEL_CANNOT_READ_IMAGES)
    return ModelRunLane(
        provider_id=entry.provider,
        transport=entry.transport.value,
        model=reading.model,
        reads_off_host=entry.reads_off_host,
        accepted_media=accepted,
    )


__all__ = ["ROLE_CAPABILITIES", "BackgroundRunGateway", "ModelRunService"]
