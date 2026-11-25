"""How the tax literal sweep tells text from other values."""

from __future__ import annotations

import ast
import re

from cadrumo.core.filing_year import FOUR_DIGIT_YEAR_LAST

from .tax_literal_sweep_vocabulary import (
    THOUSAND,
    YEAR_NAME,
    annotation_kind,
    called_name,
    constant_number,
    dom_cell_call,
    expression_names,
    imports_for,
    machine_unit_name,
    reader_name,
    scope_nodes,
)


class _ExpressionKinds:
    """Classify an expression as text, a sequence of text, a pattern or a match by what produces it."""

    _tree: ast.Module
    _owner: str
    _module: str
    _parents: dict[ast.AST, ast.AST]

    def _enclosing_function(self, node: ast.AST) -> str:
        """Return the enclosing function and class names, innermost first, in snake case."""
        names = []
        current = node
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(re.sub(r"(?<=[a-z])(?=[A-Z])", "_", current.name))
        return ".".join(names)

    def _scope(self, node: ast.AST) -> ast.AST:
        current = node
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current
        return self._tree

    def _expression_kind(self, node: ast.AST, seen: frozenset[tuple[int, str]] = frozenset()) -> str:
        for phase in (self._projection_kind, self._call_kind, self._name_kind):
            kind = phase(node, seen)
            if kind is not None:
                return kind
        return "unknown"

    def _projection_kind(self, node: ast.AST, seen: frozenset[tuple[int, str]]) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            return "text"
        if isinstance(node, ast.ListComp) and all(
            self._expression_kind(generator.iter, seen) == "grammar_sequence" for generator in node.generators
        ):
            return "grammar_sequence"
        if isinstance(node, ast.Attribute) and node.attr == "path" and self._expression_kind(node.value, seen) == "url":
            return "text"
        if isinstance(node, ast.Subscript):
            parent_kind = self._expression_kind(node.value, seen)
            if parent_kind in {"text", "match"}:
                return "text"
            if parent_kind == "grammar_sequence":
                return "grammar_sequence" if isinstance(node.slice, ast.Slice) else "text"
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "args"
            and self._expression_kind(node.value, seen) == "expression"
        ):
            return "grammar_sequence"
        return None

    def _call_kind(self, node: ast.AST, seen: frozenset[tuple[int, str]]) -> str | None:
        if not isinstance(node, ast.Call):
            return None
        name = called_name(node)
        if name == "str":
            return "text"
        if isinstance(node.func, ast.Attribute):
            kind = self._method_call_kind(node, node.func, name, seen)
            if kind is not None:
                return kind
        for function in ast.walk(self._tree):
            if isinstance(function, ast.FunctionDef) and function.name == name:
                kind = annotation_kind(function.returns, self._tree, self._module)
                if kind != "unknown":
                    if (
                        kind == "collection"
                        and self._owner.startswith("adapters/")
                        and any(isinstance(call, ast.Call) and dom_cell_call(call) for call in ast.walk(function))
                    ):
                        return "grammar_sequence"
                    return kind
        return None

    def _method_call_kind(
        self, node: ast.Call, func: ast.Attribute, name: str, seen: frozenset[tuple[int, str]]
    ) -> str | None:
        receiver = self._expression_kind(func.value, seen)
        if receiver == "text":
            if name in {"split", "rsplit", "partition", "rpartition"}:
                return "grammar_sequence"
            if name in {"strip", "lstrip", "rstrip", "replace", "upper", "lower", "casefold", "join"}:
                return "text"
        if name == "items" and receiver == "text_mapping":
            return "text_items"
        if name == "compile" and reader_name(func.value) == "re":
            return "pattern"
        if name in {"match", "fullmatch", "search"} and receiver == "pattern":
            return "match"
        if name == "group" and receiver == "match":
            return "text"
        if self._owner.startswith("adapters/") and dom_cell_call(node):
            return "grammar_sequence"
        return None

    def _name_kind(self, node: ast.AST, seen: frozenset[tuple[int, str]]) -> str | None:
        if not isinstance(node, ast.Name):
            return None
        scope = self._scope(node)
        key = (id(scope), node.id)
        if key in seen:
            return "unknown"
        seen = seen | {key}
        assignments = [
            part.value
            for part in scope_nodes(scope)
            if isinstance(part, ast.Assign) and any(reader_name(target) == node.id for target in part.targets)
        ]
        if len(assignments) > 1:
            for assigned in assignments:
                if (
                    isinstance(assigned, ast.Subscript)
                    and isinstance(assigned.slice, ast.Slice)
                    and ast.dump(assigned.value) == ast.dump(node)
                ):
                    continue
                if self._expression_kind(assigned, seen) not in {"text", "grammar_sequence", "pattern", "match"}:
                    return "unknown"
        local_binding = False
        for declaration in scope_nodes(scope):
            kind, bound = self._declaration_kind(declaration, node, scope, seen)
            local_binding = local_binding or bound
            if kind is not None:
                return kind
        if scope is not self._tree and not local_binding:
            for declaration in self._tree.body:
                if isinstance(declaration, (ast.Assign, ast.AnnAssign)):
                    targets = declaration.targets if isinstance(declaration, ast.Assign) else [declaration.target]
                    if any(reader_name(t) == node.id for t in targets) and declaration.value is not None:
                        return self._expression_kind(declaration.value, seen)
        return None

    def _declaration_kind(
        self, declaration: ast.AST, node: ast.Name, scope: ast.AST, seen: frozenset[tuple[int, str]]
    ) -> tuple[str | None, bool]:
        """Return the kind one declaration gives ``node`` (``None`` for none) and whether it binds the name."""
        value = None
        bound = False
        if isinstance(declaration, ast.arg) and declaration.arg == node.id:
            bound = True
            kind = self._argument_kind(declaration, scope, seen)
            if kind != "unknown":
                return kind, bound
        if isinstance(declaration, ast.AnnAssign) and reader_name(declaration.target) == node.id:
            kind = annotation_kind(declaration.annotation, self._tree, self._module)
            if kind != "unknown":
                return kind, bound
            bound = True
            value = declaration.value
        if isinstance(declaration, ast.Assign) and any(reader_name(t) == node.id for t in declaration.targets):
            bound = True
            value = declaration.value
        if isinstance(declaration, ast.Assign) and any(
            isinstance(target, (ast.Tuple, ast.List)) and any(reader_name(part) == node.id for part in target.elts)
            for target in declaration.targets
        ):
            bound = True
            if self._expression_kind(declaration.value, seen) == "grammar_sequence":
                return "text", bound
        if (
            isinstance(declaration, (ast.comprehension, ast.For))
            and reader_name(declaration.target) == node.id
            and self._expression_kind(declaration.iter, seen) == "grammar_sequence"
        ):
            return "text", bound
        if (
            isinstance(declaration, ast.For)
            and isinstance(declaration.target, (ast.Tuple, ast.List))
            and any(reader_name(part) == node.id for part in declaration.target.elts)
        ):
            bound = True
            if self._expression_kind(declaration.iter, seen) == "text_items":
                return "text", bound
        if isinstance(declaration, ast.For) and reader_name(declaration.target) == node.id:
            bound = True
            if self._iterates_text_keys(declaration, scope):
                return "text", bound
        if value is not None:
            kind = self._expression_kind(value, seen)
            if kind != "unknown":
                return kind, bound
        return None, bound

    def _argument_kind(self, declaration: ast.arg, scope: ast.AST, seen: frozenset[tuple[int, str]]) -> str:
        kind = annotation_kind(declaration.annotation, self._tree, self._module)
        if kind == "collection" and isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = [*scope.args.posonlyargs, *scope.args.args]
            if declaration in arguments:
                index = arguments.index(declaration)
                callers = [
                    call
                    for call in ast.walk(self._tree)
                    if isinstance(call, ast.Call) and called_name(call) == scope.name and len(call.args) > index
                ]
                if callers and all(
                    self._expression_kind(call.args[index], seen) == "grammar_sequence" for call in callers
                ):
                    return "grammar_sequence"
        return kind

    def _iterates_text_keys(self, declaration: ast.For, scope: ast.AST) -> bool:
        if not isinstance(declaration.iter, ast.Name):
            return False
        for argument in scope_nodes(scope):
            annotation = (
                argument.annotation if isinstance(argument, ast.arg) and argument.arg == declaration.iter.id else None
            )
            if isinstance(annotation, ast.Subscript) and reader_name(annotation.value) in {"Mapping", "dict"}:
                first = annotation.slice.elts[0] if isinstance(annotation.slice, ast.Tuple) else annotation.slice
                if annotation_kind(first, self._tree, self._module) == "text":
                    return True
        return False


class BoundReader(_ExpressionKinds):
    """Decide whether a number bounding a constraint or a length is a technical bound."""

    def _constraint_declaration(self, node: ast.AST) -> tuple[str, ast.AST | None]:
        current = node
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, ast.arg):
                return current.arg, current.annotation
            if isinstance(current, ast.AnnAssign):
                return expression_names(current.target), current.annotation
            if isinstance(current, ast.TypeAlias):
                return reader_name(current.name), current.value
            if isinstance(current, ast.Assign):
                return " ".join(expression_names(t) for t in current.targets), current.value
            if isinstance(current, ast.stmt):
                break
        return "", None

    def _structural_length(self, length: ast.Call, comparison: ast.Compare) -> bool:
        if not length.args:
            return False
        value = length.args[0]
        if self._expression_kind(value) in {"text", "grammar_sequence"}:
            return True
        scope = self._scope(comparison)
        spelling = ast.dump(value)
        if self._reads_character_predicate(scope, spelling):
            return True
        numbers = {constant_number(side) for side in (comparison.left, *comparison.comparators)} - {None}
        indices = self._literal_indices(scope, spelling)
        if indices and max(indices) + 1 in numbers and self._compares_fields_to_labels(scope, spelling):
            return True
        if self._owner == "adapters/outbound/aeat/sede/declarations_listbox.py":
            return (
                isinstance(value, ast.Name)
                and value.id == "cell_texts"
                and bool(indices)
                and max(indices) + 1 in numbers
            )
        if self._owner == "domain/calculations/registry/export_components.py":
            return self._counts_export_policy_tuple(scope, numbers)
        return False

    @staticmethod
    def _reads_character_predicate(scope: ast.AST, spelling: str) -> bool:
        # A character predicate establishes text grammar even when a library's
        # generic validator parameter is deliberately annotated as object.
        return any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr in {"isdigit", "isascii", "isdecimal"}
            and ast.dump(call.func.value) == spelling
            for call in scope_nodes(scope)
        )

    @staticmethod
    def _literal_indices(scope: ast.AST, spelling: str) -> list[int]:
        return [
            part.slice.value
            for part in scope_nodes(scope)
            if isinstance(part, ast.Subscript)
            and ast.dump(part.value) == spelling
            and isinstance(part.slice, ast.Constant)
            and isinstance(part.slice.value, int)
        ]

    @staticmethod
    def _compares_fields_to_labels(scope: ast.AST, spelling: str) -> bool:
        # Fixed text record fields are checked against literal field labels.
        return any(
            isinstance(part, ast.Compare)
            and any(
                isinstance(side, ast.Constant) and isinstance(side.value, str)
                for side in (part.left, *part.comparators)
            )
            and any(
                isinstance(side, ast.Subscript) and ast.dump(side.value) == spelling
                for side in (part.left, *part.comparators)
            )
            for part in scope_nodes(scope)
        )

    @staticmethod
    def _counts_export_policy_tuple(scope: ast.AST, numbers: set[float | None]) -> bool:
        return any(
            isinstance(part, ast.Compare)
            and any(
                isinstance(side, ast.Tuple) and len(side.elts) in numbers for side in (part.left, *part.comparators)
            )
            and any(
                isinstance(member, ast.Attribute)
                and isinstance(member.value, ast.Name)
                and member.value.id == "ExportValuePolicy"
                for member in ast.walk(part)
            )
            for part in scope_nodes(scope)
        )

    def _constraint_class(self, node: ast.AST) -> ast.ClassDef | None:
        current = node
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, ast.ClassDef):
                return current
        return None

    def _technical_bound(self, node: ast.Call, low: float | None, high: float | None) -> bool:
        field, _annotation = self._constraint_declaration(node)
        owner = self._owner
        if machine_unit_name(field):
            return True
        if low == THOUSAND and high is None and YEAR_NAME.search(field):
            return True
        if field == "http_status" and (low, high) == (100, 599):
            return owner in {"application/connectivity_probe.py", "application/workflow/run_models.py"}
        if (low, high) == (0, 366) and field in {"dias_miembro", "dias_arrendamiento"}:
            return self._member_days_wire_mirror(node, field)
        if field == "quarters_filed" and (low, high) == (1, 4):
            return owner in {"application/modelo/projection.py", "application/modelo/projection_operation.py"} and any(
                isinstance(part, ast.Attribute) and part.attr in {"is_quarterly", "quarters_available"}
                for part in ast.walk(self._tree)
            )
        if field == "lookback_years" and (low, high) == (1, 50):
            return (
                owner == "core/external_constants.py"
                and "aeat_notifications_query" in self._enclosing_function(node).lower()
            )
        if field == "cadrumo_bucket_default_session_absolute_minutes" and (low, high) == (60, 720):
            return owner == "core/config_runtime_fields.py"
        if high == FOUR_DIGIT_YEAR_LAST and field.endswith("year"):
            return any(
                keyword.arg == "ge"
                and isinstance(keyword.value, ast.Name)
                and imports_for(self._tree, self._module).get(keyword.value.id)
                == ("cadrumo.core.filing_year", "FOUR_DIGIT_YEAR_FIRST")
                for keyword in node.keywords
            )
        return False

    def _member_days_wire_mirror(self, node: ast.Call, field: str) -> bool:
        # The calendar envelope belongs to this wire mirror's unchanged
        # transfer into the canonical domain row, not to an arbitrary cap.
        owner_class = self._constraint_class(node)
        row_type = imports_for(self._tree, self._module).get("Modelo184MemberRow")
        return (
            self._owner == "application/modelo/edit_apply_row_contracts.py"
            and row_type == ("cadrumo.domain.modelos.row_models", "Modelo184MemberRow")
            and owner_class is not None
            and any(
                isinstance(function, ast.FunctionDef)
                and function.name == "to_row"
                and any(
                    isinstance(call, ast.Call)
                    and called_name(call) == "Modelo184MemberRow"
                    and any(
                        arg.arg == field
                        and isinstance(arg.value, ast.Attribute)
                        and isinstance(arg.value.value, ast.Name)
                        and arg.value.value.id == "self"
                        and arg.value.attr == field
                        for arg in call.keywords
                    )
                    for call in ast.walk(function)
                )
                for function in owner_class.body
            )
        )

    def _plurality_bound(self, node: ast.Call, low: float | None, high: float | None) -> bool:
        if (low, high) == (2, 2):
            field, _annotation = self._constraint_declaration(node)
            return self._owner == "application/modelo/projection_operation.py" and field == "years"
        if low != 2 or high is not None:
            return False
        field, annotation = self._constraint_declaration(node)
        names = expression_names(annotation) if annotation is not None else ""
        if self._owner in {"application/ledger/merge_operation.py", "application/ledger/split_operation.py"}:
            return any(token in names for token in {"TransactionId", "_TransactionPrefix", "LedgerSplitChildRequest"})
        if self._owner == "domain/modelos/source_disagreement.py":
            return field == "sources" and "SourceDisagreementEntry" in names
        if self._owner == "application/modelo/calculation_report.py":
            return field == "sources" and "ModeloCalculationReportResolutionSource" in names
        if self._owner == "application/workflow/resume_contracts.py":
            return field == "candidates" and "WorkflowResumeCandidateSnapshot" in names
        if self._owner == "application/inventory/registered_requests.py":
            return (
                field == "evidence"
                and "PhysicalClosingEvidence" in names
                and imports_for(self._tree, self._module).get("PhysicalClosingEvidence")
                == ("cadrumo.domain.contribuyente.inventory.closing_foundations", "PhysicalClosingEvidence")
            )
        return False
