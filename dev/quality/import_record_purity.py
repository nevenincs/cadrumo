"""Pure classmethod recognition for declaration factory provenance."""

from __future__ import annotations

import ast


def pure_record_classmethod(definition: ast.AST | None) -> bool:
    """Prove a classmethod only constructs its class from call-free arguments."""
    if not isinstance(definition, ast.FunctionDef):
        return False
    if len(definition.decorator_list) != 1 or not isinstance(definition.decorator_list[0], ast.Name):
        return False
    if definition.decorator_list[0].id != "classmethod":
        return False
    statements = [item for item in definition.body if not _docstring(item)]
    if len(statements) != 1 or not isinstance(statements[0], ast.Return):
        return False
    value = statements[0].value
    return _constructs_class(value)


def _constructs_class(value: ast.expr | None) -> bool:
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name) or value.func.id != "cls":
        return False
    return all(
        not isinstance(item, ast.Call)
        for argument in (*value.args, *(item.value for item in value.keywords))
        for item in ast.walk(argument)
    )


def _docstring(item: ast.stmt) -> bool:
    return isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str)


def contains_receiver_value(node: ast.AST) -> bool:
    """Identify raw receiver values within an expression."""
    return (isinstance(node, ast.Name) and node.id == "self") or any(
        contains_receiver_value(child) for child in ast.iter_child_nodes(node)
    )


def require_unescaped_use(node: ast.AST, allowed: ast.AST | None, parents: dict[int, ast.AST]) -> None:
    """Check a conservative factory safety condition."""
    if allowed is not None:
        if node is not allowed:
            raise ValueError("mutable factory input escapes")
    else:
        parent = parents.get(id(node))
        if not isinstance(parent, ast.Call) or parent.func is not node:
            raise ValueError("bound factory alias escapes")


def pure_return_statement(item: ast.stmt) -> bool:
    """Check a conservative factory safety condition."""
    return isinstance(item, ast.Return) or (
        isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str)
    )


def reference_node(node: ast.AST) -> bool:
    """Check a conservative factory safety condition."""
    return isinstance(node, (ast.Name, ast.Attribute))


def loaded_name(node: ast.AST, name: str) -> bool:
    """Check a conservative factory safety condition."""
    return isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)


def require_constructor_use(parent: ast.AST | None, node: ast.AST) -> None:
    """Refuse a class reference outside its direct construction call."""
    if not isinstance(parent, ast.Call) or parent.func is not node:
        raise ValueError("factory class escapes construction")
