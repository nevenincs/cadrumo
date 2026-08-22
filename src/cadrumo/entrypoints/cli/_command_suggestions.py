"""Command-resolution suggestions and lazy subcommand loading.

Typer's built-in :class:`~typer.core.TyperGroup` suggests a near-miss
command via :func:`~difflib.get_close_matches`. That covers typos
(``overvew`` -> ``overview``) but misses two operator-facing cases:

* **Semantic synonyms** — a different word for the same verb, e.g.
  ``config profile modify`` for ``config profile edit``. The edit
  distance is too large for ``get_close_matches`` to relate them.
* **Cross-path commands** — a command that exists, but under a
  different group, e.g. ``app status`` for ``app overview status``.

:class:`CadrumoTyperGroup` keeps
Typer's typo suggestions and layers a per-group synonym table on top so both
cases produce a translated "did you mean" hint instead of a bare "No such
command".

The same group class also owns **lazy subcommand loading**. The Cadrumo
CLI command tree is wide: every leaf command module pulls the application
layer and, transitively, the ~0.6 s registry parse. Importing the
whole tree just to construct the ``cadrumo`` command app made
``aeat --version`` and ``aeat --help`` pay that cost even though they
never dispatch into a subcommand.

Heavy subcommand groups therefore register a
:class:`LazySubcommand` loader
instead of an eagerly-imported Typer instance. The loader's module is imported
only when
:meth:`CadrumoTyperGroup.get_command`
resolves that subcommand, which happens only when an operator invokes something
in that subtree. ``--version`` / ``--help`` / the bare landing surface
short-circuit in their callbacks before any subcommand is resolved, so they
never trigger a loader.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, cast, override

import typer
from typer._click.core import Command as TyCommand

# Use typer's internal click re-export to align with TyperGroup's type signatures
from typer._click.core import Context as TyContext

# TyperGroup is built on typer's vendored click, so its resolve_command raises
# the vendored UsageError rather than top-level click's distinct exception.
from typer._click.exceptions import UsageError as TyUsageError
from typer.core import TyperGroup
from typer.main import get_command as _typer_get_command

from ...core.i18n import tr
from ._command_policy import CommandExecutionPolicy, execution_policy_for

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
    command module and returns its :class:`~typer.Typer` instance. The
    import — and therefore the application-layer / registry cost — is
    paid only when
    :meth:`LazySubcommand.load`
    runs, which
    :class:`CadrumoTyperGroup`
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

    @property
    def loader_owner(self) -> str:
        """Return the stable Python owner of this deferred loader."""
        return _callable_owner(self._factory)


CommandNodeKind = Literal["root", "group", "leaf"]


@dataclass(frozen=True, slots=True)
class LiveCommandNode:
    """One runtime CLI node with its loading and handling ownership.

    ``path`` includes the executable token so independently collected censuses
    share one canonical namespace. Owners use ``module:qualname`` strings: they
    identify the registration callable that materialises a lazy node and the
    callback that handles the node, while remaining serialisable and stable
    across fresh processes. ``loader_owner`` is ``None`` for an eagerly
    registered node because no runtime loader exists; it never aliases handler
    ownership to conceal that distinction.

    ``execution_policy`` comes only from the node's registered callback.  It is
    ``None`` for an unannotated callback or a non-executing group; the census
    never invents a state-free default or joins a path-keyed policy table.
    """

    path: tuple[str, ...]
    kind: CommandNodeKind
    loader_owner: str | None
    handler_owner: str
    execution_policy: CommandExecutionPolicy | None


def _callable_owner(callback: object | None) -> str:
    """Project a callable to a stable owner string, or ``<none>``."""
    if callback is None:
        return "<none>"
    module = getattr(callback, "__module__", type(callback).__module__)
    qualname = getattr(callback, "__qualname__", type(callback).__qualname__)
    return f"{module}:{qualname}"


def _is_command_group(command: object) -> bool:
    """Recognise a group across Typer's vendored Click type boundary."""
    return callable(getattr(command, "list_commands", None)) and callable(getattr(command, "get_command", None))


def walk_live_command_tree(app: typer.Typer) -> tuple[LiveCommandNode, ...]:
    """Return a stable census of every command reachable from ``app``.

    The walk resolves children through the same ``list_commands`` /
    ``get_command`` protocol used by Click dispatch. Lazy ownership is captured
    before resolution triggers the loader. The returned tuple is sorted by
    operator-facing path, independent of registration or dictionary order.

    Args:
        app: Runtime Typer application to census.

    Returns:
        Immutable command-node records including the root, all groups, and all
        leaves reachable from the runtime tree.
    """
    root = _typer_get_command(app)
    root.name = app.info.name or root.name
    root_token = root.name or "<root>"
    nodes: list[LiveCommandNode] = []

    def visit(
        command: TyCommand,
        path: tuple[str, ...],
        *,
        loader_owner: str | None,
        ancestors: frozenset[int],
    ) -> None:
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
                execution_policy=execution_policy_for(getattr(command, "callback", None)),
            )
        )
        if not is_group:
            return

        context = TyContext(command, info_name=path[-1])
        try:
            lazy_table = _LAZY_REGISTRY.get(command.name or "", {})
            group = cast(Any, command)
            for child_name in group.list_commands(context):
                lazy = lazy_table.get(child_name)
                child = group.get_command(context, child_name)
                if child is None:
                    continue
                owner = lazy.loader_owner if lazy is not None else None
                visit(child, (*path, child_name), loader_owner=owner, ancestors=child_ancestors)
        finally:
            context.close()

    visit(root, (root_token,), loader_owner=None, ancestors=frozenset())
    return tuple(sorted(nodes, key=lambda node: node.path))


def execution_policy_for_cli_path(
    app: typer.Typer,
    cli_path: tuple[str, ...],
) -> CommandExecutionPolicy:
    """Resolve one CLI path and return its callback-attached execution policy.

    Resolution follows Click's real ``get_command`` protocol one token at a
    time without calling ``list_commands``. Registered lazy loaders still own
    their module import boundaries; nested eager registrars remain visible as
    import cost until the command-loading campaign converts them.

    ``cli_path`` excludes the executable token (for example
    ``("config", "profile", "list")``).  Missing paths, traversal through a
    leaf, and unclassified callbacks fail closed instead of manufacturing a
    safe default.
    """
    command = _typer_get_command(app)
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
    policy = execution_policy_for(getattr(command, "callback", None))
    if policy is None:
        raise LookupError(f"CLI path has no execution policy: {' '.join(cli_path)!r}")
    return policy


#: Lazy-subcommand registry keyed by the owning group's command
#: ``name``. Typer materializes the Click
#: :class:`CadrumoTyperGroup`
#: instance lazily, inside ``get_command(app)``; the instance therefore
#: cannot carry its lazy table at app-construction time. Keying by
#: group name lets
#: :func:`register_lazy_subcommand`
#: populate the table
#: at module-import time and lets every materialized group instance of
#: that name read it back. CLI group names (``cadrumo``, ``app``, ``config``)
#: are unique, so the keying is unambiguous.
_LAZY_REGISTRY: dict[str, dict[str, LazySubcommand]] = {}


def register_lazy_subcommand(group_name: str, lazy: LazySubcommand) -> None:
    """Register ``lazy`` under ``group_name`` for deferred resolution.

    The owning
    :class:`CadrumoTyperGroup` imports
    the command module only when the subcommand is first resolved through
    ``get_command``.
    """
    _LAZY_REGISTRY.setdefault(group_name, {})[lazy.name] = lazy


def materialise_lazy_subcommands(app: typer.Typer) -> None:
    """Load every lazily-registered subcommand reachable from ``app``.

    Walks ``app`` and its registered Typer groups, draining
    :data:`_LAZY_REGISTRY` for each group name reached. Idempotent, and
    terminates on a cyclic group graph via the identity-seen set.

    A consumer that walks the FULL command tree — a conformance gate, the
    capability projection, a reference generator — must drain the table first,
    or it silently walks a tree missing whole command families and reports
    success while blind to them.

    Args:
        app: Root Typer application whose subtree is materialised in place.
    """
    seen: set[int] = set()
    pending: list[typer.Typer] = [app]
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        for lazy in _LAZY_REGISTRY.get(node.info.name or "", {}).values():
            lazy.load()
        for group in node.registered_groups:
            if group.typer_instance is not None:
                pending.append(group.typer_instance)


#: ``Context.meta`` key carrying the unparsed invocation remainder
#: (subcommand chain + options) captured before click clears
#: ``ctx.args`` / the protected list ahead of the group-callback run.
#: The root callback's introspection-only gate reads it to decide
#: whether the invocation can only render help or a usage error.
INVOCATION_REMAINDER_META_KEY = "cadrumo.invocation_remainder"


class CadrumoTyperGroup(TyperGroup):
    """:class:`~typer.core.TyperGroup` with synonym hints and lazy loading.

    Three behaviours layer on top of the base Typer group:

    * **Synonym suggestions.** Typo-distance suggestions from the base
      class are preserved; the synonym table only adds a hint when the
      base class produced none.
    * **Lazy subcommands.** Subcommands registered through
      :func:`register_lazy_subcommand`
      import their command module only when first resolved, keeping the
      construction of the ``cadrumo`` command app free of the registry parse.
    * **Remainder capture.** Click empties ``ctx.args`` and the
      protected list before running the group callback, so the callback
      cannot see the tokens that follow the group name.
      :meth:`CadrumoTyperGroup.invoke`
      stashes them in ``ctx.meta`` first (``setdefault`` — the outermost group's
      full remainder wins) so the root callback can recognise help-only and
      unknown-command invocations without re-reading ``sys.argv`` (which is
      meaningless for in-process invocations).
    """

    def _lazy_table(self) -> dict[str, LazySubcommand]:
        """Return the lazy-subcommand table for this group, if any."""
        return _LAZY_REGISTRY.get(self.name or "", {})

    @override
    # KWARGS-ANY-RATIONALE-CLICK-MAIN: click's ``BaseCommand.main`` contract is
    # ``*args: Any, **kwargs: Any`` passthrough; the override forwards verbatim.
    def main(self, *args: Any, standalone_mode: bool = True, **kwargs: Any) -> object:
        """Terminal exception funnel honouring the JSON error contract.

        Typer's standalone ``main`` renders every :class:`~click.ClickException`
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

        raw_argv = kwargs.get("args")
        invocation_argv = list(raw_argv) if raw_argv is not None else sys.argv[1:]
        return run_standalone_with_error_contract(
            lambda: super(CadrumoTyperGroup, self).main(*args, standalone_mode=False, **kwargs),
            argv=invocation_argv,
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
        per-command import happens later, in
        :meth:`CadrumoTyperGroup.get_command`,
        and only for the command actually selected.
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
        except TyUsageError as exc:
            if args:
                hint = _synonym_hint(self.name, args[0])
                if hint is not None and "Did you mean" not in (exc.message or ""):
                    message = (exc.message or "").rstrip(".")
                    raise TyUsageError(f"{message}. {hint}", ctx=exc.ctx) from exc
            raise


def _synonym_hint(group_name: str | None, token: str) -> str | None:
    """Return a translated suggestion for ``token`` under ``group_name``.

    Returns ``None`` when the group declares no synonym table or
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
    "CadrumoTyperGroup",
    "LazySubcommand",
    "LiveCommandNode",
    "execution_policy_for_cli_path",
    "materialise_lazy_subcommands",
    "register_lazy_subcommand",
    "walk_live_command_tree",
]
