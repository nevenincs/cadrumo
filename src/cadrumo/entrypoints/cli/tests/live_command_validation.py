"""Validate a cited ``aeat`` invocation against the live CLI command tree.

The one validator every command-citation gate shares: documented commands,
the CLI's own hint strings, operator-instruction surfaces, and the argv tuples
the acceptance harness hands to an installed ``aeat``. Each caller decomposes
its own source into a :class:`CitedCommand`; this module owns what "resolves in
the live CLI" means.

Resolution walks the *materialized* Typer/click tree in process (no shell-out),
which triggers the lazy-subcommand loaders, so a verb or option that exists
only in a stale document or a stale harness script cannot pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import cast

import click

from .cli_runner import cadrumo_click_command


@cache
def live_root_command() -> click.Command:
    """Materialize the live ``cadrumo`` click command (root of the tree)."""
    return cadrumo_click_command()


@cache
def live_root_option_names() -> frozenset[str]:
    """Long/short option strings declared on the root callback.

    Root-global options (``--language`` / ``--format`` / ``--profile`` /
    ``--help`` / etc.) are accepted before the command path, so option validity
    unions them with the resolved command's own params.
    """
    return command_option_names(live_root_command())


@dataclass(frozen=True)
class ResolvedCommandPath:
    """Resolution outcome for a cited verb path."""

    command: click.Command | None
    # The verb path that resolved (may be a prefix of the cited tokens when
    # trailing tokens are arguments rather than subcommands).
    resolved_path: tuple[str, ...]


def resolve_path(tokens: tuple[str, ...]) -> ResolvedCommandPath:
    """Walk the live tree for the longest verb prefix of ``tokens``.

    Returns the deepest command reachable by treating leading tokens as
    subcommand names. Resolution stops at the first token that is not a
    subcommand of the current group (that token and the rest are arguments).
    """
    cmd: click.Command = live_root_command()
    ctx = click.Context(cmd, info_name="aeat")
    resolved: list[str] = []
    for tok in tokens:
        if not hasattr(cmd, "list_commands"):
            break
        # ``list_commands`` is the structural group marker; the vendored
        # TyperGroup is not a guaranteed upstream ``click.Group`` subclass, so
        # narrow by interface (cast) rather than isinstance to stay
        # vendor-robust while exposing ``get_command`` to the checker.
        group = cast(click.Group, cmd)
        sub = group.get_command(ctx, tok)
        if sub is None:
            break
        ctx = click.Context(sub, info_name=tok, parent=ctx)
        cmd = sub
        resolved.append(tok)
    return ResolvedCommandPath(command=cmd, resolved_path=tuple(resolved))


def command_option_names(cmd: click.Command) -> frozenset[str]:
    """Long/short option strings (including ``--no-*`` secondaries) declared on ``cmd``."""
    names: set[str] = set()
    for param in cmd.params:
        if getattr(param, "param_type_name", None) == "option":
            names.update(param.opts)
            names.update(param.secondary_opts)
    return frozenset(names)


def value_consuming_option_names(cmd: click.Command) -> frozenset[str]:
    """Option strings on ``cmd`` that consume a following value token.

    A boolean flag (``--force`` / ``--no-force``) or a counting option
    (``-v -v``) takes no value; every other option consumes the next token as
    its value. Knowing this set for the *resolved* command lets the
    dead-subcommand check tell an option value (``--layout plugin``) apart from
    a subcommand name — a caller's string parser cannot, because it runs before
    the command is known.
    """
    names: set[str] = set()
    for param in cmd.params:
        if getattr(param, "param_type_name", None) != "option":
            continue
        if getattr(param, "is_flag", False) or getattr(param, "count", False):
            continue
        names.update(param.opts)
        names.update(param.secondary_opts)
    return frozenset(names)


def option_value_tokens(tokens: tuple[str, ...], value_consuming: frozenset[str]) -> set[str]:
    """Tokens in ``tokens`` consumed as the value of a value-consuming option.

    Walks the ordered stream and, for each cited value-consuming option written
    without an inline ``=value``, marks the next token as its value. Used to
    exclude an option value from the dead-subcommand check.
    """
    consumed: set[str] = set()
    expect_value = False
    for tok in tokens:
        if expect_value:
            consumed.add(tok)
            expect_value = False
            continue
        if tok.startswith("-") and tok != "-":
            name = tok.split("=", 1)[0]
            if "=" not in tok and name in value_consuming:
                expect_value = True
    return consumed


def required_positional_count(cmd: click.Command) -> int:
    """Number of required, non-variadic positional arguments on ``cmd``."""
    count = 0
    for param in cmd.params:
        if getattr(param, "param_type_name", None) == "argument" and param.required and param.nargs != -1:
            count += 1
    return count


@dataclass(frozen=True)
class CitedCommand:
    """A single cited ``aeat`` invocation, decomposed for validation."""

    raw: str
    verb_tokens: tuple[str, ...]
    cited_options: tuple[str, ...]
    # True when at least one non-flag token follows the verb path (a value or
    # a placeholder) — used to evaluate the missing-required-positional check.
    has_positional_token: bool
    # The full ordered token stream after the executable token (verb tokens,
    # options, option values, positionals), preserved so the dead-subcommand
    # check can consult the resolved command's value-consuming options and tell
    # an option *value* apart from a subcommand. Defaults to empty for directly
    # constructed fixtures, which exercise the option-name and verb-resolution
    # paths that do not need the ordered stream.
    tokens: tuple[str, ...] = ()


def split_verb_and_positionals(cited: CitedCommand) -> tuple[ResolvedCommandPath, tuple[str, ...]]:
    """Resolve the verb path, returning the leftover (positional) verb tokens."""
    resolved = resolve_path(cited.verb_tokens)
    leftover = cited.verb_tokens[len(resolved.resolved_path) :]
    return resolved, leftover


def validate_cited_command(cited: CitedCommand) -> list[str]:
    """Return human-readable violations for a single cited command.

    Three checks, in order: (a) the leading verb tokens resolve to a real
    command; (b) every cited option is a parameter of the resolved command or a
    root-global option; (c) a leftover verb token under a resolved GROUP that is
    not the value of a value-consuming option is a dead subcommand.

    Missing-required-positional is deliberately NOT enforced: narrative
    citations legitimately name a leaf by its bare verb, and a rule that
    flagged that shape produces systematic false positives.
    """
    violations: list[str] = []
    resolved, leftover = split_verb_and_positionals(cited)
    cmd = resolved.command
    if cmd is None or not resolved.resolved_path:
        violations.append(f"command path does not resolve in the live CLI: `{cited.raw}`")
        return violations

    # (b) Option validity: every cited option must be a param of the resolved
    # command or a root-global option.
    valid_options = command_option_names(cmd) | live_root_option_names()
    for opt in cited.cited_options:
        if opt not in valid_options:
            violations.append(
                f"`{cited.raw}` cites option `{opt}`, which is not a parameter of "
                f"`aeat {' '.join(resolved.resolved_path)}` (nor a global option)",
            )

    # (c) Dead subcommand of a live group: longest-prefix resolution stops at
    # the deepest reachable command and treats the rest as "arguments", but a
    # GROUP takes no positional arguments — a leftover verb token under a
    # group can only be a subcommand name that does not exist (the shape that
    # let `aeat app ledger payable-invoice` pass while uninvokable after the
    # invoice unification rename). A leftover token that is really the *value*
    # of a value-consuming option on the resolved group (`aeat app quickfile
    # --modelo 130`) is NOT a dead subcommand: a string parser cannot know
    # the group's options, so it over-collects the value into the verb path;
    # exclude those values by consulting the resolved command's real params.
    if hasattr(cmd, "list_commands") and leftover:
        value_consuming = value_consuming_option_names(cmd) | value_consuming_option_names(live_root_command())
        option_values = option_value_tokens(cited.tokens, value_consuming)
        dead = [tok for tok in leftover if tok not in option_values]
        if dead:
            violations.append(
                f"`{cited.raw}` cites `{dead[0]}`, which is not a subcommand of "
                f"the group `aeat {' '.join(resolved.resolved_path)}`",
            )
            return violations

    return violations
