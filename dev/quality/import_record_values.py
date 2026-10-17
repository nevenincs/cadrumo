"""Finite string values and constructor module normalization."""

from __future__ import annotations

import ast

from .import_module_syntax import resolve_from
from .import_record_index import DeclarationIndex
from .import_record_models import SourceExpression


class DeclarationValues(DeclarationIndex):
    """Trace finite declaration values without executing product code."""

    def _record_type_branch(self, expression: SourceExpression) -> ast.expr:
        node = expression.node
        if not isinstance(node, ast.IfExp) or not isinstance(node.test, ast.Call):
            raise ValueError("unsupported declaration condition")
        test = node.test
        if not isinstance(test.func, ast.Name) or test.func.id != "isinstance" or len(test.args) != 2:
            raise ValueError("unsupported declaration type guard")
        expected = self.reference(expression.module, test.args[1])
        sources = self._expand(SourceExpression(expression.module, test.args[0], expression.bindings), (), frozenset())
        matched: set[bool] = set()
        for source in sources:
            if isinstance(source.node, ast.Constant):
                matched.add(False)
            elif isinstance(source.node, ast.Call):
                matched.add(self.constructor_reference(source) == expected)
            else:
                raise ValueError("unknown guarded declaration")
        if len(matched) != 1:
            raise ValueError("mixed declaration type guard")
        return node.body if True in matched else node.orelse

    def _strings(self, expression: SourceExpression) -> frozenset[str] | None:
        node = expression.node
        if isinstance(node, ast.Name) and node.id in expression.bindings:
            values = [self._strings(value) for value in expression.bindings[node.id]]
            return (
                frozenset(value for group in values if group is not None for value in group)
                if all(group is not None for group in values)
                else None
            )
        if isinstance(node, ast.Name) and node.id == "__package__":
            module = self.modules[expression.module]
            return frozenset({module.name if module.is_package else module.name.rpartition(".")[0]})
        if (
            isinstance(node, ast.IfExp)
            and isinstance(node.test, ast.Call)
            and isinstance(node.test.func, ast.Attribute)
            and node.test.func.attr == "startswith"
            and len(node.test.args) == 1
        ):
            values = self._strings(SourceExpression(expression.module, node.test.func.value, expression.bindings))
            prefixes = self._strings(SourceExpression(expression.module, node.test.args[0], expression.bindings))
            if values is None or prefixes is None:
                return None
            conditions = {value.startswith(prefix) for value in values for prefix in prefixes}
            if len(conditions) != 1:
                return None
            branch = node.body if True in conditions else node.orelse
            return self._strings(SourceExpression(expression.module, branch, expression.bindings))
        if isinstance(node, ast.Attribute):
            sources = self._expand(expression, (), frozenset())
            values = [self._strings(source) for source in sources]
            return (
                frozenset(value for group in values if group is not None for value in group)
                if all(group is not None for group in values)
                else None
            )
        if isinstance(node, ast.Subscript):
            return self._dictionary_strings(expression)
        return self.context(expression.module).values_for(node, getattr(node, "lineno", 1))

    def _dictionary_strings(self, expression: SourceExpression) -> frozenset[str] | None:
        node = expression.node
        if not isinstance(node, ast.Subscript):
            return None
        keys = self._strings(SourceExpression(expression.module, node.slice, expression.bindings))
        if keys is None:
            return None
        mappings = self._expand(SourceExpression(expression.module, node.value, expression.bindings), (), frozenset())
        targets: set[str] = set()
        for mapping in mappings:
            if not isinstance(mapping.node, ast.Dict):
                return None
            resolved: set[str] = set()
            for key, value in zip(mapping.node.keys, mapping.node.values, strict=True):
                if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                    return None
                if key.value in keys:
                    values = self._strings(SourceExpression(mapping.module, value, mapping.bindings))
                    if values is None:
                        return None
                    targets.update(values)
                    resolved.add(key.value)
            if resolved != set(keys):
                return None
        return frozenset(targets)

    def _record_modules(self, expression: SourceExpression) -> frozenset[str]:
        value = self._argument(expression, "module")
        values = self._strings(value) if value is not None else None
        if values is None or not values:
            raise ValueError(f"unknown module constructor value in {expression.module}")
        targets: set[str] = set()
        for target in values:
            if target.startswith(".") and self.normalizes_module(expression):
                package = self._argument(expression, "package")
                packages = self._strings(package) if package is not None else None
                if packages is None or len(packages) != 1:
                    raise ValueError(f"unknown relative package in {expression.module}")
                level = len(target) - len(target.lstrip("."))
                resolved = resolve_from(next(iter(packages)), True, level, target[level:] or None)
                if resolved is None:
                    raise ValueError("invalid relative package")
                target = resolved
            targets.add(target)
        return frozenset(targets)
