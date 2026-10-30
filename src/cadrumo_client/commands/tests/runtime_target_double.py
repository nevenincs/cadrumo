"""Answer the runtime's profile questions in tests whose runtime client is a double.

The answers come from the canonical profile resolver and selection read the
runtime itself uses, over the test's storage root, so only the connection is
replaced.
"""

from __future__ import annotations

import pytest

from cadrumo.application.workflow.errors import ProfileLabelAmbiguousError
from cadrumo.application.workflow.profile_bucket_scan import resolve_profile_bucket
from cadrumo.core.bucket_pointer import read_pointer_selection
from cadrumo.core.config import load_settings
from cadrumo_client.commands import profile_selection
from cadrumo_client.commands.profile_selection import LoginTarget


def _resolved(name: str) -> LoginTarget | None:
    try:
        pointer = resolve_profile_bucket(name.strip())
    except ProfileLabelAmbiguousError:
        return None
    return None if pointer is None else LoginTarget(str(pointer.bucket_id), pointer.label)


def _selected() -> str | None:
    return read_pointer_selection(load_settings().cadrumo_storage_root).bucket_id


def answer_login_targets_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve login targets and the selection as the runtime does, without a runtime to ask."""
    monkeypatch.setattr(profile_selection, "runtime_login_target", _resolved)
    monkeypatch.setattr(profile_selection, "runtime_selected_profile_id", _selected)
