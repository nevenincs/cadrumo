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

import inspect
import sys
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from importlib.util import resolve_name
from typing import Any, Literal, Never, cast, override

import typer
import typer.core as typer_core
from typer._click.core import Command as TyCommand

# Use typer's internal click re-export to align with TyperGroup's type signatures
from typer._click.core import Context as TyContext
from typer._click.core import make_default_short_help

# TyperGroup is built on typer's vendored click, so its resolve_command raises
# the vendored UsageError rather than top-level click's distinct exception.
from typer._click.exceptions import UsageError as TyUsageError
from typer._click.shell_completion import CompletionItem
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



@dataclass(frozen=True, slots=True)
class LazyOptionalDependencyProvider:
    """Deferred access to the canonical optional-dependency inventory."""

    resolve: Callable[[], frozenset[str]]


type LazyOptionalDependencies = frozenset[str] | LazyOptionalDependencyProvider


@dataclass(frozen=True, slots=True)
class LazyImportTarget:
    """One explicit module attribute that owns a deferred Typer node.

    Relative modules must name their import package explicitly. Optional
    dependencies are likewise declared on the target; an arbitrary
    ``ModuleNotFoundError`` is never enough to make a feature optional.
    """

    module: str
    attribute: str = "app"
    package: str | None = None
    optional_dependencies: LazyOptionalDependencies = frozenset()

    def __post_init__(self) -> None:
        if not self.module:
            raise ValueError("a lazy import target requires a module")
        if not self.attribute or "." in self.attribute:
            raise ValueError("a lazy import target requires one public attribute name")
        if self.module.startswith(".") and not self.package:
            raise ValueError("a relative lazy import target requires its package")
        dependencies = self.optional_dependencies
        if isinstance(dependencies, frozenset) and any(
            not dependency or dependency.startswith(".") for dependency in dependencies
        ):
            raise ValueError("optional dependency names must be absolute modules")

    @property
    def owner(self) -> str:
        """Return the stable, import-addressable owner of this target."""
        module = resolve_name(self.module, self.package) if self.module.startswith(".") else self.module
        return f"{module}:{self.attribute}"

    def optional_dependency_names(self) -> frozenset[str]:
        """Resolve the explicit optional-dependency set only after a failure."""
        dependencies = self.optional_dependencies
        return dependencies if isinstance(dependencies, frozenset) else dependencies.resolve()

    def load(self) -> typer.Typer:
        """Import exactly this module and read exactly this attribute."""
        module = import_module(self.module, self.package)
        try:
            target = getattr(module, self.attribute)
        except AttributeError as error:
            raise RuntimeError(f"lazy CLI target {self.owner!r} does not exist") from error
        return _require_typer_target(target, owner=self.owner)


@dataclass(frozen=True, slots=True)
class LazyFactoryTarget:
    """An explicit factory target for a deferred node built at runtime."""

    factory: Callable[[], typer.Typer]
    optional_dependencies: LazyOptionalDependencies = frozenset()

    @property
    def owner(self) -> str:
        """Return the stable Python owner of the factory."""
        return _callable_owner(self.factory)

    def load(self) -> typer.Typer:
        """Build and validate the deferred Typer node."""
        return _require_typer_target(self.factory(), owner=self.owner)

    def optional_dependency_names(self) -> frozenset[str]:
        """Resolve the explicit optional-dependency set only after a failure."""
        dependencies = self.optional_dependencies
        return dependencies if isinstance(dependencies, frozenset) else dependencies.resolve()


type LazyNodeTarget = LazyImportTarget | LazyFactoryTarget
type OptionalUnavailableFactory = Callable[[str, ModuleNotFoundError], typer.Typer]
type RequiredUnavailableRefusal = Callable[[str, ModuleNotFoundError], Never]


def _require_typer_target(target: object, *, owner: str) -> typer.Typer:
    if not isinstance(target, typer.Typer):
        raise RuntimeError(f"lazy CLI target {owner!r} does not expose a Typer app")
    return target


def _dependency_is_explicitly_optional(missing: str, dependencies: frozenset[str]) -> bool:
    """Return whether ``missing`` belongs to one declared optional module."""
    return missing in dependencies


class LazySubcommand:
    """A deferred command node materialized from one explicit target.

    Import targets name their module, package, and public attribute. Dynamic
    factory targets name the callable that constructs the node. The import —
    and therefore the application-layer / registry cost — is paid only when
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

    __slots__ = (
        "_command",
        "_decorate",
        "_help",
        "_hidden",
        "_optional_unavailable",
        "_required_unavailable",
        "_short_help",
        "_target",
        "name",
    )

    def __init__(
        self,
        name: str,
        target: LazyNodeTarget,
        *,
        decorate: Callable[[typer.Typer], None] | None = None,
        optional_unavailable: OptionalUnavailableFactory | None = None,
        required_unavailable: RequiredUnavailableRefusal | None = None,
        help: str | None = None,
        hidden: bool = False,
        short_help: str | None = None,
    ) -> None:
        if not name:
            raise ValueError("a lazy command requires an operator-facing name")
        self.name = name
        self._target = target
        self._decorate = decorate
        self._optional_unavailable = optional_unavailable
        self._required_unavailable = required_unavailable
        self._help = help
        self._hidden = hidden
        self._short_help = short_help
        self._command: TyCommand | None = None

    def load(self) -> TyCommand:
        """Import the module, decorate the Typer, return the Click command.

        The materialized Click command is cached so repeated resolution
        within a single process (help rendering then dispatch, or
        ``resolve_command`` then ``get_command``) imports the module
        exactly once.
        """
        if self._command is None:
            try:
                typer_instance = self._target.load()
            except ModuleNotFoundError as error:
                missing = error.name or str(error).strip() or type(error).__name__
                if _dependency_is_explicitly_optional(missing, self._target.optional_dependency_names()):
                    if self._optional_unavailable is None:
                        raise RuntimeError(
                            f"lazy CLI target {self._target.owner!r} declares optional dependency {missing!r} "
                            "without an unavailable surface"
                        ) from error
                    typer_instance = _require_typer_target(
                        self._optional_unavailable(self.name, error),
                        owner=f"optional-unavailable:{self._target.owner}",
                    )
                elif self._required_unavailable is None:
                    raise
                else:
                    self._required_unavailable(self.name, error)
                    raise RuntimeError("required lazy-target refusal returned instead of raising") from error
            if self._decorate is not None:
                self._decorate(typer_instance)
            command = _typer_get_command(typer_instance)
            command.name = self.name
            self._command = command
        return self._command

    @property
    def loader_owner(self) -> str:
        """Return the stable Python owner of this deferred loader."""
        return self._target.owner

    @property
    def target(self) -> LazyNodeTarget:
        """Expose immutable target metadata without materializing the node."""
        return self._target

    @property
    def is_materialized(self) -> bool:
        """Report cached materialization without importing the target."""
        return self._command is not None

    @property
    def help(self) -> str | None:
        """Return the immutable long-help registration metadata."""
        return self._help

    @property
    def hidden(self) -> bool:
        """Return whether discovery surfaces suppress this node."""
        return self._hidden

    @property
    def short_help(self) -> str | None:
        """Return the immutable explicit short-help metadata, if any."""
        return self._short_help

    def get_short_help_str(self, limit: int = 45) -> str:
        """Render short help with the same rules as Click ``Command``."""
        if self._short_help:
            text = inspect.cleandoc(self._short_help)
        elif self._help:
            text = make_default_short_help(self._help, limit)
        else:
            text = ""
        return text.strip()


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

    Policy is intentionally absent from this Click census. Executable policy
    authority is read from the immutable CommandSpec graph by its consumers.
    """

    path: tuple[str, ...]
    kind: CommandNodeKind
    loader_owner: str | None
    handler_owner: str


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
            )
        )
        if not is_group:
            return

        context = TyContext(command, info_name=path[-1])
        try:
            lazy_table = command._lazy_table() if isinstance(command, CadrumoTyperGroup) else {}
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


def resolve_command_path(
    app: typer.Typer,
    cli_path: tuple[str, ...],
) -> TyCommand:
    """Materialize only the nodes selected by ``cli_path``, token by token.

    Resolution follows Click's real ``get_command`` protocol one token at a
    time without calling ``list_commands``. Registered lazy loaders still own
    their module import boundaries; nested eager registrars remain visible as
    import cost until the command-loading campaign converts them.

    ``cli_path`` excludes the executable token (for example
    ``("config", "profile", "list")``). Missing paths and traversal through a
    leaf fail closed. No sibling loader is inspected or materialized.
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
    return cast(TyCommand, command)


def materialise_lazy_subcommands(app: typer.Typer) -> None:
    """Load every lazily-registered subcommand reachable from ``app``.

    Walks the vendored Click ``list_commands`` / ``get_command`` protocol, the
    same graph dispatch uses. This is deliberately not a walk over Typer's
    ``registered_groups``: a materialized lazy node is a Click child and is not
    inserted back into that Typer-only list. Idempotent, and terminates on a
    cyclic command graph via the identity-seen set.

    A consumer that walks the FULL command tree — a conformance gate, the
    capability projection, a reference generator — must drain the table first,
    or it silently walks a tree missing whole command families and reports
    success while blind to them.

    Args:
        app: Root Typer application whose subtree is materialised in place.
    """
    root = _typer_get_command(app)
    seen: set[int] = set()
    pending: list[TyCommand] = [root]
    while pending:
        command = pending.pop()
        if id(command) in seen:
            continue
        seen.add(id(command))
        if not _is_command_group(command):
            continue
        context = TyContext(command, info_name=command.name)
        try:
            group = cast(Any, command)
            for child_name in group.list_commands(context):
                child = group.get_command(context, child_name)
                if child is not None:
                    pending.append(cast(TyCommand, child))
        finally:
            context.close()


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
      the node-local immutable lazy-child projection
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

    lazy_subcommands: tuple[LazySubcommand, ...] = ()

    def _lazy_table(self) -> dict[str, LazySubcommand]:
        """Project this node's immutable spec-derived lazy children by token."""
        return {child.name: child for child in self.lazy_subcommands}

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
    def format_commands(self, ctx: TyContext, formatter: Any) -> None:
        """Render lazy command rows from registration metadata only.

        Typer's implementation obtains every command object before rendering
        its short help.  That turns a parent ``--help`` into a sibling-handler
        import sweep.  Lazy registrations already own the operator name and
        short-help metadata, so only eager children need concrete resolution.
        """
        lazy = self._lazy_table()
        eager_names = set(super().list_commands(ctx))
        rows: list[tuple[str, str]] = []
        visible_names: list[str] = []
        entries: list[tuple[str, TyCommand | LazySubcommand]] = []
        for name in self.list_commands(ctx):
            declaration = lazy.get(name) if name not in eager_names else None
            if declaration is not None:
                if declaration.hidden:
                    continue
                entries.append((name, declaration))
                visible_names.append(name)
                continue
            command = super().get_command(ctx, name)
            if command is None or command.hidden:
                continue
            entries.append((name, command))
            visible_names.append(name)
        if not entries:
            return
        limit = formatter.width - 6 - max(len(name) for name in visible_names)
        for name, entry in entries:
            if isinstance(entry, LazySubcommand):
                short_help = entry.get_short_help_str(limit)
            else:
                short_help = entry.get_short_help_str(limit)
            rows.append((name, short_help))
        if rows:
            localise = cast(Callable[[str], str], typer_core.__dict__["_"])
            with formatter.section(localise("Commands")):
                formatter.write_dl(rows)

    @override
    def shell_complete(self, ctx: TyContext, incomplete: str) -> list[CompletionItem]:
        """Complete lazy names and descriptions without loading their targets."""
        lazy = self._lazy_table()
        eager_names = set(super().list_commands(ctx))
        results: list[CompletionItem] = []
        for name in self.list_commands(ctx):
            if not name.startswith(incomplete):
                continue
            declaration = lazy.get(name) if name not in eager_names else None
            if declaration is not None:
                if not declaration.hidden:
                    results.append(CompletionItem(name, help=declaration.get_short_help_str()))
                continue
            command = super().get_command(ctx, name)
            if command is not None and not command.hidden:
                results.append(CompletionItem(name, help=command.get_short_help_str()))
        # Command-level option completion does not inspect subcommands.
        results.extend(TyCommand.shell_complete(self, ctx, incomplete))
        return results

    @override
    def get_command(self, ctx: TyContext, cmd_name: str) -> TyCommand | None:
        """Resolve ``cmd_name``, importing a lazy module only if selected.

        Eagerly materialized commands resolve through the base class. A
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
    "LazyFactoryTarget",
    "LazyImportTarget",
    "LazyNodeTarget",
    "LazyOptionalDependencyProvider",
    "LazySubcommand",
    "LiveCommandNode",
    "materialise_lazy_subcommands",
    "resolve_command_path",
    "walk_live_command_tree",
]
