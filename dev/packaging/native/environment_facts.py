"""What the installed Python side declares about its own process environment.

The package-side conformance check compares these facts with the package's
declaration. They are collected by the interpreter under test, which is the
assembled package's own, so they describe what ships: the command line's
settings and storage root, the runtime's agent launch composer and reserved
exit codes, and the bundled agent's settings.

The module imports only the standard library and the installed components,
lazily, and no packaging tool, so an interpreter can run it by path. It reads
one JSON request on standard input and prints one JSON document.
"""

from __future__ import annotations

import ast
import contextlib
import enum
import importlib.util
import json
import os
import sys
import tempfile
import types
import typing
from collections.abc import Callable, Generator, Mapping
from pathlib import Path, PurePath
from typing import Any

_WORKER_ENVIRONMENT = "spawn_env"
"""The name under which the agent's worker management builds its worker's environment."""


def kind_label(annotation: object) -> str:
    """Name the value space of a settings field, as the package's kinds are compared with it.

    ``text`` holds any string, including an enumeration of strings; ``language``
    is the command line's output language; ``secret`` is a field that holds a
    credential. A field that is none of these reads ``other:`` and its spelling.
    """
    from pydantic import SecretStr

    members = [member for member in typing.get_args(annotation) if member is not type(None)]
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        if len(members) != 1:
            return f"other:{annotation!r}"
        annotation = members[0]
    if typing.get_origin(annotation) is typing.Literal:
        return "text"
    if annotation is SecretStr:
        return "secret"
    if not isinstance(annotation, type):
        return f"other:{annotation!r}"
    if issubclass(annotation, enum.Enum):
        return "language" if annotation.__name__ == "OutputLanguage" else "text"
    for label, accepted in (
        ("boolean", bool),
        ("integer", int),
        ("number", float),
        ("text", str),
        ("path", PurePath),
    ):
        if issubclass(annotation, accepted):
            return label
    return f"other:{annotation!r}"


def _relative(path: Path, root: Path) -> str:
    """Spell ``path`` beneath ``root`` with forward slashes, or as it is when it lies elsewhere."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


@contextlib.contextmanager
def _without_environment(names: set[str]) -> Generator[None]:
    """Hide the named variables from this process while a caller builds settings from arguments."""
    hidden = {key: value for key, value in os.environ.items() if key.upper() in names}
    for key in hidden:
        del os.environ[key]
    try:
        yield
    finally:
        os.environ.update(hidden)


def collect_cli(request: Mapping[str, Any], scratch: Path) -> dict[str, Any]:
    """Collect the command line's settings, built-in storage root and diagnostic-log placement."""
    from cadrumo.core.config import AuthorityRootSettings, Settings
    from cadrumo.core.errors.hierarchy import CoreValidationError
    from cadrumo.core.storage_environment import (
        STORAGE_PATH_RULES,
        STORAGE_ROOT,
        TEMPORARY_VARIABLES,
        StorageMode,
        StorageRootRefusal,
        host_installed_default_root,
    )
    from cadrumo.core.storage_taxonomy import StorageCategory
    from cadrumo.core.storage_taxonomy_locations import storage_location, storage_path

    fields = Settings.model_fields
    environment_fields = {
        environment_name: field
        for field_name, field in fields.items()
        for environment_name in Settings._environment_names_for_field(field_name)
    }
    settings = {
        name: kind_label(environment_fields[name].annotation) if name in environment_fields else None
        for name in sorted(Settings.env_var_names())
    }
    root = {
        "variable": STORAGE_ROOT.variable,
        "development_variable": STORAGE_ROOT.development_variable,
        "development_default": Path(*STORAGE_ROOT.development_default).as_posix(),
        "checkout_marker": STORAGE_ROOT.checkout_marker,
        "precedence": {mode.value: list(STORAGE_ROOT.root_variables(mode)) for mode in StorageMode},
        "relative_override": {mode.value: STORAGE_ROOT.relative_override(mode).value for mode in StorageMode},
        "installed_defaults": [
            {
                "platform": rule.platform.value,
                "candidates": [
                    {"variable": candidate.variable, "subpath": list(candidate.subpath)}
                    for candidate in rule.candidates
                ],
                "home_variable": rule.home_variable,
            }
            for rule in STORAGE_ROOT.installed_defaults
        ],
        "channel": {
            "product_directory": STORAGE_ROOT.product_directory,
            "stable": STORAGE_ROOT.stable_channel,
            "separator": STORAGE_ROOT.channel_separator,
        },
        "posix_directory_mode": STORAGE_ROOT.posix_directory_mode,
        "refusals": [refusal.value for refusal in StorageRootRefusal],
        "path_rules": STORAGE_PATH_RULES._asdict(),
    }
    try:
        default_root: dict[str, str] = {"root": str(host_installed_default_root(request["received"]))}
    except CoreValidationError as error:
        default_root = {"refusal": str((error.context or {})["storage_root_refusal"])}
    log_root = scratch / "log-root"
    # The settings are built from their arguments alone: this process's own overrides place its logs elsewhere.
    with _without_environment(set(settings)):
        default_logs = storage_path(StorageCategory.LOGS, settings=Settings(cadrumo_local_storage_root=log_root))
        relocated_logs = storage_path(
            StorageCategory.LOGS,
            settings=Settings(cadrumo_local_storage_root=log_root, cadrumo_log_dir=Path(request["log_relative"])),
        )
    return {
        "settings": settings,
        "root": root,
        "channel_directories": {channel: STORAGE_ROOT.channel_directory(channel) for channel in request["channels"]},
        "default_root": default_root,
        "authority_variables": sorted(name.upper() for name in AuthorityRootSettings.model_fields),
        "temporary_variables": list(TEMPORARY_VARIABLES),
        "log": {
            "default": _relative(default_logs, log_root),
            "relocated": _relative(relocated_logs, log_root),
            "file_name": PurePath(storage_location(StorageCategory.LOG_FILE).subpath).name,
        },
    }


def collect_runtime(request: Mapping[str, Any], scratch: Path) -> dict[str, Any]:
    """Collect the runtime's agent launch: its package variables, gateway invocation, slots and reserved exits."""
    from cadrumo_agent_service.adapters.agent_programs import (
        GATEWAY_ARGUMENTS,
        PACKAGE_AEAT_VARIABLE,
        PACKAGE_AGENT_VARIABLE,
        PACKAGE_PYTHON_VARIABLE,
        PACKAGE_RELAY_VARIABLE,
    )
    from cadrumo_agent_service.host.launch_environment import (
        ADVERTISED_VARIABLES,
        GATEWAY_SLOTS,
        agent_launch_environment,
    )
    from cadrumo_agent_service.host.native_refusal import NativeLaunchRefusalCode
    from cadrumo_client.contracts.contracts import (
        NATIVE_HOST_LAUNCH_PROFILE_REFUSED_EXIT_CODE,
        RESERVED_HOST_EXIT_CODES,
    )

    programs = {name: scratch / name for name in ("relay", "aeat", "python")}
    for program in programs.values():
        program.write_bytes(b"")
    composed = agent_launch_environment(
        storage_root=scratch / "storage",
        agent_root=scratch / "hosted",
        relay=programs["relay"],
        aeat=programs["aeat"],
        python=programs["python"],
        received=request["received"],
    )
    return {
        "agent_variable": PACKAGE_AGENT_VARIABLE,
        "relay_variable": PACKAGE_RELAY_VARIABLE,
        "program_variables": [PACKAGE_AEAT_VARIABLE, PACKAGE_PYTHON_VARIABLE],
        "advertised_variables": sorted(ADVERTISED_VARIABLES),
        "gateway_arguments": list(GATEWAY_ARGUMENTS),
        "gateway_slots": sorted(GATEWAY_SLOTS),
        "composed": sorted(composed),
        "reserved_exit_codes": [
            {"owner": reserved.owner, "first": reserved.first, "last": reserved.last}
            for reserved in RESERVED_HOST_EXIT_CODES
        ],
        "launch_profile_refused": NATIVE_HOST_LAUNCH_PROFILE_REFUSED_EXIT_CODE,
        "native_refusals": [refusal.value for refusal in NativeLaunchRefusalCode],
    }


def worker_environment_writes(module: str, setting_env: Callable[[str], str]) -> list[str]:
    """Return the environment names the gateway writes into its worker's environment.

    The agent names every such write through ``setting_env``, so reading its
    worker management source finds each name without running a gateway. An
    empty answer means the source no longer has the shape this reads.
    """
    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin is None or not spec.origin.endswith(".py"):
        return []
    names: set[str] = set()
    for node in ast.walk(ast.parse(Path(spec.origin).read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == _WORKER_ENVIRONMENT
                and isinstance(target.slice, ast.Call)
                and isinstance(target.slice.func, ast.Name)
                and target.slice.func.id == "setting_env"
                and len(target.slice.args) == 1
                and isinstance(target.slice.args[0], ast.Constant)
                and isinstance(target.slice.args[0].value, str)
            ):
                names.add(setting_env(target.slice.args[0].value))
    return sorted(names)


def collect_agent() -> dict[str, Any] | None:
    """Collect the bundled agent's settings, credentials, contract and worker environment; ``None`` if absent."""
    if importlib.util.find_spec("cadrumo_agent") is None:
        return None
    # Imported by name: the agent is installed in the package's interpreter, not in the one that checks this file.
    config = importlib.import_module("cadrumo_agent.control.config")
    registry = importlib.import_module("cadrumo_agent.control.env_registry")
    field_env_names = importlib.import_module("cadrumo_agent.control.settings_base").field_env_names

    settings: dict[str, str] = {}
    for field, info in config.Settings.model_fields.items():
        label = kind_label(info.annotation)
        for name in field_env_names(config.Settings, field):
            settings.setdefault(name, label)
    return {
        "prefix": importlib.import_module("cadrumo_agent.control.env_prefix").ENV_PREFIX,
        "hosting_contract": importlib.import_module("cadrumo_agent.control.hosting_contract").HOSTING_CONTRACT,
        "settings": dict(sorted(settings.items())),
        "credentials": sorted(registry.CREDENTIAL_ENV_NAMES),
        "settings_file_variable": registry.ENV_FILE_VARIABLE.env_name,
        "worker_environment_writes": worker_environment_writes(
            "cadrumo_agent.control.worker_management", config.setting_env
        ),
    }


def collect(request: Mapping[str, Any]) -> dict[str, Any]:
    """Collect every installed component's environment facts for one request.

    ``request`` names the caller's environment (``received``), the channels
    whose root directories to name, and the relative diagnostic-log directory
    to place. Directories the components create are made in a scratch tree
    that is removed afterwards.
    """
    from cadrumo.core.storage_environment import prepare_temporary_directory

    with tempfile.TemporaryDirectory(prefix="cadrumo-conformance-", dir=prepare_temporary_directory()) as directory:
        scratch = Path(directory)
        return {
            "cli": collect_cli(request, scratch),
            "runtime": collect_runtime(request, scratch),
            "agent": collect_agent(),
        }


def main() -> int:
    """Print the facts for the JSON request on standard input."""
    sys.stdout.write(json.dumps(collect(json.loads(sys.stdin.read()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
