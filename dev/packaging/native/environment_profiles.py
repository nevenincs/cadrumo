"""Validate launch profiles and invocation declarations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .environment_declaration_constants import (
    _LITERAL,
    _NAME,
    _OPTION,
    _PROFILE,
    _SLOT,
    ARGUMENT_KINDS,
    BASE_GROUPS,
    NUMERIC_ARGUMENT_KINDS,
    OPTION_KINDS,
    PIN_KINDS,
    PLATFORMS,
)
from .environment_declaration_primitives import _fail, _keys, _list, _strings, _table
from .environment_models import FixedValue, Invocation, InvocationArgument, LaunchSlot


def _argument(raw: object, where: str) -> InvocationArgument:
    entry = _table(raw, where)
    if "literal" in entry:
        return _literal_argument(entry, where)
    if "option" in entry:
        return _option_argument(entry, where)
    return _typed_argument(entry, where)


def _literal_argument(entry: dict[str, Any], where: str) -> InvocationArgument:
    _keys(entry, where, {"literal"})
    if not isinstance(entry["literal"], str) or not _LITERAL.fullmatch(entry["literal"]):
        raise _fail(f"{where} literal is malformed")
    return InvocationArgument(literal=entry["literal"], slot=None, kind=None, minimum=0)


def _option_argument(entry: dict[str, Any], where: str) -> InvocationArgument:
    # An option is an optional flag followed by one typed value; the pair is present whole or absent.
    _keys(entry, where, {"option", "slot", "kind"})
    if not isinstance(entry["option"], str) or not _OPTION.fullmatch(entry["option"]):
        raise _fail(f"{where} option must be a lower-case double-dash flag")
    if not isinstance(entry["slot"], str) or not _SLOT.fullmatch(entry["slot"]):
        raise _fail(f"{where} slot is malformed")
    if entry["kind"] not in OPTION_KINDS:
        raise _fail(f"{where} option kind must be one of {sorted(OPTION_KINDS)}")
    return InvocationArgument(literal=None, slot=entry["slot"], kind=entry["kind"], minimum=0, option=entry["option"])


def _typed_argument(entry: dict[str, Any], where: str) -> InvocationArgument:
    _keys(entry, where, {"slot", "kind"}, {"minimum"})
    if not isinstance(entry["slot"], str) or not _SLOT.fullmatch(entry["slot"]):
        raise _fail(f"{where} slot is malformed")
    if entry["kind"] not in ARGUMENT_KINDS:
        raise _fail(f"{where} has an undeclared argument kind {entry['kind']!r}")
    if entry["kind"] not in NUMERIC_ARGUMENT_KINDS:
        if "minimum" in entry:
            raise _fail(f"{where} minimum applies only to a numeric argument")
        return InvocationArgument(literal=None, slot=entry["slot"], kind=entry["kind"], minimum=0)
    minimum = entry.get("minimum", 1)
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
        raise _fail(f"{where} minimum must be a positive integer")
    return InvocationArgument(literal=None, slot=entry["slot"], kind=entry["kind"], minimum=minimum)


def _pairs(raw: object, where: str, slots: set[str]) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, list):
        raise _fail(f"{where} must be a list of slot pairs")
    pairs: list[tuple[str, str]] = []
    for pair in raw:
        if not isinstance(pair, list) or len(pair) != 2 or not set(pair) <= slots or pair[0] == pair[1]:
            raise _fail(f"{where} must pair two distinct declared argument slots: {pair!r}")
        pairs.append((pair[0], pair[1]))
    return tuple(pairs)


def _options_trail(arguments: Sequence[InvocationArgument], where: str) -> None:
    """Hold the options to the end, each flag distinct, so that reading them left to right is unambiguous."""
    tail = [argument for argument in arguments if argument.option is not None]
    if arguments[len(arguments) - len(tail) :] != tuple(tail):
        raise _fail(f"{where} options must follow every other argument")
    flags = [argument.option for argument in tail if argument.option is not None]
    literals = {argument.literal for argument in arguments if argument.literal is not None}
    if len(flags) != len(set(flags)) or literals & set(flags):
        raise _fail(f"{where} option flags must be distinct from each other and from every literal")


def _invocations(raw: object) -> tuple[Invocation, ...]:
    if not isinstance(raw, list):
        raise _fail("invocations must be an array of tables")
    invocations: list[Invocation] = []
    for index, item in enumerate(raw):
        where = f"invocations[{index}]"
        invocations.append(_invocation(item, where))
    return tuple(invocations)


def _invocation(item: object, where: str) -> Invocation:
    entry = _table(item, where)
    _keys(entry, where, {"profile", "platform", "arguments"}, {"distinct", "greater"})
    if entry["platform"] not in {*PLATFORMS, "all"}:
        raise _fail(f"{where} platform must be windows, posix or all")
    if not isinstance(entry["arguments"], list) or not entry["arguments"]:
        raise _fail(f"{where} must declare at least one argument")
    arguments = tuple(_argument(argument, f"{where}.arguments[{i}]") for i, argument in enumerate(entry["arguments"]))
    if arguments[0].literal is None:
        raise _fail(f"{where} must start with a literal argument")
    _options_trail(arguments, where)
    slots = [argument.slot for argument in arguments if argument.slot is not None]
    if len(slots) != len(set(slots)):
        raise _fail(f"{where} repeats an argument slot")
    comparable = _comparable_slots(arguments)
    return Invocation(
        profile=str(entry["profile"]),
        platform=entry["platform"],
        arguments=arguments,
        distinct=_pairs(entry.get("distinct", []), f"{where}.distinct", comparable),
        greater=_pairs(entry.get("greater", []), f"{where}.greater", comparable),
    )


def _comparable_slots(arguments: tuple[InvocationArgument, ...]) -> set[str]:
    # Only required numeric values are always present and comparable.
    return {
        argument.slot
        for argument in arguments
        if argument.slot is not None and argument.option is None and argument.kind in NUMERIC_ARGUMENT_KINDS
    }


def _fixed(
    raw: object,
    where: str,
    names: Mapping[str, Mapping[str, str]],
    *,
    role: str,
    allow_build_setting: bool = False,
) -> FixedValue:
    entry = _table(raw, where)
    allowed = {"value", "layout_path", "image"}
    if allow_build_setting:
        allowed.add("build_setting")
    sources = allowed & set(entry)
    if len(sources) != 1:
        choices = "value, layout_path, image or build_setting" if allow_build_setting else "value, layout_path or image"
        raise _fail(f"{where} must declare exactly one of {choices}")
    _keys(entry, where, {"name", *sources})
    name, source = entry["name"], next(iter(sources))
    if names.get(name, {}).get("role") != role:
        raise _fail(f"{where} sets {name!r}, which is not a declared {role} name")
    if not isinstance(entry[source], str) or not entry[source]:
        raise _fail(f"{where} {source} must be a non-empty string")
    return FixedValue(name=name, source=source, value=entry[source])


def _profiles(
    raw: object, names: Mapping[str, Mapping[str, str]], groups: Mapping[str, tuple[str, ...]], root_variable: str
) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for profile, item in _table(raw, "profiles").items():
        profiles[profile] = _profile(profile, item, names, groups, root_variable)
    return profiles


def _profile(
    profile: str,
    item: object,
    names: Mapping[str, Mapping[str, str]],
    groups: Mapping[str, tuple[str, ...]],
    root_variable: str,
) -> dict[str, Any]:
    where = f"profiles.{profile}"
    if not _PROFILE.fullmatch(profile):
        raise _fail(f"profile name is not a lowercase hyphenated identifier: {profile!r}")
    entry = _table(item, where)
    _keys(
        entry,
        where,
        {"image", "base", "pins", "path"},
        {"base_groups", "operator", "pass", "fixed", "slots", "agent_names"},
    )
    if not isinstance(entry["image"], str) or not _PROFILE.fullmatch(entry["image"]):
        raise _fail(f"{where} image is malformed")
    if entry["base"] not in {"groups", "inherit"} or entry["path"] not in {"package", "inherit"}:
        raise _fail(f"{where} base must be groups or inherit and path must be package or inherit")
    pins, inherit = _profile_pins(entry, where)
    base_groups, operator, passed = _profile_admissions(entry, where, inherit, names, groups)
    fixed = tuple(
        _fixed(value, f"{where}.fixed[{index}]", names, role="fixed")
        for index, value in enumerate(_list(entry.get("fixed", []), f"{where}.fixed"))
    )
    slots = _profile_slots(entry, where, names, root_variable, pins, fixed)
    _validate_profile_names(operator, passed, fixed, slots, where)
    agent_names = entry.get("agent_names", False)
    if not isinstance(agent_names, bool):
        raise _fail(f"{where}.agent_names must be a boolean")
    return {
        "image": entry["image"],
        "inherit": inherit,
        "base_groups": base_groups,
        "pins": pins,
        "operator": operator,
        "pass": passed,
        "fixed": fixed,
        "slots": tuple(slots),
        "package_path": entry["path"] == "package",
        "agent_names": agent_names,
        "prefix": "",
        "prefix_refused": (),
    }


def _validate_profile_names(
    operator: tuple[str, ...],
    passed: tuple[str, ...],
    fixed: tuple[FixedValue, ...],
    slots: list[LaunchSlot],
    where: str,
) -> None:
    defined = [*operator, *passed, *(value.name for value in fixed), *(slot.name for slot in slots)]
    if len(defined) != len(set(defined)):
        raise _fail(f"{where} admits or sets one name twice")


def _profile_admissions(
    entry: dict[str, Any],
    where: str,
    inherit: bool,
    names: Mapping[str, Mapping[str, str]],
    groups: Mapping[str, tuple[str, ...]],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    base_groups = _strings(entry.get("base_groups", []), f"{where}.base_groups") if not inherit else ()
    if not inherit and not base_groups:
        raise _fail(f"{where} must name its base groups")
    if not set(base_groups) <= set(BASE_GROUPS):
        raise _fail(f"{where}.base_groups names an undeclared base group")
    operator_groups = _strings(entry.get("operator", []), f"{where}.operator")
    if not set(operator_groups) <= set(groups):
        raise _fail(f"{where}.operator names an undeclared group")
    operator = tuple(name for group in operator_groups for name in groups[group])
    passed = _strings(entry.get("pass", []), f"{where}.pass", _NAME)
    for name in passed:
        if name not in names:
            raise _fail(f"{where}.pass admits an undeclared name {name}")
    return base_groups, operator, passed


def _profile_pins(entry: dict[str, Any], where: str) -> tuple[tuple[str, ...], bool]:
    # true pins the root, the temporary variables and the authority; a list pins only those named.
    pins: tuple[str, ...]
    if isinstance(entry["pins"], bool):
        pins = PIN_KINDS if entry["pins"] else ()
    else:
        pins = _strings(entry["pins"], f"{where}.pins")
        if not set(pins) <= set(PIN_KINDS):
            raise _fail(f"{where}.pins names an undeclared pin; declared: {list(PIN_KINDS)}")
        pins = tuple(kind for kind in PIN_KINDS if kind in pins)
    inherit = bool(entry["base"] == "inherit")
    if inherit and (pins or entry["path"] != "inherit" or set(entry) - {"image", "base", "pins", "path"}):
        raise _fail(f"{where} inherits its caller's environment and may not pin, project or admit names")
    return pins, inherit


def _profile_slots(
    entry: dict[str, Any],
    where: str,
    names: Mapping[str, Mapping[str, str]],
    root_variable: str,
    pins: tuple[str, ...],
    fixed: tuple[FixedValue, ...],
) -> list[LaunchSlot]:
    slots: list[LaunchSlot] = []
    for index, value in enumerate(_list(entry.get("slots", []), f"{where}.slots")):
        slot = _table(value, f"{where}.slots[{index}]")
        _keys(slot, f"{where}.slots[{index}]", {"name", "required"})
        name = slot["name"]
        # The storage root is a slot where a parent hands its own root to an image that does not pin it,
        # and a package fact one image fixes is a slot where that image relays it to a child image.
        role = names.get(name, {}).get("role")
        admitted = (
            role == "slot"
            or (name == root_variable and "root" not in pins)
            or (role == "fixed" and name not in {value.name for value in fixed})
        )
        if not admitted or not isinstance(slot["required"], bool):
            raise _fail(f"{where}.slots[{index}] must name a declared slot and whether it is required")
        slots.append(LaunchSlot(name=name, kind=names[name]["kind"], required=slot["required"]))
    return slots
