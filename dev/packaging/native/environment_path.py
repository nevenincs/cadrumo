"""Validate optional external PATH defaults."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from typing import Any

from .environment_declaration_constants import _BASE_NAME, _PATH_COMPONENT
from .environment_declaration_primitives import _fail, _keys, _list, _strings, _table
from .environment_models import ExternalPathDefault


def _external_path_defaults(
    raw: object,
    base: Mapping[str, Mapping[str, tuple[str, ...]]],
) -> tuple[ExternalPathDefault, ...]:
    defaults: list[ExternalPathDefault] = []
    seen: set[tuple[str, str | None, str, tuple[str, ...]]] = set()
    for index, item in enumerate(_list(raw, "path.external_defaults")):
        where = f"path.external_defaults[{index}]"
        default = _external_path_default(item, where, base)
        identity = (default.platform, default.variable, default.path, default.subpaths)
        if identity in seen:
            raise _fail(f"{where} repeats an installation directory")
        seen.add(identity)
        defaults.append(default)
    return tuple(defaults)


def _external_path_default(
    item: object,
    where: str,
    base: Mapping[str, Mapping[str, tuple[str, ...]]],
) -> ExternalPathDefault:
    entry = _table(item, where)
    _keys(entry, where, {"platform"}, {"variable", "path", "subpaths"})
    platform = entry["platform"]
    if not isinstance(platform, str) or platform not in {"windows", "posix", "macos"}:
        raise _fail(f"{where}.platform must be windows, posix or macos")
    has_variable, has_path = "variable" in entry, "path" in entry
    if has_variable == has_path:
        raise _fail(f"{where} must declare exactly one of variable or path")
    family = "windows" if platform == "windows" else "posix"
    subpaths = _strings(entry.get("subpaths", []), f"{where}.subpaths", _PATH_COMPONENT)
    if any(part in {".", ".."} for part in subpaths):
        raise _fail(f"{where}.subpaths must not contain current or parent components")
    if has_variable:
        variable = _external_default_variable(entry, where, family, base)
        path = ""
    else:
        variable = None
        path = _external_default_path(entry, where, family, subpaths)
    return ExternalPathDefault(platform, variable, path, subpaths)


def _external_default_variable(
    entry: dict[str, Any],
    where: str,
    family: str,
    base: Mapping[str, Mapping[str, tuple[str, ...]]],
) -> str:
    variable = entry["variable"]
    if not isinstance(variable, str) or not _BASE_NAME.fullmatch(variable):
        raise _fail(f"{where}.variable is malformed")
    canonical_variable = variable.upper() if family == "windows" else variable
    if canonical_variable not in base[family]["system"]:
        raise _fail(f"{where}.variable must be a declared {family} system base name")
    return variable


def _external_default_path(entry: dict[str, Any], where: str, family: str, subpaths: tuple[str, ...]) -> str:
    raw_path = entry["path"]
    if not isinstance(raw_path, str) or not raw_path:
        raise _fail(f"{where}.path must be a non-empty absolute path")
    path_type: type[PurePath] = PureWindowsPath if family == "windows" else PurePosixPath
    candidate = path_type(raw_path)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise _fail(f"{where}.path must be an absolute path without parent components")
    if subpaths:
        raise _fail(f"{where}.subpaths is only valid with variable")
    return str(candidate)
