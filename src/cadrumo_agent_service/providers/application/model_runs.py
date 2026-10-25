"""Which lane answers a tax model run, and the run itself, for one admitted profile.

A tax worker's model run names its role and never a lane. The lane and model
are the ones the person selected for that role, stored in the profile's
own model-role selections record. A role with no selection refuses ``no_selection``. Nothing
stands in for a missing selection: not another lane, not another role's
choice, not a catalogue default. A selected lane that is turned off, no longer
reported or not reachable refuses ``lane_unavailable``. Any lane is eligible,
API or CLI; whether a lane takes an attachment is what the ready agent's live
catalog reports for background requests, read in the same lookup, and never
inferred from its transport.

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
    ModelRunMediaKind,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunRoleSelection,
    ModelRunSelectedModel,
    model_run_media_kind,
)

from ..domain.catalog import ProviderConsumer
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
            return ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)
        read = self._read_selections()
        if isinstance(read, ModelRunRefusal):
            return read
        return self._resolve(model_role, read)[1]

    def selections(self) -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
        """Return every role's selection and the lane a run would use or why it would refuse.

        The record is read once, so every role is reported from the same state.
        """
        read = self._read_selections()
        if isinstance(read, ModelRunRefusal):
            return read
        states: list[ModelRunRoleSelection] = []
        for model_role in ModelRole:
            selected, answer = self._resolve(model_role, read)
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

    def _resolve(
        self, model_role: ModelRole, read: ModelRoleSelectionsRead
    ) -> tuple[ModelRoleSelection | None, ModelRunLane | ModelRunRefusal]:
        """Return the role's stored selection, if readable, and the lane it resolves to or the refusal."""
        if isinstance(read, UnreadableModelRoleSelections):
            # An unreadable record says nothing about any role, so no role reads as unselected.
            return None, ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        selection = None if isinstance(read, AbsentModelRoleSelections) else read.record.selection(model_role)
        if selection is None:
            return None, ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)
        try:
            entry = self._catalog_source.catalog().entry(selection.lane)
        except ProviderCatalogUnavailableError:
            return selection, ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        if entry is None:
            return selection, ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        resolution = self._resolver.resolve(entry.id, ProviderConsumer.ASSISTANT)
        if isinstance(resolution, ProviderCredentialUnavailable):
            code = _SIGNED_OUT.get(resolution.reason, ModelRunRefusalCode.LANE_UNAVAILABLE)
            return selection, ModelRunRefusal(code=code)
        lane = ModelRunLane(provider_id=entry.provider, transport=entry.transport.value, model=selection.model)
        return selection, lane.model_copy(update={"accepted_media": self._gateway.accepted_media(lane)})

    def run(self, header: ModelRunHeader, body: ModelRunBody) -> ModelRunOutput | ModelRunRefusal:
        """Run one request on the lane its role resolves to now.

        A run carrying consent is refused when that lane is not the one the
        consent was recorded for. An attachment the lane's catalog entry says
        it does not take is refused before anything is sent.
        """
        lane = self.lookup(header.role)
        if isinstance(lane, ModelRunRefusal):
            return lane
        if header.consent is not None and not header.consent.matches(lane):
            return ModelRunRefusal(code=ModelRunRefusalCode.CONSENT_MISSING)
        if lane.accepted_media is not None:
            for attachment in body.attachments:
                if model_run_media_kind(attachment.media_type) not in lane.accepted_media:
                    return ModelRunRefusal(code=ModelRunRefusalCode.INPUT_NOT_SUPPORTED)
        return self._gateway.run(lane=lane, body=body, deadline_seconds=header.deadline_seconds)


__all__ = ["BackgroundRunGateway", "ModelRunService"]
