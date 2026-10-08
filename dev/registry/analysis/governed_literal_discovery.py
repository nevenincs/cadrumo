"""Report regulatory-looking Python literals for governed-fact discovery.

This is deliberately a discovery instrument, not a quality gate.  Its broad
semantic heuristics produce candidates for human classification and its CLI
always succeeds, even when candidates or unread inputs are present.  The
modelo-specific zero-target scanners remain the enforceable tools for their
existing denominator.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8
from dev.first_party_source import PRODUCT_PACKAGE, is_production_source
from dev.quality.unread_inputs import report_unread

SOURCE_ROOT: Final[Path] = REPO_ROOT / PRODUCT_PACKAGE

_SEMANTIC_TOKEN: Final[re.Pattern[str]] = re.compile(
    r"(?:amount|article|base|cap|ceiling|coefficient|cutoff|deadline|deduction|exemption|"
    r"limit|minimum|maximum|multiplier|percentage|rate|retention|threshold|tax|year)",
    re.IGNORECASE,
)
_DATE_LITERAL: Final[re.Pattern[str]] = re.compile(r"^(?:19|20)\d{2}-\d{2}-\d{2}$")
_LEGAL_TEXT: Final[re.Pattern[str]] = re.compile(
    r"\b(?:art(?:í|i)culo|decreto|ley|orden|reglamento|tributari[ao]|impuesto|deber(?:á|a))\b",
    re.IGNORECASE,
)
_MODULE_SCOPE: Final[str] = "<module>"
_NON_POLICY_ROLE: Final[re.Pattern[str]] = re.compile(
    r"(?:schema|protocol|status|code|version|port|timeout|size|length|index|count|precision|scale|"
    r"build|release|generated|migration)",
    re.IGNORECASE,
)
_UNIT_IDENTITIES: Final[frozenset[int | float]] = frozenset({0, 1, 100, 365, 366})


class CandidateKind(StrEnum):
    """Literal shapes intentionally included in the discovery report."""

    DATE = "date"
    DECIMAL = "decimal"
    EXPRESSION = "expression"
    LEGAL_TEXT = "legal_text"
    MAPPING = "mapping"
    NUMERIC = "numeric"
    STRING = "string"


@dataclass(frozen=True, slots=True, order=True)
class GovernedLiteralCandidate:
    """One regulatory-looking value that needs human classification."""

    path: str
    line: int
    enclosing_symbol: str
    semantic_role: str
    kind: CandidateKind
    excerpt: str

    def render(self) -> str:
        """Return one stable, greppable report row."""
        return f"{self.path}:{self.line}::{self.enclosing_symbol} [{self.kind} {self.semantic_role}] {self.excerpt}"


def _candidate_modules(source_root: Path) -> Iterator[Path]:
    for path in sorted(source_root.rglob("*.py")):
        if is_production_source(path, root=source_root):
            yield path


def _parents(tree: ast.Module) -> dict[int, ast.AST]:
    return {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _scopes(tree: ast.Module) -> dict[int, str]:
    result: dict[int, str] = {id(tree): _MODULE_SCOPE}

    def visit(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            child_scope = scope
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                child_scope = child.name if scope == _MODULE_SCOPE else f"{scope}.{child.name}"
            result[id(child)] = child_scope
            visit(child, child_scope)

    visit(tree, _MODULE_SCOPE)
    return result


def _role(node: ast.AST, parents: dict[int, ast.AST], scopes: dict[int, str]) -> str:
    current = node
    while (parent := parents.get(id(current))) is not None:
        role = _parent_role(current, parent, parents, scopes)
        if role is not None:
            return role
        current = parent
    return scopes.get(id(node), _MODULE_SCOPE).rsplit(".", maxsplit=1)[-1]


def _parent_role(
    current: ast.AST,
    parent: ast.AST,
    parents: dict[int, ast.AST],
    scopes: dict[int, str],
) -> str | None:
    if isinstance(parent, ast.keyword) and parent.arg:
        return parent.arg
    if isinstance(parent, ast.arguments):
        return _default_parameter_role(current, parent, parents)
    if isinstance(parent, ast.Assign):
        return _assignment_role(parent)
    if isinstance(parent, ast.AnnAssign) and isinstance(parent.target, ast.Name):
        return parent.target.id
    if isinstance(parent, ast.Return):
        return scopes.get(id(parent), _MODULE_SCOPE).rsplit(".", maxsplit=1)[-1]
    return None


def _default_parameter_role(
    current: ast.AST,
    arguments: ast.arguments,
    parents: dict[int, ast.AST],
) -> str | None:
    owner = parents.get(id(arguments))
    if not isinstance(owner, ast.FunctionDef | ast.AsyncFunctionDef):
        return None
    return _positional_default_role(current, arguments) or _keyword_default_role(current, arguments)


def _positional_default_role(current: ast.AST, arguments: ast.arguments) -> str | None:
    positional = (*arguments.posonlyargs, *arguments.args)
    offset = len(positional) - len(arguments.defaults)
    for index, default in enumerate(arguments.defaults):
        if current is default:
            return positional[offset + index].arg
    return None


def _keyword_default_role(current: ast.AST, arguments: ast.arguments) -> str | None:
    for index, default in enumerate(arguments.kw_defaults):
        if current is default:
            return arguments.kwonlyargs[index].arg
    return None


def _assignment_role(assignment: ast.Assign) -> str | None:
    names = [target.id for target in assignment.targets if isinstance(target, ast.Name)]
    return names[0] if names else None


def _inside_mapping(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    current = node
    while (parent := parents.get(id(current))) is not None:
        if isinstance(parent, ast.Dict):
            return True
        if isinstance(parent, ast.Assign | ast.AnnAssign | ast.Return):
            return False
        current = parent
    return False


def _has_ancestor(node: ast.AST, parents: dict[int, ast.AST], kinds: type[ast.AST] | tuple[type[ast.AST], ...]) -> bool:
    current = node
    while (parent := parents.get(id(current))) is not None:
        if isinstance(parent, kinds):
            return True
        current = parent
    return False


def _decimal_call_names(tree: ast.Module) -> frozenset[str]:
    names = {"Decimal", "decimal.Decimal"}
    for node in tree.body:
        names.update(_decimal_import_names(node))
    return frozenset(names)


def _decimal_import_names(node: ast.stmt) -> set[str]:
    if isinstance(node, ast.ImportFrom) and node.module == "decimal":
        return {alias.asname or alias.name for alias in node.names if alias.name == "Decimal"}
    if isinstance(node, ast.Import):
        return {f"{alias.asname or alias.name}.Decimal" for alias in node.names if alias.name == "decimal"}
    return set()


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return ""


def _is_unit_expression(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Div)
        and isinstance(node.right, ast.Constant)
        and node.right.value in _UNIT_IDENTITIES
    )


def _excerpt(value: object, limit: int = 96) -> str:
    rendered = " ".join(repr(value).split())
    return rendered if len(rendered) <= limit else f"{rendered[: limit - 1]}…"


def _literal_candidate(
    node: ast.Constant,
    role: str,
    parents: dict[int, ast.AST],
) -> tuple[CandidateKind, str] | None:
    value = node.value
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return _numeric_candidate(value, role, node, parents)
    if isinstance(value, str) and value.strip():
        return _string_candidate(value, role, node, parents)
    return None


def _numeric_candidate(
    value: int | float,
    role: str,
    node: ast.Constant,
    parents: dict[int, ast.AST],
) -> tuple[CandidateKind, str] | None:
    if value in _UNIT_IDENTITIES or _NON_POLICY_ROLE.search(role) or not _SEMANTIC_TOKEN.search(role):
        return None
    kind = CandidateKind.MAPPING if _inside_mapping(node, parents) else CandidateKind.NUMERIC
    return kind, _excerpt(value)


def _string_candidate(
    value: str,
    role: str,
    node: ast.Constant,
    parents: dict[int, ast.AST],
) -> tuple[CandidateKind, str] | None:
    if _DATE_LITERAL.fullmatch(value) and not _NON_POLICY_ROLE.search(role):
        return CandidateKind.DATE, _excerpt(value)
    if _LEGAL_TEXT.search(value) and not _NON_POLICY_ROLE.search(role):
        return CandidateKind.LEGAL_TEXT, _excerpt(value)
    if not _SEMANTIC_TOKEN.search(role):
        return None
    kind = CandidateKind.MAPPING if _inside_mapping(node, parents) else CandidateKind.STRING
    return kind, _excerpt(value)


def _collect(tree: ast.Module, path: str) -> tuple[GovernedLiteralCandidate, ...]:
    parents = _parents(tree)
    scopes = _scopes(tree)
    docstrings = _docstring_nodes(tree)
    found: set[GovernedLiteralCandidate] = set()
    decimal_names = _decimal_call_names(tree)
    for node in ast.walk(tree):
        candidate = _candidate_for_node(node, path, parents, scopes, docstrings, decimal_names)
        if candidate is not None:
            found.add(candidate)
    return tuple(sorted(found))


def _docstring_nodes(tree: ast.Module) -> set[int]:
    return {
        id(body[0].value)
        for owner in ast.walk(tree)
        if isinstance(owner, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and (body := owner.body)
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    }


def _candidate_for_node(
    node: ast.AST,
    path: str,
    parents: dict[int, ast.AST],
    scopes: dict[int, str],
    docstrings: set[int],
    decimal_names: frozenset[str],
) -> GovernedLiteralCandidate | None:
    role = _role(node, parents, scopes)
    classification_role = _classification_role(node, role, scopes)
    if isinstance(node, ast.Call) and _call_name(node.func) in decimal_names:
        return _decimal_candidate(node, path, role, classification_role, scopes)
    expression = _expression_candidate(node, path, role, classification_role, scopes)
    if expression is not None:
        return expression
    return _constant_node_candidate(node, path, role, classification_role, parents, scopes, docstrings)


def _classification_role(node: ast.AST, role: str, scopes: dict[int, str]) -> str:
    if _SEMANTIC_TOKEN.search(role) or _NON_POLICY_ROLE.search(role):
        return role
    return scopes.get(id(node), _MODULE_SCOPE).rsplit(".", maxsplit=1)[-1]


def _decimal_candidate(
    node: ast.Call,
    path: str,
    role: str,
    classification_role: str,
    scopes: dict[int, str],
) -> GovernedLiteralCandidate | None:
    argument = node.args[0] if node.args else None
    if not isinstance(argument, ast.Constant):
        return None
    if not _SEMANTIC_TOKEN.search(classification_role) or _NON_POLICY_ROLE.search(classification_role):
        return None
    return GovernedLiteralCandidate(
        path,
        node.lineno,
        scopes.get(id(node), _MODULE_SCOPE),
        role,
        CandidateKind.DECIMAL,
        f"Decimal({_excerpt(argument.value)})",
    )


def _expression_candidate(
    node: ast.AST,
    path: str,
    role: str,
    classification_role: str,
    scopes: dict[int, str],
) -> GovernedLiteralCandidate | None:
    if not isinstance(node, ast.UnaryOp | ast.BinOp | ast.List | ast.Tuple | ast.Set):
        return None
    if not _SEMANTIC_TOKEN.search(classification_role) or _is_unit_expression(node):
        return None
    if not any(isinstance(child, ast.Constant) for child in ast.walk(node)):
        return None
    return GovernedLiteralCandidate(
        path,
        node.lineno,
        scopes.get(id(node), _MODULE_SCOPE),
        role,
        CandidateKind.EXPRESSION,
        _excerpt(ast.unparse(node)),
    )


def _constant_node_candidate(
    node: ast.AST,
    path: str,
    role: str,
    classification_role: str,
    parents: dict[int, ast.AST],
    scopes: dict[int, str],
    docstrings: set[int],
) -> GovernedLiteralCandidate | None:
    if not isinstance(node, ast.Constant) or id(node) in docstrings:
        return None
    if _has_ancestor(node, parents, (ast.Raise, ast.Call, ast.UnaryOp, ast.BinOp, ast.List, ast.Tuple, ast.Set)):
        return None
    classified = _literal_candidate(node, classification_role, parents)
    if classified is None:
        return None
    kind, excerpt = classified
    return GovernedLiteralCandidate(path, node.lineno, scopes.get(id(node), _MODULE_SCOPE), role, kind, excerpt)


def discover_governed_literal_candidates(
    source_root: Path = SOURCE_ROOT,
) -> tuple[GovernedLiteralCandidate, ...]:
    """Return broad candidates without classifying, suppressing, or gating them."""
    candidates: list[GovernedLiteralCandidate] = []
    unread: list[str] = []
    for path in _candidate_modules(source_root):
        try:
            tree = ast.parse(path.read_text(encoding=UTF_8))
        except FileNotFoundError:
            continue
        except (SyntaxError, UnicodeDecodeError) as error:
            unread.append(f"{path}: {type(error).__name__}: {error}")
            continue
        relative = path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else path.as_posix()
        candidates.extend(_collect(tree, relative))
    report_unread(
        "governed literal discovery",
        "a governed-literal candidate in an unread module is absent from this report",
        unread,
    )
    return tuple(sorted(candidates))


def main(argv: Sequence[str] | None = None) -> int:
    """Print the discovery report and always return success."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not args.source_root.is_dir():
        parser.error(f"source root is not a directory: {args.source_root}")
    candidates = discover_governed_literal_candidates(args.source_root)
    if args.json:
        json.dump([asdict(item) for item in candidates], sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        for item in candidates:
            sys.stdout.write(f"{item.render()}\n")
        sys.stdout.write(f"{len(candidates)} governed-literal candidate(s); report only\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["CandidateKind", "GovernedLiteralCandidate", "discover_governed_literal_candidates", "main"]
