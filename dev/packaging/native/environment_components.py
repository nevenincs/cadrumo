"""Validate native host and packaged component declarations."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .environment_declaration_constants import _BASE_NAME, _NAME, _SLOT
from .environment_declaration_primitives import _fail, _integer, _keys, _relative, _strings, _table


def _temporary_member(raw: object, names: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    entry = _table(raw, "pins.temporary_member")
    _keys(entry, "pins.temporary_member", {"name", "default", "create_explicit"})
    if names.get(entry["name"], {}).get("role") != "location":
        raise _fail("pins.temporary_member must name a declared location")
    if not isinstance(entry["create_explicit"], bool):
        raise _fail("pins.temporary_member.create_explicit must be a boolean")
    return {
        "name": entry["name"],
        "default": _relative(entry["default"], "pins.temporary_member.default"),
        "create_explicit": entry["create_explicit"],
    }


def _host_classes(raw: object) -> dict[str, Any]:
    entry = _table(raw, "host_classes")
    _keys(entry, "host_classes", {"cleared_prefixes", "cleared_names", "namespace_prefix"})
    prefix = entry["namespace_prefix"]
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*_", prefix):
        raise _fail("host_classes.namespace_prefix must be an upper-case prefix ending in an underscore")
    return {
        "cleared_prefixes": list(_strings(entry["cleared_prefixes"], "host_classes.cleared_prefixes", _BASE_NAME)),
        "cleared_names": list(_strings(entry["cleared_names"], "host_classes.cleared_names", _BASE_NAME)),
        "namespace_prefix": prefix,
    }


def _native_host(raw: object) -> dict[str, Any]:
    entry = _table(raw, "native_host")
    _keys(entry, "native_host", {"owner", "first", "last", "launch_profile_refused", "refusals"})
    if not isinstance(entry["owner"], str) or not _SLOT.fullmatch(entry["owner"]):
        raise _fail("native_host.owner must be a lower-case token")
    first = _integer(entry["first"], "native_host.first")
    last = _integer(entry["last"], "native_host.last", minimum=first)
    refused = _integer(entry["launch_profile_refused"], "native_host.launch_profile_refused")
    # POSIX reports only the low byte of an exit status.
    if last > 0xFF or not first <= refused <= last:
        raise _fail("native_host exit codes must lie in one byte and hold launch_profile_refused")
    return {
        "owner": entry["owner"],
        "first": first,
        "last": last,
        "launch_profile_refused": refused,
        "refusals": list(_strings(entry["refusals"], "native_host.refusals", _SLOT)),
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
    "log_variable",
    "log_format",
    "log_max_bytes",
    "log_backups",
    "language_variable",
    "language_default",
    "profile_variable",
    "local_ai_address",
    "development_role_image_variable",
)
#: The local AI server's address: IPv4 loopback, a port outside the privileged range and
#: below every platform's ephemeral range, and never the publisher's default port.
_LOCAL_AI_ADDRESS = re.compile(r"127\.0\.0\.1:(?P<port>[1-9][0-9]{3,4})")
_LOCAL_AI_PORTS = range(1024, 32768)
_LOCAL_AI_UPSTREAM_PORT = 11434


def _components(raw: object, names: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    entry = _table(raw, "components")
    _keys(entry, "components", {*_COMPONENT_PATHS, *_COMPONENT_VALUES})
    components: dict[str, Any] = {key: _relative(entry[key], f"components.{key}") for key in _COMPONENT_PATHS}
    if not components["log_file"].startswith(components["logs"] + "/"):
        raise _fail("components.log_file must lie in components.logs")
    if names.get(entry["log_variable"], {}).get("role") != "location":
        raise _fail("components.log_variable must name a declared location")
    if not isinstance(entry["log_format"], str) or not entry["log_format"]:
        raise _fail("components.log_format must be a non-empty string")
    if names.get(entry["language_variable"], {}).get("kind") != "language":
        raise _fail("components.language_variable must name a declared language name")
    language = entry["language_default"]
    if not isinstance(language, str) or not re.fullmatch(r"[a-z]{2}", language):
        raise _fail("components.language_default must be a two-letter lower-case language")
    if names.get(entry["profile_variable"]) != {"kind": "directory", "role": "slot"}:
        raise _fail("components.profile_variable must name a declared directory slot")
    address, development_image = _component_runtime_values(entry, names)
    components.update(
        log_variable=entry["log_variable"],
        log_format=entry["log_format"],
        log_max_bytes=_integer(entry["log_max_bytes"], "components.log_max_bytes"),
        log_backups=_integer(entry["log_backups"], "components.log_backups", minimum=0),
        language_variable=entry["language_variable"],
        language_default=language,
        profile_variable=entry["profile_variable"],
        local_ai_address=address,
        development_role_image_variable=development_image,
    )
    return components


def _component_runtime_values(entry: dict[str, Any], names: Mapping[str, Mapping[str, str]]) -> tuple[str, str]:
    address = entry["local_ai_address"]
    if not isinstance(address, str):
        raise _fail("components.local_ai_address must be 127.0.0.1 with a port from 1024 to 32767 other than 11434")
    matched = _LOCAL_AI_ADDRESS.fullmatch(address)
    port = int(matched["port"]) if matched else None
    if port is None or port not in _LOCAL_AI_PORTS or port == _LOCAL_AI_UPSTREAM_PORT:
        raise _fail("components.local_ai_address must be 127.0.0.1 with a port from 1024 to 32767 other than 11434")
    development_image = entry["development_role_image_variable"]
    if not isinstance(development_image, str) or not _NAME.fullmatch(development_image) or development_image in names:
        raise _fail("components.development_role_image_variable must be an environment name no profile admits")
    return address, development_image
