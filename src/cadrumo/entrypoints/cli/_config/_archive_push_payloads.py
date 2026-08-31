"""Typed ``--json`` payload schemas for ``aeat config profile archive push``.

``push`` writes every secure-object row's on-wire ciphertext to the configured
remote store. It shares the ``archive`` subject with ``export``/``import`` but
NOT their artifact: those carry one portable capsule, this writes thousands of
ciphertext blobs under per-namespace manifests. ``archive import`` cannot read
what ``push`` wrote, and the schemas are kept separate so that stays visible.

There is no ``archive pull``. The counterpart does not exist, and its absence
sits beside a working local ``export``/``import`` pair precisely so an operator
can see it is missing.
"""

from __future__ import annotations

from ....core.json_contract import OutputSchema


class ProfileArchivePushFailedObjectPayload(OutputSchema):
    """One failed ciphertext object in a sync push report.

    The row identifies the secure-object namespace, the remote
    :func:`remote_mirror_object_key_hmac`,
    and the storage error observed while writing or verifying that ciphertext
    object. Plaintext secure-object payloads never appear in this schema.
    """

    namespace: str
    hmac: str
    error: str


class ProfileArchivePushFailedManifestPayload(OutputSchema):
    """One failed namespace manifest in a sync push report.

    Mirrors failures around
    :func:`put_remote_mirror_namespace_manifest`
    or the follow-up manifest inspection pass for one secure-object namespace.
    """

    namespace: str
    error: str


class ProfileArchivePushDegradedManifestPayload(OutputSchema):
    """One degraded namespace manifest detected during a sync push.

    ``detail`` summarizes the
    :class:`RemoteMirrorInspection` issue found
    after upload/download validation of that namespace's remote manifest.
    """

    namespace: str
    detail: str


class ProfileArchivePushResult(OutputSchema):
    """JSON envelope for ``aeat config profile archive push``.

    Summarizes the ciphertext mirror pass over the active bucket's secure-object
    rows. Object uploads return
    :class:`ProviderObjectMetadata` internally,
    while namespace manifests are validated through
    :class:`RemoteMirrorNamespaceManifest` and
    :class:`RemoteMirrorInspection`. This
    payload exposes counts and error rows only, not decrypted profile data.
    """

    operation: str = "config.profile.archive.push"
    profile: str
    root_folder_id: str
    dry_run: bool
    namespace_filter: str | None = None
    limit: int | None = None
    pushed_total: int
    skipped_total: int
    failed_total: int
    manifest_pushed_total: int
    manifest_failed_total: int
    manifest_degraded_total: int
    pushed_by_namespace: dict[str, int] = {}
    skipped_by_namespace: dict[str, int] = {}
    failed_objects: list[ProfileArchivePushFailedObjectPayload] = []
    manifest_pushed_by_namespace: dict[str, int] = {}
    failed_manifests: list[ProfileArchivePushFailedManifestPayload] = []
    degraded_manifests: list[ProfileArchivePushDegradedManifestPayload] = []
    # A namespace whose manifest was withheld for an object failure rolls
    # back every object it already pushed (see ``_push_mirror_objects``); a
    # row here means that rollback delete itself failed, so the object is
    # durable on the remote provider with no manifest that can enumerate or
    # reconcile it and requires manual operator cleanup.
    cleanup_failed_objects: list[ProfileArchivePushFailedObjectPayload] = []
