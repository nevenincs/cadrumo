"""Validate storage-root rules and their declaration vectors."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .environment_declaration_constants import _BASE_NAME, _SLOT
from .environment_declaration_primitives import _fail, _integer, _keys, _list, _strings, _table

ROOT_PLATFORMS = ("windows", "linux", "macos")
_PATH_RULES = ("unicode_required", "normalize_absolute", "refuse_links", "enforce_existing_permissions")
_ROOT_KEYS = {
    "variable",
    "posix_directory_mode",
    "refusals",
    "path_rules",
    "channel",
    "installed_defaults",
}


def _installed_default(raw: object, where: str) -> dict[str, Any]:
    rule = _table(raw, where)
    _keys(rule, where, {"platform", "candidates", "home_variable"})
    candidates = []
    for position, item in enumerate(_list(rule["candidates"], f"{where}.candidates")):
        candidate = _table(item, f"{where}.candidates[{position}]")
        _keys(candidate, f"{where}.candidates[{position}]", {"variable", "subpath"})
        if not isinstance(candidate["variable"], str) or not _BASE_NAME.fullmatch(candidate["variable"]):
            raise _fail(f"{where}.candidates[{position}].variable is malformed")
        subpath = (
            _strings(candidate["subpath"], f"{where}.candidates[{position}].subpath") if candidate["subpath"] else ()
        )
        candidates.append({"variable": candidate["variable"], "subpath": list(subpath)})
    home = rule["home_variable"]
    if not candidates or not isinstance(home, str) or not _BASE_NAME.fullmatch(home):
        raise _fail(f"{where} needs base candidates and a home variable")
    return {"platform": rule["platform"], "candidates": candidates, "home_variable": home}


def _root(entry: Mapping[str, Any], names: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    _keys(entry, "root", _ROOT_KEYS, {"vectors"})
    variable = entry["variable"]
    if names.get(variable, {}).get("role") != "location":
        raise _fail("root.variable must name the declared location")
    mode, rules, channel = _root_policy(entry)
    return {
        "variable": variable,
        "installed_defaults": _root_defaults(entry),
        "channel": {key: channel[key] for key in ("product_directory", "stable", "separator")},
        "blank_is_unset": True,
        "posix_directory_mode": mode,
        "refusals": list(_strings(entry["refusals"], "root.refusals", _SLOT)),
        "path_rules": {rule: rules[rule] for rule in _PATH_RULES},
    }


def _root_defaults(entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    defaults = [
        _installed_default(item, f"root.installed_defaults[{index}]")
        for index, item in enumerate(_list(entry["installed_defaults"], "root.installed_defaults"))
    ]
    if [rule["platform"] for rule in defaults] != list(ROOT_PLATFORMS):
        raise _fail(f"root.installed_defaults must declare {list(ROOT_PLATFORMS)} in order")
    return defaults


def _root_policy(entry: Mapping[str, Any]) -> tuple[int, dict[str, Any], dict[str, Any]]:
    mode = _integer(entry["posix_directory_mode"], "root.posix_directory_mode")
    if mode > 0o777:
        raise _fail("root.posix_directory_mode must be a permission mode")
    rules = _table(entry["path_rules"], "root.path_rules")
    _keys(rules, "root.path_rules", set(_PATH_RULES))
    if not all(isinstance(rules[rule], bool) for rule in _PATH_RULES):
        raise _fail("root.path_rules values must be booleans")
    channel = _table(entry["channel"], "root.channel")
    _keys(channel, "root.channel", {"product_directory", "stable", "separator"})
    if not all(isinstance(value, str) and re.fullmatch(r"[a-z0-9-]+", value) for value in channel.values()):
        raise _fail("root.channel values must be lower-case tokens")
    return mode, rules, channel


_VECTOR_OPTIONAL = frozenset(
    {
        "known_folder",
        "channel",
        "root",
        "refusal",
        "invalid_environment",
        "invalid_known_folder",
    }
)


def _vector(raw: object, where: str, root: Mapping[str, Any]) -> dict[str, Any]:
    entry = _table(raw, where)
    _keys(entry, where, {"name", "platform", "environment"}, _VECTOR_OPTIONAL)
    if entry["platform"] not in ROOT_PLATFORMS:
        raise _fail(f"{where} names an undeclared platform")
    if ("root" in entry) == ("refusal" in entry):
        raise _fail(f"{where} must declare exactly one of root and refusal")
    if "refusal" in entry and entry["refusal"] not in root["refusals"]:
        raise _fail(f"{where} names an undeclared refusal")
    environment, optional, flags, invalid = _vector_values(entry, where)
    return {
        "name": str(entry["name"]),
        "platform": entry["platform"],
        "environment": dict(sorted(environment.items())),
        "known_folder": optional["known_folder"],
        "channel": str(entry.get("channel", root["channel"]["stable"])),
        "expected_root": optional["root"],
        "refusal": optional["refusal"],
        "invalid_environment": list(invalid),
        **flags,
    }


def _vector_values(
    entry: dict[str, Any],
    where: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], tuple[str, ...]]:
    environment = _table(entry["environment"], f"{where}.environment")
    optional = {key: entry.get(key) for key in ("known_folder", "root", "refusal")}
    if not all(isinstance(value, str) for value in (*environment.values(), *(v for v in optional.values() if v))):
        raise _fail(f"{where} values must be strings")
    flags = {key: entry.get(key, False) for key in ("invalid_known_folder",)}
    if not all(isinstance(value, bool) for value in flags.values()):
        raise _fail(f"{where} flags must be booleans")
    invalid = (
        _strings(entry["invalid_environment"], f"{where}.invalid_environment") if "invalid_environment" in entry else ()
    )
    return environment, optional, flags, invalid


def _vectors(raw: object, root: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    vectors = tuple(
        _vector(item, f"root.vectors[{index}]", root)
        for index, item in enumerate(_list([] if raw is None else raw, "root.vectors"))
    )
    if len({vector["name"] for vector in vectors}) != len(vectors):
        raise _fail("root.vectors repeats a vector name")
    return vectors


def channel_directory(root: Mapping[str, Any], channel: str) -> str:
    """Name the per-channel root directory; the stable channel uses the bare product directory."""
    names = root["channel"]
    if channel == names["stable"]:
        return str(names["product_directory"])
    return f"{names['product_directory']}{names['separator']}{channel}"
