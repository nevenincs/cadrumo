"""Validate agent admission and launch conformance vectors."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .environment_declaration_constants import _NAME, PLATFORMS
from .environment_declaration_primitives import _fail, _integer, _keys, _list, _strings, _table


def _agent(raw: object, names: Mapping[str, Mapping[str, str]], profiles: Mapping[str, dict[str, Any]]) -> None:
    """Hold the agent's names to the agent image and compile its prefix admission.

    No other profile admits or sets a name under the agent's prefix. An agent-image profile
    with ``agent_names`` admits every name under the prefix except the never-admitted ones,
    so it lists none of them by name; a declared slot keeps its kind validation.
    """
    entry = _table(raw, "agent")
    _keys(entry, "agent", {"image", "prefix", "hosting_contract", "never_admitted"})
    image, prefix = entry["image"], entry["prefix"]
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)*_", prefix):
        raise _fail("agent.prefix must be an upper-case prefix ending in an underscore")
    _integer(entry["hosting_contract"], "agent.hosting_contract")
    never = _strings(entry["never_admitted"], "agent.never_admitted", _NAME)
    if not all(name.startswith(prefix) for name in never) or set(never) & set(names):
        raise _fail("agent.never_admitted names carry the agent prefix and are declared nowhere")
    for profile, declared in profiles.items():
        _validate_agent_profile(profile, declared, image, prefix, never)


def _validate_agent_profile(
    profile: str,
    declared: dict[str, Any],
    image: str,
    prefix: str,
    never: tuple[str, ...],
) -> None:
    if declared["image"] != image and _profile_spells_prefix(declared, prefix):
        raise _fail(f"profiles.{profile} admits an agent name outside the {image} image")
    if declared["agent_names"] and declared["image"] != image:
        raise _fail(f"profiles.{profile} admits the agent's names outside the {image} image")
    if declared["image"] == image and any(name.startswith(prefix) for name in declared["pass"]):
        raise _fail(f"profiles.{profile} lists an agent name; the agent image admits them by prefix only")
    if declared["agent_names"]:
        declared["prefix"], declared["prefix_refused"] = prefix, never


def _profile_spells_prefix(declared: Mapping[str, Any], prefix: str) -> bool:
    spelled = [*declared["operator"], *declared["pass"], *(slot.name for slot in declared["slots"])]
    spelled += [value.name for value in declared["fixed"]]
    return any(name.startswith(prefix) for name in spelled)


def _text_table(raw: object, where: str) -> dict[str, str]:
    table = _table(raw, where)
    if not all(isinstance(value, str) for value in table.values()):
        raise _fail(f"{where} values must be strings")
    return {str(key): str(value) for key, value in table.items()}


def _launch_vector(
    raw: object, where: str, profiles: Mapping[str, Mapping[str, Any]], native_host: Mapping[str, Any]
) -> dict[str, Any]:
    entry = _table(raw, where)
    _keys(
        entry,
        where,
        {"name", "platform", "image", "arguments", "ambient"},
        {"profile", "environment", "path", "refusal"},
    )
    if entry["platform"] not in PLATFORMS:
        raise _fail(f"{where} platform must be windows or posix")
    arguments = _launch_arguments(entry, where)
    if ("refusal" in entry) == ("profile" in entry) or ("refusal" in entry and ({"environment", "path"} & set(entry))):
        raise _fail(f"{where} must declare either a profile and its environment or a refusal")
    vector: dict[str, Any] = {
        "name": str(entry["name"]),
        "platform": entry["platform"],
        "image": str(entry["image"]),
        "arguments": [str(argument) for argument in arguments],
        "ambient": _text_table(entry["ambient"], f"{where}.ambient"),
        "profile": None,
        "environment": {},
        "path": None,
        "refusal": None,
    }
    if "refusal" in entry:
        vector["refusal"] = _launch_refusal(entry, where, native_host)
        return vector
    if entry["profile"] not in profiles:
        raise _fail(f"{where} selects an undeclared profile")
    vector["profile"] = entry["profile"]
    vector["environment"] = _text_table(entry.get("environment", {}), f"{where}.environment")
    if "path" in entry:
        vector["path"] = list(_strings(entry["path"], f"{where}.path"))
    return vector


def _launch_arguments(entry: dict[str, Any], where: str) -> list[str]:
    arguments = _list(entry["arguments"], f"{where}.arguments")
    if not all(isinstance(argument, str) for argument in arguments):
        raise _fail(f"{where}.arguments must be strings")
    return [str(argument) for argument in arguments]


def _launch_refusal(entry: dict[str, Any], where: str, native_host: Mapping[str, Any]) -> dict[str, str]:
    refusal = _text_table(entry["refusal"], f"{where}.refusal")
    _keys(refusal, f"{where}.refusal", {"code", "subject"})
    if refusal["code"] not in native_host["refusals"]:
        raise _fail(f"{where} names an undeclared refusal")
    return {"code": refusal["code"], "subject": refusal["subject"]}


def _launch_vectors(
    raw: object, profiles: Mapping[str, Mapping[str, Any]], native_host: Mapping[str, Any]
) -> tuple[dict[str, Any], ...]:
    vectors = tuple(
        _launch_vector(item, f"launch_vectors[{index}]", profiles, native_host)
        for index, item in enumerate(_list(raw, "launch_vectors"))
    )
    if len({vector["name"] for vector in vectors}) != len(vectors):
        raise _fail("launch_vectors repeats a vector name")
    return vectors
