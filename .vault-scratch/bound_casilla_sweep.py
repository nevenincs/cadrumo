"""P02.S06 — bound-casilla binding-resolution sweep.

Enumerates every casilla with `input_kind = "bound"` across every modelo
revision, locates the named binding, and classifies it.

Classifications
---------------
* `direct_resolvable` — selector declares a period anchor
  (``period`` / ``source_periods`` / ``source_period_offset_from_target``)
  and ``required_period_anchors_for_target`` returns at least one
  non-empty anchor across the revision's declared target periods.
  Resolved through `resolve_previous_filing_binding_values`.
* `direct_dead` — selector declares no period anchor and no relation
  in the revision targets it. Silent-zero hazard.
* `relation_driven` — selector declares no period anchor and at least
  one `RelationDefinition` in the revision has
  ``target_binding == binding.id``. Resolved through the relation
  system.
* `relation_orphaned` — selector declares ``relation = "..."`` but no
  matching `RelationDefinition` exists in the revision.
* `non_previous_filing` — binding's source is not ``previous_filing``
  (profile, invoice, ledger, etc.). The cap is irrelevant; resolution
  goes through a different pipeline.

Output: JSON inventory at .vault-scratch/bound_casilla_sweep.json with
one entry per (modelo, revision, casilla_id).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from aeat.core.resources import bundled_path
from aeat.domain.calculations.registry import load_registry_tree
from aeat.domain.calculations.registry._bindings import (
    _PreviousModeloSelector,
    _selector_as_dict,
)
from aeat.domain.calculations.registry._schema import (
    DataBindingDefinition,
    ModeloDefinition,
    ModeloRevision,
    RelationDefinition,
)


REGISTRY_ROOT = bundled_path("registry", "aeat")
OUTPUT_PATH = Path(__file__).resolve().parent / "bound_casilla_sweep.json"


def _binding_by_id(revision: ModeloRevision, binding_id: str) -> DataBindingDefinition | None:
    for binding in revision.bindings:
        if binding.id == binding_id:
            return binding
    return None


def _relations_targeting(revision: ModeloRevision, binding_id: str) -> tuple[RelationDefinition, ...]:
    return tuple(relation for relation in revision.relations if relation.target_binding == binding_id)


def _revision_target_periods(revision: ModeloRevision) -> tuple[str, ...]:
    selector = revision.period_selector
    return tuple(selector.periods)


def _classify_previous_filing(
    revision: ModeloRevision,
    binding: DataBindingDefinition,
) -> dict[str, object]:
    raw_selector = _selector_as_dict(binding)
    try:
        selector = _PreviousModeloSelector.model_validate(raw_selector)
    except Exception as exc:
        return {
            "classification": "selector_validation_failed",
            "detail": str(exc),
            "raw_selector": raw_selector,
        }

    has_period_anchor = bool(
        selector.period is not None
        or selector.source_periods
        or selector.source_period_offset_from_target is not None
    )

    relations = _relations_targeting(revision, binding.id)

    if has_period_anchor:
        target_periods = _revision_target_periods(revision)
        resolves_for: list[str] = []
        suppresses_for: list[str] = []
        for target_period in target_periods:
            anchors = selector.required_period_anchors_for_target(target_period)
            if anchors:
                resolves_for.append(target_period)
            else:
                suppresses_for.append(target_period)
        return {
            "classification": "direct_resolvable",
            "raw_selector": raw_selector,
            "resolves_for_target_periods": resolves_for,
            "suppresses_for_target_periods": suppresses_for,
            "max_year_delta": selector.max_year_delta,
        }

    if selector.relation is not None:
        relation_match = next((r for r in relations if r.id == selector.relation), None)
        if relation_match is not None:
            return {
                "classification": "relation_driven",
                "raw_selector": raw_selector,
                "relation_id": selector.relation,
                "relation_kind": relation_match.kind,
            }
        return {
            "classification": "relation_orphaned",
            "raw_selector": raw_selector,
            "relation_id": selector.relation,
        }

    if relations:
        return {
            "classification": "relation_driven",
            "raw_selector": raw_selector,
            "relation_ids": [r.id for r in relations],
            "relation_kinds": sorted({r.kind for r in relations}),
        }

    return {
        "classification": "direct_dead",
        "raw_selector": raw_selector,
    }


def _classify_binding(
    revision: ModeloRevision,
    binding: DataBindingDefinition,
) -> dict[str, object]:
    if binding.source == "previous_filing":
        return _classify_previous_filing(revision, binding)
    return {
        "classification": "non_previous_filing",
        "binding_source": binding.source,
    }


def _sweep_modelo(modelo: ModeloDefinition) -> Iterable[dict[str, object]]:
    for revision_id, revision in modelo.revisions.items():
        for casilla in revision.casillas:
            if casilla.input_kind != "bound":
                continue
            binding_id = casilla.binding
            if binding_id is None:
                yield {
                    "modelo": modelo.id,
                    "revision": revision_id,
                    "casilla_id": casilla.id,
                    "casilla_label": casilla.label,
                    "binding_id": None,
                    "classification": "bound_casilla_missing_binding_reference",
                }
                continue
            binding = _binding_by_id(revision, binding_id)
            if binding is None:
                yield {
                    "modelo": modelo.id,
                    "revision": revision_id,
                    "casilla_id": casilla.id,
                    "casilla_label": casilla.label,
                    "binding_id": binding_id,
                    "classification": "binding_reference_not_found",
                }
                continue
            classification = _classify_binding(revision, binding)
            entry: dict[str, object] = {
                "modelo": modelo.id,
                "revision": revision_id,
                "casilla_id": casilla.id,
                "casilla_label": casilla.label,
                "binding_id": binding_id,
                "binding_source": binding.source,
            }
            entry.update(classification)
            yield entry


def main() -> None:
    modelos, _catalogues = load_registry_tree(REGISTRY_ROOT)
    inventory: list[dict[str, object]] = []
    for modelo in modelos:
        inventory.extend(_sweep_modelo(modelo))

    by_classification: dict[str, int] = {}
    for entry in inventory:
        key = str(entry.get("classification", "unknown"))
        by_classification[key] = by_classification.get(key, 0) + 1

    output = {
        "total_bound_casillas": len(inventory),
        "by_classification": by_classification,
        "entries": inventory,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Total bound casillas: {len(inventory)}")
    for key, count in sorted(by_classification.items()):
        print(f"  {key}: {count}")


if __name__ == "__main__":
    main()
