"""Consumer-only Python trees for the subordinate import checker.

Python outside the declared roots -- build hooks, packaging generators, native
bundle scripts and the repository's pytest root configuration -- imports
first-party code without being an importable package of its own.  Import
Linter cannot graph it, so the authority declares each such repository-root
tree, and the checker parses its files as consumer-only modules: nothing may
import them, so only their outgoing imports are governed.

A consumer module is named by its repository-relative path.  That spelling is
never a dotted first-party identity, so a consumer can neither shadow a root
module nor be mistaken for a descendant of the package whose private names it
reaches.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping, Sequence

from .import_authority import repository_python_files
from .import_check_models import Authority, Finding, SourceModule
from .import_dynamic_aliases import DYNAMIC_TARGET_KEYWORDS, dynamic_aliases
from .import_module_syntax import matches_any_module
from .import_target_evaluation import TargetEvaluationContext


def consumer_source_files(authority: Authority) -> tuple[str, ...]:
    """Return every policy-included Python file in the declared consumer trees, repository-relative."""
    return tuple(
        sorted(
            {
                relative
                for tree in authority.consumer_trees
                for relative in repository_python_files(authority.repository, tree.path)
            }
        )
    )


def check_consumer_contracts(
    authority: Authority, modules: Mapping[str, SourceModule], findings: list[Finding]
) -> None:
    """Hold consumer paths to the forbidden modules of the contracts bound to them.

    Every import form counts, as it does for Import Linter: function-local,
    ``TYPE_CHECKING``-guarded and finite dynamic targets alike.  A dynamic
    target the evaluator cannot close is already a hard finding of the dynamic
    checks, so an unresolved call cannot hide a forbidden reach here.
    """
    for scope in authority.consumer_contracts:
        for module in modules.values():
            if not module.consumer or not _within(module.name, scope.paths):
                continue
            for lineno, target in _reached_targets(module):
                if matches_any_module(target, scope.contract.forbidden_modules):
                    findings.append(
                        Finding(
                            "CONSUMER_CONTRACT",
                            f"{module.name!r} reaches {target!r}, forbidden by {scope.contract.name!r}",
                            module.path,
                            lineno,
                        )
                    )


def _within(name: str, paths: Sequence[str]) -> bool:
    """Whether the consumer path ``name`` lies at or below one bound path."""
    return any(name == path or name.startswith(f"{path}/") for path in paths)


def _reached_targets(module: SourceModule) -> Iterator[tuple[int, str]]:
    """Yield every absolute static and finite dynamic module target in ``module``."""
    aliases = dynamic_aliases(module)
    context: TargetEvaluationContext | None = None
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            yield node.lineno, node.module
        elif isinstance(node, ast.Call):
            kind = aliases.loader_kind(node)
            if kind is None:
                continue
            target = (
                node.args[0]
                if node.args
                else next(
                    (keyword.value for keyword in node.keywords if keyword.arg == DYNAMIC_TARGET_KEYWORDS[kind]),
                    None,
                )
            )
            if context is None:
                context = TargetEvaluationContext(module.tree, module.name)
            for value in sorted(context.values_for(target, node.lineno) or ()):
                yield node.lineno, value
