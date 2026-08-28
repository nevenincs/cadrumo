"""Structural discovery for source capabilities that may feed modelo casillas.

Discovery is intentionally syntax-driven and produces evidence locators.  It
does not decide that a repository's payload is legally equivalent to a casilla;
that decision belongs to the reviewed connectivity census.
"""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from cadrumo.domain.calculations.registry.authority import bundled_authority

if TYPE_CHECKING:
    from cadrumo.application.registry.source_connectivity import SourceConnectivityCensusManifest

type SecureRepositoryMechanism = Literal["secure_bound", "profile_secure_document", "secure_object"]
type IngressChannel = Literal["cli", "worksheet"]

_SECURE_NAMES = frozenset(
    {
        "ProfileBareModelSecurePersistence",
        "SecureBoundRepository",
        "SecureObjectRepository",
        "_SecureBoundRepository",
        "resolve_profile_secure_object_repository",
        "secure_object_repository_for_bucket",
    }
)


@dataclass(frozen=True, slots=True)
class SecureRepositoryCapability:
    """One typed production repository backed by encrypted secure storage."""

    module: str
    repository_name: str
    line: int
    mechanism: SecureRepositoryMechanism
    payload_types: tuple[str, ...]
    aggregate_grain: str

    @property
    def evidence_locator(self) -> str:
        """Return a re-fetchable source locator for review and census rows."""
        return f"{self.module}:{self.line}"

    @property
    def capability_id(self) -> str:
        """Return the stable structural identity independent of source line."""
        return f"secure_repository:{self.module}:{self.repository_name}"


@dataclass(frozen=True, slots=True)
class IngressCapability:
    """One supported operator write surface that can introduce source data."""

    module: str
    callback_name: str
    line: int
    channel: IngressChannel
    command_group_symbol: str
    command_name: str
    execution_policy: str
    declaration_module: str | None = None

    @property
    def evidence_locator(self) -> str:
        """Return a re-fetchable source locator for review and census rows."""
        return f"{self.declaration_module or self.module}:{self.line}"

    @property
    def capability_id(self) -> str:
        """Return the stable structural identity independent of source line."""
        return f"ingress:{self.module}:{self.callback_name}"


@dataclass(frozen=True, slots=True)
class CalculationHelperCapability:
    """One exported domain helper that performs typed arithmetic or aggregation."""

    module: str
    function_name: str
    line: int
    return_type: str
    operation_kinds: tuple[str, ...]

    @property
    def evidence_locator(self) -> str:
        """Return a re-fetchable source locator for review and census rows."""
        return f"{self.module}:{self.line}"

    @property
    def capability_id(self) -> str:
        """Return the stable structural identity independent of source line."""
        return f"calculation_helper:{self.module}:{self.function_name}"


@dataclass(frozen=True, slots=True)
class SourceReadinessCapability:
    """One explicit source-readiness declaration function."""

    module: str
    function_name: str
    line: int
    readiness_type: str
    source_kind_expression: str

    @property
    def evidence_locator(self) -> str:
        """Return a re-fetchable source locator for review and census rows."""
        return f"{self.module}:{self.line}"

    @property
    def capability_id(self) -> str:
        """Return the stable structural identity independent of source line."""
        return f"source_readiness:{self.module}:{self.function_name}"


@dataclass(frozen=True, slots=True)
class RowAssemblerCapability:
    """One registry row grouping and its typed application assembler."""

    module: str
    grouping: str
    source_kind: str
    assembler_name: str
    observation_return_type: str
    line: int

    @property
    def capability_id(self) -> str:
        """Return the stable grouping identity independent of dispatch line."""
        return f"row_assembler:{self.grouping}"


@dataclass(frozen=True, slots=True)
class SourceOwnershipCapability:
    """One source kind owned by the canonical production calculation route."""

    source_kind: str
    resolver_id: str
    resolver_type: str | None
    stage: str

    @property
    def capability_id(self) -> str:
        """Return the stable source-kind identity independent of resolver placement."""
        return f"source_ownership:{self.source_kind}"


@dataclass(frozen=True, slots=True)
class LexicalDestinationAdvisory:
    """Non-authoritative token overlap between a capability and a casilla."""

    capability_kind: str
    capability_locator: str
    modelo_id: str
    revision_id: str
    casilla_id: str
    shared_tokens: tuple[str, ...]
    advisory_only: Literal[True] = True


def _production_python_files(source_root: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(source_root.rglob("*.py"))
        if "tests" not in path.relative_to(source_root).parts and path.name != "__init__.py"
    )


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _dotted_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    if isinstance(node, ast.Subscript):
        return _dotted_name(node.value)
    return ""


def _class_names(node: ast.ClassDef) -> frozenset[str]:
    return frozenset(name.rsplit(".", maxsplit=1)[-1] for child in ast.walk(node) if (name := _dotted_name(child)))


def _self_attribute_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return node.attr
    return None


def _constructor_uses_secure_object_store_port(node: ast.ClassDef) -> bool:
    constructor = next(
        (child for child in node.body if isinstance(child, ast.FunctionDef) and child.name == "__init__"),
        None,
    )
    if constructor is None:
        return False
    arguments = (*constructor.args.posonlyargs, *constructor.args.args, *constructor.args.kwonlyargs)
    secure_arguments = {
        argument.arg
        for argument in arguments
        if argument.arg != "self"
        and argument.annotation is not None
        and any(
            _dotted_name(part).rsplit(".", maxsplit=1)[-1].endswith("SecureObjectStorePort")
            for part in ast.walk(argument.annotation)
        )
    }
    if not secure_arguments:
        return False
    secure_attributes = {
        attribute
        for child in ast.walk(constructor)
        if isinstance(child, (ast.Assign, ast.AnnAssign))
        for target in (child.targets if isinstance(child, ast.Assign) else (child.target,))
        if (attribute := _self_attribute_name(target)) is not None
        and child.value is not None
        and any(isinstance(part, ast.Name) and part.id in secure_arguments for part in ast.walk(child.value))
    }
    if not secure_attributes:
        return False
    for method in node.body:
        if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) or method.name == "__init__":
            continue
        for call in (child for child in ast.walk(method) if isinstance(child, ast.Call)):
            receiver = _self_attribute_name(call.func.value) if isinstance(call.func, ast.Attribute) else None
            if receiver in secure_attributes:
                return True
            call_inputs = (*call.args, *(keyword.value for keyword in call.keywords))
            if any(
                _self_attribute_name(part) in secure_attributes
                for call_input in call_inputs
                for part in ast.walk(call_input)
            ):
                return True
    return False


def _secure_mechanism(node: ast.ClassDef) -> SecureRepositoryMechanism | None:
    base_names = {_dotted_name(base).rsplit(".", maxsplit=1)[-1] for base in node.bases}
    if base_names & {"SecureBoundRepository", "_SecureBoundRepository"}:
        return "secure_bound"
    names = _class_names(node)
    if "ProfileBareModelSecurePersistence" in names:
        return "profile_secure_document"
    if names & _SECURE_NAMES or _constructor_uses_secure_object_store_port(node):
        return "secure_object"
    return None


def _payload_types(node: ast.ClassDef) -> tuple[str, ...]:
    payloads: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Subscript) and _dotted_name(base.value).rsplit(".", maxsplit=1)[-1] in {
            "SecureBoundRepository",
            "_SecureBoundRepository",
        }:
            payloads.add(ast.unparse(base.slice))
    for child in ast.walk(node):
        if isinstance(child, ast.keyword) and child.arg == "model_type":
            payloads.add(ast.unparse(child.value))
        if isinstance(child, (ast.Assign, ast.AnnAssign)):
            targets = child.targets if isinstance(child, ast.Assign) else [child.target]
            value = child.value
            if value is not None and any(
                isinstance(target, ast.Name) and target.id == "payload_type" for target in targets
            ):
                payloads.add(ast.unparse(value))
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name in {
            "add",
            "create",
            "load",
            "record",
            "save",
            "upsert",
        }:
            annotations = [child.returns, *(argument.annotation for argument in child.args.args[1:])]
            for annotation in annotations:
                if annotation is None:
                    continue
                for name in (_dotted_name(part).rsplit(".", maxsplit=1)[-1] for part in ast.walk(annotation)):
                    if name and name not in {
                        "None",
                        "Path",
                        "bool",
                        "bytes",
                        "dict",
                        "int",
                        "list",
                        "str",
                        "tuple",
                    }:
                        payloads.add(name)
    return tuple(sorted(payloads))


def _aggregate_grain(node: ast.ClassDef, mechanism: SecureRepositoryMechanism) -> str:
    for child in ast.walk(node):
        if isinstance(child, ast.keyword) and child.arg == "definition":
            return f"namespace_definition:{ast.unparse(child.value)}"
    if mechanism == "secure_bound":
        extractor = next(
            (child for child in node.body if isinstance(child, ast.FunctionDef) and child.name == "extract_identifier"),
            None,
        )
        return "natural_identifier:extract_identifier" if extractor is not None else "natural_identifier:inherited"
    names = sorted(
        {
            name
            for child in ast.walk(node)
            if isinstance(child, ast.Name)
            and ((name := child.id).endswith("_NAMESPACE") or name.lower().endswith(("_key", "_object_key")))
        }
    )
    if names:
        return "declared_key:" + ",".join(names)
    return "secure_object_key:repository_declared"


def discover_secure_repositories(repo_root: Path) -> tuple[SecureRepositoryCapability, ...]:
    """Enumerate typed production repositories that structurally use secure storage."""
    source_root = repo_root / "src" / "cadrumo"
    capabilities: list[SecureRepositoryCapability] = []
    for path in _production_python_files(source_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or not node.name.endswith(("Repository", "Storage")):
                continue
            mechanism = _secure_mechanism(node)
            if mechanism is None:
                continue
            payload_types = _payload_types(node)
            if not payload_types:
                continue
            capabilities.append(
                SecureRepositoryCapability(
                    module=path.relative_to(repo_root).as_posix(),
                    repository_name=node.name,
                    line=node.lineno,
                    mechanism=mechanism,
                    payload_types=payload_types,
                    aggregate_grain=_aggregate_grain(node, mechanism),
                )
            )
    return tuple(sorted(capabilities, key=lambda item: (item.module, item.repository_name, item.line)))


def _command_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.Call | None:
    return next(
        (
            decorator
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "command"
        ),
        None,
    )


def _execution_policy(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or _dotted_name(decorator.func).rsplit(".", maxsplit=1)[-1] != (
            "command_execution_policy"
        ):
            continue
        if decorator.args:
            return ast.unparse(decorator.args[0])
    return None


def _string_value(node: ast.AST, bindings: dict[str, ast.AST] | None = None) -> str | None:
    bindings = bindings or {}
    if isinstance(node, ast.Name) and node.id in bindings:
        return _string_value(bindings[node.id], bindings)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        for value in node.values:
            if (resolved := _string_value(value, bindings)) is not None:
                return resolved
        return None
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "replace"
        and len(node.args) == 2
        and not node.keywords
    ):
        source = _string_value(node.func.value, bindings)
        old = _string_value(node.args[0], bindings)
        new = _string_value(node.args[1], bindings)
        if source is not None and old is not None and new is not None:
            return source.replace(old, new)
        return None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                resolved = _string_value(value.value, bindings)
                if resolved is None:
                    return None
                parts.append(resolved)
            else:
                return None
        return "".join(parts)
    return None


def _call_bindings(function: ast.FunctionDef, call: ast.Call) -> dict[str, ast.AST]:
    names = [argument.arg for argument in function.args.args]
    bound: dict[str, ast.AST] = dict(zip(names, call.args, strict=False))
    bound.update({keyword.arg: keyword.value for keyword in call.keywords if keyword.arg is not None})
    defaults = function.args.defaults
    for argument, default in zip(function.args.args[-len(defaults) :], defaults, strict=False):
        bound.setdefault(argument.arg, default)
    for argument, default in zip(function.args.kwonlyargs, function.args.kw_defaults, strict=False):
        if default is not None:
            bound.setdefault(argument.arg, default)
    return bound


def _function_bindings(function: ast.FunctionDef, call: ast.Call) -> dict[str, ast.AST]:
    """Resolve declared defaults and local aliases without executing a command spec."""
    bindings = _call_bindings(function, call)
    for statement in function.body:
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            bindings[statement.targets[0].id] = statement.value
    return bindings


def _call_argument(
    call: ast.Call,
    name: str,
    position: int,
    bindings: dict[str, ast.AST],
) -> ast.AST:
    """Resolve one constructor argument from keyword or canonical positional form."""
    keyword = next((item.value for item in call.keywords if item.arg == name), None)
    value = keyword if keyword is not None else call.args[position]
    if isinstance(value, ast.Name) and value.id in bindings:
        return bindings[value.id]
    return value


def _deferred_handler_target(
    expression: ast.AST,
    functions: dict[str, ast.FunctionDef],
    bindings: dict[str, ast.AST] | None = None,
) -> tuple[str, str] | None:
    bindings = bindings or {}
    if isinstance(expression, ast.Call) and (helper := functions.get(_dotted_name(expression.func))) is not None:
        return _deferred_handler_target(helper, functions, _function_bindings(helper, expression) | bindings)
    for node in ast.walk(expression):
        if not isinstance(node, ast.Call) or _dotted_name(node.func).rsplit(".", maxsplit=1)[-1] != "DeferredTarget":
            continue
        if len(node.args) < 2:
            continue
        module = _string_value(node.args[0], bindings)
        handler = _string_value(node.args[1], bindings)
        if module and handler and module.startswith("cadrumo.entrypoints.cli"):
            return module, handler
    return None


def _write_policy_names(cli_root: Path) -> frozenset[str]:
    names: set[str] = set()
    for path in _production_python_files(cli_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if value is None or "local-state" not in {
                child.value
                for child in ast.walk(value)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            }:
                continue
            names.update(target.id for target in targets if isinstance(target, ast.Name))
    return frozenset(names)


def _module_level_bindings(tree: ast.Module) -> dict[str, ast.AST]:
    """Bind module-level ``NAME = <expr>`` assignments for structural resolution.

    A command-spec module routinely hoists the handler's dotted module path to a
    module-level constant and passes that NAME into its ``_leaf`` wrapper. The
    wrapper's own parameter bindings cannot see it, so resolution returned
    ``None`` for the handler target and the walk raised as if the spec were
    unresolvable. Seeding the module scope resolves the name the same way the
    interpreter would, without executing the module.
    """
    bindings: dict[str, ast.AST] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if statement.value is not None:
                bindings[statement.target.id] = statement.value
    return bindings


def _command_spec_ingress(repo_root: Path, cli_root: Path) -> tuple[IngressCapability, ...]:
    write_policies = _write_policy_names(cli_root)
    capabilities: list[IngressCapability] = []
    for path in _production_python_files(cli_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        leaf_wrapper = functions.get("_leaf")
        module_bindings = _module_level_bindings(tree)
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            call_name = _dotted_name(call.func).rsplit(".", maxsplit=1)[-1]
            bindings: dict[str, ast.AST] = dict(module_bindings)
            command_call = call
            if call_name == "_leaf" and leaf_wrapper is not None:
                bindings = module_bindings | _function_bindings(leaf_wrapper, call)
                command_call = next(
                    (
                        child
                        for child in ast.walk(leaf_wrapper)
                        if isinstance(child, ast.Call)
                        and _dotted_name(child.func).rsplit(".", maxsplit=1)[-1] == "CommandSpec"
                    ),
                    call,
                )
            elif call_name != "CommandSpec":
                continue
            kind = _string_value(_call_argument(command_call, "kind", 3, bindings), bindings)
            policy_node = _call_argument(command_call, "policy", 8, bindings)
            policy = _dotted_name(policy_node) if policy_node is not None else ""
            if kind != "leaf" or policy.rsplit(".", maxsplit=1)[-1] not in write_policies:
                continue
            target = _deferred_handler_target(_call_argument(command_call, "handler", 9, bindings), functions, bindings)
            token = _string_value(_call_argument(command_call, "token", 2, bindings), bindings)
            parent = _string_value(_call_argument(command_call, "parent_key", 1, bindings), bindings)
            if target is None or token is None or parent is None:
                raise ValueError(f"write command spec cannot be resolved structurally: {path}:{call.lineno}")
            module_name, handler_name = target
            module_path = f"src/{module_name.replace('.', '/')}.py"
            capabilities.append(
                IngressCapability(
                    module=module_path,
                    callback_name=handler_name,
                    line=call.lineno,
                    channel="cli",
                    command_group_symbol=parent,
                    command_name=token,
                    execution_policy=policy,
                    declaration_module=path.relative_to(repo_root).as_posix(),
                )
            )
    return tuple(capabilities)


def discover_ingress_surfaces(repo_root: Path) -> tuple[IngressCapability, ...]:
    """Enumerate policy-declared CLI writes, distinguishing worksheet pulls."""
    cli_root = repo_root / "src" / "cadrumo" / "entrypoints" / "cli"
    capabilities: list[IngressCapability] = []
    for path in _production_python_files(cli_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            command = _command_decorator(node)
            policy = _execution_policy(node)
            if command is None or policy is None or "WRITE" not in policy:
                continue
            assert isinstance(command.func, ast.Attribute)
            group = _dotted_name(command.func.value)
            command_name = node.name
            if command.args and isinstance(command.args[0], ast.Constant) and isinstance(command.args[0].value, str):
                command_name = command.args[0].value
            called_names = {_dotted_name(child).rsplit(".", maxsplit=1)[-1] for child in ast.walk(node)}
            channel: IngressChannel = (
                "worksheet"
                if called_names & {"_pull_operator_edits_for_command", "assemble_observations_for_grouping"}
                else "cli"
            )
            capabilities.append(
                IngressCapability(
                    module=path.relative_to(repo_root).as_posix(),
                    callback_name=node.name,
                    line=node.lineno,
                    channel=channel,
                    command_group_symbol=group,
                    command_name=command_name,
                    execution_policy=policy,
                )
            )
    by_id = {row.capability_id: row for row in capabilities}
    for row in _command_spec_ingress(repo_root, cli_root):
        by_id[row.capability_id] = row
    return tuple(sorted(by_id.values(), key=lambda item: (item.module, item.line, item.callback_name)))


def _exported_symbols(source_root: Path) -> frozenset[str]:
    exported: set[str] = set()
    for path in sorted(source_root.rglob("__init__.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                continue
            exported.update(
                child.value for child in node.elts if isinstance(child, ast.Constant) and isinstance(child.value, str)
            )
    return frozenset(exported)


def discover_calculation_helpers(repo_root: Path) -> tuple[CalculationHelperCapability, ...]:
    """Enumerate public domain functions with structural calculation behavior.

    Package facades expose selected private-module definitions through
    ``__all__``.  A non-private module is itself a public definition surface,
    so its public functions remain discoverable even when the package root is
    intentionally inert and does not redeclare them.
    """
    domain_root = repo_root / "src" / "cadrumo" / "domain"
    exported = _exported_symbols(domain_root)
    capabilities: list[CalculationHelperCapability] = []
    for path in sorted(domain_root.rglob("*.py")):
        if "tests" in path.relative_to(domain_root).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative_parts = path.relative_to(domain_root).parts
        module_is_public = (
            path.name not in {"__init__.py", "conftest.py"}
            and not path.name.startswith("_")
            and all(not part.startswith("_") for part in relative_parts[:-1])
        )
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_") or (not module_is_public and node.name not in exported):
                continue
            binary_operations = {
                type(child.op).__name__ for child in ast.walk(node) if isinstance(child, (ast.BinOp, ast.AugAssign))
            }
            aggregate_calls = {
                name
                for child in ast.walk(node)
                if isinstance(child, ast.Call)
                and (name := _dotted_name(child.func).rsplit(".", maxsplit=1)[-1])
                in {"Decimal", "max", "min", "quantize", "sum"}
            }
            operation_kinds = tuple(sorted(binary_operations | {f"call:{name}" for name in aggregate_calls}))
            if not operation_kinds or node.returns is None:
                continue
            capabilities.append(
                CalculationHelperCapability(
                    module=path.relative_to(repo_root).as_posix(),
                    function_name=node.name,
                    line=node.lineno,
                    return_type=ast.unparse(node.returns),
                    operation_kinds=operation_kinds,
                )
            )
    return tuple(sorted(capabilities, key=lambda item: (item.module, item.line, item.function_name)))


def discover_source_readiness(repo_root: Path) -> tuple[SourceReadinessCapability, ...]:
    """Enumerate functions that construct an explicit ready/source-kind record."""
    source_root = repo_root / "src" / "cadrumo"
    capabilities: list[SourceReadinessCapability] = []
    for path in _production_python_files(source_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.returns is None:
                continue
            readiness_type = ast.unparse(node.returns)
            constructor = next(
                (
                    child
                    for child in ast.walk(node)
                    if isinstance(child, ast.Call)
                    and {keyword.arg for keyword in child.keywords} >= {"ready", "source_kind"}
                ),
                None,
            )
            if constructor is None:
                continue
            source_keyword = next(keyword for keyword in constructor.keywords if keyword.arg == "source_kind")
            capabilities.append(
                SourceReadinessCapability(
                    module=path.relative_to(repo_root).as_posix(),
                    function_name=node.name,
                    line=node.lineno,
                    readiness_type=readiness_type,
                    source_kind_expression=ast.unparse(source_keyword.value),
                )
            )
    return tuple(sorted(capabilities, key=lambda item: (item.module, item.line, item.function_name)))


def discover_row_assemblers(repo_root: Path) -> tuple[RowAssemblerCapability, ...]:
    """Derive row-grouping dispatch to typed assembler records from its canonical module."""
    path = repo_root / "src" / "cadrumo" / "application" / "calculations" / "row_set_assembly.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    dispatch_assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "_GROUPING_DISPATCH"
        and isinstance(node.value, ast.Dict)
    )
    dispatch_value = dispatch_assignment.value
    assert isinstance(dispatch_value, ast.Dict)
    grouping_members = [
        (key.value, ast.unparse(value))
        for key, value in zip(dispatch_value.keys, dispatch_value.values, strict=True)
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    ]
    dispatcher = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "assemble_observations_for_grouping"
    )
    assemblers_by_member: dict[str, tuple[str, int]] = {}
    for child in ast.walk(dispatcher):
        if not isinstance(child, ast.If) or not isinstance(child.test, ast.Compare) or len(child.test.comparators) != 1:
            continue
        member = ast.unparse(child.test.comparators[0])
        returned_call = next(
            (
                nested
                for nested in ast.walk(child)
                if isinstance(nested, ast.Call)
                and _dotted_name(nested.func).rsplit(".", maxsplit=1)[-1].startswith("assemble_")
                and _dotted_name(nested.func).rsplit(".", maxsplit=1)[-1] != "assemble_observations_for_grouping"
            ),
            None,
        )
        if returned_call is not None:
            assemblers_by_member[member] = (_dotted_name(returned_call.func).rsplit(".", maxsplit=1)[-1], child.lineno)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    records: list[RowAssemblerCapability] = []
    for grouping, member in grouping_members:
        assembler_name, line = assemblers_by_member[member]
        assembler = functions[assembler_name]
        records.append(
            RowAssemblerCapability(
                module=path.relative_to(repo_root).as_posix(),
                grouping=grouping,
                source_kind=member,
                assembler_name=assembler_name,
                observation_return_type=ast.unparse(assembler.returns) if assembler.returns is not None else "",
                line=line,
            )
        )
    return tuple(sorted(records, key=lambda item: (item.grouping, item.source_kind)))


def discover_source_ownership() -> tuple[SourceOwnershipCapability, ...]:
    """Project source ownership from the canonical live calculation route."""
    from cadrumo.application.modelo.calculation_route import CALCULATION_ROUTE_RESOLVER_OWNERSHIP

    return tuple(
        SourceOwnershipCapability(
            source_kind=source.value,
            resolver_id=row.resolver_id,
            resolver_type=None if row.resolver_type is None else row.resolver_type.__name__,
            stage=row.stage,
        )
        for row in CALCULATION_ROUTE_RESOLVER_OWNERSHIP
        for source in row.owned_sources
    )


def discovered_source_capability_ids(repo_root: Path) -> tuple[str, ...]:
    """Return the collision-free union of every structural capability identity."""
    capability_ids = tuple(
        row.capability_id
        for rows in (
            discover_secure_repositories(repo_root),
            discover_ingress_surfaces(repo_root),
            discover_calculation_helpers(repo_root),
            discover_source_readiness(repo_root),
            discover_row_assemblers(repo_root),
            discover_source_ownership(),
        )
        for row in rows
    )
    if len(set(capability_ids)) != len(capability_ids):
        duplicates = sorted(
            capability_id for capability_id in set(capability_ids) if capability_ids.count(capability_id) > 1
        )
        raise ValueError(f"source capability identities collide: {duplicates!r}")
    return tuple(sorted(capability_ids))


def discovered_source_capability_evidence(repo_root: Path) -> dict[str, str]:
    """Map every stable capability identity to its current review locator."""
    evidence: dict[str, str] = {}
    located_rows = (
        *discover_secure_repositories(repo_root),
        *discover_ingress_surfaces(repo_root),
        *discover_calculation_helpers(repo_root),
        *discover_source_readiness(repo_root),
    )
    evidence.update((row.capability_id, row.evidence_locator) for row in located_rows)
    evidence.update((row.capability_id, f"{row.module}:{row.line}") for row in discover_row_assemblers(repo_root))
    evidence.update(
        (row.capability_id, "src/cadrumo/application/modelo/calculation_route.py")
        for row in discover_source_ownership()
    )
    if len(evidence) != len(discovered_source_capability_ids(repo_root)):
        raise ValueError("source capability evidence map does not cover discovery exactly")
    return dict(sorted(evidence.items()))


_COVERAGE_SELECTOR_PREFIXES = {
    "remaining_calculation_helpers": "calculation_helper:",
    "remaining_ingress_surfaces": "ingress:",
    "remaining_row_assemblers": "row_assembler:",
    "remaining_secure_repositories": "secure_repository:",
    "remaining_source_ownership": "source_ownership:",
    "remaining_source_readiness": "source_readiness:",
}


def _capability_digest(capability_ids: tuple[str, ...]) -> str:
    payload = "".join(f"{capability_id}\n" for capability_id in sorted(capability_ids))
    return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}"


def assign_capabilities_to_census(
    capability_ids: tuple[str, ...],
    manifest: SourceConnectivityCensusManifest,
) -> dict[str, tuple[str, ...]]:
    """Assign every discovered capability exactly once or refuse census drift."""
    entries = manifest.entries
    discovered = set(capability_ids)
    assignments: dict[str, tuple[str, ...]] = {}
    explicitly_claimed: set[str] = set()

    for entry in entries:
        if entry.capability_selector is not None:
            continue
        claimed = set(entry.capability_ids)
        unknown = claimed - discovered
        if unknown:
            raise ValueError(f"census claims undiscovered capabilities: {sorted(unknown)!r}")
        overlap = explicitly_claimed & claimed
        if overlap:
            raise ValueError(f"capabilities have multiple explicit census rows: {sorted(overlap)!r}")
        explicitly_claimed.update(claimed)
        assignments[entry.candidate_id] = tuple(sorted(claimed))

    selector_claimed: set[str] = set()
    for entry in entries:
        selector = entry.capability_selector
        if selector is None:
            continue
        prefix = _COVERAGE_SELECTOR_PREFIXES[selector]
        claimed = tuple(
            sorted(
                capability_id for capability_id in discovered - explicitly_claimed if capability_id.startswith(prefix)
            )
        )
        actual_digest = _capability_digest(claimed)
        if actual_digest != entry.expected_capability_digest:
            raise ValueError(
                f"capability coverage drift for {entry.candidate_id}: "
                f"expected {entry.expected_capability_digest}, got {actual_digest}"
            )
        if entry.expected_capability_count is not None and len(claimed) != entry.expected_capability_count:
            raise ValueError(
                f"capability coverage count drift for {entry.candidate_id}: "
                f"expected {entry.expected_capability_count}, got {len(claimed)}"
            )
        overlap = selector_claimed.intersection(claimed)
        if overlap:
            raise ValueError(f"capabilities match multiple census selectors: {sorted(overlap)!r}")
        selector_claimed.update(claimed)
        assignments[entry.candidate_id] = claimed

    unclaimed = discovered - explicitly_claimed - selector_claimed
    if unclaimed:
        raise ValueError(f"discovered capabilities lack a census row: {sorted(unclaimed)!r}")
    return assignments


def validate_census_completeness(repo_root: Path) -> dict[str, tuple[str, ...]]:
    """Validate the bundled census against independent live-tree discovery."""
    from cadrumo.application.registry.source_connectivity import load_source_connectivity_census

    manifest = load_source_connectivity_census()
    return assign_capabilities_to_census(discovered_source_capability_ids(repo_root), manifest)


_LEXICAL_STOPWORDS = frozenset(
    {
        "aggregate",
        "aggregation",
        "calculation",
        "capability",
        "casilla",
        "catalogue",
        "compute",
        "document",
        "importe",
        "ledger",
        "modelo",
        "observation",
        "payload",
        "profile",
        "record",
        "repository",
        "secure",
        "source",
        "total",
    }
)


def _lexical_tokens(value: str) -> frozenset[str]:
    expanded = re.sub(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])", " ", value)
    return frozenset[str](
        token for token in re.findall(r"[a-záéíóúñ]{4,}", expanded.lower()) if token not in _LEXICAL_STOPWORDS
    )


def discover_lexical_destination_advisories(repo_root: Path) -> tuple[LexicalDestinationAdvisory, ...]:
    """Emit report-only token overlaps; never infer binding identity or equivalence."""
    capability_phrases: list[tuple[str, str, str]] = []
    capability_phrases.extend(
        ("secure_repository", row.evidence_locator, " ".join((row.repository_name, *row.payload_types)))
        for row in discover_secure_repositories(repo_root)
    )
    capability_phrases.extend(
        ("calculation_helper", row.evidence_locator, f"{row.function_name} {row.return_type}")
        for row in discover_calculation_helpers(repo_root)
    )
    capability_phrases.extend(
        ("source_readiness", row.evidence_locator, f"{row.function_name} {row.source_kind_expression}")
        for row in discover_source_readiness(repo_root)
    )
    capability_phrases.extend(
        ("row_assembler", f"{row.module}:{row.line}", f"{row.grouping} {row.observation_return_type}")
        for row in discover_row_assemblers(repo_root)
    )
    capability_token_sets = tuple(
        (capability_kind, locator, _lexical_tokens(phrase))
        for capability_kind, locator, phrase in capability_phrases
        if _lexical_tokens(phrase)
    )

    advisories: list[LexicalDestinationAdvisory] = []
    for modelo in bundled_authority().modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                destination_text = " ".join(
                    (
                        casilla.semantic_role or "",
                        *casilla.localization_keys,
                        *casilla.section,
                    )
                )
                destination_tokens = _lexical_tokens(destination_text)
                if not destination_tokens:
                    continue
                for capability_kind, locator, capability_tokens in capability_token_sets:
                    shared = tuple(sorted(capability_tokens & destination_tokens))
                    single_token_source_fact = capability_kind in {"secure_repository", "source_readiness"}
                    if (
                        not shared
                        or len(shared) * 2 < len(capability_tokens)
                        or (len(shared) == 1 and not single_token_source_fact)
                    ):
                        continue
                    advisories.append(
                        LexicalDestinationAdvisory(
                            capability_kind=capability_kind,
                            capability_locator=locator,
                            modelo_id=str(modelo.id),
                            revision_id=str(revision.id),
                            casilla_id=str(casilla.id),
                            shared_tokens=shared,
                        )
                    )
    return tuple(
        sorted(
            advisories,
            key=lambda item: (
                item.capability_kind,
                item.capability_locator,
                item.modelo_id,
                item.revision_id,
                item.casilla_id,
            ),
        )
    )


__all__ = [
    "CalculationHelperCapability",
    "IngressCapability",
    "IngressChannel",
    "LexicalDestinationAdvisory",
    "RowAssemblerCapability",
    "SecureRepositoryCapability",
    "SecureRepositoryMechanism",
    "SourceOwnershipCapability",
    "SourceReadinessCapability",
    "assign_capabilities_to_census",
    "discover_calculation_helpers",
    "discover_ingress_surfaces",
    "discover_lexical_destination_advisories",
    "discover_row_assemblers",
    "discover_secure_repositories",
    "discover_source_ownership",
    "discover_source_readiness",
    "discovered_source_capability_evidence",
    "discovered_source_capability_ids",
    "validate_census_completeness",
]
