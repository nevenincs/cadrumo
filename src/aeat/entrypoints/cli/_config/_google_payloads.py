"""Typed ``--json`` payload schemas for google config CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every google-config command surface this module covers.

Field sets match the production payload dicts constructed in ``_google.py``
at their emit sites. All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.
"""

from __future__ import annotations

from pydantic import Field

from ....domain.calculations.registry import CasillaId, FormulaId, LegalRefId, SourceRefId
from .._schemas import OutputSchema, register_schema


@register_schema("config.google.register")
class GoogleRegisterResult(OutputSchema):
    """JSON envelope for ``aeat config google register``."""

    operation: str = "config.google.register"
    profile: str
    client_id: str
    project_id: str


@register_schema("config.google.login")
class GoogleLoginResult(OutputSchema):
    """JSON envelope for ``aeat config google login``."""

    operation: str = "config.google.login"
    profile: str
    mode: str
    account_email: str
    granted_scopes: list[str] = []


@register_schema("config.google.status")
class GoogleStatusResult(OutputSchema):
    """JSON envelope for ``aeat config google status``."""

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
    """JSON envelope for ``aeat config google logout``."""

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
    """JSON envelope for ``aeat config google folder set``."""

    operation: str = "config.google.folder.set"
    profile: str
    root_folder_id: str


@register_schema("config.google.folder.get")
class GoogleFolderGetResult(OutputSchema):
    """JSON envelope for ``aeat config google folder get``."""

    operation: str = "config.google.folder.get"
    profile: str
    configured: bool
    root_folder_id: str | None = None


# ---------------------------------------------------------------------------
# Drive sync sub-app
# ---------------------------------------------------------------------------


@register_schema("config.google.sync.probe")
class GoogleSyncProbeResult(OutputSchema):
    """JSON envelope for ``aeat config google sync probe``."""

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
    """One failed mirror object in a sync push report."""

    namespace: str
    hmac: str
    error: str


class GoogleSyncFailedManifestPayload(OutputSchema):
    """One failed namespace manifest in a sync push report."""

    namespace: str
    error: str


class GoogleSyncDegradedManifestPayload(OutputSchema):
    """One degraded namespace manifest repaired during a sync push."""

    namespace: str
    detail: str


@register_schema("config.google.sync.push")
class GoogleSyncPushResult(OutputSchema):
    """JSON envelope for ``aeat config google sync push``."""

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
    """JSON envelope for ``aeat config google sync calc export``."""

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
    """One divergence row in a calc verify report."""

    casilla_id: CasillaId
    label: str
    local: str | None = None
    sheets: str | None = None
    aeat: str | None = None


@register_schema("config.google.sync.calc.verify")
class GoogleSyncCalcVerifyResult(OutputSchema):
    """JSON envelope for ``aeat config google sync calc verify``."""

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
    """One populated operator casilla edit emitted by ``sync calc pull``."""

    casilla_id: CasillaId
    label: str
    value: str | None = None


class GoogleSyncCalcComputeCasillaPayload(OutputSchema):
    """One computed casilla emitted by ``sync calc compute``."""

    casilla_id: CasillaId
    value: str
    formula_id: FormulaId | None = None
    legal_refs: list[LegalRefId] = Field(min_length=1)
    source_refs: list[SourceRefId] = Field(min_length=1)


@register_schema("config.google.sync.calc.pull")
class GoogleSyncCalcPullResult(OutputSchema):
    """JSON envelope for ``aeat config google sync calc pull``.

    The payload composes pull metadata, populated operator/binding/relation
    edits, and optional row-set assemblies. Casilla-bearing rows are typed
    so the CLI cannot emit anonymous string casilla references at this
    boundary. Computing casilla values from the pulled edits is a separate
    verb (``sync calc compute``); this transport payload carries no computed
    block.
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

    Pulls operator-edited cells from a calc-sheets workbook, runs the shared
    registry engine over them, and emits the computed casilla values. The
    verb persists nothing; the computed block is the result surface.
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
