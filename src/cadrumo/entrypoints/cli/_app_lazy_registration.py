"""Metadata-only nested registrations for every application command family."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from functools import cache
from importlib import import_module, resources
from typing import Literal, cast

import typer
from typer.models import DefaultPlaceholder

from ...core.i18n import output_language
from ._app_execution_policies import declare_metadata_group
from ._command_suggestions import (
    CadrumoTyperGroup,
    LazyFactoryTarget,
    LazyOptionalDependencyProvider,
    LazySubcommand,
    register_lazy_subcommand,
)

type AppPath = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AppCommandRecord:
    """Generated, non-authoritative metadata for one app node."""

    path: AppPath
    kind: Literal["group", "leaf"]
    help_by_language: tuple[tuple[str, str], ...]
    short_help_by_language: tuple[tuple[str, str | None], ...]
    hidden: bool
    deprecated: bool | str
    invoke_without_command: bool
    no_args_is_help: bool
    handler_owner: str

    def help(self) -> str:
        return dict(self.help_by_language).get(output_language(), dict(self.help_by_language)["es"])

    def short_help(self) -> str | None:
        return dict(self.short_help_by_language).get(output_language())


@dataclass(frozen=True)
class AppCommandTarget:
    """One immutable app path bound to its real deferred target object."""

    record: AppCommandRecord

    def __post_init__(self) -> None:
        slug = "__".join(self.record.path).replace("-", "_")
        object.__setattr__(self, "__module__", __name__)
        object.__setattr__(self, "__qualname__", f"app_targets.load_{slug}")

    def __call__(self) -> typer.Typer:
        if self.record.kind == "group":
            return _group_target(self.record)
        return _leaf_target(self.record)


def _load_records() -> tuple[AppCommandRecord, ...]:
    raw = resources.files(__package__).joinpath("app_lazy_manifest.v1.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    if payload.get("format_version") != 1:
        raise ValueError("unsupported app lazy manifest format")
    records = tuple(
        AppCommandRecord(
            path=tuple(row["path"]),
            kind=row["kind"],
            help_by_language=tuple(sorted(row["help_by_language"].items())),
            short_help_by_language=tuple(sorted(row["short_help_by_language"].items())),
            hidden=row["hidden"],
            deprecated=row["deprecated"],
            invoke_without_command=row["invoke_without_command"],
            no_args_is_help=row["no_args_is_help"],
            handler_owner=row["handler_owner"],
        )
        for row in payload["records"]
    )
    paths = tuple(record.path for record in records)
    if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
        raise ValueError("app lazy manifest paths must be unique and sorted")
    return records


APP_COMMAND_RECORDS = _load_records()
APP_COMMAND_TARGETS: dict[AppPath, AppCommandTarget] = {}
REGISTRAR_SOURCE_PATHS: set[AppPath] = set()
_RECORD_BY_PATH = {record.path: record for record in APP_COMMAND_RECORDS}


def _registry_key(path: AppPath) -> str:
    return "app" if not path else "app." + ".".join(path)


def _decorate(target: typer.Typer) -> None:
    from ._errors import decorate_typer_app

    decorate_typer_app(target)


def _required_unavailable(name: str, error: ModuleNotFoundError):
    from . import _required_import_failure

    return _required_import_failure(name, error)


def _optional_unavailable(name: str, error: ModuleNotFoundError) -> typer.Typer:
    from . import _optional_import_surface

    return _optional_import_surface(name, error)


def _optional_dependencies() -> frozenset[str]:
    from . import _optional_dependency_names

    return _optional_dependency_names()


def _register(record: AppCommandRecord) -> None:
    target = AppCommandTarget(record)
    if record.path in APP_COMMAND_TARGETS:
        raise ValueError(f"duplicate app target: {' '.join(record.path)!r}")
    APP_COMMAND_TARGETS[record.path] = target
    register_lazy_subcommand(
        _registry_key(record.path[:-1]),
        LazySubcommand(
            record.path[-1],
            LazyFactoryTarget(
                target,
                optional_dependencies=LazyOptionalDependencyProvider(_optional_dependencies),
            ),
            child_registry_key=_registry_key(record.path),
            decorate=_decorate,
            optional_unavailable=_optional_unavailable,
            required_unavailable=_required_unavailable,
            help=record.help(),
            short_help=record.short_help(),
            hidden=record.hidden,
            deprecated=record.deprecated,
        ),
    )


def _group_target(record: AppCommandRecord) -> typer.Typer:
    # Only a genuinely executable nested group imports its own callback owner.
    # Metadata groups are constructed without importing a command module.
    if record.invoke_without_command and record.path != ("diagnostics",):
        return _source_group(record)
    shell = typer.Typer(
        name=record.path[-1],
        help=record.help(),
        no_args_is_help=record.no_args_is_help,
        cls=CadrumoTyperGroup,
    )
    declare_metadata_group(shell)
    return shell


def _leaf_target(record: AppCommandRecord) -> typer.Typer:
    module = import_module(record.handler_owner.partition(":")[0])
    info = _find_command_info(module, record)
    if info is None:
        info = _find_registrar_command_info(module, record)
    target = typer.Typer()
    target.registered_commands.append(info)
    return target


def _source_group(record: AppCommandRecord) -> typer.Typer:
    module = import_module(record.handler_owner.partition(":")[0])
    candidates = list(_module_typer_apps(module))
    if record.path[0] in {"ledger", "live", "modelo"}:
        candidates.append(_registrar_source_app(record.handler_owner.partition(":")[0], record.path[0]))
    for candidate in candidates:
        for current in _walk_typer_apps(candidate):
            callback = current.registered_callback
            owner = _callback_owner(None if callback is None else callback.callback)
            if owner == record.handler_owner:
                shell = typer.Typer(
                    name=record.path[-1],
                    help=record.help(),
                    no_args_is_help=record.no_args_is_help,
                    invoke_without_command=True,
                    cls=CadrumoTyperGroup,
                )
                shell.registered_callback = callback
                return shell
    raise RuntimeError(f"source group callback is absent for {' '.join(record.path)!r}")


def _find_command_info(module: object, record: AppCommandRecord) -> typer.models.CommandInfo | None:
    matches: list[typer.models.CommandInfo] = []
    for candidate in _module_typer_apps(module):
        for current in _walk_typer_apps(candidate):
            for info in current.registered_commands:
                if _callback_owner(info.callback) == record.handler_owner:
                    matches.append(info)
    unique = {id(info): info for info in matches}
    if not unique:
        return None
    if len(unique) != 1:
        raise RuntimeError(
            f"expected one source command for {' '.join(record.path)!r}; found {len(unique)} in "
            f"{record.handler_owner.partition(':')[0]!r}"
        )
    return next(iter(unique.values()))


def _find_registrar_command_info(module: object, record: AppCommandRecord) -> typer.models.CommandInfo:
    if record.path[0] not in {"ledger", "live", "modelo"}:
        raise RuntimeError(f"command has no owned module target: {' '.join(record.path)!r}")
    host = _registrar_source_app(record.handler_owner.partition(":")[0], record.path[0])
    for current in _walk_typer_apps(host):
        for command in current.registered_commands:
            if _callback_owner(command.callback) == record.handler_owner and _command_name(command) == record.path[-1]:
                REGISTRAR_SOURCE_PATHS.add(record.path)
                return command
    raise RuntimeError(f"registrar command is absent for {' '.join(record.path)!r}")


@cache
def _registrar_source_app(module_name: str, family: str) -> typer.Typer:
    module = import_module(module_name)
    candidates = tuple(
        value
        for name, value in vars(module).items()
        if name.startswith("register") and callable(value)
    )
    host = typer.Typer()
    registered_any = False
    for registrar in candidates:
        signature = inspect.signature(registrar)
        parameters = tuple(signature.parameters.values())
        if not parameters or parameters[0].name not in {"app", "work_app", "evidence_app"}:
            continue
        kwargs: dict[str, object] = {}
        unresolved = False
        for parameter in parameters[1:]:
            if parameter.kind in {parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD}:
                continue
            dependency = _registration_dependency(family, parameter.name)
            if dependency is not None:
                kwargs[parameter.name] = dependency
            elif parameter.default is parameter.empty:
                unresolved = True
                break
        if unresolved:
            continue
        registrar(host, **kwargs)
        registered_any = True
    return host if registered_any else typer.Typer()


class _DeferredRegistrationDependency:
    """Keep a handler dependency off registration's import path."""

    __slots__ = ("attribute", "module")

    def __init__(self, module: str, attribute: str) -> None:
        self.module = module
        self.attribute = attribute

    def __call__(self, *args: object, **kwargs: object) -> object:
        callback = getattr(import_module(self.module), self.attribute)
        return callback(*args, **kwargs)


def _registration_dependency(family: str, name: str) -> object | None:
    direct = {
        "active_bucket_id": ("cadrumo.entrypoints.cli._common", "active_bucket_id_or_refuse"),
        "activate_output_language": ("cadrumo.entrypoints.cli._common", "activate_subcommand_output_language"),
        "parse_binding_override": ("cadrumo.entrypoints.cli._modelo_cli_support", "parse_binding_override"),
        "parse_casilla_override": ("cadrumo.entrypoints.cli._modelo_cli_support", "parse_casilla_override"),
        "bad_parameter_from_error": ("cadrumo.entrypoints.cli._modelo_cli_support", "bad_parameter_from_error"),
        "bad_parameter_from_localized_context": (
            "cadrumo.entrypoints.cli._modelo_cli_support",
            "bad_parameter_from_localized_context",
        ),
        "resolve_actor_option": ("cadrumo.entrypoints.cli._modelo_cli_support", "resolve_actor_option"),
        "resolve_default_actor": ("cadrumo.entrypoints.cli._modelo_cli_support", "resolve_default_actor"),
        "selector_bad_parameter": ("cadrumo.entrypoints.cli._modelo_cli_support", "selector_bad_parameter"),
        "calculate_input_bundle_from_cli": (
            "cadrumo.entrypoints.cli._modelo_cli_support",
            "work_calculate_input_bundle_from_cli",
        ),
    }
    target = direct.get(name)
    if target is not None:
        return _DeferredRegistrationDependency(*target)
    root_modules = {
        "ledger": "cadrumo.entrypoints.cli._ledger",
        "live": "cadrumo.entrypoints.cli._app_live",
        "modelo": "cadrumo.entrypoints.cli._modelo",
    }
    aliases = {
        "resolve_transaction_id": "_resolve_read_id",
        "require_active_profile": "_require_active_profile",
        "resolve_work_unit_for_cli": "_resolve_work_unit_for_cli",
        "resolve_revision_for_cli": "_resolve_revision_for_cli",
        "resolve_year_period": "_resolve_year_period",
        "resolve_optional_cli_period": "_resolve_optional_cli_period",
        "bare_period_error": "_bare_period_error",
        "guard_foral_profile_ccaa": "guard_active_profile_foral_ccaa",
        "missing_binding_guidance": "_missing_binding_guidance",
    }
    attribute = aliases.get(name, name)
    return _DeferredRegistrationDependency(root_modules[family], attribute)


def _module_typer_apps(module: object) -> tuple[typer.Typer, ...]:
    return tuple(value for value in vars(module).values() if isinstance(value, typer.Typer))


def _walk_typer_apps(root: typer.Typer) -> tuple[typer.Typer, ...]:
    pending = [root]
    seen: set[int] = set()
    result: list[typer.Typer] = []
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        result.append(current)
        pending.extend(child for group in current.registered_groups if (child := group.typer_instance) is not None)
    return tuple(result)


def _callback_owner(callback: object | None) -> str:
    if callback is None:
        return "<none>"
    module = getattr(callback, "__module__", type(callback).__module__)
    qualname = getattr(callback, "__qualname__", type(callback).__qualname__)
    return f"{module}:{qualname}"


def _command_name(info: typer.models.CommandInfo) -> str | None:
    if isinstance(info.name, str):
        return info.name
    if info.name is not None and not isinstance(info.name, DefaultPlaceholder):
        return cast(str, info.name)
    callback = info.callback
    if callback is None:
        return None
    name = getattr(callback, "__name__", None)
    return str(name).replace("_", "-") if isinstance(name, str) else None


@cache
def build_app_family(family: str) -> typer.Typer:
    """Build one metadata-only family root and enroll all descendants."""
    root_path = (family,)
    root_record = _RECORD_BY_PATH[root_path]
    descendants = tuple(
        record for record in APP_COMMAND_RECORDS if record.path[:1] == root_path and len(record.path) > 1
    )
    for record in descendants:
        _register(record)
    shell = typer.Typer(
        name=family,
        help=root_record.help(),
        no_args_is_help=root_record.no_args_is_help,
        cls=CadrumoTyperGroup,
    )
    declare_metadata_group(shell)
    return shell


__all__ = ["APP_COMMAND_RECORDS", "APP_COMMAND_TARGETS", "AppCommandRecord", "AppCommandTarget", "build_app_family"]
