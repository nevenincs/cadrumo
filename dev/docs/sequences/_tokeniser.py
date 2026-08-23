"""Build-time command-line tokeniser for ``cli-sequence`` frames.

Highlighting a documented command is correct by construction only if it is
classified against the real command tree, never by client-side bash guessing.
This module tokenises one frame's ``argv`` against the immutable command graph:
each token is classified as the executable, a group verb, a leaf verb, an
option, an option value, a positional argument, or an interpolated ``{name}``
placeholder, and every verb (and option) token carries the command-path key the
browser widget uses to open that path's live ``--help`` from the generated
``cli-tree.json`` projection.

Tokenisation runs in Python at build time against the same immutable graph the
CLI reference uses, so the token grammar and the help catalogue cannot diverge.
The output is a tuple of
strict :class:`CommandToken` records that the ``cli-sequence`` directive turns
into HTML spans and inlines into its per-sequence JSON payload.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from cadrumo.core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

__all__ = [
    "CommandToken",
    "TokenKind",
    "command_path_key",
    "tokenise_command",
]

#: The executable token every frame argv leads with (the sole human CLI verb).
_EXECUTABLE: str = "aeat"

#: A ``{name}`` interpolation token, the placeholder class the parser threads a
#: prior ``@capture`` value into. The inner name matches the schema Identifier.
_PLACEHOLDER_RE = re.compile(r"^\{[A-Za-z_][A-Za-z0-9_]*\}$")


class TokenKind(StrEnum):
    """Closed classification of a token on a ``cli-sequence`` command line."""

    #: The leading ``aeat`` executable.
    EXECUTABLE = "executable"
    #: A verb that resolves to a Click group (a namespace with subcommands).
    GROUP = "group"
    #: A verb that resolves to a Click leaf command (an invokable operation).
    LEAF = "leaf"
    #: An ``--option`` / ``-o`` token (its value, if separate, follows).
    OPTION = "option"
    #: The value token consumed by the preceding value-taking option.
    OPTION_VALUE = "option_value"
    #: A positional argument value.
    ARGUMENT = "argument"
    #: An interpolated ``{name}`` placeholder (a threaded ``@capture`` value).
    PLACEHOLDER = "placeholder"


class CommandToken(BaseModel):
    """One classified token of a rendered ``cli-sequence`` command line.

    ``command_path`` is the space-joined command path the token addresses — set
    on the executable (the root), on every verb token (the path up to and
    including that verb), and on an option token (the owning command's path) —
    so the widget can open that path's live help from ``cli-tree.json``; it is
    ``None`` on option values, positional arguments, and placeholders.
    ``option_name`` carries the written option string on an option and on the
    value it consumes, linking the value back to its option.
    """

    model_config = _STRICT_FROZEN

    text: Annotated[str, StringConstraints(min_length=1)]
    kind: TokenKind
    command_path: str | None = None
    option_name: str | None = None


@dataclass(frozen=True)
class _NodeInfo:
    """The tokeniser's view of one command-tree node."""

    is_group: bool
    children: frozenset[str]
    #: Every declared option string mapped to whether it consumes a value.
    options: Mapping[str, bool]


def command_path_key(path: Sequence[str]) -> str:
    """Return the space-joined command-path key for ``path`` (e.g. ``aeat app modelo calculate``).

    This is the key the widget resolves against the ``cli-tree.json`` help
    projection; it is the full command path as the operator types it, leading
    ``aeat`` included.
    """
    return " ".join(path)


@cache
def _command_tree() -> Mapping[tuple[str, ...], _NodeInfo]:
    """Project the command graph once to a token-classification index."""
    from cadrumo.entrypoints.cli.command_api import OptionSpec, command_spec_nodes

    children: defaultdict[tuple[str, ...], set[str]] = defaultdict(set)
    nodes = command_spec_nodes()
    for node in nodes:
        path = node.path
        if len(path) >= 2:
            children[path[:-1]].add(path[-1])

    index: dict[tuple[str, ...], _NodeInfo] = {}
    for node in nodes:
        path = node.path
        options: dict[str, bool] = {}
        for param in node.spec.parameters:
            if not isinstance(param, OptionSpec):
                continue
            takes_value = not param.is_flag
            for opt in param.declarations:
                options[opt] = takes_value
        index[path] = _NodeInfo(
            is_group=node.spec.kind != "leaf",
            children=frozenset(children.get(path, frozenset())),
            options=options,
        )
    return index


def _is_option_token(token: str) -> bool:
    """Return whether ``token`` is an option flag rather than a value."""
    return len(token) > 1 and token.startswith("-")


def tokenise_command(argv: Sequence[str]) -> tuple[CommandToken, ...]:
    """Classify every token of a frame's ``argv`` against the command graph.

    ``argv`` leads with the ``aeat`` executable and may carry ``{name}``
    placeholder tokens (unresolved, as authored). Verb resolution walks the tree
    from the root: a bare token that names a child of the current group descends
    into it (classified GROUP or LEAF by the child's own node), any other bare
    token is a positional argument, an ``-o``/``--option`` token is an option
    (its separate value, when the option takes one, is the next token unless that
    token is itself a placeholder), and a ``{name}`` token is always a
    placeholder. Classification degrades to ARGUMENT for a token that does not
    resolve against the tree, so an as-yet-unknown verb never raises here.
    """
    if not argv:
        return ()

    tree = _command_tree()
    tokens: list[CommandToken] = []

    current_path: tuple[str, ...] = (_EXECUTABLE,)
    executable_path = current_path if current_path in tree else None
    tokens.append(
        CommandToken(
            text=argv[0],
            kind=TokenKind.EXECUTABLE,
            command_path=command_path_key(current_path) if executable_path is not None else None,
        ),
    )

    index = 1
    while index < len(argv):
        token = argv[index]
        node = tree.get(current_path)

        if _PLACEHOLDER_RE.match(token):
            tokens.append(CommandToken(text=token, kind=TokenKind.PLACEHOLDER))
            index += 1
            continue

        if _is_option_token(token):
            option_key = token.split("=", 1)[0]
            has_inline_value = "=" in token
            takes_value = bool(node and node.options.get(option_key, False))
            tokens.append(
                CommandToken(
                    text=token,
                    kind=TokenKind.OPTION,
                    command_path=command_path_key(current_path),
                    option_name=option_key,
                ),
            )
            index += 1
            if takes_value and not has_inline_value and index < len(argv):
                value = argv[index]
                if _PLACEHOLDER_RE.match(value):
                    tokens.append(CommandToken(text=value, kind=TokenKind.PLACEHOLDER, option_name=option_key))
                else:
                    tokens.append(CommandToken(text=value, kind=TokenKind.OPTION_VALUE, option_name=option_key))
                index += 1
            continue

        if node is not None and node.is_group and token in node.children:
            child_path = (*current_path, token)
            child = tree.get(child_path)
            kind = TokenKind.GROUP if (child is not None and child.is_group) else TokenKind.LEAF
            tokens.append(CommandToken(text=token, kind=kind, command_path=command_path_key(child_path)))
            current_path = child_path
        else:
            tokens.append(CommandToken(text=token, kind=TokenKind.ARGUMENT))
        index += 1

    return tuple(tokens)
