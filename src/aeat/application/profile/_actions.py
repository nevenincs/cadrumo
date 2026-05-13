"""Application services for autónomo profile management."""

from __future__ import annotations

import json
from typing import Any

from ..workflow._models import WorkflowState
from ..workflow._utils import _normalise_key, utc_now
from ._models import ProfileRecord


def _coerce_profile_record(raw: dict[str, Any]) -> ProfileRecord:
    """Round-trip a raw mapping into a strict :class:`ProfileRecord`.

    The persistence layer rehydrates ``WorkflowState.profiles`` values
    as plain dicts (the field is typed ``dict[str, Any]``), so any
    timestamp survives as an ISO-8601 string. Strict-mode
    ``model_validate`` would refuse to coerce that string back into a
    ``datetime``; routing through ``model_validate_json`` accepts the
    ISO-8601 form via the JSON parser's typed coercion.
    """

    return ProfileRecord.model_validate_json(json.dumps(raw, default=str))


def set_active_profile(state: WorkflowState, name: str) -> WorkflowState:
    """Select or create an active profile."""

    profile_name = name.strip()
    if not profile_name:
        raise ValueError("profile name must not be blank")
    profiles = dict(state.profiles)
    if profile_name not in profiles:
        profiles[profile_name] = ProfileRecord(name=profile_name)
    return state.model_copy(update={"active_profile": profile_name, "profiles": profiles, "updated_at": utc_now()})


def set_profile_values(state: WorkflowState, profile_name: str, values: dict[str, str]) -> WorkflowState:
    """Merge values into one profile and select it."""

    profiles = dict(state.profiles)
    current = profiles.get(profile_name, ProfileRecord(name=profile_name))
    if isinstance(current, dict):
        current = _coerce_profile_record(current)

    merged = {**current.values, **{_normalise_key(key): raw.strip() for key, raw in values.items()}}
    profiles[profile_name] = current.model_copy(update={"values": merged, "updated_at": utc_now()})
    return state.model_copy(update={"active_profile": profile_name, "profiles": profiles, "updated_at": utc_now()})


def clear_profile_values(state: WorkflowState, profile_name: str, keys: tuple[str, ...]) -> WorkflowState:
    """Clear values from one profile and select it."""

    profiles = dict(state.profiles)
    current = profiles.get(profile_name, ProfileRecord(name=profile_name))
    if isinstance(current, dict):
        current = _coerce_profile_record(current)

    values = dict(current.values)
    for key in keys:
        values.pop(_normalise_key(key), None)
    profiles[profile_name] = current.model_copy(update={"values": values, "updated_at": utc_now()})
    return state.model_copy(update={"active_profile": profile_name, "profiles": profiles, "updated_at": utc_now()})
