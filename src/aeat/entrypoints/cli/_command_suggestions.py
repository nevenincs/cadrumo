"""Command-resolution suggestions and lazy subcommand loading.

Typer's built-in :class:`~typer.core.TyperGroup` suggests a near-miss
command via :func:`difflib.get_close_matches`. That covers typos
(``overvew`` -> ``overview``) but misses two operator-facing cases:

* **Semantic synonyms** — a different word for the same verb, e.g.
  ``config profile modify`` for ``config profile edit``. The edit
  distance is too large for ``get_close_matches`` to relate them.
* **Cross-path commands** — a command that exists, but under a
  different group, e.g. ``app status`` for ``app overview status``.

:class:`AeatTyperGroup` keeps Typer's typo suggestions and layers a
per-group synonym table on top so both cases produce a translated
"did you mean" hint instead of a bare "No such command".

The same group class also owns **lazy subcommand loading**. The AEAT
command tree is wide: every leaf command module pulls the application
layer and, transitively, the ~0.6 s registry parse. Importing the
whole tree just to construct the ``aeat`` app object made
``aeat --version`` and ``aeat --help`` pay that cost even though they
never dispatch into a subcommand.

Heavy subcommand groups therefore register a :class:`LazySubcommand`
loader instead of an eagerly-imported Typer instance. The loader's
module is imported only when :meth:`AeatTyperGroup.get_command`
resolves that subcommand — i.e. only when an operator actually invokes
something in that subtree. ``--version`` / ``--help`` / the bare
landing surface short-circuit in their callbacks before any subcommand
is resolved, so they never trigger a loader.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import override

import click
import typer
from typer._click.core import Command as TyCommand

# Use typer's internal click re-export to align with TyperGroup's type signatures
from typer._click.core import Context as TyContext

# TyperGroup is built on typer's vendored click, so its resolve_command raises
# the vendored UsageError — a distinct class that is NOT a subclass of the
# top-level ``click.UsageError``. The synonym-hint catch must name both.
from typer._click.exceptions import UsageError as TyUsageError
from typer.core import TyperGroup
from typer.main import get_command as _typer_get_command

from ...core.i18n import tr

#: Per-group synonym tables keyed by the group's command ``name``.
#: Each inner mapping projects an unknown command token onto the
#: canonical command path an operator most likely intended.
_COMMAND_SYNONYMS: dict[str, dict[str, str]] = {
    "profile": {
        "modify": "edit",
        "update": "edit",
        "change": "edit",
        "remove": "delete",
    },
    "app": {
        "status": "overview status",
        "overview-status": "overview status",
    },
}


class LazySubcommand:
    """A deferred subcommand: a Typer factory imported on first use.

    ``factory`` is a zero-argument callable that imports the owning
    command module and returns its :class:`typer.Typer` instance. The
    import — and therefore the application-layer / registry cost — is
    paid only when :meth:`load` runs, which :class:`AeatTyperGroup`
    triggers on the first ``get_command`` / ``list_commands`` access.

    ``decorate`` is applied to the Typer instance before it is
    converted to a Click command. The CLI error boundary
    (``decorate_typer_app``) is wired this way: an eagerly-registered
    subtree would be decorated at app-construction time, but a lazily
    loaded one must be decorated at load time instead.
    """

    __slots__ = ("_command", "_decorate", "_factory", "name")

    def __init__(
        self,
        name: str,
        factory: Callable[[], typer.Typer],
        *,
        decorate: Callable[[typer.Typer], None] | None = None,
    ) -> None:
        self.name = name
        self._factory = factory
        self._decorate = decorate
        self._command: TyCommand | None = None

    def load(self) -> TyCommand:
        """Import the module, decorate the Typer, return the Click command.

        The materialized Click command is cached so repeated resolution
        within a single process (help rendering then dispatch, or
        ``resolve_command`` then ``get_command``) imports the module
        exactly once.
        """
        if self._command is None:
            typer_instance = self._factory()
            if self._decorate is not None:
                self._decorate(typer_instance)
            command = _typer_get_command(typer_instance)
            command.name = self.name
            self._command = command
        return self._command


#: Lazy-subcommand registry keyed by the owning group's command
#: ``name``. Typer materializes the Click :class:`AeatTyperGroup`
#: instance lazily, inside ``get_command(app)``; the instance therefore
#: cannot carry its lazy table at app-construction time. Keying by
#: group name lets :func:`register_lazy_subcommand` populate the table
#: at module-import time and lets every materialized group instance of
#: that name read it back. AEAT group names (``aeat``, ``app``,
#: ``config``) are unique, so the keying is unambiguous.
_LAZY_REGISTRY: dict[str, dict[str, LazySubcommand]] = {}


def register_lazy_subcommand(group_name: str, lazy: LazySubcommand) -> None:
    """Register ``lazy`` under ``group_name`` for deferred resolution.

    The owning :class:`AeatTyperGroup` imports the command module only
    when the subcommand is first resolved through ``get_command``.
    """
    _LAZY_REGISTRY.setdefault(group_name, {})[lazy.name] = lazy


#: ``Context.meta`` key carrying the unparsed invocation remainder
#: (subcommand chain + options) captured before click clears
#: ``ctx.args`` / the protected list ahead of the group-callback run.
#: The root callback's introspection-only gate reads it to decide
#: whether the invocation can only render help or a usage error.
INVOCATION_REMAINDER_META_KEY = "aeat.invocation_remainder"


class AeatTyperGroup(TyperGroup):
    """:class:`TyperGroup` with synonym hints and lazy subcommand loading.

    Three behaviours layer on top of the base Typer group:

    * **Synonym suggestions.** Typo-distance suggestions from the base
      class are preserved; the synonym table only adds a hint when the
      base class produced none.
    * **Lazy subcommands.** Subcommands registered through
      :func:`register_lazy_subcommand` import their command module only
      when first resolved, keeping the construction of the ``aeat`` app
      object free of the registry parse.
    * **Remainder capture.** Click empties ``ctx.args`` and the
      protected list before running the group callback, so the callback
      cannot see the tokens that follow the group name. :meth:`invoke`
      stashes them in ``ctx.meta`` first (``setdefault`` — the outermost
      group's full remainder wins) so the root callback can recognise
      help-only and unknown-command invocations without re-reading
      ``sys.argv`` (which is meaningless for in-process invocations).
    """

    def _lazy_table(self) -> dict[str, LazySubcommand]:
        """Return the lazy-subcommand table for this group, if any."""
        return _LAZY_REGISTRY.get(self.name or "", {})

    @override
    # KWARGS-ANY-RATIONALE-CLICK-MAIN: click's ``BaseCommand.main`` contract is
    # ``*args: Any, **kwargs: Any`` passthrough; the override forwards verbatim.
    def main(self, *args: object, standalone_mode: bool = True, **kwargs: object) -> object:
        """Terminal exception funnel honouring the JSON error contract.

        Typer's standalone ``main`` renders every :class:`ClickException`
        (usage errors, bad parameters) as Rich text and lets unexpected
        exceptions escape as raw tracebacks — so under ``--format json``
        the shared-spine error document never appeared on any parse-time
        or crash failure. Run the underlying dispatch non-standalone and
        re-implement the terminal handling with a JSON-aware branch (see
        :mod:`._terminal_errors`): usage errors keep their Click exit
        codes but emit the shared-spine error document when JSON is
        requested; unexpected exceptions become the structured crash
        boundary instead of a raw traceback.
        """
        if not standalone_mode:
            return super().main(*args, standalone_mode=False, **kwargs)
        from ._terminal_errors import run_standalone_with_error_contract

        return run_standalone_with_error_contract(
            lambda: super(AeatTyperGroup, self).main(*args, standalone_mode=False, **kwargs),
        )

    @override
    def invoke(self, ctx: TyContext) -> object:
        """Stash the unparsed remainder in ``ctx.meta``, then dispatch.

        Captured before the base implementation clears ``ctx.args`` /
        the protected list ahead of the group-callback run, so the root
        callback's introspection-only gate can inspect the full token
        stream the operator typed after the group name.
        """
        remainder = [*getattr(ctx, "_protected_args", ()), *ctx.args]
        ctx.meta.setdefault(INVOCATION_REMAINDER_META_KEY, remainder)
        return super().invoke(ctx)

    @override
    def list_commands(self, ctx: TyContext) -> list[str]:
        """Return eager and lazy subcommand names without importing modules.

        Help rendering and shell completion enumerate command names
        through this method; returning the lazy names from the registry
        keeps the listing complete without paying any import cost. The
        per-command import happens later, in :meth:`get_command`, and
        only for the command actually selected.
        """
        eager = super().list_commands(ctx)
        lazy = self._lazy_table()
        merged = [*eager, *(name for name in lazy if name not in eager)]
        return sorted(merged)

    @override
    def get_command(self, ctx: TyContext, cmd_name: str) -> TyCommand | None:
        """Resolve ``cmd_name``, importing a lazy module only if selected.

        Eagerly-registered commands resolve through the base class. A
        lazy subcommand triggers its loader — importing the command
        module and the application layer it pulls — exactly once, the
        first time that subtree is dispatched into.
        """
        eager = super().get_command(ctx, cmd_name)
        if eager is not None:
            return eager
        lazy = self._lazy_table().get(cmd_name)
        if lazy is not None:
            return lazy.load()
        return None

    @override
    def resolve_command(
        self,
        ctx: TyContext,
        args: list[str],
    ) -> tuple[str | None, TyCommand | None, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except (click.UsageError, TyUsageError) as exc:
            if args:
                hint = _synonym_hint(self.name, args[0])
                if hint is not None and "Did you mean" not in (exc.message or ""):
                    message = (exc.message or "").rstrip(".")
                    exc.message = f"{message}. {hint}"
            raise


def _synonym_hint(group_name: str | None, token: str) -> str | None:
    """Return a translated suggestion for ``token`` under ``group_name``.

    Returns :data:`None` when the group declares no synonym table or
    the token is not a known synonym.
    """
    if group_name is None:
        return None
    table = _COMMAND_SYNONYMS.get(group_name)
    if table is None:
        return None
    canonical = table.get(token.strip().lower())
    if canonical is None:
        return None
    return tr("cli.root.errors.did_you_mean_command", command=canonical)


__all__ = [
    "INVOCATION_REMAINDER_META_KEY",
    "AeatTyperGroup",
    "LazySubcommand",
    "register_lazy_subcommand",
]
