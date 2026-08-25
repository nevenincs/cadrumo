"""Helpers for opening Sede browser contexts from encrypted auth sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import cadrumo.adapters.outbound.aeat.auth.session_store as session_store

from .....core.i18n import tr
from .errors import SedeNavigationError

if TYPE_CHECKING:
    from ..auth.authenticator_types import AeatSession


def storage_state_for_session(session: AeatSession) -> dict[str, object]:
    """Return decrypted Playwright storage state for an authenticated session."""
    if session.storage_state_path is None:
        raise SedeNavigationError(
            "AeatSession has no persisted auth session; run `aeat config auth status` first",
            translated_message=tr("adapters.sede.errors.no_auth_session"),
        )
    persisted = session_store.load(session.storage_state_path)
    if persisted is None:
        raise SedeNavigationError(
            "AEAT auth session is not persisted; run `aeat config auth status` first",
            translated_message=tr("adapters.sede.errors.no_auth_session"),
        )
    return dict(persisted.storage_state)
