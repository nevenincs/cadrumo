"""Shared support for registry CLI tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import cache

import typer
from click.testing import Result
from typer.core import TyperGroup

from ....core.resources import bundled_path, resources
from ....tests.cli_runner import aeat_click_command
from ....tests.cli_runner import invoke_cached_cli as _invoke_cached_cli

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_WORKBOOK_ROOT = bundled_path("corpus", "aeat_official", "disenos_registro")
_BUCKET_ID = "registry-cli"
_CLI_ENV: dict[str, str] = {}
_ENGLISH_CLI_ENV: Mapping[str, str] = {"AEAT_OUTPUT_LANGUAGE": "en"}


def _set_cli_env(env: Mapping[str, str]) -> None:
    global _CLI_ENV

    _CLI_ENV = dict(env)


def _clear_cli_env() -> None:
    global _CLI_ENV

    _CLI_ENV = {}


def invoke_cached_cli(args: Sequence[str], *, env: Mapping[str, str] | None = None) -> Result:
    merged_env = {**_CLI_ENV, **dict(env or {})}
    return _invoke_cached_cli(args, env=merged_env)


def _child(group: object, name: str):
    """Resolve a subcommand from the AEAT command tree."""

    assert isinstance(group, TyperGroup)
    return group.get_command(typer.Context(group), name)


def _command_path(*path: str) -> object:
    current: object = aeat_click_command()
    for segment in path:
        current = _child(current, segment)
        assert current is not None, f"missing command path {' '.join(path)}"
    return current


def _command_tree_paths(group: TyperGroup, *, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    ctx = typer.Context(group)
    paths: set[tuple[str, ...]] = set()
    for name in group.list_commands(ctx):
        child = group.get_command(ctx, name)
        path = (*prefix, name)
        paths.add(path)
        if isinstance(child, TyperGroup):
            paths.update(_command_tree_paths(child, prefix=path))
    return paths


@cache
def _registry_modelos() -> tuple[str, ...]:
    return tuple(sorted(modelo.id for modelo in resources().modelos.all()))


@cache
def _registry_application_surfaces() -> set[str]:
    return {
        link.surface
        for modelo in resources().modelos.all()
        for revision in modelo.revisions.values()
        for link in revision.application_links
    }


def _first_registry_modelo() -> str:
    return _registry_modelos()[0]
