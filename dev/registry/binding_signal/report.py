"""Assemble the binding-signal artifact from independent audit stages."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .common import model_dump, required_mapping, rows
from .consumer_audit import ConsumerSignals
from .models import SignalInputs
from .revision_audit import RevisionSignals

SCHEMA_VERSION = "binding-signal.v3"
_SUMMARY_FINDING_LIMIT = 25
_CRITICAL_LIMITATION_CODES = frozenset(
    {
        "PROVIDER_REGISTRATION_IMPORT_FAILED",
        "REGISTRY_LOADER_FAILED",
        "RUNTIME_RESOLVER_INVENTORY_IMPORT_FAILED",
        "CANONICAL_CONSUMER_PROJECTION_IMPORT_FAILED",
        "CONSUMER_CENSUS_UNAVAILABLE",
        "TOML_PARSE_FAILURES",
        "SUPPORT_ENVELOPE_UNAVAILABLE",
    }
)


def build_report(
    inputs: SignalInputs,
    revisions: RevisionSignals,
    consumers: ConsumerSignals,
) -> dict[str, object]:
    """Create the complete advisory inventory with the stable v3 shape."""
    _append_late_limitations(inputs, consumers)
    findings = [*revisions.findings, *consumers.findings]
    counters = _report_counters(inputs, revisions, consumers, findings)
    revision_rows = _revision_rows(inputs, revisions)
    provider_distribution = _provider_distribution(revisions, inputs.registrations)
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return _payload(
        inputs,
        revisions,
        consumers,
        findings,
        counters,
        revision_rows,
        provider_distribution,
        generated_at,
    )


def _append_late_limitations(inputs: SignalInputs, consumers: ConsumerSignals) -> None:
    raw = inputs.raw
    if raw.modelos_without_revisions:
        inputs.limitations.append(
            {
                "code": "MODELOS_WITHOUT_REVISIONS",
                "count": len(raw.modelos_without_revisions),
                "items": raw.modelos_without_revisions,
            }
        )
    if raw.parse_failures:
        inputs.limitations.append(
            {"code": "TOML_PARSE_FAILURES", "count": len(raw.parse_failures), "items": raw.parse_failures}
        )
    if consumers.census_unavailable_modelo:
        inputs.limitations.append(
            {
                "code": "CONSUMER_CENSUS_UNAVAILABLE",
                "count": sum(consumers.census_unavailable_modelo.values()),
                "by_modelo": dict(sorted(consumers.census_unavailable_modelo.items())),
            }
        )


def _report_counters(
    inputs: SignalInputs,
    revisions: RevisionSignals,
    consumers: ConsumerSignals,
    findings: list[dict[str, object]],
) -> dict[str, Any]:
    route_status = Counter(_closure_status(route) for route in consumers.routes)
    canonical_consumer_counts = Counter(
        item["kind"] for references in revisions.canonical_consumers.values() for item in references
    )
    classification = "processing_error" if _processing_error(inputs) else "measured"
    return {
        "findings_by_code": Counter(item["code"] for item in findings),
        "finding_severity": dict(sorted(Counter(item["severity"] for item in findings).items())),
        "route_status": route_status,
        "canonical_consumer_counts": canonical_consumer_counts,
        "classification": classification,
    }


def _closure_status(route: dict[str, object]) -> str:
    closure = required_mapping(route["closure"], context="binding route closure")
    return str(closure["status"])


def _processing_error(inputs: SignalInputs) -> bool:
    if inputs.raw.parse_failures:
        return True
    return any(str(item.get("code")) in _CRITICAL_LIMITATION_CODES for item in inputs.limitations)


def _revision_rows(inputs: SignalInputs, signals: RevisionSignals) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for coordinate in sorted(inputs.raw.revisions):
        modelo_id, revision_id = coordinate
        raw = inputs.raw.revisions[coordinate]
        effective = inputs.compiled.get(coordinate)
        compiled_families = model_dump(effective) if effective is not None else {}
        effective_families = compiled_families or raw["families"]
        result.append(
            {
                "modelo": modelo_id,
                "revision": revision_id,
                "predecessor": raw["metadata"].get("predecessor"),
                "declared_casillas": signals.declared_casilla_counts[coordinate],
                "effective_casillas": signals.effective_casilla_counts[coordinate],
                "inherited_casillas": max(
                    0,
                    signals.effective_casilla_counts[coordinate] - signals.declared_casilla_counts[coordinate],
                ),
                "authored_bindings": len(rows(raw["families"].get("bindings", ()))),
                "effective_bindings": len(rows(effective_families.get("bindings", ()))),
                "authored_relations": len(rows(raw["families"].get("relations", ()))),
                "authored_formulas": len(rows(raw["families"].get("formulas", ()))),
                "effective_formulas": len(rows(effective_families.get("formulas", ()))),
                "compiled_materialisation_available": coordinate in inputs.compiled,
            }
        )
    return result


def _provider_distribution(
    signals: RevisionSignals,
    registrations: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    return [
        {
            "provider_kind": kind,
            "bindings": signals.provider_counts[kind],
            "modelos": len(signals.provider_modelos[kind]),
            "revisions": len(signals.provider_revisions[kind]),
            "registration": registrations.get(kind),
        }
        for kind in sorted(signals.provider_counts)
    ]


def _payload(
    inputs: SignalInputs,
    revisions: RevisionSignals,
    consumers: ConsumerSignals,
    findings: list[dict[str, object]],
    counters: dict[str, Any],
    revision_rows: list[dict[str, object]],
    provider_distribution: list[dict[str, object]],
    generated_at: str,
) -> dict[str, object]:
    scope = _scope_payload(inputs)
    summary = _summary_payload(inputs, revisions, consumers, findings, counters)
    lanes = _lanes_payload(inputs, revisions, consumers, counters, revision_rows, provider_distribution)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "scope": scope,
        "summary": summary,
        "lanes": lanes,
        "bindings": revisions.binding_rows,
        "canonical_consumer_references": _canonical_references(revisions),
        "structural_consumer_references": revisions.consumer_refs,
        "python_binding_references": consumers.code_binding_refs,
        "casilla_edges": revisions.casilla_edges,
        "routes": consumers.routes,
        "unreferenced_bindings": consumers.unreferenced_rows,
        "findings": sorted(findings, key=lambda item: str(item["key"])),
        "hotspots": _hotspots(counters, consumers),
        "limitations": inputs.limitations,
    }


def _scope_payload(inputs: SignalInputs) -> dict[str, object]:
    support = inputs.support_scope
    envelope = (
        {
            "authority": "supported_filing_years",
            "floor": support.floor,
            "horizon": support.horizon,
            "hard_ceiling": support.hard_ceiling,
        }
        if support is not None
        else None
    )
    return {
        "root": inputs.root.resolve().as_posix(),
        "registry_root": inputs.registry_root.resolve().as_posix(),
        "authority": "advisory",
        "tests_run": False,
        "support_envelope": envelope,
        "revisions_below_support_floor": sorted(inputs.raw.revisions_below_floor),
    }


def _summary_payload(
    inputs: SignalInputs,
    revisions: RevisionSignals,
    consumers: ConsumerSignals,
    findings: list[dict[str, object]],
    counters: dict[str, Any],
) -> dict[str, object]:
    return {
        "classification": counters["classification"],
        "modelos": len({modelo for modelo, _revision in inputs.raw.revisions}),
        "revisions": len(inputs.raw.revisions),
        "revisions_below_support_floor": len(inputs.raw.revisions_below_floor),
        "bindings": len(revisions.binding_rows),
        "canonical_consumer_references": sum(len(items) for items in revisions.canonical_consumers.values()),
        "structural_consumer_references": len(revisions.consumer_refs),
        "python_binding_references": len(consumers.code_binding_refs),
        "binding_routes": len(consumers.routes),
        "casilla_edges": len(revisions.casilla_edges),
        "unreferenced_bindings": len(consumers.unreferenced_rows),
        "consumer_census_unavailable_bindings": sum(consumers.census_unavailable_modelo.values()),
        "findings": len(findings),
        "finding_severity": counters["finding_severity"],
        "limitations": len(inputs.limitations),
    }


def _lanes_payload(
    inputs: SignalInputs,
    revisions: RevisionSignals,
    consumers: ConsumerSignals,
    counters: dict[str, Any],
    revision_rows: list[dict[str, object]],
    provider_distribution: list[dict[str, object]],
) -> dict[str, object]:
    from collections import Counter

    return {
        "fragment_inventory": {
            "files_by_family": dict(sorted(inputs.raw.family_file_counts.items())),
            "rows_by_family": dict(sorted(inputs.raw.family_row_counts.items())),
        },
        "revision_topology": {
            "predecessor_shapes": dict(sorted(revisions.predecessor_shapes.items())),
            "revisions": revision_rows,
        },
        "declaration_shape": dict(sorted(revisions.declaration_shapes.items())),
        "provider_distribution": provider_distribution,
        "provider_enrollment": [inputs.registrations[key] for key in sorted(inputs.registrations)],
        "runtime_resolver_enrollment": [inputs.runtime_resolvers[key] for key in sorted(inputs.runtime_resolvers)],
        "temporal_distribution": dict(sorted(revisions.temporal_counts.items())),
        "canonical_consumer_distribution": dict(sorted(counters["canonical_consumer_counts"].items())),
        "structural_consumer_distribution": dict(
            sorted(Counter(item["family"] for item in revisions.consumer_refs).items())
        ),
        "route_status": dict(sorted(counters["route_status"].items())),
        "unreferenced_bindings": {
            "authority": "canonical_typed_registry_consumers",
            "by_classification": dict(sorted(consumers.unreferenced_classification.items())),
            "by_provider_disposition": dict(sorted(consumers.unreferenced_disposition.items())),
            "by_provider_kind": dict(sorted(consumers.unreferenced_provider.items())),
            "by_modelo": dict(sorted(consumers.unreferenced_modelo.items())),
        },
    }


def _canonical_references(revisions: RevisionSignals) -> list[dict[str, object]]:
    return [
        {"modelo": modelo, "revision": revision, "binding": binding, "consumers": consumers}
        for (modelo, revision, binding), consumers in sorted(revisions.canonical_consumers.items())
    ]


def _hotspots(counters: dict[str, Any], consumers: ConsumerSignals) -> dict[str, object]:
    finding_counts = counters["findings_by_code"]
    route_status = counters["route_status"]
    return {
        "findings_by_code": [
            {"code": code, "count": count}
            for code, count in sorted(finding_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "open_routes_by_status": [
            {"status": status, "count": count}
            for status, count in sorted(route_status.items(), key=lambda item: (-item[1], item[0]))
            if status.startswith("open_")
        ],
        "unreferenced_by_classification": [
            {"classification": key, "count": count}
            for key, count in sorted(
                consumers.unreferenced_classification.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "unreferenced_by_modelo": [
            {"modelo": key, "count": count}
            for key, count in sorted(consumers.unreferenced_modelo.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


def blocking_findings(payload: Mapping[str, object]) -> list[Mapping[str, object]]:
    """Return findings that meet the signal's actionable error threshold."""
    return [
        item
        for item in rows(payload["findings"])
        if item["severity"] == "error" and item["actionability"] == "actionable"
    ]


def summary(payload: Mapping[str, object], output: Path) -> dict[str, object]:
    """Create the compact command-line envelope for a full binding report."""
    lanes = required_mapping(payload["lanes"], context="audit lanes")
    blocking = blocking_findings(payload)
    summary_data = required_mapping(payload["summary"], context="audit summary")
    if summary_data.get("classification") == "processing_error":
        codes = sorted({str(item.get("code")) for item in rows(payload.get("limitations", ()))})
        headline = f"binding census incomplete ({', '.join(codes) or 'unknown'}); counts below are partial"
    elif blocking:
        headline = f"{len(blocking)} blocking binding finding(s); full list in the output artifact"
    else:
        headline = "no blocking binding findings"
    return {
        "schema_version": "binding-signal-summary.v3",
        "headline": headline,
        "blocking_findings_total": len(blocking),
        "blocking_findings": [
            {"code": item["code"], **required_mapping(item["coordinate"], context="finding coordinate")}
            for item in blocking[:_SUMMARY_FINDING_LIMIT]
        ],
        "output": output.resolve().as_posix(),
        "summary": payload["summary"],
        "declaration_shape": lanes["declaration_shape"],
        "route_status": lanes["route_status"],
        "hotspots": payload["hotspots"],
    }
