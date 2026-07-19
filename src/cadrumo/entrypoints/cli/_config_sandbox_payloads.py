"""Typed ``--json`` payload schemas for config sandbox commands.

Every registered result is a strict :class:`OutputSchema`.
"""

from __future__ import annotations

from ._config_payloads import ProfilePointerPayload
from ._schemas import OutputSchema, register_schema


@register_schema("config.profile.sandbox.create")
class ConfigProfileSandboxCreateResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox create``.

    Reports the new sandbox bucket identity and label; the sandbox is now the
    active profile. ``seeded_from`` names the live profile whose facts were
    copied in, or ``None`` when the sandbox started empty.
    """

    bucket_id: str
    label: str
    seeded_from: str | None = None


@register_schema("config.profile.sandbox.list")
class ConfigProfileSandboxListResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox list``.

    Reuses :class:`ProfilePointerPayload` rows, filtered to buckets whose
    label carries the reserved sandbox prefix.
    """

    active_profile: str | None = None
    sandboxes: list[ProfilePointerPayload]


class SandboxNamespacePayload(OutputSchema):
    """One secure-object namespace row in a sandbox discard preview.

    Mirrors :class:`~cadrumo.application.bucket_maintenance.SandboxNamespaceInventoryRow`:
    only the namespace name and stored-row count, never decrypted payload
    material.
    """

    namespace: str
    row_count: int


@register_schema("config.profile.sandbox.discard")
class ConfigProfileSandboxDiscardResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox discard``.

    Covers both the ``--dry-run`` preview branch (``dry_run=True``, no
    mutation — ``namespaces`` lists what would be removed) and the confirmed
    erase branch (``dry_run=False`` — ``previous_label`` reports the erased
    sandbox's prior label; ``namespaces`` stays empty).
    """

    dry_run: bool = False
    bucket_id: str
    previous_label: str | None = None
    namespaces: list[SandboxNamespacePayload] = []


@register_schema("config.profile.sandbox.prune")
class ConfigProfileSandboxPruneResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox prune``.

    Covers the ``--dry-run`` preview branch (``sandboxes`` names every
    sandbox that would be discarded, nothing removed) and the confirmed
    branch (``discarded`` names every sandbox actually erased). Both
    branches report the total count considered.
    """

    dry_run: bool = False
    total: int
    sandboxes: list[str] = []
    discarded: list[str] = []


@register_schema("config.profile.sandbox.archive")
class ConfigProfileSandboxArchiveResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox archive``.

    Reports the archived sandbox's bucket identity and label. Unlike
    ``discard``, the sandbox bucket, manifest, and encrypted record all
    survive intact — the sandbox merely drops off the live
    ``sandbox list`` surface until ``sandbox restore`` reactivates it.
    """

    bucket_id: str
    label: str


@register_schema("config.profile.sandbox.restore")
class ConfigProfileSandboxRestoreResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox restore``.

    Reports the restored sandbox's bucket identity and label. The
    symmetric inverse of ``sandbox archive``.
    """

    bucket_id: str
    label: str


class SandboxDiskUsageSubdirPayload(OutputSchema):
    """One on-disk subdirectory row in a sandbox disk-usage report.

    Mirrors :class:`~cadrumo.application.bucket_maintenance.BucketDiskUsageSubdirRow`:
    a fixed-layout subdirectory name (``db``, ``blobs``, ``audit``) plus its
    summed regular-file byte total and file count.
    """

    subdir: str
    total_bytes: int
    file_count: int


class SandboxDiskUsagePayload(OutputSchema):
    """One sandbox's disk-usage row within a ``sandbox usage`` report."""

    label: str
    bucket_id: str
    total_bytes: int
    subdirs: list[SandboxDiskUsageSubdirPayload]


@register_schema("config.profile.sandbox.usage")
class ConfigProfileSandboxUsageResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox usage``.

    Reports the on-disk footprint of one named sandbox, or of every sandbox
    at once when no name is given (``total_bytes`` then sums across every
    listed sandbox). The measurement reads only filesystem metadata — never
    decrypted secure-object content — via
    :meth:`~cadrumo.application.bucket_maintenance.BucketMaintenanceService`.disk_usage.
    """

    total_bytes: int
    sandboxes: list[SandboxDiskUsagePayload]


@register_schema("config.profile.sandbox.merge")
class ConfigProfileSandboxMergeResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox merge``.

    Reports the promoted scope, the source sandbox and target profile
    labels, and the per-category row counts merged via
    :func:`~cadrumo.application.bucket_maintenance.merge_sandbox`. A re-run
    against unchanged sandbox content reports the same counts (an
    idempotent no-op write into the target, never a duplicate row).
    """

    scope: str
    source_label: str
    target_label: str
    merged_counts: dict[str, int]
