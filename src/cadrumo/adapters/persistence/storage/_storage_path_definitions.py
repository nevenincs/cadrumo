"""Filesystem and blob storage-hierarchy path contracts.

Split out of ``_secure_object_namespaces.py`` along the seam that module's own
docstring already named: the SQL secure-object namespace keys are a
different concern -- logical database keys, not filesystem paths -- and keep
their own declarations there. Everything here is the other half: the
per-bucket and per-keystore layout names (read from the one core storage
taxonomy) and the :class:`StoragePathDefinition` contracts for the on-disk
hierarchy, including the parameterised fan-out SHAPES (a content-hash
prefix, an outbound namespace, a per-run id) that cannot be enumerable
:class:`~cadrumo.core.StorageCategory` members.

:data:`STORAGE_PATH_DEFINITIONS` is consumed by
``_namespace_registry.STORAGE_NAMESPACE_REGISTRY``, which combines it with
the SQL namespace definitions into one
:class:`~adapters.persistence.storage.StorageHierarchyRegistry`. Nothing
here reaches back into ``_namespace_registry.py``, so there is no cycle.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core import StorageCategory, storage_location
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core.observability.store import ENVELOPE_FILENAME, EVENTS_FILENAME, TRACE_FILENAME
from ._namespace_taxonomy import StoragePathAnchor, StoragePathKind
from .errors import NamespaceRegistryError

# The bucket and keystore layout names are read from the core storage
# taxonomy, which is their single declaration; this module is a consumer of
# that authority, not a second one. They were declared in adapters
# originally, and core could not import them without inverting the
# hexagonal direction -- so the core modules that needed the same names
# re-typed them as inline literals instead, unpinned against these. Moving
# the declaration inward is what made those copies deletable rather than
# merely pinnable, and it adds no upward dependency: an adapter depending on
# core is the legal direction.
ROOT_FALLBACK_DATABASE_FILENAME = storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath
BUCKETS_DIRNAME = storage_location(StorageCategory.BUCKETS).subpath
BUCKET_DB_DIRNAME = storage_location(StorageCategory.BUCKET_DATABASE).subpath
#: Relative to the bucket root, not to ``db/`` -- this is the nested file, the
#: sibling constant above is the directory that holds it.
BUCKET_DATABASE_FILENAME = storage_location(StorageCategory.BUCKET_DATABASE_FILE).subpath
BUCKET_BLOBS_DIRNAME = storage_location(StorageCategory.BUCKET_BLOBS).subpath
#: Names the RETIRED plaintext bucket manifest, kept to recognise it on a
#: pre-cutover bucket. It backs no path definition below -- see the note where
#: one would otherwise sit.
BUCKET_MANIFEST_FILENAME = storage_location(StorageCategory.BUCKET_MANIFEST).subpath
BUCKET_LOCK_FILENAME = storage_location(StorageCategory.BUCKET_LOCK).subpath
BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME = storage_location(StorageCategory.BUCKET_OUTPUT_LANGUAGE_HINT).subpath
KEYSTORE_DIRNAME = storage_location(StorageCategory.BUCKET_KEYSTORE).subpath
PROFILE_SESSION_FILENAME = storage_location(StorageCategory.KEYSTORE_PROFILE_SESSION).subpath
#: The crash-window sidecar for an interrupted session-key swap. Its location is
#: derived from the receipt above at the call site, which is why the name is
#: declared once in the taxonomy and read here rather than typed at the writer.
PROFILE_SESSION_RETIREMENT_FILENAME = storage_location(StorageCategory.KEYSTORE_PROFILE_SESSION_RETIREMENT).subpath
LOGIN_THROTTLE_FILENAME = storage_location(StorageCategory.KEYSTORE_LOGIN_THROTTLE).subpath
#: The three owner directories below the hold-evidence root, each the home of one
#: persisted format. Declared as whole taxonomy subpaths (``<root>``-relative,
#: two components) rather than as bare leaf names, so the grammars below spell
#: exactly what the taxonomy declares.
PROFILE_CUSTODY_HOLD_LEGAL_OWNER_SUBPATH = storage_location(StorageCategory.PROFILE_CUSTODY_HOLD_LEGAL_OWNER).subpath
PROFILE_CUSTODY_HOLD_FILING_OWNER_SUBPATH = storage_location(StorageCategory.PROFILE_CUSTODY_HOLD_FILING_OWNER).subpath
PROFILE_CUSTODY_HOLD_DERIVED_SUBPATH = storage_location(StorageCategory.PROFILE_CUSTODY_HOLD_DERIVED_EVIDENCE).subpath
PROFILE_CUSTODY_DIRNAME = storage_location(StorageCategory.PROFILE_CAPSULE_CUSTODY).subpath
#: Bucket-root-relative nested paths (``custody/envelope.v1.json``), not single
#: components -- so their definitions below omit ``segment``, matching
#: ``bucket_database_file``'s treatment of the same shape.
PROFILE_PASSWORD_ENVELOPE_FILENAME = storage_location(StorageCategory.PROFILE_CAPSULE_PASSWORD_ENVELOPE).subpath
PROFILE_RECOVERY_ENVELOPE_FILENAME = storage_location(StorageCategory.PROFILE_CAPSULE_RECOVERY_ENVELOPE).subpath
PROFILE_DATA_DIRNAME = storage_location(StorageCategory.PROFILE_CAPSULE_DATA).subpath
PROFILE_COMMIT_FILENAME = storage_location(StorageCategory.PROFILE_CAPSULE_COMMIT).subpath
ACTIVE_PROFILE_POINTER_FILENAME = storage_location(StorageCategory.ACTIVE_PROFILE_POINTER).subpath
#: Directory holding the application-owned config-reset journal. The
#: application module owns the durable journal itself; the name is declared
#: once in the core taxonomy (:class:`~cadrumo.core.StorageCategory.CONFIG_RESET_JOURNAL`)
#: and read here, so the on-disk hierarchy has one inventory rather than two
#: agreeing constants.
CONFIG_RESET_JOURNAL_DIRNAME = storage_location(StorageCategory.CONFIG_RESET_JOURNAL).subpath
OPERATION_JOURNAL_DIRNAME = storage_location(StorageCategory.OPERATION_JOURNAL).subpath
#: The six names below back the parameterised fan-out grammars further down this
#: module (run-trace, LLM usage/telemetry logs, the token acquisition lock, and
#: the two cache families). Each was previously hand-typed straight into its
#: grammar string even though the taxonomy already declares it, duplicating the
#: name the same way the bucket/keystore literals above did before this module
#: started reading them off ``storage_location`` too.
RUNS_DIRNAME = storage_location(StorageCategory.RUNS).subpath
LLM_USAGE_DIRNAME = storage_location(StorageCategory.LLM_USAGE).subpath
LLM_RUN_TELEMETRY_DIRNAME = storage_location(StorageCategory.LLM_RUN_TELEMETRY).subpath
TOKENS_DIRNAME = storage_location(StorageCategory.TOKENS).subpath
#: Two-component subpaths (``cache/<name>``) -- interpolated whole, not split,
#: since the taxonomy declares the compound as one subpath rather than two
#: nested categories.
VALIDATION_VERDICT_CACHE_SUBPATH = storage_location(StorageCategory.VALIDATION_VERDICT_CACHE).subpath
LLM_CACHE_SUBPATH = storage_location(StorageCategory.LLM_CACHE).subpath
BLOB_MANIFEST_SCHEMA_VERSION = 1
SECRET_RECORD_SCHEMA_VERSION = 1
SECRET_INDEX_FILENAME = "index.json"  # noqa: S105 - filename, not a credential
SECRET_INDEX_SCHEMA_VERSION = 1


class StoragePathDefinition(BaseModel):
    """Contract for one storage hierarchy path or logical marker."""

    model_config = _STRICT_FROZEN

    key: str = Field(min_length=1)
    kind: StoragePathKind
    grammar: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    segment: str | None = Field(default=None, min_length=1)
    schema_version: int | None = Field(default=None, ge=1)
    anchor: StoragePathAnchor | None = Field(default=None)
    """Which directory ``grammar``'s ``<root>`` token means.

    Required for every ``<root>``-anchored kind (``FILE``, ``DIRECTORY``,
    ``BLOB_OBJECT``) and forbidden for ``LOGICAL_SQL`` (a ``db://`` logical
    path has no ``<root>`` token to anchor). The three blob-content entries
    declare :attr:`StoragePathAnchor.BLOB_STORE_ROOT` rather than
    :attr:`~StoragePathAnchor.STORAGE_ROOT`; see :class:`StoragePathAnchor`'s
    own docstring for what that distinction currently rests on (an open
    question, not a settled one) and for why both anchors are checked by
    the directory-agreement gate regardless.
    """

    @field_validator("key")
    @classmethod
    def _key_is_registry_safe(cls, value: str) -> str:
        if value != value.strip():
            raise NamespaceRegistryError("path key must not carry surrounding whitespace")
        if any(separator in value for separator in ("/", "\\")):
            raise NamespaceRegistryError("path key must not contain path separators")
        return value

    @field_validator("segment")
    @classmethod
    def _segment_is_single_path_component(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value != value.strip():
            raise NamespaceRegistryError("path segment must not carry surrounding whitespace")
        if "/" in value or "\\" in value:
            raise NamespaceRegistryError("path segment must be a single component")
        return value

    @model_validator(mode="after")
    def _anchor_matches_kind(self) -> StoragePathDefinition:
        if self.kind is StoragePathKind.LOGICAL_SQL:
            if self.anchor is not None:
                raise NamespaceRegistryError(
                    f"path {self.key!r} is LOGICAL_SQL (a db:// logical path) and must not declare "
                    "an anchor -- there is no <root> token to anchor",
                )
        elif self.anchor is None:
            raise NamespaceRegistryError(
                f"path {self.key!r} is {self.kind.value} and must declare an anchor -- "
                "which directory its <root> token means is not inferrable",
            )
        return self


STORAGE_PATH_DEFINITIONS: Final[tuple[StoragePathDefinition, ...]] = (
    StoragePathDefinition(
        # Root-scoped, not nested under buckets/ -- the cold-start database
        # used only before any profile bucket exists. Every profile-bound
        # write refuses this route (StorageRouteKind.ROOT_FALLBACK_DATABASE),
        # so no real taxpayer content ever lands here; it is a placeholder URL,
        # classified REGENERABLE in PERSISTED_FORMATS accordingly.
        key="root_fallback_database",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{ROOT_FALLBACK_DATABASE_FILENAME}",
        owner="cadrumo.core.config",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=ROOT_FALLBACK_DATABASE_FILENAME,
    ),
    StoragePathDefinition(
        key="bucket_root",
        kind=StoragePathKind.DIRECTORY,
        grammar=f"<root>/{BUCKETS_DIRNAME}/<bucket_id>/",
        owner="cadrumo.adapters.persistence.storage.bucket",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=BUCKETS_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_db",
        kind=StoragePathKind.DIRECTORY,
        grammar=f"<root>/{BUCKETS_DIRNAME}/<bucket_id>/{BUCKET_DB_DIRNAME}/",
        owner="cadrumo.adapters.persistence.storage.bucket",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=BUCKET_DB_DIRNAME,
    ),
    StoragePathDefinition(
        # No single-component segment: the file sits two levels below the
        # bucket root, inside the directory the entry above governs. ``segment``
        # is omitted rather than given the nested value, matching the other
        # non-single-component entries below (``secure_objects_table``,
        # ``blob_manifest``). ``BUCKET_DATABASE_FILENAME`` is already the
        # bucket-root-relative nested path (``db/cadrumo.db``, per its own
        # docstring above) -- interpolating ``BUCKET_DB_DIRNAME`` in front of it
        # too would re-duplicate the ``db`` segment it already carries.
        key="bucket_database_file",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{BUCKETS_DIRNAME}/<bucket_id>/{BUCKET_DATABASE_FILENAME}",
        owner="cadrumo.core.config",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        key="bucket_blobs",
        kind=StoragePathKind.DIRECTORY,
        grammar=f"<root>/{BUCKETS_DIRNAME}/<bucket_id>/{BUCKET_BLOBS_DIRNAME}/",
        owner="cadrumo.adapters.persistence.storage.bucket",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=BUCKET_BLOBS_DIRNAME,
    ),
    # The plaintext bucket manifest has NO definition here, deliberately. Its
    # reader was removed with the capsule cutover and nothing writes one, so a
    # definition would declare a hierarchy member no current bucket has -- the
    # same "declaration backed by nothing" the enrollment gate exists to catch,
    # committed on purpose. The filename constant survives above because the
    # name is still needed to RECOGNISE the retired member on a bucket that
    # predates the cutover; naming a retired member is not declaring a format.
    StoragePathDefinition(
        key="bucket_lock",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{BUCKETS_DIRNAME}/<bucket_id>/{BUCKET_LOCK_FILENAME}",
        owner="cadrumo.adapters.persistence.storage.bucket",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=BUCKET_LOCK_FILENAME,
    ),
    StoragePathDefinition(
        key="bucket_output_language_hint",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{BUCKETS_DIRNAME}/<bucket_id>/{BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME}",
        owner="cadrumo.adapters.persistence.storage.bucket",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME,
    ),
    # The profile capsule's three current-format records. Each is a single
    # on-disk file with its own schema version, so each is a persisted format
    # in its own right and belongs in this inventory -- the independent source
    # the durability declaration is checked against. They were previously
    # absent from it while their layout constants were already declared above,
    # so the names existed here but the paths did not, and the enrollment gate
    # read every capsule format as a declaration backed by nothing.
    StoragePathDefinition(
        key="profile_capsule_password_envelope",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{BUCKETS_DIRNAME}/<bucket_id>/{PROFILE_PASSWORD_ENVELOPE_FILENAME}",
        owner="cadrumo.adapters.persistence.storage.custody",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        key="profile_capsule_recovery_envelope",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{BUCKETS_DIRNAME}/<bucket_id>/{PROFILE_RECOVERY_ENVELOPE_FILENAME}",
        owner="cadrumo.adapters.persistence.storage.custody",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        key="profile_capsule_commit",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{BUCKETS_DIRNAME}/<bucket_id>/{PROFILE_COMMIT_FILENAME}",
        owner="cadrumo.adapters.persistence.storage.custody",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=PROFILE_COMMIT_FILENAME,
    ),
    StoragePathDefinition(
        # Root-scoped rather than bucket-scoped, and deliberately so: it names
        # WHICH bucket is active, so it cannot live inside one.
        key="active_profile_pointer",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{ACTIVE_PROFILE_POINTER_FILENAME}",
        owner="cadrumo.core.config",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=ACTIVE_PROFILE_POINTER_FILENAME,
    ),
    StoragePathDefinition(
        key="keystore_bucket",
        kind=StoragePathKind.DIRECTORY,
        grammar=f"<root>/{KEYSTORE_DIRNAME}/<bucket_id>/",
        owner="cadrumo.adapters.persistence.storage.master_key",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=KEYSTORE_DIRNAME,
    ),
    StoragePathDefinition(
        key="profile_session",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{KEYSTORE_DIRNAME}/<bucket_id>/{PROFILE_SESSION_FILENAME}",
        owner="cadrumo.adapters.persistence.storage.master_key",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=PROFILE_SESSION_FILENAME,
    ),
    StoragePathDefinition(
        # The session receipt's crash-window sibling. It has its own schema
        # version and its own strict reader, so it is a persisted format in its
        # own right and belongs in this inventory -- the independent source the
        # durability declaration is checked against. It was previously invisible
        # here because its writer derives the path from the receipt's own path,
        # and a durability declaration with no discoverable home reads as stale.
        key="profile_session_retirement_journal",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{KEYSTORE_DIRNAME}/<bucket_id>/{PROFILE_SESSION_RETIREMENT_FILENAME}",
        owner="cadrumo.adapters.persistence.storage.custody",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=PROFILE_SESSION_RETIREMENT_FILENAME,
    ),
    StoragePathDefinition(
        key="login_throttle",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{KEYSTORE_DIRNAME}/<bucket_id>/{LOGIN_THROTTLE_FILENAME}",
        owner="cadrumo.adapters.persistence.storage.master_key",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=LOGIN_THROTTLE_FILENAME,
    ),
    # The three custody hold-evidence records. Each is one file per profile
    # under its own owner directory, each carries its own schema version, and
    # each is enrolled in the durability inventory. No ``segment``: the owner
    # subpaths above are two components, matching the treatment of every other
    # nested entry here.
    StoragePathDefinition(
        key="profile_legal_hold_snapshot",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{PROFILE_CUSTODY_HOLD_LEGAL_OWNER_SUBPATH}/<profile_id>.json",
        owner="cadrumo.application.evidence",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        key="profile_filing_retention_snapshot",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{PROFILE_CUSTODY_HOLD_FILING_OWNER_SUBPATH}/<profile_id>.json",
        owner="cadrumo.application.filing",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        # Fans out one further level: the derived join is written once per
        # OWNER, so the owner is a parameter here rather than a declared
        # directory the way the two source snapshots above are.
        key="profile_custody_hold_evidence",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{PROFILE_CUSTODY_HOLD_DERIVED_SUBPATH}/<owner>/<profile_id>.json",
        owner="cadrumo.application.user_profile",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        # Was ``<cadrumo_secret_store_dir>/index.json`` -- a placeholder token
        # with no declared regex fragment, so any test pinning this key failed
        # with the grammar compiler's own tooling error rather than a
        # conformance result. ``cadrumo_secret_store_dir`` resolves to
        # ``<root>/secrets`` (the ``SECRETS`` taxonomy member), so spelling
        # that out directly makes the grammar both compilable and consistent
        # with every other ``<root>``-anchored entry here.
        key="secret_index",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/secrets/{SECRET_INDEX_FILENAME}",
        owner="cadrumo.adapters.persistence.storage.secret_store",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=SECRET_INDEX_FILENAME,
        schema_version=SECRET_INDEX_SCHEMA_VERSION,
    ),
    StoragePathDefinition(
        key="config_reset_journal",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{CONFIG_RESET_JOURNAL_DIRNAME}/<operation_id>.json",
        owner="cadrumo.application.config_reset",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=CONFIG_RESET_JOURNAL_DIRNAME,
    ),
    StoragePathDefinition(
        key="operation_journal",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{OPERATION_JOURNAL_DIRNAME}/<operation_id>.json",
        owner="cadrumo.adapters.persistence.operations",
        anchor=StoragePathAnchor.STORAGE_ROOT,
        segment=OPERATION_JOURNAL_DIRNAME,
        schema_version=1,
    ),
    StoragePathDefinition(
        key="secure_objects_table",
        kind=StoragePathKind.LOGICAL_SQL,
        grammar="db://secure_objects/<namespace>/<object_key>",
        owner="cadrumo.adapters.persistence.storage.sql",
    ),
    StoragePathDefinition(
        key="blob_manifest",
        kind=StoragePathKind.BLOB_OBJECT,
        grammar="<root>/blobs/<sha256[:2]>/<sha256>.manifest.json",
        owner="cadrumo.adapters.persistence.storage.blob_store",
        anchor=StoragePathAnchor.BLOB_STORE_ROOT,
        schema_version=BLOB_MANIFEST_SCHEMA_VERSION,
    ),
    # The six entries below declare parameterised fan-out SHAPES, not
    # enumerable locations: a content hash prefix, a namespace, and a per-run
    # id cannot each get their own StorageCategory member, but the shape they
    # fan out into can be declared here exactly as ``blob_manifest`` above
    # already does -- and, for that entry, the grammar string is not merely
    # descriptive: ``blob_store/_blob_store.py`` parses it at import time to
    # derive its own shard-directory name and manifest suffix. Each new entry
    # below is pinned by a test that produces a REAL path through the real
    # write path and asserts it against a regex derived from this grammar, so
    # the declaration and production behaviour cannot silently drift apart.
    StoragePathDefinition(
        key="blob_content_plaintext",
        kind=StoragePathKind.BLOB_OBJECT,
        grammar="<root>/blobs/<sha256[:2]>/<sha256>",
        owner="cadrumo.adapters.persistence.storage.blob_store",
        anchor=StoragePathAnchor.BLOB_STORE_ROOT,
    ),
    StoragePathDefinition(
        key="blob_content_ciphertext",
        kind=StoragePathKind.BLOB_OBJECT,
        grammar="<root>/blobs/<sha256[:2]>/<sha256>.enc",
        owner="cadrumo.adapters.persistence.storage.blob_store",
        anchor=StoragePathAnchor.BLOB_STORE_ROOT,
    ),
    StoragePathDefinition(
        # The Google-Drive-alternative local filesystem provider fans out one
        # directory per outbound-attachment namespace beneath the bucket's
        # blobs directory, then writes the HMAC-addressed payload alongside
        # an integrity sidecar. Two entries because the payload and its
        # sidecar are two distinct on-disk artefacts sharing one stem.
        key="local_provider_object",
        kind=StoragePathKind.BLOB_OBJECT,
        grammar=f"<root>/{BUCKETS_DIRNAME}/<bucket_id>/{BUCKET_BLOBS_DIRNAME}/<namespace>/<hmac_prefix>--<label>.bin",
        owner="cadrumo.adapters.outbound.storage",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        key="local_provider_object_sidecar",
        kind=StoragePathKind.BLOB_OBJECT,
        grammar=(
            f"<root>/{BUCKETS_DIRNAME}/<bucket_id>/{BUCKET_BLOBS_DIRNAME}/<namespace>/<hmac_prefix>--<label>.meta.json"
        ),
        owner="cadrumo.adapters.outbound.storage",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        # The observability run-trace directory fans out one subdirectory per
        # 16-lowercase-hex run id beneath RUNS; the category's own docstring
        # already reasons about this per-run structure (it is why the
        # category is fingerprint-excluded), the id itself was just never
        # promoted to a declared shape until now.
        key="run_trace",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{RUNS_DIRNAME}/<run_id>/{TRACE_FILENAME}",
        owner="cadrumo.core.observability",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        key="run_events",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{RUNS_DIRNAME}/<run_id>/{EVENTS_FILENAME}",
        owner="cadrumo.core.observability",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        key="run_envelope",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{RUNS_DIRNAME}/<run_id>/{ENVELOPE_FILENAME}",
        owner="cadrumo.core.observability",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    # The five entries below declare filename TEMPLATES rather than a single
    # fixed leaf -- a daily log filename, a bucket/provider-keyed lock name, a
    # digest-suffixed cache filename, a provider/model-keyed cache path --
    # each governed by the taxonomy's parent directory member (LLM_USAGE,
    # LLM_RUN_TELEMETRY, TOKENS, VALIDATION_VERDICT_CACHE, LLM_CACHE) plus a
    # grammar spelling the interpolated shape, exactly the mechanism the six
    # entries above already use for the blob/run fan-outs.
    #
    # Three of the five (llm_usage_record, llm_run_telemetry_record,
    # llm_cache_entry) are NOT materialised as files: their producers persist
    # through ``secure_object_repository_for_active_bucket().save(...)``
    # (encrypted SQL secure objects), and each producer's own docstring
    # states its returned path is "logical ... for operator display only" /
    # "The cache itself is persisted in encrypted SQL secure objects". The
    # grammar still documents that real, produced STRING -- callers build and
    # return it for display -- but no byte is ever written at it. Declared as
    # ``kind=FILE`` anyway (matching the composition the honesty review's taint
    # pass found, and giving the display-path contract a governed home) rather
    # than invented as a new kind; the conformance tests for these three name
    # this explicitly and assert the returned Path, never on-disk presence.
    StoragePathDefinition(
        key="llm_usage_record",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{LLM_USAGE_DIRNAME}/usage-<timestamp>.jsonl",
        owner="cadrumo.adapters.outbound.llm",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        key="llm_run_telemetry_record",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{LLM_RUN_TELEMETRY_DIRNAME}/run-telemetry-<timestamp>.jsonl",
        owner="cadrumo.adapters.outbound.llm",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        key="auth_acquisition_lock",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{TOKENS_DIRNAME}/<bucket_id>-<auth_provider_kind>-auth.lock",
        owner="cadrumo.application.auth",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        key="validation_verdict_cache_entry",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{VALIDATION_VERDICT_CACHE_SUBPATH}/cadrumo_validation_verdict_<sha256[:16]>.json",
        owner="cadrumo.domain.calculations.registry",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
    StoragePathDefinition(
        key="llm_cache_entry",
        kind=StoragePathKind.FILE,
        grammar=f"<root>/{LLM_CACHE_SUBPATH}/<provider>/<model>/<sha256>-<sha256>.json",
        owner="cadrumo.adapters.outbound.llm",
        anchor=StoragePathAnchor.STORAGE_ROOT,
    ),
)
