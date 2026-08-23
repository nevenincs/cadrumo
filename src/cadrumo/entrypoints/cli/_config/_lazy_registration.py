"""Metadata-only nested registrations for the complete config command tree."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import typer
from typer.models import DefaultPlaceholder

from ....core.i18n import tr
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


def _target_factory(path: ConfigPath, kind: str) -> Callable[[], typer.Typer]:
    """Bind one stable, path-specific target owner for census attribution."""

    def _load_config_target() -> typer.Typer:
        return _group_target(path) if kind == "group" else _leaf_target(path)

    slug = "__".join(path).replace("-", "_")
    _load_config_target.__name__ = f"load_{slug}"
    _load_config_target.__qualname__ = f"config_targets.load_{slug}"
    return _load_config_target


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

_LEAF_HELP_KEYS: dict[ConfigPath, str] = {
    ("auth", "apoderado", "check"): "cli.config.auth.apoderado.check_help",
    ("auth", "apoderado", "clear"): "cli.config.auth.apoderado.clear_help",
    ("auth", "apoderado", "configure"): "cli.config.auth.apoderado.configure_help",
    ("auth", "apoderado", "scopes", "list"): "cli.config.auth.apoderado.scopes.list_help",
    ("auth", "apoderado", "status"): "cli.config.auth.apoderado.status_help",
    ("auth", "certificate", "check"): "cli.config.auth.certificate.check_help",
    ("auth", "certificate", "list"): "cli.config.auth.certificate.list_help",
    ("auth", "certificate", "register"): "cli.config.auth.certificate.register_help",
    ("auth", "certificate", "remove"): "cli.config.auth.certificate.remove_help",
    ("auth", "certificate", "secret", "remove"): "cli.config.auth.certificate.secret.remove_help",
    ("auth", "certificate", "secret", "set"): "cli.config.auth.certificate.secret.set_help",
    ("auth", "certificate", "select"): "cli.config.auth.certificate.select_help",
    ("auth", "configure"): "cli.config.auth.configure_help",
    ("auth", "diagnostics", "list"): "cli.config.auth.diagnostics.list_help",
    ("auth", "diagnostics", "report"): "cli.config.auth.diagnostics.report_help",
    ("auth", "diagnostics", "show"): "cli.config.auth.diagnostics.show_help",
    ("auth", "login"): "cli.config.auth.login_help",
    ("auth", "logout"): "cli.config.auth.logout_help",
    ("auth", "providers"): "cli.config.auth.providers_help",
    ("auth", "reset"): "cli.config.auth.reset_help",
    ("auth", "status"): "cli.config.auth.status_help",
    ("auth", "test"): "cli.config.auth.test_help",
    ("check",): "cli.config.check.help",
    ("collab", "recipient", "add"): "cli.config.collab.recipient.add_help",
    ("collab", "recipient", "list"): "cli.config.collab.recipient.list_help",
    ("collab", "recipient", "remove"): "cli.config.collab.recipient.remove_help",
    ("google", "credential-source", "set"): "cli.config.google.credential_source.set_help",
    ("google", "credential-source", "show"): "cli.config.google.credential_source.show_help",
    ("google", "folder", "get"): "cli.config.google.folder.get_help",
    ("google", "folder", "set"): "cli.config.google.folder.set_help",
    ("google", "login"): "cli.config.google.login_help",
    ("google", "logout"): "cli.config.google.logout_help",
    ("google", "register"): "cli.config.google.register_help",
    ("google", "status"): "cli.config.google.status_help",
    ("google", "sync", "calc", "compute"): "cli.config.google.sync.calc.compute_help",
    ("google", "sync", "calc", "export"): "cli.config.google.sync.calc.export_help",
    ("google", "sync", "calc", "pull"): "cli.config.google.sync.calc.pull_help",
    ("google", "sync", "calc", "verify"): "cli.config.google.sync.calc.verify_help",
    ("google", "sync", "probe"): "cli.config.google.sync.probe_help",
    ("google", "sync", "push"): "cli.config.google.sync.push_help",
    ("login",): "cli.config.login.help",
    ("logout",): "cli.config.logout.help",
    ("passphrase", "change"): "cli.config.passphrase.change_help",
    ("profile", "archive", "export"): "cli.config.profile.archive.export_help",
    ("profile", "archive", "inspect"): "cli.config.profile.archive.inspect_help",
    ("profile", "capabilities", "set"): "cli.config.profile.capabilities.set_help",
    ("profile", "capabilities", "show"): "cli.config.profile.capabilities.show_help",
    ("profile", "censo", "file"): "cli.config.profile.censo.file_help",
    ("profile", "censo", "pull"): "cli.config.profile.censo.pull_help",
    ("profile", "complete-setup"): "cli.config.profile.complete_setup.help",
    ("profile", "create"): "cli.config.profile.create_help",
    ("profile", "delete"): "cli.config.profile.delete.help",
    ("profile", "descendiente", "add"): "cli.config.profile.descendiente.add_help",
    ("profile", "descendiente", "list"): "cli.config.profile.descendiente.list_help",
    ("profile", "descendiente", "remove"): "cli.config.profile.descendiente.remove_help",
    ("profile", "edit"): "cli.config.profile.edit_help",
    ("profile", "history"): "cli.config.profile.history_help",
    ("profile", "list"): "cli.config.list.help",
    ("profile", "preflight"): "cli.config.profile.preflight_help",
    ("profile", "restore"): "cli.config.profile.restore.help",
    ("profile", "show"): "cli.config.profile.show_help",
    ("profile", "status"): "cli.config.status.help",
    ("profile", "validate"): "cli.config.profile.validate_help",
    ("provision", "pull"): "cli.config.provision.pull.help",
    ("provision", "report"): "cli.config.provision.report.help",
    ("provision", "verify"): "cli.config.provision.verify.help",
    ("repair", "connectivity"): "cli.config.repair.connectivity_help",
    ("repair", "integrity", "objects"): "cli.config.repair.integrity.objects_help",
    ("repair", "integrity", "registry"): "cli.config.repair.integrity.registry_help",
    ("repair", "logs"): "cli.config.repair.logs_help",
    ("repair", "profile"): "cli.config.repair.profile_help",
    ("repair", "quarantine"): "cli.config.repair.quarantine_help",
    ("repair", "reset-progress"): "cli.config.repair.reset_progress_help",
    ("reset", "resume"): "cli.config.reset.resume_help",
    ("reset", "start"): "cli.config.reset.start_help",
    ("reset", "status"): "cli.config.reset.status_help",
    ("storage", "check"): "cli.config.storage.check.help",
    ("storage", "init"): "cli.config.storage.init.help",
    ("storage", "list"): "cli.config.storage.list.area_help",
    ("storage", "reclaim"): "cli.config.storage.reclaim.area_help",
    ("storage", "show"): "cli.config.storage.show.area_help",
}


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
    return tr(_LEAF_HELP_KEYS[path])


def _register(path: ConfigPath, kind: str, help_text: str) -> None:
    parent = path[:-1]
    name = path[-1]
    register_lazy_subcommand(
        _registry_key(parent),
        LazySubcommand(
            name,
            LazyFactoryTarget(
                _target_factory(path, kind),
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
        group = next(
            (
                group
                for group in current.registered_groups
                if _mounted_group_name(group) == token
            ),
            None,
        )
        if group is None:
            raise RuntimeError(f"source group is absent at {' '.join(path)!r}")
        child = group.typer_instance
        if child is None:
            raise RuntimeError(f"source group has no Typer instance at {' '.join(path)!r}")
        current = child
    return current


def _mounted_group_name(group: typer.models.TyperInfo) -> str | None:
    if isinstance(group.name, str):
        return group.name
    if group.name is not None and not isinstance(group.name, DefaultPlaceholder):
        raise TypeError(f"unsupported Typer group name: {type(group.name).__name__}")
    child = group.typer_instance
    return None if child is None else child.info.name


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
        mode = cast_wizard_mode(name)
        return build_wizard_leaf_app(name, mode, help=tr(help_key), epilog=epilog), (name,)
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
        from ._profile_readiness import _read_profile_record
        from ._profile_support import resolve_profile_by_label
        from ._repair_cli import register_repair_maintenance_commands
        from ._repair_profile import register_repair_profile_command

        repair = typer.Typer(name="repair", no_args_is_help=False, invoke_without_command=True)
        register_repair_maintenance_commands(repair)
        register_repair_profile_command(
            repair,
            resolve_profile_by_label=resolve_profile_by_label,
            read_profile_record=_read_profile_record,
        )
        return repair, path[1:]
    if path[:1] == ("reset",):
        from ._reset_cli import reset_app

        return reset_app, path[1:]
    if path[:1] == ("storage",):
        from ._storage_cli import storage_app

        return storage_app, path[1:]
    raise RuntimeError(f"unmapped config target: {' '.join(path)!r}")


def cast_wizard_mode(name: str) -> Literal["create", "edit"]:
    """Narrow a manifest token after the explicit path membership guard."""
    if name not in {"create", "edit"}:
        raise ValueError(f"unsupported wizard mode: {name!r}")
    return name


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
for _path in _LEAF_HELP_KEYS:
    _register(_path, "leaf", _leaf_help(_path))

__all__ = ["app"]
