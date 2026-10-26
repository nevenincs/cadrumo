"""Documentation counts for the authoritative locale audit."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from .signal_policy import INVARIANT_ECHO_REASONS


def ratio(value: int, total: int) -> float:
    """Return a stable zero-safe ratio for an inventory counter."""
    return round(value / total, 6) if total else 0.0


def documentation_counts(
    counts: Counter[str],
    *,
    source_echo_samples: Sequence[Mapping[str, object]] | None = None,
    invariant_echo_samples: Sequence[Mapping[str, object]] | None = None,
    near_echo_samples: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Return the stable user-document inventory schema, including zeroes."""
    if source_echo_samples is None:
        source_echo_samples = list[Mapping[str, object]]()
    if invariant_echo_samples is None:
        invariant_echo_samples = list[Mapping[str, object]]()
    if near_echo_samples is None:
        near_echo_samples = list[Mapping[str, object]]()
    return {
        "docs_source_pages": counts["docs_source_pages"],
        "docs_source_messages": counts["docs_source_messages"],
        "docs_catalogue_files_expected": counts["docs_catalogue_files_expected"],
        "docs_catalogue_files_read": counts["docs_catalogue_files_read"],
        "docs_source_drift_pages": counts["docs_source_drift_pages"],
        "docs_source_messages_missing": counts["docs_source_messages_missing"],
        "docs_catalogue_messages_stale": counts["docs_catalogue_messages_stale"],
        "docs_catalogue_messages_obsolete": counts["docs_catalogue_messages_obsolete"],
        "docs_translation_comparisons": counts["docs_translation_comparisons"],
        "docs_translation_source_echo": counts["docs_translation_source_echo"],
        "docs_translation_source_echo_ratio": ratio(
            counts["docs_translation_source_echo"], counts["docs_translation_comparisons"]
        ),
        "docs_translation_source_echo_samples": source_echo_samples,
        "docs_translation_invariant_echo": counts["docs_translation_invariant_echo"],
        "docs_translation_invariant_echo_ratio": ratio(
            counts["docs_translation_invariant_echo"], counts["docs_translation_comparisons"]
        ),
        "docs_translation_invariant_echo_samples": invariant_echo_samples,
        "docs_translation_near_echo": counts["docs_translation_near_echo"],
        "docs_translation_near_echo_ratio": ratio(
            counts["docs_translation_near_echo"], counts["docs_translation_comparisons"]
        ),
        "docs_translation_near_echo_samples": near_echo_samples,
        "docs_extraction_failures": counts["docs_extraction_failures"],
        "docs_orphan_catalogue_files": counts["docs_orphan_catalogue_files"],
        "docs_missing_catalogue_files": counts["docs_missing_catalogue_files"],
        "docs_orphan_source_templates": counts["docs_orphan_source_templates"],
        "docs_generated_english_only_pages": counts["docs_generated_english_only_pages"],
        "docs_generated_spellchecked_pages": counts["docs_generated_spellchecked_pages"],
        "docs_generated_prose_cells": counts["docs_generated_prose_cells"],
        "docs_generated_source_failures": counts["docs_generated_source_failures"],
        **documentation_locale_counts(counts, "docs_catalogue_files_expected"),
        **documentation_locale_counts(counts, "docs_catalogue_files_read"),
        **documentation_locale_counts(counts, "docs_catalogue_messages_stale"),
        **documentation_locale_counts(counts, "docs_catalogue_messages_obsolete"),
        **documentation_locale_counts(counts, "docs_translation_comparisons"),
        **documentation_locale_counts(counts, "docs_translation_source_echo"),
        **documentation_locale_counts(counts, "docs_translation_invariant_echo"),
        **{
            f"docs_translation_invariant_echo_reason_{reason}": counts[
                f"docs_translation_invariant_echo_reason_{reason}"
            ]
            for reason in INVARIANT_ECHO_REASONS
        },
        **{
            f"docs_translation_invariant_echo_{locale}_{reason}": counts[
                f"docs_translation_invariant_echo_{locale}_{reason}"
            ]
            for locale in ("ca", "es", "hu")
            for reason in INVARIANT_ECHO_REASONS
        },
        **documentation_locale_counts(counts, "docs_translation_near_echo"),
    }


def docs_extraction_finding(path: Path, exc: BaseException) -> dict[str, object]:
    """Normalize a user-document discovery/extraction tool failure."""
    return {
        "classification": "blocking",
        "kind": "docs_source_extraction_failure",
        "domain": "docs",
        "path": path.as_posix(),
        "error_type": type(exc).__name__,
        "detail": str(exc),
        "next_action": "restore the user-doc gettext extraction path, then rerun check-locales",
    }


def documentation_locale_counts(counts: Counter[str], stem: str) -> dict[str, int]:
    """Expand one documentation counter into its target-locale inventory."""
    return {f"{stem}_{locale}": counts[f"{stem}_{locale}"] for locale in ("ca", "es", "hu")}
