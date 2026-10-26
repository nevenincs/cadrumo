"""Read non-shipped consumers without treating test-only reach as product use."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from dev.first_party_source import is_test_source
from dev.quality.source_import_analysis import (
    module_name_for,
)
from dev.quality.unread_inputs import format_unread_notice

from .unreachable_graph import module_edges, resolved_symbol_uses
from .unreachable_memo import parse_module
from .unreachable_models import ShippedModule, _OutsideUse
from .unreachable_receiver_types import ReceiverTypes, receiver_types
from .unreachable_records import record_member_uses
from .unreachable_references import _references
from .unreachable_tree import ShippedTreeSpec, iter_python_files


def _outside_module_name(path: Path, spec: ShippedTreeSpec) -> str:
    """The dotted name an outside file really has, so its relative imports resolve.

    A file under ``src/`` is named from the source root, so an in-source test
    keeps its true package position and a multi-level ``from ...`` import
    resolves. Anything else is named from the repository root, which gives the
    harness trees their own package position without colliding with the
    shipped package.
    """
    root = spec.src_root if path.is_relative_to(spec.src_root) else spec.repo_root
    return module_name_for(path, src_root=root)


def _outside_use(
    spec: ShippedTreeSpec,
    known: frozenset[str],
    receivers: ReceiverTypes | None = None,
    *,
    modules: Mapping[str, ShippedModule] | None = None,
) -> _OutsideUse:
    use = _OutsideUse()
    probes: list[tuple[ShippedModule, str]] = []
    for corpus in spec.outside:
        for path in iter_python_files(corpus.root):
            if corpus.test_modules_only and not is_test_source(path, root=spec.src_root):
                continue
            try:
                tree = parse_module(path)
            except (OSError, SyntaxError, UnicodeDecodeError) as error:
                # Collect each failure so one unavailable result names the
                # complete set of references the walk could not consult.
                use.unreadable.append(f"{path}: {type(error).__name__}: {error}")
                continue
            label = "tests" if is_test_source(path, root=spec.repo_root) else corpus.label
            for name in _references(tree):
                use.names.setdefault(name, set()).add(label)
            probe = ShippedModule(
                name=_outside_module_name(path, spec),
                path=path,
                is_package=path.name == "__init__.py",
                tree=tree,
            )
            probes.append((probe, label))
    outside_receivers = receiver_types(
        {probe.name: probe for probe, _ in probes}, known_classes=receivers.classes if receivers else frozenset()
    )
    if receivers is not None:
        receivers = ReceiverTypes(
            {**receivers.values, **outside_receivers.values},
            {**receivers.returns, **outside_receivers.returns},
            receivers.classes | outside_receivers.classes,
            {**receivers.fields, **outside_receivers.fields},
            {**receivers.contexts, **outside_receivers.contexts},
            {**receivers.iterables, **outside_receivers.iterables},
        )
    for probe, label in probes:
        runtime, type_only = module_edges(probe, known)
        for target in runtime | type_only:
            use.modules.setdefault(target, set()).add(label)
        for pair in resolved_symbol_uses(probe, known, receivers):
            use.resolved.setdefault(pair, set()).add(label)
    if modules is not None:
        combined = {**modules, **{probe.name: probe for probe, _label in probes}}
        for label in {label for _probe, label in probes} - {"tests"}:
            consumers = frozenset(probe.name for probe, owner in probes if owner == label)
            for pair in record_member_uses(combined, consumers):
                use.resolved.setdefault(pair, set()).add(label)
    if use.unreadable:
        raise OSError(
            format_unread_notice(
                "unreachable-code reference walk",
                "coverage is unproven; references from these files were not consulted",
                use.unreadable,
            ).rstrip()
        )
    return use
