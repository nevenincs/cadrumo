"""Occurrences for the subordinate import checker."""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import override

from dev._paths import UTF_8

from .import_check_models import Authority, ImportOccurrence, SourceModule
from .import_dynamic_aliases import DYNAMIC_TARGET_KEYWORDS, DynamicLoaderKind, dynamic_aliases
from .import_dynamic_strings import carries_interpreter_payload, string_payload_imports
from .import_dynamic_targets import dynamic_target, metadata_target_set_targets
from .import_module_syntax import (
    is_first_party,
    is_package,
    is_type_checking_guard,
    matches_any_module,
    resolve_from,
)
from .import_record_provenance import RecordTargetProvenance
from .import_target_evaluation import TargetEvaluationContext


def collect_import_occurrences(
    authority: Authority,
    modules: Mapping[str, SourceModule],
    record_provenance: RecordTargetProvenance,
) -> tuple[ImportOccurrence, ...]:
    """Collect direct, occurrence-level violations from the declared authority."""
    known = frozenset((*modules, *authority.root_packages))
    occurrences: list[ImportOccurrence] = []
    for module in modules.values():
        visitor = _OccurrenceVisitor(
            authority=authority,
            module=module,
            modules=modules,
            known=known,
            record_provenance=record_provenance,
            occurrences=occurrences,
        )
        visitor.visit(module.tree)
    return tuple(occurrences)


class _OccurrenceVisitor(ast.NodeVisitor):
    """Traverse one module while retaining scope and TYPE_CHECKING context."""

    def __init__(
        self,
        *,
        authority: Authority,
        module: SourceModule,
        modules: Mapping[str, SourceModule],
        known: frozenset[str],
        record_provenance: RecordTargetProvenance,
        occurrences: list[ImportOccurrence],
    ) -> None:
        """Index lexical parents and assignments for conservative target evaluation."""
        self.authority = authority
        self.module = module
        self.modules = modules
        self.known = known
        self.record_provenance = record_provenance
        self.occurrences = occurrences
        self.context: TargetEvaluationContext | None = None
        self.aliases = dynamic_aliases(module)
        self.scopes: list[str] = []
        self.type_checking_depth = 0

    @override
    def visit_If(self, node: ast.If) -> None:
        is_type_checking = is_type_checking_guard(node.test)
        self.visit(node.test)
        if is_type_checking:
            self.type_checking_depth += 1
        for statement in node.body:
            self.visit(statement)
        if is_type_checking:
            self.type_checking_depth -= 1
        for statement in node.orelse:
            self.visit(statement)

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node)

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node)

    def _visit_scope(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        # Decorators, defaults, annotations, bases and class keywords run in the
        # enclosing scope when the definition executes, so they are visited
        # there; only the body belongs to the new lexical scope.
        for decorator in node.decorator_list:
            self.visit(decorator)
        for type_param in node.type_params:
            self.visit(type_param)
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                self.visit(base)
            for keyword in node.keywords:
                self.visit(keyword)
        else:
            self.visit(node.args)
            if node.returns is not None:
                self.visit(node.returns)
        self.scopes.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.scopes.pop()

    @override
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if is_first_party(alias.name, self.authority.root_names):
                self.record(alias.name, (), node.lineno, self._static_form())

    @override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        target = resolve_from(self.module.name, self.module.is_package, node.level, node.module)
        if target is None or not is_first_party(target, self.authority.root_names):
            return
        for alias in node.names:
            child = f"{target}.{alias.name}"
            if (
                alias.name != "*"
                and is_package(target, self.modules, self.authority.root_names)
                and child in self.known
            ):
                self.record(child, (), node.lineno, self._static_form())
            else:
                self.record(target, (alias.name,), node.lineno, self._static_form())

    @override
    def visit_Call(self, node: ast.Call) -> None:
        kind = self.aliases.loader_kind(node)
        if kind is not None:
            _record_dynamic_call(self, node, kind)
        self._record_string_payloads(node)
        self.generic_visit(node)

    @override
    def visit_List(self, node: ast.List) -> None:
        self._record_string_payloads(node)
        self.generic_visit(node)

    @override
    def visit_Tuple(self, node: ast.Tuple) -> None:
        self._record_string_payloads(node)
        self.generic_visit(node)

    def _record_string_payloads(self, node: ast.Call | ast.List | ast.Tuple) -> None:
        """Record the first-party imports an interpreter payload names at *node*."""
        if not carries_interpreter_payload(node):
            return
        for item in string_payload_imports(node, self._evaluation_context()):
            if not is_first_party(item.target, self.authority.root_names):
                continue
            for symbol in item.symbols or ("",):
                child = f"{item.target}.{symbol}"
                if symbol and is_package(item.target, self.modules, self.authority.root_names) and child in self.known:
                    self.record(child, (), item.lineno, "string")
                else:
                    self.record(item.target, (symbol,) if symbol else (), item.lineno, "string")

    def _evaluation_context(self) -> TargetEvaluationContext:
        if self.context is None:
            self.context = TargetEvaluationContext(self.module.tree, self.module.name)
        return self.context

    def _static_form(self) -> str:
        if self.type_checking_depth:
            return "type_checking"
        return "local" if self.scopes else "static"

    def record(self, target: str, symbols: tuple[str, ...], lineno: int, import_form: str) -> None:
        lexical_scope = ".".join(self.scopes) if self.scopes else "<module>"
        for contract in self.authority.forbidden_contracts:
            if not matches_any_module(self.module.name, contract.source_modules):
                continue
            if matches_any_module(self.module.name, contract.forbidden_modules):
                continue
            if not matches_any_module(target, contract.forbidden_modules):
                continue
            fingerprint = import_occurrence_fingerprint(
                source_module=self.module.name,
                target_module=target,
                imported_symbols=symbols,
                import_form=import_form,
                lexical_scope=lexical_scope,
                contract=contract.key,
            )
            self.occurrences.append(
                ImportOccurrence(
                    fingerprint=fingerprint,
                    source_module=self.module.name,
                    target_module=target,
                    imported_symbols=tuple(sorted(symbols)),
                    import_form=import_form,
                    lexical_scope=lexical_scope,
                    contract=contract.key,
                    path=self.module.path,
                    lineno=lineno,
                )
            )
        source_lane = _adapter_lane(self.module.name)
        target_lane = _adapter_lane(target)
        if source_lane is not None and target_lane is not None and source_lane != target_lane:
            contract = "advisory:adapter-top-level-coupling"
            fingerprint = import_occurrence_fingerprint(
                source_module=self.module.name,
                target_module=target,
                imported_symbols=symbols,
                import_form=import_form,
                lexical_scope=lexical_scope,
                contract=contract,
            )
            self.occurrences.append(
                ImportOccurrence(
                    fingerprint=fingerprint,
                    source_module=self.module.name,
                    target_module=target,
                    imported_symbols=tuple(sorted(symbols)),
                    import_form=import_form,
                    lexical_scope=lexical_scope,
                    contract=contract,
                    path=self.module.path,
                    lineno=lineno,
                )
            )


def _adapter_lane(module: str) -> str | None:
    """Return the top-level adapter namespace without asserting peer legality."""
    prefix = "cadrumo.adapters."
    if not module.startswith(prefix):
        return None
    tail = module.removeprefix(prefix)
    return tail.partition(".")[0] or None


def import_occurrence_fingerprint(
    *,
    source_module: str,
    target_module: str,
    imported_symbols: Sequence[str],
    import_form: str,
    lexical_scope: str,
    contract: str,
) -> str:
    """Return the stable identity of one occurrence-contract record."""
    identity = {
        "contract": contract,
        "import_form": import_form,
        "imported_symbols": sorted(imported_symbols),
        "lexical_scope": lexical_scope,
        "source_module": source_module,
        "target_module": target_module,
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode(UTF_8)).hexdigest()


def _record_dynamic_call(self: _OccurrenceVisitor, node: ast.Call, kind: DynamicLoaderKind) -> None:
    """Record dynamic call."""
    context = self._evaluation_context()
    keyword_name = DYNAMIC_TARGET_KEYWORDS[kind]
    target_node = (
        node.args[0]
        if node.args
        else next((keyword.value for keyword in node.keywords if keyword.arg == keyword_name), None)
    )
    if target_node is not None:
        targets, exhaustive_census = _occurrence_dynamic_targets(self, target_node, node, context)
        _record_dynamic_targets(self, node, kind, context, targets, exhaustive_census)


def _occurrence_dynamic_targets(
    self: _OccurrenceVisitor, target_node: ast.AST, node: ast.Call, context: TargetEvaluationContext
) -> tuple[frozenset[str] | None, bool]:
    """Occurrence dynamic targets."""
    targets = context.values_for(target_node, node.lineno)
    exhaustive_census = False
    if targets is None or not targets:
        targets, exhaustive_census = metadata_target_set_targets(
            target_node,
            node.lineno,
            self.module,
            context,
            self.authority.repository,
        )
    if targets is None or not targets:
        targets = self.record_provenance.targets(self.module.name, target_node)
    return targets, exhaustive_census


def _record_dynamic_targets(
    self: _OccurrenceVisitor,
    node: ast.Call,
    kind: DynamicLoaderKind,
    context: TargetEvaluationContext,
    targets: frozenset[str] | None,
    exhaustive_census: bool,
) -> None:
    """Record dynamic targets."""
    for target in sorted(() if exhaustive_census else targets or ()):
        if kind == "run_module" and target.startswith("."):
            continue
        resolved = dynamic_target(self.module, target, node, context, record_provenance=self.record_provenance)
        if (
            (resolved is not None and resolved)
            and resolved in self.known
            and is_first_party(resolved, self.authority.root_names)
        ):
            self.record(resolved, (), node.lineno, "dynamic")
