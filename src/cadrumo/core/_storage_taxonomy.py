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
from typing import Final

from pydantic import BaseModel, Field, model_validator

from ._models import STRICT_FROZEN_CONFIG


class StorageNodeKind(StrEnum):
    """Whether a member names a directory or a single file.

    Declared rather than inferred. A name-suffix heuristic cannot reach the
    per-bucket file names -- ``manifest.toml``, ``.lock``, the keystore
    sidecars -- that follow no suffix convention, and inferring wrongly creates
    a directory where a document belongs, which fails much later at the write.

    A second enum names the same axis one layer out: the storage adapter's
    ``StoragePathKind`` answers a wider question, adding a member for a row
    living in the encrypted database rather than on disk and one for
    content-addressed blob content. The two are deliberately **not** merged --
    ``core`` must not import an adapter type, and a ``StrEnum`` carrying
    members cannot later be extended to subclass another -- so the
    relationship is a declared parity rather than a shared definition:
    ``DIRECTORY`` and ``FILE`` must spell their values identically on both
    sides. Both are ``StrEnum``, so code compares them by value across the
    boundary and a divergent spelling would return ``False`` rather than
    raising. A gate pins that overlap, and pins only the overlap, so the
    adapter stays free to grow members ``core`` has no use for.
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


class StorageArea(StrEnum):
    """Stable operator vocabulary for the four aggregate storage families."""

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
    root-scoped names distinct from per-bucket subdirectories.
    """

    # ── State substrate and identity ────────────────────────────────────────
    TOKENS = "tokens"
    SECRETS = "secrets"
    BLOBS = "blobs"
    LIVE_STATE = "live-state"

    # ── Fixed layout: within the secret store ────────────────────────────────
    SECRETS_MASTER_KEY = "secrets.master-key"
    SECRETS_MASTER_KDF = "secrets.master-kdf"
    SECRETS_MASTER_LOCK = "secrets.master-lock"
    SECRETS_KEYRING_LOCK = "secrets.keyring-lock"
    SECRETS_MASTER_RECOVERY_KEY = "secrets.master-recovery-key"

    # ── Fixed layout: live IVA remote-state capture ─────────────────────────
    LIVE_STATE_IVA_WALLET = "live-state.iva-wallet"
    LIVE_STATE_IVA_REMOTE_STATE = "live-state.iva-remote-state"
    LIVE_STATE_IVA_REMOTE_STATE_FILED_HISTORY = "live-state.iva-remote-state.filed-history"
    LIVE_STATE_IVA_REMOTE_STATE_WALLET = "live-state.iva-remote-state.wallet"

    # ── Diagnostic and append-only telemetry logs ───────────────────────────
    LOGS = "logs"
    LOG_FILE = "logs.file"
    LLM_USAGE = "llm-usage"
    LLM_RUN_TELEMETRY = "llm-run-telemetry"
    MCP_TELEMETRY = "mcp-telemetry"
    RUNS = "runs"

    # ── Regenerable, evictable caches ───────────────────────────────────────
    LLM_CACHE = "llm-cache"
    CORPUS_TEXT_CACHE = "corpus-text-cache"
    CORPUS_TEXT_CACHE_FILE = "corpus-text-cache.file"
    CORPUS_SEARCH_CACHE = "corpus-search-cache"
    CORPUS_SEARCH_INDEX = "corpus-search-cache.index"
    VALIDATION_VERDICT_CACHE = "validation-verdict-cache"
    REGISTRY_DISK_CACHE = "registry-disk-cache"
    LOCALE_CATALOGUE_CACHE = "locale-catalogue-cache"

    # ── Durable generated outputs ───────────────────────────────────────────
    SUBMISSIONS = "submissions"
    SUBMISSIONS_AMENDMENT_RESULTS = "submissions.amendment-results"
    SUBMISSIONS_AMENDMENTS = "submissions.amendments"
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
    ATTACHMENTS_MANIFESTS = "attachments.manifests"
    USAGE_RATIOS = "usage-ratios"

    # ── Fixed layout: the bucket container and the active-profile pointer ───
    BUCKETS = "buckets"
    ACTIVE_PROFILE_POINTER = "active-profile-pointer"
    ROOT_FALLBACK_DATABASE = "root-fallback-database"
    CONFIG_RESET_JOURNAL = "config-reset-journal"
    OPERATION_JOURNAL = "operation-journal"
    PROFILE_CUSTODY_TRANSACTION_JOURNAL = "profile-custody-transaction-journal"
    PROFILE_CUSTODY_RECEIPT = "profile-custody-receipt"
    PROFILE_CUSTODY_HOLD_EVIDENCE = "profile-custody-hold-evidence"
    # The three owner directories below the hold-evidence root. Each names one
    # persisted format's home, so each is declared here rather than joined as a
    # literal at the authority that writes into it: the path registry spells the
    # same segments, and a name typed in both places drifts on the first rename.
    PROFILE_CUSTODY_HOLD_LEGAL_OWNER = "profile-custody-hold-evidence.legal-owner"
    PROFILE_CUSTODY_HOLD_FILING_OWNER = "profile-custody-hold-evidence.filing-owner"
    PROFILE_CUSTODY_HOLD_DERIVED_EVIDENCE = "profile-custody-hold-evidence.derived"
    PROFILE_CUSTODY_LABEL_HEAD = "profile-custody-label-head"

    # ── Fixed layout: per-bucket ────────────────────────────────────────────
    BUCKET_DATABASE = "bucket.db"
    BUCKET_DATABASE_FILE = "bucket.db-file"
    BUCKET_BLOBS = "bucket.blobs"
    BUCKET_MANIFEST = "bucket.manifest"
    BUCKET_LOCK = "bucket.lock"
    BUCKET_OUTPUT_LANGUAGE_HINT = "bucket.output-language-hint"
    BUCKET_KEYSTORE = "bucket.keystore"

    # ── Fixed layout: current-format profile capsule ───────────────────────
    PROFILE_CAPSULE_CUSTODY = "profile-capsule.custody"
    PROFILE_CAPSULE_PASSWORD_ENVELOPE = "profile-capsule.password-envelope"  # noqa: S105 - taxonomy label, not a credential
    PROFILE_CAPSULE_RECOVERY_ENVELOPE = "profile-capsule.recovery-envelope"
    PROFILE_CAPSULE_DATA = "profile-capsule.data"
    PROFILE_CAPSULE_COMMIT = "profile-capsule.commit"

    # ── Fixed layout: per-keystore ──────────────────────────────────────────
    # The value still says "session" while the artefact it locates is the
    # profile acceleration receipt. The token is an on-disk path segment, so
    # correcting it moves real directories: it is carried by an authorised
    # destructive local reset, never by a read-tolerant rename.
    KEYSTORE_PROFILE_SESSION = "keystore.profile-session"
    KEYSTORE_PROFILE_SESSION_RETIREMENT = "keystore.profile-session-retirement"
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

    test_pinned_exception: str | None = None
    """Why this member's resolution deliberately diverges from its declared subpath under pytest.

    ``None`` for every member but one. The registry disk cache is the sole
    case: under pytest its resolver selects the host-shared OS temp directory
    instead of ``<root>/cache/registry``, so every xdist worker and every
    subprocess-spawning test shares one compiled pickle for the immutable
    bundled tree rather than each getting a private, per-worker cache. Without
    this field that branch reads as an undeclared special case buried in one
    consumer; stating the reason here turns it into a positive, member-level
    declaration the taxonomy alone carries -- the same discipline
    :data:`EXTERNAL_PATH_SETTINGS_FIELDS` applies to a whole field escaping the
    taxonomy, narrowed to one member's one runtime branch.
    """

    @model_validator(mode="after")
    def _fixed_override_policy_forbids_a_settings_field(self) -> StorageLocation:
        """Refuse a FIXED member that also exposes an operator-facing settings field.

        The two claims contradict each other. ``FIXED`` asserts an operator
        cannot relocate this member -- the guarantee that a keystore cannot be
        moved out from under the bucket it unlocks. A ``settings_field`` is
        precisely the field an operator overrides a location through. Today's
        declarations happen to keep every ``FIXED`` member's field ``None``,
        but "happens to" is not a guard: nothing before this validator stopped
        a future ``FIXED`` member from also naming a ``settings_field``, which
        would let a settings override silently defeat the immovability
        ``FIXED`` exists to promise. Refusing the combination at declaration
        time makes it unconstructable instead of merely absent so far.
        """
        if self.override_policy is StorageOverridePolicy.FIXED and self.settings_field is not None:
            raise ValueError(
                f"storage category {self.category.value!r} declares override_policy=FIXED and "
                f"settings_field={self.settings_field!r}; a FIXED member must not expose an "
                "operator-overridable settings field, or its immovability guarantee is not real",
            )
        return self

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
    test_pinned_exception: str | None = None,
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
        test_pinned_exception=test_pinned_exception,
    )


# Deliberately not at module top: this closes a circular import.
# ``_storage_taxonomy_locations`` imports the axis enums, ``StorageLocation``
# and ``_location`` from THIS module, so it can only be imported back here
# once those names are already bound -- i.e. after the class/function
# definitions above, not before them.
from ._storage_taxonomy_locations import (  # noqa: E402 - see comment above
    FINGERPRINT_EXCLUDED_STORAGE_FIELDS,
    ROOT_DERIVED_STORAGE_FIELDS,
    ROOT_DERIVED_STORAGE_LOCATIONS,
    STORAGE_FIELD_CATEGORIES,
    STORAGE_TAXONOMY,
    bucket_scoped_storage_path,
    storage_location,
    storage_path,
    storage_tree_targets,
)

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
    "StorageArea",
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
