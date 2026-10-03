"""Report for the authoritative locale audit."""

from __future__ import annotations

from .signal_contracts import TranslationBacklogItem, TranslationMatrix
from .signal_discovery import covered_by_namespace


def signal_finite_dynamic_keys(finite_families: dict[str, tuple[str, ...]]) -> set[str]:
    """Signal finite dynamic keys."""
    finite_dynamic_keys = {key for values in finite_families.values() for key in values}
    return finite_dynamic_keys


def signal_findings(
    inventory_findings: list[dict[str, object]],
    catalogue_findings: list[dict[str, object]],
    required_keys: set[str],
    matrix: TranslationMatrix,
    catalogue_only_findings: list[dict[str, object]],
    unresolved_families: tuple[str, ...],
) -> list[dict[str, object]]:
    """Signal findings."""
    unbounded_findings: list[dict[str, object]] = [
        {
            "classification": "blocking",
            "kind": "unbounded_key_family",
            "key_prefix": marker,
            "next_action": "replace with a finite canonical key declaration",
        }
        for marker in unresolved_families
    ]
    findings: list[dict[str, object]] = [
        *inventory_findings,
        *(finding for finding in catalogue_findings if finding.get("key") not in required_keys),
        *matrix["findings"],
        *catalogue_only_findings,
        *unbounded_findings,
    ]
    return findings


def signal_keys_to_repair(backlog: list[TranslationBacklogItem]) -> set[str]:
    """Signal keys to repair."""
    keys_to_repair = {
        str(item["key"]) for item in backlog if isinstance(item, dict) and item["state"] == "needs_repair"
    }
    return keys_to_repair


def signal_translation_backlog(
    matrix: TranslationMatrix, inventory_open: bool
) -> tuple[list[TranslationBacklogItem], dict[str, object]]:
    """Signal translation backlog."""
    backlog = matrix["backlog"]
    keys_to_translate = {
        str(item["key"]) for item in backlog if isinstance(item, dict) and item["state"] in {"missing", "needs_value"}
    }
    cells_to_translate = sum(
        1 for item in backlog if isinstance(item, dict) and item["state"] in {"missing", "needs_value"}
    )
    keys_to_repair = signal_keys_to_repair(backlog)
    translation_backlog = {
        "exact": not inventory_open,
        "unique_keys_to_translate": len(keys_to_translate) if not inventory_open else None,
        "cells_to_translate": cells_to_translate if not inventory_open else None,
        "known_unique_keys_to_translate": len(keys_to_translate),
        "known_cells_to_translate": cells_to_translate,
        "unique_keys_to_repair": len(keys_to_repair),
        "cells_to_repair": matrix["cells"]["needs_repair"],
        "cells_to_review": matrix["cells"]["needs_review"],
    }
    return backlog, translation_backlog


def signal_dynamic_family_details(
    finite_families: dict[str, tuple[str, ...]],
    unresolved_families: tuple[str, ...],
    locale_leaves: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Signal dynamic family details."""
    dynamic_key_families: dict[str, object] = {
        "finite": [
            {
                "key_prefix": marker,
                "concrete_keys": list(keys),
            }
            for marker, keys in sorted(finite_families.items())
        ],
        "unresolved": [
            {
                "key_prefix": marker,
                "concrete_catalogue_keys": sorted(
                    {
                        key
                        for leaves in locale_leaves.values()
                        for key in leaves
                        if covered_by_namespace(key, (marker.rstrip("*").rstrip("."),))
                    }
                ),
            }
            for marker in unresolved_families
        ],
    }
    return dynamic_key_families


def signal_catalogue_only_cells(locale_leaves: dict[str, dict[str, object]], required_keys: set[str]) -> int:
    """Count populated catalogue cells outside the required key inventory."""
    return sum(1 for leaves in locale_leaves.values() for key in leaves if key not in required_keys)
