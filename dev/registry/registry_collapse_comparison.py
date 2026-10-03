"""Typed registry and temporal comparison primitives for collapse verification."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic_core import to_jsonable_python

from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
)
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .registry_collapse_models import _REPRESENTATION_ONLY, CheckStatus, ComparisonResult


def _typed_projection(value: object) -> object:
    """Project a typed value to comparable JSON, members of an unordered set in canonical order.

    A set's iteration order follows its insertion history, so two equal sets can
    list their members differently; dumping straight to JSON would compare them
    as sequences. The model is dumped in Python mode so a set stays a set, and
    each leaf takes the JSON form Pydantic gives it.
    """
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return _typed_projection(dump(mode="python"))
    if isinstance(value, Mapping):
        return {
            str(key): _typed_projection(child) for key, child in value.items() if str(key) not in _REPRESENTATION_ONLY
        }
    if isinstance(value, set | frozenset):
        return sorted((_typed_projection(child) for child in value), key=canonical_json_bytes)
    if isinstance(value, list | tuple):
        return [_typed_projection(child) for child in value]
    return to_jsonable_python(value)


def _first_difference(left: object, right: object, path: str = "$") -> Mapping[str, object] | None:
    if type(left) is not type(right):
        return {"location": path, "before": left, "after": right, "reason": "type_changed"}
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return _mapping_difference(left, right, path)
    if isinstance(left, list) and isinstance(right, list):
        return _sequence_difference(left, right, path)
    return None if left == right else {"location": path, "before": left, "after": right, "reason": "value_changed"}


def _mapping_difference(
    left: Mapping[object, object],
    right: Mapping[object, object],
    path: str,
) -> Mapping[str, object] | None:
    # Mapping key order is serialization detail; sequence order remains meaningful.
    if set(left) != set(right):
        return {
            "location": path,
            "before": sorted(left, key=str),
            "after": sorted(right, key=str),
            "reason": "mapping_keys_changed",
        }
    for key in sorted(left, key=str):
        difference = _first_difference(left[key], right[key], f"{path}.{key}")
        if difference is not None:
            return difference
    return None


def _sequence_difference(
    left: list[object],
    right: list[object],
    path: str,
) -> Mapping[str, object] | None:
    if len(left) != len(right):
        return {"location": path, "before": len(left), "after": len(right), "reason": "length_changed"}
    for index, (before, after) in enumerate(zip(left, right, strict=True)):
        difference = _first_difference(before, after, f"{path}[{index}]")
        if difference is not None:
            return difference
    return None


def compare_modelos(before: ModeloDefinition, after: ModeloDefinition) -> ComparisonResult:
    """Compare complete typed meaning after validating storage-sidecar projection."""
    sidecar_gaps = (*_lineage_attestation_projection_gaps(before), *_lineage_attestation_projection_gaps(after))
    if sidecar_gaps:
        return ComparisonResult(CheckStatus.FAILED, len(before.revisions), sidecar_gaps)
    left, right = _typed_projection(before), _typed_projection(after)
    difference = _first_difference(left, right)
    return ComparisonResult(
        status=CheckStatus.PASSED if difference is None else CheckStatus.FAILED,
        checked=len(before.revisions),
        differences=() if difference is None else (difference,),
    )


def _lineage_attestation_projection_gaps(modelo: ModeloDefinition) -> tuple[Mapping[str, object], ...]:
    """Require every excluded lineage sidecar to repeat its effective casilla provenance."""
    gaps: list[Mapping[str, object]] = []
    for revision_id, revision in modelo.revisions.items():
        by_lineage: dict[str, list[CasillaDefinition]] = {}
        for casilla in revision.casillas:
            if casilla.continuidad_id is not None:
                by_lineage.setdefault(str(casilla.continuidad_id), []).append(casilla)
        for attestation in revision.lineage_attestations:
            if attestation.family != "casillas" or attestation.continuidad_id is None:
                gaps.append(
                    {
                        "location": f"$.revisions.{revision_id}.lineage_attestations",
                        "reason": "unsupported_lineage_attestation_projection",
                        "family": attestation.family,
                    }
                )
                continue
            matches = by_lineage.get(str(attestation.continuidad_id), ())
            if len(matches) != 1:
                gaps.append(
                    {
                        "location": f"$.revisions.{revision_id}.lineage_attestations",
                        "reason": "lineage_attestation_target_not_unique",
                        "continuidad_id": str(attestation.continuidad_id),
                    }
                )
                continue
            casilla = matches[0]
            projected = {
                "origin": casilla.continuidad_origin,
                "evidence": casilla.continuidad_evidence,
                "legal_refs": casilla.legal_refs,
                "source_refs": casilla.source_refs,
            }
            authored = {
                "origin": attestation.origin,
                "evidence": attestation.evidence,
                "legal_refs": attestation.legal_refs,
                "source_refs": attestation.source_refs,
            }
            if _typed_projection(projected) != _typed_projection(authored):
                gaps.append(
                    {
                        "location": f"$.revisions.{revision_id}.lineage_attestations.{attestation.continuidad_id}",
                        "reason": "lineage_attestation_provenance_differs_from_hydrated_casilla",
                    }
                )
    return tuple(gaps)
