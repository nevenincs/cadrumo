"""Read non-shipped consumers without treating test-only reach as product use."""

from __future__ import annotations

import sys
from pathlib import Path

from dev.first_party_source import is_test_source
from dev.quality.source_import_analysis import (
    module_name_for,
)

from .unreachable_graph import module_edges, resolved_symbol_uses
from .unreachable_memo import parse_module
from .unreachable_models import ShippedModule, _OutsideUse
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


def _outside_use(spec: ShippedTreeSpec, known: frozenset[str]) -> _OutsideUse:
    use = _OutsideUse()
    for corpus in spec.outside:
        for path in iter_python_files(corpus.root):
            if corpus.test_modules_only and not is_test_source(path, root=spec.src_root):
                continue
            try:
                tree = parse_module(path)
            except (OSError, SyntaxError, UnicodeDecodeError):
                # The tree can move under a long scan; a file that is gone or
                # unreadable is skipped rather than crashing the audit, but it
                # is recorded so the report can say the corpus was incomplete.
                use.unreadable.append(str(path))
                continue
            for name in _references(tree):
                use.names.setdefault(name, set()).add(corpus.label)
            probe = ShippedModule(
                name=_outside_module_name(path, spec),
                path=path,
                is_package=path.name == "__init__.py",
                tree=tree,
            )
            runtime, type_only = module_edges(probe, known)
            for target in runtime | type_only:
                use.modules.setdefault(target, set()).add(corpus.label)
            for pair in resolved_symbol_uses(probe, known):
                use.resolved.setdefault(pair, set()).add(corpus.label)
    if use.unreadable:
        # Reported at the point of loss rather than folded into the findings.
        # These files' references were never read, so any symbol only THEY use
        # is about to be reported as dead. A reviewer needs to know the corpus
        # was incomplete before acting on a deletion list.
        sys.stderr.write(
            f"unreachable-code: {len(use.unreadable)} file(s) were unreadable during the "
            "reference walk and did not contribute references; findings over symbols they "
            f"use may be false: {sorted(use.unreadable)}" + chr(10)
        )
    return use
