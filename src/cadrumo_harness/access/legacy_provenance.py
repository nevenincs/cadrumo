"""Explicit maintenance decoding of historical coding-agent provenance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ProvenanceUpgrade:
    """Replacement plus original encrypted-custody evidence; never log either payload."""

    original: bytes
    replacement: bytes
    original_digest: str
    changed_fields: tuple[str, ...]


def _legacy_actor(value: str) -> str | None:
    if not value.startswith("agent:"):
        return None
    parts = value.removeprefix("agent:").split(".")
    if len(parts) != 3:
        return None
    frontend, kind, identifier = parts
    replacement = {"mcp": "external-client", "agent-host": "installed-service"}.get(frontend)
    if replacement is None or kind not in {"human", "attended", "api_key"}:
        return None
    try:
        client_id = UUID(identifier)
    except ValueError:
        return None
    return f"automation:{replacement}.{kind}.{client_id}"


def upgrade_legacy_provenance(
    payload: bytes, *, actor_fields: tuple[str, ...], origin_fields: tuple[str, ...]
) -> ProvenanceUpgrade:
    """Upgrade only explicitly selected top-level fields of an authorized record.

    The maintenance caller owns namespace admission, CAS and encrypted evidence
    persistence. Arbitrary strings and nested taxpayer fields are never scanned.
    This conversion supplies no authentication or operation authority.
    """
    document: Any = json.loads(payload)
    if not isinstance(document, dict):
        raise ValueError("provenance record must be an object")
    changed: list[str] = []
    for field in actor_fields:
        value = document.get(field)
        replacement = _legacy_actor(value) if isinstance(value, str) else None
        if replacement is not None:
            document[field] = replacement
            changed.append(field)
    for field in origin_fields:
        if document.get(field) == "agent":
            document[field] = "automation"
            changed.append(field)
    replacement = (
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if changed
        else payload
    )
    return ProvenanceUpgrade(
        original=payload,
        replacement=replacement,
        original_digest=hashlib.sha256(payload).hexdigest(),
        changed_fields=tuple(sorted(set(changed))),
    )
