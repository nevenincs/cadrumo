"""Translation matrix for the authoritative locale audit."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from difflib import SequenceMatcher

from ._status import CatalogueLeafState, classify_catalogue_leaf
from .signal_contracts import TranslationBacklogItem, TranslationMatrix
from .signal_discovery import signal_key_domain
from .signal_tokens import human_translation_text, translation_tokens, translation_words


def translation_matrix(
    required_keys: set[str],
    locale_leaves: Mapping[str, Mapping[str, object]],
    spelling: dict[tuple[str, str], tuple[str, ...]] | None = None,
) -> TranslationMatrix:
    """Classify every required locale cell and preserve placeholder and spelling refusals."""
    spelling = spelling or {}
    counts = Counter[str]()
    backlog: list[TranslationBacklogItem] = []
    findings: list[dict[str, object]] = []
    for key in sorted(required_keys):
        inventory_translation_key(key, locale_leaves, spelling, counts, backlog, findings)
    required_cells = len(required_keys) * len(locale_leaves)
    return {
        "backlog": backlog,
        "findings": findings,
        "cells": {
            "required": required_cells,
            "defined": required_cells - counts["missing"],
            "ready": counts["ready"],
            "missing": counts["missing"],
            "needs_value": counts["needs_value"],
            "needs_repair": counts["needs_repair"],
            "needs_review": counts["needs_review"],
        },
    }


def suspicious_translation_locales(
    key: str,
    locale_leaves: Mapping[str, Mapping[str, object]],
) -> set[str]:
    """Identify long target prose that reproduces the Spanish source word sequence."""
    source = locale_leaves.get("es", {}).get(key)
    if not isinstance(source, str):
        return set()
    normalized_source = human_translation_text(source)
    source_words = translation_words(normalized_source)
    if len(normalized_source) < 40 or sum(character.isalpha() for character in normalized_source) < 25:
        return set()
    suspicious: set[str] = set()
    for locale, leaves in locale_leaves.items():
        check_suspicious_translation_locale(locale, leaves, key, normalized_source, source_words, suspicious)
    return suspicious


def inventory_translation_key(
    key: str,
    locale_leaves: Mapping[str, Mapping[str, object]],
    spelling: dict[tuple[str, str], tuple[str, ...]],
    counts: Counter[str],
    backlog: list[TranslationBacklogItem],
    findings: list[dict[str, object]],
) -> None:
    """Inventory translation key."""
    domain = signal_key_domain(key)
    review_locales = suspicious_translation_locales(key, locale_leaves)
    source_value = locale_leaves.get("es", {}).get(key)
    source_placeholders = translation_tokens(source_value) if isinstance(source_value, str) else None
    for locale, leaves in sorted(locale_leaves.items()):
        inventory_translation_cell(
            locale, leaves, key, domain, review_locales, source_placeholders, spelling, counts, backlog, findings
        )


def inventory_translation_cell(
    locale: str,
    leaves: Mapping[str, object],
    key: str,
    domain: str,
    review_locales: set[str],
    source_placeholders: tuple[frozenset[str], frozenset[str]] | None,
    spelling: dict[tuple[str, str], tuple[str, ...]],
    counts: Counter[str],
    backlog: list[TranslationBacklogItem],
    findings: list[dict[str, object]],
) -> None:
    """Inventory translation cell."""
    state, reason = translation_cell_state(locale, leaves, key, source_placeholders, spelling, review_locales)
    counts[state] += 1
    if state == "ready":
        return
    item: TranslationBacklogItem = {
        "domain": domain,
        "key": key,
        "locale": locale,
        "state": state,
        "reason": reason,
        "next_action": (
            "set_translation"
            if state in {"missing", "needs_value"}
            else "review_translation"
            if state == "needs_review"
            else "repair_translation"
        ),
    }
    if reason == "translation_spelling_unknown":
        item["unknown_words"] = list(spelling[(locale, key)])
    backlog.append(item)
    findings.append({"classification": "blocking", "kind": reason, **item})


def translation_cell_state(
    locale: str,
    leaves: Mapping[str, object],
    key: str,
    source_placeholders: tuple[frozenset[str], frozenset[str]] | None,
    spelling: dict[tuple[str, str], tuple[str, ...]],
    review_locales: set[str],
) -> tuple[str, str | None]:
    """Translation cell state."""
    if key not in leaves:
        state, reason = "missing", "translation_missing"
    else:
        value = leaves[key]
        if not isinstance(value, str):
            state, reason = "needs_value", "translation_not_text"
        else:
            leaf_state = classify_catalogue_leaf(key, value)
            if leaf_state is CatalogueLeafState.AUTHORED:
                state, reason = authored_translation_state(
                    locale, value, key, source_placeholders, spelling, review_locales
                )
            elif leaf_state is CatalogueLeafState.UNBINDABLE:
                state, reason = "needs_repair", "reserved_placeholder"
            else:
                state, reason = "needs_value", f"translation_{leaf_state.value}"
    return state, reason


def check_suspicious_translation_locale(
    locale: str,
    leaves: Mapping[str, object],
    key: str,
    normalized_source: str,
    source_words: tuple[str, ...],
    suspicious: set[str],
) -> None:
    """Check suspicious translation locale."""
    if locale == "es":
        return
    target = leaves.get(key)
    if not isinstance(target, str):
        return
    normalized_target = human_translation_text(target)
    target_words = translation_words(normalized_target)
    combined_words = len(source_words) + len(target_words)
    maximum_ratio = 2 * min(len(source_words), len(target_words)) / combined_words if combined_words else 1.0
    if maximum_ratio < 0.985:
        return
    if SequenceMatcher(None, source_words, target_words).ratio() >= 0.985:
        suspicious.add(locale)


def authored_translation_state(
    locale: str,
    value: str,
    key: str,
    source_placeholders: tuple[frozenset[str], frozenset[str]] | None,
    spelling: dict[tuple[str, str], tuple[str, ...]],
    review_locales: set[str],
) -> tuple[str, str | None]:
    """Authored translation state."""
    state, reason = (
        ("needs_repair", "translation_placeholder_mismatch")
        if locale != "es" and source_placeholders is not None and translation_tokens(value) != source_placeholders
        else ("needs_review", "translation_spelling_unknown")
        if (locale, key) in spelling
        else ("needs_review", "translation_too_similar")
        if locale in review_locales
        else ("ready", None)
    )
    return state, reason
