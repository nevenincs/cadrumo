"""Structural lifecycle gate for every generated-output settings directory.

Every ``_dir`` / ``_path`` / ``_root`` Path-typed :class:`~core.config.Settings`
field must map to exactly one declared growth-lifecycle class:

- ``ROTATION`` - a size-capped rotating handler bounds the file(s).
- ``TTL`` - entries expire after a time-to-live window.
- ``RETENTION`` - a prune/eviction removes entries past an age or count bound.
- ``UNBOUNDED_BY_DESIGN`` - durable state / evidence / filing artefacts (and
  bounded single-file caches) deliberately retained, with a stated reason.
- ``EXEMPT_INPUT`` - not an app-generated output: read-only bundled inputs,
  an operator-supplied credential path, or the storage-root container itself.

The gate fails when a field is unclassified, double-classified, or - for a
non-exempt output directory - defaults outside the state-root derivation
without being an opt-in (``None``-default) override, so a new dir field with a
``PROJECT_ROOT``-anchored default or no declared lifecycle can no longer land
silently.
"""

from __future__ import annotations

from pathlib import Path
from types import UnionType
from typing import Union, get_args, get_origin

import pytest

from ..config import _STATE_ROOT_DERIVED_DIRS, Settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PATH_FIELD_SUFFIXES = ("_dir", "_path", "_root")

# Logs rotate via a size-capped RotatingFileHandler.
_ROTATION = frozenset({"cadrumo_log_dir"})

# Time-to-live expiry of cached entries.
_TTL = frozenset({"cadrumo_status_cache_dir"})

# An age/count prune or eviction bounds the store.
_RETENTION = frozenset(
    {
        "cadrumo_llm_cache_dir",
        "cadrumo_llm_usage_dir",
        "cadrumo_llm_run_telemetry_dir",
        "cadrumo_runs_dir",
        "cadrumo_registry_disk_cache_dir",  # fingerprint-count eviction
        "cadrumo_wallet_diagnostic_dump_dir",
    }
)

# Durable state / evidence / filing artefacts retained by design, plus bounded
# single-file caches. Each is deliberately not pruned:
#   - token/secret/blob/audit: the encrypted-store substrate; audit and
#     evidence must not be silently pruned (secure-storage governs them).
#   - submissions/drafts/justificantes/filing-history/workflow-runs/inbox(+pdf):
#     filing-grade artefacts retained for audit and re-derivation.
#   - financial txs/invoices/attachments: durable financial catalogues.
#   - storage backups: operator-managed DB backups.
#   - registry parity store: registry parity-tape audit artefacts.
#   - usage-ratios.json: a single operator-config FILE (one entry per category).
#   - corpus-text cache: a single content-fingerprinted cache FILE, bounded by
#     the finite bundled-corpus source set; stale keys are inert (they embed
#     source size+mtime).
_UNBOUNDED_BY_DESIGN = frozenset(
    {
        "cadrumo_token_dir",
        "cadrumo_secret_store_dir",
        "cadrumo_blob_store_dir",
        "cadrumo_audit_dir",
        "cadrumo_storage_backup_dir",
        "cadrumo_submissions_dir",
        "cadrumo_drafts_dir",
        "cadrumo_justificantes_dir",
        "cadrumo_filing_history_dir",
        "cadrumo_workflow_runs_dir",
        "cadrumo_inbox_dir",
        "cadrumo_inbox_pdf_dir",
        "cadrumo_financial_txs_dir",
        "cadrumo_invoices_dir",
        "cadrumo_attachments_dir",
        "cadrumo_usage_ratios_path",
        "cadrumo_registry_parity_store_dir",
        "cadrumo_corpus_text_cache_dir",
    }
)

# Not app-generated output: bundled read-only inputs, an operator credential
# path, and the storage-root container itself (its categorised children carry
# the lifecycles above).
_EXEMPT_INPUT = frozenset(
    {
        "aeat_manuals_root",
        "aeat_normatives_root",
        "cadrumo_iva_catalogue_root",
        "cadrumo_certificate_path",
        "cadrumo_local_storage_root",
    }
)

_ALL_CLASSES = (_ROTATION, _TTL, _RETENTION, _UNBOUNDED_BY_DESIGN, _EXEMPT_INPUT)


def _path_typed_fields() -> set[str]:
    """Enumerate every ``_dir``/``_path``/``_root`` Path-typed Settings field."""
    fields: set[str] = set()
    for name, field_info in Settings.model_fields.items():
        if not name.endswith(_PATH_FIELD_SUFFIXES):
            continue
        annotation = field_info.annotation
        origin = get_origin(annotation)
        members: tuple[object, ...] = get_args(annotation) if origin in (Union, UnionType) else (annotation,)
        if any(member is Path for member in members):
            fields.add(name)
    return fields


def test_every_path_field_maps_to_exactly_one_lifecycle_class() -> None:
    path_fields = _path_typed_fields()
    classified = set().union(*_ALL_CLASSES)

    unclassified = sorted(path_fields - classified)
    assert not unclassified, (
        "Path-typed Settings fields with no declared lifecycle class: "
        f"{unclassified}. Add each to exactly one class in "
        "test_settings_lifecycle_gate.py (rotation / TTL / retention / "
        "unbounded-by-design with a stated reason) or EXEMPT_INPUT."
    )
    stale = sorted(classified - path_fields)
    assert not stale, f"Lifecycle classes name fields that no longer exist: {stale}"


def test_lifecycle_classes_are_pairwise_disjoint() -> None:
    for i, left in enumerate(_ALL_CLASSES):
        for right in _ALL_CLASSES[i + 1 :]:
            overlap = sorted(left & right)
            assert not overlap, f"fields classified in two lifecycle classes at once: {overlap}"


def test_non_exempt_output_dirs_derive_from_the_state_root() -> None:
    """A non-exempt output directory must derive from ``cadrumo_local_storage_root``
    or be an opt-in (``None``-default) override -- never a ``PROJECT_ROOT``-anchored
    effective default that resolves inside site-packages on an installed run."""
    for name in sorted(_path_typed_fields() - _EXEMPT_INPUT):
        field_info = Settings.model_fields[name]
        derived = name in _STATE_ROOT_DERIVED_DIRS
        opt_in_override = field_info.default is None
        assert derived or opt_in_override, (
            f"{name}: a non-exempt output directory must either derive from the "
            "state root (be listed in _STATE_ROOT_DERIVED_DIRS) or be an opt-in "
            "override with a None default; a concrete PROJECT_ROOT-anchored "
            "default is the eliminated defect."
        )


def test_usage_ratios_path_is_classified_as_a_file_output() -> None:
    """``cadrumo_usage_ratios_path`` is a single JSON FILE (not a directory); it is
    classified unbounded-by-design and still derives its location from the root."""
    assert "cadrumo_usage_ratios_path" in _UNBOUNDED_BY_DESIGN
    assert "cadrumo_usage_ratios_path" in _STATE_ROOT_DERIVED_DIRS
