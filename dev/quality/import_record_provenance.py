"""Bounded receiver provenance for dynamic imports."""

from __future__ import annotations

import ast
from typing import override

from .import_record_models import SourceExpression
from .import_record_walks import DeclarationWalks


class RecordTargetProvenance(DeclarationWalks):
    """Trace finite declaration recordtargetprovenance without executing product code."""

    def targets(self, module: str, node: ast.AST) -> frozenset[str] | None:
        """Resolve only values reaching this receiver; open branches fail closed."""
        try:
            expressions = self._expand(SourceExpression(module, node), (), frozenset())
            targets: set[str] = set()
            for expression in expressions:
                values = self._strings(expression)
                if values is None:
                    return None
                targets.update(values)
            return frozenset(targets) if targets else None
        except (RecursionError, ValueError):
            return None

    @override
    def _expand(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        node = expression.node
        if expression.wrapped_node and path:
            if path[0] != "spec":
                raise ValueError("unknown command-node projection")
            return self._expand(SourceExpression(expression.module, node, expression.bindings), path[1:], visiting)
        key = (expression.module, id(node), path)
        if key in visiting or len(visiting) > 80:
            raise ValueError("cyclic or unbounded declaration source")
        visiting = visiting | {key}
        if isinstance(node, ast.Attribute):
            return self._expand(
                SourceExpression(expression.module, node.value, expression.bindings), (node.attr, *path), visiting
            )
        if isinstance(node, ast.Name):
            return self._expand_name(expression, path, visiting)
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return tuple(
                item
                for value in node.elts
                for item in self._expand(
                    SourceExpression(expression.module, value, expression.bindings), path, visiting
                )
            )
        if isinstance(node, ast.DictComp):
            bindings = dict(expression.bindings)
            for generator in node.generators:
                if isinstance(generator.target, ast.Name):
                    bindings[generator.target.id] = (
                        SourceExpression(expression.module, generator.iter, dict(bindings)),
                    )
                elif isinstance(generator.target, ast.Tuple):
                    for index, target in enumerate(generator.target.elts):
                        if not isinstance(target, ast.Name):
                            raise ValueError("unsupported mapping generator")
                        if index == 1:
                            bindings[target.id] = (
                                self._iteration_projection(
                                    SourceExpression(expression.module, generator.iter, dict(bindings)), (index,)
                                ),
                            )
                else:
                    raise ValueError("unsupported mapping generator")
            return self._expand(SourceExpression(expression.module, node.value, bindings), path, visiting)
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            bindings = dict(expression.bindings)
            for generator in node.generators:
                if not isinstance(generator.target, ast.Name):
                    raise ValueError("unsupported comprehension binding")
                values = self._expand(SourceExpression(expression.module, generator.iter, bindings), (), visiting)
                bindings[generator.target.id] = values
            return self._expand(SourceExpression(expression.module, node.elt, bindings), path, visiting)
        if isinstance(node, ast.BoolOp):
            return tuple(
                item
                for value in node.values
                for item in self._expand(
                    SourceExpression(expression.module, value, expression.bindings), path, visiting
                )
            )
        if isinstance(node, ast.Starred):
            return self._expand(SourceExpression(expression.module, node.value, expression.bindings), path, visiting)
        if isinstance(node, ast.Subscript):
            return self._expand(SourceExpression(expression.module, node.value, expression.bindings), path, visiting)
        if isinstance(node, ast.IfExp):
            if (
                isinstance(node.test, ast.Call)
                and isinstance(node.test.func, ast.Name)
                and node.test.func.id == "isinstance"
            ):
                branch = self._record_type_branch(expression)
                return self._expand(SourceExpression(expression.module, branch, expression.bindings), path, visiting)
            return tuple(
                item
                for branch in (node.body, node.orelse)
                for item in self._expand(
                    SourceExpression(expression.module, branch, expression.bindings), path, visiting
                )
            )
        if isinstance(node, ast.Call):
            return self._expand_call(expression, path, visiting)
        if isinstance(node, ast.Constant) and node.value is None:
            return ()
        if path:
            raise ValueError("unresolved record projection")
        return (expression,)

    def _expand_name(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        node = expression.node
        if not isinstance(node, ast.Name):
            raise ValueError("expected name")
        if node.id in expression.bindings:
            return tuple(item for value in expression.bindings[node.id] for item in self._expand(value, path, visiting))
        context = self.context(expression.module)
        scope = context.nearest_function(node)
        assignments = context.latest_values(node.id, node.lineno, scope)
        if assignments is not None and assignments:
            if any(assignment.projection for assignment in assignments):
                values: list[SourceExpression] = []
                for assignment in assignments:
                    source = SourceExpression(expression.module, assignment.value, expression.bindings)
                    if assignment.projection:
                        source = self._iteration_projection(source, assignment.projection)
                    values.extend(self._expand(source, path, visiting))
                return tuple(values)
            return tuple(
                item
                for assignment in assignments
                for item in self._expand(
                    SourceExpression(expression.module, assignment.value, expression.bindings), path, visiting
                )
            )
        parameters = set()
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            parameters = {item.arg for item in (*scope.args.posonlyargs, *scope.args.args, *scope.args.kwonlyargs)}
        binding = self.modules[expression.module].bindings.get(node.id) if node.id not in parameters else None
        if (
            binding is not None
            and binding.target is not None
            and binding.target in self.modules
            and binding.imported_name is not None
        ):
            imported = self._module_assignment(binding.target, binding.imported_name)
            return self._expand(imported, path, visiting)
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            callback = f"{expression.module}.{scope.name}"
            parameters = (*scope.args.posonlyargs, *scope.args.args)
            if parameters and node.id == parameters[0].arg and callback in self.callback_sources:
                targets = self._callback_targets(callback)
                return (
                    tuple(SourceExpression(expression.module, ast.Constant(value=value)) for value in targets)
                    if path == ("module",)
                    else self._fail()
                )
        sources = self._comprehension_sources(expression)
        if sources is not None:
            return tuple(item for source in sources for item in self._expand(source, path, visiting))
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.id in {
            item.arg for item in (*scope.args.posonlyargs, *scope.args.args, *scope.args.kwonlyargs)
        }:
            sources = self._parameter_sources(expression.module, scope, node.id)
            if sources:
                return tuple(item for source in sources for item in self._expand(source, path, visiting))
        if not path:
            return (expression,)
        raise ValueError("unknown receiver source")

    def _iteration_projection(self, source: SourceExpression, projection: tuple[int, ...]) -> SourceExpression:
        node = source.node
        if len(projection) != 1 or not isinstance(node, ast.Call):
            raise ValueError("unsupported iteration projection")
        index = projection[0]
        if isinstance(node.func, ast.Name) and node.func.id == "zip" and len(node.args) > index:
            return SourceExpression(source.module, node.args[index], source.bindings)
        if isinstance(node.func, ast.Name) and node.func.id == "enumerate" and node.args and index == 1:
            return SourceExpression(source.module, node.args[0], source.bindings)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "items" and index == 1:
            return SourceExpression(source.module, node.func.value, source.bindings)
        raise ValueError("unknown iteration projection")

    def _comprehension_sources(self, expression: SourceExpression) -> tuple[SourceExpression, ...] | None:
        node = expression.node
        if not isinstance(node, ast.Name):
            return None
        context = self.context(expression.module)
        for candidate in ast.walk(self.modules[expression.module].tree):
            if not isinstance(candidate, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
                continue
            projections = (candidate.key, candidate.value) if isinstance(candidate, ast.DictComp) else (candidate.elt,)
            visible = candidate.generators
            for index, generator in enumerate(candidate.generators):
                if any(any(item is node for item in ast.walk(condition)) for condition in generator.ifs):
                    projections = tuple(generator.ifs)
                    visible = candidate.generators[: index + 1]
                    break
            if not any(any(item is node for item in ast.walk(projection)) for projection in projections):
                continue
            if context.nearest_function(candidate) is not context.nearest_function(node):
                continue
            bindings = dict(expression.bindings)
            for generator in visible:
                if not isinstance(generator.target, ast.Name):
                    raise ValueError("unsupported comprehension source")
                bindings[generator.target.id] = (SourceExpression(expression.module, generator.iter, dict(bindings)),)
            return bindings.get(node.id)
        return None

    def _parameter_sources(
        self, module: str, function: ast.FunctionDef | ast.AsyncFunctionDef, name: str
    ) -> tuple[SourceExpression, ...]:
        reference = f"{module}.{function.name}"
        parameters = [parameter.arg for parameter in (*function.args.posonlyargs, *function.args.args)]
        sources: list[SourceExpression] = []
        for caller, source in self.modules.items():
            if not self._reference_visible(caller, reference):
                continue
            parents = {id(child): parent for parent in ast.walk(source.tree) for child in ast.iter_child_nodes(parent)}
            for node in ast.walk(source.tree):
                if self.reference(caller, node) == reference:
                    parent = parents.get(id(node))
                    if not isinstance(parent, ast.Call) or parent.func is not node:
                        raise ValueError("parameterized callable escapes direct invocation")
                if not isinstance(node, ast.Call) or self.reference(caller, node.func) != reference:
                    continue
                value = next((keyword.value for keyword in node.keywords if keyword.arg == name), None)
                if value is None and name in parameters and len(node.args) > parameters.index(name):
                    value = node.args[parameters.index(name)]
                if value is None:
                    raise ValueError("unknown helper argument")
                sources.append(SourceExpression(caller, value))
        sources.extend(self._parameterized_sources(module, function, name))
        return tuple(sources)

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
            if isinstance(declared, ast.Constant) and isinstance(declared.value, str):
                names = tuple(part.strip() for part in declared.value.split(","))
            elif isinstance(declared, (ast.Tuple, ast.List)) and all(
                isinstance(part, ast.Constant) and isinstance(part.value, str) for part in declared.elts
            ):
                names = tuple(part.value for part in declared.elts if isinstance(part, ast.Constant))
            else:
                raise ValueError("open parameterized argument names")
            if name not in names:
                continue
            if not isinstance(cases, (ast.Tuple, ast.List)):
                raise ValueError("open parameterized declaration cases")
            indirect = next((item.value for item in decorator.keywords if item.arg == "indirect"), None)
            if (
                indirect is not None
                and not (isinstance(indirect, ast.Constant) and indirect.value is False)
                and not (
                    isinstance(indirect, (ast.Tuple, ast.List))
                    and all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in indirect.elts)
                    and name not in {item.value for item in indirect.elts if isinstance(item, ast.Constant)}
                )
            ):
                raise ValueError("indirect parameterized declaration")
            for case in cases.elts:
                if len(names) == 1:
                    value = case
                elif isinstance(case, (ast.Tuple, ast.List)) and len(case.elts) == len(names):
                    value = case.elts[names.index(name)]
                else:
                    raise ValueError("open parameterized declaration")
                if not isinstance(value, (ast.Call, ast.Constant)):
                    raise ValueError("parameterized record must be constructed inline")
                self._require_inline_parameter_value(module, value)
                sources.append(SourceExpression(module, value))
        return tuple(sources)

    def _require_inline_parameter_value(self, module: str, node: ast.AST) -> None:
        if isinstance(node, ast.Constant) or (isinstance(node, ast.Name) and node.id == "__package__"):
            return
        if isinstance(node, ast.Call) and self.fields(self.reference(module, node.func) or ""):
            if f"{self.reference(module, node.func)}.__post_init__" in self.definitions:
                raise ValueError("parameterized record has post-init behavior")
            for child in (*node.args, *(keyword.value for keyword in node.keywords)):
                self._require_inline_parameter_value(module, child)
            return
        if isinstance(node, (ast.Tuple, ast.List)):
            for child in node.elts:
                self._require_inline_parameter_value(module, child)
            return
        if isinstance(node, ast.Attribute):
            self._require_closed_factory_input(SourceExpression(module, node), frozenset())
            return
        raise ValueError("parameterized record has an open constructor input")

    def _module_assignment(self, module: str, name: str) -> SourceExpression:
        assignments = self.context(module).latest_values(name, 10**9, None)
        if assignments is not None and assignments:
            values = ast.Tuple(
                elts=[item.value for item in assignments if isinstance(item.value, ast.expr)], ctx=ast.Load()
            )
            return SourceExpression(module, values)
        raise ValueError("imported declaration is not finite")

    def _expand_call(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        node = expression.node
        if not isinstance(node, ast.Call):
            raise ValueError("expected call")
        reference = self.constructor_reference(expression)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            mappings = self._expand(
                SourceExpression(expression.module, node.func.value, expression.bindings), (), visiting
            )
            values: list[SourceExpression] = []
            for mapping in mappings:
                if not isinstance(mapping.node, ast.Dict):
                    raise ValueError("unknown dictionary source")
                values.extend(
                    SourceExpression(mapping.module, value, mapping.bindings) for value in mapping.node.values
                )
            if len(node.args) > 1:
                values.append(SourceExpression(expression.module, node.args[1], expression.bindings))
            return tuple(item for value in values for item in self._expand(value, path, visiting))
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"values", "items"}:
            return self._expand(
                SourceExpression(expression.module, node.func.value, expression.bindings), path, visiting
            )
        if isinstance(node.func, ast.Attribute) and node.func.attr in {
            "root",
            "spec",
            "children",
            "nodes",
            "resolve_path",
            "by_schema_identity",
            "by_key",
        }:
            objects = self._expand(
                SourceExpression(expression.module, node.func.value, expression.bindings), (), visiting
            )
            if objects and all(
                {"declared", "families", "resolver"}
                <= {
                    item.target.id
                    for item in self.fields(self.constructor_reference(obj) or "")
                    if isinstance(item.target, ast.Name)
                }
                for obj in objects
            ):
                suffix = path[1:] if node.func.attr == "nodes" and path and path[0] == "spec" else path
                if node.func.attr == "root":
                    roots = [self._argument(obj, "declared") for obj in objects]
                    if any(root is None for root in roots):
                        raise ValueError("unknown graph root")
                    return tuple(
                        item for root in roots if root is not None for item in self._expand(root, suffix, visiting)
                    )
                records = tuple(item for obj in objects for item in self._graph_records(obj, suffix, visiting))
                if node.func.attr == "nodes" and not path:
                    return tuple(
                        SourceExpression(item.module, item.node, item.bindings, wrapped_node=True) for item in records
                    )
                return records
        if reference in self.classes:
            if not self.fields(reference):
                raise ValueError("unproven custom constructor")
            if not path:
                return (expression,)
            fields = {item.target.id for item in self.fields(reference) if isinstance(item.target, ast.Name)}
            if path[0] == "specs" and {"declared", "families", "resolver"} <= fields:
                return self._graph_records(expression, path[1:], visiting)
            field_value = self._argument(expression, path[0])
            if field_value is None:
                raise ValueError("unknown constructor field")
            if path == ("module",):
                values = self._record_modules(expression)
                return tuple(SourceExpression(expression.module, ast.Constant(value=value)) for value in values)
            return self._expand(field_value, path[1:], visiting)
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in {"tuple", "list", "set", "frozenset"}
            and len(node.args) == 1
        ):
            return self._expand(SourceExpression(expression.module, node.args[0], expression.bindings), path, visiting)
        if reference == "dataclasses.replace":
            return self._replace_sources(expression, path, visiting)
        definition = self.definitions.get(reference or "")
        if not isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound = self._bound_method_results(expression, path, visiting)
            if bound is not None:
                return bound
            raise ValueError(f"unknown declaration constructor in {expression.module}:{getattr(node, 'lineno', 0)}")
        return self._factory_results(expression, reference or "", definition, path, visiting)

    def _bound_method_results(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...] | None:
        node = expression.node
        if not isinstance(node, ast.Call):
            return None
        function = node.func
        if isinstance(function, ast.Name):
            self._require_unescaped_factory_name(expression.module, function.id)
            context = self.context(expression.module)
            assignments = context.latest_values(
                function.id, getattr(node, "lineno", 10**9), context.nearest_function(node)
            )
            if assignments is None or len(assignments) != 1:
                return None
            function = assignments[0].value
        if not isinstance(function, ast.Attribute):
            return None
        if isinstance(function.value, ast.Name):
            if function.value.id not in expression.bindings:
                raise ValueError("named mutable factory receiver")
        elif not (
            isinstance(function.value, ast.Call)
            and self.reference(expression.module, function.value.func) in self.classes
        ):
            raise ValueError("unknown factory receiver construction")
        receivers = self._expand(SourceExpression(expression.module, function.value, expression.bindings), (), visiting)
        results: list[SourceExpression] = []
        for receiver in receivers:
            owner = self.constructor_reference(receiver)
            if owner is None or not self.fields(owner):
                return None
            self._require_construction_only_class(owner)
            if f"{owner}.__post_init__" in self.definitions:
                raise ValueError("factory receiver has post-init behavior")
            for field in self.fields(owner):
                if not isinstance(field.target, ast.Name):
                    continue
                argument = self._argument(receiver, field.target.id)
                if argument is None:
                    raise ValueError("unknown factory constructor input")
                self._require_closed_factory_input(argument, frozenset())
            reference = f"{owner}.{function.attr}"
            definition = self.definitions.get(reference)
            if not isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return None
            results.extend(self._factory_results(expression, reference, definition, path, visiting, receiver=receiver))
        return tuple(results) if receivers else None

    def _require_construction_only_class(self, owner: str) -> None:
        if owner in self._closed_factory_classes:
            return
        for module, source in self.modules.items():
            if not self._reference_visible(module, owner):
                continue
            parents = {id(child): parent for parent in ast.walk(source.tree) for child in ast.iter_child_nodes(parent)}
            for node in ast.walk(source.tree):
                if not isinstance(node, (ast.Name, ast.Attribute)) or self.reference(module, node) != owner:
                    continue
                parent = parents.get(id(node))
                if not isinstance(parent, ast.Call) or parent.func is not node:
                    raise ValueError("factory class escapes construction")
        self._closed_factory_classes.add(owner)

    def _reference_visible(self, module: str, reference: str) -> bool:
        if reference.rpartition(".")[0] == module:
            return True
        for binding in self.modules[module].bindings.values():
            if binding.target is None:
                continue
            prefix = binding.target
            if binding.imported_name is not None:
                prefix = f"{prefix}.{binding.imported_name}"
            if reference == prefix or reference.startswith(f"{prefix}."):
                return True
        return False

    def _require_closed_factory_input(self, expression: SourceExpression, visiting: frozenset[tuple[str, int]]) -> None:
        node = expression.node
        key = (expression.module, id(node))
        if key in visiting or len(visiting) > 80:
            raise ValueError("cyclic factory input")
        visiting = visiting | {key}
        if isinstance(node, ast.Constant) or (isinstance(node, ast.Name) and node.id == "__package__"):
            return
        if isinstance(node, ast.Name):
            values = self._expand(expression, (), frozenset())
            if not values or any(not isinstance(value.node, ast.Constant) for value in values):
                self._require_unescaped_factory_name(expression.module, node.id, allowed=node)
            for value in values:
                self._require_closed_factory_input(value, visiting)
            return
        if isinstance(node, (ast.Tuple, ast.List, ast.Set, ast.Dict)):
            children = (*node.keys, *node.values) if isinstance(node, ast.Dict) else node.elts
            for child in children:
                if child is None:
                    raise ValueError("open factory input mapping")
                self._require_closed_factory_input(
                    SourceExpression(expression.module, child, expression.bindings), visiting
                )
            return
        if isinstance(node, ast.Attribute):
            owner = self.reference(expression.module, node.value)
            definition = self.classes.get(owner or "")
            if (
                definition is not None
                and any(
                    self.reference((owner or "").rpartition(".")[0], base)
                    in {"enum.Enum", "enum.IntEnum", "enum.StrEnum"}
                    for base in definition.bases
                )
                and not any(isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) for item in definition.body)
            ):
                return
            raise ValueError("unknown factory input attribute")
        if isinstance(node, ast.Call):
            owner = self.constructor_reference(expression)
            fields = self.fields(owner or "")
            if not fields or f"{owner}.__post_init__" in self.definitions:
                raise ValueError("unknown nested factory input")
            for field in fields:
                if not isinstance(field.target, ast.Name):
                    continue
                value = self._argument(expression, field.target.id)
                if value is None:
                    raise ValueError("unknown nested constructor field")
                self._require_closed_factory_input(value, visiting)
            return
        raise ValueError("open factory input")

    def _require_unescaped_factory_name(self, module: str, name: str, *, allowed: ast.AST | None = None) -> None:
        tree = self.modules[module].tree
        parents = {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name) or node.id != name or not isinstance(node.ctx, ast.Load):
                continue
            if allowed is not None:
                if node is not allowed:
                    raise ValueError("mutable factory input escapes")
            else:
                parent = parents.get(id(node))
                if not isinstance(parent, ast.Call) or parent.func is not node:
                    raise ValueError("bound factory alias escapes")
        if any(
            binding.target == module and binding.imported_name == name
            for source in self.modules.values()
            for binding in source.bindings.values()
        ):
            raise ValueError("factory source escapes its declaring module")

    def _graph_records(
        self, graph: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        declared = self._argument(graph, "declared")
        families = self._argument(graph, "families")
        if declared is None or families is None:
            raise ValueError("unknown graph declaration")
        result = list(self._expand(declared, path, visiting))
        for family in self._expand(families, (), visiting):
            source = self._argument(family, "source")
            if source is None:
                raise ValueError("unknown graph family")
            for target in self._expand(source, (), visiting):
                modules = self._record_modules(target)
                qualname = self._argument(target, "qualname")
                names = self._strings(qualname) if qualname is not None else None
                if names is None:
                    raise ValueError("unknown graph family symbol")
                for module in modules:
                    for name in names:
                        result.extend(self._expand(self._module_assignment(module, name), path, visiting))
        return tuple(result)

    def _replace_sources(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        node = expression.node
        if not isinstance(node, ast.Call) or len(node.args) != 1:
            raise ValueError("unsupported record replacement")
        originals = self._expand(SourceExpression(expression.module, node.args[0], expression.bindings), (), visiting)
        updated: list[SourceExpression] = []
        for original in originals:
            if not isinstance(original.node, ast.Call):
                raise ValueError("unknown replacement source")
            bindings = dict(original.bindings)
            changed = {keyword.arg for keyword in node.keywords}
            keywords = [keyword for keyword in original.node.keywords if keyword.arg not in changed]
            reference = self.constructor_reference(original)
            fields = [item.target.id for item in self.fields(reference or "") if isinstance(item.target, ast.Name)]
            arguments = list(original.node.args)
            for index, keyword in enumerate(node.keywords):
                if keyword.arg is None:
                    raise ValueError("open replacement fields")
                name = f"replacement_{id(node)}_{index}"
                bindings[name] = (SourceExpression(expression.module, keyword.value, expression.bindings),)
                value = ast.Name(id=name, ctx=ast.Load())
                if keyword.arg in fields and fields.index(keyword.arg) < len(arguments):
                    arguments[fields.index(keyword.arg)] = value
                else:
                    keywords.append(ast.keyword(arg=keyword.arg, value=value))
            call = ast.Call(func=original.node.func, args=arguments, keywords=keywords)
            updated.extend(self._expand(SourceExpression(original.module, call, bindings), path, visiting))
        return tuple(updated)

    def _factory_results(
        self,
        expression: SourceExpression,
        reference: str,
        definition: ast.FunctionDef | ast.AsyncFunctionDef,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
        *,
        receiver: SourceExpression | None = None,
    ) -> tuple[SourceExpression, ...]:
        call = expression.node
        if not isinstance(call, ast.Call):
            raise ValueError("expected factory call")
        parameters = (*definition.args.posonlyargs, *definition.args.args)
        bindings: dict[str, tuple[SourceExpression, ...]] = {}
        owner, _, _ = reference.rpartition(".")
        module = owner
        if owner in self.classes:
            module = owner.rpartition(".")[0]
            if parameters and parameters[0].arg == "self":
                if receiver is None:
                    raise ValueError("unknown factory receiver")
                bindings["self"] = (receiver,)
                parameters = parameters[1:]
            if parameters and parameters[0].arg == "cls":
                bindings["cls"] = (SourceExpression(module, ast.Name(id=owner.rpartition(".")[2])),)
                parameters = parameters[1:]
        for parameter, value in zip(parameters, call.args, strict=False):
            bindings[parameter.arg] = (SourceExpression(expression.module, value, expression.bindings),)
        for keyword in call.keywords:
            if keyword.arg is None:
                raise ValueError("open keyword arguments")
            bindings[keyword.arg] = (SourceExpression(expression.module, keyword.value, expression.bindings),)
        for parameter, default in zip(
            definition.args.args[-len(definition.args.defaults) :] if definition.args.defaults else (),
            definition.args.defaults,
            strict=True,
        ):
            bindings.setdefault(parameter.arg, (SourceExpression(module, default),))
        for parameter, default in zip(definition.args.kwonlyargs, definition.args.kw_defaults, strict=True):
            if default is not None:
                bindings.setdefault(parameter.arg, (SourceExpression(module, default),))
        rebound = {
            target.id
            for item in ast.walk(definition)
            if isinstance(item, (ast.Assign, ast.AnnAssign, ast.NamedExpr, ast.AugAssign))
            for target in ast.walk(item)
            if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Store)
        }
        if rebound & bindings.keys():
            raise ValueError("factory parameter is rebound")
        if receiver is not None:
            self._require_pure_receiver_method(owner, definition, frozenset())
        returns = [
            node
            for node in ast.walk(definition)
            if isinstance(node, ast.Return)
            and node.value is not None
            and self.context(module).nearest_function(node) is definition
        ]
        if not returns:
            return self._walked_records(module, reference, definition, bindings, path, visiting)
        return tuple(
            item
            for result in returns
            if result.value is not None
            for item in self._expand(SourceExpression(module, result.value, bindings), path, visiting)
        )

    def _require_pure_receiver_method(
        self, owner: str, definition: ast.FunctionDef | ast.AsyncFunctionDef, visiting: frozenset[str]
    ) -> None:
        reference = f"{owner}.{definition.name}"
        if reference in visiting or definition.decorator_list:
            raise ValueError("cyclic receiver method")
        visiting = visiting | {reference}
        if any(
            not isinstance(item, ast.Return)
            and not (
                isinstance(item, ast.Expr)
                and isinstance(item.value, ast.Constant)
                and isinstance(item.value.value, str)
            )
            for item in definition.body
        ):
            raise ValueError("factory receiver method is not a pure return")
        module = owner.rpartition(".")[0]
        for statement in definition.body:
            if isinstance(statement, ast.Return) and not isinstance(statement.value, ast.Call):
                raise ValueError("receiver method must return a constructed record")
        for item in ast.walk(definition):
            if isinstance(item, ast.Name) and item.id == "self":
                parent = next((parent for parent in ast.walk(definition) if item in ast.iter_child_nodes(parent)), None)
                if not isinstance(parent, ast.Attribute) or parent.value is not item:
                    raise ValueError("raw factory receiver escapes")
            if not isinstance(item, ast.Call):
                continue
            arguments = (*item.args, *(keyword.value for keyword in item.keywords))
            if any(self._contains_receiver_value(argument) for argument in arguments):
                called = self.reference(module, item.func) or ""
                if not self.fields(called) and not self._pure_record_classmethod(called):
                    raise ValueError("factory receiver escapes")
            if not isinstance(item.func, ast.Attribute) or not any(
                isinstance(child, ast.Name) and child.id == "self" for child in ast.walk(item.func.value)
            ):
                continue
            if not isinstance(item.func.value, ast.Name) or item.func.value.id != "self":
                raise ValueError("factory receiver calls an unknown method")
            sibling = self.definitions.get(f"{owner}.{item.func.attr}")
            if not isinstance(sibling, (ast.FunctionDef, ast.AsyncFunctionDef)):
                raise ValueError("factory receiver calls an unknown method")
            self._require_pure_receiver_method(owner, sibling, visiting)

    @staticmethod
    def _contains_receiver_value(node: ast.AST) -> bool:
        return (isinstance(node, ast.Name) and node.id == "self") or any(
            RecordTargetProvenance._contains_receiver_value(child) for child in ast.iter_child_nodes(node)
        )

    def _pure_record_classmethod(self, reference: str) -> bool:
        owner = reference.rpartition(".")[0]
        definition = self.definitions.get(reference)
        if not self.fields(owner) or not isinstance(definition, ast.FunctionDef):
            return False
        if len(definition.decorator_list) != 1 or not isinstance(definition.decorator_list[0], ast.Name):
            return False
        if definition.decorator_list[0].id != "classmethod":
            return False
        statements = [
            item
            for item in definition.body
            if not (
                isinstance(item, ast.Expr)
                and isinstance(item.value, ast.Constant)
                and isinstance(item.value.value, str)
            )
        ]
        if len(statements) != 1 or not isinstance(statements[0], ast.Return):
            return False
        value = statements[0].value
        return (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "cls"
            and all(
                not isinstance(item, ast.Call)
                for argument in (*value.args, *(item.value for item in value.keywords))
                for item in ast.walk(argument)
            )
        )

    def _callback_targets(self, callback: str) -> frozenset[str]:
        targets: set[str] = set()
        for source in self.callback_sources[callback]:
            targets.update(self._collect_targets(source, frozenset()))
        if not targets or len(targets) > 4096:
            raise ValueError("empty or unbounded callback source")
        return frozenset(targets)

    def _collect_targets(self, source: SourceExpression, visiting: frozenset[tuple[str, int]]) -> frozenset[str]:
        key = (source.module, id(source.node))
        if key in visiting or len(visiting) > 80:
            raise ValueError("cyclic declaration inventory")
        visiting = visiting | {key}
        targets: set[str] = set()
        for expression in self._expand(source, (), frozenset()):
            node = expression.node
            if not isinstance(node, ast.Call):
                if isinstance(node, ast.Constant) and node.value is None:
                    continue
                raise ValueError(
                    f"unknown declaration record: {expression.module}:{getattr(node, 'lineno', 0)} {ast.unparse(node)}"
                )
            reference = self.constructor_reference(expression)
            names = {item.target.id for item in self.fields(reference or "") if isinstance(item.target, ast.Name)}
            if "module" in names:
                targets.update(self._record_modules(expression))
                continue
            for name in names:
                if (reference or "", name) not in self.target_fields:
                    continue
                child = self._argument(expression, name)
                if child is None:
                    raise ValueError("missing declaration field")
                targets.update(self._collect_targets(child, visiting))
            if {"mount_key", "source"} <= names:
                child = self._argument(expression, "source")
                if child is None:
                    raise ValueError("unknown family declaration")
                for record in self._expand(child, (), frozenset()):
                    modules = self._record_modules(record)
                    qualname = self._argument(record, "qualname")
                    qualnames = self._strings(qualname) if qualname is not None else None
                    if qualnames is None:
                        raise ValueError("unknown family symbol")
                    for module in modules:
                        if module not in self.modules:
                            raise ValueError("unknown family module")
                        for symbol in qualnames:
                            targets.update(self._collect_targets(self._module_assignment(module, symbol), visiting))
        return frozenset(targets)

    @staticmethod
    def _fail() -> tuple[SourceExpression, ...]:
        raise ValueError("unsupported callback projection")
