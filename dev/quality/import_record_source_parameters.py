"""Bounded receiver provenance for dynamic imports."""

from __future__ import annotations

import ast

from .import_check_models import SourceModule
from .import_record_factory import FactoryProvenance
from .import_record_models import SourceExpression
from .import_record_parameters import parameter_names, parameter_values
from .import_record_projection import reference_visible


class ParameterSourceProvenance(FactoryProvenance):
    """Resolve finite arguments passed to declaration factories."""

    def _parameter_sources(
        self, module: str, function: ast.FunctionDef | ast.AsyncFunctionDef, name: str
    ) -> tuple[SourceExpression, ...]:
        reference = f"{module}.{function.name}"
        parameters = [parameter.arg for parameter in (*function.args.posonlyargs, *function.args.args)]
        sources: list[SourceExpression] = []
        for caller, source in self.modules.items():
            if not reference_visible(self.modules, caller, reference):
                continue
            self._collect_parameter_sources(caller, source, reference, parameters, name, sources)
        sources.extend(self._parameterized_sources(module, function, name))
        return tuple(sources)

    def _collect_parameter_sources(
        self,
        caller: str,
        source: SourceModule,
        reference: str,
        parameters: list[str],
        name: str,
        sources: list[SourceExpression],
    ) -> None:
        parents = {id(child): parent for parent in ast.walk(source.tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(source.tree):
            self._collect_parameter_node(caller, node, reference, parameters, name, sources, parents)

    def _collect_parameter_node(
        self,
        caller: str,
        node: ast.AST,
        reference: str,
        parameters: list[str],
        name: str,
        sources: list[SourceExpression],
        parents: dict[int, ast.AST],
    ) -> None:
        if self.reference(caller, node) == reference:
            parent = parents.get(id(node))
            if not isinstance(parent, ast.Call) or parent.func is not node:
                raise ValueError("parameterized callable escapes direct invocation")
        if not isinstance(node, ast.Call) or self.reference(caller, node.func) != reference:
            return
        value = _parameter_value(node, parameters, name)
        if value is None:
            raise ValueError("unknown helper argument")
        sources.append(SourceExpression(caller, value))

    def _parameterized_sources(
        self, module: str, function: ast.FunctionDef | ast.AsyncFunctionDef, name: str
    ) -> tuple[SourceExpression, ...]:
        sources: list[SourceExpression] = []
        for decorator in function.decorator_list:
            if (
                not isinstance(decorator, ast.Call)
                or self.reference(module, decorator.func) != "pytest.mark.parametrize"
            ):
                raise ValueError("unknown parameter-function decorator")
            declared, cases = _parameter_arguments(decorator)
            names = parameter_names(declared)
            if name not in names:
                continue
            for value in parameter_values(decorator, cases, names, name):
                self._require_inline_parameter_value(module, value)
                sources.append(SourceExpression(module, value))
        return tuple(sources)

    def _require_inline_parameter_value(self, module: str, node: ast.AST) -> None:
        if isinstance(node, ast.Constant) or (isinstance(node, ast.Name) and node.id == "__package__"):
            return
        if isinstance(node, ast.Call) and self.fields(self.reference(module, node.func) or ""):
            self._require_inline_call(module, node)
            return
        if isinstance(node, (ast.Tuple, ast.List)):
            for child in node.elts:
                self._require_inline_parameter_value(module, child)
            return
        if isinstance(node, ast.Attribute):
            self._require_closed_factory_input(SourceExpression(module, node), frozenset())
            return
        raise ValueError("parameterized record has an open constructor input")

    def _require_inline_call(self, module: str, node: ast.Call) -> None:
        if f"{self.reference(module, node.func)}.__post_init__" in self.definitions:
            raise ValueError("parameterized record has post-init behavior")
        for child in (*node.args, *(keyword.value for keyword in node.keywords)):
            self._require_inline_parameter_value(module, child)
        return

    def _module_assignment(self, module: str, name: str) -> SourceExpression:
        assignments = self.context(module).latest_values(name, 10**9, None)
        if assignments is not None and assignments:
            values = ast.Tuple(
                elts=[item.value for item in assignments if isinstance(item.value, ast.expr)], ctx=ast.Load()
            )
            return SourceExpression(module, values)
        raise ValueError("imported declaration is not finite")


def _parameter_arguments(decorator: ast.Call) -> tuple[ast.expr | None, ast.expr | None]:
    declared = (
        decorator.args[0]
        if decorator.args
        else next((item.value for item in decorator.keywords if item.arg == "argnames"), None)
    )
    cases = (
        decorator.args[1]
        if len(decorator.args) > 1
        else next((item.value for item in decorator.keywords if item.arg == "argvalues"), None)
    )
    return declared, cases


def _parameter_value(node: ast.Call, parameters: list[str], name: str) -> ast.expr | None:
    value = next((keyword.value for keyword in node.keywords if keyword.arg == name), None)
    if value is None and name in parameters and len(node.args) > parameters.index(name):
        value = node.args[parameters.index(name)]
    return value
