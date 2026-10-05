"""Inspect raw and compiler-materialised binding declarations by revision."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .common import model_dump, rows, string_values
from .models import SignalInputs
from .semantics import finding, provider, structural_binding_mentions, temporal_shape

_Coordinate = tuple[str, str]
_BindingCoordinate = tuple[str, str, str]


@dataclass(slots=True)
class RevisionSignals:
    """Materialised declaration facts shared with the reverse-route stage."""

    findings: list[dict[str, object]] = field(default_factory=list)
    casilla_edges: list[dict[str, object]] = field(default_factory=list)
    consumer_refs: list[dict[str, object]] = field(default_factory=list)
    canonical_consumers: dict[_BindingCoordinate, list[dict[str, object]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    binding_rows: list[dict[str, object]] = field(default_factory=list)
    declaration_shapes: Counter[str] = field(default_factory=Counter)
    provider_counts: Counter[str] = field(default_factory=Counter)
    provider_modelos: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    provider_revisions: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    temporal_counts: Counter[str] = field(default_factory=Counter)
    predecessor_shapes: Counter[str] = field(default_factory=Counter)
    declared_casilla_counts: Counter[_Coordinate] = field(default_factory=Counter)
    effective_casilla_counts: Counter[_Coordinate] = field(default_factory=Counter)


def audit_revisions(
    inputs: SignalInputs,
    edition_token_in_identifier: Callable[[str, str], str | None],
) -> RevisionSignals:
    """Collect declarations, casilla edges, and consumer references in order."""
    signals = RevisionSignals()
    for coordinate, record in sorted(inputs.raw.revisions.items()):
        _audit_revision(inputs, signals, coordinate, record, edition_token_in_identifier)
    return signals


def _audit_revision(
    inputs: SignalInputs,
    signals: RevisionSignals,
    coordinate: _Coordinate,
    record: Any,
    edition_token_in_identifier: Callable[[str, str], str | None],
) -> None:
    metadata = record["metadata"]
    _record_predecessor(metadata.get("predecessor"), coordinate, inputs.raw.declared_coordinates, signals)
    raw_families = record["families"]
    locations = record["locations"]
    raw_binding_by_id = _authored_binding_index(
        raw_families,
        locations,
        coordinate,
        signals.findings,
    )
    compiled_revision = inputs.compiled.get(coordinate)
    compiled_families = model_dump(compiled_revision) if compiled_revision is not None else {}
    effective_families = compiled_families or raw_families
    effective_binding_by_id = _effective_binding_index(
        effective_families,
        raw_binding_by_id,
        coordinate,
        compiled_revision is not None,
        inputs.registrations,
        edition_token_in_identifier,
        signals,
    )
    _audit_casilla_edges(raw_families, effective_families, effective_binding_by_id, coordinate, signals)
    _record_canonical_consumers(inputs, compiled_revision, coordinate, signals)
    _record_structural_consumers(effective_families, effective_binding_by_id, compiled_revision, coordinate, signals)


def _record_predecessor(
    predecessor: object,
    coordinate: _Coordinate,
    declared_coordinates: set[_Coordinate],
    signals: RevisionSignals,
) -> None:
    modelo_id, revision_id = coordinate
    if predecessor is None:
        signals.predecessor_shapes["absent_full_copy_or_unstated"] += 1
    elif isinstance(predecessor, str):
        signals.predecessor_shapes["named_delta"] += 1
        if (modelo_id, predecessor) not in declared_coordinates:
            signals.findings.append(
                finding(
                    "PREDECESSOR_NOT_FOUND",
                    severity="error",
                    actionability="actionable",
                    coordinate={"modelo": modelo_id, "revision": revision_id},
                    message=f"named predecessor {predecessor!r} is not a sibling revision",
                )
            )
    elif isinstance(predecessor, Mapping) and set(predecessor) == {"none"}:
        signals.predecessor_shapes["declared_root"] += 1
    else:
        signals.predecessor_shapes["invalid"] += 1


def _authored_binding_index(
    raw_families: Mapping[str, object],
    locations: Mapping[str, object],
    coordinate: _Coordinate,
    findings: list[dict[str, object]],
) -> dict[str, tuple[Mapping[str, object], Mapping[str, object]]]:
    bindings = rows(raw_families.get("bindings", ()))
    row_locations = locations.get("bindings", ())
    result: dict[str, tuple[Mapping[str, object], Mapping[str, object]]] = {}
    for index, binding in enumerate(bindings):
        location = row_locations[index] if isinstance(row_locations, Sequence) and index < len(row_locations) else {}
        if not isinstance(location, Mapping):
            location = {}
        binding_id = binding.get("id")
        if not isinstance(binding_id, str):
            findings.append(
                finding(
                    "BINDING_ID_MISSING",
                    severity="error",
                    actionability="actionable",
                    coordinate={"modelo": coordinate[0], "revision": coordinate[1], "ordinal": index + 1},
                    message="binding row has no string id",
                    evidence=(location,),
                )
            )
            continue
        if binding_id in result:
            findings.append(
                finding(
                    "DUPLICATE_BINDING_ID",
                    severity="error",
                    actionability="actionable",
                    coordinate={"modelo": coordinate[0], "revision": coordinate[1], "binding": binding_id},
                    message="binding id is authored more than once in the revision",
                    evidence=(result[binding_id][1], location),
                )
            )
        result[binding_id] = (binding, location)
    return result


def _effective_binding_index(
    effective_families: Mapping[str, object],
    authored: Mapping[str, tuple[Mapping[str, object], Mapping[str, object]]],
    coordinate: _Coordinate,
    compiled: bool,
    registrations: Mapping[str, Mapping[str, object]],
    edition_token_in_identifier: Callable[[str, str], str | None],
    signals: RevisionSignals,
) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for index, binding in enumerate(rows(effective_families.get("bindings", ()))):
        binding_id = binding.get("id")
        if not isinstance(binding_id, str):
            _missing_materialized_id(index, coordinate, compiled, signals)
            continue
        result[binding_id] = binding
        _record_effective_binding(
            binding,
            binding_id,
            authored.get(binding_id),
            coordinate,
            registrations,
            edition_token_in_identifier,
            signals,
        )
    return result


def _missing_materialized_id(
    index: int,
    coordinate: _Coordinate,
    compiled: bool,
    signals: RevisionSignals,
) -> None:
    if not compiled:
        return
    signals.findings.append(
        finding(
            "MATERIALIZED_BINDING_ID_MISSING",
            severity="error",
            actionability="actionable",
            coordinate={"modelo": coordinate[0], "revision": coordinate[1], "ordinal": index + 1},
            message="compiler-materialised binding has no string id",
        )
    )


def _record_effective_binding(
    binding: Mapping[str, object],
    binding_id: str,
    authored: tuple[Mapping[str, object], Mapping[str, object]] | None,
    coordinate: _Coordinate,
    registrations: Mapping[str, Mapping[str, object]],
    edition_token_in_identifier: Callable[[str, str], str | None],
    signals: RevisionSignals,
) -> None:
    modelo_id, revision_id = coordinate
    location = authored[1] if authored else _inherited_binding_location()
    kind, provider_payload, shape = provider(binding)
    temporal_kind, relative_fields, absolute_fields = temporal_shape(provider_payload)
    _record_provider_counts(kind, shape, temporal_kind, modelo_id, revision_id, signals)
    signals.binding_rows.append(
        _binding_row(
            binding,
            binding_id,
            authored,
            coordinate,
            location,
            kind,
            provider_payload,
            shape,
            temporal_kind,
            relative_fields,
            absolute_fields,
        )
    )
    _record_binding_shape_findings(shape, kind, binding_id, coordinate, location, registrations, signals)
    _record_binding_temporal_findings(
        binding_id, modelo_id, revision_id, absolute_fields, location, edition_token_in_identifier, signals
    )


def _inherited_binding_location() -> dict[str, object]:
    return {"path": None, "family": "bindings", "ordinal": None, "surface": "compiler_materialised"}


def _record_provider_counts(
    kind: str | None,
    shape: str,
    temporal_kind: str,
    modelo_id: str,
    revision_id: str,
    signals: RevisionSignals,
) -> None:
    label = kind or "<missing>"
    signals.declaration_shapes[shape] += 1
    signals.provider_counts[label] += 1
    signals.provider_modelos[label].add(modelo_id)
    signals.provider_revisions[label].add(f"{modelo_id}/{revision_id}")
    signals.temporal_counts[temporal_kind] += 1


def _binding_row(
    binding: Mapping[str, object],
    binding_id: str,
    authored: tuple[Mapping[str, object], Mapping[str, object]] | None,
    coordinate: _Coordinate,
    location: Mapping[str, object],
    kind: str | None,
    provider_payload: Mapping[str, object],
    shape: str,
    temporal_kind: str,
    relative_fields: tuple[str, ...],
    absolute_fields: tuple[str, ...],
) -> dict[str, object]:
    return {
        "modelo": coordinate[0],
        "revision": coordinate[1],
        "binding_id": binding_id,
        "declaration_shape": shape,
        "declaration_authorship": "authored_here" if authored else "materialised_inherited",
        "provider_kind": kind,
        "provider": dict(provider_payload),
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


def _record_binding_shape_findings(
    shape: str,
    kind: str | None,
    binding_id: str,
    coordinate: _Coordinate,
    location: Mapping[str, object],
    registrations: Mapping[str, Mapping[str, object]],
    signals: RevisionSignals,
) -> None:
    where = {"modelo": coordinate[0], "revision": coordinate[1], "binding": binding_id}
    if shape != "provider_union":
        signals.findings.append(
            finding(
                "BINDING_DECLARATION_GENERATION_DIVERGENCE",
                severity="error" if shape == "unclassified" else "warning",
                actionability="actionable",
                coordinate=where,
                message=f"binding uses declaration shape {shape!r} instead of provider_union",
                evidence=(location,),
            )
        )
    _record_provider_kind_findings(kind, where, location, registrations, signals.findings)


def _record_provider_kind_findings(
    kind: str | None,
    coordinate: Mapping[str, object],
    location: Mapping[str, object],
    registrations: Mapping[str, Mapping[str, object]],
    findings: list[dict[str, object]],
) -> None:
    if kind is None:
        findings.append(
            finding(
                "PROVIDER_KIND_MISSING",
                severity="error",
                actionability="actionable",
                coordinate=coordinate,
                message="binding has no provider/source discriminator",
                evidence=(location,),
            )
        )
    elif registrations and kind not in registrations:
        findings.append(
            finding(
                "PROVIDER_KIND_UNENROLLED",
                severity="error",
                actionability="actionable",
                coordinate=coordinate,
                message=f"provider kind {kind!r} has no canonical registration",
                evidence=(location,),
            )
        )


def _record_binding_temporal_findings(
    binding_id: str,
    modelo_id: str,
    revision_id: str,
    absolute_fields: tuple[str, ...],
    location: Mapping[str, object],
    edition_token_in_identifier: Callable[[str, str], str | None],
    signals: RevisionSignals,
) -> None:
    edition_token = edition_token_in_identifier(binding_id, revision_id)
    coordinate = {"modelo": modelo_id, "revision": revision_id, "binding": binding_id}
    _record_edition_token_finding(edition_token, coordinate, location, signals.findings)
    if absolute_fields:
        signals.findings.append(
            finding(
                "PROVIDER_ABSOLUTE_TEMPORAL_COORDINATE",
                severity="error",
                actionability="actionable",
                coordinate=coordinate,
                message="provider declares temporal coordinates outside its relative temporal member",
                evidence=({"fields": absolute_fields, **location},),
            )
        )


def _record_edition_token_finding(
    edition_token: str | None,
    coordinate: Mapping[str, object],
    location: Mapping[str, object],
    findings: list[dict[str, object]],
) -> None:
    if edition_token is None:
        return
    findings.append(
        finding(
            "BINDING_ID_TEMPORAL_COUPLING_CANDIDATE",
            severity="warning",
            actionability="review",
            coordinate=coordinate,
            message=(
                f"binding id contains declaring-edition token {edition_token!r}; semantic equivalence is not inferred"
            ),
            evidence=({"edition_token": edition_token, **location},),
        )
    )


def _audit_casilla_edges(
    raw_families: Mapping[str, object],
    effective_families: Mapping[str, object],
    effective_binding_by_id: Mapping[str, Mapping[str, object]],
    coordinate: _Coordinate,
    signals: RevisionSignals,
) -> None:
    declared = rows(raw_families.get("casillas", ()))
    effective = rows(effective_families.get("casillas", ()))
    signals.declared_casilla_counts[coordinate] = len(declared)
    signals.effective_casilla_counts[coordinate] = len(effective)
    for casilla in effective:
        _audit_casilla_edges_for_row(casilla, effective_binding_by_id, coordinate, signals)


def _audit_casilla_edges_for_row(
    casilla: Mapping[str, object],
    effective_binding_by_id: Mapping[str, Mapping[str, object]],
    coordinate: _Coordinate,
    signals: RevisionSignals,
) -> None:
    casilla_id = casilla.get("id")
    requested: list[tuple[str, str]] = []
    primary = casilla.get("binding")
    if isinstance(primary, str):
        requested.append(("primary", primary))
    requested.extend(("alternate", item) for item in string_values(casilla.get("alternate_bindings")))
    for role, binding_id in requested:
        _record_casilla_edge(casilla, casilla_id, binding_id, role, effective_binding_by_id, coordinate, signals)


def _record_casilla_edge(
    casilla: Mapping[str, object],
    casilla_id: object,
    binding_id: str,
    role: str,
    effective_binding_by_id: Mapping[str, Mapping[str, object]],
    coordinate: _Coordinate,
    signals: RevisionSignals,
) -> None:
    edge: dict[str, object] = {
        "modelo": coordinate[0],
        "revision": coordinate[1],
        "casilla": casilla_id,
        "inherited_from": casilla.get("inherited_from"),
        "binding": binding_id,
        "role": role,
        "binding_declared": binding_id in effective_binding_by_id,
    }
    signals.casilla_edges.append(edge)
    if not edge["binding_declared"]:
        signals.findings.append(
            finding(
                "EFFECTIVE_CASILLA_BINDING_MISSING",
                severity="error",
                actionability="actionable",
                coordinate={
                    "modelo": coordinate[0],
                    "revision": coordinate[1],
                    "casilla": casilla_id,
                    "binding": binding_id,
                    "role": role,
                },
                message="effective casilla references no effective binding in the materialised revision",
                evidence=(edge,),
            )
        )


def _record_canonical_consumers(
    inputs: SignalInputs,
    compiled_revision: Any,
    coordinate: _Coordinate,
    signals: RevisionSignals,
) -> None:
    if compiled_revision is None or inputs.binding_consumers is None:
        return
    for binding_id, references in inputs.binding_consumers(compiled_revision).items():
        key = (coordinate[0], coordinate[1], str(binding_id))
        signals.canonical_consumers[key].extend(
            {"kind": str(getattr(reference.kind, "value", reference.kind)), "owner": reference.owner}
            for reference in references
        )


def _record_structural_consumers(
    effective_families: Mapping[str, object],
    effective_binding_by_id: Mapping[str, Mapping[str, object]],
    compiled_revision: Any,
    coordinate: _Coordinate,
    signals: RevisionSignals,
) -> None:
    surface = "compiler_materialised" if compiled_revision is not None else "raw_authored"
    for family, row, field_path, binding_id in structural_binding_mentions(effective_families):
        signals.consumer_refs.append(
            {
                "modelo": coordinate[0],
                "revision": coordinate[1],
                "family": family,
                "consumer_id": row.get("id"),
                "field_path": ".".join(field_path),
                "binding_id": binding_id,
                "binding_declared": binding_id in effective_binding_by_id,
                "surface": surface,
            }
        )
