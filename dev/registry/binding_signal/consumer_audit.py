"""Build reverse consumer, runtime-route, and unconsumed-binding evidence."""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import override

from dev.first_party_source import DEVELOPMENT_TOOLING, PRODUCT_PACKAGE, is_test_source

from .common import relative, required_mapping
from .models import SignalInputs
from .revision_audit import RevisionSignals
from .semantics import binding_closure, finding, unconsumed_binding_report

_BindingCoordinate = tuple[str, str, str]


@dataclass(slots=True)
class ConsumerSignals:
    """Reverse-route evidence and counts joined by revision-local binding id."""

    routes: list[dict[str, object]] = field(default_factory=list)
    findings: list[dict[str, object]] = field(default_factory=list)
    code_binding_refs: list[dict[str, object]] = field(default_factory=list)
    code_refs_by_binding: dict[str, list[dict[str, object]]] = field(default_factory=lambda: defaultdict(list))
    structural_consumers: dict[_BindingCoordinate, list[dict[str, object]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    census_unavailable_modelo: Counter[str] = field(default_factory=Counter)
    unreferenced_rows: list[dict[str, object]] = field(default_factory=list)
    unreferenced_classification: Counter[str] = field(default_factory=Counter)
    unreferenced_disposition: Counter[str] = field(default_factory=Counter)
    unreferenced_provider: Counter[str] = field(default_factory=Counter)
    unreferenced_modelo: Counter[str] = field(default_factory=Counter)


class _BindingLiteralVisitor(ast.NodeVisitor):
    """Find exact string references while retaining their lexical scope."""

    def __init__(self, *, binding_ids: frozenset[str], path: str) -> None:
        self.binding_ids = binding_ids
        self.path = path
        self.scope: list[str] = []
        self.rows: list[dict[str, object]] = []

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    @override
    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and node.value in self.binding_ids:
            self.rows.append(
                {
                    "binding_id": node.value,
                    "path": self.path,
                    "line": node.lineno,
                    "scope": ".".join(self.scope) or "<module>",
                    "surface": "test" if is_test_source(self.path) else "code",
                }
            )


def python_binding_references(
    root: Path,
    binding_ids: frozenset[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Find exact binding-id literals without treating generated refs as absent."""
    rows: list[dict[str, object]] = []
    limitations: list[dict[str, object]] = []
    scan_roots = (root / PRODUCT_PACKAGE, root / DEVELOPMENT_TOOLING / "registry")
    for scan_root in scan_roots:
        if not scan_root.is_dir():
            limitations.append(
                {
                    "code": "PYTHON_BINDING_REFERENCE_ROOT_MISSING",
                    "path": relative(scan_root, root),
                    "message": "scan root is not a directory; its binding-id literals are outside this measurement",
                }
            )
            continue
        _scan_python_root(scan_root, root, binding_ids, rows, limitations)
    return rows, limitations


def _scan_python_root(
    scan_root: Path,
    root: Path,
    binding_ids: frozenset[str],
    rows: list[dict[str, object]],
    limitations: list[dict[str, object]],
) -> None:
    for path in sorted(scan_root.rglob("*.py")):
        relative_path = relative(path, root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except (OSError, SyntaxError, UnicodeError) as exc:
            limitations.append(
                {
                    "code": "PYTHON_BINDING_REFERENCE_PARSE_FAILED",
                    "path": relative_path,
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        visitor = _BindingLiteralVisitor(binding_ids=binding_ids, path=relative_path)
        visitor.visit(tree)
        rows.extend(visitor.rows)


def audit_consumers(inputs: SignalInputs, revisions: RevisionSignals) -> ConsumerSignals:
    """Join typed, structural, and literal references to each binding row."""
    results = ConsumerSignals()
    binding_ids = frozenset(str(item["binding_id"]) for item in revisions.binding_rows)
    results.code_binding_refs, limits = python_binding_references(inputs.root, binding_ids)
    inputs.limitations.extend(limits)
    _index_code_references(results)
    _index_structural_references(revisions, results)
    censused_revisions = frozenset(inputs.compiled) if inputs.binding_consumers is not None else frozenset()
    for binding in revisions.binding_rows:
        _audit_binding_consumers(binding, inputs, revisions, results, censused_revisions)
    return results


def _index_code_references(results: ConsumerSignals) -> None:
    for item in results.code_binding_refs:
        results.code_refs_by_binding[str(item["binding_id"])].append(item)


def _index_structural_references(revisions: RevisionSignals, results: ConsumerSignals) -> None:
    for item in revisions.consumer_refs:
        key = (str(item["modelo"]), str(item["revision"]), str(item["binding_id"]))
        results.structural_consumers[key].append(item)


def _audit_binding_consumers(
    binding: dict[str, object],
    inputs: SignalInputs,
    revisions: RevisionSignals,
    results: ConsumerSignals,
    censused_revisions: frozenset[tuple[str, str]],
) -> None:
    coordinate = (str(binding["modelo"]), str(binding["revision"]), str(binding["binding_id"]))
    typed = revisions.canonical_consumers.get(coordinate, [])
    structural = results.structural_consumers.get(coordinate, [])
    registration = inputs.registrations.get(str(binding.get("provider_kind") or ""))
    status, failures = binding_closure(binding, registration, inputs.runtime_resolvers)
    _append_route(binding, typed, structural, registration, status, failures, inputs, results)
    if coordinate[:2] not in censused_revisions:
        results.census_unavailable_modelo[coordinate[0]] += 1
        return
    _append_unconsumed(binding, typed, structural, registration, results)


def _append_route(
    binding: dict[str, object],
    typed: list[dict[str, object]],
    structural: list[dict[str, object]],
    registration: dict[str, object] | None,
    status: str,
    failures: tuple[str, ...],
    inputs: SignalInputs,
    results: ConsumerSignals,
) -> None:
    route_registration = registration.get("route") if registration else None
    resolver_id = route_registration.get("resolver_id") if isinstance(route_registration, Mapping) else None
    binding_id = str(binding["binding_id"])
    results.routes.append(
        {
            "binding": {
                "modelo": binding["modelo"],
                "revision": binding["revision"],
                "id": binding_id,
                "declaration_shape": binding["declaration_shape"],
                "declaration_authorship": binding["declaration_authorship"],
                "location": binding["location"],
            },
            "consumers": {
                "canonical": typed,
                "structural": structural,
                "exact_python_literals": results.code_refs_by_binding.get(binding_id, []),
            },
            "provider": {
                "kind": binding.get("provider_kind"),
                "payload": binding.get("provider"),
                "registered": registration is not None,
                "disposition": registration.get("disposition") if registration else None,
                "provider_model": registration.get("provider_model") if registration else None,
                "value_contract": binding.get("value"),
            },
            "resolution_mechanism": {
                "registration": route_registration,
                "executable": inputs.runtime_resolvers.get(str(resolver_id)) if resolver_id else None,
            },
            "terminal_origin_contract": registration.get("permitted_terminal_origins", ()) if registration else (),
            "closure": {"status": status, "failures": list(failures), "authority": "static_binding_contract"},
        }
    )
    _record_open_route(binding, status, failures, results)


def _record_open_route(
    binding: dict[str, object],
    status: str,
    failures: tuple[str, ...],
    results: ConsumerSignals,
) -> None:
    if not status.startswith("open_"):
        return
    results.findings.append(
        finding(
            f"BINDING_ROUTE_{status.upper()}",
            severity="error",
            actionability="actionable",
            coordinate={"modelo": binding["modelo"], "revision": binding["revision"], "binding": binding["binding_id"]},
            message=f"binding route does not satisfy static closure: {', '.join(failures)}",
            evidence=(required_mapping(binding["location"], context="binding location"),),
        )
    )


def _append_unconsumed(
    binding: dict[str, object],
    typed: list[dict[str, object]],
    structural: list[dict[str, object]],
    registration: dict[str, object] | None,
    results: ConsumerSignals,
) -> None:
    disposition = str(registration.get("disposition")) if registration else "unregistered"
    row, finding_row = unconsumed_binding_report(
        binding,
        typed_consumers=typed,
        structural_mentions=structural,
        provider_disposition=disposition,
        python_literal_references=len(results.code_refs_by_binding.get(str(binding["binding_id"]), [])),
    )
    if row is None:
        return
    results.unreferenced_classification[str(row["classification"])] += 1
    results.unreferenced_disposition[disposition] += 1
    results.unreferenced_provider[str(binding.get("provider_kind") or "<missing>")] += 1
    results.unreferenced_modelo[str(binding["modelo"])] += 1
    results.unreferenced_rows.append(row)
    if finding_row is not None:
        results.findings.append(finding_row)
