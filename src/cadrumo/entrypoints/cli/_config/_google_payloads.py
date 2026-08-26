"""Typed ``--json`` payload schemas for Google config CLI commands.

Each class declared here is a strict
:class:`OutputSchema` subclass and is referenced as a deferred public schema
target by production-authored CommandSpec so the
JSON-contract test suite can enumerate every google-config command surface this
module covers. Validated results enter
:class:`SchemaEnvelope` through
:func:`emit_envelope`.

Field sets match the production payload dicts constructed in ``_google.py``,
and ``_google_folder.py`` at their emit sites. All
sequence fields use ``list`` rather than ``tuple`` because
``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.

The payload classes document only the CLI transport shapes referenced by
production-authored CommandSpec. OAuth state remains
owned by :mod:`google`, Drive mirror state by
:mod:`storage`, and calc-sheets semantics by
:mod:`calc_sheets`.

See Also:
    :mod:`_google`
        Google OAuth, status, and Drive mirror emit sites.
    :mod:`_google_folder`
        Drive root-folder configuration emit sites.
"""

from __future__ import annotations

from ....adapters.outbound.storage import ProviderKind
from ....core.json_contract import OutputSchema


class GoogleRegisterResult(OutputSchema):
    """JSON envelope for ``aeat config google register``.

    Projects the operator-imported
    :class:`OAuthClient` after
    :func:`save_client` persists
    it for the active profile. Only non-secret orientation fields are exposed;
    ``client_secret`` never enters the CLI payload.
    """

    operation: str = "config.google.register"
    profile: str
    client_id: str
    project_id: str


class GoogleLoginResult(OutputSchema):
    """JSON envelope for ``aeat config google login``.

    The ``consent`` branch mirrors the
    :class:`OAuthMetadata` returned with an
    :class:`OAuthToken` by
    :func:`run_login_flow`. The
    ``refresh-only`` branch reports the existing metadata without exposing the
    refresh token.
    """

    operation: str = "config.google.login"
    profile: str
    mode: str
    account_email: str
    granted_scopes: list[str] = []


class GoogleStatusResult(OutputSchema):
    """JSON envelope for ``aeat config google status``.

    Combines stored :class:`OAuthClient`
    presence with the non-secret
    :class:`OAuthMetadata` audit record. Missing
    client or session records are represented with ``False`` booleans and
    ``None`` detail fields so status remains a read-only inspection surface.
    """

    operation: str = "config.google.status"
    profile: str
    client_registered: bool
    client_id: str | None = None
    session_present: bool
    account_email: str | None = None
    granted_scopes: list[str] = []
    issued_at: str | None = None
    last_refresh_at: str | None = None
    reauth_required: bool | None = None


class GoogleLogoutResult(OutputSchema):
    """JSON envelope for ``aeat config google logout``.

    Reports the result of
    :func:`delete_session`: token
    and metadata removal are surfaced separately, while the registered
    :class:`OAuthClient` is intentionally
    preserved for the next login.
    """

    operation: str = "config.google.logout"
    profile: str
    token_removed: bool
    metadata_removed: bool
    client_preserved: bool


# ---------------------------------------------------------------------------
# Drive sync sub-app
# ---------------------------------------------------------------------------


class GoogleSyncProbeResult(OutputSchema):
    """JSON envelope for ``aeat config google sync probe``.

    Adapts :class:`ProviderProbeReport` from
    the resolved Google Drive :class:`StorageProvider`.
    ``root_folder_id`` is included from the configured provider so operators
    can line up probe health with the selected Drive root.
    """

    operation: str = "config.google.sync.probe"
    profile: str
    provider_kind: ProviderKind
    reachable: bool
    writable: bool
    read_only: bool
    root_folder_present: bool | None = None
    root_folder_id: str
    detail: str = ""


class GoogleSyncFailedObjectPayload(OutputSchema):
    """One failed ciphertext object in a sync push report.

    The row identifies the secure-object namespace, the remote
    :func:`remote_mirror_object_key_hmac`,
    and the storage error observed while writing or verifying that ciphertext
    object. Plaintext secure-object payloads never appear in this schema.
    """

    namespace: str
    hmac: str
    error: str


class GoogleSyncFailedManifestPayload(OutputSchema):
    """One failed namespace manifest in a sync push report.

    Mirrors failures around
    :func:`put_remote_mirror_namespace_manifest`
    or the follow-up manifest inspection pass for one secure-object namespace.
    """

    namespace: str
    error: str


class GoogleSyncDegradedManifestPayload(OutputSchema):
    """One degraded namespace manifest detected during a sync push.

    ``detail`` summarizes the
    :class:`RemoteMirrorInspection` issue found
    after upload/download validation of that namespace's remote manifest.
    """

    namespace: str
    detail: str


class GoogleSyncPushResult(OutputSchema):
    """JSON envelope for ``aeat config google sync push``.

    Summarizes the ciphertext mirror pass over the active bucket's secure-object
    rows. Object uploads return
    :class:`ProviderObjectMetadata` internally,
    while namespace manifests are validated through
    :class:`RemoteMirrorNamespaceManifest` and
    :class:`RemoteMirrorInspection`. This
    payload exposes counts and error rows only, not decrypted profile data.
    """

    operation: str = "config.google.sync.push"
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
    failed_objects: list[GoogleSyncFailedObjectPayload] = []
    manifest_pushed_by_namespace: dict[str, int] = {}
    failed_manifests: list[GoogleSyncFailedManifestPayload] = []
    degraded_manifests: list[GoogleSyncDegradedManifestPayload] = []
    # A namespace whose manifest was withheld for an object failure rolls
    # back every object it already pushed (see ``_push_mirror_objects``); a
    # row here means that rollback delete itself failed, so the object is
    # durable on the remote provider with no manifest that can enumerate or
    # reconcile it and requires manual operator cleanup.
    cleanup_failed_objects: list[GoogleSyncFailedObjectPayload] = []
