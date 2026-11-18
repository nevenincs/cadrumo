"""Synthetic catalog answers as the service relays them, each conforming to the served schema.

The agent's schema closes a lane's provider to the providers it serves, so these lanes name real
providers (a hosted ``deepseek`` lane and the local ``llamacpp`` engine's lane); every model, name and
digest is invented. Times are read from the clock so no year is written into the documents.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

from pydantic import JsonValue, TypeAdapter

_DIGEST = "sha256:" + "0" * 64
_DOCUMENT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _health(*, local: bool) -> dict[str, Any]:
    health: dict[str, Any] = {
        "configured": "available",
        "transport": "available",
        "authentication": "not_applicable" if local else "authenticated",
        "catalog": "available",
        "admission": "unproven",
        "selectable": True,
        "reasons": [],
        "checked_at": _now(),
    }
    if local:
        health["engine"] = {"engine": "llamacpp", "state": "running", "reason": None, "door": None}
    return health


def _model(entry: str, *, installed: bool | None) -> dict[str, Any]:
    model: dict[str, Any] = {
        "entry_id": entry,
        "model": entry,
        "display_name": f"Synthetic {entry}",
        "description": None,
        "capabilities": [],
        "native_control_ids": [],
        "efforts": ["low", "high"],
        "default_effort": "low",
        "multi_agent_generation": None,
        "vision": False,
        "size_bytes": None,
        "context_length": 8192,
        "licence": {"spdx": None, "name": "Synthetic licence", "digest": _DIGEST},
        "llamacpp_default_context": None,
    }
    if installed is not None:
        model["installed"] = installed
    return model


def _lane(provider: str, transport: str, *, local: bool) -> dict[str, Any]:
    entry = f"synthetic-{provider}-model"
    return {
        "provider_id": provider,
        "transport": transport,
        "display_name": f"Synthetic {provider}",
        "auth_kind": "none" if local else "api_key",
        "execution_mode": "synthetic",
        "executable": True,
        "model_source": "catalog",
        "health": _health(local=local),
        "catalog": {
            "schema_version": 2,
            "state": {
                "status": "available",
                "checked_at": _now(),
                "revision": None,
                "expires_at": None,
                "reason": None,
            },
            "recommended_entry_id": entry,
            "recommended": {"text": entry},
            # A hosted lane downloads nothing, so the service leaves ``installed`` out of its models.
            "models": [_model(entry, installed=True if local else None)],
            "native_controls": [],
        },
        "hosted_certification": "unknown",
        "capability_proofs": [],
        "background_requests": {
            "text": "proven",
            "image": "unsupported",
            "pdf": "unsupported",
            "options": [],
            "accepts_images": False,
            "accepts_pdfs": False,
        },
        "model_download": "required" if local else "none",
    }


def served_catalog() -> dict[str, JsonValue]:
    """A running agent's catalog as the service relays it: one hosted lane and the local engine's lane."""
    return _DOCUMENT.validate_python(
        {
            "api_version": "v1",
            "providers": [_lane("deepseek", "api", local=False), _lane("llamacpp", "api", local=True)],
        }
    )


def declared_catalog() -> dict[str, JsonValue]:
    """The catalog the agent declares before it runs, in the service's envelope."""
    lane = {
        "id": "deepseek_api",
        "provider": "deepseek",
        "transport": "api",
        "display_name": "Synthetic deepseek",
        "description": "A synthetic declared lane.",
        "auth_kind": "api_key",
        "default_base_url": None,
        "agent_credential_id": None,
        "reads_off_host": True,
        "cli_programs": [],
        "icon": None,
        "platform": {
            "docs_url": None,
            "models_url": None,
            "status": {"kind": "none", "page_url": None, "api_url": None},
        },
        "default_model": None,
        "models": [],
        "recommended": {},
        "background": {"runnable": False, "inputs": [], "options": []},
        "unread": [],
        "model_download": "none",
    }
    attribution = dict.fromkeys(("title", "url", "pin", "licence", "notice", "trademarks"), "Synthetic attribution")
    return _DOCUMENT.validate_python(
        {"kind": "declared", "catalog": {"schema_version": 7, "providers": [lane], "icon_attribution": attribution}}
    )


def changed(document: dict[str, JsonValue], path: tuple[str | int, ...], value: object) -> dict[str, JsonValue]:
    """A copy of ``document`` with the value at ``path`` replaced, or removed when ``value`` is ``...``."""
    copied = copy.deepcopy(document)
    cursor: Any = copied
    for step in path[:-1]:
        cursor = cursor[step]
    if value is ...:
        del cursor[path[-1]]
    else:
        cursor[path[-1]] = value
    return _DOCUMENT.validate_python(copied)
