"""Focused contracts for the reusable lazy command-node loader."""

from __future__ import annotations

import subprocess
import sys
from typing import Never

import pytest
import typer

from .._app_execution_policies import METADATA
from .._command_policy import command_execution_policy, execution_policy_for
from .._command_suggestions import (
    CadrumoTyperGroup,
    LazyImportTarget,
    LazySubcommand,
    materialise_lazy_subcommands,
    register_lazy_subcommand,
    resolve_command_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PACKAGE = "cadrumo.entrypoints.cli.tests"
_TARGET = f"{_PACKAGE}._lazy_loader_target"
_NESTED_TARGET = f"{_PACKAGE}._lazy_loader_nested_target"
_SIBLING = f"{_PACKAGE}._lazy_loader_sibling"
_BROKEN_OPTIONAL = f"{_PACKAGE}._s09_optional_package"
_BROKEN_OPTIONAL_INTERNAL = f"{_PACKAGE}._s09_optional_internal_package"


class RequiredTargetUnavailableError(RuntimeError):
    """Test-only typed refusal retaining the required import defect."""


def _required_refusal(_name: str, error: ModuleNotFoundError) -> Never:
    raise RequiredTargetUnavailableError(error.name) from error


def _optional_surface(name: str, _error: ModuleNotFoundError) -> typer.Typer:
    app = typer.Typer(name=name)

    @app.callback()
    @command_execution_policy(METADATA)
    def unavailable() -> None:
        return None

    return app


def test_import_target_loads_exact_module_without_importing_sibling() -> None:
    sys.modules.pop(_SIBLING, None)
    loader = LazySubcommand("selected", LazyImportTarget(_TARGET))

    command = loader.load()

    assert command.name == "selected"
    assert _TARGET in sys.modules
    assert _SIBLING not in sys.modules
    assert loader.loader_owner == f"{_TARGET}:app"
    assert loader.target == LazyImportTarget(_TARGET)


def test_bootstrap_registration_does_not_eagerly_load_optional_inventory() -> None:
    code = (
        "import sys; import cadrumo.entrypoints.cli; "
        "raise SystemExit('cadrumo.core._optional_extras' in sys.modules)"
    )

    # S603-RATIONALE: the executable is this test process's trusted interpreter
    # and every argument is a fixed source literal; no operator input enters.
    completed = subprocess.run([sys.executable, "-c", code], check=False, timeout=60)  # noqa: S603

    assert completed.returncode == 0


def test_repeated_materialisation_preserves_command_callback_and_policy_identity() -> None:
    loader = LazySubcommand("selected", LazyImportTarget(_TARGET))

    first = loader.load()
    second = loader.load()

    assert first is second
    assert first.callback is second.callback
    assert execution_policy_for(first.callback) is METADATA


def test_required_dependency_failure_is_typed_and_retains_original_cause() -> None:
    missing = "cadrumo_s09_required_dependency_that_does_not_exist"
    loader = LazySubcommand(
        "required",
        LazyImportTarget(missing),
        required_unavailable=_required_refusal,
    )

    with pytest.raises(RequiredTargetUnavailableError) as raised:
        loader.load()

    assert isinstance(raised.value.__cause__, ModuleNotFoundError)
    assert raised.value.__cause__.name == missing


def test_only_an_explicitly_named_optional_dependency_can_degrade() -> None:
    missing = "cadrumo_s09_optional_dependency_that_does_not_exist"
    loader = LazySubcommand(
        "optional",
        LazyImportTarget(missing, optional_dependencies=frozenset({missing})),
        optional_unavailable=_optional_surface,
    )

    command = loader.load()

    assert command.name == "optional"
    assert execution_policy_for(command.callback) is METADATA


def test_missing_dependency_inside_optional_package_fails_loudly() -> None:
    loader = LazySubcommand(
        "broken-optional",
        LazyImportTarget(_BROKEN_OPTIONAL, optional_dependencies=frozenset({_BROKEN_OPTIONAL})),
        optional_unavailable=_optional_surface,
    )

    with pytest.raises(ModuleNotFoundError) as raised:
        loader.load()

    assert raised.value.name == "s09_absent_transitive_dependency"


def test_same_namespace_internal_module_is_not_mistaken_for_absent_optional_package() -> None:
    loader = LazySubcommand(
        "broken-optional-internal",
        LazyImportTarget(
            _BROKEN_OPTIONAL_INTERNAL,
            optional_dependencies=frozenset({_BROKEN_OPTIONAL_INTERNAL}),
        ),
        optional_unavailable=_optional_surface,
    )

    with pytest.raises(ModuleNotFoundError) as raised:
        loader.load()

    assert raised.value.name == f"{_BROKEN_OPTIONAL_INTERNAL}.broken_internal"


def test_nested_resolution_materialises_only_each_selected_token() -> None:
    root = typer.Typer(name="s09-root", cls=CadrumoTyperGroup)

    @root.callback()
    @command_execution_policy(METADATA)
    def root_callback() -> None:
        return None

    register_lazy_subcommand(
        "s09-root",
        LazySubcommand("parent", LazyImportTarget(_TARGET), child_registry_key="s09-parent-target"),
    )
    register_lazy_subcommand(
        "s09-parent-target",
        LazySubcommand("nested", LazyImportTarget(_NESTED_TARGET)),
    )

    command = resolve_command_path(root, ("parent", "nested", "run"))

    assert command.name == "run"
    assert execution_policy_for(command.callback) is METADATA


def test_full_materialisation_reaches_nested_lazy_click_nodes() -> None:
    root = typer.Typer(name="s09-full-root", cls=CadrumoTyperGroup)

    @root.callback()
    @command_execution_policy(METADATA)
    def root_callback() -> None:
        return None

    parent = LazySubcommand(
        "parent",
        LazyImportTarget(_TARGET),
        child_registry_key="s09-full-parent-target",
    )
    nested = LazySubcommand("nested", LazyImportTarget(_NESTED_TARGET))
    register_lazy_subcommand("s09-full-root", parent)
    register_lazy_subcommand("s09-full-parent-target", nested)

    materialise_lazy_subcommands(root)

    assert parent.is_materialized
    assert nested.is_materialized


def test_duplicate_registration_refuses_instead_of_silently_replacing_target() -> None:
    key = "s09-duplicate-parent"
    first = LazySubcommand("same", LazyImportTarget(_TARGET))
    register_lazy_subcommand(key, first)

    with pytest.raises(ValueError, match="duplicate lazy CLI registration"):
        register_lazy_subcommand(key, LazySubcommand("same", LazyImportTarget(_NESTED_TARGET)))


def test_invalid_target_attribute_refuses_instead_of_falling_back() -> None:
    loader = LazySubcommand("invalid", LazyImportTarget(_TARGET, attribute="missing_app"))

    with pytest.raises(RuntimeError, match="does not exist"):
        loader.load()
