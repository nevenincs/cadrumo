"""Filesystem and blob storage-hierarchy path contracts.

Split out of ``_namespace_registry.py`` along the seam that module's own
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

from pydantic import BaseModel, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core import StorageCategory, storage_location
from ._namespace_taxonomy import StoragePathKind
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
BUCKETS_DIRNAME = storage_location(StorageCategory.BUCKETS).subpath
BUCKET_DB_DIRNAME = storage_location(StorageCategory.BUCKET_DATABASE).subpath
#: Relative to the bucket root, not to ``db/`` -- this is the nested file, the
#: sibling constant above is the directory that holds it.
BUCKET_DATABASE_FILENAME = storage_location(StorageCategory.BUCKET_DATABASE_FILE).subpath
BUCKET_BLOBS_DIRNAME = storage_location(StorageCategory.BUCKET_BLOBS).subpath
BUCKET_AUDIT_DIRNAME = storage_location(StorageCategory.BUCKET_AUDIT).subpath
BUCKET_MANIFEST_FILENAME = storage_location(StorageCategory.BUCKET_MANIFEST).subpath
BUCKET_LOCK_FILENAME = storage_location(StorageCategory.BUCKET_LOCK).subpath
BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME = storage_location(StorageCategory.BUCKET_OUTPUT_LANGUAGE_HINT).subpath
KEYSTORE_DIRNAME = storage_location(StorageCategory.BUCKET_KEYSTORE).subpath
BUCKET_DEK_FILENAME = storage_location(StorageCategory.KEYSTORE_BUCKET_DEK).subpath
PROFILE_SESSION_FILENAME = storage_location(StorageCategory.KEYSTORE_PROFILE_SESSION).subpath
LOGIN_THROTTLE_FILENAME = storage_location(StorageCategory.KEYSTORE_LOGIN_THROTTLE).subpath
#: Directory holding the application-owned config-reset journal. The
#: application module owns the durable journal itself; the name is declared
#: here so the on-disk hierarchy has one inventory, and the enrollment gate
#: pins the two declarations together.
CONFIG_RESET_JOURNAL_DIRNAME = "reset-operations"
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


STORAGE_PATH_DEFINITIONS: Final[tuple[StoragePathDefinition, ...]] = (
    StoragePathDefinition(
        # Root-scoped, not nested under buckets/ -- the cold-start database
        # used only before any profile bucket exists. Every profile-bound
        # write refuses this route (StorageRouteKind.ROOT_FALLBACK_DATABASE),
        # so no real taxpayer content ever lands here; it is a placeholder URL,
        # classified REGENERABLE in PERSISTED_FORMATS accordingly.
        key="root_fallback_database",
        kind=StoragePathKind.FILE,
        grammar="<root>/cadrumo.db",
        owner="cadrumo.core.config",
        segment=storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath,
    ),
    StoragePathDefinition(
        key="bucket_root",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/buckets/<bucket_id>/",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKETS_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_db",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/buckets/<bucket_id>/db/",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKET_DB_DIRNAME,
    ),
    StoragePathDefinition(
        # No single-component segment: the file sits two levels below the
        # bucket root, inside the directory the entry above governs. ``segment``
        # is omitted rather than given the nested value, matching the other
        # non-single-component entries below (``secure_objects_table``,
        # ``blob_manifest``).
        key="bucket_database_file",
        kind=StoragePathKind.FILE,
        grammar="<root>/buckets/<bucket_id>/db/cadrumo.db",
        owner="cadrumo.core.config",
    ),
    StoragePathDefinition(
        key="bucket_blobs",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/buckets/<bucket_id>/blobs/",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKET_BLOBS_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_audit",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/buckets/<bucket_id>/audit/",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKET_AUDIT_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_manifest",
        kind=StoragePathKind.FILE,
        grammar="<root>/buckets/<bucket_id>/manifest.toml",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKET_MANIFEST_FILENAME,
    ),
    StoragePathDefinition(
        key="bucket_lock",
        kind=StoragePathKind.FILE,
        grammar="<root>/buckets/<bucket_id>/.lock",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKET_LOCK_FILENAME,
    ),
    StoragePathDefinition(
        key="bucket_output_language_hint",
        kind=StoragePathKind.FILE,
        grammar="<root>/buckets/<bucket_id>/output-language.hint",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME,
    ),
    StoragePathDefinition(
        key="keystore_bucket",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/keystore/<bucket_id>/",
        owner="cadrumo.adapters.persistence.storage.master_key",
        segment=KEYSTORE_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_dek",
        kind=StoragePathKind.FILE,
        grammar="<root>/keystore/<bucket_id>/bucket.dek.json",
        owner="cadrumo.adapters.persistence.storage.master_key",
        segment=BUCKET_DEK_FILENAME,
    ),
    StoragePathDefinition(
        key="profile_session",
        kind=StoragePathKind.FILE,
        grammar="<root>/keystore/<bucket_id>/session.v1.json",
        owner="cadrumo.adapters.persistence.storage.master_key",
        segment=PROFILE_SESSION_FILENAME,
    ),
    StoragePathDefinition(
        key="login_throttle",
        kind=StoragePathKind.FILE,
        grammar="<root>/keystore/<bucket_id>/login-throttle.json",
        owner="cadrumo.adapters.persistence.storage.master_key",
        segment=LOGIN_THROTTLE_FILENAME,
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
        grammar="<root>/secrets/index.json",
        owner="cadrumo.adapters.persistence.storage.secret_store",
        segment=SECRET_INDEX_FILENAME,
        schema_version=SECRET_INDEX_SCHEMA_VERSION,
    ),
    StoragePathDefinition(
        key="config_reset_journal",
        kind=StoragePathKind.FILE,
        grammar="<root>/reset-operations/<operation_id>.json",
        owner="cadrumo.application.config_reset",
        segment=CONFIG_RESET_JOURNAL_DIRNAME,
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
    ),
    StoragePathDefinition(
        key="blob_content_ciphertext",
        kind=StoragePathKind.BLOB_OBJECT,
        grammar="<root>/blobs/<sha256[:2]>/<sha256>.enc",
        owner="cadrumo.adapters.persistence.storage.blob_store",
    ),
    StoragePathDefinition(
        # The Google-Drive-alternative local filesystem provider fans out one
        # directory per outbound-attachment namespace beneath the bucket's
        # blobs directory, then writes the HMAC-addressed payload alongside
        # an integrity sidecar. Two entries because the payload and its
        # sidecar are two distinct on-disk artefacts sharing one stem.
        key="local_provider_object",
        kind=StoragePathKind.BLOB_OBJECT,
        grammar="<root>/buckets/<bucket_id>/blobs/<namespace>/<hmac_prefix>--<label>.bin",
        owner="cadrumo.adapters.outbound.storage",
    ),
    StoragePathDefinition(
        key="local_provider_object_sidecar",
        kind=StoragePathKind.BLOB_OBJECT,
        grammar="<root>/buckets/<bucket_id>/blobs/<namespace>/<hmac_prefix>--<label>.meta.json",
        owner="cadrumo.adapters.outbound.storage",
    ),
    StoragePathDefinition(
        # The observability run-trace directory fans out one subdirectory per
        # 16-lowercase-hex run id beneath RUNS; the category's own docstring
        # already reasons about this per-run structure (it is why the
        # category is fingerprint-excluded), the id itself was just never
        # promoted to a declared shape until now.
        key="run_trace",
        kind=StoragePathKind.FILE,
        grammar="<root>/runs/<run_id>/trace.json",
        owner="cadrumo.core.observability",
    ),
    StoragePathDefinition(
        key="run_events",
        kind=StoragePathKind.FILE,
        grammar="<root>/runs/<run_id>/events.jsonl",
        owner="cadrumo.core.observability",
    ),
    StoragePathDefinition(
        key="run_envelope",
        kind=StoragePathKind.FILE,
        grammar="<root>/runs/<run_id>/envelope.json",
        owner="cadrumo.core.observability",
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
        grammar="<root>/llm-usage/usage-<timestamp>.jsonl",
        owner="cadrumo.adapters.outbound.llm",
    ),
    StoragePathDefinition(
        key="llm_run_telemetry_record",
        kind=StoragePathKind.FILE,
        grammar="<root>/llm-run-telemetry/run-telemetry-<timestamp>.jsonl",
        owner="cadrumo.adapters.outbound.llm",
    ),
    StoragePathDefinition(
        key="auth_acquisition_lock",
        kind=StoragePathKind.FILE,
        grammar="<root>/tokens/<bucket_id>-<auth_provider_kind>-auth.lock",
        owner="cadrumo.application.auth",
    ),
    StoragePathDefinition(
        key="validation_verdict_cache_entry",
        kind=StoragePathKind.FILE,
        grammar="<root>/cache/registry-verdict/cadrumo_validation_verdict_<sha256[:16]>.json",
        owner="cadrumo.domain.calculations.registry",
    ),
    StoragePathDefinition(
        key="llm_cache_entry",
        kind=StoragePathKind.FILE,
        grammar="<root>/cache/llm-cache/<provider>/<model>/<sha256>-<sha256>.json",
        owner="cadrumo.adapters.outbound.llm",
    ),
)
