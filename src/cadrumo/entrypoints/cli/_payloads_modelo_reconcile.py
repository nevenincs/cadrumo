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

from ...application.modelo._taxation_comparison import TaxationRecommendation
from ...application.modelo.reconciliation_records import (
    ModeloReconciliationDiffKind,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
)
from ...core.modelo import Modelo
from ...core.filing_year import FilingYear
from ...core.identity import BucketId, WorkUnitId
from ...core.json_contract import OutputSchema
from ...core.text_bounds import NonEmptyStr
from ...domain.calculations.registry.ids import LegalRefId, SourceRefId
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
    ``source_refs`` carry the registry ref types the canonical diff declares,
    so the published contract states the citation shape an operator is meant
    to resolve rather than promising bare text.

    That a ``total`` or ``casilla`` diff must actually CARRY grounding — and
    that a ``header_field`` diff carries none, comparing filing identity rather
    than a regulated amount — is enforced on
    :class:`ModeloReconciliationDiff` and is
    deliberately not restated here. Unlike the shapes above, that rule governs
    what the reconciler may record, not what this transport may emit: every row
    is projected field-by-field from a diff that has already satisfied it, and
    a second copy could only drift from the registry reason behind it.
    """

    field_name: NonEmptyStr
    work_unit_value: str = ""
    evidence_value: str = ""
    kind: NonEmptyStr
    diff_kind: ModeloReconciliationDiffKind = ModeloReconciliationDiffKind.HEADER_FIELD
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()


class ModeloReconcileResult(OutputSchema):
    """Result payload for ``modelo reconcile import`` and ``modelo reconcile pull``.

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
    # Same bound the canonical :class:`~WorkUnit` declares, so a
    # transport row cannot carry a filing year the work unit itself refuses.
    filing_year: FilingYear
    modelo: Modelo
    revision: NonEmptyStr
    conjunta_cuota_resultante: DecimalWireText
    individual_cuota_resultante: DecimalWireText
    conjunta_resultado: DecimalWireText
    individual_resultado: DecimalWireText
    delta_resultado: DecimalWireText
    recommendation: TaxationRecommendation
    recommendation_reason: NonEmptyStr

    # Scope of the individual branch, not an incidental diagnostic: it states
    # which households the figure above is valid for, so a machine consumer
    # cannot read the individual result as authoritative without it. The
    # operator-facing caveat PROSE stays on the envelope ``notices`` channel per
    # ``aeat-cli-contract``; this is the structured
    # flag that channel's text describes.
    individual_branch_single_earner_only: bool
