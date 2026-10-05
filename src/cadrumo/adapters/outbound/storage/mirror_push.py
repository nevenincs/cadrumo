"""Canonical ciphertext mirror push, preserving namespace and lineage policy."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import TypedDict

from ....application.user_profile.archive_operation_ports import (
    ArchiveNamespaceCount,
    ArchivePushManifestDegradation,
    ArchivePushManifestFailure,
    ArchivePushObjectFailure,
    ProfileArchivePushReport,
)
from ....core.hashing import sha256_hex
from ...persistence.storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ...persistence.storage.namespace_taxonomy import StorageRemoteMirrorPolicy
from ...persistence.storage.secure_object_namespaces import SecureObjectNamespaceDefinition
from ...persistence.storage.sql.secure_object_crypto import verify_revision_self_consistency
from ...persistence.storage.sql.secure_object_records import SecureObjectRawRow
from ...persistence.storage.sql.secure_objects import SecureObjectRepository
from .errors import OutboundStorageError, OutboundStorageValidationError
from .mirror_manifest import (
    build_remote_mirror_namespace_manifest,
    compare_remote_mirror_manifests,
    get_remote_mirror_namespace_manifest,
    inspect_remote_mirror_download,
    inspect_remote_mirror_upload,
    put_remote_mirror_namespace_manifest,
    remote_mirror_object_key_hmac,
    remote_mirror_object_label,
)
from .protocol import StorageProvider
from .records import (
    ProviderObjectMetadata,
    ProviderProbeReport,
    RemoteMirrorIssue,
    RemoteMirrorIssueKind,
    RemoteMirrorNamespaceManifest,
)


class AdmittedMirrorStorageProvider:
    """Admit each lazy physical provider call before releasing authority for I/O."""

    def __init__(self, provider_factory: Callable[[], StorageProvider], before_handoff: Callable[[], None]) -> None:
        """Retain one physical provider and its operation-owned admission callback."""
        self._provider_factory = provider_factory
        self._provider: StorageProvider | None = None
        self._before_handoff = before_handoff

    def _admitted_provider(self) -> StorageProvider:
        self._before_handoff()
        if self._provider is None:
            self._provider = self._provider_factory()
        return self._provider

    def put(
        self, namespace: str, object_key_hmac: str, payload: bytes, *, content_hash: str, label: str
    ) -> ProviderObjectMetadata:
        """Admit the existing provider's ciphertext write."""
        return self._admitted_provider().put(
            namespace, object_key_hmac, payload, content_hash=content_hash, label=label
        )

    def get(self, namespace: str, object_key_hmac: str) -> tuple[bytes, ProviderObjectMetadata]:
        """Admit a read whose lazy setup may have durable effects."""
        return self._admitted_provider().get(namespace, object_key_hmac)

    def delete(self, namespace: str, object_key_hmac: str) -> bool:
        """Admit canonical rollback deletion without retaining a guard across I/O."""
        return self._admitted_provider().delete(namespace, object_key_hmac)

    def iter_namespaces(self) -> Iterator[str]:
        """Admit lazy provider iteration before any remote work begins."""
        yield from self._admitted_provider().iter_namespaces()

    def iter_objects(self, namespace: str) -> Iterator[ProviderObjectMetadata]:
        """Admit lazy object iteration through the same provider owner."""
        yield from self._admitted_provider().iter_objects(namespace)

    def probe(self, *, read_only: bool = False) -> ProviderProbeReport:
        """Admit provider setup and canonical probe effects."""
        return self._admitted_provider().probe(read_only=read_only)


def build_profile_archive_push_report(
    *,
    profile: str,
    root_folder_id: str,
    dry_run: bool,
    namespace_filter: str | None,
    limit: int | None,
    result: MirrorRowsResult,
) -> ProfileArchivePushReport:
    """Project the complete canonical mirror outcome into immutable human metadata."""
    return ProfileArchivePushReport(
        profile=profile,
        root_folder_id=root_folder_id,
        dry_run=dry_run,
        namespace_filter=namespace_filter,
        limit=limit,
        pushed_total=sum(result["pushed_by_namespace"].values()),
        skipped_total=sum(result["skipped_by_namespace"].values()),
        failed_total=len(result["failed_objects"]),
        manifest_pushed_total=len(result["manifest_pushed_by_namespace"]),
        manifest_failed_total=len(result["failed_manifests"]),
        manifest_degraded_total=len(result["degraded_manifests"]),
        pushed_by_namespace=tuple(
            ArchiveNamespaceCount(namespace=key, count=value)
            for key, value in sorted(result["pushed_by_namespace"].items())
        ),
        skipped_by_namespace=tuple(
            ArchiveNamespaceCount(namespace=key, count=value)
            for key, value in sorted(result["skipped_by_namespace"].items())
        ),
        manifest_pushed_by_namespace=tuple(
            ArchiveNamespaceCount(namespace=key, count=value)
            for key, value in sorted(result["manifest_pushed_by_namespace"].items())
        ),
        failed_objects=tuple(
            ArchivePushObjectFailure(namespace=ns, hmac=key, error=error) for ns, key, error in result["failed_objects"]
        ),
        cleanup_failed_objects=tuple(
            ArchivePushObjectFailure(namespace=ns, hmac=key, error=error)
            for ns, key, error in result["cleanup_failed_objects"]
        ),
        failed_manifests=tuple(
            ArchivePushManifestFailure(namespace=ns, error=error) for ns, error in result["failed_manifests"]
        ),
        degraded_manifests=tuple(
            ArchivePushManifestDegradation(namespace=ns, detail=detail) for ns, detail in result["degraded_manifests"]
        ),
    )


@dataclass(frozen=True)
class _MirrorRowPartition:
    """Row partition produced before any remote mirror write occurs.

    ``planned_rows_by_namespace`` carries the rows that will be uploaded on a
    non-dry-run; ``skipped_by_namespace`` records the per-namespace counts a
    dry-run reports without touching the provider.
    """

    planned_rows_by_namespace: dict[str, list[SecureObjectRawRow]]
    skipped_by_namespace: dict[str, int]


@dataclass(frozen=True)
class _MirrorPreflightOutcome:
    """Result of inspecting the existing remote mirror before pushing.

    ``manifests_by_namespace`` holds the locally-built manifest for each
    namespace cleared to push; ``blocked_namespaces`` names the namespaces a
    preflight failure removed from the push set. ``failed`` and ``degraded``
    accumulate the operator-facing `(namespace, detail)` diagnostics.
    """

    manifests_by_namespace: dict[str, RemoteMirrorNamespaceManifest]
    blocked_namespaces: set[str]
    failed: list[tuple[str, str]]
    degraded: list[tuple[str, str]]


@dataclass(frozen=True)
class _MirrorObjectPushOutcome:
    """Result of uploading each planned row's ciphertext to the provider.

    ``pushed_by_namespace`` counts the rows that uploaded cleanly AND stayed
    published -- an object rolled back by a same-namespace failure is not
    counted. ``failed_namespaces`` names every namespace that saw at least
    one object failure (so its manifest is withheld); ``failed`` carries the
    `(namespace, hmac, error)` triples for the operator surface.
    ``cleanup_failed`` carries the `(namespace, hmac, error)` triples for a
    rollback delete that itself failed: an object this namespace already
    uploaded, whose namespace later failed, that could not be removed and so
    remains durable but unmanifested (``aeat-ledger-contract`` and
    ``no-silent-under-declaration`` both bar treating this as ordinary success).
    """

    pushed_by_namespace: dict[str, int]
    failed_namespaces: set[str]
    failed: list[tuple[str, str, str]]
    cleanup_failed: list[tuple[str, str, str]] = field(default_factory=list)


def _partition_mirror_rows(
    *,
    repository: SecureObjectRepository,
    namespace_filter: str | None,
    limit: int | None,
    dry_run: bool,
) -> _MirrorRowPartition:
    """Split :meth:`SecureObjectRepository.iter_all_records_raw` into push vs skip.

    Applies the optional ``namespace_filter`` and ``limit`` while iterating;
    on a dry-run every selected row is counted as skipped and no row is
    planned for upload.
    """
    planned_rows_by_ns: dict[str, list[SecureObjectRawRow]] = {}
    skipped_by_ns: dict[str, int] = {}
    total_seen = 0
    for raw_row in repository.iter_all_records_raw():
        if namespace_filter is not None and raw_row.namespace != namespace_filter:
            continue
        total_seen += 1
        if limit is not None and total_seen > limit:
            break
        if dry_run:
            skipped_by_ns[raw_row.namespace] = skipped_by_ns.get(raw_row.namespace, 0) + 1
            continue
        planned_rows_by_ns.setdefault(raw_row.namespace, []).append(raw_row)
    return _MirrorRowPartition(planned_rows_by_namespace=planned_rows_by_ns, skipped_by_namespace=skipped_by_ns)


#: Named once so the refusal text and the code that enforces it cannot drift
#: apart: WHY a lineage failure blocks the namespace rather than merely
#: degrading it. A degraded push still writes ``manifest_by_ns[namespace]`` to
#: the remote provider (``put_remote_mirror_namespace_manifest``), carrying
#: the row's (forged) ``revision_ancestor_ids`` verbatim into
#: ``RemoteMirrorNamespaceManifest.model_dump_json()``. The NEXT sync then
#: reads that manifest back as the remote side of its comparison -- so a
#: degraded push does not merely tolerate today's forgery, it replicates it
#: into the state every future run trusts as authoritative. Ciphertext
#: confidentiality is not what is at risk here (the AEAD already authenticates
#: the payload bytes); it is the lineage metadata the manifest carries that a
#: degraded push would launder into remote authority.
_LINEAGE_FAILURE_BLOCKS_NOT_DEGRADES = (
    "namespace blocked rather than degraded: a degraded push would persist "
    "this forged lineage metadata into the remote manifest, which the next "
    "sync would then trust as the remote comparison state"
)


def _first_lineage_inconsistent_row(rows: list[SecureObjectRawRow]) -> str | None:
    """Return a diagnostic for the first row whose revision lineage fails to recompute.

    :meth:`SecureObjectRepository.iter_all_records_raw` bypasses the
    encrypted-column type decorators by design, so rows sealed under a
    rotated master key still surface for mirroring
    (:func:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository.iter_all_records_raw`).
    That means the decrypting read path's
    :func:`~adapters.persistence.storage.sql.secure_object_crypto.verify_revision_self_consistency`
    call — which the decode core runs before every decrypt
    (:func:`~adapters.persistence.storage.sql._secure_object_row_codec.decode_secure_object_row`)
    — never otherwise runs on these raw rows at all. Recomputing it here, in
    this raw-read/mirror-preflight boundary, before a row's stored lineage
    metadata seeds a manifest or reaches the remote provider, closes that gap
    for the same tampered-covered-column class the decrypting read path
    already refuses (``revision_id``, ``payload_hash``, ``ciphertext_hash``,
    and the previous-revision links).

    Returns ``None`` when every row's lineage recomputes cleanly. The
    returned diagnostic names both the surface (mirror preflight, over the
    raw row) and, via :data:`_LINEAGE_FAILURE_BLOCKS_NOT_DEGRADES`, why the
    caller must block the namespace rather than degrade the push.
    """
    for row in rows:
        if not verify_revision_self_consistency(
            row.revision_id,
            namespace=row.namespace,
            object_key=row.object_key,
            schema_version=row.schema_version,
            written_at=row.written_at,
            previous_revision_id=row.previous_revision_id,
            payload_hash=row.payload_hash,
            ciphertext_hash=row.ciphertext_hash,
            previous_payload_hash=row.previous_payload_hash,
        ):
            hmac_hex = remote_mirror_object_key_hmac(row.namespace, row.object_key)
            return (
                f"revision_lineage_inconsistent:mirror_preflight:{hmac_hex[:16]}:{_LINEAGE_FAILURE_BLOCKS_NOT_DEGRADES}"
            )
    return None


#: Named once so the refusal text and the reason cannot drift apart: WHY an
#: unmirrorable namespace is blocked here rather than skipped quietly. A skip
#: lands in ``skipped_by_namespace``, which the operator reads as "nothing to
#: do" — the same channel a dry run and an empty namespace use. A namespace
#: that declares it must not leave the machine is not nothing-to-do; it is a
#: declaration the sync is being asked to violate, and the operator has to be
#: able to tell those apart. Blocking also matches what the decrypting read
#: path already does with an unregistered namespace, which refuses rather than
#: returning empty.
_UNMIRRORABLE_NAMESPACE_BLOCKS_NOT_SKIPS = (
    "namespace blocked rather than skipped: its registry definition withholds "
    "remote mirroring, so pushing it would contradict the declaration, and a "
    "silent skip would be indistinguishable from having nothing to push"
)


def _unmirrorable_namespace_reason(namespace: str) -> str | None:
    """Return why ``namespace`` must not be mirrored, or ``None`` when it may be.

    :meth:`SecureObjectRepository.iter_all_records_raw` deliberately bypasses
    the decrypting read path, and with it
    ``SecureObjectRepository._enforce_registered_read_policy`` — the funnel
    that otherwise resolves a row's namespace definition and refuses an
    unregistered one. The mirror therefore has to re-assert the registry
    contract at its own boundary, exactly as
    :func:`_first_lineage_inconsistent_row` re-asserts the pre-decrypt lineage
    gate for the same reason.

    An unregistered namespace is refused rather than waved through. The rows
    most likely to be unregistered are the newest, and mirroring a row whose
    disposition nothing has declared is precisely what
    :data:`StorageRemoteMirrorPolicy` exists to prevent; refusing names it in
    the operator-facing failure list rather than dropping it silently.
    """
    try:
        definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_value(namespace)
    except KeyError:
        return f"namespace_unregistered:mirror_preflight:{_UNMIRRORABLE_NAMESPACE_BLOCKS_NOT_SKIPS}"
    return _mirror_refusal_for_definition(definition)


def _mirror_refusal_for_definition(definition: SecureObjectNamespaceDefinition) -> str | None:
    """Return why ``definition``'s namespace must not be mirrored, or ``None``.

    Split from the registry lookup so the decision can be exercised against a
    policy the shipped registry does not currently carry. No namespace ships
    as ``LOCAL_ONLY`` today, so a test that re-labelled a shipped one to reach
    that branch would be asserting against a production declaration somebody
    may legitimately change; taking a definition directly lets the test build
    the case it means to test.
    """
    policy = definition.remote_mirror_policy
    if policy is StorageRemoteMirrorPolicy.CIPHERTEXT_WITH_METADATA:
        return None
    return f"remote_mirror_withheld:{policy.value}:{_UNMIRRORABLE_NAMESPACE_BLOCKS_NOT_SKIPS}"


def _preflight_mirror_namespaces(
    *,
    provider: StorageProvider,
    planned_rows_by_namespace: dict[str, list[SecureObjectRawRow]],
) -> _MirrorPreflightOutcome:
    """Inspect the existing remote mirror for every planned namespace.

    Builds the local :class:`RemoteMirrorNamespaceManifest` per namespace and
    compares it against the remote state. A namespace is blocked (and its
    manifest withheld, and none of its ciphertext pushed) on a raw-row
    revision-lineage failure, a remote inspection error, or a blocking
    revision conflict; degradations are recorded without blocking.

    The lineage check runs first and per namespace, not once across every
    planned row: it is the raw-read counterpart of the pre-decrypt lineage
    gate the decode core always runs (see
    :func:`_first_lineage_inconsistent_row`), so a namespace whose rows are
    genuine is unaffected by a tampered row elsewhere, and a namespace with
    even one tampered covered column is blocked before its raw metadata ever
    seeds a manifest or reaches the remote provider.

    A lineage failure is deliberately a BLOCK, never a degradation, and that
    is a load-bearing distinction rather than a severity preference: a
    degraded namespace still enters ``manifest_by_ns`` and is pushed to the
    remote provider later in this pass, carrying the row's (forged)
    ``revision_ancestor_ids`` verbatim — and the next sync then reads that
    manifest back as the remote side of ITS comparison. Degrading here would
    not merely tolerate a local forgery once; it would replicate it into the
    remote state every future run trusts as authoritative. See
    :data:`_LINEAGE_FAILURE_BLOCKS_NOT_DEGRADES`.
    """
    manifest_by_ns: dict[str, RemoteMirrorNamespaceManifest] = {}
    blocked: set[str] = set()
    failed: list[tuple[str, str]] = []
    degraded: list[tuple[str, str]] = []
    for namespace, rows in planned_rows_by_namespace.items():
        unmirrorable = _unmirrorable_namespace_reason(namespace)
        if unmirrorable is not None:
            failed.append((namespace, unmirrorable))
            blocked.add(namespace)
            continue
        lineage_failure = _first_lineage_inconsistent_row(rows)
        if lineage_failure is not None:
            failed.append((namespace, lineage_failure))
            blocked.add(namespace)
            continue
        manifest = build_remote_mirror_namespace_manifest(namespace, rows)
        try:
            blocking_failures, degradations = _inspect_existing_remote_mirror(provider=provider, manifest=manifest)
        except OutboundStorageError as exc:
            failed.append((namespace, type(exc).__name__))
            blocked.add(namespace)
            continue
        if degradations:
            degraded.append((namespace, "; ".join(degradations)))
        if blocking_failures:
            failed.append((namespace, "; ".join(blocking_failures)))
            blocked.add(namespace)
            continue
        manifest_by_ns[namespace] = manifest
    return _MirrorPreflightOutcome(
        manifests_by_namespace=manifest_by_ns,
        blocked_namespaces=blocked,
        failed=failed,
        degraded=degraded,
    )


def _push_mirror_objects(
    *,
    provider: StorageProvider,
    planned_rows_by_namespace: dict[str, list[SecureObjectRawRow]],
    blocked_namespaces: set[str],
) -> _MirrorObjectPushOutcome:
    """Upload every planned row's ciphertext payload to the provider.

    Skips namespaces that preflight blocked. Each row uploads via
    :meth:`StorageProvider.put` under its `<hmac>--<label>.bin` name; a
    per-object upload error records the failure and marks the namespace so
    its manifest is later withheld.

    A namespace's manifest is withheld on any object failure within it, so a
    row this same namespace already uploaded successfully would otherwise be
    left durable on the remote provider with no manifest that can enumerate
    or reconcile it (finding: partial failure leaves ciphertext unowned).
    Every namespace marked failed is therefore rolled back here: every object
    key that namespace pushed is deleted before the outcome is returned, so a
    withheld-manifest namespace is either fully absent from the remote or
    fully manifested, never partially orphaned.
    """
    pushed_by_ns: dict[str, int] = {}
    failed_namespaces: set[str] = set()
    failed: list[tuple[str, str, str]] = []
    pushed_keys_by_namespace: dict[str, list[str]] = {}
    for namespace, rows in planned_rows_by_namespace.items():
        if namespace in blocked_namespaces:
            continue
        for raw_row in rows:
            hmac_hex = remote_mirror_object_key_hmac(raw_row.namespace, raw_row.object_key)
            label = remote_mirror_object_label(raw_row.namespace)
            content_hash = f"sha256-{sha256_hex(raw_row.payload)}"
            try:
                provider.put(
                    raw_row.namespace,
                    hmac_hex,
                    raw_row.payload,
                    content_hash=content_hash,
                    label=label,
                )
            except OutboundStorageError as exc:
                failed.append((raw_row.namespace, hmac_hex, type(exc).__name__))
                failed_namespaces.add(raw_row.namespace)
                continue
            pushed_by_ns[raw_row.namespace] = pushed_by_ns.get(raw_row.namespace, 0) + 1
            pushed_keys_by_namespace.setdefault(raw_row.namespace, []).append(hmac_hex)

    cleanup_failed: list[tuple[str, str, str]] = []
    for namespace in failed_namespaces:
        for hmac_hex in pushed_keys_by_namespace.get(namespace, ()):
            try:
                provider.delete(namespace, hmac_hex)
            except OutboundStorageError as exc:
                cleanup_failed.append((namespace, hmac_hex, type(exc).__name__))
        # The manifest for this namespace is withheld regardless of rollback
        # outcome, so its object count must not be reported as pushed.
        pushed_by_ns.pop(namespace, None)

    return _MirrorObjectPushOutcome(
        pushed_by_namespace=pushed_by_ns,
        failed_namespaces=failed_namespaces,
        failed=failed,
        cleanup_failed=cleanup_failed,
    )


def _push_mirror_manifests(
    *,
    provider: StorageProvider,
    manifests_by_namespace: dict[str, RemoteMirrorNamespaceManifest],
    failed_namespaces: set[str],
    manifest_failed: list[tuple[str, str]],
) -> dict[str, int]:
    """Persist and verify each namespace manifest whose objects uploaded cleanly.

    Withholds the manifest for any namespace that saw an object failure.
    Appends post-push inspection failures (or a put error) onto the shared
    ``manifest_failed`` accumulator and returns the per-namespace object
    counts for the manifests that pushed and verified.
    """
    manifest_pushed_by_ns: dict[str, int] = {}
    for namespace, manifest in manifests_by_namespace.items():
        if namespace in failed_namespaces:
            continue
        try:
            put_remote_mirror_namespace_manifest(provider, manifest)
            inspection_failures = _inspect_pushed_remote_mirror(provider=provider, manifest=manifest)
        except OutboundStorageError as exc:
            manifest_failed.append((namespace, type(exc).__name__))
            continue
        if inspection_failures:
            manifest_failed.append((namespace, "; ".join(inspection_failures)))
            continue
        manifest_pushed_by_ns[namespace] = manifest.object_count
    return manifest_pushed_by_ns


class MirrorRowsResult(TypedDict):
    """Typed result of :func:`push_secure_object_mirror_rows`.

    Each value mirrors the corresponding field on the mirror-pass outcome
    dataclasses (:class:`_MirrorObjectPushOutcome`,
    :class:`_MirrorRowPartition`, :class:`_MirrorPreflightOutcome`), so the
    push handler reads precisely-typed counts and diagnostic triples rather
    than ``object``.
    """

    pushed_by_namespace: dict[str, int]
    skipped_by_namespace: dict[str, int]
    failed_objects: list[tuple[str, str, str]]
    manifest_pushed_by_namespace: dict[str, int]
    failed_manifests: list[tuple[str, str]]
    degraded_manifests: list[tuple[str, str]]
    cleanup_failed_objects: list[tuple[str, str, str]]


def push_secure_object_mirror_rows(
    *,
    provider: StorageProvider,
    repository: SecureObjectRepository,
    namespace_filter: str | None,
    limit: int | None,
    dry_run: bool,
) -> MirrorRowsResult:
    """Push complete permitted ciphertext namespaces through canonical mirror policy.

    Parameter types: ``repository``
    (:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`).
    """
    if limit is not None and not dry_run:
        raise OutboundStorageValidationError(
            "non-dry-run Google sync push with --limit cannot produce a complete remote mirror manifest",
            context={"limit": str(limit)},
            translated_message="cli.config.google.detail.sync_push_limit_requires_dry_run",
        )

    partition = _partition_mirror_rows(
        repository=repository,
        namespace_filter=namespace_filter,
        limit=limit,
        dry_run=dry_run,
    )
    planned_rows_by_ns = partition.planned_rows_by_namespace

    if dry_run:
        preflight = _MirrorPreflightOutcome(manifests_by_namespace={}, blocked_namespaces=set(), failed=[], degraded=[])
    else:
        preflight = _preflight_mirror_namespaces(provider=provider, planned_rows_by_namespace=planned_rows_by_ns)

    object_push = _push_mirror_objects(
        provider=provider,
        planned_rows_by_namespace=planned_rows_by_ns,
        blocked_namespaces=preflight.blocked_namespaces,
    )

    manifest_failed = preflight.failed
    if dry_run:
        manifest_pushed_by_ns: dict[str, int] = {}
    else:
        manifest_pushed_by_ns = _push_mirror_manifests(
            provider=provider,
            manifests_by_namespace=preflight.manifests_by_namespace,
            failed_namespaces=object_push.failed_namespaces,
            manifest_failed=manifest_failed,
        )

    return {
        "pushed_by_namespace": object_push.pushed_by_namespace,
        "skipped_by_namespace": partition.skipped_by_namespace,
        "failed_objects": object_push.failed,
        "manifest_pushed_by_namespace": manifest_pushed_by_ns,
        "failed_manifests": manifest_failed,
        "degraded_manifests": preflight.degraded,
        "cleanup_failed_objects": object_push.cleanup_failed,
    }


def _inspect_existing_remote_mirror(
    *,
    provider: StorageProvider,
    manifest: RemoteMirrorNamespaceManifest,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    remote_manifest = get_remote_mirror_namespace_manifest(provider, manifest.namespace)
    if remote_manifest is None:
        return (), ()

    blocking_failures: list[str] = []
    degradations: list[str] = []
    for inspection in (
        compare_remote_mirror_manifests(local=manifest, remote=remote_manifest),
        inspect_remote_mirror_download(provider, remote_manifest),
    ):
        for issue in inspection.issues:
            formatted = _format_remote_mirror_issue(issue)
            if issue.kind is RemoteMirrorIssueKind.REVISION_CONFLICT:
                blocking_failures.append(formatted)
                continue
            degradations.append(formatted)
    return tuple(blocking_failures), tuple(degradations)


def _format_remote_mirror_issue(issue: RemoteMirrorIssue) -> str:
    object_key = issue.object_key_hmac[:16] if issue.object_key_hmac is not None else "<namespace>"
    return f"{issue.kind.value}:{object_key}:{issue.detail}"


def _inspect_pushed_remote_mirror(
    *,
    provider: StorageProvider,
    manifest: RemoteMirrorNamespaceManifest,
) -> tuple[str, ...]:
    failures: list[str] = []
    for inspection in (
        inspect_remote_mirror_upload(provider, manifest),
        inspect_remote_mirror_download(provider, manifest),
    ):
        for issue in inspection.issues:
            failures.append(_format_remote_mirror_issue(issue))
    return tuple(failures)
