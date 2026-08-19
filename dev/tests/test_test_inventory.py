"""Tests for the shared production-test inventory helper."""

from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path

import pytest

from cadrumo.tests._inventory import (
    FIXTURES_DIR,
    REPO_ROOT,
    SRC_CADRUMO,
    aeat_relative,
    ast_for_path,
    bare_utf8_literal_violations,
    cast_call_linenos,
    cast_rationale_violations,
    discover_test_control_modules,
    discover_test_modules,
    has_marker_on_line_or_adjacent_comment_block,
    module_name,
    non_test_package_python_files,
    non_test_python_files_under,
    package_ast_items,
    package_python_files,
    production_ast_items,
    production_python_files,
    qualified_name,
    regex_line_hits,
    repo_path,
    repo_relative,
)

from ._project_inventory import project_test_control_modules, project_test_modules

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CENTRAL_HARNESS = SRC_CADRUMO / "tests"
_ARCHITECTURE_IMPORT_OWNERS = (
    ("cadrumo.adapters.persistence", "hex_persistence_adapter"),
    ("cadrumo.adapters.inbound", "hex_inbound_adapter"),
    ("cadrumo.adapters.outbound", "hex_outbound_adapter"),
    ("cadrumo.application", "hex_application"),
    ("cadrumo.entrypoints", "hex_entrypoint"),
    ("cadrumo.domain", "hex_domain"),
    ("cadrumo.core", "hex_core"),
)


def _declared_hex_owner(tree: ast.Module) -> str | None:
    """Return the single hex owner declared by module-level ``pytestmark``."""
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets
        ):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            return None
        owners = {
            name.rsplit(".", 1)[-1]
            for element in node.value.elts
            if (name := qualified_name(element)) is not None and name.rsplit(".", 1)[-1].startswith("hex_")
        }
        return next(iter(owners)) if len(owners) == 1 else None
    return None


def _production_import_owner(module: str) -> str | None:
    """Map one direct production import to its hexagonal owner."""
    if "tests" in module.split("."):
        return None
    for prefix, owner in _ARCHITECTURE_IMPORT_OWNERS:
        if module == prefix or module.startswith(f"{prefix}."):
            return owner
    if module == "cadrumo" or module.startswith("cadrumo."):
        return "untracked_production_owner"
    return None


def _central_module_package(path: Path) -> str:
    """Return the import package containing one central-harness module."""
    parts = path.with_suffix("").parts
    cadrumo_index = max(index for index, part in enumerate(parts) if part == "cadrumo")
    return ".".join(parts[cadrumo_index:-1])


def _central_harness_ownership(path: Path) -> tuple[str | None, frozenset[str], frozenset[str]]:
    """Return declared/imported owners and executable structural evidence."""
    tree = ast_for_path(path)
    if tree is None:
        return None, frozenset(), frozenset()
    declared_owner = _declared_hex_owner(tree)
    imported_owners: set[str] = set()
    imported_modules: set[str] = set()
    structural_evidence: set[str] = set()
    package = _central_module_package(path)
    for node in ast.walk(tree):
        modules: tuple[str, ...] = ()
        if isinstance(node, ast.Import):
            modules = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                try:
                    base = importlib.util.resolve_name(f"{'.' * node.level}{node.module or ''}", package)
                except ImportError:
                    continue
            elif node.module is not None:
                base = node.module
            else:
                continue
            modules = (base, *(f"{base}.{alias.name}" for alias in node.names if alias.name != "*"))
        imported_modules.update(modules)
        imported_owners.update(owner for module in modules if (owner := _production_import_owner(module)) is not None)

        if isinstance(node, ast.Call):
            call_name = qualified_name(node.func) or ""
            leaf = call_name.rsplit(".", 1)[-1]
            if leaf in {
                "ast_for_path",
                "glob",
                "iterdir",
                "package_python_files",
                "production_ast_items",
                "read_bytes",
                "read_text",
                "rglob",
                "walk",
                "walk_packages",
            } or leaf.startswith(("discover_", "scan_")):
                structural_evidence.add(f"source-tree-analysis:{leaf}")
        if isinstance(node, ast.For):
            iter_names = {candidate.id for candidate in ast.walk(node.iter) if isinstance(candidate, ast.Name)}
            nested_iters = (
                candidate
                for statement in node.body
                for candidate in ast.walk(statement)
                if isinstance(candidate, ast.For)
            )
            if any(name.isupper() for name in iter_names) and any(
                any(candidate.id.isupper() for candidate in ast.walk(nested.iter) if isinstance(candidate, ast.Name))
                for nested in nested_iters
            ):
                structural_evidence.add("nested-declared-inventory-iteration")

    if any(module == "cadrumo.tests" or module.startswith("cadrumo.tests.") for module in imported_modules):
        structural_evidence.add("central-test-support-contract")
    if any(module == "dev" or module.startswith("dev.") for module in imported_modules):
        structural_evidence.add("development-inventory-contract")
    if declared_owner in imported_owners and len(imported_owners) > 1:
        structural_evidence.add("declared-cross-owner-boundary")

    return declared_owner, frozenset(imported_owners), frozenset(structural_evidence)


def _central_harness_owner_violation(path: Path) -> str | None:
    """Reject owner-specific test assertions from the cross-cutting harness."""
    tree = ast_for_path(path)
    if tree is None:
        return f"{path.as_posix()}: source is not parseable"
    declared_owner = _declared_hex_owner(tree)
    package = _central_module_package(path)
    import_owner: dict[str, str] = {}
    import_source: dict[str, str] = {}

    def register_import(
        node: ast.Import | ast.ImportFrom,
        owners: dict[str, str] = import_owner,
        sources: dict[str, str] = import_source,
    ) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                binding = alias.asname or alias.name.split(".", 1)[0]
                sources[binding] = alias.name
                if owner := _production_import_owner(alias.name):
                    owners[binding] = owner
            return
        if node.level:
            try:
                base = importlib.util.resolve_name(f"{'.' * node.level}{node.module or ''}", package)
            except ImportError:
                return
        elif node.module is not None:
            base = node.module
        else:
            return
        for alias in node.names:
            binding = alias.asname or alias.name
            source = f"{base}.{alias.name}" if alias.name != "*" else base
            sources[binding] = source
            if owner := _production_import_owner(base) or _production_import_owner(source):
                owners[binding] = owner

    for statement in tree.body:
        if isinstance(statement, ast.Import | ast.ImportFrom):
            register_import(statement)

    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    function_class: dict[str, str] = {}
    class_owner: dict[str, dict[str, str]] = {}
    class_source: dict[str, dict[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            owners = dict(import_owner)
            sources = dict(import_source)
            for member in node.body:
                if isinstance(member, ast.Import | ast.ImportFrom):
                    register_import(member, owners, sources)
            for member in node.body:
                targets: tuple[ast.expr, ...] = ()
                value: ast.expr | None = None
                if isinstance(member, ast.Assign):
                    targets = tuple(member.targets)
                    value = member.value
                elif isinstance(member, ast.AnnAssign):
                    targets = (member.target,)
                    value = member.value
                if value is None:
                    continue
                bound_owners = {
                    owners[candidate.id]
                    for candidate in ast.walk(value)
                    if isinstance(candidate, ast.Name) and candidate.id in owners
                }
                bound_sources = {
                    sources[candidate.id]
                    for candidate in ast.walk(value)
                    if isinstance(candidate, ast.Name) and candidate.id in sources
                }
                for target in targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if len(bound_owners) == 1:
                        owners[target.id] = next(iter(bound_owners))
                    if len(bound_sources) == 1:
                        sources[target.id] = next(iter(bound_sources))
            class_owner[node.name] = owners
            class_source[node.name] = sources
            for member in node.body:
                if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef):
                    qualified = f"{node.name}.{member.name}"
                    functions[qualified] = member
                    function_class[qualified] = node.name
    global_owner: dict[str, set[str]] = {}
    callable_maps: dict[str, set[str]] = {}
    for statement in tree.body:
        targets: tuple[ast.expr, ...] = ()
        value: ast.expr | None = None
        if isinstance(statement, ast.Assign):
            targets = tuple(statement.targets)
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            targets = (statement.target,)
            value = statement.value
        if value is None:
            continue
        names = {target.id for target in targets if isinstance(target, ast.Name)}
        owners = {
            import_owner[candidate.id]
            for candidate in ast.walk(value)
            if isinstance(candidate, ast.Name) and candidate.id in import_owner
        }
        helpers = {
            candidate.id
            for candidate in ast.walk(value)
            if isinstance(candidate, ast.Name) and candidate.id in functions
        }
        for name in names:
            if owners:
                global_owner[name] = owners
            if helpers and isinstance(value, ast.Dict):
                callable_maps[name] = helpers

    summaries: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
    mapped_runtime_tests: set[str] = set()
    support_owner_cache: dict[str, frozenset[str]] = {}

    def scoped_bindings(name: str) -> tuple[dict[str, str], dict[str, str]]:
        owners = dict(import_owner)
        sources = dict(import_source)
        if owner_class := function_class.get(name):
            owners.update(class_owner[owner_class])
            sources.update(class_source[owner_class])
        node = functions[name]
        for candidate in ast.walk(node):
            if not isinstance(candidate, ast.Import | ast.ImportFrom):
                continue
            if isinstance(candidate, ast.Import):
                for alias in candidate.names:
                    binding = alias.asname or alias.name.split(".", 1)[0]
                    sources[binding] = alias.name
                    if owner := _production_import_owner(alias.name):
                        owners[binding] = owner
                continue
            if candidate.level:
                try:
                    base = importlib.util.resolve_name(f"{'.' * candidate.level}{candidate.module or ''}", package)
                except ImportError:
                    continue
            else:
                base = candidate.module or ""
            for alias in candidate.names:
                binding = alias.asname or alias.name
                source = f"{base}.{alias.name}" if alias.name != "*" else base
                sources[binding] = source
                if owner := _production_import_owner(base) or _production_import_owner(source):
                    owners[binding] = owner
        return owners, sources

    def summarize(name: str, active: frozenset[str] = frozenset()) -> tuple[frozenset[str], frozenset[str]]:
        if name in summaries:
            return summaries[name]
        if name in active:
            return frozenset(), frozenset()
        node = functions[name]
        scoped_owner, scoped_source = scoped_bindings(name)
        owners: set[str] = set()
        evidence: set[str] = set()
        mapped_callables: dict[str, set[str]] = {}
        for candidate in ast.walk(node):
            if isinstance(candidate, ast.Import):
                for alias in candidate.names:
                    if owner := _production_import_owner(alias.name):
                        owners.add(owner)
            elif isinstance(candidate, ast.ImportFrom):
                if candidate.level:
                    try:
                        base = importlib.util.resolve_name(f"{'.' * candidate.level}{candidate.module or ''}", package)
                    except ImportError:
                        base = ""
                else:
                    base = candidate.module or ""
                for alias in candidate.names:
                    source = f"{base}.{alias.name}" if alias.name != "*" else base
                    if owner := _production_import_owner(base) or _production_import_owner(source):
                        owners.add(owner)
            if (
                isinstance(candidate, ast.Assign)
                and isinstance(candidate.value, ast.Subscript)
                and isinstance(candidate.value.value, ast.Name)
                and candidate.value.value.id in callable_maps
            ):
                for target in candidate.targets:
                    if isinstance(target, ast.Name):
                        mapped_callables[target.id] = callable_maps[candidate.value.value.id]
            if isinstance(candidate, ast.Name):
                if candidate.id in scoped_owner:
                    owners.add(scoped_owner[candidate.id])
                owners.update(global_owner.get(candidate.id, ()))
            if isinstance(candidate, ast.Attribute) and isinstance(candidate.value, ast.Name):
                owner_class = function_class.get(name)
                if (
                    owner_class
                    and candidate.value.id in {"self", "cls", owner_class}
                    and (owner := class_owner[owner_class].get(candidate.attr))
                ):
                    owners.add(owner)
            if not isinstance(candidate, ast.Call):
                continue
            call_name = qualified_name(candidate.func) or ""
            leaf = call_name.rsplit(".", 1)[-1]
            if leaf in {
                "ast_for_path",
                "glob",
                "iterdir",
                "package_python_files",
                "production_ast_items",
                "read_bytes",
                "read_text",
                "rglob",
                "walk",
                "walk_packages",
            } or leaf.startswith(("discover_", "scan_")):
                evidence.add(f"source-tree-analysis:{leaf}")
            if isinstance(candidate.func, ast.Name):
                binding = candidate.func.id
                source = scoped_source.get(binding, "")
                if source == "cadrumo.core" or (source.startswith("cadrumo.core.") and binding.isupper()):
                    evidence.add("root-facade-governance-contract")
                if source.startswith("cadrumo.tests.") and not source.startswith("cadrumo.tests._inventory."):
                    evidence.add("exercised-central-test-support")
                if source.startswith("dev.") and (
                    binding.startswith(("discover_", "find_", "scan_", "walk_"))
                    or "census" in source
                    or "inventory" in source
                ):
                    evidence.add("development-inventory-api")
                if binding in functions:
                    helper_owners, helper_evidence = summarize(binding, active | {name})
                    owners.update(helper_owners)
                    evidence.update(helper_evidence)
                for helper in mapped_callables.get(binding, ()):
                    helper_owners, helper_evidence = summarize(helper, active | {name})
                    owners.update(helper_owners)
                    evidence.update(helper_evidence)
                    if helper_owners and name.startswith("test_"):
                        mapped_runtime_tests.add(name)
        if declared_owner in owners and len(owners) > 1:
            evidence.add("declared-cross-owner-boundary")
        result = frozenset(owners), frozenset(evidence)
        summaries[name] = result
        return result

    def assertion_behavior_owners(name: str) -> tuple[tuple[int, frozenset[str]], ...]:
        """Classify owner interaction independently for every assertion."""
        node = functions[name]
        scoped_owner, scoped_source = scoped_bindings(name)
        owner_class = function_class.get(name)
        bindings: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
        binding_uncovered_owners: dict[str, frozenset[str]] = {}
        active_loop_owners: dict[str, frozenset[str]] = {}

        def owners_for(candidate: ast.AST) -> frozenset[str]:
            if isinstance(candidate, ast.Name):
                if candidate.id in active_loop_owners:
                    return active_loop_owners[candidate.id]
                if candidate.id in scoped_owner:
                    return frozenset({scoped_owner[candidate.id]})
                if candidate.id in bindings:
                    binding_owners, binding_evidence = bindings[candidate.id]
                    if binding_uncovered_owners.get(candidate.id) or binding_evidence & {
                        "relational-data",
                        "runtime-callable-map",
                        "runtime-direct-binding",
                    }:
                        return binding_owners
                    return frozenset()
                owners = global_owner.get(candidate.id, ())
                return frozenset(owners)
            if (
                isinstance(candidate, ast.Attribute)
                and isinstance(candidate.value, ast.Name)
                and owner_class
                and candidate.value.id in {"self", "cls", owner_class}
            ):
                owner = class_owner[owner_class].get(candidate.attr)
                return frozenset({owner}) if owner else frozenset()
            return frozenset()

        structural_leaves = {
            "ast_for_path",
            "glob",
            "hasattr",
            "iterdir",
            "isinstance",
            "issubclass",
            "package_python_files",
            "production_ast_items",
            "read_bytes",
            "read_text",
            "rglob",
            "walk",
            "walk_packages",
        }

        def support_expression_owners(expression: ast.AST) -> frozenset[str]:
            owners: set[str] = set()
            for call in (candidate for candidate in ast.walk(expression) if isinstance(candidate, ast.Call)):
                if not isinstance(call.func, ast.Name):
                    continue
                source = scoped_source.get(call.func.id, "")
                if not source.startswith("cadrumo.tests."):
                    continue
                if source in support_owner_cache:
                    owners.update(support_owner_cache[source])
                    continue
                parts = source.split(".")
                resolved: frozenset[str] = frozenset()
                for stop in range(len(parts), 1, -1):
                    module_path = SRC_CADRUMO.parent.joinpath(*parts[:stop]).with_suffix(".py")
                    if module_path.is_file():
                        resolved = _central_harness_ownership(module_path)[1]
                        break
                support_owner_cache[source] = resolved
                owners.update(resolved)
            return frozenset(owners)

        def expression_summary(expression: ast.AST) -> tuple[frozenset[str], frozenset[str]]:
            owners: set[str] = set()
            evidence: set[str] = set()
            for candidate in ast.walk(expression):
                owners.update(owners_for(candidate))
                if isinstance(candidate, ast.Name) and candidate.id in bindings:
                    _, binding_evidence = bindings[candidate.id]
                    evidence.update(
                        binding_evidence - {"relational-data", "runtime-callable-map", "runtime-direct-binding"}
                    )
                if not isinstance(candidate, ast.Call):
                    continue
                call_name = qualified_name(candidate.func) or ""
                leaf = call_name.rsplit(".", 1)[-1]
                if leaf in structural_leaves or leaf.startswith(("discover_", "scan_")):
                    evidence.add("structural-traversal")
                if isinstance(candidate.func, ast.Name):
                    binding = candidate.func.id
                    source = scoped_source.get(binding, "")
                    if source.startswith("cadrumo.tests._inventory."):
                        evidence.add("structural-traversal")
                    elif source.startswith("cadrumo.tests."):
                        evidence.add("central-test-support")
                    elif source.startswith("dev.") and (
                        binding.startswith(("discover_", "find_", "scan_", "walk_"))
                        or "census" in source
                        or "inventory" in source
                    ):
                        evidence.add("development-inventory")
                    if binding in functions:
                        helper_owners, helper_evidence = summarize(binding, frozenset({name}))
                        owners.update(helper_owners)
                        evidence.update(helper_evidence)
            return frozenset(owners), frozenset(evidence)

        def bind_target(
            target: ast.expr,
            summary: tuple[frozenset[str], frozenset[str]],
            uncovered_owners: frozenset[str] = frozenset(),
        ) -> None:
            if isinstance(target, ast.Name):
                bindings[target.id] = summary
                binding_uncovered_owners[target.id] = uncovered_owners
            elif isinstance(target, ast.Tuple | ast.List):
                for element in target.elts:
                    bind_target(element, summary, uncovered_owners)

        def target_names(target: ast.expr) -> tuple[str, ...]:
            if isinstance(target, ast.Name):
                return (target.id,)
            if isinstance(target, ast.Tuple | ast.List):
                return tuple(name for element in target.elts for name in target_names(element))
            return ()

        def raw_expression_owners(expression: ast.AST) -> frozenset[str]:
            owners: set[str] = set()
            for candidate in ast.walk(expression):
                if isinstance(candidate, ast.Name):
                    if candidate.id in scoped_owner:
                        owners.add(scoped_owner[candidate.id])
                    owners.update(global_owner.get(candidate.id, ()))
                    if candidate.id in bindings:
                        owners.update(bindings[candidate.id][0])
                elif (
                    isinstance(candidate, ast.Attribute)
                    and isinstance(candidate.value, ast.Name)
                    and owner_class
                    and candidate.value.id in {"self", "cls", owner_class}
                    and (owner := class_owner[owner_class].get(candidate.attr))
                ):
                    owners.add(owner)
            return frozenset(owners)

        function_parents = {child: parent for parent in ast.walk(node) for child in ast.iter_child_nodes(parent)}

        def uncovered_expression_owners(expression: ast.AST) -> frozenset[str]:
            """Return owners whose values lack structural ancestry in this expression."""
            expression_parents = {
                child: parent for parent in ast.walk(expression) for child in ast.iter_child_nodes(parent)
            }
            structural_calls = {
                candidate
                for candidate in ast.walk(expression)
                if isinstance(candidate, ast.Call)
                and (
                    (qualified_name(candidate.func) or "").rsplit(".", 1)[-1] in structural_leaves
                    or (qualified_name(candidate.func) or "").rsplit(".", 1)[-1].startswith(("discover_", "scan_"))
                )
            }
            central_support_calls = {
                candidate
                for candidate in ast.walk(expression)
                if isinstance(candidate, ast.Call)
                and isinstance(candidate.func, ast.Name)
                and scoped_source.get(candidate.func.id, "").startswith("cadrumo.tests.")
            }
            development_inventory_calls = {
                candidate
                for candidate in ast.walk(expression)
                if isinstance(candidate, ast.Call)
                and isinstance(candidate.func, ast.Name)
                and (source := scoped_source.get(candidate.func.id, "")).startswith("dev.")
                and (
                    candidate.func.id.startswith(("discover_", "find_", "scan_", "walk_"))
                    or "census" in source
                    or "inventory" in source
                )
            }
            derived_iterator_nodes: set[ast.AST] = set()
            for comprehension in (
                candidate
                for candidate in ast.walk(expression)
                if isinstance(candidate, ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp)
            ):
                results: tuple[ast.AST, ...]
                if isinstance(comprehension, ast.DictComp):
                    results = (comprehension.key, comprehension.value)
                else:
                    results = (comprehension.elt,)
                result_names = {
                    item.id for result in results for item in ast.walk(result) if isinstance(item, ast.Name)
                }
                for generator in comprehension.generators:
                    if result_names.intersection(target_names(generator.target)):
                        derived_iterator_nodes.update(ast.walk(generator.iter))
            uncovered: set[str] = set()
            for candidate in ast.walk(expression):
                candidate_owners: frozenset[str] = frozenset()
                if isinstance(candidate, ast.Name):
                    if candidate.id in binding_uncovered_owners:
                        candidate_owners = binding_uncovered_owners[candidate.id]
                    elif candidate.id in scoped_owner:
                        candidate_owners = frozenset({scoped_owner[candidate.id]})
                    else:
                        candidate_owners = frozenset(global_owner.get(candidate.id, ()))
                elif (
                    isinstance(candidate, ast.Attribute)
                    and isinstance(candidate.value, ast.Name)
                    and owner_class
                    and candidate.value.id in {"self", "cls", owner_class}
                ):
                    owner = class_owner[owner_class].get(candidate.attr)
                    candidate_owners = frozenset({owner}) if owner else frozenset()
                if not candidate_owners:
                    continue
                current: ast.AST | None = candidate
                covered = candidate in derived_iterator_nodes
                while current in expression_parents:
                    current = expression_parents[current]
                    if current in structural_calls:
                        covered = True
                        break
                    if current in development_inventory_calls:
                        covered = True
                        break
                    if current in central_support_calls and candidate_owners.intersection(
                        support_expression_owners(current)
                    ):
                        covered = True
                        break
                    if isinstance(current, ast.Attribute) and current.attr == "__module__":
                        covered = True
                        break
                parent = expression_parents.get(candidate)
                if isinstance(candidate, ast.Name) and candidate.id in scoped_owner:
                    if candidate.id.isupper() and isinstance(parent, ast.Subscript | ast.Attribute):
                        covered = True
                    if isinstance(parent, ast.Attribute) and parent.attr.isupper():
                        covered = True
                if not covered:
                    uncovered.update(candidate_owners)
            return frozenset(uncovered)

        def iterated_data_summary(
            candidate: ast.AST,
            expression: ast.AST,
        ) -> tuple[frozenset[str], frozenset[str]]:
            """Return provenance only when a value consumes an enclosing loop target."""
            owners: set[str] = set()
            evidence: set[str] = set()
            referenced = {item.id for item in ast.walk(expression) if isinstance(item, ast.Name)}
            current = candidate
            while current in function_parents:
                current = function_parents[current]
                if isinstance(current, ast.For) and referenced.intersection(target_names(current.target)):
                    iter_owners, iter_evidence = expression_summary(current.iter)
                    owners.update(iter_owners)
                    evidence.update(iter_evidence)
            return frozenset(owners), frozenset(evidence)

        for decorator in node.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and (qualified_name(decorator.func) or "").endswith("parametrize")
                and len(decorator.args) >= 2
            ):
                continue
            parameter_names: tuple[str, ...] = ()
            raw_names = decorator.args[0]
            if isinstance(raw_names, ast.Constant) and isinstance(raw_names.value, str):
                parameter_names = tuple(part.strip() for part in raw_names.value.split(","))
            elif isinstance(raw_names, ast.Tuple):
                parameter_names = tuple(
                    element.value
                    for element in raw_names.elts
                    if isinstance(element, ast.Constant) and isinstance(element.value, str)
                )
            parameter_summary = expression_summary(decorator.args[1])
            for parameter_name in parameter_names:
                bind_target(
                    ast.Name(id=parameter_name),
                    parameter_summary,
                )

        for _ in range(3):
            for candidate in ast.walk(node):
                if isinstance(candidate, ast.Assign):
                    summary = expression_summary(candidate.value)
                    if isinstance(candidate.value, ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp):
                        inventory_comprehension = any(
                            isinstance(item, ast.Name) and item.id.isupper() for item in ast.walk(candidate.value)
                        )
                        summary = (
                            summary[0] | raw_expression_owners(candidate.value),
                            summary[1]
                            | {"relational-data"}
                            | ({"structural-traversal"} if inventory_comprehension else set()),
                        )
                    iter_owners, iter_evidence = iterated_data_summary(candidate, candidate.value)
                    summary = (summary[0] | iter_owners, summary[1] | iter_evidence)
                    declaration_reference = any(
                        isinstance(item, ast.Name) and item.id in scoped_owner and item.id.isupper()
                        for item in ast.walk(candidate.value)
                    )
                    if declaration_reference:
                        summary = (summary[0], summary[1] | {"declaration-inventory"})
                    elif summary[0] and not any(isinstance(item, ast.Call) for item in ast.walk(candidate.value)):
                        summary = (summary[0], summary[1] | {"runtime-direct-binding"})
                    uncovered_owners = (
                        uncovered_expression_owners(candidate.value)
                        if summary[1] & {"central-test-support", "development-inventory", "structural-traversal"}
                        else frozenset()
                    )
                    for target in candidate.targets:
                        bind_target(target, summary, uncovered_owners)
                elif isinstance(candidate, ast.AnnAssign) and candidate.value is not None:
                    bind_target(
                        candidate.target,
                        expression_summary(candidate.value),
                    )
                elif isinstance(candidate, ast.With):
                    for item in candidate.items:
                        if item.optional_vars is not None:
                            context_owners, context_evidence = expression_summary(item.context_expr)
                            bind_target(
                                item.optional_vars,
                                (context_owners, context_evidence - {"central-test-support"}),
                            )
                elif (
                    isinstance(candidate, ast.Expr)
                    and isinstance(candidate.value, ast.Call)
                    and isinstance(candidate.value.func, ast.Attribute)
                    and isinstance(candidate.value.func.value, ast.Name)
                    and candidate.value.func.attr in {"add", "append", "extend", "update"}
                    and candidate.value.func.value.id in bindings
                ):
                    binding = candidate.value.func.value.id
                    current_owners, current_evidence = bindings[binding]
                    argument_evidence = frozenset(
                        evidence
                        for argument in (
                            *candidate.value.args,
                            *(keyword.value for keyword in candidate.value.keywords),
                        )
                        for evidence in expression_summary(argument)[1]
                    )
                    argument_owners = frozenset(
                        owner
                        for argument in (
                            *candidate.value.args,
                            *(keyword.value for keyword in candidate.value.keywords),
                        )
                        for owner in raw_expression_owners(argument)
                    )
                    bindings[binding] = (
                        current_owners | argument_owners,
                        current_evidence | argument_evidence | {"relational-data"},
                    )
                    if (current_evidence | argument_evidence) & {
                        "central-test-support",
                        "development-inventory",
                        "structural-traversal",
                    }:
                        binding_uncovered_owners[binding] = binding_uncovered_owners.get(
                            binding, frozenset()
                        ) | frozenset(
                            owner
                            for argument in (
                                *candidate.value.args,
                                *(keyword.value for keyword in candidate.value.keywords),
                            )
                            for owner in uncovered_expression_owners(argument)
                        )
                if (
                    isinstance(candidate, ast.Assign)
                    and isinstance(candidate.value, ast.Subscript)
                    and isinstance(candidate.value.value, ast.Name)
                    and candidate.value.value.id in callable_maps
                ):
                    mapped_owners: set[str] = set()
                    for helper in callable_maps[candidate.value.value.id]:
                        helper_owners, _ = summarize(helper)
                        mapped_owners.update(helper_owners)
                    mapped_summary = (frozenset(mapped_owners), frozenset({"runtime-callable-map"}))
                    for target in candidate.targets:
                        bind_target(target, mapped_summary)

        findings: list[tuple[int, frozenset[str]]] = []
        for assertion in (candidate for candidate in ast.walk(node) if isinstance(candidate, ast.Assert)):
            active_loop_owners.clear()
            ancestor = assertion
            while ancestor in function_parents:
                ancestor = function_parents[ancestor]
                if isinstance(ancestor, ast.For):
                    loop_owners = raw_expression_owners(ancestor.iter)
                    for target_name in target_names(ancestor.target):
                        active_loop_owners[target_name] = loop_owners
            parents = {child: parent for parent in ast.walk(assertion.test) for child in ast.iter_child_nodes(parent)}
            structural_calls = {
                candidate
                for candidate in ast.walk(assertion.test)
                if isinstance(candidate, ast.Call)
                and (
                    (qualified_name(candidate.func) or "").rsplit(".", 1)[-1] in structural_leaves
                    or (qualified_name(candidate.func) or "").rsplit(".", 1)[-1].startswith(("discover_", "scan_"))
                )
            }
            assertion_owners: set[str] = set()
            context_owners: set[str] = set()
            current: ast.AST = assertion
            while current in function_parents:
                current = function_parents[current]
                if isinstance(current, ast.With):
                    for item in current.items:
                        context_owners.update(support_expression_owners(item.context_expr))
            assertion_runtime: set[str] = set()
            for candidate in ast.walk(assertion.test):
                candidate_owners = owners_for(candidate)
                if not candidate_owners:
                    continue
                assertion_owners.update(candidate_owners)
                if isinstance(candidate, ast.Name) and candidate.id in bindings:
                    uncovered_owners = binding_uncovered_owners.get(candidate.id, frozenset())
                    assertion_runtime.update(uncovered_owners)
                    candidate_owners -= uncovered_owners
                    if not candidate_owners:
                        continue
                current: ast.AST | None = candidate
                covered = False
                support_covered = False
                while current in parents:
                    current = parents[current]
                    if current in structural_calls:
                        covered = True
                        break
                    if isinstance(current, ast.Call) and candidate_owners.intersection(
                        support_expression_owners(current)
                    ):
                        covered = True
                        support_covered = True
                        break
                    if isinstance(current, ast.Attribute) and current.attr == "__module__":
                        covered = True
                        break
                parent = parents.get(candidate)
                if (
                    isinstance(parent, ast.Call)
                    and parent.func is candidate
                    and not support_covered
                    and "central-test-support" not in expression_summary(parent)[1]
                ):
                    covered = False
                if (
                    isinstance(candidate, ast.Name)
                    and candidate.id in bindings
                    and bindings[candidate.id][1]
                    - {"relational-data", "runtime-callable-map", "runtime-direct-binding"}
                ):
                    covered = True
                if candidate_owners.intersection(context_owners):
                    covered = True
                if isinstance(candidate, ast.Name) and candidate.id in scoped_owner:
                    if candidate.id.isupper() and isinstance(parent, ast.Subscript | ast.Attribute):
                        covered = True
                    if isinstance(parent, ast.Attribute) and parent.attr.isupper():
                        covered = True
                if not covered:
                    assertion_runtime.update(candidate_owners)
            for call in (candidate for candidate in ast.walk(assertion.test) if isinstance(candidate, ast.Call)):
                if not isinstance(call.func, ast.Name) or call.func.id not in functions:
                    continue
                helper_owners, helper_evidence = summarize(call.func.id, frozenset({name}))
                assertion_owners.update(helper_owners)
                if not helper_evidence:
                    assertion_runtime.update(helper_owners)
            relational = (
                isinstance(assertion.test, ast.Compare)
                or (
                    isinstance(assertion.test, ast.Call)
                    and (qualified_name(assertion.test.func) or "").rsplit(".", 1)[-1] in {"isinstance", "issubclass"}
                )
                or (
                    isinstance(assertion.test, ast.UnaryOp)
                    and isinstance(assertion.test.operand, ast.BinOp | ast.BoolOp | ast.Compare)
                )
            )
            if relational:
                for candidate in ast.walk(assertion.test):
                    if isinstance(candidate, ast.Name) and candidate.id in bindings:
                        assertion_owners.update(bindings[candidate.id][0])
            if relational and not structural_calls and declared_owner in assertion_owners and len(assertion_owners) > 1:
                assertion_runtime.clear()
            if relational and "central-test-support" in expression_summary(assertion.test)[1]:
                assertion_runtime.clear()
            if assertion_runtime:
                findings.append((assertion.lineno, frozenset(assertion_runtime)))
        return tuple(findings)

    violations: list[str] = []
    for name in sorted(functions):
        test_name = name.rsplit(".", 1)[-1]
        if not test_name.startswith("test_"):
            continue
        for lineno, behavior_owners in assertion_behavior_owners(name):
            if declared_owner not in behavior_owners:
                violations.append(
                    f"{path.as_posix()}::{name}:{lineno}: declares {declared_owner or 'no hex owner'} but exercises "
                    f"production owner(s) {sorted(behavior_owners)}; marker/import ownership is inconsistent"
                )
            else:
                violations.append(
                    f"{path.as_posix()}::{name}:{lineno}: directly exercises production owner(s) "
                    f"{sorted(behavior_owners)} without assertion-local structural evidence"
                )
    return "\n".join(violations) or None


def test_discover_test_modules_returns_real_source_tests_and_excludes_fixtures() -> None:
    """Inventory discovery includes source tests and excludes fixture payloads."""
    modules = discover_test_modules()

    assert Path(__file__).resolve() in modules
    assert repo_path("src/cadrumo/tests/test_marker_integrity.py") in modules
    assert all(not path.is_relative_to(FIXTURES_DIR) for path in modules)


def test_discover_test_control_modules_includes_support_and_conftest_files() -> None:
    """Test-control discovery covers tests, support modules, and conftests."""
    modules = discover_test_control_modules()

    assert Path(__file__).resolve() in modules
    assert repo_path("src/cadrumo/tests/_inventory.py") in modules
    assert repo_path("src/cadrumo/application/conftest.py") in modules
    assert all(not path.is_relative_to(FIXTURES_DIR) for path in modules)


def test_central_harness_has_no_owner_specific_behavior_modules() -> None:
    """Central tests are structural, fixture-bearing, or genuinely cross-cutting."""
    modules = tuple(path for path in discover_test_modules() if path.is_relative_to(_CENTRAL_HARNESS))
    ownership = tuple(_central_harness_ownership(path) for path in modules)

    assert Path(__file__).resolve() in modules, "central-harness ownership inventory is empty"
    assert any(evidence for _, _, evidence in ownership), "no structurally-owned central modules were analyzed"
    assert any(imported for _, imported, _ in ownership), "no production-bearing central modules were analyzed"
    assert any(len(imported) > 1 for _, imported, _ in ownership), "no cross-owner central modules were analyzed"
    violations = [violation for path in modules if (violation := _central_harness_owner_violation(path))]

    assert not violations, "central harness contains owner-specific behavior tests:\n" + "\n".join(violations)


@pytest.mark.parametrize(
    ("declared_owner", "production_import", "production_use"),
    [
        ("hex_application", "import cadrumo.application", "cadrumo.application.__dict__"),
        ("hex_domain", "from cadrumo.domain import calculations", "calculations.__dict__"),
        ("hex_core", "from ..core import config", "config.__dict__"),
    ],
)
def test_central_harness_ownership_gate_rejects_single_owner_behavior(
    tmp_path: Path,
    declared_owner: str,
    production_import: str,
    production_use: str,
) -> None:
    """A matching declared owner and direct production import is not cross-cutting."""
    module = tmp_path / "cadrumo" / "tests" / f"test_{declared_owner}_behavior.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                production_import,
                "",
                f"pytestmark = [pytest.mark.unit, pytest.mark.{declared_owner}]",
                "",
                "def test_behavior() -> None:",
                f"    observed = {production_use}",
                "    assert observed",
            ]
        ),
        encoding="utf-8",
    )

    violation = _central_harness_owner_violation(module)

    assert violation is not None
    assert declared_owner in violation


def test_central_harness_ownership_gate_rejects_marker_import_mismatch(tmp_path: Path) -> None:
    """A misleading marker cannot disguise a singleton production owner."""
    module = tmp_path / "cadrumo" / "tests" / "test_mismatched_owner.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                "from ..application import user_profile",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "def test_behavior() -> None:",
                "    assert user_profile.__dict__",
            ]
        ),
        encoding="utf-8",
    )

    violation = _central_harness_owner_violation(module)

    assert violation is not None
    assert "marker/import ownership is inconsistent" in violation
    assert "hex_core" in violation
    assert "hex_application" in violation


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            "class TestBehavior:\n    def test_method(self) -> None:\n        assert config.__dict__\n",
            "TestBehavior.test_method",
        ),
        (
            "def test_local_import() -> None:\n"
            "    from ..core import config as local_config\n"
            "    assert local_config.__dict__\n",
            "test_local_import",
        ),
        (
            "def test_untracked_binding() -> None:\n"
            "    from cadrumo import future_owner\n"
            "    assert future_owner.__dict__\n",
            "untracked_production_owner",
        ),
    ],
)
def test_central_harness_ownership_gate_fails_closed_over_nested_and_unknown_owners(
    tmp_path: Path,
    body: str,
    expected: str,
) -> None:
    """Class methods, local imports, and new production packages cannot escape."""
    module = tmp_path / "cadrumo" / "tests" / f"test_{expected.replace('.', '_')}.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        f"import pytest\nfrom ..core import config\n\npytestmark = [pytest.mark.unit, pytest.mark.hex_core]\n\n{body}",
        encoding="utf-8",
    )

    violation = _central_harness_owner_violation(module)

    assert violation is not None
    assert expected in violation


def test_central_harness_ownership_gate_distinguishes_structural_scan_from_direct_behavior(
    tmp_path: Path,
) -> None:
    """The same singleton owner is central only when source analysis proves it."""
    direct = tmp_path / "cadrumo" / "tests" / "test_direct_locale_behavior.py"
    direct.parent.mkdir(parents=True)
    direct.write_text(
        "\n".join(
            [
                "import pytest",
                "from ..core.i18n import tr",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "def test_message() -> None:",
                "    assert tr('application.wizard.output_labels.next', locale='es')",
            ]
        ),
        encoding="utf-8",
    )
    structural = tmp_path / "cadrumo" / "tests" / "test_locale_source_structure.py"
    structural.write_text(
        "\n".join(
            [
                "import ast",
                "from pathlib import Path",
                "import pytest",
                "from ..core import i18n",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "def test_module_parses() -> None:",
                "    tree = ast.parse(Path(i18n.__file__).read_text(encoding='utf-8'))",
                "    assert tree.body",
            ]
        ),
        encoding="utf-8",
    )

    assert _central_harness_owner_violation(direct) is not None
    assert _central_harness_owner_violation(structural) is None
    assert "source-tree-analysis:read_text" in _central_harness_ownership(structural)[2]


def test_central_harness_ownership_gate_rejects_runtime_half_of_mixed_module(tmp_path: Path) -> None:
    """A module's AST gate cannot shield a sibling runtime witness."""
    module = tmp_path / "cadrumo" / "tests" / "test_mixed_inventory_and_runtime.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                "from ..domain.renta import calculate_art_7p_exemption",
                "from ._inventory import production_ast_items",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "def _runtime_witness() -> object:",
                "    return calculate_art_7p_exemption",
                "",
                "_WITNESSES = {'art-7p': _runtime_witness}",
                "",
                "def test_inventory() -> None:",
                "    assert tuple(production_ast_items())",
                "",
                "def test_runtime() -> None:",
                "    witness = _WITNESSES['art-7p']",
                "    assert witness()",
            ]
        ),
        encoding="utf-8",
    )

    violation = _central_harness_owner_violation(module)

    assert violation is not None
    assert "::test_runtime:" in violation
    assert "::test_inventory:" not in violation


def test_central_harness_ownership_gate_rejects_mixed_structural_and_runtime_assertion(
    tmp_path: Path,
) -> None:
    """A structural branch cannot shield owner behavior in the same assertion."""
    module = tmp_path / "cadrumo" / "tests" / "test_mixed_assertion.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                "from ..domain.renta import calculate_art_7p_exemption",
                "from ._inventory import production_ast_items",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "def test_mixed_assertion() -> None:",
                "    assert tuple(production_ast_items()) and calculate_art_7p_exemption",
            ]
        ),
        encoding="utf-8",
    )

    violation = _central_harness_owner_violation(module)

    assert violation is not None
    assert "::test_mixed_assertion:" in violation
    assert "hex_domain" in violation


def test_central_harness_ownership_gate_rejects_superficial_declared_owner_in_mixed_assertion(
    tmp_path: Path,
) -> None:
    """Naming the declared owner cannot shield another owner's runtime branch."""
    module = tmp_path / "cadrumo" / "tests" / "test_superficial_cross_owner_assertion.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                "from ..core import config",
                "from ..domain.renta import calculate_art_7p_exemption",
                "from ._inventory import production_ast_items",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "def test_superficial_cross_owner_assertion() -> None:",
                "    assert (",
                "        tuple(production_ast_items())",
                "        and config.__dict__",
                "        and calculate_art_7p_exemption",
                "    )",
            ]
        ),
        encoding="utf-8",
    )

    violation = _central_harness_owner_violation(module)

    assert violation is not None
    assert "::test_superficial_cross_owner_assertion:" in violation
    assert "hex_domain" in violation


def test_central_harness_ownership_gate_rejects_runtime_sibling_of_structural_assertion(
    tmp_path: Path,
) -> None:
    """One structural assertion cannot cover a sibling runtime assertion."""
    module = tmp_path / "cadrumo" / "tests" / "test_structural_and_runtime_siblings.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                "from ..domain.renta import calculate_art_7p_exemption",
                "from ._inventory import production_ast_items",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "def test_sibling_assertions() -> None:",
                "    assert tuple(production_ast_items())",
                "    assert calculate_art_7p_exemption",
            ]
        ),
        encoding="utf-8",
    )

    violation = _central_harness_owner_violation(module)

    assert violation is not None
    assert "::test_sibling_assertions:" in violation
    assert "hex_domain" in violation


def test_central_harness_ownership_gate_rejects_loop_predicate_as_structural_data(
    tmp_path: Path,
) -> None:
    """A loop target used only as a predicate cannot bless the assigned value."""
    module = tmp_path / "cadrumo" / "tests" / "test_loop_predicate_runtime.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                "from ..domain.renta import calculate_art_7p_exemption",
                "from ._inventory import production_ast_items",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "def test_loop_predicate_runtime() -> None:",
                "    observed = None",
                "    for item in production_ast_items():",
                "        observed = (",
                "            calculate_art_7p_exemption",
                "            if item",
                "            else calculate_art_7p_exemption",
                "        )",
                "    assert observed",
            ]
        ),
        encoding="utf-8",
    )

    violation = _central_harness_owner_violation(module)

    assert violation is not None
    assert "::test_loop_predicate_runtime:" in violation
    assert "hex_domain" in violation


@pytest.mark.parametrize(
    "module_name,test_body",
    [
        (
            "test_loop_boolop_runtime.py",
            [
                "    observed = None",
                "    for item in production_ast_items():",
                "        observed = item and calculate_art_7p_exemption",
                "    assert observed",
            ],
        ),
        (
            "test_comprehension_runtime.py",
            [
                "    observed = [",
                "        calculate_art_7p_exemption",
                "        for item in production_ast_items()",
                "        if item",
                "    ]",
                "    assert observed",
            ],
        ),
    ],
)
def test_central_harness_ownership_gate_rejects_unrelated_owner_in_structural_binding(
    tmp_path: Path,
    module_name: str,
    test_body: list[str],
) -> None:
    """Structural provenance cannot cover an unrelated value in one binding."""
    module = tmp_path / "cadrumo" / "tests" / module_name
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                "from ..domain.renta import calculate_art_7p_exemption",
                "from ._inventory import production_ast_items",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "def test_structural_binding() -> None:",
                *test_body,
            ]
        ),
        encoding="utf-8",
    )

    violation = _central_harness_owner_violation(module)

    assert violation is not None
    assert "::test_structural_binding:" in violation
    assert "hex_domain" in violation


def test_central_harness_ownership_gate_accepts_structural_item_data_bindings(
    tmp_path: Path,
) -> None:
    """Values derived from structural items retain their structural provenance."""
    module = tmp_path / "cadrumo" / "tests" / "test_structural_item_data.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                "from ._inventory import production_ast_items",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "def test_structural_item_data() -> None:",
                "    categories = [item.category for item in production_ast_items()]",
                "    modules = set()",
                "    for item in production_ast_items():",
                "        modules.add(item.module)",
                "    assert categories",
                "    assert modules",
            ]
        ),
        encoding="utf-8",
    )

    assert _central_harness_owner_violation(module) is None


def test_central_harness_ownership_gate_rejects_runtime_after_completed_support_context(
    tmp_path: Path,
) -> None:
    """A completed support context cannot cover a later owner assertion."""
    module = tmp_path / "cadrumo" / "tests" / "test_completed_support_context.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                "from ..domain.renta import calculate_art_7p_exemption",
                "from .secure_sql import isolated_runtime_profile",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "def test_completed_context(tmp_path) -> None:",
                "    with isolated_runtime_profile(tmp_path=tmp_path):",
                "        pass",
                "    assert calculate_art_7p_exemption",
            ]
        ),
        encoding="utf-8",
    )

    violation = _central_harness_owner_violation(module)

    assert violation is not None
    assert "::test_completed_context:" in violation
    assert "hex_domain" in violation


def test_central_harness_ownership_gate_rejects_bound_runtime_after_support_context(
    tmp_path: Path,
) -> None:
    """A value bound in a support context carries no evidence beyond its scope."""
    module = tmp_path / "cadrumo" / "tests" / "test_bound_in_completed_support_context.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                "from ..domain.renta import calculate_art_7p_exemption",
                "from .secure_sql import isolated_runtime_profile",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "def test_bound_after_context(tmp_path) -> None:",
                "    with isolated_runtime_profile(tmp_path=tmp_path):",
                "        observed = calculate_art_7p_exemption",
                "    assert observed",
            ]
        ),
        encoding="utf-8",
    )

    violation = _central_harness_owner_violation(module)

    assert violation is not None
    assert "::test_bound_after_context:" in violation
    assert "hex_domain" in violation


def test_central_harness_ownership_gate_accepts_related_owner_inside_support_context(
    tmp_path: Path,
) -> None:
    """A support context covers its related owner only inside its lexical body."""
    module = tmp_path / "cadrumo" / "tests" / "test_active_support_context.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                "from ..adapters.persistence.storage import has_active_bucket_session",
                "from .secure_sql import isolated_runtime_profile",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]",
                "",
                "def test_inside_context(tmp_path) -> None:",
                "    with isolated_runtime_profile(tmp_path=tmp_path):",
                "        assert has_active_bucket_session()",
            ]
        ),
        encoding="utf-8",
    )

    assert _central_harness_owner_violation(module) is None


def test_central_harness_ownership_gate_resolves_class_body_relative_imports(
    tmp_path: Path,
) -> None:
    """Class attributes cannot hide a relative production import from methods."""
    module = tmp_path / "cadrumo" / "tests" / "test_class_body_import.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]",
                "",
                "class TestClassBodyImport:",
                "    from ..domain import renta as imported_renta",
                "    runtime_owner = imported_renta",
                "",
                "    def test_runtime_owner(self) -> None:",
                "        assert self.runtime_owner.__dict__",
            ]
        ),
        encoding="utf-8",
    )

    violation = _central_harness_owner_violation(module)

    assert violation is not None
    assert "::TestClassBodyImport.test_runtime_owner:" in violation
    assert "hex_domain" in violation


def test_central_harness_ownership_gate_accepts_structural_and_cross_owner_controls(tmp_path: Path) -> None:
    """No production import and a multi-owner import graph remain central candidates."""
    structural = tmp_path / "cadrumo" / "tests" / "structural" / "test_inventory.py"
    structural.parent.mkdir(parents=True)
    structural.write_text(
        "import pytest\n\npytestmark = [pytest.mark.unit, pytest.mark.hex_core]\n",
        encoding="utf-8",
    )
    cross_owner = tmp_path / "cadrumo" / "tests" / "cross_owner" / "test_boundary.py"
    cross_owner.parent.mkdir(parents=True)
    cross_owner.write_text(
        "\n".join(
            [
                "import pytest",
                "from cadrumo.application.aggregation import CounterpartSourceKind as app_csk",
                "from cadrumo.domain.calculations.registry import CounterpartSourceKind as domain_csk",
                "",
                "pytestmark = [pytest.mark.integration, pytest.mark.hex_application]",
                "",
                "def test_public_identity_crosses_the_owner_boundary() -> None:",
                "    assert app_csk is domain_csk",
            ]
        ),
        encoding="utf-8",
    )

    assert _central_harness_owner_violation(structural) is None
    assert _central_harness_owner_violation(cross_owner) is None


def test_repo_relative_uses_posix_paths() -> None:
    """Repository-relative rendering is stable on Windows and POSIX."""
    assert repo_relative(Path(__file__).resolve()) == "src/cadrumo/tests/test_test_inventory.py"


def test_aeat_relative_uses_posix_package_paths() -> None:
    """Package-relative rendering is stable on Windows and POSIX."""
    assert aeat_relative(Path(__file__).resolve()) == "tests/test_test_inventory.py"


def test_repo_path_roundtrips_repo_relative() -> None:
    """A rendered relative path resolves back under the repository root."""
    current = Path(__file__).resolve()
    relative = repo_relative(current)

    assert repo_path(relative) == current
    assert repo_path(relative).is_relative_to(REPO_ROOT)


def test_production_python_files_excludes_tests_conftest_and_data() -> None:
    """Production source inventory has one shared scan surface."""
    files = production_python_files()

    assert repo_path("src/cadrumo/core/config.py") in files
    assert repo_path("src/cadrumo/conftest.py") not in files
    assert all("tests" not in path.relative_to(repo_path("src/cadrumo")).parts for path in files)
    assert all("_data" not in path.relative_to(repo_path("src/cadrumo")).parts for path in files)


def test_package_python_files_includes_tests_but_excludes_data_by_default() -> None:
    """Package inventory keeps tests in scope while excluding bundled data helpers."""
    files = package_python_files()

    assert Path(__file__).resolve() in files
    assert repo_path("src/cadrumo/core/config.py") in files
    assert all("_data" not in path.relative_to(repo_path("src/cadrumo")).parts for path in files)


def test_project_test_modules_discovers_dev_docs_tests_outside_source_tree() -> None:
    """Project-level test discovery includes dev/docs tests outside ``src/cadrumo``."""
    modules = project_test_modules()

    assert repo_path("dev/docs/tests/test_docs.py") in modules
    assert all("src" not in path.relative_to(REPO_ROOT).parts[:1] for path in modules)


def test_project_test_control_modules_cover_tests_support_and_exclude_production_helpers() -> None:
    """Project test-control discovery includes tests/support without docs tooling."""
    modules = project_test_control_modules()

    assert set(project_test_modules()) <= set(modules)
    assert repo_path("dev/docs/tests/test_docs.py") in modules
    assert repo_path("dev/docs/terminology/_sweep.py") not in modules
    assert all("src" not in path.relative_to(REPO_ROOT).parts[:1] for path in modules)


def test_project_test_control_modules_do_not_execute_control_flow_at_import_time() -> None:
    """Project-level test controls must keep collection import side-effect free."""
    allowed_top_level = (
        ast.Expr,
        ast.Import,
        ast.ImportFrom,
        ast.Assign,
        ast.AnnAssign,
        # A PEP 695 ``type X = ...`` statement is a declaration, and its value is
        # evaluated lazily rather than at import. So it does strictly LESS work at
        # import time than the ``Assign`` form above, which this gate has always
        # permitted -- omitting it flagged the newer spelling of a construct the
        # older spelling is allowed to use.
        ast.TypeAlias,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )
    violations: list[str] = []
    for path in project_test_control_modules():
        tree = ast_for_path(path)
        if not isinstance(tree, ast.Module):
            continue
        for node in tree.body:
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            if isinstance(node, allowed_top_level):
                continue
            violations.append(f"{repo_relative(path)}:{node.lineno}: {type(node).__name__}")

    assert not violations, "project test-control modules must not run control flow at import time:\n" + "\n".join(
        violations
    )


def test_non_test_package_python_files_excludes_test_tree_and_scan_excludes() -> None:
    """Non-test package inventory keeps conftest by default and honors rel excludes."""
    files = non_test_package_python_files(include_data=True, scan_excludes={"core/config.py"})

    assert repo_path("src/cadrumo/core/config.py") not in files
    assert repo_path("src/cadrumo/conftest.py") in files
    assert all(not path.name.startswith("test_") for path in files)
    assert all("tests" not in path.relative_to(SRC_CADRUMO).parts for path in files)


def test_non_test_python_files_under_handles_direct_files_and_package_dirs() -> None:
    """Scoped non-test inventory supports file and directory inputs."""
    config_path = repo_path("src/cadrumo/core/config.py")
    tests_dir = repo_path("src/cadrumo/tests")

    assert non_test_python_files_under(config_path) == (config_path,)
    assert non_test_python_files_under(tests_dir) == ()
    assert config_path in non_test_python_files_under(repo_path("src/cadrumo/core"))


def test_production_ast_items_filters_cache_to_production_package_files(tmp_path: Path) -> None:
    """Production AST iteration shares the production-file surface."""
    config_path = repo_path("src/cadrumo/core/config.py")
    config_tree = ast_for_path(config_path)
    assert config_tree is not None
    test_tree = ast.parse("def test_example(): pass")
    external_path = tmp_path / "external.py"
    external_tree = ast.parse("value = 1")

    assert production_ast_items(
        {
            config_path: config_tree,
            Path(__file__).resolve(): test_tree,
            external_path: external_tree,
        },
    ) == ((config_path, config_tree),)


def test_package_ast_items_reuses_cache_for_test_modules() -> None:
    """Package AST iteration includes test modules and reuses cached trees."""
    current = Path(__file__).resolve()
    current_tree = ast.parse("CURRENT = True")
    config_path = repo_path("src/cadrumo/core/config.py")
    config_tree = ast.parse("CONFIG = True")

    items = dict(package_ast_items({current: current_tree, config_path: config_tree}))

    assert items[current] is current_tree
    assert items[config_path] is config_tree


def test_module_name_renders_importable_aeat_modules() -> None:
    """Module-name rendering handles ordinary modules and package initializers."""
    assert module_name(repo_path("src/cadrumo/core/config.py")) == "cadrumo.core.config"
    assert module_name(repo_path("src/cadrumo/application/__init__.py")) == "cadrumo.application"


def test_ast_for_path_prefers_supplied_cache(tmp_path: Path) -> None:
    """AST lookup reuses the caller's cache before touching the file."""
    path = tmp_path / "module.py"
    path.write_text("BROKEN =", encoding="utf-8")
    cached = ast.parse("value = 1", filename=str(path))

    assert ast_for_path(path, {path: cached}) is cached


def test_ast_for_path_falls_back_to_real_parse(tmp_path: Path) -> None:
    """AST lookup parses a real source file when no cache entry exists."""
    path = tmp_path / "module.py"
    path.write_text("value = 1\n", encoding="utf-8")

    tree = ast_for_path(path)
    cached_tree = ast_for_path(path)

    assert isinstance(tree, ast.Module)
    assert isinstance(tree.body[0], ast.Assign)
    assert cached_tree is tree


def test_ast_for_path_returns_none_for_unparseable_source(tmp_path: Path) -> None:
    """Invalid Python source is reported as absent rather than hidden by a fake tree."""
    path = tmp_path / "module.py"
    path.write_text("value =", encoding="utf-8")

    assert ast_for_path(path) is None


def test_qualified_name_renders_call_name_attribute_chains() -> None:
    """Qualified-name rendering handles the AST shapes guard tests scan."""
    call_stmt = ast.parse("pytest.mark.skipif(True)").body[0]
    assert isinstance(call_stmt, ast.Expr)
    call_expr = call_stmt.value
    assert isinstance(call_expr, ast.Call)

    assert qualified_name(call_expr) == "pytest.mark.skipif"
    assert qualified_name(call_expr.func) == "pytest.mark.skipif"
    name_stmt = ast.parse("name").body[0]
    assert isinstance(name_stmt, ast.Expr)
    assert qualified_name(name_stmt.value) == "name"


def test_cast_call_linenos_detects_real_cast_shapes() -> None:
    """Cast-call discovery detects supported AST shapes without text matching."""
    tree = ast.parse(
        "\n".join(
            [
                "value = cast(str, raw)",
                "other = typing.cast(int, raw)",
                "third = t.cast(float, raw)",
                "ignored = helper.cast(raw)",
            ],
        ),
    )

    assert list(cast_call_linenos(tree)) == [1, 2, 3]


def test_marker_lookup_accepts_same_line_and_leading_comment_block() -> None:
    """Marker lookup follows only the adjacent blank/comment block."""
    assert has_marker_on_line_or_adjacent_comment_block(
        ["# CAST-RATIONALE-TEST: documented", "", "value = cast(str, raw)"],
        3,
        "CAST-RATIONALE-",
    )
    assert has_marker_on_line_or_adjacent_comment_block(
        ["value = cast(str, raw)  # CAST-RATIONALE-TEST"],
        1,
        "CAST-RATIONALE-",
    )
    assert not has_marker_on_line_or_adjacent_comment_block(
        ["# CAST-RATIONALE-TEST: too far", "other = 1", "value = cast(str, raw)"],
        3,
        "CAST-RATIONALE-",
    )


def test_cast_rationale_violations_ignore_out_of_tree_cache_entries(tmp_path: Path) -> None:
    """Cast-rationale inventory only evaluates package production files."""
    path = tmp_path / "external.py"
    path.write_text("value = cast(str, raw)\n", encoding="utf-8")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert cast_rationale_violations({path: tree}) == []


def test_regex_line_hits_reports_repo_relative_matches_and_skips_comments(tmp_path: Path) -> None:
    """Regex scan helper reports real source lines while ignoring comment-only hits."""
    path = tmp_path / "module.py"
    path.write_text('# token\nvalue = "token"\n', encoding="utf-8")

    assert regex_line_hits([path], re.compile("token")) == [f"{path.as_posix()}:2: 'token'"]


def test_regex_line_hits_can_include_comment_lines(tmp_path: Path) -> None:
    """Callers can opt into comment-line matches for textual inventory tests."""
    path = tmp_path / "module.py"
    path.write_text("# token\n", encoding="utf-8")

    assert regex_line_hits([path], re.compile("token"), skip_comment_lines=False) == [
        f"{path.as_posix()}:1: 'token'",
    ]


def test_bare_utf8_literal_violations_ignore_hash_protocol_lines(tmp_path: Path) -> None:
    """UTF-8 inventory reports text I/O literals while preserving hash-protocol escapes."""
    path = tmp_path / "module.py"
    path.write_text(
        "\n".join(
            [
                'payload = path.read_text(encoding="utf-8")',
                'digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()',
                'body = data.decode("utf-8")',
            ],
        ),
        encoding="utf-8",
    )

    assert bare_utf8_literal_violations(path) == [
        (1, 'payload = path.read_text(encoding="utf-8")'),
        (3, 'body = data.decode("utf-8")'),
    ]
