"""Refuse an agent bundle whose served API is not the one Cadrumo pins.

The agent service validates what cadrumo-agent serves against the agent's own
OpenAPI document, pinned in this repository with the agent commit it came from.
A bundle built from a checkout whose document differs would ship a service that
validates against another API than the one the agent it hosts serves.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from dev.paths import REPO_ROOT

PIN_DIRECTORY = REPO_ROOT / "src/cadrumo_agent_service/_data/agent_api"
PIN_RECORD = "pin.json"
_PIN_KEYS = frozenset({"source", "path", "commit", "sha256"})
_COMMIT = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class AgentApiPinError(ValueError):
    """The bundled cadrumo-agent serves another API than the pinned one, or the pin is malformed."""


@dataclass(frozen=True, slots=True)
class AgentApiPin:
    """A validated pin: the pinned document's path in the checkout, its agent commit and digest."""

    path: str
    commit: str
    sha256: str
    pinned: Path


def _read_record(record_path: Path) -> dict[str, str]:
    """The pin record's text fields, refused unless it holds exactly the expected keys."""
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AgentApiPinError(f"The agent API pin record {record_path} cannot be read: {error}") from error
    if not isinstance(record, dict) or set(record) != _PIN_KEYS or not all(isinstance(v, str) for v in record.values()):
        raise AgentApiPinError(
            f"The agent API pin record {record_path} must be an object with exactly the text keys "
            f"{', '.join(sorted(_PIN_KEYS))}"
        )
    return {str(key): str(value) for key, value in record.items()}


def _validate_record(record: dict[str, str], record_path: Path) -> Path:
    """Refuse a record naming another source, a path outside the checkout or a malformed digest; answer its path."""
    if record["source"] != "cadrumo-agent":
        raise AgentApiPinError(
            f"The agent API pin record {record_path} names source {record['source']!r}, not 'cadrumo-agent'"
        )
    relative = Path(record["path"])
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise AgentApiPinError(
            f"The agent API pin record {record_path} names path {record['path']!r}, not one inside the checkout"
        )
    if not _COMMIT.fullmatch(record["commit"]) or not _SHA256.fullmatch(record["sha256"]):
        raise AgentApiPinError(
            f"The agent API pin record {record_path} must name a full 40-hex commit and a 64-hex sha256"
        )
    return relative


def _require_digest(pinned: Path, sha256: str, record_path: Path) -> None:
    """Refuse a pinned document that does not hash to the digest its record names."""
    try:
        pinned_bytes = pinned.read_bytes()
    except OSError as error:
        raise AgentApiPinError(f"The pinned agent API {pinned} cannot be read: {error}") from error
    if hashlib.sha256(pinned_bytes).hexdigest() != sha256:
        raise AgentApiPinError(
            f"The pinned agent API {pinned} does not hash to the sha256 its pin record {record_path} names; "
            "re-pin both together"
        )


def _pin(directory: Path) -> AgentApiPin:
    record_path = directory / PIN_RECORD
    record = _read_record(record_path)
    pinned = directory / _validate_record(record, record_path).name
    _require_digest(pinned, record["sha256"], record_path)
    return AgentApiPin(path=record["path"], commit=record["commit"], sha256=record["sha256"], pinned=pinned)


def require_pinned_agent_api(source: Path, directory: Path = PIN_DIRECTORY) -> None:
    """Refuse a cadrumo-agent checkout whose OpenAPI document differs byte for byte from the pinned one."""
    pin = _pin(directory)
    served = source / pin.path
    try:
        served_bytes = served.read_bytes()
    except OSError as error:
        raise AgentApiPinError(
            f"The bundled cadrumo-agent checkout {source} has no readable {pin.path} ({error}); "
            f"Cadrumo pins the one at cadrumo-agent commit {pin.commit}"
        ) from error
    if served_bytes == pin.pinned.read_bytes():
        return
    raise AgentApiPinError(
        f"The bundled cadrumo-agent checkout {source} serves another API than Cadrumo pins: its "
        f"{pin.path} has sha256 {hashlib.sha256(served_bytes).hexdigest()}, the pinned {pin.pinned} has "
        f"{pin.sha256} (cadrumo-agent commit {pin.commit}). Bundle the pinned agent commit, or re-pin "
        "the agent API together with the agent service's validation of it."
    )
