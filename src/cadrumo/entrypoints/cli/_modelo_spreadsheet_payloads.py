"""Typed ``--json`` payload schemas for ``aeat app modelo spreadsheet``.

Each class here is a strict :class:`OutputSchema` subclass referenced as a
deferred public schema target by a production-authored CommandSpec, so the
JSON-contract suite can enumerate the whole spreadsheet surface. Validated
results enter :class:`SchemaEnvelope` through :func:`emit_envelope`.

Sequence fields use ``list`` rather than ``tuple`` because
``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.

The classes carry the CLI transport shape only. Workbook semantics stay owned
by :mod:`calc_sheets`, and the export plan by :mod:`export`.
"""

from __future__ import annotations

from typing import Literal

from ...core import CasillaId
from ...core.json_contract import OutputSchema
from ...domain.calculations.registry.ids import FormulaId, LegalRefId, RelationId, SourceRefId
from ...domain.calculations.registry.schema_base import LegalRefs, SourceRefs


class ModeloSpreadsheetPushResult(OutputSchema):
    """JSON envelope for ``aeat app modelo spreadsheet push``.

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

    operation: str = "modelo.spreadsheet.push"
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


class ModeloSpreadsheetVerifyDivergencePayload(OutputSchema):
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


class ModeloSpreadsheetVerifyResult(OutputSchema):
    """JSON envelope for ``aeat app modelo spreadsheet verify``.

    Projects the :class:`ParityReport`
    returned by
    :func:`verify_modelo_parity`.
    The payload keeps the aggregate verdict beside the divergent casilla rows
    so consumers can fail fast without discarding audit detail.
    """

    operation: str = "modelo.spreadsheet.verify"
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
    divergences: list[ModeloSpreadsheetVerifyDivergencePayload] = []


class ModeloSpreadsheetPullOperatorEditPayload(OutputSchema):
    """One populated operator casilla edit emitted by ``sync calc pull``.

    Narrows the populated
    :class:`OperatorEdit`
    subset of a :class:`PullResult`
    to the public CLI fields.
    """

    casilla_id: CasillaId
    label: str
    value: str | None = None


class ModeloSpreadsheetPullRelationEditPayload(OutputSchema):
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


class ModeloSpreadsheetCalculateCasillaPayload(OutputSchema):
    """One registry-computed casilla emitted by ``sync calc compute``.

    Mirrors a :class:`RegistryCalculationEntry`
    produced from a pulled workbook. Legal and source references are required so
    the Google Sheets compute surface keeps the same grounding contract as the
    core modelo calculation output.
    """

    casilla_id: CasillaId
    value: str
    formula_id: FormulaId | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs


class ModeloSpreadsheetPullResult(OutputSchema):
    """JSON envelope for ``aeat app modelo spreadsheet pull``.

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

    operation: str = "modelo.spreadsheet.pull"
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
    operator_edits: list[ModeloSpreadsheetPullOperatorEditPayload] = []
    binding_edits: list[dict[str, object]] = []
    relation_edits: list[ModeloSpreadsheetPullRelationEditPayload] = []
    row_set_edits_populated: int
    row_set_cells_populated: int
    assembled_groupings: list[dict[str, object]] = []
    assembled_observation_count: int
    row_set_edits: list[dict[str, object]] = []


class ModeloSpreadsheetCalculateResult(OutputSchema):
    """JSON envelope for ``aeat app modelo spreadsheet calculate``.

    Pulls operator-edited cells through
    :func:`pull_operator_edits`,
    then runs
    :func:`compute_from_pull`
    against the shared registry engine. The verb persists nothing; the
    computed block is the result surface.
    """

    operation: str = "modelo.spreadsheet.calculate"
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
    computed: list[ModeloSpreadsheetCalculateCasillaPayload] = []
