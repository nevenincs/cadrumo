"""Which lane answers a tax model run, and the run itself, for one admitted profile.

A tax worker's model run names its role and never a lane. The lane and model
are the ones the person selected for that role, stored in the profile's
own model-role selections record. A role with no selection refuses ``no_selection``. Nothing
stands in for a missing selection: not another lane, not another role's
choice, not a catalogue default. A selected lane that is turned off, no longer
reported or not reachable refuses ``lane_unavailable``. Any lane is eligible,
API or CLI; whether a lane takes an attachment is what the ready agent's live
catalog reports for background requests, read in the same lookup, and never
inferred from its transport. Whether a lane reads off-host is likewise the
catalogue entry's typed declaration, carried with the lane: a run on such a
lane needs the consent the tax side bound to it, and a run on a lane that stays
on this computer needs none. The model's licence, size, vision and context
window travel with the lane as the catalogue states them, each ``None`` when it
states nothing; no lookup substitutes a recommended model.

The run goes to cadrumo-agent as a background request through
:class:`BackgroundRunGateway`. No secret leaves this service with the answer.
"""

from __future__ import annotations

from typing import Protocol

from cadrumo.core.model_catalogue import ModelRole
from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunLicence,
    ModelRunMediaKind,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunRoleSelection,
    ModelRunSelectedModel,
    model_run_media_kind,
)

from ..domain.catalog import ProviderCatalog, ProviderCatalogEntry, ProviderConsumer
from ..domain.record import ModelRoleSelection
from .ports import (
    AbsentModelRoleSelections,
    ModelRoleSelectionsRead,
    ModelRoleSelectionsStore,
    ProviderCatalogSource,
    ProviderCatalogUnavailableError,
    StoreRefusal,
    StoreRefusalCode,
    UnreadableModelRoleSelections,
)
from .resolution import (
    ProviderCredentialResolver,
    ProviderCredentialUnavailable,
    ProviderCredentialUnavailableReason,
)

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

    def run(self, *, lane: ModelRunLane, body: ModelRunBody, deadline_seconds: int) -> ModelRunOutput | ModelRunRefusal:
        """Run ``body`` on ``lane`` and return the final reply, or refuse with one closed code."""
        ...

    def accepted_media(self, lane: ModelRunLane) -> tuple[ModelRunMediaKind, ...] | None:
        """Return the attachment families a background request on ``lane`` may carry; ``None`` when unknown."""
        ...


class ModelRunService:
    """Resolve the lane for a role and run requests on it, for one admitted profile."""

    def __init__(
        self,
        *,
        selections: ModelRoleSelectionsStore,
        resolver: ProviderCredentialResolver,
        catalog_source: ProviderCatalogSource,
        gateway: BackgroundRunGateway,
    ) -> None:
        """Bind the service to the profile's selections, resolver, the agent's catalog and the run gateway."""
        self._selections = selections
        self._resolver = resolver
        self._catalog_source = catalog_source
        self._gateway = gateway

    def lookup(self, role: str) -> ModelRunLane | ModelRunRefusal:
        """Return the lane and model the person selected for ``role``; nothing in the answer is secret."""
        try:
            model_role = ModelRole(role)
        except ValueError:
            # Not the person's missing choice: pointing them at the selection would hide the caller's defect.
            return ModelRunRefusal(code=ModelRunRefusalCode.UNKNOWN_ROLE)
        read = self._read_selections()
        if isinstance(read, ModelRunRefusal):
            return read
        return self._resolve(model_role, read, self._lane_answers())[1]

    def selections(self) -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
        """Return every role's selection and the lane a run would use or why it would refuse.

        The record is read once, and each lane the roles name is decided once,
        so every role is reported from the same state and a lane two roles
        share reads its credential and asks for its media only once.
        """
        read = self._read_selections()
        if isinstance(read, ModelRunRefusal):
            return read
        lanes = self._lane_answers()
        states: list[ModelRunRoleSelection] = []
        for model_role in ModelRole:
            selected, answer = self._resolve(model_role, read, lanes)
            stored = None if selected is None else ModelRunSelectedModel(lane_id=selected.lane, model=selected.model)
            if isinstance(answer, ModelRunRefusal):
                states.append(ModelRunRoleSelection(role=model_role.value, selected=stored, refusal=answer.code))
            else:
                states.append(ModelRunRoleSelection(role=model_role.value, selected=stored, lane=answer))
        return tuple(states)

    def _read_selections(self) -> ModelRoleSelectionsRead | ModelRunRefusal:
        read = self._selections.read()
        if isinstance(read, StoreRefusal):
            return ModelRunRefusal(code=_STORE_SIGNED_OUT.get(read.code, ModelRunRefusalCode.LANE_UNAVAILABLE))
        return read

    def _lane_answers(self) -> _LaneAnswers:
        return _LaneAnswers(catalog_source=self._catalog_source, resolver=self._resolver, gateway=self._gateway)

    @staticmethod
    def _resolve(
        model_role: ModelRole, read: ModelRoleSelectionsRead, lanes: _LaneAnswers
    ) -> tuple[ModelRoleSelection | None, ModelRunLane | ModelRunRefusal]:
        """Return the role's stored selection, if readable, and the lane it resolves to or the refusal."""
        if isinstance(read, UnreadableModelRoleSelections):
            # An unreadable record says nothing about any role, so no role reads as unselected.
            return None, ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        selection = None if isinstance(read, AbsentModelRoleSelections) else read.record.selection(model_role)
        if selection is None:
            return None, ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)
        return selection, lanes.answer(selection)

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
        lane = self.lookup(header.role)
        if isinstance(lane, ModelRunRefusal):
            return lane
        if header.consent is None:
            if lane.reads_off_host:
                return ModelRunRefusal(code=ModelRunRefusalCode.CONSENT_MISSING)
        elif not header.consent.matches(lane):
            return ModelRunRefusal(code=ModelRunRefusalCode.CONSENT_MISSING)
        if lane.accepted_media is not None:
            for attachment in body.attachments:
                if model_run_media_kind(attachment.media_type) not in lane.accepted_media:
                    return ModelRunRefusal(code=ModelRunRefusalCode.INPUT_NOT_SUPPORTED)
        return self._gateway.run(lane=lane, body=body, deadline_seconds=header.deadline_seconds)


class _LaneAnswers:
    """Each lane's availability and accepted media, decided at most once for one read of the selections.

    Availability is decided by resolving the lane's credential, because a
    provider record is only readable whole. The resolution is dropped as soon
    as it is judged, so no secret outlives the decision or reaches an answer.
    """

    def __init__(
        self,
        *,
        catalog_source: ProviderCatalogSource,
        resolver: ProviderCredentialResolver,
        gateway: BackgroundRunGateway,
    ) -> None:
        self._catalog_source = catalog_source
        self._resolver = resolver
        self._gateway = gateway
        self._catalog: ProviderCatalog | ModelRunRefusal | None = None
        self._lanes: dict[str, ModelRunLane | ModelRunRefusal] = {}

    def answer(self, selection: ModelRoleSelection) -> ModelRunLane | ModelRunRefusal:
        """Return the lane carrying ``selection``'s model, or the refusal its lane meets."""
        decided = self._lanes.get(selection.lane)
        if decided is None:
            decided = self._lanes[selection.lane] = self._decide(selection)
        if isinstance(decided, ModelRunRefusal):
            return decided
        catalog = self._read_catalog()
        entry = catalog.entry(selection.lane) if isinstance(catalog, ProviderCatalog) else None
        return _model_lane(decided, selection.model, entry)

    def _decide(self, selection: ModelRoleSelection) -> ModelRunLane | ModelRunRefusal:
        catalog = self._read_catalog()
        if isinstance(catalog, ModelRunRefusal):
            return catalog
        entry = catalog.entry(selection.lane)
        if entry is None:
            return ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        resolution = self._resolver.resolve(entry.id, ProviderConsumer.ASSISTANT)
        if isinstance(resolution, ProviderCredentialUnavailable):
            return ModelRunRefusal(code=_SIGNED_OUT.get(resolution.reason, ModelRunRefusalCode.LANE_UNAVAILABLE))
        del resolution
        lane = _model_lane(
            ModelRunLane(
                provider_id=entry.provider,
                transport=entry.transport.value,
                model=selection.model,
                reads_off_host=entry.reads_off_host,
                licence=None,
                size_bytes=None,
                vision=None,
                context_length=None,
            ),
            selection.model,
            entry,
        )
        return lane.model_copy(update={"accepted_media": self._gateway.accepted_media(lane)})

    def _read_catalog(self) -> ProviderCatalog | ModelRunRefusal:
        if self._catalog is None:
            try:
                self._catalog = self._catalog_source.catalog()
            except ProviderCatalogUnavailableError:
                self._catalog = ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        return self._catalog


def _model_lane(lane: ModelRunLane, model_id: str, entry: ProviderCatalogEntry | None) -> ModelRunLane:
    """Return ``lane`` carrying ``model_id`` and the facts the lane's catalogue entry states for that model.

    A model the entry does not list carries no fact: each is ``None``, never a value borrowed from another model.
    """
    model = None if entry is None else entry.model(model_id)
    licence = None if model is None else model.licence
    return ModelRunLane(
        provider_id=lane.provider_id,
        transport=lane.transport,
        model=model_id,
        reads_off_host=lane.reads_off_host,
        licence=None
        if licence is None
        else ModelRunLicence(spdx=licence.spdx, name=licence.name, digest=licence.digest),
        size_bytes=None if model is None else model.size_bytes,
        vision=None if model is None else model.vision,
        context_length=None if model is None else model.context_length,
        accepted_media=lane.accepted_media,
    )


__all__ = ["BackgroundRunGateway", "ModelRunService"]
