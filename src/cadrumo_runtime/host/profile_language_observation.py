"""Publish language hint invalidations for held profile sessions."""

from __future__ import annotations

from _thread import RLock
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.storage.bucket.output_language_hint import read_bucket_output_language_hint
from cadrumo_client.contracts.session_events import ProfileLanguageChanged

from .profile_connection import ProfileConnection
from .session_events import RuntimeSessionEvents


def observe_language(
    profile_id: UUID,
    *,
    root: Path,
    boot: UUID,
    guard: RLock,
    connections: dict[UUID, ProfileConnection],
    observations: dict[UUID, tuple[UUID, str | None]],
    events: RuntimeSessionEvents,
    establish_baseline: bool,
) -> None:
    """Publish only changes to the hint observed by an existing session."""
    try:
        language = read_bucket_output_language_hint(storage_root=root, bucket_id=str(profile_id))
    except Exception:
        return
    changed: list[ProfileLanguageChanged] = []
    with guard:
        for connection_id, connection in connections.items():
            session_id = connection.session_id
            if connection.profile_id != profile_id or session_id is None:
                continue
            previous = observations.get(connection_id)
            if previous == (session_id, language):
                continue
            observations[connection_id] = session_id, language
            if establish_baseline and (previous is None or previous[0] != session_id):
                # Before its first operation this session has no canonical
                # read to invalidate. Later changes still publish a cue.
                continue
            changed.append(
                ProfileLanguageChanged(
                    runtime_boot_id=boot,
                    connection_id=connection_id,
                    profile_id=profile_id,
                    session_id=session_id,
                )
            )
    for event in changed:
        events.publish(event)
