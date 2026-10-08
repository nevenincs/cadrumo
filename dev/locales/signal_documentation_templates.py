"""Documentation templates for the authoritative locale audit."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from cadrumo.core.hashing import sha256_file
from dev._paths import UTF_8

from .signal_contracts import DocumentationEchoDictionaries
from .signal_documentation_echo import inventory_documentation_translation_message
from .signal_gettext import read_gettext_messages


def inventory_documentation_manifest(
    extracted: Path,
    pages: list[str],
    repository: Path,
    docs_root: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    catalogue_messages: Mapping[tuple[str, str], Mapping[str, bool]],
    catalogue_obsolete: Mapping[tuple[str, str], set[str]],
    catalogue_translations: Mapping[tuple[str, str], Mapping[str, tuple[str, ...]]],
    spelling_values: dict[str, dict[str, str]] | None,
    echo_cache: DocumentationEchoDictionaries,
    platform_identity_terms: frozenset[str],
    source_echo_samples: list[dict[str, object]],
    invariant_echo_samples: list[dict[str, object]],
    near_echo_samples: list[dict[str, object]],
) -> None:
    """Inventory documentation manifest."""
    from dev.docs.i18n import SOURCE_MANIFEST_NAME, SOURCE_MANIFEST_SCHEMA_VERSION, TARGET_LANGUAGES

    manifest_payload = json.loads((extracted / SOURCE_MANIFEST_NAME).read_text(encoding=UTF_8))
    if manifest_payload.get("schema_version") != SOURCE_MANIFEST_SCHEMA_VERSION or not isinstance(
        manifest_payload.get("sources"), dict
    ):
        raise ValueError("unsupported or malformed docs source manifest")
    source_digests = manifest_payload["sources"]
    expected_pages = set(pages)
    manifest_pages = set(source_digests)
    counts["docs_orphan_source_templates"] = len(manifest_pages - expected_pages)
    for page in pages:
        inventory_documentation_page(
            page,
            extracted,
            source_digests,
            TARGET_LANGUAGES,
            repository,
            docs_root,
            counts,
            findings,
            catalogue_messages,
            catalogue_obsolete,
            catalogue_translations,
            spelling_values,
            echo_cache,
            platform_identity_terms,
            source_echo_samples,
            invariant_echo_samples,
            near_echo_samples,
        )


def inventory_documentation_page(
    page: str,
    extracted: Path,
    source_digests: Mapping[str, object],
    target_languages: tuple[str, ...],
    repository: Path,
    docs_root: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    catalogue_messages: Mapping[tuple[str, str], Mapping[str, bool]],
    catalogue_obsolete: Mapping[tuple[str, str], set[str]],
    catalogue_translations: Mapping[tuple[str, str], Mapping[str, tuple[str, ...]]],
    spelling_values: dict[str, dict[str, str]] | None,
    echo_cache: DocumentationEchoDictionaries,
    platform_identity_terms: frozenset[str],
    source_echo_samples: list[dict[str, object]],
    invariant_echo_samples: list[dict[str, object]],
    near_echo_samples: list[dict[str, object]],
) -> None:
    """Inventory documentation page."""
    catalogue = Path(page).with_suffix(".po").as_posix()
    pot = extracted / Path(page).with_suffix(".pot")
    expected_digest = sha256_file(docs_root / page)
    source_current = source_digests.get(page) == expected_digest
    source_messages = read_gettext_messages(pot)
    if not source_current or source_messages is None:
        counts["docs_source_drift_pages"] += 1
        findings.append(
            {
                "classification": "blocking",
                "kind": (
                    "docs_source_template_stale" if source_messages is not None else "docs_source_template_missing"
                ),
                "domain": "docs",
                "path": f"docs/{page}",
                "next_action": "run python -m dev.docs.i18n, then translate the catalogue delta",
            }
        )
        return
    source_ids = set(source_messages)
    counts["docs_source_messages"] += len(source_ids)
    if spelling_values is not None:
        for identity, source_text in source_messages.items():
            spelling_values.setdefault("en", {})[f"parallel:docs/{page}:{identity}"] = source_text
    page_drifted = False
    for locale in target_languages:
        if inventory_documentation_locale(
            locale,
            page,
            catalogue,
            source_ids,
            source_messages,
            repository,
            counts,
            findings,
            catalogue_messages,
            catalogue_obsolete,
            catalogue_translations,
            echo_cache,
            platform_identity_terms,
            source_echo_samples,
            invariant_echo_samples,
            near_echo_samples,
        ):
            page_drifted = True
    counts["docs_source_drift_pages"] += int(page_drifted)


def inventory_documentation_locale(
    locale: str,
    page: str,
    catalogue: str,
    source_ids: set[str],
    source_messages: dict[str, str],
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    catalogue_messages: Mapping[tuple[str, str], Mapping[str, bool]],
    catalogue_obsolete: Mapping[tuple[str, str], set[str]],
    catalogue_translations: Mapping[tuple[str, str], Mapping[str, tuple[str, ...]]],
    echo_cache: DocumentationEchoDictionaries,
    platform_identity_terms: frozenset[str],
    source_echo_samples: list[dict[str, object]],
    invariant_echo_samples: list[dict[str, object]],
    near_echo_samples: list[dict[str, object]],
) -> bool:
    """Inventory documentation locale."""
    page_drifted = False
    translated_messages = {
        identity: values
        for (candidate, identity), localized in catalogue_translations.items()
        if candidate == catalogue and (values := localized.get(locale)) is not None
    }
    for identity, translations in sorted(translated_messages.items()):
        inventory_documentation_translation_message(
            identity,
            translations,
            source_messages,
            locale,
            catalogue,
            repository,
            counts,
            findings,
            echo_cache,
            platform_identity_terms,
            source_echo_samples,
            invariant_echo_samples,
            near_echo_samples,
        )
    catalogue_ids = {
        message_id
        for (candidate, message_id), states in catalogue_messages.items()
        if candidate == catalogue and locale in states
    }
    obsolete_ids = catalogue_obsolete.get((locale, catalogue), set())
    catalogue_ids.update(obsolete_ids)
    missing = source_ids - catalogue_ids
    stale = catalogue_ids - source_ids
    counts["docs_source_messages_missing"] += len(missing)
    counts["docs_catalogue_messages_stale"] += len(stale)
    counts[f"docs_catalogue_messages_stale_{locale}"] += len(stale)
    if missing or stale:
        page_drifted = True
        findings.append(
            {
                "classification": "blocking",
                "kind": "docs_source_catalogue_drift",
                "domain": "docs",
                "path": f"docs/{page}",
                "locale": locale,
                "source_messages_missing": len(missing),
                "catalogue_messages_stale": len(stale),
                "missing_message_ids": sorted(missing),
                "stale_message_ids": sorted(stale),
                "catalogue_messages_obsolete": len(obsolete_ids),
                "obsolete_message_ids": sorted(obsolete_ids),
                "next_action": "run python -m dev.docs.i18n, then translate the catalogue delta",
            }
        )
    return page_drifted
