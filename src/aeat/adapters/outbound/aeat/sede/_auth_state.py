"""Helpers for opening Sede browser contexts from encrypted auth sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..auth import _session_store
from ._errors import SedeNavigationError

if TYPE_CHECKING:
    from ..auth._authenticator import AeatSession


def storage_state_for_session(session: AeatSession) -> dict[str, object]:
    """Return decrypted Playwright storage state for an authenticated session."""

    if session.storage_state_path is None:
        raise SedeNavigationError("AeatSession has no persisted auth session; run `aeat config auth status` first")
    persisted = _session_store.load(session.storage_state_path)
    if persisted is None:
        raise SedeNavigationError("AEAT auth session is not persisted; run `aeat config auth status` first")
    return dict(persisted.storage_state)
