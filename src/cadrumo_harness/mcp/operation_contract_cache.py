"""Remember public operation descriptions for exactly one admitted session."""

from __future__ import annotations

from uuid import UUID

from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1
from cadrumo_client.transport.frontend_client import FrontendClient


class OperationContractCache:
    """Hold descriptions by definition ID for the session that fetched them.

    A description is never served to another profile or session: the first use
    by a different admitted identity discards everything remembered. An entry is
    also dropped when the runtime reports another contract digest for its
    definition, or refuses the definition on a fresh read.
    """

    def __init__(self) -> None:
        """Start with no remembered session."""
        self._owner: tuple[UUID, UUID] | None = None
        self._entries: dict[str, OperationPublicDefinitionDescriptionV1] = {}

    def clear(self) -> None:
        """Forget every description and the session that owned them."""
        self._owner = None
        self._entries.clear()

    def description(
        self,
        client: FrontendClient,
        definition_id: str,
        *,
        deadline: float,
        digest: str | None = None,
        fresh: bool = False,
    ) -> OperationPublicDefinitionDescriptionV1:
        """Return a remembered description, or read it from the runtime and remember it.

        ``fresh`` always reads. ``digest`` is the contract digest the caller has
        just seen the runtime report; a remembered description with another
        digest is stale and is read again.
        """
        self._bind(client)
        if not fresh:
            remembered = self._entries.get(definition_id)
            if remembered is not None and (digest is None or remembered.contract.definition_contract_digest == digest):
                return remembered
        try:
            description = client.describe(definition_id, deadline=deadline)
        except Exception:
            self._entries.pop(definition_id, None)
            raise
        self._entries[definition_id] = description
        return description

    def _bind(self, client: FrontendClient) -> None:
        owner = (client.profile_id, client.session_id)
        if owner != self._owner:
            self._entries.clear()
            self._owner = owner
