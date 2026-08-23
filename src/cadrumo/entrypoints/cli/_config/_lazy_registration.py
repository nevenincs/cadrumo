"""Metadata-only nested registrations for the complete config command tree."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import typer

from ....core.i18n import output_language, tr
from .._command_schema import command_registration_metadata
from .._command_suggestions import (
    CadrumoTyperGroup,
    LazyFactoryTarget,
    LazyOptionalDependencyProvider,
    LazySubcommand,
    register_lazy_subcommand,
)
from ._execution_policies import declare_metadata_group
from ._root_cli import config_root

type ConfigPath = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ConfigTarget:
    path: ConfigPath
    kind: str

    def __call__(self) -> typer.Typer:
        return _group_target(self.path) if self.kind == "group" else _leaf_target(self.path)


_GROUP_HELP_KEYS: dict[ConfigPath, str] = {
    ("auth",): "cli.config.auth.help",
    ("auth", "apoderado"): "cli.config.auth.apoderado.help",
    ("auth", "apoderado", "scopes"): "cli.config.auth.apoderado.scopes.help",
    ("auth", "certificate"): "cli.config.auth.certificate.help",
    ("auth", "certificate", "secret"): "cli.config.auth.certificate.secret.help",
    ("auth", "diagnostics"): "cli.config.auth.diagnostics.help",
    ("collab",): "cli.config.collab.help",
    ("collab", "recipient"): "cli.config.collab.recipient.help",
    ("google",): "cli.config.google.help",
    ("google", "credential-source"): "cli.config.google.credential_source.help",
    ("google", "folder"): "cli.config.google.folder.help",
    ("google", "sync"): "cli.config.google.sync.help",
    ("google", "sync", "calc"): "cli.config.google.sync.calc.help",
    ("passphrase",): "cli.config.passphrase.help",
    ("profile",): "cli.config.profile.help",
    ("profile", "archive"): "cli.config.profile.archive.help",
    ("profile", "capabilities"): "cli.config.profile.capabilities.help",
    ("profile", "censo"): "cli.config.profile.censo.help",
    ("profile", "descendiente"): "cli.config.profile.descendiente.help",
    ("provision",): "cli.config.provision.help",
    ("repair",): "cli.config.repair.help",
    ("repair", "integrity"): "cli.config.repair.integrity.help",
    ("reset",): "cli.config.reset.help",
    ("storage",): "cli.config.storage.help",
}

_LEAF_PATHS: tuple[ConfigPath, ...] = (
    ("auth", "apoderado", "check"),
    ("auth", "apoderado", "clear"),
    ("auth", "apoderado", "configure"),
    ("auth", "apoderado", "scopes", "list"),
    ("auth", "apoderado", "status"),
    ("auth", "certificate", "check"),
    ("auth", "certificate", "list"),
    ("auth", "certificate", "register"),
    ("auth", "certificate", "remove"),
    ("auth", "certificate", "secret", "remove"),
    ("auth", "certificate", "secret", "set"),
    ("auth", "certificate", "select"),
    ("auth", "configure"),
    ("auth", "diagnostics", "list"),
    ("auth", "diagnostics", "report"),
    ("auth", "diagnostics", "show"),
    ("auth", "login"),
    ("auth", "logout"),
    ("auth", "providers"),
    ("auth", "reset"),
    ("auth", "status"),
    ("auth", "test"),
    ("check",),
    ("collab", "recipient", "add"),
    ("collab", "recipient", "list"),
    ("collab", "recipient", "remove"),
    ("google", "credential-source", "set"),
    ("google", "credential-source", "show"),
    ("google", "folder", "get"),
    ("google", "folder", "set"),
    ("google", "login"),
    ("google", "logout"),
    ("google", "register"),
    ("google", "status"),
    ("google", "sync", "calc", "compute"),
    ("google", "sync", "calc", "export"),
    ("google", "sync", "calc", "pull"),
    ("google", "sync", "calc", "verify"),
    ("google", "sync", "probe"),
    ("google", "sync", "push"),
    ("login",),
    ("logout",),
    ("passphrase", "change"),
    ("profile", "archive", "export"),
    ("profile", "archive", "inspect"),
    ("profile", "capabilities", "set"),
    ("profile", "capabilities", "show"),
    ("profile", "censo", "file"),
    ("profile", "censo", "pull"),
    ("profile", "complete-setup"),
    ("profile", "create"),
    ("profile", "delete"),
    ("profile", "descendiente", "add"),
    ("profile", "descendiente", "list"),
    ("profile", "descendiente", "remove"),
    ("profile", "edit"),
    ("profile", "history"),
    ("profile", "list"),
    ("profile", "preflight"),
    ("profile", "restore"),
    ("profile", "show"),
    ("profile", "status"),
    ("profile", "validate"),
    ("provision", "pull"),
    ("provision", "report"),
    ("provision", "verify"),
    ("repair", "connectivity"),
    ("repair", "integrity", "objects"),
    ("repair", "integrity", "registry"),
    ("repair", "logs"),
    ("repair", "profile"),
    ("repair", "quarantine"),
    ("repair", "reset-progress"),
    ("reset", "resume"),
    ("reset", "start"),
    ("reset", "status"),
    ("storage", "check"),
    ("storage", "init"),
    ("storage", "list"),
    ("storage", "reclaim"),
    ("storage", "show"),
)


def _registry_key(path: ConfigPath) -> str:
    return "config" if not path else "config." + ".".join(path)


def _decorate(target: typer.Typer) -> None:
    from .._errors import decorate_typer_app

    decorate_typer_app(target)


def _required_unavailable(name: str, error: ModuleNotFoundError):
    from .. import _required_import_failure

    return _required_import_failure(name, error)


def _optional_unavailable(name: str, error: ModuleNotFoundError) -> typer.Typer:
    from .. import _optional_import_surface

    return _optional_import_surface(name, error)


def _optional_dependencies() -> frozenset[str]:
    from .. import _optional_dependency_names

    return _optional_dependency_names()


def _leaf_help(path: ConfigPath) -> str:
    language = output_language()
    cli_path = ("config", *path)
    row = next((row for row in command_registration_metadata() if row.cli_path == cli_path), None)
    if row is None:
        raise RuntimeError(f"missing registration metadata for {' '.join(cli_path)!r}")
    return row.help.get(language) or row.help.get("es") or ""


def _register(path: ConfigPath, kind: str, help_text: str) -> None:
    parent = path[:-1]
    name = path[-1]
    register_lazy_subcommand(
        _registry_key(parent),
        LazySubcommand(
            name,
            LazyFactoryTarget(
                _ConfigTarget(path, kind),
                optional_dependencies=LazyOptionalDependencyProvider(_optional_dependencies),
            ),
            child_registry_key=_registry_key(path),
            decorate=_decorate,
            optional_unavailable=_optional_unavailable,
            required_unavailable=_required_unavailable,
            help=help_text,
        ),
    )


def _group_target(path: ConfigPath) -> typer.Typer:
    if path in {("repair",), ("profile", "descendiente")}:
        source, relative = _source_app(path)
        source_group = _typer_group(source, relative)
        shell = typer.Typer(
            name=path[-1],
            help=tr(_GROUP_HELP_KEYS[path]),
            no_args_is_help=False,
            invoke_without_command=True,
            cls=CadrumoTyperGroup,
        )
        shell.registered_callback = source_group.registered_callback
        return shell
    shell = typer.Typer(
        name=path[-1],
        help=tr(_GROUP_HELP_KEYS[path]),
        no_args_is_help=True,
        cls=CadrumoTyperGroup,
    )
    declare_metadata_group(shell)
    return shell


def _leaf_target(path: ConfigPath) -> typer.Typer:
    source, relative = _source_app(path)
    parent = _typer_group(source, relative[:-1])
    command_name = relative[-1]
    info = next((info for info in parent.registered_commands if info.name == command_name), None)
    if info is None:
        raise RuntimeError(f"source command is absent for {' '.join(path)!r}")
    target = typer.Typer()
    target.registered_commands.append(info)
    return target


def _typer_group(root: typer.Typer, path: ConfigPath) -> typer.Typer:
    current = root
    for token in path:
        group = next((group for group in current.registered_groups if group.name == token), None)
        if group is None:
            raise RuntimeError(f"source group is absent at {' '.join(path)!r}")
        current = cast("typer.models.TyperInfo", group).typer_instance
    return current


def _temporary_app(registrar: Callable[[typer.Typer], None]) -> typer.Typer:
    target = typer.Typer()
    registrar(target)
    return target


def _source_app(path: ConfigPath) -> tuple[typer.Typer, ConfigPath]:
    if path[:2] == ("auth", "apoderado"):
        from ._apoderado import apoderado_app, register_apoderado_commands
        from ._profile_support import resolve_active_profile_pointer

        host = typer.Typer()
        register_apoderado_commands(host, resolve_active_profile_pointer=resolve_active_profile_pointer)
        return apoderado_app, path[2:]
    if path[:2] == ("auth", "certificate"):
        from ._certificate import certificate_app

        return certificate_app, path[2:]
    if path[:2] == ("auth", "diagnostics"):
        from ._auth_diagnostics import auth_diagnostics_app

        return auth_diagnostics_app, path[2:]
    if path[0] == "auth":
        from ._auth import auth_app

        return auth_app, path[1:]
    if path == ("check",):
        from ._check_cli import register

        return _temporary_app(register), path
    if path[:1] == ("collab",):
        from ._collab import collab_app, register_collab_commands

        register_collab_commands(typer.Typer())
        return collab_app, path[1:]
    if path[:1] == ("google",):
        from ._google import google_app

        return google_app, path[1:]
    if path in {("login",), ("logout",)}:
        from ._custody import register_custody_commands

        return _temporary_app(register_custody_commands), path
    if path[:1] == ("passphrase",):
        from ._passphrase import register_passphrase_commands

        return _temporary_app(register_passphrase_commands), path
    if path == ("profile", "list"):
        from ._profile_list_cli import app as list_app

        return list_app, ("list",)
    if path == ("profile", "status"):
        from ._profile_status_cli import app as status_app

        return status_app, ("status",)
    if path[:2] == ("profile", "archive"):
        from ._archive_cli import register_archive_commands
        from ._profile_support import resolve_profile_by_label

        host = typer.Typer()
        register_archive_commands(host, resolve_profile_by_label=resolve_profile_by_label)
        return host, path[1:]
    if path[:2] == ("profile", "capabilities"):
        from ._capabilities_cli import register

        return _temporary_app(register), path[1:]
    if path[:2] == ("profile", "censo"):
        from ._censo_file import censo_app

        return censo_app, path[2:]
    if path[:2] == ("profile", "descendiente"):
        from ._descendiente import descendiente_app, register_descendiente_commands
        from ._profile_support import resolve_active_profile_pointer

        register_descendiente_commands(
            typer.Typer(),
            resolve_active_profile_pointer=resolve_active_profile_pointer,
        )
        return descendiente_app, path[2:]
    if path == ("profile", "complete-setup"):
        from ._complete_setup_cli import register

        return _temporary_app(register), path[1:]
    if path in {("profile", "create"), ("profile", "edit")}:
        from ._manager_dispatch import build_wizard_leaf_app

        name = path[-1]
        help_key = f"cli.config.profile.{name}_help"
        epilog = tr("cli.config.profile.create_epilog") if name == "create" else None
        return build_wizard_leaf_app(name, cast("object", name), help=tr(help_key), epilog=epilog), (name,)
    if path == ("profile", "delete"):
        from ._profile_delete import register_profile_delete_command
        from ._profile_support import resolve_profile_by_label

        host = typer.Typer()
        register_profile_delete_command(host, resolve_profile_by_label=resolve_profile_by_label)
        return host, path[1:]
    if path == ("profile", "history"):
        from ._bucket_history import register_bucket_history_commands

        return _temporary_app(register_bucket_history_commands), path[1:]
    if path in {
        ("profile", "preflight"),
        ("profile", "show"),
        ("profile", "validate"),
    }:
        from ._profile_inspect import register_profile_inspect_commands
        from ._profile_support import resolve_active_profile_pointer

        host = typer.Typer()
        register_profile_inspect_commands(host, resolve_active_profile_pointer=resolve_active_profile_pointer)
        return host, path[1:]
    if path == ("profile", "restore"):
        from ._restore_cli import register_restore_commands

        return _temporary_app(register_restore_commands), path[1:]
    if path[:1] == ("provision",):
        from ._provision_cli import register_provision_commands

        return _temporary_app(register_provision_commands), path
    if path[:1] == ("repair",):
        from ._profile_support import read_profile_record, resolve_profile_by_label
        from ._repair_cli import register_repair_maintenance_commands
        from ._repair_profile import register_repair_profile_command

        repair = typer.Typer(name="repair", no_args_is_help=False, invoke_without_command=True)
        register_repair_maintenance_commands(repair)
        register_repair_profile_command(
            repair,
            resolve_profile_by_label=resolve_profile_by_label,
            read_profile_record=read_profile_record,
        )
        return repair, path[1:]
    if path[:1] == ("reset",):
        from ._reset_cli import reset_app

        return reset_app, path[1:]
    if path[:1] == ("storage",):
        from ._storage_cli import storage_app

        return storage_app, path[1:]
    raise RuntimeError(f"unmapped config target: {' '.join(path)!r}")


app = typer.Typer(
    name="config",
    help=tr("cli.config.app_help"),
    no_args_is_help=False,
    invoke_without_command=True,
    add_help_option=False,
    cls=CadrumoTyperGroup,
)
app.callback()(config_root)

for _path, _help_key in _GROUP_HELP_KEYS.items():
    _register(_path, "group", tr(_help_key))
for _path in _LEAF_PATHS:
    _register(_path, "leaf", _leaf_help(_path))

__all__ = ["app"]
