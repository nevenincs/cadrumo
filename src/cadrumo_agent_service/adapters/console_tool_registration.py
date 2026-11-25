"""Register the ``cadrumo-mcp`` tool server for the provider programs a person runs in the desktop console.

The console runs Claude Code in the profile's agent workspace and Codex with
the profile's ``CODEX_HOME``. Each provider program finds its tool servers in a
file of its own form: Claude Code in the workspace's ``.mcp.json``, admitted
without a prompt when ``.claude/settings.local.json`` lists the server in
``enabledMcpjsonServers``; Codex in ``config.toml`` in its home, as an
``[mcp_servers.<name>]`` table. This module writes the ``cadrumo`` entry of
each and keeps every other entry a person or the provider wrote.

An entry names a launcher, its arguments and the storage and profile locations
the launcher serves; never a credential. A launcher started this way is
admitted or refused by the runtime and MCP admission alone, so nothing written
here grants authority.

The agent's own runs never read these files: its Claude sessions admit only
injected tool servers and its Codex sessions run with a per-run home, so the
console's registration cannot reach a hosted run.

Each write is atomic and happens only when the content changes. A file that is
not a well-formed document of its provider's form is a person's to repair and
is kept as it is.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from cadrumo.core.atomic_write import atomic_write_text

TOOL_SERVER_NAME: Final = "cadrumo"
"""The name each provider's registration gives the ``cadrumo-mcp`` tool server."""
CLAUDE_REGISTRATION: Final = ".mcp.json"
"""Claude Code's project tool server file, at the workspace root."""
CLAUDE_LOCAL_SETTINGS: Final = (".claude", "settings.local.json")
"""Claude Code's project-local settings, which admit a project tool server without a prompt."""
CODEX_REGISTRATION: Final = "config.toml"
"""Codex's configuration file, in its home."""

_OWN_TABLE: Final = re.compile(
    rf"^\s*\[\s*mcp_servers\s*\.\s*(?:{TOOL_SERVER_NAME}|\"{TOOL_SERVER_NAME}\"|'{TOOL_SERVER_NAME}')\s*(?:\..*)?\]\s*(?:#.*)?$"
)
_ANY_TABLE: Final = re.compile(r"^\s*\[")


class RegistrationNotKeptError(ValueError):
    """An existing registration file is not a document of its provider's form, so it is kept untouched."""


def register_console_tool_server(
    *,
    workspace: Path,
    codex_home: Path | None,
    launcher: Path,
    arguments: Sequence[str],
    environment: Mapping[str, str],
) -> None:
    """Write the ``cadrumo`` tool server entry for Claude Code in ``workspace`` and Codex in ``codex_home``.

    ``environment`` holds the locations the launcher serves; it is written into
    each entry because Codex starts a tool server with only a fixed set of the
    console's variables.

    Raises:
        OSError: When a file cannot be read or written.
    """
    server: dict[str, Any] = {"command": str(launcher), "args": list(arguments), "env": dict(environment)}
    _keep_or_update(workspace / CLAUDE_REGISTRATION, lambda text: _claude_registration(text, server))
    _keep_or_update(workspace.joinpath(*CLAUDE_LOCAL_SETTINGS), _claude_local_settings)
    if codex_home is not None:
        codex_home.mkdir(parents=True, exist_ok=True)
        _keep_or_update(codex_home / CODEX_REGISTRATION, lambda text: _codex_registration(text, server))


def _keep_or_update(path: Path, render: Callable[[str | None], str]) -> None:
    try:
        existing = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = None
    except UnicodeDecodeError:
        return
    try:
        updated = render(existing)
    except RegistrationNotKeptError:
        return
    if updated != existing:
        atomic_write_text(path, updated)


def _json_object(text: str | None) -> dict[str, Any]:
    if text is None or not text.strip():
        return {}
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise RegistrationNotKeptError(str(exc)) from exc
    if not isinstance(document, dict):
        raise RegistrationNotKeptError("not a JSON object")
    return document


def _json_text(document: Mapping[str, Any]) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _claude_registration(text: str | None, server: Mapping[str, Any]) -> str:
    document = _json_object(text)
    servers = document.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise RegistrationNotKeptError("mcpServers is not an object")
    document["mcpServers"] = {**servers, TOOL_SERVER_NAME: {"type": "stdio", **server}}
    return _json_text(document)


def _claude_local_settings(text: str | None) -> str:
    document = _json_object(text)
    enabled = document.get("enabledMcpjsonServers", [])
    if not isinstance(enabled, list):
        raise RegistrationNotKeptError("enabledMcpjsonServers is not a list")
    if TOOL_SERVER_NAME not in enabled:
        document["enabledMcpjsonServers"] = [*enabled, TOOL_SERVER_NAME]
    return _json_text(document)


def _toml_string(value: str) -> str:
    # A JSON string without ASCII escaping is a TOML basic string: both escape
    # the quote, the backslash and control characters the same way.
    return json.dumps(value, ensure_ascii=False)


def _codex_table(server: Mapping[str, Any]) -> str:
    arguments = ", ".join(_toml_string(argument) for argument in server["args"])
    environment = ", ".join(f"{_toml_string(name)} = {_toml_string(value)}" for name, value in server["env"].items())
    return (
        f"[mcp_servers.{TOOL_SERVER_NAME}]\n"
        f"command = {_toml_string(server['command'])}\n"
        f"args = [{arguments}]\n"
        f"env = {{ {environment} }}\n"
    )


def _without_own_tables(text: str) -> str:
    kept: list[str] = []
    own = False
    for line in text.splitlines():
        if _ANY_TABLE.match(line):
            own = _OWN_TABLE.match(line) is not None
        if not own:
            kept.append(line)
    return "\n".join(kept).rstrip()


def _codex_registration(text: str | None, server: Mapping[str, Any]) -> str:
    existing = "" if text is None else text
    try:
        tomllib.loads(existing)
    except tomllib.TOMLDecodeError as exc:
        raise RegistrationNotKeptError(str(exc)) from exc
    rest = _without_own_tables(existing)
    updated = (rest + "\n\n" if rest else "") + _codex_table(server)
    try:
        parsed = tomllib.loads(updated)
    except tomllib.TOMLDecodeError as exc:
        # The person declared the entry in a form this module does not replace, such as dotted keys.
        raise RegistrationNotKeptError(str(exc)) from exc
    if parsed.get("mcp_servers", {}).get(TOOL_SERVER_NAME) != dict(server):
        raise RegistrationNotKeptError("the entry does not read back as written")
    return updated


__all__ = [
    "CLAUDE_LOCAL_SETTINGS",
    "CLAUDE_REGISTRATION",
    "CODEX_REGISTRATION",
    "TOOL_SERVER_NAME",
    "RegistrationNotKeptError",
    "register_console_tool_server",
]
