"""The typed authority for every application-chosen on-disk location.

Where a byte lands used to be decided by four mutually unaware authorities: an
untyped ``dict[str, str]`` in the settings module, bare string constants in the
persistence namespace registry, module-local constants in application and
entrypoint modules, and unpinned inline copies of the registry's own names. A
name declared in the adapter layer could not be imported by ``core`` without
inverting the hexagonal direction, so the duplicates were unfixable where they
sat. This module is the single declaration all of them collapse onto: every
application-chosen name lives here, in ``core``, and the adapter layer consumes
it downward.

Six axes ride on each member because a bare name cannot carry them:

- the literal POSIX relative subpath, verbatim as it exists on disk;
- :class:`StorageNodeKind`, so file-versus-directory is a type-level fact rather
  than a guess made from a field-name suffix -- a guess cannot reach the
  per-bucket file names no suffix convention governs, and would put a directory
  exactly where a document must be written;
- :class:`StorageScope`, because ``blobs`` and ``audit`` each legitimately name
  both a top-level category and a per-bucket subdirectory at a different depth,
  so members are identified by scope and name together;
- :class:`StorageOverridePolicy`, so the guarantee that an operator cannot
  relocate a keystore out from under the bucket it unlocks is declared data
  rather than an accident of which module a constant sat in;
- :class:`StorageLifecycle` and :class:`StorageGrouping`, the conceptual
  classifications that answer what may be reclaimed and what belongs together;
- :class:`FingerprintParticipation`, an independent third axis that no union of
  the other two reproduces, governing what the drift fingerprint covers.

The conceptual grouping has no effect on the resolved path. ``cache/`` is the
sole on-disk category prefix and remains so: the encrypted-state substrate, the
diagnostic logs, and the durable outputs keep bare, self-describing leaf names.

See Also:
    :class:`~core.config.Settings`
        Central settings aggregate whose path fields these members name.
    :func:`storage_path`
        Resolver for a root-scoped member.
    :func:`bucket_scoped_storage_path`
        Resolver for a bucket- or keystore-scoped member.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ._models import STRICT_FROZEN_CONFIG
from .errors import CoreValidationError

if TYPE_CHECKING:
    from .config import Settings


class StorageNodeKind(StrEnum):
    """Whether a member names a directory or a single file.

    Declared rather than inferred. A name-suffix heuristic cannot reach the
    per-bucket file names -- ``manifest.toml``, ``.lock``, the keystore
    sidecars -- that follow no suffix convention, and inferring wrongly creates
    a directory where a document belongs, which fails much later at the write.
    """

    DIRECTORY = "directory"
    FILE = "file"


class StorageScope(StrEnum):
    """The anchor a member's subpath is relative to.

    Scope is a required part of a member's identity, not a decoration: the
    top-level ``blobs`` and ``audit`` categories share their names with
    per-bucket subdirectories at a different depth, and both are correct.
    Keying on name alone would conflate them.
    """

    ROOT = "root"
    BUCKET_RELATIVE = "bucket_relative"
    KEYSTORE_RELATIVE = "keystore_relative"


class StorageOverridePolicy(StrEnum):
    """Whether an operator may relocate a member.

    The bucket and keystore layout is deliberately fixed. An operator must not
    be able to move a keystore out from under the bucket it unlocks, and that
    guarantee is expressed here as data so it can be read and enforced, rather
    than resting on which module a constant happened to sit in.
    """

    OPERATOR_OVERRIDABLE = "operator_overridable"
    FIXED = "fixed"


class StorageLifecycle(StrEnum):
    """How a member's contents are bounded over time.

    Governs what a reclaim operation may delete. ``UNBOUNDED_BY_DESIGN`` covers
    the substrate a filing is defended with: growth is the point, and pruning it
    would destroy evidence.
    """

    UNBOUNDED_BY_DESIGN = "unbounded_by_design"
    RETENTION = "retention"
    ROTATION = "rotation"
    TTL = "ttl"


class StorageGrouping(StrEnum):
    """The conceptual family a member belongs to.

    Purely a classification for operator-facing presentation and reclaim
    grouping. It has no effect on the resolved path, so a member grouped as a
    cache need not sit under the ``cache/`` prefix and several do not.
    """

    STATE = "state"
    LOGS = "logs"
    CACHE = "cache"
    EXPORTS = "exports"


class FingerprintParticipation(StrEnum):
    """Whether writes beneath a member move the data-root drift digest.

    An independent axis, never derived. Measured against every candidate, no
    expression over lifecycle or grouping reproduces the shipped set, and three
    candidates differ in both directions at once -- omitting members that are
    excluded while adding members that are not. Getting it wrong is invisible
    in both directions: excluding too much walks the digest toward the
    empty-tree constant that once defeated drift detection outright, and
    excluding too little churns it on every cache write until an operator
    learns to distrust the refusal.
    """

    PARTICIPATING = "participating"
    EXCLUDED = "excluded"


class ExternalPathRole(StrEnum):
    """Why a path-valued setting is legitimately outside the taxonomy.

    A location enrolls when the application both chooses it and writes data
    there. Failing either question is an escape -- but an escape is a positive
    declaration carrying its reason, never mere absence from a frozenset, so a
    setting cannot fall outside the taxonomy by being overlooked.
    """

    BUNDLED_RESOURCE = "bundled_resource"
    OPERATOR_INPUT = "operator_input"
    THIRD_PARTY_CACHE = "third_party_cache"
    EXTERNAL_EXECUTABLE = "external_executable"
    OPERATOR_DIRECTED_OUTPUT = "operator_directed_output"


class StorageCategory(StrEnum):
    """Every application-chosen on-disk location, identified by scope and name.

    Root-scoped members carry their bare category name. Bucket- and
    keystore-scoped members carry a scope-qualifying prefix, which is what keeps
    the top-level ``blobs``/``audit`` categories distinct from the per-bucket
    subdirectories that share their on-disk names.
    """

    # ── State substrate and identity ────────────────────────────────────────
    TOKENS = "tokens"
    SECRETS = "secrets"
    BLOBS = "blobs"
    AUDIT = "audit"
    REGISTRY_PARITY_STORE = "registry-parity-store"

    # ── Diagnostic and append-only telemetry logs ───────────────────────────
    LOGS = "logs"
    LLM_USAGE = "llm-usage"
    LLM_RUN_TELEMETRY = "llm-run-telemetry"
    RUNS = "runs"

    # ── Regenerable, evictable caches ───────────────────────────────────────
    LLM_CACHE = "llm-cache"
    STATUS_CACHE = "status-cache"
    CORPUS_TEXT_CACHE = "corpus-text-cache"
    VALIDATION_VERDICT_CACHE = "validation-verdict-cache"
    REGISTRY_DISK_CACHE = "registry-disk-cache"

    # ── Durable generated outputs ───────────────────────────────────────────
    STORAGE_BACKUP = "storage-backup"
    SUBMISSIONS = "submissions"
    INBOX = "inbox"
    INBOX_PDF = "inbox-pdf"
    WORKFLOW_RUNS = "workflow-runs"
    DRAFTS = "drafts"
    JUSTIFICANTES = "justificantes"
    FILING_HISTORY = "filing-history"
    FILED_DECLARATIONS = "filed-declarations"
    IVA_COMPENSATION_HISTORY = "iva-compensation-history"
    IVA_READ_EVIDENCE = "iva-read-evidence"
    FINANCIAL_TRANSACTIONS = "financial-transactions"
    INVOICES = "invoices"
    ATTACHMENTS = "attachments"
    USAGE_RATIOS = "usage-ratios"

    # ── Fixed layout: the bucket container and the active-profile pointer ───
    BUCKETS = "buckets"
    ACTIVE_PROFILE_POINTER = "active-profile-pointer"

    # ── Fixed layout: per-bucket ────────────────────────────────────────────
    BUCKET_DATABASE = "bucket.db"
    BUCKET_BLOBS = "bucket.blobs"
    BUCKET_AUDIT = "bucket.audit"
    BUCKET_MANIFEST = "bucket.manifest"
    BUCKET_LOCK = "bucket.lock"
    BUCKET_OUTPUT_LANGUAGE_HINT = "bucket.output-language-hint"
    BUCKET_KEYSTORE = "bucket.keystore"

    # ── Fixed layout: per-keystore ──────────────────────────────────────────
    KEYSTORE_BUCKET_DEK = "keystore.bucket-dek"
    KEYSTORE_PROFILE_SESSION = "keystore.profile-session"
    KEYSTORE_LOGIN_THROTTLE = "keystore.login-throttle"


class StorageLocation(BaseModel):
    """One declared location and every axis a bare name cannot carry.

    Frozen and strict: the taxonomy is a declaration, and a mutable one would
    let a consumer rewrite the authority it is reading.
    """

    model_config = STRICT_FROZEN_CONFIG

    category: StorageCategory
    subpath: str = Field(min_length=1)
    """POSIX-style path relative to this member's scope anchor, verbatim."""

    node_kind: StorageNodeKind
    scope: StorageScope
    override_policy: StorageOverridePolicy
    lifecycle: StorageLifecycle
    grouping: StorageGrouping
    fingerprint_participation: FingerprintParticipation

    settings_field: str | None = None
    """Flat :class:`~core.config.Settings` attribute holding the resolved path.

    Members name their settings field rather than absorbing it. Path fields stay
    flat, introspectable attributes on the settings model because the structural
    gates discover their subject by walking ``Settings.model_fields``; a model
    that hid them behind a nested object or a property would leave those gates
    discovering nothing, which passes silently and covers nothing.
    """

    derives_settings_default: bool = False
    """Whether settings validation computes this field's default from the root.

    False for a member whose field is a deliberate opt-in override. The registry
    disk cache is the worked case: its name is governed here, but its field must
    stay absent by default because its resolver selects a shared temporary
    location under pytest precisely by observing that the field is unset.
    Governing the name and deriving the field are separate decisions.
    """

    def relative_path(self) -> Path:
        """Return :attr:`subpath` as a path relative to this member's anchor."""
        return Path(*self.subpath.split("/"))


def _location(
    category: StorageCategory,
    subpath: str,
    *,
    lifecycle: StorageLifecycle,
    grouping: StorageGrouping,
    settings_field: str | None = None,
    node_kind: StorageNodeKind = StorageNodeKind.DIRECTORY,
    scope: StorageScope = StorageScope.ROOT,
    override_policy: StorageOverridePolicy = StorageOverridePolicy.OPERATOR_OVERRIDABLE,
    fingerprint_participation: FingerprintParticipation = FingerprintParticipation.PARTICIPATING,
    derives_settings_default: bool = True,
) -> StorageLocation:
    """Build one declaration, defaulting the axes most members share."""
    return StorageLocation(
        category=category,
        subpath=subpath,
        node_kind=node_kind,
        scope=scope,
        override_policy=override_policy,
        lifecycle=lifecycle,
        grouping=grouping,
        fingerprint_participation=fingerprint_participation,
        settings_field=settings_field,
        derives_settings_default=derives_settings_default and settings_field is not None,
    )


_ROOT_LOCATIONS: Final[tuple[StorageLocation, ...]] = (
    # ── State substrate and identity ────────────────────────────────────────
    _location(
        StorageCategory.TOKENS,
        "tokens",
        settings_field="cadrumo_token_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
    ),
    _location(
        StorageCategory.SECRETS,
        "secrets",
        settings_field="cadrumo_secret_store_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
    ),
    _location(
        StorageCategory.BLOBS,
        "blobs",
        settings_field="cadrumo_blob_store_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
    ),
    _location(
        StorageCategory.AUDIT,
        "audit",
        settings_field="cadrumo_audit_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
    ),
    _location(
        StorageCategory.REGISTRY_PARITY_STORE,
        "audit/registry/parity",
        settings_field="cadrumo_registry_parity_store_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
    ),
    # ── Diagnostic and append-only telemetry logs ───────────────────────────
    _location(
        StorageCategory.LOGS,
        "logs",
        settings_field="cadrumo_log_dir",
        lifecycle=StorageLifecycle.ROTATION,
        grouping=StorageGrouping.LOGS,
    ),
    _location(
        StorageCategory.LLM_USAGE,
        "llm-usage",
        settings_field="cadrumo_llm_usage_dir",
        lifecycle=StorageLifecycle.RETENTION,
        grouping=StorageGrouping.LOGS,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        StorageCategory.LLM_RUN_TELEMETRY,
        "llm-run-telemetry",
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
        settings_field="cadrumo_runs_dir",
        lifecycle=StorageLifecycle.RETENTION,
        grouping=StorageGrouping.LOGS,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    # ── Regenerable, evictable caches ───────────────────────────────────────
    _location(
        StorageCategory.LLM_CACHE,
        "cache/llm-cache",
        settings_field="cadrumo_llm_cache_dir",
        lifecycle=StorageLifecycle.RETENTION,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        StorageCategory.STATUS_CACHE,
        "cache/status-cache",
        settings_field="cadrumo_status_cache_dir",
        lifecycle=StorageLifecycle.TTL,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        StorageCategory.CORPUS_TEXT_CACHE,
        "cache/corpus-text",
        settings_field="cadrumo_corpus_text_cache_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        StorageCategory.VALIDATION_VERDICT_CACHE,
        "cache/registry-verdict",
        settings_field="cadrumo_validation_verdict_cache_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        # The name is governed here; the field is deliberately NOT derived, so
        # the resolver's pytest branch can keep selecting on its absence.
        StorageCategory.REGISTRY_DISK_CACHE,
        "cache/registry",
        settings_field="cadrumo_registry_disk_cache_dir",
        lifecycle=StorageLifecycle.RETENTION,
        grouping=StorageGrouping.CACHE,
        derives_settings_default=False,
    ),
    # ── Durable generated outputs ───────────────────────────────────────────
    _location(
        StorageCategory.STORAGE_BACKUP,
        "backups",
        settings_field="cadrumo_storage_backup_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        StorageCategory.SUBMISSIONS,
        "submissions",
        settings_field="cadrumo_submissions_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.INBOX,
        "inbox",
        settings_field="cadrumo_inbox_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.INBOX_PDF,
        "inbox/pdfs",
        settings_field="cadrumo_inbox_pdf_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.WORKFLOW_RUNS,
        "workflow-runs",
        settings_field="cadrumo_workflow_runs_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.DRAFTS,
        "drafts",
        settings_field="cadrumo_drafts_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.JUSTIFICANTES,
        "justificantes",
        settings_field="cadrumo_justificantes_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.FILING_HISTORY,
        "filing-history",
        settings_field="cadrumo_filing_history_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.FILED_DECLARATIONS,
        "filed-declarations",
        settings_field="cadrumo_filed_declarations_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.IVA_COMPENSATION_HISTORY,
        "live/iva-compensation-history",
        settings_field="cadrumo_iva_compensation_history_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.IVA_READ_EVIDENCE,
        "live/iva-read-evidence",
        settings_field="cadrumo_iva_read_evidence_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.FINANCIAL_TRANSACTIONS,
        "financial/transactions",
        settings_field="cadrumo_financial_txs_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.INVOICES,
        "financial/invoices",
        settings_field="cadrumo_invoices_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.ATTACHMENTS,
        "financial/attachments",
        settings_field="cadrumo_attachments_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.USAGE_RATIOS,
        "financial/usage-ratios.json",
        settings_field="cadrumo_usage_ratios_path",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    # ── Fixed layout: the bucket container and the active-profile pointer ───
    _location(
        StorageCategory.BUCKETS,
        "buckets",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.ACTIVE_PROFILE_POINTER,
        "active-profile",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
)


_BUCKET_LOCATIONS: Final[tuple[StorageLocation, ...]] = (
    _location(
        StorageCategory.BUCKET_DATABASE,
        "db",
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.BUCKET_BLOBS,
        "blobs",
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.BUCKET_AUDIT,
        "audit",
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.BUCKET_MANIFEST,
        "manifest.toml",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.BUCKET_LOCK,
        ".lock",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.BUCKET_OUTPUT_LANGUAGE_HINT,
        "output-language.hint",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.BUCKET_KEYSTORE,
        "keystore",
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.KEYSTORE_BUCKET_DEK,
        "bucket.dek.json",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.KEYSTORE_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.KEYSTORE_PROFILE_SESSION,
        "session.v1.json",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.KEYSTORE_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.KEYSTORE_LOGIN_THROTTLE,
        "login-throttle.json",
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


ROOT_DERIVED_STORAGE_FIELDS: Final[tuple[str, ...]] = tuple(
    location.settings_field
    for location in _ROOT_LOCATIONS
    if location.derives_settings_default and location.settings_field is not None
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
    bucket_root = (
        Path(resolved.cadrumo_local_storage_root) / storage_location(StorageCategory.BUCKETS).relative_path() / trimmed
    )
    if location.scope is StorageScope.KEYSTORE_RELATIVE:
        bucket_root = bucket_root / storage_location(StorageCategory.BUCKET_KEYSTORE).relative_path()
    return bucket_root / location.relative_path()


def storage_tree_targets(settings: Settings) -> tuple[Path, ...]:
    """Return every directory :func:`~core.config.ensure_storage_tree` creates.

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


__all__ = [
    "FINGERPRINT_EXCLUDED_STORAGE_FIELDS",
    "ROOT_DERIVED_STORAGE_FIELDS",
    "STORAGE_FIELD_CATEGORIES",
    "STORAGE_TAXONOMY",
    "ExternalPathRole",
    "FingerprintParticipation",
    "StorageCategory",
    "StorageGrouping",
    "StorageLifecycle",
    "StorageLocation",
    "StorageNodeKind",
    "StorageOverridePolicy",
    "StorageScope",
    "bucket_scoped_storage_path",
    "storage_location",
    "storage_path",
    "storage_tree_targets",
]
