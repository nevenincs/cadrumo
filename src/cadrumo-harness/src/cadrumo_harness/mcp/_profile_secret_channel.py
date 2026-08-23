"""One-shot local profile-secret channel for installed MCP subprocesses.

Secrets never travel over MCP, argv, environment variables, logs, or retained
evidence.  An operator-owned launcher may provide a bounded strict-JSON file;
the server reads and unlinks it at startup, keeps only the validated value in
memory, and frames it onto each profile-authenticated CLI child's stdin.
"""

from __future__ import annotations

import json
from pathlib import Path

from cadrumo.entrypoints.cli.command_api import build_verb_input_schemas, command_schema_refs

_MAX_PAYLOAD_BYTES = 8_192
_profile_passphrase: str | None = None
_profile_field: str | None = None


def _authoritative_fields() -> tuple[str, ...]:
    command_keys = tuple(reference.command for reference in command_schema_refs())
    contracts = {
        tuple(field.name for field in schema.profile_authentication_contract.fields)
        for schema in build_verb_input_schemas(command_keys).values()
        if schema.profile_authentication != "not-applicable"
    }
    if len(contracts) != 1 or len(next(iter(contracts))) != 1:
        raise RuntimeError(f"profile-authentication contract drifted: {sorted(contracts)!r}")
    return next(iter(contracts))


def load_profile_secret_file(path: Path) -> None:
    """Consume one bounded strict payload and remove its filesystem bytes."""
    global _profile_field, _profile_passphrase
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise RuntimeError("profile-secret channel must not be a symbolic link")
    resolved = expanded.resolve(strict=True)
    if not resolved.is_file():
        raise RuntimeError("profile-secret channel must be a regular file")
    payload = resolved.read_bytes()
    resolved.unlink()
    if not payload or len(payload) > _MAX_PAYLOAD_BYTES:
        raise RuntimeError("profile-secret channel payload is empty or oversized")
    try:
        pairs = json.loads(payload, object_pairs_hook=lambda value: value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("profile-secret channel payload is not strict JSON") from exc
    expected = _authoritative_fields()
    if not isinstance(pairs, list) or tuple(name for name, _ in pairs) != expected:
        raise RuntimeError(f"profile-secret channel fields must be exactly {expected!r}")
    passphrase = pairs[0][1]
    if not isinstance(passphrase, str) or not passphrase:
        raise RuntimeError("profile-secret channel passphrase must be a non-empty string")
    _profile_passphrase = passphrase
    _profile_field = expected[0]


def profile_secret_stdin_payload() -> str | None:
    """Return the in-memory secret framed for the canonical CLI stdin channel."""
    if _profile_passphrase is None or _profile_field is None:
        return None
    return json.dumps({_profile_field: _profile_passphrase}, ensure_ascii=False, separators=(",", ":"))


def clear_profile_secret() -> None:
    """Forget the in-memory secret after server shutdown or a test."""
    global _profile_field, _profile_passphrase
    _profile_passphrase = None
    _profile_field = None


__all__ = ["clear_profile_secret", "load_profile_secret_file", "profile_secret_stdin_payload"]
