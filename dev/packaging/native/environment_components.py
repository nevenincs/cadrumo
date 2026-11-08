"""Validate native host and packaged component declarations."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .environment_declaration_constants import BASE_NAME, SLOT
from .environment_declaration_primitives import (
    fail,
    require_integer,
    require_keys,
    require_relative,
    require_strings,
    require_table,
)


def declare_temporary_member(raw: object) -> dict[str, Any]:
    """Validate the declared temporary-member policy."""
    entry = require_table(raw, "pins.temporary_member")
    require_keys(entry, "pins.temporary_member", {"default"})
    return {"default": require_relative(entry["default"], "pins.temporary_member.default")}


def declare_host_classes(raw: object) -> dict[str, Any]:
    """Validate the declared host classes."""
    entry = require_table(raw, "host_classes")
    require_keys(entry, "host_classes", {"cleared_prefixes", "cleared_names", "namespace_prefix"})
    prefix = entry["namespace_prefix"]
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*_", prefix):
        raise fail("host_classes.namespace_prefix must be an upper-case prefix ending in an underscore")
    return {
        "cleared_prefixes": list(
            require_strings(entry["cleared_prefixes"], "host_classes.cleared_prefixes", BASE_NAME)
        ),
        "cleared_names": list(require_strings(entry["cleared_names"], "host_classes.cleared_names", BASE_NAME)),
        "namespace_prefix": prefix,
    }


def declare_native_host(raw: object) -> dict[str, Any]:
    """Validate the declared native host."""
    entry = require_table(raw, "native_host")
    require_keys(entry, "native_host", {"owner", "first", "last", "launch_profile_refused", "refusals"})
    if not isinstance(entry["owner"], str) or not SLOT.fullmatch(entry["owner"]):
        raise fail("native_host.owner must be a lower-case token")
    first = require_integer(entry["first"], "native_host.first")
    last = require_integer(entry["last"], "native_host.last", minimum=first)
    refused = require_integer(entry["launch_profile_refused"], "native_host.launch_profile_refused")
    # POSIX reports only the low byte of an exit status.
    if last > 0xFF or not first <= refused <= last:
        raise fail("native_host exit codes must lie in one byte and hold launch_profile_refused")
    return {
        "owner": entry["owner"],
        "first": first,
        "last": last,
        "launch_profile_refused": refused,
        "refusals": list(require_strings(entry["refusals"], "native_host.refusals", SLOT)),
    }


_COMPONENT_PATHS = (
    "console_workspace",
    "webview",
    "manager_log_file",
    "manager_preferences",
    "manager_failed_versions",
    "logs",
    "log_file",
)
_COMPONENT_VALUES = (
    "log_format",
    "log_max_bytes",
    "log_backups",
    "language_variable",
    "language_default",
    "profile_variable",
    "local_ai_address",
    "llama_server_address",
)
#: Each local AI server's address: IPv4 loopback, a port outside the privileged range and
#: below every platform's ephemeral range, and never the publisher's default port.
_LOCAL_AI_ADDRESS = re.compile(r"127\.0\.0\.1:(?P<port>[1-9][0-9]{3,4})")
_LOCAL_AI_PORTS = range(1024, 32768)
_LOCAL_AI_UPSTREAM_PORT = 11434


def declare_components(raw: object, names: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    """Validate the declared installable components against the manager strings."""
    entry = require_table(raw, "components")
    require_keys(entry, "components", {*_COMPONENT_PATHS, *_COMPONENT_VALUES})
    components: dict[str, Any] = {key: require_relative(entry[key], f"components.{key}") for key in _COMPONENT_PATHS}
    if not components["log_file"].startswith(components["logs"] + "/"):
        raise fail("components.log_file must lie in components.logs")
    if not isinstance(entry["log_format"], str) or not entry["log_format"]:
        raise fail("components.log_format must be a non-empty string")
    if names.get(entry["language_variable"], {}).get("kind") != "language":
        raise fail("components.language_variable must name a declared language name")
    language = entry["language_default"]
    if not isinstance(language, str) or not re.fullmatch(r"[a-z]{2}", language):
        raise fail("components.language_default must be a two-letter lower-case language")
    if names.get(entry["profile_variable"]) != {"kind": "directory", "role": "slot"}:
        raise fail("components.profile_variable must name a declared directory slot")
    address = _local_ai_address(entry, "local_ai_address")
    llama_server_address = _local_ai_address(entry, "llama_server_address")
    if llama_server_address == address:
        raise fail("components.llama_server_address must differ from components.local_ai_address")
    components.update(
        log_format=entry["log_format"],
        log_max_bytes=require_integer(entry["log_max_bytes"], "components.log_max_bytes"),
        log_backups=require_integer(entry["log_backups"], "components.log_backups", minimum=0),
        language_variable=entry["language_variable"],
        language_default=language,
        profile_variable=entry["profile_variable"],
        local_ai_address=address,
        llama_server_address=llama_server_address,
    )
    return components


def _local_ai_address(entry: dict[str, Any], key: str) -> str:
    address = entry[key]
    refusal = f"components.{key} must be 127.0.0.1 with a port from 1024 to 32767 other than 11434"
    if not isinstance(address, str):
        raise fail(refusal)
    matched = _LOCAL_AI_ADDRESS.fullmatch(address)
    port = int(matched["port"]) if matched else None
    if port is None or port not in _LOCAL_AI_PORTS or port == _LOCAL_AI_UPSTREAM_PORT:
        raise fail(refusal)
    return address
