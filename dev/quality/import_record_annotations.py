"""Resolve statically named classes inside declaration field annotations."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping


def annotation_classes(
    module: str,
    annotation: ast.AST,
    visiting: frozenset[str],
    reference: Callable[[str, ast.AST], str | None],
    classes: Mapping[str, ast.ClassDef],
    definitions: Mapping[str, ast.AST],
) -> set[str]:
    """Follow known class references and finite type aliases in an annotation."""
    targets: set[str] = set()
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            annotation = ast.parse(annotation.value, mode="eval")
        except SyntaxError:
            return targets
    for node in ast.walk(annotation):
        if not isinstance(node, (ast.Name, ast.Attribute)):
            continue
        resolved = reference(module, node)
        if resolved is None or resolved in visiting:
            continue
        if resolved in classes:
            targets.add(resolved)
        alias = definitions.get(resolved)
        if isinstance(alias, ast.TypeAlias):
            targets.update(
                annotation_classes(
                    resolved.rpartition(".")[0], alias.value, visiting | {resolved}, reference, classes, definitions
                )
            )
    return targets
