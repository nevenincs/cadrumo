"""Deterministic ownership-manifest contract for the live fixture census."""

from __future__ import annotations

import argparse
import ast
import builtins
import copy
import hashlib
import json
import os
import sys
import tempfile
import tomllib
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, replace
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT
from .fixture_census import (
    FactoryFixtureCandidate,
    FixtureCensus,
    FixtureRecord,
    census,
    iter_source_files,
)

MANIFEST_PATH: Final[Path] = Path(__file__).with_name("fixture_ownership.toml")
_SCHEMA: Final[str] = "fixture-ownership-v6"
_RETAINED_CURRENT_OWNER: Final[str] = "retained-current-owner"
_RETAINED_DIVERGENT: Final[str] = "retained-divergent"
_SUBSTITUTABLE_DUPLICATE: Final[str] = "substitutable-duplicate"
_DIVERGENCE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "body",
        "lifecycle",
        "owner-global",
        "compound",
    }
)
_ADJUDICATED_DISPOSITIONS: Final[frozenset[str]] = frozenset({_RETAINED_DIVERGENT, _SUBSTITUTABLE_DUPLICATE})


class FixtureOwnershipError(RuntimeError):
    """Raised when fixture ownership is incomplete, stale, or substitutable."""


def fixture_id(record: FixtureRecord) -> str:
    """Return the stable manifest identity for one fixture declaration."""
    return f"{record.path}:{record.line}:{record.qualname}"


def _sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _constraint_sha256(record: FixtureRecord) -> str:
    parameters = list(record.parameters)
    if record.owner_kind == "class" and parameters and parameters[0].name in {"self", "cls"}:
        parameters = parameters[1:]
    dependencies = list(record.dependencies)
    if record.owner_kind == "class" and dependencies and dependencies[0] in {"self", "cls"}:
        dependencies = dependencies[1:]
    extra_keywords = {
        name: expression
        for name, expression in record.decorator.keyword_arguments
        if name not in {"autouse", "name", "params", "scope"}
    }
    return _sha256(
        {
            "decorator": {
                "scope": record.decorator.scope,
                "autouse": record.decorator.autouse,
                "params": record.decorator.params_expression,
                "extra_keywords": extra_keywords,
            },
            "parameters": [
                {
                    "name": parameter.name,
                    "kind": parameter.kind,
                    "default": parameter.default,
                }
                for parameter in parameters
            ],
            "dependencies": dependencies,
        }
    )


def _topology_payload(record: FixtureRecord) -> dict[str, object]:
    return {
        "imports": [asdict(binding) for binding in record.imported_bindings],
        "consumers": [asdict(consumer) for consumer in record.consumers],
        "autouse_reach": [asdict(consumer) for consumer in record.autouse_reach],
    }


def _bound_names(node: ast.AST) -> set[str]:
    names = {child.id for child in ast.walk(node) if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)}
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        names.add(node.name)
    return names


def _executable_body(body: list[ast.stmt]) -> list[ast.stmt]:
    """Exclude a leading function docstring from runtime evidence."""
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


class _RuntimeNormalizer(ast.NodeTransformer):
    """Remove syntax that does not change ordinary executable fixture behavior."""

    def _function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef:
        node = self.generic_visit(node)
        assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body = node.body[1:]
        node.returns = None
        node.type_comment = None
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ):
            argument.annotation = None
            argument.type_comment = None
        if node.args.vararg is not None:
            node.args.vararg.annotation = None
            node.args.vararg.type_comment = None
        if node.args.kwarg is not None:
            node.args.kwarg.annotation = None
            node.args.kwarg.type_comment = None
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node = self.generic_visit(node)
        assert isinstance(node, ast.ClassDef)
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body = node.body[1:]
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST | None:
        node = self.generic_visit(node)
        assert isinstance(node, ast.AnnAssign)
        if node.value is None:
            return None
        return ast.Assign(targets=[node.target], value=node.value)


def _runtime_dump(node: ast.AST) -> str:
    normalized = _RuntimeNormalizer().visit(copy.deepcopy(node))
    if normalized is None:
        return "<annotation-only>"
    return ast.dump(normalized, annotate_fields=True, include_attributes=False)


def _module_bindings(tree: ast.Module) -> dict[str, ast.AST]:
    bindings: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for name in _bound_names(node):
                bindings[name] = node
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".", maxsplit=1)[0]
                if isinstance(node, ast.Import):
                    bindings[bound_name] = ast.Import(names=[copy.deepcopy(alias)])
                else:
                    bindings[bound_name] = ast.ImportFrom(
                        module=node.module,
                        names=[copy.deepcopy(alias)],
                        level=node.level,
                    )
    return bindings


def _referenced_names(node: ast.AST) -> set[str]:
    local_names = _bound_names(node)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        local_names.update(argument.arg for argument in node.args.posonlyargs)
        local_names.update(argument.arg for argument in node.args.args)
        local_names.update(argument.arg for argument in node.args.kwonlyargs)
        if node.args.vararg is not None:
            local_names.add(node.args.vararg.arg)
        if node.args.kwarg is not None:
            local_names.add(node.args.kwarg.arg)
    return (
        {child.id for child in ast.walk(node) if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)}
        - local_names
        - frozenset(dir(builtins))
    )


def _binding_semantics(
    name: str,
    bindings: Mapping[str, ast.AST],
    active: frozenset[str] = frozenset(),
) -> object:
    if name in active:
        return {"name": name, "cycle": True}
    node = bindings.get(name)
    if node is None:
        return {"name": name, "binding": "<unresolved>"}
    dependencies = {
        dependency: _binding_semantics(dependency, bindings, active | {name})
        for dependency in sorted(_referenced_names(node) - {name})
    }
    return {"name": name, "runtime_ast": _runtime_dump(node), "dependencies": dependencies}


def _factory_binding_call_node(tree: ast.Module, candidate: FactoryFixtureCandidate) -> ast.Call:
    """Locate the module-level ``name = call(...)`` assignment a candidate names.

    Mirrors the exact shape ``fixture_census._module_level_factory_candidates``
    used to discover the candidate in the first place, so the node found here
    is provably the same one that made this a candidate.
    """
    call_node = next(
        (
            statement.value
            for statement in tree.body
            if isinstance(statement, ast.Assign)
            and isinstance(statement.value, ast.Call)
            and statement.lineno == candidate.line
            and any(isinstance(target, ast.Name) and target.id == candidate.bound_name for target in statement.targets)
        ),
        None,
    )
    if call_node is None:
        raise FixtureOwnershipError(
            f"cannot locate factory call assignment for {candidate.path}:{candidate.line}:{candidate.bound_name}"
        )
    return call_node


def _closure_record_for_candidate(
    fixtures_by_path: Mapping[str, list[FixtureRecord]],
    candidate: FactoryFixtureCandidate,
) -> FixtureRecord:
    """Return the nested ``@pytest.fixture`` closure a resolved candidate produces.

    ``resolved_factory`` names the OUTER factory function, not the closure
    itself, so the closure is the sole direct-child fixture whose qualname
    prefix is that outer function's name -- the same nesting shape
    ``fixture_census._fixture_factory_fact`` required to recognize the factory.
    """
    factory_path, _line, factory_function_name = candidate.resolved_factory.rsplit(":", 2)
    matches = [
        record
        for record in fixtures_by_path.get(factory_path, [])
        if record.qualname != factory_function_name and record.qualname.rsplit(".", 1)[0] == factory_function_name
    ]
    if len(matches) != 1:
        found = (
            ", ".join(f"{record.qualname} (scope={record.decorator.scope}, line {record.line})" for record in matches)
            or "none"
        )
        raise FixtureOwnershipError(
            "cannot uniquely resolve the nested fixture closure for factory "
            f"{candidate.resolved_factory} bound at {candidate.path}:{candidate.line}:{candidate.bound_name}; "
            f"closures found: {found}. A factory returning a DIFFERENT closure per argument -- the shipped case "
            "selects on `scope` -- cannot be resolved statically, because the decorator the binding inherits "
            "is chosen at the call site. Give the factory one closure, or teach this resolver which argument "
            "selects it."
        )
    return matches[0]


def _factory_binding_record(
    candidate: FactoryFixtureCandidate,
    closure_record: FixtureRecord,
    call_node: ast.Call,
) -> FixtureRecord:
    """Materialize the fixture one factory binding actually produces.

    The decorator lives on the closure, not the binding: scope, autouse and
    parameters are properties of the produced fixture, so they are the
    closure's, copied verbatim. The closure's own body is shared by every
    binding of the same factory, so it cannot distinguish them on its own --
    the call arguments at this binding site are folded into the body digest so
    two bindings of the same factory with different arguments are not treated
    as clones by name/body grouping alone.
    """
    has_explicit_name = closure_record.decorator.name_expression is not None
    effective_name = closure_record.effective_name if has_explicit_name else candidate.bound_name
    call_dump = ast.dump(call_node, annotate_fields=True, include_attributes=False)
    normalized_body = "\n".join((closure_record.normalized_body, call_dump))
    normalized_body_sha256 = hashlib.sha256(normalized_body.encode("utf-8")).hexdigest()
    owner_kind = "conftest" if Path(candidate.path).name == "conftest.py" else "module"
    return FixtureRecord(
        path=candidate.path,
        line=candidate.line,
        column=candidate.column,
        qualname=candidate.bound_name,
        function_name=candidate.bound_name,
        effective_name=effective_name,
        owner_kind=owner_kind,
        decorator=closure_record.decorator,
        parameters=closure_record.parameters,
        dependencies=closure_record.dependencies,
        body_ast_format=closure_record.body_ast_format,
        normalized_body=normalized_body,
        normalized_body_sha256=normalized_body_sha256,
        imported_bindings=(),
        consumers=(),
        autouse_reach=(),
    )


def _factory_binding_records(result: FixtureCensus) -> tuple[FixtureRecord, ...]:
    """Return one synthetic FixtureRecord per resolved factory-bound candidate.

    A factory function returns an ``@pytest.fixture``-decorated closure, and a
    module binds that closure to a name through a plain call assignment. The
    assignment carries no decorator, so the decorator-only walk that fills
    ``FixtureCensus.fixtures`` cannot see it, and this binding would otherwise
    never reach a disposition. Each returned record represents the fixture the
    binding actually produces, keyed by its own binding-site identity so it is
    never confused with the closure definition it wraps.
    """
    root = Path(result.root)
    fixtures_by_path: dict[str, list[FixtureRecord]] = {}
    for record in result.fixtures:
        fixtures_by_path.setdefault(record.path, []).append(record)
    parsed_trees: dict[str, ast.Module] = {}
    records: list[FixtureRecord] = []
    for candidate in result.factory_fixture_candidates:
        closure_record = _closure_record_for_candidate(fixtures_by_path, candidate)
        tree = parsed_trees.get(candidate.path)
        if tree is None:
            source = (root / candidate.path).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=candidate.path)
            parsed_trees[candidate.path] = tree
        call_node = _factory_binding_call_node(tree, candidate)
        records.append(_factory_binding_record(candidate, closure_record, call_node))
    return tuple(records)


def _with_factory_bindings(result: FixtureCensus) -> FixtureCensus:
    """Return one census view where every resolved factory binding is a fixture too."""
    return replace(result, fixtures=result.fixtures + _factory_binding_records(result))


def _owner_global_sha256(result: FixtureCensus) -> dict[str, str]:
    """Fingerprint only module bindings referenced by each fixture body.

    A factory-bound record (see ``_factory_binding_record``) has no function
    body of its own at its binding-site line -- it is a call assignment, not a
    def. Its distinguishing content is the call arguments at that site, so
    when no function is found, the call assignment itself stands in as the
    node whose free variables get fingerprinted.
    """
    root = Path(result.root)
    parsed: dict[str, tuple[ast.Module, dict[str, ast.AST]]] = {}
    fingerprints: dict[str, str] = {}
    builtin_names = frozenset(dir(builtins))
    for record in result.fixtures:
        if record.path not in parsed:
            source = (root / record.path).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=record.path)
            parsed[record.path] = (tree, _module_bindings(tree))
        tree, bindings = parsed[record.path]
        function = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.lineno == record.line
                and node.name == record.function_name
            ),
            None,
        )
        if function is not None:
            semantic_nodes: list[ast.AST] = [
                ast.Module(body=_executable_body(function.body), type_ignores=[]),
                *function.args.defaults,
                *(default for default in function.args.kw_defaults if default is not None),
            ]
            fixture_decorator = next(
                (
                    decorator
                    for decorator in function.decorator_list
                    if ast.unparse(decorator) == record.decorator.expression
                ),
                None,
            )
            if isinstance(fixture_decorator, ast.Call):
                semantic_nodes.extend(
                    keyword.value
                    for keyword in fixture_decorator.keywords
                    if keyword.arg not in {"autouse", "name", "scope"}
                )
        else:
            call_node = next(
                (
                    statement.value
                    for statement in tree.body
                    if isinstance(statement, ast.Assign)
                    and isinstance(statement.value, ast.Call)
                    and statement.lineno == record.line
                    and any(
                        isinstance(target, ast.Name) and target.id == record.function_name
                        for target in statement.targets
                    )
                ),
                None,
            )
            if call_node is None:
                raise FixtureOwnershipError(f"cannot locate fixture body for {fixture_id(record)}")
            semantic_nodes = [call_node]
        referenced = sorted(
            {
                name
                for semantic_node in semantic_nodes
                for name in _referenced_names(semantic_node)
                if name not in builtin_names
            }
        )
        evidence = {name: _binding_semantics(name, bindings) for name in referenced}
        fingerprints[fixture_id(record)] = _sha256(evidence)
    return fingerprints


def _divergence_evidence(
    result: FixtureCensus,
    *,
    constraints: Mapping[str, str],
    owner_globals: Mapping[str, str],
) -> dict[str, tuple[str, str]]:
    """Prove every repeated relationship has a concrete semantic distinction."""
    name_groups: dict[str, list[FixtureRecord]] = {}
    body_groups: dict[str, list[FixtureRecord]] = {}
    for record in result.fixtures:
        name_groups.setdefault(record.effective_name, []).append(record)
        body_groups.setdefault(record.normalized_body_sha256, []).append(record)
    evidence: dict[str, tuple[str, str]] = {}
    for record in result.fixtures:
        peers = {
            fixture_id(peer): peer
            for peer in (*name_groups[record.effective_name], *body_groups[record.normalized_body_sha256])
            if fixture_id(peer) != fixture_id(record)
        }
        if not peers:
            continue
        record_id = fixture_id(record)
        distinctions: list[dict[str, str]] = []
        kinds: set[str] = set()
        proven = True
        for peer_id, peer in sorted(peers.items()):
            if record.normalized_body_sha256 != peer.normalized_body_sha256:
                kind = "body"
                values = (record.normalized_body_sha256, peer.normalized_body_sha256)
            elif constraints[record_id] != constraints[peer_id]:
                kind = "lifecycle"
                values = (constraints[record_id], constraints[peer_id])
            elif owner_globals[record_id] != owner_globals[peer_id]:
                kind = "owner-global"
                values = (owner_globals[record_id], owner_globals[peer_id])
            else:
                proven = False
                break
            kinds.add(kind)
            distinctions.append(
                {
                    "peer": peer_id,
                    "kind": kind,
                    "left_sha256": values[0],
                    "right_sha256": values[1],
                }
            )
        if not proven:
            continue
        divergence_kind = next(iter(kinds)) if len(kinds) == 1 else "compound"
        if divergence_kind not in _DIVERGENCE_KINDS:
            raise FixtureOwnershipError(f"unknown divergence kind: {divergence_kind}")
        evidence[record_id] = (divergence_kind, _sha256(distinctions))
    return evidence


def _group_id(kind: str, value: str, member_count: int) -> str:
    return f"{kind}-sha256:{_sha256({'value': value, 'member_count': member_count})}"


def _ownership_groups(
    result: FixtureCensus,
    *,
    constraints: Mapping[str, str],
    owner_globals: Mapping[str, str],
) -> dict[str, tuple[str, int, str]]:
    """Nominate one deterministic canonical owner per substitutable semantic group."""
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for record in result.fixtures:
        record_id = fixture_id(record)
        grouped.setdefault(
            (
                record.normalized_body_sha256,
                constraints[record_id],
                owner_globals[record_id],
            ),
            [],
        ).append(record_id)
    ownership: dict[str, tuple[str, int, str]] = {}
    for raw_members in grouped.values():
        if len(raw_members) < 2:
            continue
        members = sorted(raw_members)
        canonical_owner = members[0]
        group_id = f"ownership-sha256:{_sha256(members)}"
        for record_id in members:
            ownership[record_id] = (group_id, len(members), canonical_owner)
    return ownership


def _fixture_rows(
    result: FixtureCensus,
    repeated_dispositions: Mapping[str, str] | None,
) -> list[dict[str, object]]:
    result = _with_factory_bindings(result)
    name_counts = Counter(record.effective_name for record in result.fixtures)
    body_counts = Counter(record.normalized_body_sha256 for record in result.fixtures)
    repeated_ids = {
        fixture_id(record)
        for record in result.fixtures
        if name_counts[record.effective_name] > 1 or body_counts[record.normalized_body_sha256] > 1
    }
    constraints = {fixture_id(record): _constraint_sha256(record) for record in result.fixtures}
    topology = {fixture_id(record): _topology_payload(record) for record in result.fixtures}
    owner_globals = _owner_global_sha256(result)
    ownership_groups = _ownership_groups(
        result,
        constraints=constraints,
        owner_globals=owner_globals,
    )
    divergence = _divergence_evidence(
        result,
        constraints=constraints,
        owner_globals=owner_globals,
    )
    if repeated_dispositions is None:
        repeated_dispositions = {
            record_id: (_RETAINED_DIVERGENT if record_id in divergence else _SUBSTITUTABLE_DUPLICATE)
            for record_id in repeated_ids
        }
    missing = repeated_ids - repeated_dispositions.keys()
    extra = repeated_dispositions.keys() - repeated_ids
    if missing or extra:
        details = []
        if missing:
            details.append(f"unclassified repeated fixtures: {sorted(missing)}")
        if extra:
            details.append(f"adjudications for non-repeated fixtures: {sorted(extra)}")
        raise FixtureOwnershipError("; ".join(details))
    rows: list[dict[str, object]] = []
    for record in result.fixtures:
        record_id = fixture_id(record)
        disposition = repeated_dispositions.get(record_id, _RETAINED_CURRENT_OWNER)
        if record_id in repeated_ids and disposition not in _ADJUDICATED_DISPOSITIONS:
            raise FixtureOwnershipError(f"invalid repeated-fixture disposition {disposition!r} for {record_id}")
        if disposition == _RETAINED_DIVERGENT and record_id not in divergence:
            raise FixtureOwnershipError(f"retained divergent fixture has no evidence: {record_id}")
        name_count = name_counts[record.effective_name]
        body_count = body_counts[record.normalized_body_sha256]
        topology_payload = topology[record_id]
        divergence_kind, divergence_sha256 = divergence.get(record_id, ("", ""))
        ownership_group_id, ownership_group_member_count, canonical_owner = ownership_groups.get(
            record_id,
            ("", 1, record_id),
        )
        rows.append(
            {
                "id": record_id,
                "effective_name": record.effective_name,
                "owner": canonical_owner,
                "disposition": disposition,
                "body_sha256": record.normalized_body_sha256,
                "scope": record.decorator.scope,
                "autouse": record.decorator.autouse,
                "constraints_sha256": constraints[record_id],
                "owner_globals_sha256": owner_globals[record_id],
                "import_count": len(record.imported_bindings),
                "imports_sha256": _sha256(topology_payload["imports"]),
                "direct_consumer_count": len(record.consumers),
                "direct_consumers_sha256": _sha256(topology_payload["consumers"]),
                "autouse_reach_count": len(record.autouse_reach),
                "autouse_reach_sha256": _sha256(topology_payload["autouse_reach"]),
                "divergence_kind": divergence_kind,
                "divergence_evidence_sha256": divergence_sha256,
                "ownership_group_id": ownership_group_id,
                "ownership_group_member_count": ownership_group_member_count,
                "semantic_name_group_id": (
                    _group_id("effective-name", record.effective_name, name_count) if name_count > 1 else ""
                ),
                "semantic_name_group_member_count": name_count,
                "exact_body_group_id": (
                    _group_id("exact-body", record.normalized_body_sha256, body_count) if body_count > 1 else ""
                ),
                "exact_body_group_member_count": body_count,
            }
        )
    return rows


def build_manifest(
    result: FixtureCensus,
    *,
    repeated_dispositions: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Build a manifest only when every repeated fixture was adjudicated."""
    rows = _fixture_rows(result, repeated_dispositions)
    dispositions = Counter(str(row["disposition"]) for row in rows)
    manifest = {
        "schema": _SCHEMA,
        "census_algorithm": "dev.quality.fixture_census:census",
        "snapshot_source": "stable-working-tree",
        "fixture_count": len(rows),
        "source_count": len(result.sources),
        "dynamic_request_count": len(result.dynamic_fixture_requests),
        "dynamic_requests_sha256": _sha256([asdict(request) for request in result.dynamic_fixture_requests]),
        "sources_sha256": _sha256(result.sources),
        "retained_current_owner_count": dispositions[_RETAINED_CURRENT_OWNER],
        "retained_divergent_count": dispositions[_RETAINED_DIVERGENT],
        "substitutable_duplicate_count": dispositions[_SUBSTITUTABLE_DUPLICATE],
        "records_sha256": _sha256(rows),
    }
    return {"manifest": manifest, "fixture": rows}


def render_manifest(payload: Mapping[str, object]) -> str:
    """Render the ownership payload as deterministic TOML."""
    manifest = payload["manifest"]
    fixtures = payload["fixture"]
    assert isinstance(manifest, Mapping)
    assert isinstance(fixtures, list)
    lines = [
        "# Generated from one stable fail-closed AST census; do not hand-edit fixture records.",
        "# Repeated fixtures require an explicit semantic disposition; equality alone never adjudicates them.",
        "",
        "[manifest]",
    ]
    for key, value in manifest.items():
        lines.append(f"{key} = {_toml_scalar(value)}")
    for row in fixtures:
        assert isinstance(row, Mapping)
        lines.extend(("", "[[fixture]]"))
        for key, value in row.items():
            lines.append(f"{key} = {_toml_scalar(value)}")
    return "\n".join(lines) + "\n"


def _toml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    raise TypeError(f"unsupported TOML scalar: {type(value).__name__}")


def parse_manifest(path: Path = MANIFEST_PATH) -> dict[str, object]:
    """Read one ownership manifest through the standard TOML parser."""
    with path.open("rb") as stream:
        return tomllib.load(stream)


def validate_manifest(result: FixtureCensus, payload: Mapping[str, object]) -> None:
    """Reject drift, incomplete classification, or any substitutable duplicate."""
    raw_rows = payload.get("fixture")
    if not isinstance(raw_rows, list):
        raise FixtureOwnershipError("ownership manifest has no fixture rows")
    dispositions: dict[str, str] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            raise FixtureOwnershipError("ownership manifest contains a non-table fixture row")
        record_id = raw_row.get("id")
        disposition = raw_row.get("disposition")
        if not isinstance(record_id, str) or not isinstance(disposition, str):
            raise FixtureOwnershipError("ownership row requires string id and disposition")
        if record_id in dispositions:
            raise FixtureOwnershipError(f"duplicate ownership row: {record_id}")
        dispositions[record_id] = disposition

    augmented_result = _with_factory_bindings(result)
    name_counts = Counter(record.effective_name for record in augmented_result.fixtures)
    body_counts = Counter(record.normalized_body_sha256 for record in augmented_result.fixtures)
    repeated_ids = {
        fixture_id(record)
        for record in augmented_result.fixtures
        if name_counts[record.effective_name] > 1 or body_counts[record.normalized_body_sha256] > 1
    }
    repeated_dispositions = {
        record_id: disposition for record_id, disposition in dispositions.items() if record_id in repeated_ids
    }
    expected = build_manifest(result, repeated_dispositions=repeated_dispositions)
    if payload != expected:
        raise FixtureOwnershipError("ownership manifest does not exactly match the live fixture census")
    substitutable = sorted(
        record_id for record_id, disposition in dispositions.items() if disposition == _SUBSTITUTABLE_DUPLICATE
    )
    if substitutable:
        raise FixtureOwnershipError(f"substitutable duplicate fixtures remain: {substitutable}")


def _source_snapshot(repo_root: Path) -> tuple[tuple[str, str], ...]:
    root = repo_root.resolve()
    return tuple(
        (path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in iter_source_files(root)
    )


def _source_snapshot_delta(
    before: tuple[tuple[str, str], ...],
    after: tuple[tuple[str, str], ...],
) -> list[dict[str, str]]:
    """Return path/hash-only diagnostics for a changed source snapshot."""
    before_by_path = dict(before)
    after_by_path = dict(after)
    delta: list[dict[str, str]] = []
    for path in sorted(before_by_path.keys() | after_by_path.keys()):
        before_sha256 = before_by_path.get(path)
        after_sha256 = after_by_path.get(path)
        if before_sha256 == after_sha256:
            continue
        if before_sha256 is None:
            status = "added"
        elif after_sha256 is None:
            status = "removed"
        else:
            status = "changed"
        delta.append(
            {
                "path": path,
                "status": status,
                "before_sha256": before_sha256 or "absent",
                "after_sha256": after_sha256 or "absent",
            }
        )
    return delta


def _raise_changed_source_snapshot(
    phase: str,
    before: tuple[tuple[str, str], ...],
    after: tuple[tuple[str, str], ...],
) -> None:
    delta = _source_snapshot_delta(before, after)
    raise FixtureOwnershipError(
        f"fixture source universe changed during {phase}: "
        f"{json.dumps(delta, ensure_ascii=True, separators=(',', ':'), sort_keys=True)}"
    )


def stable_census(repo_root: Path) -> FixtureCensus:
    """Build one census and refuse a source universe that moved during the scan."""
    before = _source_snapshot(repo_root)
    result = census(repo_root)
    after = _source_snapshot(repo_root)
    if before != after:
        _raise_changed_source_snapshot("census generation", before, after)
    return result


def stable_manifest(repo_root: Path) -> dict[str, object]:
    """Build census and owner-global evidence within one guarded source snapshot."""
    before = _source_snapshot(repo_root)
    result = census(repo_root)
    payload = build_manifest(result)
    after = _source_snapshot(repo_root)
    if before != after:
        _raise_changed_source_snapshot("manifest generation", before, after)
    return payload


def _substitutable_ids(payload: Mapping[str, object]) -> list[str]:
    rows = payload.get("fixture")
    if not isinstance(rows, list):
        raise FixtureOwnershipError("ownership manifest has no fixture rows")
    return sorted(
        str(row["id"])
        for row in rows
        if isinstance(row, Mapping)
        and row.get("disposition") == _SUBSTITUTABLE_DUPLICATE
        and isinstance(row.get("id"), str)
    )


def _refuse_substitutable(payload: Mapping[str, object]) -> None:
    substitutable = _substitutable_ids(payload)
    if substitutable:
        raise FixtureOwnershipError(f"substitutable duplicate fixtures remain: {substitutable}")


def write_manifest(repo_root: Path, path: Path = MANIFEST_PATH) -> dict[str, object]:
    """Atomically replace a manifest only after stable, substitute-free generation."""
    source_before = _source_snapshot(repo_root)
    payload = stable_manifest(repo_root)
    _refuse_substitutable(payload)
    rendered = render_manifest(payload).encode("utf-8")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        source_after = _source_snapshot(repo_root)
        if source_before != source_after:
            _raise_changed_source_snapshot("manifest write", source_before, source_after)
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return payload


def check_manifest(repo_root: Path, path: Path = MANIFEST_PATH) -> dict[str, object]:
    """Check a generated manifest and keep proven substitutes visibly red."""
    expected = stable_manifest(repo_root)
    if parse_manifest(path) != expected:
        raise FixtureOwnershipError("ownership manifest does not exactly match stable generation")
    _refuse_substitutable(expected)
    return expected


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="check the committed manifest")
    action.add_argument("--write", action="store_true", help="write a stable generated manifest")
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    arguments = parser.parse_args(argv)
    try:
        if arguments.write:
            payload = write_manifest(arguments.root, arguments.manifest)
        else:
            payload = check_manifest(arguments.root, arguments.manifest)
    except (FixtureOwnershipError, OSError, SyntaxError) as error:
        print(f"fixture ownership failed: {error}", file=sys.stderr)
        return 1
    manifest = payload["manifest"]
    assert isinstance(manifest, Mapping)
    print(
        f"fixtures={manifest['fixture_count']} "
        f"retained-divergent={manifest['retained_divergent_count']} "
        f"substitutable={manifest['substitutable_duplicate_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
