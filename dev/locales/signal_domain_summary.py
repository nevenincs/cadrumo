"""Domain summary for the authoritative locale audit."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence

from .signal_contracts import TranslationBacklogItem, TranslationMatrix
from .signal_discovery import signal_key_domain


def domain_translation_locale_counts(items: list[TranslationBacklogItem], locales: list[str]) -> dict[str, int]:
    """Domain translation locale counts."""
    by_locale = {
        locale: sum(1 for item in items if item["locale"] == locale and item["state"] in {"missing", "needs_value"})
        for locale in locales
    }
    return by_locale


def domain_stale_translation_cells(
    locale_leaves: Mapping[str, Mapping[str, object]], domain: str, required_keys: set[str]
) -> int:
    """Domain stale translation cells."""
    stale = sum(
        1
        for leaves in locale_leaves.values()
        for key in leaves
        if signal_key_domain(key) == domain and key not in required_keys
    )
    return stale


def domain_translation_state(to_translate: int, states: Counter[str], stale: int) -> str:
    """Domain translation state."""
    state = (
        "translate"
        if to_translate
        else "repair"
        if states["needs_repair"]
        else "review"
        if states["needs_review"]
        else "stale"
        if stale
        else "complete"
    )
    return state


def domain_summaries(
    required_keys: set[str],
    matrix: TranslationMatrix,
    locale_leaves: Mapping[str, Mapping[str, object]],
    inventory_findings: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Summarize translation work by domain, retaining blocking inventory findings."""
    locales = sorted(locale_leaves)
    keys_by_domain: dict[str, set[str]] = defaultdict(set)
    for key in required_keys:
        keys_by_domain[signal_key_domain(key)].add(key)
    backlog = matrix["backlog"]
    rows: list[dict[str, object]] = []
    for domain in sorted(keys_by_domain):
        append_translation_domain_summary(domain, keys_by_domain, backlog, locales, locale_leaves, required_keys, rows)
    unassigned = next((row for row in rows if row["domain"] == "unassigned"), None)
    if unassigned is None:
        unassigned: dict[str, object] = {
            "domain": "unassigned",
            "state": "complete",
            "required_keys": 0,
            "keys_to_translate": 0,
            "to_translate": 0,
            "needs_repair": 0,
            "needs_review": 0,
            "catalogue_only": 0,
            "to_translate_by_locale": dict.fromkeys(locales, 0),
            "next_action": None,
        }
        rows.append(unassigned)
    blocking_inventory_findings = [
        finding for finding in inventory_findings if finding.get("classification") == "blocking"
    ]
    unassigned["inventory_violations"] = len(blocking_inventory_findings)
    if blocking_inventory_findings:
        unassigned["state"] = "inventory_open"
        unassigned["next_action"] = "canonicalize production presentation declarations"
    order = {"inventory_open": 0, "translate": 1, "repair": 2, "review": 3, "stale": 4, "complete": 5}

    def _sort_key(row: dict[str, object]) -> tuple[int, int, str]:
        raw_count = row["to_translate"]
        count = raw_count if isinstance(raw_count, int) else 0
        return order[str(row["state"])], -count, str(row["domain"])

    return sorted(rows, key=_sort_key)


def locale_summaries(
    required_keys: set[str],
    matrix: TranslationMatrix,
    locale_leaves: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    """Summarize required cells and stale catalogue entries for every locale."""
    backlog = matrix["backlog"]
    rows: list[dict[str, object]] = []
    for locale, leaves in sorted(locale_leaves.items()):
        items = [item for item in backlog if isinstance(item, dict) and item.get("locale") == locale]
        states = Counter(str(item["state"]) for item in items)
        rows.append(
            {
                "locale": locale,
                "required": len(required_keys),
                "defined": len(required_keys) - states["missing"],
                "ready": len(required_keys) - len(items),
                "missing": states["missing"],
                "needs_value": states["needs_value"],
                "to_translate": states["missing"] + states["needs_value"],
                "needs_repair": states["needs_repair"],
                "needs_review": states["needs_review"],
                "catalogue_only": sum(1 for key in leaves if key not in required_keys),
            }
        )
    return rows


def largest_domain_locale(domains: Sequence[Mapping[str, object]]) -> tuple[str, str, int] | None:
    """Select the largest nonempty domain and locale translation backlog."""
    candidates: list[tuple[int, str, str]] = []
    for row in domains:
        by_locale = row.get("to_translate_by_locale")
        if not isinstance(by_locale, dict):
            continue
        for locale, raw_count in by_locale.items():
            if not isinstance(raw_count, int):
                continue
            count = raw_count
            if count:
                candidates.append((count, str(row["domain"]), str(locale)))
    if not candidates:
        return None
    count, domain, locale = max(candidates)
    return domain, locale, count


def headline(
    backlog: Mapping[str, object],
    locales: Sequence[Mapping[str, object]],
    largest: tuple[str, str, int] | None,
    inventory_items: int,
) -> str:
    """Describe exact totals or the known backlog while source inventory remains open."""
    locale_text = ", ".join(f"{row['locale']} {row['to_translate']}" for row in locales)
    largest_text = f" Largest backlog: {largest[0]}/{largest[1]} with {largest[2]}." if largest else ""
    if not backlog["exact"]:
        return (
            f"Translation total is not yet knowable: canonicalize {inventory_items} inventory violations. "
            f"Known backlog: {backlog['known_cells_to_translate']} cells across "
            f"{backlog['known_unique_keys_to_translate']} keys ({locale_text}).{largest_text}"
        )
    return (
        f"Translate {backlog['cells_to_translate']} locale cells for {backlog['unique_keys_to_translate']} "
        f"unique keys: {locale_text}.{largest_text}"
    )


def next_action(
    inventory_open: bool,
    inventory_items: int,
    matrix: TranslationMatrix,
    domains: Sequence[Mapping[str, object]],
    catalogue_only: int,
) -> dict[str, object] | None:
    """Choose the first supported repair action for the current inventory and backlog."""
    if inventory_open:
        return {
            "action": "canonicalize_production_declarations",
            "items": inventory_items,
            "command": "fix source declarations, then run just check-locales",
        }
    cells = matrix["cells"]
    if int(cells["missing"]):
        return {
            "action": "create_missing_catalogue_leaves",
            "items": cells["missing"],
            "command": "just locales-scaffold",
        }
    if int(cells["needs_value"]):
        largest = largest_domain_locale(domains)
        return {
            "action": "translate",
            "domain": largest[0] if largest else None,
            "locale": largest[1] if largest else None,
            "cells": largest[2] if largest else cells["needs_value"],
            "command": "just locales-set-batch <manifest>",
        }
    if catalogue_only:
        return {
            "action": "remove_stale_keys",
            "items": catalogue_only,
            "command": "just locales-remove-batch <manifest>",
        }
    return None


def append_translation_domain_summary(
    domain: str,
    keys_by_domain: dict[str, set[str]],
    backlog: list[TranslationBacklogItem],
    locales: list[str],
    locale_leaves: Mapping[str, Mapping[str, object]],
    required_keys: set[str],
    rows: list[dict[str, object]],
) -> None:
    """Append translation domain summary."""
    keys = keys_by_domain[domain]
    items = [item for item in backlog if isinstance(item, dict) and item.get("domain") == domain]
    states = Counter(str(item["state"]) for item in items)
    by_locale = domain_translation_locale_counts(items, locales)
    translated_keys = {str(item["key"]) for item in items if item["state"] in {"missing", "needs_value"}}
    stale = domain_stale_translation_cells(locale_leaves, domain, required_keys)
    to_translate = states["missing"] + states["needs_value"]
    state = domain_translation_state(to_translate, states, stale)
    largest_locale = max(locales, key=lambda locale: (by_locale[locale], locale))
    rows.append(
        {
            "domain": domain,
            "state": state,
            "required_keys": len(keys),
            "keys_to_translate": len(translated_keys),
            "to_translate": to_translate,
            "needs_repair": states["needs_repair"],
            "needs_review": states["needs_review"],
            "catalogue_only": stale,
            "to_translate_by_locale": by_locale,
            "next_action": (
                f"translate {domain}/{largest_locale}: {by_locale[largest_locale]} cells"
                if to_translate
                else f"repair {states['needs_repair']} broken translations"
                if states["needs_repair"]
                else f"review {states['needs_review']} suspicious translations"
                if states["needs_review"]
                else None
            ),
        }
    )
