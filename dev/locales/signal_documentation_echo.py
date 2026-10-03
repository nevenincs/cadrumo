"""Documentation echo for the authoritative locale audit."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from ._spelling import SpellingToolError, load_dictionaries
from .signal_contracts import DocumentationEchoDictionaries
from .signal_echo_classification import (
    translation_echo_normalize,
    translation_invariant_echo_reason,
    translation_similarity,
)
from .signal_policy import ECHO_SAMPLE_LIMIT, NEAR_ECHO_THRESHOLD


def inventory_documentation_translation_message(
    identity: str,
    translations: tuple[str, ...],
    source_messages: dict[str, str],
    locale: str,
    catalogue: str,
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    echo_cache: DocumentationEchoDictionaries,
    platform_identity_terms: frozenset[str],
    source_echo_samples: list[dict[str, object]],
    invariant_echo_samples: list[dict[str, object]],
    near_echo_samples: list[dict[str, object]],
) -> None:
    """Inventory documentation translation message."""
    source_text = source_messages.get(identity)
    if source_text is None:
        return
    source_forms = tuple(source_text.split("\x04"))
    for index, (source_form, translation_form) in enumerate(zip(source_forms, translations, strict=False)):
        inventory_documentation_translation_form(
            index,
            source_form,
            translation_form,
            source_forms,
            locale,
            catalogue,
            identity,
            repository,
            counts,
            findings,
            echo_cache,
            platform_identity_terms,
            source_echo_samples,
            invariant_echo_samples,
            near_echo_samples,
        )


def inventory_documentation_translation_form(
    index: int,
    source_form: str,
    translation_form: str,
    source_forms: tuple[str, ...],
    locale: str,
    catalogue: str,
    identity: str,
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    echo_cache: DocumentationEchoDictionaries,
    platform_identity_terms: frozenset[str],
    source_echo_samples: list[dict[str, object]],
    invariant_echo_samples: list[dict[str, object]],
    near_echo_samples: list[dict[str, object]],
) -> None:
    """Inventory documentation translation form."""
    counts["docs_translation_comparisons"] += 1
    counts[f"docs_translation_comparisons_{locale}"] += 1
    source_normalized = translation_echo_normalize(source_form)
    translation_normalized = translation_echo_normalize(translation_form)
    ratio = translation_similarity(source_normalized, translation_normalized)
    form = "singular" if len(source_forms) == 1 else f"plural[{index}]"
    location = f"docs/locales/{locale}/LC_MESSAGES/{catalogue}"
    evidence: dict[str, object] = {
        "domain": "docs",
        "form": form,
        "locale": locale,
        "message_id": identity,
        "path": location,
        "ratio": round(ratio, 6),
        "source": source_form,
        "translation": translation_form,
    }
    if source_normalized == translation_normalized:
        record_exact_documentation_echo(
            source_form,
            locale,
            evidence,
            repository,
            counts,
            findings,
            echo_cache,
            platform_identity_terms,
            source_echo_samples,
            invariant_echo_samples,
            near_echo_samples,
        )
    elif ratio >= NEAR_ECHO_THRESHOLD:
        counts["docs_translation_near_echo"] += 1
        counts[f"docs_translation_near_echo_{locale}"] += 1
        finding = {
            "classification": "advisory",
            "kind": "docs_translation_near_echo",
            **evidence,
            "next_action": "review whether this translation is sufficiently localized",
        }
        findings.append(finding)
        if len(near_echo_samples) < ECHO_SAMPLE_LIMIT:
            near_echo_samples.append(evidence)


def record_exact_documentation_echo(
    source_form: str,
    locale: str,
    evidence: dict[str, object],
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    echo_cache: DocumentationEchoDictionaries,
    platform_identity_terms: frozenset[str],
    source_echo_samples: list[dict[str, object]],
    invariant_echo_samples: list[dict[str, object]],
    near_echo_samples: list[dict[str, object]],
) -> None:
    """Record exact documentation echo."""
    if echo_cache.loaded is None and not echo_cache.unavailable:
        try:
            loaded_dictionaries = load_dictionaries(repository)
            object_dictionaries: dict[str, object] = {}
            for dictionary_locale, dictionary in loaded_dictionaries.items():
                object_dictionaries[dictionary_locale] = dictionary
            echo_cache.loaded = object_dictionaries
        except SpellingToolError:
            echo_cache.unavailable = True
    reason = translation_invariant_echo_reason(
        source_form,
        locale,
        dictionary=(echo_cache.loaded or {}).get(locale),
        source_dictionary=(echo_cache.loaded or {}).get("en"),
        platform_terms=platform_identity_terms,
    )
    if reason is None:
        counts["docs_translation_source_echo"] += 1
        counts[f"docs_translation_source_echo_{locale}"] += 1
        finding = {
            "classification": "blocking",
            "kind": "docs_translation_source_echo",
            **evidence,
            "next_action": ("replace the source echo with an accented target-language translation"),
        }
        findings.append(finding)
        if len(source_echo_samples) < ECHO_SAMPLE_LIMIT:
            source_echo_samples.append(evidence)
    else:
        counts["docs_translation_invariant_echo"] += 1
        counts[f"docs_translation_invariant_echo_{locale}"] += 1
        counts[f"docs_translation_invariant_echo_reason_{reason}"] += 1
        counts[f"docs_translation_invariant_echo_{locale}_{reason}"] += 1
        invariant_evidence: dict[str, object] = {**evidence, "reason": reason}
        findings.append(
            {
                "classification": "advisory",
                "kind": "docs_translation_invariant_echo",
                **invariant_evidence,
                "next_action": "retain the independently classified invariant spelling",
            }
        )
        if len(invariant_echo_samples) < ECHO_SAMPLE_LIMIT:
            invariant_echo_samples.append(invariant_evidence)
