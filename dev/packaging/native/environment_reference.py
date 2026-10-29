"""Reference evaluation of declared launch profiles."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from typing import Any

from .environment_declaration_constants import _IDENTIFIER, _REVISION, NUMERIC_ARGUMENT_KINDS
from .environment_models import ApplicationEnvironment, ExternalPathDefault, Invocation, InvocationArgument


class LaunchRefusedError(Exception):
    """A reference launch the profile refuses; carries the closed code and subject."""

    def __init__(self, code: str, subject: str) -> None:
        """Keep the refusal's code and subject."""
        super().__init__(code, subject)
        self.code = code
        self.subject = subject


def _argument_value(kind: str, minimum: int, text: str, family: str) -> int | str | None:
    """Bind numeric capabilities or bounded metadata to their declared argument kind."""
    if kind == "revision":
        return text if _REVISION.fullmatch(text) else None
    if kind == "identifier":
        return text if _IDENTIFIER.fullmatch(text) else None
    return _numeric_argument_value(kind, minimum, text, family)


def _numeric_argument_value(kind: str, minimum: int, text: str, family: str) -> int | None:
    if not text.isascii() or not text.isdigit() or (text.startswith("0") and len(text) > 1):
        return None
    value = int(text)
    maximum = (1 << 64) - 2 if kind == "handle" else (1 << 31) - 1
    if kind not in NUMERIC_ARGUMENT_KINDS or (kind == "handle") != (family == "windows"):
        return None
    return value if max(minimum, 1) <= value <= maximum else None


def _invocation_matches(invocation: Invocation, arguments: Sequence[str], family: str) -> bool:
    """Match arguments left to right, with no backtracking.

    A literal and a typed value each take one argument. An option takes two when its flag is the next argument
    and then needs a valid value; otherwise it is skipped. Every argument must be consumed.
    """
    values: dict[str, int] = {}
    cursor = 0
    for declared in invocation.arguments:
        cursor = _match_argument(declared, arguments, cursor, family, values)
        if cursor < 0:
            return False
    return (
        cursor == len(arguments)
        and all(values[a] != values[b] for a, b in invocation.distinct)
        and all(values[a] > values[b] for a, b in invocation.greater)
    )


def _match_argument(
    declared: InvocationArgument, arguments: Sequence[str], cursor: int, family: str, values: dict[str, int]
) -> int:
    actual = arguments[cursor] if cursor < len(arguments) else None
    if declared.literal is not None:
        return cursor + 1 if actual == declared.literal else -1
    if declared.option is not None:
        if actual != declared.option:
            return cursor
        cursor += 1
        actual = arguments[cursor] if cursor < len(arguments) else None
    return _match_typed_argument(declared, actual, cursor, family, values)


def _match_typed_argument(
    declared: InvocationArgument,
    actual: str | None,
    cursor: int,
    family: str,
    values: dict[str, int],
) -> int:
    if actual is None or declared.slot is None:
        return -1
    value = _argument_value(str(declared.kind), declared.minimum, actual, family)
    if value is None:
        return -1
    if isinstance(value, int):
        values[declared.slot] = value
    return cursor + 1


def reference_select(declaration: ApplicationEnvironment, family: str, image: str, arguments: Sequence[str]) -> str:
    """Select a profile name as the host must, independently of the native implementation."""
    for invocation in declaration.invocations:
        if invocation.platform not in {family, "all"}:
            continue
        if declaration.profiles[invocation.profile]["image"] == image and _invocation_matches(
            invocation, arguments, family
        ):
            return invocation.profile
    for name, profile in declaration.profiles.items():
        if profile["image"] == image and not profile["invoked"]:
            return name
    raise LaunchRefusedError("invocation_undeclared", image)


def reference_define(
    declaration: ApplicationEnvironment,
    family: str,
    profile_name: str,
    ambient: Mapping[str, str],
    *,
    package: str,
    root: str,
    layout_paths: Mapping[str, str],
    suffix: str,
    existing_dirs: Sequence[str] = (),
) -> dict[str, str]:
    """Define a profile's environment as the host must, for vectors whose root is already resolved.

    Directory and executable launch parameters are not checked against a filesystem here.
    `existing_dirs` supplies the optional directories materialized by the vector oracle.
    """
    path_type: type[PurePath] = PureWindowsPath if family == "windows" else PurePosixPath
    folded = family == "windows"

    def get(name: str) -> str | None:
        return _ambient_value(ambient, name, folded)

    profile = declaration.profiles[profile_name]
    if profile["inherit"]:
        return _inherited_environment(ambient, declaration.package_values, folded)
    defined: dict[str, str] = {}

    def put(name: str, value: str) -> None:
        _put_value(defined, name, value, folded)

    parameters = _reference_parameters(profile, path_type, get)
    base = [name for group in profile["base_groups"] for name in declaration.base[family][group]]
    for name in (*base, *profile["operator"], *profile["pass"]):
        value = get(name)
        if value is not None:
            put(name, value)
    _reference_prefix(profile, ambient, folded, put)
    package_path = path_type(package)
    _reference_fixed_values(profile, declaration, path_type, get, put, package_path, root, layout_paths, suffix)
    for name, value in parameters:
        put(name, value)

    if profile["package_path"]:
        put(
            "PATH",
            _reference_path(
                profile, declaration, family, base, existing_dirs, path_type, get, package_path, layout_paths
            ),
        )
    for name, value in declaration.package_values.items():
        put(name, value)
    return defined


def _inherited_environment(
    ambient: Mapping[str, str],
    package_values: Mapping[str, str],
    folded: bool,
) -> dict[str, str]:
    inherited = {
        name: value for name, value in ambient.items() if (name.upper() if folded else name) not in package_values
    }
    return {**inherited, **package_values}


def _ambient_value(ambient: Mapping[str, str], name: str, folded: bool) -> str | None:
    found = None
    for key, value in ambient.items():
        if (key.upper() == name.upper()) if folded else (key == name):
            found = value
    return found


def _put_value(defined: dict[str, str], name: str, value: str, folded: bool) -> None:
    for key in [key for key in defined if (key.upper() == name.upper() if folded else key == name)]:
        del defined[key]
    defined[name] = value


def _reference_prefix(
    profile: Mapping[str, Any],
    ambient: Mapping[str, str],
    folded: bool,
    put: Callable[[str, str], None],
) -> None:
    prefix = profile["prefix"]
    if prefix:
        fold = str.upper if folded else str
        kept_out = {fold(name) for name in (*profile["prefix_refused"], *(slot.name for slot in profile["slots"]))}
        for key in list(ambient):
            if fold(key).startswith(prefix) and len(key) > len(prefix) and fold(key) not in kept_out:
                put(key, ambient[key])


def _reference_fixed_values(
    profile: Mapping[str, Any],
    declaration: ApplicationEnvironment,
    path_type: type[PurePath],
    get: Callable[[str], str | None],
    put: Callable[[str, str], None],
    package_path: PurePath,
    root: str,
    layout_paths: Mapping[str, str],
    suffix: str,
) -> None:
    pins = profile["pins"]
    if "root" in pins:
        put(declaration.root["variable"], str(path_type(root)))
    if "temporary" in pins:
        member = declaration.temporary_member["name"]
        admitted = member in profile["operator"] or member in profile["pass"]
        override = get(member) if admitted else None
        temporary = path_type(root) / (override or declaration.temporary_member["default"])
        for name in declaration.temporary:
            put(name, str(temporary))
    if "authority" in pins:
        put(declaration.authority.name, str(package_path / layout_paths[declaration.authority.value]))
    _reference_profile_fixed(profile, put, package_path, layout_paths, suffix)


def _reference_profile_fixed(
    profile: Mapping[str, Any],
    put: Callable[[str, str], None],
    package_path: PurePath,
    layout_paths: Mapping[str, str],
    suffix: str,
) -> None:
    for fixed in profile["fixed"]:
        if fixed.source == "value":
            put(fixed.name, fixed.value)
        elif fixed.source == "image":
            image = package_path / (layout_paths["executable"] if fixed.value == "python" else layout_paths["native"])
            put(fixed.name, str(image if fixed.value == "python" else image / f"{fixed.value}{suffix}"))
        else:
            put(fixed.name, str(package_path / layout_paths[fixed.value]))


def _reference_parameters(
    profile: Mapping[str, Any],
    path_type: type[PurePath],
    get: Callable[[str], str | None],
) -> list[tuple[str, str]]:
    parameters: list[tuple[str, str]] = []
    for slot in profile["slots"]:
        value = get(slot.name)
        if value is None:
            if slot.required:
                raise LaunchRefusedError("launch_value_missing", slot.name)
            continue
        if slot.kind == "port" and not (value.isdigit() and value.isascii() and int(value) <= 0xFFFF):
            raise LaunchRefusedError("launch_value_malformed", slot.name)
        if slot.kind in {"directory", "executable"} and not path_type(value).is_absolute():
            raise LaunchRefusedError("launch_value_malformed", slot.name)
        parameters.append((slot.name, value))
    return parameters


def _reference_path(
    profile: Mapping[str, Any],
    declaration: ApplicationEnvironment,
    family: str,
    base: Sequence[str],
    existing_dirs: Sequence[str],
    path_type: type[PurePath],
    get: Callable[[str], str | None],
    package_path: PurePath,
    layout_paths: Mapping[str, str],
) -> str:
    entries: list[str] = []
    for entry in declaration.path_entries:
        if entry == "executable":
            entries.append(str(package_path))
        elif entry == "external" and declaration.path_external in {*profile["operator"], *profile["pass"]}:
            entries.extend(_reference_external_path(declaration.path_external, family, existing_dirs, path_type, get))
        elif entry == "native":
            entries.append(str(package_path / layout_paths["native"]))
        elif entry == "external_defaults" and declaration.path_external in {
            *profile["operator"],
            *profile["pass"],
        }:
            entries.extend(_reference_default_paths(declaration, family, base, existing_dirs, path_type, get))
        elif entry == "system":
            entries.extend(_reference_system_path(declaration, family, path_type, get))
    return (";" if family == "windows" else ":").join(entries)


def _reference_external_path(
    name: str,
    family: str,
    existing_dirs: Sequence[str],
    path_type: type[PurePath],
    get: Callable[[str], str | None],
) -> list[str]:
    directories = get(name)
    if directories is None or directories == "":
        return []
    separator = ";" if family == "windows" else ":"
    return [
        str(path_type(directory))
        for directory in directories.split(separator)
        if str(path_type(directory)) in existing_dirs
    ]


def _reference_system_path(
    declaration: ApplicationEnvironment,
    family: str,
    path_type: type[PurePath],
    get: Callable[[str], str | None],
) -> list[str]:
    if family != "windows":
        return list(declaration.posix_system)
    system = get(declaration.windows_system[0])
    if system is None:
        raise ValueError("The Windows system directory variable is missing")
    return [str(path_type(system, *declaration.windows_system[1]))]


def _reference_default_paths(
    declaration: ApplicationEnvironment,
    family: str,
    base: Sequence[str],
    existing_dirs: Sequence[str],
    path_type: type[PurePath],
    get: Callable[[str], str | None],
) -> list[str]:
    entries: list[str] = []
    for default in declaration.external_path_defaults:
        if default.platform == "windows" and family != "windows":
            continue
        if default.platform in {"posix", "macos"} and family != "posix":
            continue
        candidate = _reference_default_candidate(default, base, path_type, get)
        if candidate is None:
            continue
        rendered = str(candidate)
        if rendered in existing_dirs:
            entries.append(rendered)
    return entries


def _reference_default_candidate(
    default: ExternalPathDefault,
    base: Sequence[str],
    path_type: type[PurePath],
    get: Callable[[str], str | None],
) -> PurePath | None:
    if default.variable is None:
        return path_type(default.path)
    if default.variable not in base:
        return None
    base_directory = get(default.variable)
    if base_directory is None or not path_type(base_directory).is_absolute():
        return None
    return path_type(base_directory).joinpath(*default.subpaths)
