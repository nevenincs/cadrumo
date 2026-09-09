"""Development projections over the immutable production command graph."""

from dataclasses import dataclass
from typing import Any, Literal, cast

import typer
from typer._click.core import Command as TyCommand
from typer._click.core import Context as TyContext
from typer.main import get_command

from cadrumo.entrypoints.cli.command_spec import CommandSpec, CommandSpecNode
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
from cadrumo.entrypoints.cli.command_suggestions import CadrumoTyperGroup


def command_spec_nodes() -> tuple[CommandSpecNode, ...]:
    """Return the path-derived command projection for development tooling."""
    return COMMAND_GRAPH.nodes()


def command_spec_for_path(path: tuple[str, ...]) -> CommandSpec:
    """Resolve one exact operator path for development tooling."""
    return COMMAND_GRAPH.resolve_path(path)


CommandNodeKind = Literal["root", "group", "leaf"]


@dataclass(frozen=True, slots=True)
class LiveCommandNode:
    """One runtime CLI node and its loading/handling owners."""

    path: tuple[str, ...]
    kind: CommandNodeKind
    loader_owner: str | None
    handler_owner: str


def _callable_owner(callback: object | None) -> str:
    if callback is None:
        return "<none>"
    module = getattr(callback, "__module__", type(callback).__module__)
    qualname = getattr(callback, "__qualname__", type(callback).__qualname__)
    return f"{module}:{qualname}"


def _is_command_group(command: object) -> bool:
    return callable(getattr(command, "list_commands", None)) and callable(getattr(command, "get_command", None))


def walk_live_command_tree(app: typer.Typer) -> tuple[LiveCommandNode, ...]:
    """Return every command reachable through Click's live dispatch protocol."""
    root = get_command(app)
    root.name = app.info.name or root.name
    root_token = root.name or "<root>"
    nodes: list[LiveCommandNode] = []

    def visit(command: TyCommand, path: tuple[str, ...], loader_owner: str | None, ancestors: frozenset[int]) -> None:
        if id(command) in ancestors:
            return
        child_ancestors = ancestors | {id(command)}
        is_group = _is_command_group(command)
        nodes.append(
            LiveCommandNode(
                path=path,
                kind="root" if len(path) == 1 else "group" if is_group else "leaf",
                loader_owner=loader_owner,
                handler_owner=_callable_owner(getattr(command, "callback", None)),
            )
        )
        if not is_group:
            return
        context = TyContext(command, info_name=path[-1])
        try:
            lazy_table = command.lazy_table() if isinstance(command, CadrumoTyperGroup) else {}
            group = cast(Any, command)
            for child_name in group.list_commands(context):
                lazy = lazy_table.get(child_name)
                child = group.get_command(context, child_name)
                if child is not None:
                    visit(child, (*path, child_name), lazy.loader_owner if lazy is not None else None, child_ancestors)
        finally:
            context.close()

    visit(root, (root_token,), None, frozenset())
    return tuple(sorted(nodes, key=lambda node: node.path))


def resolve_command_path(app: typer.Typer, cli_path: tuple[str, ...]) -> TyCommand:
    """Materialize only the nodes selected by ``cli_path``."""
    command = get_command(app)
    resolved: list[str] = []
    for token in cli_path:
        if not _is_command_group(command):
            raise LookupError(f"CLI path traverses through a leaf at {' '.join(resolved)!r}")
        context = TyContext(command, info_name=resolved[-1] if resolved else command.name)
        try:
            child = cast(Any, command).get_command(context, token)
        finally:
            context.close()
        if child is None:
            raise LookupError(f"unknown CLI path: {' '.join(cli_path)!r}")
        command = child
        resolved.append(token)
    return cast(TyCommand, command)
