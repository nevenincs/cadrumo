"""Measure authored and executable binding-route signal without running tests.

The audit has two independent inputs:

* raw registry fragments, which establish what is on disk and which declaration
  generation each row uses;
* the development loader and binding-provider registrations, which establish the
  compiler-materialised revision surface and the code-enrolled resolution mechanism.

Failure to import either live surface is recorded as a limitation. Raw enumeration
still completes, so an in-flight registry migration remains measurable.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "binding-signal.v2"
BINDING_REF_KEYS = frozenset(
    {
        "binding",
        "binding_id",
        "binding_ids",
        "bindings",
        "target_binding",
        "source_binding",
        "source_bindings",
        "alternate_bindings",
    }
)


@dataclass(frozen=True)
class Location:
    """Stable authored-fragment coordinate for one declaration row."""

    path: str
    family: str
    ordinal: int


def _json_value(value: object) -> object:
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset, tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _stable_dump(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_value(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _load_toml(path: Path) -> tuple[dict[str, object] | None, str | None]:
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream), None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _revision_table(data: Mapping[str, object], revision_id: str) -> Mapping[str, object]:
    revisions = data.get("revisions")
    if not isinstance(revisions, Mapping):
        return {}
    revision = revisions.get(revision_id)
    return revision if isinstance(revision, Mapping) else {}


def _rows(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _walk_binding_refs(value: object, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], str]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            child = (*path, key_text)
            if key_text in BINDING_REF_KEYS or key_text.endswith("_binding") or key_text.endswith("_binding_id"):
                for binding_id in _string_values(item):
                    yield child, binding_id
            yield from _walk_binding_refs(item, child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            yield from _walk_binding_refs(item, (*path, str(index)))


def _provider(binding: Mapping[str, object]) -> tuple[str | None, Mapping[str, object], str]:
    provider = binding.get("provider")
    if isinstance(provider, Mapping):
        kind = provider.get("kind")
        return (kind if isinstance(kind, str) else None, provider, "provider_union")
    source = binding.get("source")
    selector = binding.get("selector")
    return (
        source if isinstance(source, str) else None,
        selector if isinstance(selector, Mapping) else {},
        "source_selector_legacy" if source is not None or selector is not None else "unclassified",
    )


def _temporal_shape(provider: Mapping[str, object]) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    temporal = provider.get("temporal")
    temporal_kind = "none"
    if isinstance(temporal, Mapping):
        kind = temporal.get("kind")
        temporal_kind = kind if isinstance(kind, str) else "untyped"

    relative: list[str] = []
    absolute: list[str] = []

    def visit(value: object, parts: tuple[str, ...], inside_temporal: bool) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                key_text = str(key)
                visit(item, (*parts, key_text), inside_temporal or key_text == "temporal")
            return
        leaf = parts[-1] if parts else ""
        locus = ".".join(parts)
        if inside_temporal and any(token in leaf for token in ("year", "period", "offset", "span")):
            relative.append(locus)
        elif not inside_temporal and (
            leaf in {"filing_year", "revision", "revision_id", "year"}
            or leaf.endswith("_filing_year")
            or leaf.endswith("_revision")
        ):
            absolute.append(locus)

    visit(provider, (), False)
    return temporal_kind, tuple(sorted(set(relative))), tuple(sorted(set(absolute)))


def _model_dump(value: object) -> dict[str, object]:
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        result = dump(mode="json")
        return result if isinstance(result, dict) else {}
    return {}


def _registration_inventory(root: Path) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    limitations: list[dict[str, object]] = []
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    try:
        from cadrumo.domain.calculations.registry.binding_provider_registration import (
            BINDING_PROVIDER_REGISTRATIONS,
        )
    except Exception as exc:
        limitations.append(
            {
                "code": "PROVIDER_REGISTRATION_IMPORT_FAILED",
                "message": f"{type(exc).__name__}: {exc}",
            }
        )
        return {}, limitations

    result: dict[str, dict[str, object]] = {}
    for kind, registration in BINDING_PROVIDER_REGISTRATIONS.items():
        route = registration.route
        provider_model = registration.provider_model
        validator = registration.validator
        kind_value = str(getattr(kind, "value", kind))
        result[kind_value] = {
            "kind": kind_value,
            "provider_model": f"{provider_model.__module__}.{provider_model.__name__}",
            "validator": (f"{validator.__module__}.{validator.__name__}" if validator is not None else None),
            "disposition": registration.disposition,
            "output": registration.output,
            "permitted_value_channels": sorted(item.value for item in registration.permitted_value_channels),
            "permitted_aggregation_ops": sorted(item.value for item in registration.permitted_aggregation_ops),
            "permitted_terminal_origins": sorted(item.value for item in registration.permitted_terminal_origins),
            "row_grouping": getattr(registration.row_grouping, "value", registration.row_grouping),
            "route": {
                "type": type(route).__name__,
                "resolver_id": getattr(route, "resolver_id", None),
                "stage": getattr(route, "stage", None),
                "owner": getattr(route, "owner", None),
                "reason": getattr(route, "reason", None),
            },
        }
    return result, limitations


def _compiled_revisions(
    root: Path,
    authored_registry_root: Path,
) -> tuple[dict[tuple[str, str], object], list[dict[str, object]]]:
    """Load compiler-materialised revisions without running full authority validation."""
    limitations: list[dict[str, object]] = []
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    try:
        from dev.registry.compiler.loader import load_registry_tree

        modelos, _catalogues = load_registry_tree(authored_registry_root)
    except Exception as exc:
        limitations.append(
            {
                "code": "REGISTRY_LOADER_FAILED",
                "message": f"{type(exc).__name__}: {exc}",
            }
        )
        return {}, limitations

    result: dict[tuple[str, str], object] = {}
    for modelo in modelos:
        modelo_id = str(modelo.id)
        for revision_id, revision in modelo.revisions.items():
            result[(modelo_id, str(revision_id))] = revision
    return result, limitations


def _runtime_resolver_inventory(
    root: Path,
) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    """Enumerate the executable resolver classes joined by their stable resolver id."""
    limitations: list[dict[str, object]] = []
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    try:
        from cadrumo.application.modelo.calculation_route import CALCULATION_ROUTE_RESOLVER_OWNERSHIP
    except Exception as exc:
        limitations.append(
            {
                "code": "RUNTIME_RESOLVER_INVENTORY_IMPORT_FAILED",
                "message": f"{type(exc).__name__}: {exc}",
            }
        )
        return {}, limitations

    result: dict[str, dict[str, object]] = {}
    for row in CALCULATION_ROUTE_RESOLVER_OWNERSHIP:
        resolver_id = str(row.resolver_id)
        resolver_type = row.resolver_type
        result[resolver_id] = {
            "resolver_id": resolver_id,
            "stage": row.stage,
            "resolver_type": (
                f"{resolver_type.__module__}.{resolver_type.__name__}" if resolver_type is not None else None
            ),
            "owned_sources": sorted(str(getattr(item, "value", item)) for item in row.owned_sources),
        }
    return result, limitations


class _BindingLiteralVisitor(ast.NodeVisitor):
    def __init__(self, *, binding_ids: frozenset[str], path: str) -> None:
        self.binding_ids = binding_ids
        self.path = path
        self.scope: list[str] = []
        self.rows: list[dict[str, object]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and node.value in self.binding_ids:
            self.rows.append(
                {
                    "binding_id": node.value,
                    "path": self.path,
                    "line": node.lineno,
                    "scope": ".".join(self.scope) or "<module>",
                    "surface": (
                        "test" if "/tests/" in f"/{self.path}" or Path(self.path).name.startswith("test_") else "code"
                    ),
                }
            )


def _python_binding_references(
    root: Path,
    binding_ids: frozenset[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Find exact binding-id literals without treating generated/dynamic references as absent."""
    rows: list[dict[str, object]] = []
    limitations: list[dict[str, object]] = []
    scan_roots = (root / "src" / "cadrumo", root / "dev" / "registry")
    for scan_root in scan_roots:
        for path in sorted(scan_root.rglob("*.py")):
            relative = _relative(path, root)
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, SyntaxError, UnicodeError) as exc:
                limitations.append(
                    {
                        "code": "PYTHON_BINDING_REFERENCE_PARSE_FAILED",
                        "path": relative,
                        "message": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            visitor = _BindingLiteralVisitor(binding_ids=binding_ids, path=relative)
            visitor.visit(tree)
            rows.extend(visitor.rows)
    return rows, limitations


def _finding(
    code: str,
    *,
    severity: str,
    actionability: str,
    coordinate: Mapping[str, object],
    message: str,
    evidence: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    key_parts = [code, *(f"{key}={coordinate[key]}" for key in sorted(coordinate))]
    return {
        "key": "|".join(key_parts),
        "code": code,
        "severity": severity,
        "actionability": actionability,
        "coordinate": dict(coordinate),
        "message": message,
        "evidence": list(evidence),
    }


def _binding_closure(
    binding: Mapping[str, object],
    registration: Mapping[str, object] | None,
    runtime_resolvers: Mapping[str, Mapping[str, object]],
) -> tuple[str, tuple[str, ...]]:
    """Grade one binding occurrence against the enrolled static closure contract."""
    failures: list[str] = []
    provider = binding.get("provider")
    value = binding.get("value")
    if not isinstance(provider, Mapping) or not isinstance(provider.get("kind"), str):
        failures.append("provider_union_member_missing")
    if not isinstance(value, Mapping):
        failures.append("value_contract_missing")
    if registration is None:
        failures.append("provider_registration_missing")
        return "open_registration", tuple(failures)

    channel = value.get("channel") if isinstance(value, Mapping) else None
    permitted_channels = registration.get("permitted_value_channels", ())
    if channel not in permitted_channels:
        failures.append("value_channel_not_permitted")
    aggregation = binding.get("aggregation")
    if isinstance(aggregation, Mapping):
        operation = aggregation.get("op")
        if operation not in registration.get("permitted_aggregation_ops", ()):
            failures.append("aggregation_operation_not_permitted")
    authored_origins = _rows(binding.get("terminal_origins"))
    permitted_origins = registration.get("permitted_terminal_origins", ())
    for origin in authored_origins:
        if origin.get("source_class") not in permitted_origins:
            failures.append("terminal_origin_not_permitted")
    if not permitted_origins:
        failures.append("terminal_origin_contract_missing")
    if failures:
        return "open_contract", tuple(sorted(set(failures)))

    disposition = registration.get("disposition")
    route = registration.get("route")
    resolver_id = route.get("resolver_id") if isinstance(route, Mapping) else None
    if disposition == "non_runtime":
        return "closed_non_runtime", ()
    if disposition == "deferred":
        return "closed_deferred", ()
    if disposition == "advisory":
        return "closed_advisory", ()
    if disposition != "filing_grade":
        return "open_disposition", ("unknown_registration_disposition",)
    if not isinstance(resolver_id, str):
        return "open_runtime_route", ("filing_grade_resolver_id_missing",)
    if resolver_id not in runtime_resolvers:
        return "open_runtime_route", ("filing_grade_resolver_not_executable",)
    return "closed_filing", ()


def audit(root: Path) -> dict[str, object]:
    """Return the complete advisory binding inventory and reverse-route signal."""
    from dev.registry.analysis.edition_delta_status import edition_token_in_identifier

    registry_root = root / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
    registrations, registration_limits = _registration_inventory(root)
    compiled, loader_limits = _compiled_revisions(root, registry_root.parent)
    runtime_resolvers, resolver_limits = _runtime_resolver_inventory(root)
    limitations = [*registration_limits, *loader_limits, *resolver_limits]
    try:
        from cadrumo.domain.calculations.registry.binding_targets import binding_consumers
    except Exception as exc:
        binding_consumers = None
        limitations.append(
            {
                "code": "CANONICAL_CONSUMER_PROJECTION_IMPORT_FAILED",
                "message": f"{type(exc).__name__}: {exc}",
            }
        )

    raw_revisions: dict[tuple[str, str], dict[str, object]] = {}
    parse_failures: list[dict[str, object]] = []
    family_file_counts: Counter[str] = Counter()
    family_row_counts: Counter[str] = Counter()

    for modelo_dir in sorted(path for path in registry_root.iterdir() if path.is_dir()):
        revisions_dir = modelo_dir / "revisions"
        if not revisions_dir.is_dir():
            continue
        for revision_dir in sorted(path for path in revisions_dir.iterdir() if path.is_dir()):
            coordinate = (modelo_dir.name, revision_dir.name)
            record: dict[str, object] = {
                "modelo": modelo_dir.name,
                "revision": revision_dir.name,
                "metadata": {},
                "families": defaultdict(list),
                "locations": defaultdict(list),
            }
            revision_file = revision_dir / "revision.toml"
            revision_data, error = _load_toml(revision_file)
            if error:
                parse_failures.append({"path": _relative(revision_file, root), "error": error})
            elif revision_data is not None:
                record["metadata"] = dict(_revision_table(revision_data, revision_dir.name))

            for family_dir in sorted(path for path in revision_dir.iterdir() if path.is_dir()):
                family = "export_layouts" if family_dir.name == "export" else family_dir.name
                for fragment in sorted(family_dir.glob("*.toml")):
                    family_file_counts[family] += 1
                    data, error = _load_toml(fragment)
                    if error:
                        parse_failures.append({"path": _relative(fragment, root), "error": error})
                        continue
                    if data is None:
                        parse_failures.append(
                            {
                                "path": _relative(fragment, root),
                                "error": "TOML loader returned no data and no diagnostic",
                            }
                        )
                        continue
                    table = _revision_table(data, revision_dir.name)
                    rows = _rows(table.get(family))
                    family_row_counts[family] += len(rows)
                    for ordinal, row in enumerate(rows, 1):
                        record["families"][family].append(dict(row))
                        record["locations"][family].append(asdict(Location(_relative(fragment, root), family, ordinal)))
            raw_revisions[coordinate] = record

    findings: list[dict[str, object]] = []
    routes: list[dict[str, object]] = []
    casilla_edges: list[dict[str, object]] = []
    consumer_refs: list[dict[str, object]] = []
    canonical_consumers: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    binding_rows: list[dict[str, object]] = []
    declaration_shapes: Counter[str] = Counter()
    provider_counts: Counter[str] = Counter()
    provider_modelos: dict[str, set[str]] = defaultdict(set)
    provider_revisions: dict[str, set[str]] = defaultdict(set)
    temporal_counts: Counter[str] = Counter()
    predecessor_shapes: Counter[str] = Counter()
    declared_casilla_counts: Counter[tuple[str, str]] = Counter()
    effective_casilla_counts: Counter[tuple[str, str]] = Counter()

    for (modelo_id, revision_id), record in sorted(raw_revisions.items()):
        metadata = record["metadata"]
        predecessor = metadata.get("predecessor") if isinstance(metadata, Mapping) else None
        if predecessor is None:
            predecessor_shapes["absent_full_copy_or_unstated"] += 1
        elif isinstance(predecessor, str):
            predecessor_shapes["named_delta"] += 1
            if (modelo_id, predecessor) not in raw_revisions:
                findings.append(
                    _finding(
                        "PREDECESSOR_NOT_FOUND",
                        severity="error",
                        actionability="actionable",
                        coordinate={"modelo": modelo_id, "revision": revision_id},
                        message=f"named predecessor {predecessor!r} is not a sibling revision",
                    )
                )
        elif isinstance(predecessor, Mapping) and set(predecessor) == {"none"}:
            predecessor_shapes["declared_root"] += 1
        else:
            predecessor_shapes["invalid"] += 1

        raw_families = record["families"]
        locations = record["locations"]
        raw_bindings = _rows(raw_families.get("bindings", ()))
        raw_binding_locations = locations.get("bindings", ())
        raw_binding_by_id: dict[str, tuple[Mapping[str, object], Mapping[str, object]]] = {}
        for index, binding in enumerate(raw_bindings):
            location = raw_binding_locations[index] if index < len(raw_binding_locations) else {}
            binding_id = binding.get("id")
            if not isinstance(binding_id, str):
                findings.append(
                    _finding(
                        "BINDING_ID_MISSING",
                        severity="error",
                        actionability="actionable",
                        coordinate={"modelo": modelo_id, "revision": revision_id, "ordinal": index + 1},
                        message="binding row has no string id",
                        evidence=(location,),
                    )
                )
                continue
            if binding_id in raw_binding_by_id:
                findings.append(
                    _finding(
                        "DUPLICATE_BINDING_ID",
                        severity="error",
                        actionability="actionable",
                        coordinate={"modelo": modelo_id, "revision": revision_id, "binding": binding_id},
                        message="binding id is authored more than once in the revision",
                        evidence=(raw_binding_by_id[binding_id][1], location),
                    )
                )
            raw_binding_by_id[binding_id] = (binding, location)

        compiled_revision = compiled.get((modelo_id, revision_id))
        compiled_families = _model_dump(compiled_revision) if compiled_revision is not None else {}
        effective_families = compiled_families or raw_families
        effective_bindings = _rows(effective_families.get("bindings", ()))
        effective_binding_by_id: dict[str, Mapping[str, object]] = {}
        for index, binding in enumerate(effective_bindings):
            binding_id = binding.get("id")
            if not isinstance(binding_id, str):
                if compiled_revision is not None:
                    findings.append(
                        _finding(
                            "MATERIALIZED_BINDING_ID_MISSING",
                            severity="error",
                            actionability="actionable",
                            coordinate={"modelo": modelo_id, "revision": revision_id, "ordinal": index + 1},
                            message="compiler-materialised binding has no string id",
                        )
                    )
                continue
            effective_binding_by_id[binding_id] = binding
            authored = raw_binding_by_id.get(binding_id)
            location = (
                authored[1]
                if authored
                else {
                    "path": None,
                    "family": "bindings",
                    "ordinal": None,
                    "surface": "compiler_materialised",
                }
            )
            kind, provider, shape = _provider(binding)
            declaration_shapes[shape] += 1
            provider_counts[kind or "<missing>"] += 1
            provider_modelos[kind or "<missing>"].add(modelo_id)
            provider_revisions[kind or "<missing>"].add(f"{modelo_id}/{revision_id}")
            temporal_kind, relative_fields, absolute_fields = _temporal_shape(provider)
            temporal_counts[temporal_kind] += 1
            binding_rows.append(
                {
                    "modelo": modelo_id,
                    "revision": revision_id,
                    "binding_id": binding_id,
                    "declaration_shape": shape,
                    "declaration_authorship": "authored_here" if authored else "materialised_inherited",
                    "provider_kind": kind,
                    "provider": dict(provider),
                    "value": binding.get("value"),
                    "aggregation": binding.get("aggregation"),
                    "applicability": binding.get("applicability"),
                    "authorship": binding.get("authorship"),
                    "authored_terminal_origins": binding.get("terminal_origins", ()),
                    "temporal": {
                        "kind": temporal_kind,
                        "relative_fields": relative_fields,
                        "absolute_coordinate_fields": absolute_fields,
                    },
                    "location": location,
                }
            )
            if shape != "provider_union":
                findings.append(
                    _finding(
                        "BINDING_DECLARATION_GENERATION_DIVERGENCE",
                        severity="error" if shape == "unclassified" else "warning",
                        actionability="actionable",
                        coordinate={"modelo": modelo_id, "revision": revision_id, "binding": binding_id},
                        message=f"binding uses declaration shape {shape!r} instead of provider_union",
                        evidence=(location,),
                    )
                )
            if kind is None:
                findings.append(
                    _finding(
                        "PROVIDER_KIND_MISSING",
                        severity="error",
                        actionability="actionable",
                        coordinate={"modelo": modelo_id, "revision": revision_id, "binding": binding_id},
                        message="binding has no provider/source discriminator",
                        evidence=(location,),
                    )
                )
            elif registrations and kind not in registrations:
                findings.append(
                    _finding(
                        "PROVIDER_KIND_UNENROLLED",
                        severity="error",
                        actionability="actionable",
                        coordinate={"modelo": modelo_id, "revision": revision_id, "binding": binding_id},
                        message=f"provider kind {kind!r} has no canonical registration",
                        evidence=(location,),
                    )
                )
            edition_token = edition_token_in_identifier(binding_id, revision_id)
            if edition_token is not None:
                findings.append(
                    _finding(
                        "BINDING_ID_TEMPORAL_COUPLING_CANDIDATE",
                        severity="warning",
                        actionability="review",
                        coordinate={"modelo": modelo_id, "revision": revision_id, "binding": binding_id},
                        message=(
                            f"binding id contains declaring-edition token {edition_token!r}; "
                            "semantic equivalence is not inferred"
                        ),
                        evidence=({"edition_token": edition_token, **location},),
                    )
                )
            if absolute_fields:
                findings.append(
                    _finding(
                        "PROVIDER_ABSOLUTE_TEMPORAL_COORDINATE",
                        severity="error",
                        actionability="actionable",
                        coordinate={"modelo": modelo_id, "revision": revision_id, "binding": binding_id},
                        message="provider declares temporal coordinates outside its relative temporal member",
                        evidence=({"fields": absolute_fields, **location},),
                    )
                )

        declared_casillas = _rows(raw_families.get("casillas", ()))
        effective_casillas = _rows(effective_families.get("casillas", ()))
        declared_casilla_counts[(modelo_id, revision_id)] = len(declared_casillas)
        effective_casilla_counts[(modelo_id, revision_id)] = len(effective_casillas)
        for casilla in effective_casillas:
            casilla_id = casilla.get("id")
            requested: list[tuple[str, str]] = []
            primary = casilla.get("binding")
            if isinstance(primary, str):
                requested.append(("primary", primary))
            requested.extend(("alternate", item) for item in _string_values(casilla.get("alternate_bindings")))
            for role, binding_id in requested:
                edge = {
                    "modelo": modelo_id,
                    "revision": revision_id,
                    "casilla": casilla_id,
                    "inherited_from": casilla.get("inherited_from"),
                    "binding": binding_id,
                    "role": role,
                    "binding_declared": binding_id in effective_binding_by_id,
                }
                casilla_edges.append(edge)
                if not edge["binding_declared"]:
                    findings.append(
                        _finding(
                            "EFFECTIVE_CASILLA_BINDING_MISSING",
                            severity="error",
                            actionability="actionable",
                            coordinate={
                                "modelo": modelo_id,
                                "revision": revision_id,
                                "casilla": casilla_id,
                                "binding": binding_id,
                                "role": role,
                            },
                            message="effective casilla references no effective binding in the materialised revision",
                            evidence=(edge,),
                        )
                    )

        if compiled_revision is not None and binding_consumers is not None:
            for binding_id, references in binding_consumers(compiled_revision).items():
                coordinate = (modelo_id, revision_id, str(binding_id))
                canonical_consumers[coordinate].extend(
                    {
                        "kind": str(getattr(reference.kind, "value", reference.kind)),
                        "owner": reference.owner,
                    }
                    for reference in references
                )

        for family, rows in sorted(effective_families.items()):
            if family == "bindings":
                continue
            for row in _rows(rows):
                for field_path, binding_id in _walk_binding_refs(row):
                    consumer_refs.append(
                        {
                            "modelo": modelo_id,
                            "revision": revision_id,
                            "family": family,
                            "consumer_id": row.get("id"),
                            "field_path": ".".join(field_path),
                            "binding_id": binding_id,
                            "binding_declared": binding_id in effective_binding_by_id,
                            "surface": "compiler_materialised" if compiled_revision is not None else "raw_authored",
                        }
                    )

    unique_binding_ids = frozenset(str(item["binding_id"]) for item in binding_rows)
    code_binding_refs, code_reference_limits = _python_binding_references(root, unique_binding_ids)
    limitations.extend(code_reference_limits)
    code_refs_by_binding: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in code_binding_refs:
        code_refs_by_binding[str(item["binding_id"])].append(item)
    structural_consumers: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for item in consumer_refs:
        structural_consumers[(str(item["modelo"]), str(item["revision"]), str(item["binding_id"]))].append(item)

    unreferenced_rows: list[dict[str, object]] = []
    unreferenced_classification: Counter[str] = Counter()
    unreferenced_disposition: Counter[str] = Counter()
    unreferenced_provider: Counter[str] = Counter()
    unreferenced_modelo: Counter[str] = Counter()
    for binding in binding_rows:
        coordinate = (str(binding["modelo"]), str(binding["revision"]), str(binding["binding_id"]))
        typed_consumers = canonical_consumers.get(coordinate, [])
        discovered_consumers = structural_consumers.get(coordinate, [])
        registration = registrations.get(str(binding.get("provider_kind") or ""))
        closure_status, closure_failures = _binding_closure(binding, registration, runtime_resolvers)
        route_registration = registration.get("route") if registration else None
        resolver_id = route_registration.get("resolver_id") if isinstance(route_registration, Mapping) else None
        routes.append(
            {
                "binding": {
                    "modelo": binding["modelo"],
                    "revision": binding["revision"],
                    "id": binding["binding_id"],
                    "declaration_shape": binding["declaration_shape"],
                    "declaration_authorship": binding["declaration_authorship"],
                    "location": binding["location"],
                },
                "consumers": {
                    "canonical": typed_consumers,
                    "structural": discovered_consumers,
                    "exact_python_literals": code_refs_by_binding.get(str(binding["binding_id"]), []),
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
                    "executable": runtime_resolvers.get(str(resolver_id)) if resolver_id else None,
                },
                "terminal_origin_contract": (
                    registration.get("permitted_terminal_origins", ()) if registration else ()
                ),
                "closure": {
                    "status": closure_status,
                    "failures": list(closure_failures),
                    "authority": "static_binding_contract",
                },
            }
        )
        if closure_status.startswith("open_"):
            findings.append(
                _finding(
                    f"BINDING_ROUTE_{closure_status.upper()}",
                    severity="error",
                    actionability="actionable",
                    coordinate={
                        "modelo": binding["modelo"],
                        "revision": binding["revision"],
                        "binding": binding["binding_id"],
                    },
                    message=f"binding route does not satisfy static closure: {', '.join(closure_failures)}",
                    evidence=(binding["location"],),
                )
            )

        if typed_consumers or discovered_consumers:
            continue
        applicability = binding.get("applicability")
        applicability_kind = applicability.get("kind") if isinstance(applicability, Mapping) else None
        provider_disposition = str(registration.get("disposition")) if registration else "unregistered"
        if applicability_kind == "non_calculation":
            classification = "excluded_non_calculation"
        elif provider_disposition == "filing_grade":
            classification = "filing_grade_review"
        elif provider_disposition == "deferred":
            classification = "deferred_provider"
        elif provider_disposition == "non_runtime":
            classification = "non_runtime_provider"
        else:
            classification = "unregistered_provider"
        unreferenced_classification[classification] += 1
        unreferenced_disposition[provider_disposition] += 1
        unreferenced_provider[str(binding.get("provider_kind") or "<missing>")] += 1
        unreferenced_modelo[str(binding["modelo"])] += 1
        row = {
            "modelo": binding["modelo"],
            "revision": binding["revision"],
            "binding": binding["binding_id"],
            "provider_kind": binding.get("provider_kind"),
            "provider_disposition": provider_disposition,
            "applicability": applicability_kind,
            "classification": classification,
            "exact_python_literal_references": len(code_refs_by_binding.get(str(binding["binding_id"]), [])),
            "location": binding["location"],
        }
        unreferenced_rows.append(row)
        if classification == "filing_grade_review":
            findings.append(
                _finding(
                    "UNREFERENCED_FILING_GRADE_BINDING",
                    severity="warning",
                    actionability="review",
                    coordinate={
                        "modelo": binding["modelo"],
                        "revision": binding["revision"],
                        "binding": binding["binding_id"],
                    },
                    message="filing-grade binding has no canonical or structural registry consumer",
                    evidence=(row,),
                )
            )

    if parse_failures:
        limitations.append(
            {
                "code": "TOML_PARSE_FAILURES",
                "count": len(parse_failures),
                "items": parse_failures,
            }
        )

    finding_counts = Counter(item["code"] for item in findings)
    severity_counts = Counter(item["severity"] for item in findings)
    route_status_counts = Counter(item["closure"]["status"] for item in routes)
    canonical_consumer_counts = Counter(
        item["kind"] for references in canonical_consumers.values() for item in references
    )
    critical_limitation_codes = {
        "PROVIDER_REGISTRATION_IMPORT_FAILED",
        "REGISTRY_LOADER_FAILED",
        "RUNTIME_RESOLVER_INVENTORY_IMPORT_FAILED",
        "CANONICAL_CONSUMER_PROJECTION_IMPORT_FAILED",
        "TOML_PARSE_FAILURES",
    }
    processing_error = bool(parse_failures) or any(
        str(item.get("code")) in critical_limitation_codes for item in limitations
    )
    revision_rows = []
    for coordinate in sorted(raw_revisions):
        modelo_id, revision_id = coordinate
        raw = raw_revisions[coordinate]
        revision_rows.append(
            {
                "modelo": modelo_id,
                "revision": revision_id,
                "predecessor": raw["metadata"].get("predecessor"),
                "declared_casillas": declared_casilla_counts[coordinate],
                "effective_casillas": effective_casilla_counts[coordinate],
                "inherited_casillas": max(
                    0, effective_casilla_counts[coordinate] - declared_casilla_counts[coordinate]
                ),
                "authored_bindings": len(_rows(raw["families"].get("bindings", ()))),
                "effective_bindings": len(
                    _rows(_model_dump(compiled.get(coordinate)).get("bindings", ()))
                    if coordinate in compiled
                    else _rows(raw["families"].get("bindings", ()))
                ),
                "authored_relations": len(_rows(raw["families"].get("relations", ()))),
                "authored_formulas": len(_rows(raw["families"].get("formulas", ()))),
                "effective_formulas": len(
                    _rows(_model_dump(compiled.get(coordinate)).get("formulas", ()))
                    if coordinate in compiled
                    else _rows(raw["families"].get("formulas", ()))
                ),
                "compiled_materialisation_available": coordinate in compiled,
            }
        )

    provider_distribution = []
    for kind in sorted(provider_counts):
        provider_distribution.append(
            {
                "provider_kind": kind,
                "bindings": provider_counts[kind],
                "modelos": len(provider_modelos[kind]),
                "revisions": len(provider_revisions[kind]),
                "registration": registrations.get(kind),
            }
        )

    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "scope": {
            "root": root.resolve().as_posix(),
            "registry_root": registry_root.resolve().as_posix(),
            "authority": "advisory",
            "tests_run": False,
        },
        "summary": {
            "classification": "processing_error" if processing_error else "measured",
            "modelos": len({modelo for modelo, _revision in raw_revisions}),
            "revisions": len(raw_revisions),
            "bindings": len(binding_rows),
            "canonical_consumer_references": sum(len(items) for items in canonical_consumers.values()),
            "structural_consumer_references": len(consumer_refs),
            "python_binding_references": len(code_binding_refs),
            "binding_routes": len(routes),
            "casilla_edges": len(casilla_edges),
            "unreferenced_bindings": len(unreferenced_rows),
            "findings": len(findings),
            "finding_severity": dict(sorted(severity_counts.items())),
            "limitations": len(limitations),
        },
        "lanes": {
            "fragment_inventory": {
                "files_by_family": dict(sorted(family_file_counts.items())),
                "rows_by_family": dict(sorted(family_row_counts.items())),
            },
            "revision_topology": {
                "predecessor_shapes": dict(sorted(predecessor_shapes.items())),
                "revisions": revision_rows,
            },
            "declaration_shape": dict(sorted(declaration_shapes.items())),
            "provider_distribution": provider_distribution,
            "provider_enrollment": [registrations[key] for key in sorted(registrations)],
            "runtime_resolver_enrollment": [runtime_resolvers[key] for key in sorted(runtime_resolvers)],
            "temporal_distribution": dict(sorted(temporal_counts.items())),
            "canonical_consumer_distribution": dict(sorted(canonical_consumer_counts.items())),
            "structural_consumer_distribution": dict(sorted(Counter(item["family"] for item in consumer_refs).items())),
            "route_status": dict(sorted(route_status_counts.items())),
            "unreferenced_bindings": {
                "authority": "canonical_and_structural_registry_consumers",
                "by_classification": dict(sorted(unreferenced_classification.items())),
                "by_provider_disposition": dict(sorted(unreferenced_disposition.items())),
                "by_provider_kind": dict(sorted(unreferenced_provider.items())),
                "by_modelo": dict(sorted(unreferenced_modelo.items())),
            },
        },
        "bindings": binding_rows,
        "canonical_consumer_references": [
            {
                "modelo": modelo,
                "revision": revision,
                "binding": binding,
                "consumers": consumers,
            }
            for (modelo, revision, binding), consumers in sorted(canonical_consumers.items())
        ],
        "structural_consumer_references": consumer_refs,
        "python_binding_references": code_binding_refs,
        "casilla_edges": casilla_edges,
        "routes": routes,
        "unreferenced_bindings": unreferenced_rows,
        "findings": sorted(findings, key=lambda item: item["key"]),
        "hotspots": {
            "findings_by_code": [
                {"code": code, "count": count}
                for code, count in sorted(finding_counts.items(), key=lambda item: (-item[1], item[0]))
            ],
            "open_routes_by_status": [
                {"status": status, "count": count}
                for status, count in sorted(route_status_counts.items(), key=lambda item: (-item[1], item[0]))
                if status.startswith("open_")
            ],
            "unreferenced_by_classification": [
                {"classification": classification, "count": count}
                for classification, count in sorted(
                    unreferenced_classification.items(), key=lambda item: (-item[1], item[0])
                )
            ],
            "unreferenced_by_modelo": [
                {"modelo": modelo, "count": count}
                for modelo, count in sorted(unreferenced_modelo.items(), key=lambda item: (-item[1], item[0]))
            ],
        },
        "limitations": limitations,
    }


def _summary(payload: Mapping[str, object], output: Path) -> dict[str, object]:
    return {
        "schema_version": "binding-signal-summary.v2",
        "output": output.resolve().as_posix(),
        "summary": payload["summary"],
        "declaration_shape": payload["lanes"]["declaration_shape"],
        "route_status": payload["lanes"]["route_status"],
        "hotspots": payload["hotspots"],
    }


def main() -> int:
    """Measure bindings, persist the detailed artifact, and print one summary envelope."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.environ.get("CADRUMO_DEV_ARTIFACTS_DIR", ".tmp")) / "binding-signal.json",
        help="Detailed JSON destination; the just command overrides this with its run artifact path.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when actionable error findings exist; default findings are advisory.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        payload = audit(root)
        _stable_dump(output, payload)
        summary = _summary(payload, output)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        processing_error = payload["summary"]["classification"] == "processing_error"
        actionable_errors = any(
            item["severity"] == "error" and item["actionability"] == "actionable" for item in payload["findings"]
        )
        if processing_error:
            return 2
        if args.strict and actionable_errors:
            return 1
        return 0
    except Exception as exc:
        failure = {
            "schema_version": "binding-signal-summary.v2",
            "output": output.resolve().as_posix(),
            "summary": {
                "classification": "processing_error",
                "exception_type": type(exc).__name__,
                "message": str(exc),
            },
        }
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
