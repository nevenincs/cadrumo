"""Compiled storage-taxonomy data and its resolution accessors.

Split out of ``_storage_taxonomy.py`` along the seam that module now names in
its own docstring: the axis enums, :class:`StorageLocation`, and the
``_location()`` factory are the TYPE layer -- stable, small, imported
everywhere. ``_ROOT_LOCATIONS`` / ``_BUCKET_LOCATIONS`` are the DATA -- one
entry per application-chosen location, and the fastest-growing part of the
taxonomy by construction, since every new governed path adds a member here.
Keeping them together pushed the combined module past its reviewed size
band; this module is the other half, consumed only through
``_storage_taxonomy``'s re-export (see its own ``__all__``), never imported
directly by anything outside ``core``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from .errors.hierarchy import CoreValidationError
from .product_identity import PRODUCT_IDENTITY
from .storage_taxonomy import (
    FingerprintParticipation,
    StorageCategory,
    StorageGrouping,
    StorageLifecycle,
    StorageLocation,
    StorageNodeKind,
    StorageOverridePolicy,
    StorageScope,
    _location,
)

if TYPE_CHECKING:
    from .config import Settings


_PRODUCT_DATABASE_FILENAME: Final[str] = f"{PRODUCT_IDENTITY.python_package}.db"
"""SQLite filename shared by the root-fallback and per-bucket database members.

Computed from the one product-identity authority rather than hardcoded a
second time, so :data:`~core.config_state_root.PRODUCT_DATABASE_FILENAME` --
which reads
this value back off the taxonomy -- can never drift from what these two
members actually resolve.
"""

_BUCKET_DATABASE_DIRNAME: Final[str] = "db"
"""Directory name shared by ``BUCKET_DATABASE`` and ``BUCKET_DATABASE_FILE``.

Named once rather than hand-typed a second time as the ``BUCKET_DATABASE_FILE``
member's own subpath prefix, so a rename of the directory cannot silently
orphan the file member nested inside it.
"""


_ROOT_LOCATIONS: Final[tuple[StorageLocation, ...]] = (
    # ── State substrate and identity ────────────────────────────────────────
    _location(
        StorageCategory.TOKENS,
        "tokens",
        consumer_module="application/auth/acquisition_lock.py",
        settings_field="cadrumo_token_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
    ),
    _location(
        StorageCategory.SECRETS,
        "secrets",
        consumer_module="adapters/persistence/storage/blob_store/_materialisation.py",
        settings_field="cadrumo_secret_store_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
    ),
    _location(
        StorageCategory.BLOBS,
        "blobs",
        consumer_module="adapters/persistence/storage/blob_store/_materialisation.py",
        settings_field="cadrumo_blob_store_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
    ),
    _location(
        StorageCategory.LIVE_STATE,
        "live-state",
        consumer_module="application/live/iva_remote_state.py",
        settings_field="cadrumo_live_state_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
    ),
    # ── Fixed layout: live IVA remote-state capture ─────────────────────────
    # These descendants are joined onto the operator-overridable live-state
    # root, so they carry no settings field and are not resolved independently.
    _location(
        StorageCategory.LIVE_STATE_IVA_WALLET,
        "live-state/iva-wallet",
        consumer_module="application/live/iva_remote_state.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.LIVE_STATE_IVA_REMOTE_STATE,
        "live-state/iva-remote-state",
        consumer_module="application/live/iva_remote_state.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.LIVE_STATE_IVA_REMOTE_STATE_FILED_HISTORY,
        "live-state/iva-remote-state/filed-history",
        consumer_module="application/live/iva_remote_state.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.LIVE_STATE_IVA_REMOTE_STATE_WALLET,
        "live-state/iva-remote-state/wallet",
        consumer_module="application/live/iva_remote_state.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    # ── Diagnostic and append-only telemetry logs ───────────────────────────
    _location(
        StorageCategory.LOGS,
        "logs",
        consumer_module="core/logging.py",
        settings_field="cadrumo_log_dir",
        lifecycle=StorageLifecycle.ROTATION,
        grouping=StorageGrouping.LOGS,
    ),
    _location(
        # Was the bare literal ``_DEFAULT_LOG_FILE_NAME = "cadrumo.log"`` in
        # ``core/logging.py``, joined onto ``storage_path(StorageCategory.LOGS)``
        # -- that join already honours the ``LOGS`` override correctly, so only
        # the filename itself needed a declared home.
        StorageCategory.LOG_FILE,
        "logs/cadrumo.log",
        consumer_module="core/logging.py",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.ROTATION,
        grouping=StorageGrouping.LOGS,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.LLM_USAGE,
        "llm-usage",
        consumer_module="adapters/outbound/llm/_usage.py",
        settings_field="cadrumo_llm_usage_dir",
        lifecycle=StorageLifecycle.RETENTION,
        grouping=StorageGrouping.LOGS,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        StorageCategory.LLM_RUN_TELEMETRY,
        "llm-run-telemetry",
        consumer_module="adapters/outbound/llm/_run_telemetry.py",
        settings_field="cadrumo_llm_run_telemetry_dir",
        lifecycle=StorageLifecycle.RETENTION,
        grouping=StorageGrouping.LOGS,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        # Observability's own output. Fingerprinting it would make every run's
        # digest depend on the traces the immediately preceding run left, so a
        # hermetic replay would refuse on essentially every attempt.
        StorageCategory.RUNS,
        "runs",
        consumer_module="core/observability/_store.py",
        settings_field="cadrumo_runs_dir",
        lifecycle=StorageLifecycle.RETENTION,
        grouping=StorageGrouping.LOGS,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    # ── Regenerable, evictable caches ───────────────────────────────────────
    _location(
        StorageCategory.LLM_CACHE,
        "cache/llm-cache",
        consumer_module="adapters/outbound/llm/_cache.py",
        settings_field="cadrumo_llm_cache_dir",
        lifecycle=StorageLifecycle.RETENTION,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        StorageCategory.CORPUS_TEXT_CACHE,
        "cache/corpus-text",
        consumer_module="domain/calculations/registry/_validate_evidence.py",
        settings_field="cadrumo_corpus_text_cache_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        # Was the bare literal ``_CORPUS_TEXT_CACHE_FILENAME`` in
        # ``_validate_evidence.py``. Same override caveat as the secret-store
        # leaves: ``CORPUS_TEXT_CACHE`` is operator-overridable, so this member
        # carries no ``settings_field`` -- the consumer keeps resolving through
        # ``cadrumo_corpus_text_cache_dir`` and cross-references only the bare
        # filename.
        StorageCategory.CORPUS_TEXT_CACHE_FILE,
        "cache/corpus-text/cadrumo_corpus_text_cache.json",
        consumer_module="domain/calculations/registry/_validate_evidence.py",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.CORPUS_SEARCH_CACHE,
        "cache/corpus-search",
        consumer_module="application/corpus_search/_runtime.py",
        settings_field="cadrumo_corpus_search_cache_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        # Was the bare literal ``_INDEX_FILENAME = "corpus.sqlite"`` in
        # ``corpus_search/_runtime.py``. Same override caveat as above.
        StorageCategory.CORPUS_SEARCH_INDEX,
        "cache/corpus-search/corpus.sqlite",
        consumer_module="application/corpus_search/_runtime.py",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.VALIDATION_VERDICT_CACHE,
        "cache/registry-verdict",
        consumer_module="domain/calculations/registry/_verdict_cache.py",
        settings_field="cadrumo_validation_verdict_cache_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        # The name is governed here; the field is deliberately NOT derived, so
        # the resolver's pytest branch can keep selecting on its absence.
        #
        # Excluded from the digest, and this is a correction rather than a
        # restatement. The compiled registry pickle lands here and is rewritten
        # on every recompile, so it churned the digest and produced spurious
        # replay refusals -- measured, with a positive control: a write into an
        # excluded directory left the digest unchanged while a write here moved
        # it. It was fingerprinted only because the old hardcoded exclusion list
        # could not resolve a field defaulting to None. Digests will differ from
        # their pre-correction value on any machine holding a compiled cache;
        # that is the correction landing, and it must not be "fixed" by
        # restoring parity with the old set.
        StorageCategory.REGISTRY_DISK_CACHE,
        "cache/registry",
        consumer_module="domain/calculations/registry/loader_cache.py",
        settings_field="cadrumo_registry_disk_cache_dir",
        lifecycle=StorageLifecycle.RETENTION,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
        derives_settings_default=False,
        test_pinned_exception=(
            "Under pytest, with no explicit override, the resolver selects the "
            "host-shared OS temp directory instead of this member's declared "
            "subpath, so every xdist worker and subprocess-spawning test shares "
            "one compiled pickle for the immutable bundled registry tree rather "
            "than each deriving a private, per-worker cache from a per-pid "
            "storage root. See loader_cache.registry_disk_cache_dir."
        ),
    ),
    _location(
        # Fingerprint-keyed flat-map cache of one shared locale catalogue
        # (source YAML -> flattened dict), mirroring
        # domain/calculations/registry/_verdict_cache.py's shape: JSON, a
        # source-digest key embedded in the payload, delete-not-migrate on any
        # mismatch. FIXED (no dedicated settings field) because the shared
        # storage-root override already gives tests private isolation, the
        # same override policy CORPUS_SEARCH_INDEX uses.
        StorageCategory.LOCALE_CATALOGUE_CACHE,
        "cache/locale-catalogue",
        consumer_module="core/i18n/_catalogue_cache.py",
        node_kind=StorageNodeKind.DIRECTORY,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    # ── Durable generated outputs ───────────────────────────────────────────
    _location(
        StorageCategory.SUBMISSIONS,
        "submissions",
        dormant_reason=(
            "the master-key rotation sweep was this location's only consumer, and it was "
            "deleted with the shared-master model it belonged to. Nothing wrote plaintext "
            "here even then -- the sweep only walked the directory looking for legacy "
            "envelope files -- so the durable records live in the encrypted secure-object "
            "store and this path is a logical marker nothing now reads or writes"
        ),
        settings_field="cadrumo_submissions_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        # Was the bare literal ``"amendment-results"`` in the since-deleted master-key rotation sweep,
        # joined onto ``cadrumo_submissions_dir``. Same override caveat as the
        # secret-store leaves above.
        StorageCategory.SUBMISSIONS_AMENDMENT_RESULTS,
        "submissions/amendment-results",
        dormant_reason=(
            "the master-key rotation sweep was this location's only consumer, and it was "
            "deleted with the shared-master model it belonged to. Nothing wrote plaintext "
            "here even then -- the sweep only walked the directory looking for legacy "
            "envelope files -- so the durable records live in the encrypted secure-object "
            "store and this path is a logical marker nothing now reads or writes"
        ),
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        # Was the bare literal ``"amendments"`` in the since-deleted master-key rotation sweep, joined
        # onto ``cadrumo_submissions_dir``. Same override caveat.
        StorageCategory.SUBMISSIONS_AMENDMENTS,
        "submissions/amendments",
        dormant_reason=(
            "the master-key rotation sweep was this location's only consumer, and it was "
            "deleted with the shared-master model it belonged to. Nothing wrote plaintext "
            "here even then -- the sweep only walked the directory looking for legacy "
            "envelope files -- so the durable records live in the encrypted secure-object "
            "store and this path is a logical marker nothing now reads or writes"
        ),
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.WORKFLOW_RUNS,
        "workflow-runs",
        consumer_module="application/workflow/persistence.py",
        settings_field="cadrumo_workflow_runs_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.DRAFTS,
        "drafts",
        dormant_reason=(
            "the master-key rotation sweep was this location's only consumer, and it was "
            "deleted with the shared-master model it belonged to. Nothing wrote plaintext "
            "here even then -- the sweep only walked the directory looking for legacy "
            "envelope files -- so the durable records live in the encrypted secure-object "
            "store and this path is a logical marker nothing now reads or writes"
        ),
        settings_field="cadrumo_drafts_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.JUSTIFICANTES,
        "justificantes",
        dormant_reason=(
            "the master-key rotation sweep was this location's only consumer, and it was "
            "deleted with the shared-master model it belonged to. Nothing wrote plaintext "
            "here even then -- the sweep only walked the directory looking for legacy "
            "envelope files -- so the durable records live in the encrypted secure-object "
            "store and this path is a logical marker nothing now reads or writes"
        ),
        settings_field="cadrumo_justificantes_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.FILING_HISTORY,
        "filing-history",
        dormant_reason=(
            "the master-key rotation sweep was this location's only consumer, and it was "
            "deleted with the shared-master model it belonged to. Nothing wrote plaintext "
            "here even then -- the sweep only walked the directory looking for legacy "
            "envelope files -- so the durable records live in the encrypted secure-object "
            "store and this path is a logical marker nothing now reads or writes"
        ),
        settings_field="cadrumo_filing_history_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.FILED_DECLARATIONS,
        "filed-declarations",
        consumer_module="entrypoints/cli/_overview_evidence.py",
        settings_field="cadrumo_filed_declarations_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.IVA_COMPENSATION_HISTORY,
        "live/iva-compensation-history",
        consumer_module="entrypoints/cli/_app_live.py",
        settings_field="cadrumo_iva_compensation_history_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.IVA_READ_EVIDENCE,
        "live/iva-read-evidence",
        consumer_module="entrypoints/cli/_app_live.py",
        settings_field="cadrumo_iva_read_evidence_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.FINANCIAL_TRANSACTIONS,
        "financial/transactions",
        dormant_reason=(
            "the master-key rotation sweep was this location's only consumer, and it was "
            "deleted with the shared-master model it belonged to. Nothing wrote plaintext "
            "here even then -- the sweep only walked the directory looking for legacy "
            "envelope files -- so the durable records live in the encrypted secure-object "
            "store and this path is a logical marker nothing now reads or writes"
        ),
        settings_field="cadrumo_financial_txs_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.INVOICES,
        "financial/invoices",
        dormant_reason=(
            "the master-key rotation sweep was this location's only consumer, and it was "
            "deleted with the shared-master model it belonged to. Nothing wrote plaintext "
            "here even then -- the sweep only walked the directory looking for legacy "
            "envelope files -- so the durable records live in the encrypted secure-object "
            "store and this path is a logical marker nothing now reads or writes"
        ),
        settings_field="cadrumo_invoices_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.ATTACHMENTS,
        "financial/attachments",
        dormant_reason=(
            "the master-key rotation sweep was this location's only consumer, and it was "
            "deleted with the shared-master model it belonged to. Nothing wrote plaintext "
            "here even then -- the sweep only walked the directory looking for legacy "
            "envelope files -- so the durable records live in the encrypted secure-object "
            "store and this path is a logical marker nothing now reads or writes"
        ),
        settings_field="cadrumo_attachments_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        # Was the bare literal ``"manifests"`` in the since-deleted master-key rotation sweep, joined onto
        # ``cadrumo_attachments_dir``. Same override caveat as the secret-store
        # leaves above.
        StorageCategory.ATTACHMENTS_MANIFESTS,
        "financial/attachments/manifests",
        dormant_reason=(
            "the master-key rotation sweep was this location's only consumer, and it was "
            "deleted with the shared-master model it belonged to. Nothing wrote plaintext "
            "here even then -- the sweep only walked the directory looking for legacy "
            "envelope files -- so the durable records live in the encrypted secure-object "
            "store and this path is a logical marker nothing now reads or writes"
        ),
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.USAGE_RATIOS,
        "financial/usage-ratios.json",
        dormant_reason=(
            "the master-key rotation sweep was this location's only consumer, and it was "
            "deleted with the shared-master model it belonged to. Nothing wrote plaintext "
            "here even then -- the sweep only walked the directory looking for legacy "
            "envelope files -- so the durable records live in the encrypted secure-object "
            "store and this path is a logical marker nothing now reads or writes"
        ),
        settings_field="cadrumo_usage_ratios_path",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    # ── Fixed layout: the bucket container and the active-profile pointer ───
    _location(
        StorageCategory.BUCKETS,
        "buckets",
        consumer_module="core/_config_state_root.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.ACTIVE_PROFILE_POINTER,
        "active-profile",
        # `core/bucket_pointer.py` is what resolves this location: its
        # `pointer_path()` reads `StorageCategory.ACTIVE_PROFILE_POINTER`.
        # `core/config.py` references the category nowhere, so the claim named a
        # module that does not back it.
        consumer_module="core/bucket_pointer.py",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        # The cold-start database used only before any profile bucket exists.
        # Not reclaimable and not operator-relocatable, exactly like the
        # per-bucket database file below -- a database is not a cache that grew
        # too large, and a database path does not move independently of the
        # storage root.
        StorageCategory.ROOT_FALLBACK_DATABASE,
        _PRODUCT_DATABASE_FILENAME,
        consumer_module="core/config.py",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        # Application-owned journal directory for in-flight and completed
        # config-reset operations, sibling to buckets/ under the storage root.
        # No dedicated settings field exists to relocate it independently of
        # the storage root -- the same shape as BUCKETS and
        # ACTIVE_PROFILE_POINTER above, so it is FIXED for the same reason:
        # nothing here permits an operator-facing override to point it
        # anywhere else.
        StorageCategory.CONFIG_RESET_JOURNAL,
        "reset-operations",
        consumer_module="application/_config_reset_repository.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.OPERATION_JOURNAL,
        "operation-journals",
        consumer_module="adapters/persistence/operations/journal.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.PROFILE_CUSTODY_TRANSACTION_JOURNAL,
        "profile-custody-transactions",
        consumer_module="application/user_profile/custody_repository.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.PROFILE_CUSTODY_RECEIPT,
        "profile-custody-receipts",
        consumer_module="application/user_profile/custody_repository.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.PROFILE_CUSTODY_HOLD_EVIDENCE,
        "profile-custody-holds",
        consumer_module="application/user_profile/custody_hold.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.PROFILE_CUSTODY_HOLD_LEGAL_OWNER,
        "profile-custody-holds/legal-case-owner",
        consumer_module="application/evidence/_profile_legal_hold.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.PROFILE_CUSTODY_HOLD_FILING_OWNER,
        "profile-custody-holds/filing-retention-owner",
        consumer_module="application/filing/_profile_filing_retention.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.PROFILE_CUSTODY_HOLD_DERIVED_EVIDENCE,
        "profile-custody-holds/derived-evidence",
        consumer_module="application/user_profile/custody_hold.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.PROFILE_CUSTODY_LABEL_HEAD,
        "profile-custody-label-heads",
        consumer_module="adapters/persistence/storage/custody/label_head_repository.py",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
)


_BUCKET_LOCATIONS: Final[tuple[StorageLocation, ...]] = (
    _location(
        StorageCategory.BUCKET_DATABASE,
        _BUCKET_DATABASE_DIRNAME,
        consumer_module="adapters/persistence/storage/_storage_path_definitions.py",
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        # The database file beneath the BUCKET_DATABASE directory above. That
        # member governs the directory only; before this member existed, the
        # file inside it was an ungoverned leaf no producer resolved through
        # the taxonomy -- exactly the nested-path gap the taxonomy exists to
        # close.
        StorageCategory.BUCKET_DATABASE_FILE,
        f"{_BUCKET_DATABASE_DIRNAME}/{_PRODUCT_DATABASE_FILENAME}",
        consumer_module="core/config.py",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.BUCKET_BLOBS,
        "blobs",
        consumer_module="adapters/persistence/storage/_storage_path_definitions.py",
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    # This member names a RETIRED artefact, kept because the name is still
    # needed to RECOGNISE it on a pre-cutover store; nothing writes one and no
    # path definition declares it.  Its consumer is therefore the refusal
    # detector, the one reader that must have the name, and not a layout
    # module.  Naming a retired member is not declaring a current format --
    # do not infer from this declaration that a current bucket has one.
    _location(
        StorageCategory.BUCKET_MANIFEST,
        "manifest.toml",
        consumer_module="adapters/persistence/storage/custody/capsule_discovery.py",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.BUCKET_LOCK,
        ".lock",
        consumer_module="adapters/persistence/storage/_storage_path_definitions.py",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.BUCKET_OUTPUT_LANGUAGE_HINT,
        "output-language.hint",
        consumer_module="adapters/persistence/storage/_storage_path_definitions.py",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        # Sibling to buckets/ under the storage root, never nested inside the
        # bucket directory it unlocks -- production states and enforces this
        # separation (adapters.persistence.storage.bucket._keystore_paths,
        # validate_keystore_separation), so this member's scope is its own
        # bucket-id-parameterized root, not BUCKET_RELATIVE.
        StorageCategory.BUCKET_KEYSTORE,
        "keystore",
        consumer_module="adapters/persistence/storage/_storage_path_definitions.py",
        scope=StorageScope.KEYSTORE_ROOT,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.PROFILE_CAPSULE_CUSTODY,
        "custody",
        consumer_module="adapters/persistence/storage/custody/paths.py",
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.PROFILE_CAPSULE_PASSWORD_ENVELOPE,
        "custody/envelope.v1.json",
        consumer_module="adapters/persistence/storage/custody/paths.py",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.PROFILE_CAPSULE_RECOVERY_ENVELOPE,
        "custody/recovery.v1.json",
        consumer_module="adapters/persistence/storage/custody/paths.py",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.PROFILE_CAPSULE_DATA,
        "data",
        consumer_module="adapters/persistence/storage/custody/paths.py",
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.PROFILE_CAPSULE_COMMIT,
        "profile.commit.v1.json",
        consumer_module="adapters/persistence/storage/custody/paths.py",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.KEYSTORE_PROFILE_SESSION,
        "session.v2.json",
        consumer_module="adapters/persistence/storage/_storage_path_definitions.py",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.KEYSTORE_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.KEYSTORE_PROFILE_SESSION_RETIREMENT,
        "session.v2.retirement.json",
        consumer_module="adapters/persistence/storage/_storage_path_definitions.py",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.KEYSTORE_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.KEYSTORE_LOGIN_THROTTLE,
        "login-throttle.json",
        consumer_module="adapters/persistence/storage/_storage_path_definitions.py",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.KEYSTORE_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
)


STORAGE_TAXONOMY: Final[dict[StorageCategory, StorageLocation]] = {
    location.category: location for location in (*_ROOT_LOCATIONS, *_BUCKET_LOCATIONS)
}
"""The single declaration of every application-chosen on-disk location.

Total over :class:`StorageCategory`: a member without a declaration would be a
name the application can pass around but never resolve.
"""


STORAGE_FIELD_CATEGORIES: Final[dict[str, StorageCategory]] = {
    location.settings_field: location.category
    for location in STORAGE_TAXONOMY.values()
    if location.settings_field is not None
}
"""Reverse index from a flat settings field name to the member that governs it."""


ROOT_DERIVED_STORAGE_LOCATIONS: Final[tuple[StorageLocation, ...]] = tuple(
    location for location in _ROOT_LOCATIONS if location.derives_settings_default
)
"""Members whose settings default is computed from the storage root, in declaration order.

Settings validation and the override-rebuild loop iterate this rather than a
parallel table, so a member cannot be declared here and silently left underived.
"""


ROOT_DERIVED_STORAGE_FIELDS: Final[tuple[str, ...]] = tuple(
    location.settings_field for location in ROOT_DERIVED_STORAGE_LOCATIONS if location.settings_field is not None
)
"""Settings fields whose default is computed from the storage root, in declaration order."""


FINGERPRINT_EXCLUDED_STORAGE_FIELDS: Final[frozenset[str]] = frozenset(
    location.settings_field
    for location in STORAGE_TAXONOMY.values()
    if location.settings_field is not None and location.fingerprint_participation is FingerprintParticipation.EXCLUDED
)
"""Settings fields whose contents are kept out of the data-root drift digest.

Compared by field NAME wherever it is checked, never by resolved-path
cardinality: two fields may legitimately be overridden onto one directory,
which shrinks a resolved-path set while exactly the same fields are consulted.
"""


def storage_location(category: StorageCategory) -> StorageLocation:
    """Return the declaration for ``category``."""
    return STORAGE_TAXONOMY[category]


def storage_path(category: StorageCategory, *, settings: Settings | None = None) -> Path:
    """Return the resolved absolute path of a root-scoped member.

    The member's settings field is the authority when it declares one and holds
    a value, so an explicit per-field operator override wins here exactly as it
    does everywhere else, and the isolation fixtures that place a category
    outside the root keep resolving to where they put it. A member with no field
    -- the fixed bucket container, the active-profile pointer -- resolves as the
    root joined with its declared subpath.

    Args:
        category: The member to resolve. Must be root-scoped.
        settings: Settings to resolve against. Defaults to the effective
            settings for the calling context.

    Returns:
        The absolute path this member occupies.

    Raises:
        CoreValidationError: When ``category`` is bucket- or keystore-scoped and
            therefore needs a bucket identifier to resolve.
    """
    location = storage_location(category)
    if location.scope is not StorageScope.ROOT:
        raise CoreValidationError(
            f"storage category {category.value!r} is {location.scope.value} and needs a bucket "
            "identifier; resolve it with bucket_scoped_storage_path instead.",
        )
    resolved = _effective_settings(settings)
    if location.settings_field is not None:
        value = getattr(resolved, location.settings_field, None)
        if value is not None:
            return Path(value)
    return Path(resolved.cadrumo_local_storage_root) / location.relative_path()


def bucket_scoped_storage_path(
    category: StorageCategory,
    bucket_id: str,
    *,
    settings: Settings | None = None,
) -> Path:
    """Return the resolved absolute path of a bucket- or keystore-scoped member.

    Bucket layout is fixed by policy, so this resolves through the declared
    subpaths rather than through any operator-facing setting: a keystore cannot
    be relocated out from under the bucket it unlocks.

    Args:
        category: The member to resolve. Must not be root-scoped.
        bucket_id: The bucket whose tree the member sits in.
        settings: Settings to resolve the bucket container against. Defaults to
            the effective settings for the calling context.

    Returns:
        The absolute path this member occupies within ``bucket_id``'s tree.

    Raises:
        CoreValidationError: When ``category`` is root-scoped, or ``bucket_id``
            is blank.
    """
    location = storage_location(category)
    if location.scope is StorageScope.ROOT:
        raise CoreValidationError(
            f"storage category {category.value!r} is root-scoped and takes no bucket "
            "identifier; resolve it with storage_path instead.",
        )
    trimmed = bucket_id.strip()
    if not trimmed:
        raise CoreValidationError("bucket_id must not be blank")
    resolved = _effective_settings(settings)
    root = Path(resolved.cadrumo_local_storage_root)

    if location.scope is StorageScope.KEYSTORE_ROOT:
        # The bucket-id-parameterized keystore root itself: <root>/keystore/<id>.
        return root / location.relative_path() / trimmed
    if location.scope is StorageScope.KEYSTORE_RELATIVE:
        # Sibling to buckets/, never nested beneath it -- the same separation
        # KEYSTORE_ROOT anchors, with this member's own subpath appended.
        keystore_root = root / storage_location(StorageCategory.BUCKET_KEYSTORE).relative_path() / trimmed
        return keystore_root / location.relative_path()

    bucket_root = root / storage_location(StorageCategory.BUCKETS).relative_path() / trimmed
    return bucket_root / location.relative_path()


def storage_tree_targets(settings: Settings) -> tuple[Path, ...]:
    """Return every directory :func:`~core.storage_materialization.ensure_storage_tree` creates.

    Derived from the declaration and from nothing else, so the materialiser
    cannot drift from the taxonomy by carrying a second list. A file-valued
    member contributes its parent and explicitly not its leaf -- creating the
    leaf would put a directory exactly where a document must be written, and the
    failure would surface much later, at the write.

    Members with no settings field are fixed layout the bucket lifecycle
    provisions per bucket, and members whose field is absent are opt-in
    locations the operator has not asked for; neither is materialised here.
    """
    targets: list[Path] = []
    for location in _ROOT_LOCATIONS:
        if location.settings_field is None:
            continue
        value = getattr(settings, location.settings_field, None)
        if value is None:
            continue
        candidate = Path(value)
        targets.append(candidate.parent if location.node_kind is StorageNodeKind.FILE else candidate)
    return tuple(targets)


def _effective_settings(settings: Settings | None) -> Settings:
    """Return ``settings`` or the effective settings for the calling context.

    Imported through the owning submodule inside the call, never at module
    scope: the settings module reaches this one during its own construction, so
    a module-scope import in this direction closes an import cycle.
    """
    if settings is not None:
        return settings
    from .config import load_settings

    return load_settings()
