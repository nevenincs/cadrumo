"""Lazy command-family graph loading and exact operator-path resolution."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib import import_module
from types import MappingProxyType
from typing import cast

from ._command_parameter_contracts import OptionSpec, ParameterSpec
from ._command_shared_contracts import DeferredTarget, SchemaState
from ._command_structure_validation import graph_by_key as _graph_by_key
from ._command_structure_validation import graph_by_schema_identity as _graph_by_schema_identity
from ._command_structure_validation import graph_nodes as _graph_nodes
from ._command_structure_validation import validate_graph as _validate_graph
from .command_spec import CommandSpec, CommandSpecNode


@dataclass(frozen=True, slots=True)
class CommandSpecFamily:
    """Specs declared by one module and attached below an already declared node.

    ``mount_key`` names the node whose children the family supplies. The
    family is imported the first time that node's children are needed, so a
    command path only loads the declarations along its own subtree.
    """

    mount_key: str
    source: DeferredTarget

    def load(self) -> tuple[CommandSpec, ...]:
        """Import the declaring module and return its specs in declared order."""
        value: object = import_module(self.source.module)
        for part in self.source.qualname.split("."):
            value = getattr(value, part)
        if isinstance(value, CommandSpec):
            return (value,)
        members: tuple[object, ...] = cast("tuple[object, ...]", value) if isinstance(value, tuple) else ()
        specs = tuple(member for member in members if isinstance(member, CommandSpec))
        if not isinstance(value, tuple) or len(specs) != len(members):
            raise TypeError(f"command spec family {self.source.identity!r} is not a CommandSpec tuple")
        return specs


@dataclass(frozen=True, slots=True)
class CommandSpecGraph:
    """Validated immutable tree assembled from distributed specifications.

    ``declared`` holds the specs available up front; ``families`` supply the
    rest on demand. Subtree queries (:meth:`children`, :meth:`resolve_path`,
    :meth:`spec`, :meth:`node`, :meth:`root`) load only the families they reach, and
    :meth:`find_schema_identity` stops loading once its identity is found. Every
    whole-graph query (:attr:`specs`, :meth:`by_key`, :meth:`nodes`,
    :meth:`by_schema_identity`) loads all families first.
    Each load revalidates the specs loaded so far; the full load validates the
    complete graph.
    """

    declared: tuple[CommandSpec, ...]
    families: tuple[CommandSpecFamily, ...] = ()
    _loaded: dict[int, tuple[CommandSpec, ...]] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        """Validate the declared specs, or raise; families validate as they load."""
        _validate_graph(self.declared)

    def _loaded_specs(self) -> tuple[CommandSpec, ...]:
        rows = list(self.declared)
        for index in range(len(self.families)):
            rows.extend(self._loaded.get(index, ()))
        return tuple(rows)

    def _load_mount(self, key: str) -> None:
        pending = [
            index for index, family in enumerate(self.families) if family.mount_key == key and index not in self._loaded
        ]
        if not pending:
            return
        loaded = {index: self.families[index].load() for index in pending}
        candidate = dict(self._loaded)
        candidate.update(loaded)
        rows = list(self.declared)
        for index in range(len(self.families)):
            rows.extend(candidate.get(index, ()))
        _validate_graph(tuple(rows))
        self._loaded.update(loaded)

    def _loadable_mounts(self) -> tuple[str, ...]:
        """Return, in family declaration order, the unloaded mounts whose node is already loaded."""
        if len(self._loaded) == len(self.families):
            return ()
        loaded_keys = {spec.key for spec in self._loaded_specs()}
        mounts = [
            family.mount_key
            for index, family in enumerate(self.families)
            if index not in self._loaded and family.mount_key in loaded_keys
        ]
        if not mounts:
            missing = sorted(
                {family.mount_key for index, family in enumerate(self.families) if index not in self._loaded}
            )
            raise ValueError(f"command spec families mount at unknown nodes: {missing!r}")
        return tuple(dict.fromkeys(mounts))

    def _load_all(self) -> tuple[CommandSpec, ...]:
        while mounts := self._loadable_mounts():
            for mount in mounts:
                self._load_mount(mount)
        return self._loaded_specs()

    def find_schema_identity(self, identity: str) -> CommandSpecNode | None:
        """Return the node whose targeted result schema is ``identity``.

        Loaded specs are searched first; otherwise families are loaded one
        mount at a time, in declaration order, until the identity appears or
        the graph is complete.
        """
        while True:
            match = next(
                (
                    spec
                    for spec in self._loaded_specs()
                    if spec.result_schema.state is SchemaState.TARGET and spec.result_schema.identity == identity
                ),
                None,
            )
            if match is not None:
                return self.node(match.key)
            mounts = self._loadable_mounts()
            if not mounts:
                return None
            self._load_mount(mounts[0])

    @property
    def specs(self) -> tuple[CommandSpec, ...]:
        """Return every command spec in declaration order, loading all families."""
        return self._load_all()

    def root(self) -> CommandSpec:
        """Return the single root spec, which is always declared up front."""
        return next(spec for spec in self.declared if spec.parent_key is None)

    def children(self, key: str) -> tuple[CommandSpec, ...]:
        """Return the direct children of ``key`` in declaration order."""
        self._load_mount(key)
        return tuple(spec for spec in self._loaded_specs() if spec.parent_key == key)

    def spec(self, key: str) -> CommandSpec:
        """Return the spec for ``key``, loading every family only when it is not yet loaded."""
        for spec in self._loaded_specs():
            if spec.key == key:
                return spec
        found = self.by_key().get(key)
        if found is None:
            raise LookupError(f"unknown command spec key: {key!r}")
        return found

    def node(self, key: str) -> CommandSpecNode:
        """Return ``key``'s spec with its operator path, derived from its loaded ancestors."""
        spec = self.spec(key)
        tokens = [spec.token]
        parent_key = spec.parent_key
        while parent_key is not None:
            parent = self.spec(parent_key)
            tokens.append(parent.token)
            parent_key = parent.parent_key
        return CommandSpecNode(tuple(reversed(tokens)), spec)

    def by_key(self) -> MappingProxyType[str, CommandSpec]:
        """Return every command spec indexed by its key."""
        return _graph_by_key(self.specs)

    def nodes(self) -> tuple[CommandSpecNode, ...]:
        """Return every command spec paired with its derived operator path."""
        return _graph_nodes(self.specs, node_type=CommandSpecNode)

    def resolve_path(self, path: tuple[str, ...]) -> CommandSpec:
        """Resolve one complete operator path, loading only the families along it."""
        root = self.root()
        if not path or path[0] != root.token:
            raise LookupError(f"unknown command spec path: {' '.join(path)!r}")
        current = root
        for token in path[1:]:
            match = next((child for child in self.children(current.key) if child.token == token), None)
            if match is None:
                raise LookupError(f"unknown command spec path: {' '.join(path)!r}")
            current = match
        return current

    def resolve_invocation(self, arguments: Sequence[str]) -> CommandSpec | None:
        """Return the leaf an argument vector would run, read before any parsing, or ``None``.

        Options declared on the node being walked are stepped over with their
        values; the first positional token a leaf receives, or ``--``, ends the
        walk. An undeclared option, an unknown or partial path, or a group
        names no leaf, so a caller relaxing anything for a declared leaf never
        relaxes it for a vector it could not read.
        """
        current = self.root()
        index = 0
        while index < len(arguments):
            argument = arguments[index]
            if argument == "--":
                break
            if argument.startswith("-"):
                name, has_inline_value = argument.split("=", 1)[0], "=" in argument
                option = _invocation_option(current.parameters, name)
                if option is None:
                    return None
                index += _invocation_option_width(option, has_inline_value)
                continue
            if current.kind == "leaf":
                break
            child = next((spec for spec in self.children(current.key) if spec.token == argument), None)
            if child is None:
                return None
            current = child
            index += 1
        return current if current.kind == "leaf" else None

    def by_schema_identity(self) -> MappingProxyType[str, CommandSpec]:
        """Return the unique executable result-schema identity index."""
        return _graph_by_schema_identity(self.specs)


def _invocation_option(parameters: tuple[ParameterSpec, ...], name: str) -> OptionSpec | None:
    """Find the first option declaring the exact spelling in the current node."""
    return next(
        (
            parameter
            for parameter in parameters
            if isinstance(parameter, OptionSpec)
            and name in {part for declaration in parameter.declarations for part in declaration.split("/")}
        ),
        None,
    )


def _invocation_option_width(option: OptionSpec, has_inline_value: bool) -> int:
    """Step over a separate value only when the declared option requires one."""
    takes_value = not (option.is_flag or option.count or has_inline_value)
    return 2 if takes_value else 1
