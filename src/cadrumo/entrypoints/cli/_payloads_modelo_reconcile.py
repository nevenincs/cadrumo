"""Typed payload schemas for modelo reconciliation and taxation comparison.

Every declared payload is a
:class:`OutputSchema` subclass referenced by
CommandSpec schema authority for the modelo
reconciliation and taxation-comparison JSON-contract surface. The application
facade remains authoritative for
:class:`ModeloReconciliationReport` and
:class:`TaxationComparisonResult`; this module only
documents the CLI transport shape that enters
:class:`SchemaEnvelope` through
:func:`emit_envelope`. The parent :mod:`_modelo_payloads` module re-exports
these split schemas so modelo emitters keep one payload import surface.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import Field

from ...application.modelo._taxation_comparison import TaxationRecommendation
from ...application.modelo.reconciliation_records import (
    ModeloReconciliationDiffKind,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
)
from ...core import Modelo
from ...core.identity import BucketId, WorkUnitId
from ...core.json_contract import OutputSchema
from ._decimal_wire import DecimalWireText


class ModeloReconciliationDiffPayload(OutputSchema):
    """One disagreement surfaced in a reconciliation report.

    Nested in :class:`ModeloReconcileResult` and projects
    :class:`ModeloReconciliationDiff`. Justificante
    reconciliation compares header evidence (modelo, period, ejercicio, tax id)
    and, where the revision declares ``reconciliation_total_casilla_ids``, the
    filed total against the canonical computed result casilla. ``diff_kind`` is
    the closed :class:`ModeloReconciliationDiffKind` category; a ``total`` diff
    carries the reconciling expectation's ``legal_refs`` / ``source_refs``.
    Individual casilla declaration diffs require the modelo-specific
    declaration parser (``diff_kind = casilla`` is reserved). ``legal_refs`` /
    ``source_refs`` stay unconstrained tuples, exactly as the canonical diff
    declares: a ``header_field`` diff carries none by design.
    """

    field_name: str = Field(min_length=1)
    work_unit_value: str = ""
    evidence_value: str = ""
    kind: str = Field(min_length=1)
    diff_kind: ModeloReconciliationDiffKind = ModeloReconciliationDiffKind.HEADER_FIELD
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


class ModeloReconcileResult(OutputSchema):
    """Result payload for ``modelo reconcile file`` and ``modelo reconcile pull``.

    Both verbs share
    :class:`ModeloReconciliationReport` from
    :func:`modelo_reconcile` or :func:`modelo_reconcile_bytes`: a work-unit-level
    :obj:`WorkUnitId`, :obj:`BucketId` scope, :class:`ModeloReconciliationVerdict`,
    :class:`ModeloReconciliationEvidenceKind`, evidence path/reference,
    :class:`ModeloReconciliationDiffPayload` list, an aware ``reconciled_at``
    timestamp, and optional narrative. Non-blocking reconciliation advisories
    ride the shared envelope ``notices`` channel exclusively
    (``aeat-cli-contract``); this result carries no
    bespoke advisory field.
    """

    work_unit_id: WorkUnitId
    bucket_id: BucketId
    source_kind: ModeloReconciliationEvidenceKind
    source_path: str
    verdict: ModeloReconciliationVerdict
    diffs: tuple[ModeloReconciliationDiffPayload, ...] = ()
    reconciled_at: datetime
    narrative: str = ""


class WorkCompareTaxationResult(OutputSchema):
    """Result payload for ``aeat app modelo work compare-taxation``.

    Projects :class:`TaxationComparisonResult` returned
    by :func:`compare_taxation_for_work_address`. It surfaces the
    semantic-role-selected cuota resultante de la autoliquidación and cuota
    diferencial / resultado for both conjunta and individual filing modes, plus
    the signed delta and
    :class:`TaxationRecommendation`.
    """

    operation: str = "modelo.work.compare_taxation"
    # Same bound the canonical :class:`~domain.modelos.WorkUnit` declares, so a
    # transport row cannot carry a filing year the work unit itself refuses.
    filing_year: Annotated[int, Field(ge=2000, le=2099)]
    modelo: Modelo
    revision: str = Field(min_length=1)
    conjunta_cuota_resultante: DecimalWireText
    individual_cuota_resultante: DecimalWireText
    conjunta_resultado: DecimalWireText
    individual_resultado: DecimalWireText
    delta_resultado: DecimalWireText
    recommendation: TaxationRecommendation
    recommendation_reason: str = Field(min_length=1)

    # Scope of the individual branch, not an incidental diagnostic: it states
    # which households the figure above is valid for, so a machine consumer
    # cannot read the individual result as authoritative without it. The
    # operator-facing caveat PROSE stays on the envelope ``notices`` channel per
    # ``aeat-cli-contract``; this is the structured
    # flag that channel's text describes.
    individual_branch_single_earner_only: bool
