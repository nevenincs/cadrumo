"""Structural discovery for source capabilities that may feed modelo casillas.

Discovery is intentionally syntax-driven and produces evidence locators.  It
does not decide that a repository's payload is legally equivalent to a casilla;
that decision belongs to the reviewed connectivity census.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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

    @property
    def evidence_locator(self) -> str:
        """Return a re-fetchable source locator for review and census rows."""
        return f"{self.module}:{self.line}"


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


@dataclass(frozen=True, slots=True)
class RowAssemblerCapability:
    """One registry row grouping and its typed application assembler."""

    module: str
    grouping: str
    source_kind: str
    assembler_name: str
    observation_return_type: str
    line: int


@dataclass(frozen=True, slots=True)
class SourceOwnershipCapability:
    """One source kind owned by the canonical production calculation route."""

    source_kind: str
    resolver_id: str
    resolver_type: str | None
    stage: str


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
    return frozenset(
        name.rsplit(".", maxsplit=1)[-1]
        for child in ast.walk(node)
        if (name := _dotted_name(child))
    )


def _secure_mechanism(node: ast.ClassDef) -> SecureRepositoryMechanism | None:
    base_names = {_dotted_name(base).rsplit(".", maxsplit=1)[-1] for base in node.bases}
    if base_names & {"SecureBoundRepository", "_SecureBoundRepository"}:
        return "secure_bound"
    names = _class_names(node)
    if "ProfileBareModelSecurePersistence" in names:
        return "profile_secure_document"
    if names & _SECURE_NAMES:
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
    return tuple(sorted(capabilities, key=lambda item: (item.module, item.line, item.callback_name)))


def _exported_symbols(source_root: Path) -> frozenset[str]:
    exported: set[str] = set()
    for path in sorted(source_root.rglob("__init__.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                continue
            exported.update(
                child.value
                for child in node.elts
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            )
    return frozenset(exported)


def discover_calculation_helpers(repo_root: Path) -> tuple[CalculationHelperCapability, ...]:
    """Enumerate exported domain functions with structural calculation behavior."""
    domain_root = repo_root / "src" / "cadrumo" / "domain"
    exported = _exported_symbols(domain_root)
    capabilities: list[CalculationHelperCapability] = []
    for path in sorted(domain_root.rglob("*.py")):
        if "tests" in path.relative_to(domain_root).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name not in exported:
                continue
            binary_operations = {
                type(child.op).__name__
                for child in ast.walk(node)
                if isinstance(child, (ast.BinOp, ast.AugAssign))
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
    path = repo_root / "src" / "cadrumo" / "application" / "calculations" / "_row_set_assembly.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    dispatch_assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "_GROUPING_DISPATCH"
        and isinstance(node.value, ast.Dict)
    )
    grouping_members = [
        (key.value, ast.unparse(value))
        for key, value in zip(dispatch_assignment.value.keys, dispatch_assignment.value.values, strict=True)
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
    from cadrumo.application.modelo import CALCULATION_ROUTE_RESOLVER_OWNERSHIP

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
    return frozenset(
        token
        for token in re.findall(r"[a-záéíóúñ]{4,}", expanded.lower())
        if token not in _LEXICAL_STOPWORDS
    )


def discover_lexical_destination_advisories(repo_root: Path) -> tuple[LexicalDestinationAdvisory, ...]:
    """Emit report-only token overlaps; never infer binding identity or equivalence."""
    from cadrumo.core.resources import resources

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
    for modelo in resources().modelos.authority.modelos:
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
    "discover_calculation_helpers",
    "discover_ingress_surfaces",
    "discover_lexical_destination_advisories",
    "discover_row_assemblers",
    "discover_secure_repositories",
    "discover_source_ownership",
    "discover_source_readiness",
]
