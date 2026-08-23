"""Typed ``--json`` payload schemas for Google config CLI commands.

Each class declared here is a strict
:class:`OutputSchema` subclass and is referenced as a deferred public schema
target by production-authored CommandSpec so the
JSON-contract test suite can enumerate every google-config command surface this
module covers. Validated results enter
:class:`SchemaEnvelope` through
:func:`_emit_envelope`.

Field sets match the production payload dicts constructed in ``_google.py``,
``_google_folder.py``, and ``_google_sync_calc.py`` at their emit sites. All
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
    :mod:`_google_sync_calc`
        Google Sheets export, pull, verify, and compute emit sites.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ....adapters.outbound.storage import ProviderKind
from ....core import CasillaId
from ....core.json_contract import OutputSchema
from ....domain.calculations.registry import FormulaId, LegalRefId, RelationId, SourceRefId


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


# ---------------------------------------------------------------------------
# Drive sync calc sub-app
# ---------------------------------------------------------------------------


class GoogleSyncCalcExportResult(OutputSchema):
    """JSON envelope for ``aeat config google sync calc export``.

    Projects :class:`CalcSheetsApplyResult`
    after :func:`build_export_plan` creates
    the pure :class:`SheetExportPlan` and
    :func:`apply_export_plan`
    materialises it in Google Sheets.

    ``dry_run=True`` projects :class:`CalcSheetsExportPreview`
    from :func:`preview_export_plan` instead: Drive and Sheets are read but
    never written. ``folder_id``, ``spreadsheet_id`` and ``spreadsheet_url``
    are ``None`` only on a preview against a target that does not exist yet —
    the first export for a modelo, period and year has nothing to look up.
    ``ranges_to_clear``, ``value_cells_changed`` and ``value_cells_unchanged``
    are populated on a preview only: a real apply rewrites every cell the plan
    carries unconditionally rather than diffing against current content, so
    those fields carry no meaning there.
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
    dry_run: bool = False
    spreadsheet_exists: bool | None = None
    folder_id: str | None = None
    spreadsheet_id: str | None = None
    spreadsheet_url: str | None = None
    value_cells_written: int
    formula_cells_written: int
    protected_ranges_written: int
    tab_count: int
    ranges_to_clear: list[str] = []
    value_cells_changed: int | None = None
    value_cells_unchanged: int | None = None
    formula_cells_to_write: int | None = None


class GoogleSyncCalcVerifyDivergencePayload(OutputSchema):
    """One divergent casilla row in a calc verify report.

    Mirrors a :class:`CasillaParity`
    row where local Decimal output, Google Sheets output, and optionally the
    AEAT oracle do not all agree.
    """

    casilla_id: CasillaId
    label: str
    local: str | None = None
    sheets: str | None = None
    aeat: str | None = None


class GoogleSyncCalcVerifyResult(OutputSchema):
    """JSON envelope for ``aeat config google sync calc verify``.

    Projects the :class:`ParityReport`
    returned by
    :func:`verify_modelo_parity`.
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
    :class:`OperatorEdit`
    subset of a :class:`PullResult`
    to the public CLI fields.
    """

    casilla_id: CasillaId
    label: str
    value: str | None = None


class GoogleSyncCalcPullRelationEditPayload(OutputSchema):
    """One populated relation edit emitted by ``sync calc pull``, with its grounding.

    The pull adapter recovers a relation's provenance, source modelo / filing
    year / periods / casillas, legal and source references, and resolution
    instant from the workbook's developer metadata. This surface emitted only
    ``{relation, value}``, so every one of those recovered facts was discarded
    AFTER a typed pull had already established them — a number reaching the
    operator with nothing saying where it came from, when the same value can
    be a local filing's carry, a live AEAT read, or a hand edit, and only the
    provenance tells them apart.

    Typed rather than a ``dict[str, object]`` bag so the transport contract is
    introspectable and a future field cannot be dropped silently.
    ``provenance`` and ``resolved_at`` stay optional because a relation edited
    in the workbook without an apply round-trip genuinely carries neither.
    """

    relation: RelationId
    value: str | None = None
    provenance: Literal["local_filing", "aeat_live", "operator_manual"] | None = None
    source_modelo: str | None = None
    source_filing_year: int | None = None
    source_periods: list[str] = []
    source_casilla_ids: list[CasillaId] = []
    legal_refs: list[LegalRefId] = []
    source_refs: list[SourceRefId] = []
    resolved_at: str | None = None


class GoogleSyncCalcComputeCasillaPayload(OutputSchema):
    """One registry-computed casilla emitted by ``sync calc compute``.

    Mirrors a :class:`RegistryCalculationEntry`
    produced from a pulled workbook. Legal and source references are required so
    the Google Sheets compute surface keeps the same grounding contract as the
    core modelo calculation output.
    """

    casilla_id: CasillaId
    value: str
    formula_id: FormulaId | None = None
    legal_refs: list[LegalRefId] = Field(min_length=1)
    source_refs: list[SourceRefId] = Field(min_length=1)


class GoogleSyncCalcPullResult(OutputSchema):
    """JSON envelope for ``aeat config google sync calc pull``.

    Projects the :class:`PullResult`
    returned by
    :func:`pull_operator_edits`.
    The payload composes
    :class:`PullMetadata`, the
    :class:`MetadataMatchState`,
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
    relation_edits: list[GoogleSyncCalcPullRelationEditPayload] = []
    row_set_edits_populated: int
    row_set_cells_populated: int
    assembled_groupings: list[dict[str, object]] = []
    assembled_observation_count: int
    row_set_edits: list[dict[str, object]] = []


class GoogleSyncCalcComputeResult(OutputSchema):
    """JSON envelope for ``aeat config google sync calc compute``.

    Pulls operator-edited cells through
    :func:`pull_operator_edits`,
    then runs
    :func:`compute_from_pull`
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
