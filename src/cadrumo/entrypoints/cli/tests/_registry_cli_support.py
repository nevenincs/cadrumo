"""Shared support for registry CLI tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import cache

import typer
from click.testing import Result
from typer.core import TyperGroup

from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.authority import bundled_authority
from ....tests.cli_runner import cadrumo_click_command
from ....tests.cli_runner import invoke_cached_cli as _invoke_cached_cli

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_WORKBOOK_ROOT = bundled_path("corpus", "aeat_official", "disenos_registro")
_BUCKET_ID = "4300e0dd-8359-4cf6-91e4-7cc4befbfac1"  # was 'registry-cli'
_CLI_ENV: dict[str, str] = {}

_ENGLISH_CLI_ENV: Mapping[str, str] = {"CADRUMO_OUTPUT_LANGUAGE": "en"}
"""Request English output. DOES NOT WORK in-process -- kept only as intent.

Measured: setting this variable in ``os.environ`` inside a warm process changes
nothing. ``load_settings`` returns ``_constructed_settings``, an ``lru_cache``
keyed on the active-profile pointer fingerprint alone, so no environment
variable is part of that key and the first-built ``Settings`` wins for the life
of the process. Passing this env to a runner that invokes the CLI IN-PROCESS
therefore leaves BOTH channels at whatever the process already resolved:

* runtime text, because ``output_language()`` reads that cached ``Settings``;
* ``help=`` text, additionally, because ``help=tr(...)`` is evaluated when the
  Typer tree is BUILT and :func:`cadrumo_click_command` caches that tree.

An assertion on localized prose under this env is therefore an assertion
against the ambient language, and is order-dependent -- which is how a
misspelled Spanish alternative once survived: the Spanish branch is the one
that actually runs. Two ways to genuinely control the language:

* runtime text, in-process: ``override_settings(cadrumo_output_language=...)``
  (verified to work for es/ca/hu);
* help text: a SUBPROCESS with the variable in its environment, since a fresh
  process builds both ``Settings`` and the Typer tree under it.

Prefer asserting language-independent structure -- exit codes, option names,
JSON keys -- over prose in either case.
"""


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
    """Resolve a subcommand from the Cadrumo command tree."""

    assert isinstance(group, TyperGroup)
    return group.get_command(typer.Context(group), name)


def _command_path(*path: str) -> object:
    current: object = cadrumo_click_command()
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
    return tuple(sorted(modelo.id for modelo in bundled_authority().modelos))


@cache
def _registry_application_surfaces() -> set[str]:
    return {
        link.surface
        for modelo in bundled_authority().modelos
        for revision in modelo.revisions.values()
        for link in revision.application_links
    }


def _first_registry_modelo() -> str:
    return _registry_modelos()[0]
