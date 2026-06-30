"""Typed ``--json`` payload schemas for Google config CLI commands.

Each class declared here is a strict
:class:`~aeat.entrypoints.cli._schemas.OutputSchema` subclass and is decorated
with :func:`~aeat.entrypoints.cli._schemas.register_schema` so the
JSON-contract test suite can enumerate every google-config command surface this
module covers. Validated results enter
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope` through
:func:`~aeat.entrypoints.cli._common._emit_envelope`.

Field sets match the production payload dicts constructed in ``_google.py``,
``_google_folder.py``, and ``_google_sync_calc.py`` at their emit sites. All
sequence fields use ``list`` rather than ``tuple`` because
``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.

The payload classes document only the CLI transport shapes registered with
:func:`~aeat.entrypoints.cli._schemas.register_schema`. OAuth state remains
owned by :mod:`~aeat.adapters.outbound.google`, Drive mirror state by
:mod:`~aeat.adapters.outbound.storage`, and calc-sheets semantics by
:mod:`~aeat.application.storage.calc_sheets`.

See Also:
    :mod:`~aeat.entrypoints.cli._config._google`
        Google OAuth, status, and Drive mirror emit sites.
    :mod:`~aeat.entrypoints.cli._config._google_folder`
        Drive root-folder configuration emit sites.
    :mod:`~aeat.entrypoints.cli._config._google_sync_calc`
        Google Sheets export, pull, verify, and compute emit sites.
"""

from __future__ import annotations

from pydantic import Field

from ....domain.calculations.registry import CasillaId, FormulaId, LegalRefId, SourceRefId
from .._schemas import OutputSchema, register_schema


@register_schema("config.google.register")
class GoogleRegisterResult(OutputSchema):
    """JSON envelope for ``aeat config google register``.

    Projects the operator-imported
    :class:`~aeat.adapters.outbound.google.OAuthClient` after
    :func:`~aeat.adapters.outbound.google._session_store.save_client` persists
    it for the active profile. Only non-secret orientation fields are exposed;
    ``client_secret`` never enters the CLI payload.
    """

    operation: str = "config.google.register"
    profile: str
    client_id: str
    project_id: str


@register_schema("config.google.login")
class GoogleLoginResult(OutputSchema):
    """JSON envelope for ``aeat config google login``.

    The ``consent`` branch mirrors the
    :class:`~aeat.adapters.outbound.google.OAuthMetadata` returned with an
    :class:`~aeat.adapters.outbound.google.OAuthToken` by
    :func:`~aeat.adapters.outbound.google._oauth_flow.run_login_flow`. The
    ``refresh-only`` branch reports the existing metadata without exposing the
    refresh token.
    """

    operation: str = "config.google.login"
    profile: str
    mode: str
    account_email: str
    granted_scopes: list[str] = []


@register_schema("config.google.status")
class GoogleStatusResult(OutputSchema):
    """JSON envelope for ``aeat config google status``.

    Combines stored :class:`~aeat.adapters.outbound.google.OAuthClient`
    presence with the non-secret
    :class:`~aeat.adapters.outbound.google.OAuthMetadata` audit record. Missing
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


@register_schema("config.google.logout")
class GoogleLogoutResult(OutputSchema):
    """JSON envelope for ``aeat config google logout``.

    Reports the result of
    :func:`~aeat.adapters.outbound.google._session_store.delete_session`: token
    and metadata removal are surfaced separately, while the registered
    :class:`~aeat.adapters.outbound.google.OAuthClient` is intentionally
    preserved for the next login.
    """

    operation: str = "config.google.logout"
    profile: str
    token_removed: bool
    metadata_removed: bool
    client_preserved: bool


# ---------------------------------------------------------------------------
# Drive folder sub-app
# ---------------------------------------------------------------------------


@register_schema("config.google.folder.set")
class GoogleFolderSetResult(OutputSchema):
    """JSON envelope for ``aeat config google folder set``.

    Mirrors the :class:`~aeat.adapters.outbound.google.DriveConfig` written by
    :func:`~aeat.adapters.outbound.google._session_store.save_drive_config` for
    the active profile. The folder id becomes the Google Drive root consumed by
    the storage provider and calc-sheets export commands.
    """

    operation: str = "config.google.folder.set"
    profile: str
    root_folder_id: str


@register_schema("config.google.folder.get")
class GoogleFolderGetResult(OutputSchema):
    """JSON envelope for ``aeat config google folder get``.

    Projects the optional
    :class:`~aeat.adapters.outbound.google.DriveConfig` loaded from the active
    profile. ``configured`` distinguishes an absent persisted root from a root
    folder id that is present and ready for provider construction.
    """

    operation: str = "config.google.folder.get"
    profile: str
    configured: bool
    root_folder_id: str | None = None


# ---------------------------------------------------------------------------
# Drive sync sub-app
# ---------------------------------------------------------------------------


@register_schema("config.google.sync.probe")
class GoogleSyncProbeResult(OutputSchema):
    """JSON envelope for ``aeat config google sync probe``.

    Adapts :class:`~aeat.adapters.outbound.storage.ProviderProbeReport` from
    the resolved Google Drive :class:`~aeat.adapters.outbound.storage.StorageProvider`.
    ``root_folder_id`` is included from the configured provider so operators
    can line up probe health with the selected Drive root.
    """

    operation: str = "config.google.sync.probe"
    profile: str
    provider_kind: str
    reachable: bool
    writable: bool
    read_only: bool
    root_folder_present: bool | None = None
    root_folder_id: str
    detail: str = ""


class GoogleSyncFailedObjectPayload(OutputSchema):
    """One failed ciphertext object in a sync push report.

    The row identifies the secure-object namespace, the remote
    :func:`~aeat.adapters.outbound.storage._mirror_manifest.remote_mirror_object_key_hmac`,
    and the storage error observed while writing or verifying that ciphertext
    object. Plaintext secure-object payloads never appear in this schema.
    """

    namespace: str
    hmac: str
    error: str


class GoogleSyncFailedManifestPayload(OutputSchema):
    """One failed namespace manifest in a sync push report.

    Mirrors failures around
    :func:`~aeat.adapters.outbound.storage._mirror_manifest.put_remote_mirror_namespace_manifest`
    or the follow-up manifest inspection pass for one secure-object namespace.
    """

    namespace: str
    error: str


class GoogleSyncDegradedManifestPayload(OutputSchema):
    """One degraded namespace manifest detected during a sync push.

    ``detail`` summarizes the
    :class:`~aeat.adapters.outbound.storage.RemoteMirrorInspection` issue found
    after upload/download validation of that namespace's remote manifest.
    """

    namespace: str
    detail: str


@register_schema("config.google.sync.push")
class GoogleSyncPushResult(OutputSchema):
    """JSON envelope for ``aeat config google sync push``.

    Summarizes the ciphertext mirror pass over the active bucket's secure-object
    rows. Object uploads return
    :class:`~aeat.adapters.outbound.storage.ProviderObjectMetadata` internally,
    while namespace manifests are validated through
    :class:`~aeat.adapters.outbound.storage.RemoteMirrorNamespaceManifest` and
    :class:`~aeat.adapters.outbound.storage.RemoteMirrorInspection`. This
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


# ---------------------------------------------------------------------------
# Drive sync calc sub-app
# ---------------------------------------------------------------------------


@register_schema("config.google.sync.calc.export")
class GoogleSyncCalcExportResult(OutputSchema):
    """JSON envelope for ``aeat config google sync calc export``.

    Projects :class:`~aeat.adapters.outbound.google._calc_sheets_apply.CalcSheetsApplyResult`
    after :func:`~aeat.application.storage.calc_sheets.build_export_plan` creates
    the pure :class:`~aeat.application.storage.calc_sheets.SheetExportPlan` and
    :func:`~aeat.adapters.outbound.google._calc_sheets_apply.apply_export_plan`
    materialises it in Google Sheets.
    """

    operation: str = "config.google.sync.calc.export"
    profile: str
    modelo: str
    revision: str
    period: str
    year: int
    engine_version: str
    registry_sha: str
    root_folder_id: str
    folder_id: str
    spreadsheet_id: str
    spreadsheet_url: str
    value_cells_written: int
    formula_cells_written: int
    protected_ranges_written: int
    tab_count: int


class GoogleSyncCalcVerifyDivergencePayload(OutputSchema):
    """One divergent casilla row in a calc verify report.

    Mirrors a :class:`~aeat.application.storage.calc_sheets._parity_harness.CasillaParity`
    row where local Decimal output, Google Sheets output, and optionally the
    AEAT oracle do not all agree.
    """

    casilla_id: CasillaId
    label: str
    local: str | None = None
    sheets: str | None = None
    aeat: str | None = None


@register_schema("config.google.sync.calc.verify")
class GoogleSyncCalcVerifyResult(OutputSchema):
    """JSON envelope for ``aeat config google sync calc verify``.

    Projects the :class:`~aeat.application.storage.calc_sheets._parity_harness.ParityReport`
    returned by
    :func:`~aeat.application.storage.calc_sheets._parity_harness.verify_modelo_parity`.
    The payload keeps the aggregate verdict beside the divergent casilla rows
    so consumers can fail fast without discarding audit detail.
    """

    operation: str = "config.google.sync.calc.verify"
    profile: str
    modelo: str
    revision: str
    period: str
    year: int
    spreadsheet_id: str
    spreadsheet_url: str
    verdict: str
    aeat_oracle_present: bool
    computed_count: int
    divergence_count: int
    divergences: list[GoogleSyncCalcVerifyDivergencePayload] = []


class GoogleSyncCalcPullOperatorEditPayload(OutputSchema):
    """One populated operator casilla edit emitted by ``sync calc pull``.

    Narrows the populated
    :class:`~aeat.adapters.outbound.google._calc_sheets_pull.OperatorEdit`
    subset of a :class:`~aeat.adapters.outbound.google._calc_sheets_pull.PullResult`
    to the public CLI fields.
    """

    casilla_id: CasillaId
    label: str
    value: str | None = None


class GoogleSyncCalcComputeCasillaPayload(OutputSchema):
    """One registry-computed casilla emitted by ``sync calc compute``.

    Mirrors a :class:`~aeat.domain.calculations.registry.RegistryCalculationEntry`
    produced from a pulled workbook. Legal and source references are required so
    the Google Sheets compute surface keeps the same grounding contract as the
    core modelo calculation output.
    """

    casilla_id: CasillaId
    value: str
    formula_id: FormulaId | None = None
    legal_refs: list[LegalRefId] = Field(min_length=1)
    source_refs: list[SourceRefId] = Field(min_length=1)


@register_schema("config.google.sync.calc.pull")
class GoogleSyncCalcPullResult(OutputSchema):
    """JSON envelope for ``aeat config google sync calc pull``.

    Projects the :class:`~aeat.adapters.outbound.google._calc_sheets_pull.PullResult`
    returned by
    :func:`~aeat.adapters.outbound.google._calc_sheets_pull.pull_operator_edits`.
    The payload composes
    :class:`~aeat.adapters.outbound.google._calc_sheets_pull.PullMetadata`, the
    :class:`~aeat.adapters.outbound.google._calc_sheets_pull.MetadataMatchState`,
    populated operator/binding/relation edits, and optional row-set assemblies.
    Casilla-bearing rows are typed so the CLI cannot emit anonymous string
    casilla references at this boundary. Computing casilla values from pulled
    edits is a separate verb (``sync calc compute``); this transport payload
    carries no computed block.
    """

    operation: str = "config.google.sync.calc.pull"
    profile: str
    modelo: str
    revision: str
    period: str
    year: int
    spreadsheet_id: str
    metadata_match: str
    metadata: dict[str, object]
    cells_read: int
    operator_edits_total: int
    operator_edits_populated: int
    binding_edits_populated: int
    relation_edits_populated: int
    operator_edits: list[GoogleSyncCalcPullOperatorEditPayload] = []
    binding_edits: list[dict[str, object]] = []
    relation_edits: list[dict[str, object]] = []
    row_set_edits_populated: int
    row_set_cells_populated: int
    assembled_groupings: list[dict[str, object]] = []
    assembled_observation_count: int
    row_set_edits: list[dict[str, object]] = []


@register_schema("config.google.sync.calc.compute")
class GoogleSyncCalcComputeResult(OutputSchema):
    """JSON envelope for ``aeat config google sync calc compute``.

    Pulls operator-edited cells through
    :func:`~aeat.adapters.outbound.google._calc_sheets_pull.pull_operator_edits`,
    then runs
    :func:`~aeat.adapters.outbound.google._calc_sheets_pull.compute_from_pull`
    against the shared registry engine. The verb persists nothing; the
    computed block is the result surface.
    """

    operation: str = "config.google.sync.calc.compute"
    profile: str
    modelo: str
    revision: str
    period: str
    year: int
    spreadsheet_id: str
    metadata_match: str
    cells_read: int
    operator_edits_populated: int
    binding_edits_populated: int
    relation_edits_populated: int
    computed: list[GoogleSyncCalcComputeCasillaPayload] = []
