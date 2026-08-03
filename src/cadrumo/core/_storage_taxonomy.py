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

from pydantic import BaseModel, Field, model_validator

from ._models import STRICT_FROZEN_CONFIG
from .errors import CoreValidationError
from .product_identity import PRODUCT_IDENTITY

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

    The keystore anchor is a second, independent bucket-id-parameterized root,
    not a nested subdirectory of the bucket it unlocks. Production states this
    as the load-bearing invariant it is
    (:func:`~adapters.persistence.storage.bucket.validate_keystore_separation`):
    the keystore lives at ``<root>/keystore/<bucket-id>/``, sibling to
    ``buckets/``, and a configuration that resolves it under ``buckets/`` is
    refused so a later unlock cannot silently violate the separation.
    ``KEYSTORE_ROOT`` names that per-bucket keystore directory itself --
    parameterized by a bucket id like ``BUCKET_RELATIVE``, but anchored at
    ``<root>/keystore/`` rather than ``<root>/buckets/`` -- and
    ``KEYSTORE_RELATIVE`` names what nests beneath it.
    """

    ROOT = "root"
    BUCKET_RELATIVE = "bucket_relative"
    KEYSTORE_ROOT = "keystore_root"
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
    MAINTAINER_TOOLING_OUTPUT = "maintainer_tooling_output"


class ExternalPathDeclaration(BaseModel):
    """One path-valued setting that legitimately sits outside the taxonomy.

    Frozen and strict for the same reason the location declarations are: an
    escape is an authority about where data does *not* land, and a mutable one
    would let a consumer widen it.
    """

    model_config = STRICT_FROZEN_CONFIG

    settings_field: str = Field(min_length=1)
    role: ExternalPathRole
    reason: str = Field(min_length=1)
    """Why this field fails the choose test, the write test, or both.

    Required and non-empty: the whole point of declaring an escape rather than
    omitting a field is that the reason is written down where the next reader
    finds it.
    """


STORAGE_ROOT_SETTINGS_FIELD: Final[str] = "cadrumo_local_storage_root"
"""The settings field naming the anchor every root-scoped member resolves against.

Neither a member nor an escape, and given its own name so it cannot be mistaken
for either. It is not a member because the taxonomy declares locations
*relative to* it -- a member for the root would be a member whose subpath is
itself. It is not an escape because the application both chooses it and writes
beneath it, so it passes both of :class:`ExternalPathRole`'s questions; calling
it external would be false. Every field is therefore exactly one of three
things, and the binding gate asserts the three are total and disjoint rather
than letting the anchor fall through an unnamed gap.
"""


EXTERNAL_PATH_SETTINGS_FIELDS: Final[dict[str, ExternalPathDeclaration]] = {
    declaration.settings_field: declaration
    for declaration in (
        ExternalPathDeclaration(
            settings_field="aeat_manuals_root",
            role=ExternalPathRole.MAINTAINER_TOOLING_OUTPUT,
            reason=(
                "The bundled AEAT Manual practico corpus ships inside the package and the "
                "*running application* never writes there -- it fails the write test from the "
                "operator's chair. But domain.manuals._fetch demonstrably does write there: it "
                "streams a manual part's PDF plus a manifest to disk under this root. That "
                "module has no entrypoints/ surface (grep confirms only a test references it), "
                "so it reads as maintainer tooling that refreshes the bundled corpus before a "
                "release, the same shape as the locales CLI writing into the package's own "
                "source tree -- but nothing enforces that boundary at the call graph, so the "
                "prior BUNDLED_RESOURCE declaration's 'never writes there' was false the moment "
                "this fetcher existed. This role says what is actually true: tooling-written, "
                "not application-written."
            ),
        ),
        ExternalPathDeclaration(
            settings_field="aeat_normatives_root",
            role=ExternalPathRole.BUNDLED_RESOURCE,
            reason=(
                "The bundled legal normatives corpus ships inside the package and is read only. "
                "Legal grounding reads it; nothing writes it."
            ),
        ),
        ExternalPathDeclaration(
            settings_field="cadrumo_iva_catalogue_root",
            role=ExternalPathRole.BUNDLED_RESOURCE,
            reason=(
                "The hand-reviewed IVA taxonomy catalogue ships inside the package and is read "
                "only; it is revised in source, never at runtime."
            ),
        ),
        ExternalPathDeclaration(
            settings_field="cadrumo_certificate_path",
            role=ExternalPathRole.OPERATOR_INPUT,
            reason=(
                "The operator's own PKCS#12 bundle, which they place wherever they keep their "
                "credentials. The application reads it to authenticate and must never write to "
                "it, so it fails both the choose test and the write test."
            ),
        ),
        ExternalPathDeclaration(
            settings_field="cadrumo_libreoffice_executable",
            role=ExternalPathRole.EXTERNAL_EXECUTABLE,
            reason=(
                "A third-party binary installed by the platform or the operator. The application "
                "executes it and does not choose where it lives. Classified nowhere before the "
                "taxonomy existed, and invisible to a name-suffix selector because it ends in "
                "none of _dir, _path, or _root -- which is why the binding gate selects by "
                "annotation."
            ),
        ),
        ExternalPathDeclaration(
            settings_field="cadrumo_wallet_diagnostic_dump_dir",
            role=ExternalPathRole.OPERATOR_DIRECTED_OUTPUT,
            reason=(
                "Unset, the diagnostic capture is off and there is no application-chosen "
                "location at all; set, the operator names the destination and the application "
                "writes there on request. Neither state is the application choosing a location, "
                "so it escapes -- and it fits none of the four original roles, which is the "
                "correction re-applying the escape test to a real field surfaced."
            ),
        ),
    )
}
"""Path-valued settings that are legitimately outside the taxonomy, with reasons.

A location enrolls when the application both chooses it and writes data there.
Failing either question puts a field here -- as a positive declaration carrying
its role and its reason, never as mere absence from a frozenset, so no field
can fall outside the taxonomy by being overlooked.
"""


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

    # ── Fixed layout: within the secret store ────────────────────────────────
    SECRETS_MASTER_KEY = "secrets.master-key"
    SECRETS_MASTER_KDF = "secrets.master-kdf"
    SECRETS_MASTER_LOCK = "secrets.master-lock"
    SECRETS_KEYRING_LOCK = "secrets.keyring-lock"
    SECRETS_MASTER_RECOVERY_KEY = "secrets.master-recovery-key"

    # ── Diagnostic and append-only telemetry logs ───────────────────────────
    LOGS = "logs"
    LLM_USAGE = "llm-usage"
    LLM_RUN_TELEMETRY = "llm-run-telemetry"
    MCP_TELEMETRY = "mcp-telemetry"
    RUNS = "runs"

    # ── Regenerable, evictable caches ───────────────────────────────────────
    LLM_CACHE = "llm-cache"
    CORPUS_TEXT_CACHE = "corpus-text-cache"
    CORPUS_SEARCH_CACHE = "corpus-search-cache"
    VALIDATION_VERDICT_CACHE = "validation-verdict-cache"
    REGISTRY_DISK_CACHE = "registry-disk-cache"

    # ── Durable generated outputs ───────────────────────────────────────────
    SUBMISSIONS = "submissions"
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
    ROOT_FALLBACK_DATABASE = "root-fallback-database"

    # ── Fixed layout: per-bucket ────────────────────────────────────────────
    BUCKET_DATABASE = "bucket.db"
    BUCKET_DATABASE_FILE = "bucket.db-file"
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

    consumer_module: str | None = None
    """Production module that consumes this location, relative to ``src/cadrumo``.

    Names the module, and a structural gate verifies the claim: that module must
    contain a real reference to this member -- an attribute load of the bound
    settings field, an attribute load of the category member, or the field name
    as a non-docstring string constant, which is how the live-evidence roots are
    reached. A name appearing in prose satisfies nothing.

    The claim is deliberately consumption rather than write-reachability.
    Tracing statically from an attribute to a filesystem write produces a false
    negative on every indirection, and a gate that blocks legitimate changes is
    a gate somebody switches off. Consumption is weaker in theory and far
    stronger in practice, because a location no module touches cannot be written
    to -- which is the condition worth catching.

    Exactly one of this and :attr:`dormant_reason` is set.
    """

    dormant_reason: str | None = None
    """Why this member has no consuming module, when it has none.

    A declared location nothing reads or writes is a decision waiting to be
    taken -- wire it or delete it -- and the point of requiring the reason is
    that the decision becomes visible in the declaration instead of waiting to
    be rediscovered by an audit. Exactly one of this and
    :attr:`consumer_module` is set.
    """

    @model_validator(mode="after")
    def _require_exactly_one_liveness_claim(self) -> StorageLocation:
        """Refuse a member that claims both a consumer and dormancy, or neither."""
        claims = (self.consumer_module, self.dormant_reason)
        if sum(claim is not None for claim in claims) != 1:
            raise ValueError(
                f"storage category {self.category.value!r} must declare exactly one of "
                "consumer_module (the production module that consumes this location) or "
                "dormant_reason (why nothing does)",
            )
        for label, value in (("consumer_module", self.consumer_module), ("dormant_reason", self.dormant_reason)):
            if value is not None and not value.strip():
                raise ValueError(f"storage category {self.category.value!r} declares an empty {label}")
        return self

    def relative_path(self) -> Path:
        """Return :attr:`subpath` as a path relative to this member's anchor."""
        return Path(*self.subpath.split("/"))


def _location(
    category: StorageCategory,
    subpath: str,
    *,
    lifecycle: StorageLifecycle,
    grouping: StorageGrouping,
    consumer_module: str | None = None,
    dormant_reason: str | None = None,
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
        consumer_module=consumer_module,
        dormant_reason=dormant_reason,
        settings_field=settings_field,
        derives_settings_default=derives_settings_default and settings_field is not None,
    )


_PRODUCT_DATABASE_FILENAME: Final[str] = f"{PRODUCT_IDENTITY.python_package}.db"
"""SQLite filename shared by the root-fallback and per-bucket database members.

Computed from the one product-identity authority rather than hardcoded a
second time, so :data:`~core.config.PRODUCT_DATABASE_FILENAME` -- which reads
this value back off the taxonomy -- can never drift from what these two
members actually resolve.
"""


_ROOT_LOCATIONS: Final[tuple[StorageLocation, ...]] = (
    # ── State substrate and identity ────────────────────────────────────────
    _location(
        StorageCategory.TOKENS,
        "tokens",
        consumer_module="application/auth/_acquisition_lock.py",
        settings_field="cadrumo_token_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
    ),
    _location(
        StorageCategory.SECRETS,
        "secrets",
        consumer_module="adapters/persistence/storage/master_key/_master_key.py",
        settings_field="cadrumo_secret_store_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
    ),
    # ── Fixed layout: within the secret store ────────────────────────────────
    # The most security-load-bearing filenames in the product -- the wrapped
    # master key, its KDF sidecar, and the locks guarding first-time
    # provisioning -- were ungoverned literal joins onto ``cadrumo_secret_store_dir``
    # / ``self._store_dir`` before these members existed, exactly the nested-path
    # gap the taxonomy exists to close (see ``BUCKET_MANIFEST`` / ``BUCKET_LOCK``,
    # the same class already closed for the bucket layout).
    #
    # ``subpath`` is written root-relative (``secrets/...``) for documentation,
    # but these five members deliberately carry no ``settings_field`` and are
    # NOT safe to resolve via :func:`storage_path`: unlike the bucket layout,
    # ``SECRETS`` above is itself :attr:`StorageOverridePolicy.OPERATOR_OVERRIDABLE`,
    # so ``storage_path(SECRETS_MASTER_KEY)`` (root + this literal subpath) would
    # silently disagree with the real location whenever an operator overrides
    # ``cadrumo_secret_store_dir`` away from its default. The consumer keeps
    # resolving through the settings field / ``self._store_dir`` it already reads
    # (which honours that override correctly) and cross-references only the bare
    # filename off these members -- see ``_master_key.py`` and ``_custody.py``.
    _location(
        StorageCategory.SECRETS_MASTER_KEY,
        "secrets/master.key",
        consumer_module="adapters/persistence/storage/master_key/_master_key.py",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.SECRETS_MASTER_KDF,
        "secrets/master.kdf",
        consumer_module="adapters/persistence/storage/master_key/_master_key.py",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.SECRETS_MASTER_LOCK,
        "secrets/master.lock",
        consumer_module="adapters/persistence/storage/master_key/_master_key.py",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.SECRETS_KEYRING_LOCK,
        "secrets/keyring.lock",
        consumer_module="adapters/persistence/storage/master_key/_master_key.py",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.SECRETS_MASTER_RECOVERY_KEY,
        "secrets/master.recovery.key",
        consumer_module="application/user_profile/_custody.py",
        node_kind=StorageNodeKind.FILE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
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
        StorageCategory.AUDIT,
        "audit",
        consumer_module="adapters/persistence/storage/_namespace_registry.py",
        settings_field="cadrumo_audit_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
    ),
    _location(
        StorageCategory.REGISTRY_PARITY_STORE,
        "audit/registry/parity",
        consumer_module="entrypoints/cli/registry.py",
        settings_field="cadrumo_registry_parity_store_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
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
        StorageCategory.MCP_TELEMETRY,
        "telemetry",
        consumer_module="entrypoints/mcp/_telemetry.py",
        settings_field="cadrumo_mcp_telemetry_dir",
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
        StorageCategory.CORPUS_SEARCH_CACHE,
        "cache/corpus-search",
        consumer_module="application/corpus_search/_runtime.py",
        settings_field="cadrumo_corpus_search_cache_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
    ),
    _location(
        StorageCategory.VALIDATION_VERDICT_CACHE,
        "cache/registry-verdict",
        consumer_module="domain/calculations/registry/_validate_verdict.py",
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
        consumer_module="domain/calculations/registry/_loader_cache.py",
        settings_field="cadrumo_registry_disk_cache_dir",
        lifecycle=StorageLifecycle.RETENTION,
        grouping=StorageGrouping.CACHE,
        fingerprint_participation=FingerprintParticipation.EXCLUDED,
        derives_settings_default=False,
    ),
    # ── Durable generated outputs ───────────────────────────────────────────
    _location(
        StorageCategory.SUBMISSIONS,
        "submissions",
        consumer_module="adapters/persistence/storage/_rotation.py",
        settings_field="cadrumo_submissions_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.WORKFLOW_RUNS,
        "workflow-runs",
        consumer_module="application/workflow/_persistence.py",
        settings_field="cadrumo_workflow_runs_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.DRAFTS,
        "drafts",
        consumer_module="adapters/persistence/storage/_rotation.py",
        settings_field="cadrumo_drafts_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.JUSTIFICANTES,
        "justificantes",
        consumer_module="adapters/persistence/storage/_rotation.py",
        settings_field="cadrumo_justificantes_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.FILING_HISTORY,
        "filing-history",
        consumer_module="adapters/persistence/storage/_rotation.py",
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
        consumer_module="adapters/persistence/storage/_rotation.py",
        settings_field="cadrumo_financial_txs_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.INVOICES,
        "financial/invoices",
        consumer_module="adapters/persistence/storage/_rotation.py",
        settings_field="cadrumo_invoices_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.ATTACHMENTS,
        "financial/attachments",
        consumer_module="adapters/persistence/storage/_rotation.py",
        settings_field="cadrumo_attachments_dir",
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.EXPORTS,
    ),
    _location(
        StorageCategory.USAGE_RATIOS,
        "financial/usage-ratios.json",
        consumer_module="adapters/persistence/storage/_rotation.py",
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
        consumer_module="core/config.py",
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
)


_BUCKET_LOCATIONS: Final[tuple[StorageLocation, ...]] = (
    _location(
        StorageCategory.BUCKET_DATABASE,
        "db",
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
        f"db/{_PRODUCT_DATABASE_FILENAME}",
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
    _location(
        StorageCategory.BUCKET_AUDIT,
        "audit",
        consumer_module="adapters/persistence/storage/_storage_path_definitions.py",
        scope=StorageScope.BUCKET_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.BUCKET_MANIFEST,
        "manifest.toml",
        consumer_module="adapters/persistence/storage/_storage_path_definitions.py",
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
        StorageCategory.KEYSTORE_BUCKET_DEK,
        "bucket.dek.json",
        consumer_module="adapters/persistence/storage/_storage_path_definitions.py",
        node_kind=StorageNodeKind.FILE,
        scope=StorageScope.KEYSTORE_RELATIVE,
        lifecycle=StorageLifecycle.UNBOUNDED_BY_DESIGN,
        grouping=StorageGrouping.STATE,
        override_policy=StorageOverridePolicy.FIXED,
    ),
    _location(
        StorageCategory.KEYSTORE_PROFILE_SESSION,
        "session.v1.json",
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
    "EXTERNAL_PATH_SETTINGS_FIELDS",
    "FINGERPRINT_EXCLUDED_STORAGE_FIELDS",
    "ROOT_DERIVED_STORAGE_FIELDS",
    "ROOT_DERIVED_STORAGE_LOCATIONS",
    "STORAGE_FIELD_CATEGORIES",
    "STORAGE_ROOT_SETTINGS_FIELD",
    "STORAGE_TAXONOMY",
    "ExternalPathDeclaration",
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
