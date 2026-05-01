"""Core cross-cutting package surface.

Promoted symbols from ``locks``, ``classification``, ``redaction``, and
``corpus_manifest`` are exposed lazily to avoid import-time cycles through
logging configuration.
"""

from __future__ import annotations

from importlib import import_module
from typing import Final

_LAZY_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "DEFAULT_LOCK_TIMEOUT": ("aeat.core.locks", "DEFAULT_LOCK_TIMEOUT"),
    "exclusive_file_lock": ("aeat.core.locks", "exclusive_file_lock"),
    "fsync_parent_dir": ("aeat.core.locks", "fsync_parent_dir"),
    "AtRestTreatment": ("aeat.core.classification", "AtRestTreatment"),
    "ClassificationPolicy": ("aeat.core.classification", "ClassificationPolicy"),
    "RedactionRule": ("aeat.core.classification", "RedactionRule"),
    "RedactionStrategy": ("aeat.core.classification", "RedactionStrategy"),
    "RetentionPolicy": ("aeat.core.classification", "RetentionPolicy"),
    "SensitivityClass": ("aeat.core.classification", "SensitivityClass"),
    "default_policy_for": ("aeat.core.classification", "default_policy_for"),
    "default_policy_table": ("aeat.core.classification", "default_policy_table"),
    "default_rules": ("aeat.core.redaction", "default_rules"),
    "default_rules_for": ("aeat.core.redaction", "default_rules_for"),
    "default_rules_for_class": ("aeat.core.redaction", "default_rules_for_class"),
    "redact": ("aeat.core.redaction", "redact"),
    "redact_for_log": ("aeat.core.redaction", "redact_for_log"),
    "redact_structured": ("aeat.core.redaction", "redact_structured"),
    "CorpusEntry": ("aeat.core.corpus_manifest", "CorpusEntry"),
    "CorpusManifest": ("aeat.core.corpus_manifest", "CorpusManifest"),
    "CorpusManifestDiff": ("aeat.core.corpus_manifest", "CorpusManifestDiff"),
    "assert_corpus_clean": ("aeat.core.corpus_manifest", "assert_corpus_clean"),
    "build_corpus_manifest": ("aeat.core.corpus_manifest", "build_corpus_manifest"),
    "load_corpus_manifest": ("aeat.core.corpus_manifest", "load_corpus_manifest"),
    "manifest_path_for": ("aeat.core.corpus_manifest", "manifest_path_for"),
    "save_corpus_manifest": ("aeat.core.corpus_manifest", "save_corpus_manifest"),
    "verify_corpus_manifest": ("aeat.core.corpus_manifest", "verify_corpus_manifest"),
}


def __getattr__(name: str) -> object:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    return getattr(import_module(module_name), attr_name)


__all__ = sorted(_LAZY_EXPORTS)
