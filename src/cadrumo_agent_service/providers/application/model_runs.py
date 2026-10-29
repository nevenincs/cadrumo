"""Which lane and model answer a tax model run, and the run itself, for one admitted profile.

A tax worker's model run names its role and never a lane or a model. Every
role runs with the one model the person selected in the agent's model picker,
which the desktop stores in the person's model record: on any lane, local or
not. A role needs a capability: the vision role reads images, so it needs a
lane whose background runs take images and a model the lane's current entries
mark vision; every other role reads text, which every model does. Current
entries are the lane's declared ones and, while the agent runs, its live ones.

No other lane, no other model and no default stands in. No selected model
refuses ``no_selection``, and so does a local model the person has since taken
off its lane's list. A selected model the role cannot use because it is not
stated to read images refuses ``model_cannot_read_images``; one a local server
does not hold is refused by the agent when the run starts, and that refusal
passes through unchanged; a lane that is not reported, turned on, signed in
or runnable refuses with its answer or ``lane_unavailable``. An unreadable
record says nothing about any model, so every role refuses
``lane_unavailable``. Whether a lane takes an attachment,
and which reply options it honours, is what the ready agent's live catalog
reports for background requests, never inferred from its transport. One
lookup, and one run, reads the live catalog once: its entries, media and
options come from that one snapshot, which no later lookup or run reuses.
Whether a lane reads off-host is the catalogue entry's typed declaration,
carried with the lane: a run on such a lane needs the consent the tax side
bound to it.

The run goes to cadrumo-agent as a background request through
:class:`BackgroundRunGateway`. No secret leaves this service with the answer.
"""

from __future__ import annotations

from collections.abc import Mapping
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
    model_run_media_kind,
)

from ..domain.catalog import (
    BackgroundInput,
    BackgroundOption,
    CatalogModelFacts,
    ModelCapability,
    ProviderAuthKind,
    ProviderCatalog,
    ProviderCatalogEntry,
    ProviderConsumer,
)
from ..domain.record import ListedModel
from .lane_entries import current_lane_entries
from .local_model_list import listed_models
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
        self, *, lane: ModelRunLane, body: ModelRunBody, deadline_seconds: int, options: tuple[BackgroundOption, ...]
    ) -> ModelRunOutput | ModelRunRefusal:
        """Run ``body`` on ``lane``, sending only the reply ``options`` it honours; refuse with one closed code."""
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
        gateway: BackgroundRunGateway,
    ) -> None:
        """Bind the service to the profile's model list, resolver, the agent's catalogs and the run gateway."""
        self._model_list = model_list
        self._resolver = resolver
        self._catalog_source = catalog_source
        self._live_models = live_models
        self._gateway = gateway

    def lookup(self, role: str) -> ModelRunLane | ModelRunRefusal:
        """Return the lane and model ``role`` resolves to now; nothing in the answer is secret."""
        return self._lookup(role, self._lane_answers())

    def _lookup(self, role: str, lanes: _LaneAnswers) -> ModelRunLane | ModelRunRefusal:
        try:
            model_role = ModelRole(role)
        except ValueError:
            # Not a missing model: pointing the person at the picker would hide the caller's defect.
            return ModelRunRefusal(code=ModelRunRefusalCode.UNKNOWN_ROLE)
        read = self._read_list()
        if isinstance(read, ModelRunRefusal):
            return read
        return self._resolve(model_role, read, lanes)

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
        model_role: ModelRole, read: LocalModelListRead, lanes: _LaneAnswers
    ) -> ModelRunLane | ModelRunRefusal:
        """Return the lane the role runs on or the refusal."""
        if isinstance(read, UnreadableLocalModelList):
            # An unreadable record says nothing about any model, so no role reads as served or unserved.
            return ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        if not isinstance(read, StoredLocalModelList) or read.record.reading is None:
            return ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)
        return lanes.resolve(ROLE_CAPABILITIES[model_role], read.record.reading, read.record.models)

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
        lane = self._lookup(header.role, lanes)
        if isinstance(lane, ModelRunRefusal):
            return lane
        if not header.consent_admits(lane):
            return ModelRunRefusal(code=ModelRunRefusalCode.CONSENT_MISSING)
        if lane.accepted_media is not None:
            for attachment in body.attachments:
                if model_run_media_kind(attachment.media_type) not in lane.accepted_media:
                    return ModelRunRefusal(code=ModelRunRefusalCode.INPUT_NOT_SUPPORTED)
        return self._gateway.run(
            lane=lane, body=body, deadline_seconds=header.deadline_seconds, options=lanes.honoured_options(lane)
        )


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
        self, capability: ModelCapability, reading: ListedModel, added: tuple[ListedModel, ...]
    ) -> ModelRunLane | ModelRunRefusal:
        """Return the selected model's lane when it can serve ``capability``, or the refusal."""
        catalog = self._read_catalog()
        if isinstance(catalog, ModelRunRefusal):
            return catalog
        entry = next((held for held in catalog.providers if held.id == reading.lane), None)
        if entry is None:
            return ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        if entry.auth_kind is ProviderAuthKind.NONE and reading.model not in listed_models(
            entry, (held.model for held in added if held.lane == entry.id)
        ):
            # A local model the person took off its lane's list is no longer one they read with.
            return ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)
        decided = self._decided(entry)
        if isinstance(decided, ModelRunRefusal):
            return decided
        accepted, entries = decided
        return _selected_model_lane(entry, accepted, entries, reading, capability)

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
        """Return the reply options ``lane`` honours, from the same snapshot; none when the snapshot does not say."""
        background = self._live_models.lane_background(lane.provider_id, lane.transport)
        return () if background is None else background.options

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
