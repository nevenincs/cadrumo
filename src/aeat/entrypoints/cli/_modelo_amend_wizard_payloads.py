"""Registered payload for the guided ``aeat app modelo work amend-wizard`` command.

The amendment wizard walks an operator through correcting an already-filed
return in plain language, then calls the same
:func:`~application.modelo.amend_modelo_revision` composition path
:mod:`_modelo.py`'s ``work amend`` verb uses. This module documents the JSON
transport shape only; the wizard's step-by-step prompting and amendment
delegation live in :mod:`_modelo_amend_wizard_cli`. Every payload here is an
:class:`OutputSchema` subclass registered on the JSON-contract surface.
"""

from __future__ import annotations

from ...core import Period
from ...core.identity import BucketId
from ...domain.calculations.registry import CasillaId, LegalRefId, SourceRefId
from ...domain.modelos import CalculationRevisionId, FilingRecordId, WorkUnitId
from ._modelo_payloads import ExternalEvidencePayload
from ._schemas import OutputSchema, register_schema


class AmendWizardCorrectedCasillaPayload(OutputSchema):
    """One casilla the operator corrected, with its baseline and new value.

    Carries the same grounding parity (``legal_refs`` / ``source_refs``) the
    ``casilla`` discovery command exposes, so a scripted or JSON-mode caller
    can audit exactly which casillas changed and why, without needing a live
    terminal.
    """

    casilla_id: CasillaId
    number: str
    label: str
    previous_value: str
    corrected_value: str
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()


@register_schema("modelo.work.amend_wizard")
class WorkAmendWizardResult(OutputSchema):
    """Successful ``aeat app modelo work amend-wizard`` result payload.

    Mirrors the shape of ``WorkAmendResult`` (the wizard composes the exact
    same :func:`~application.modelo.amend_modelo_revision` path) plus the
    ``corrected_casillas`` audit trail of what the wizard asked and what the
    operator (or the scripted answer queue) supplied, and an
    ``export_next_action`` pointer to the existing ``modelo export`` verb —
    the amendment wizard never writes a fichero-BOE itself.
    """

    operation: str = "modelo.work.amend_wizard"
    amendment_kind: str
    amendment_reason: str
    amends_filing_record_id: FilingRecordId
    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    filed_at: str
    filed_by: str
    notes: str | None = None
    aeat_accepted: bool | None = None
    status: str
    superseded_at: str | None = None
    superseded_by_filing_record_id: FilingRecordId | None = None
    external_evidence: ExternalEvidencePayload | None = None
    kind: str = "internal_filing"
    live_submission: bool = False
    corrected_casillas: tuple[AmendWizardCorrectedCasillaPayload, ...] = ()
    export_next_action: str


__all__ = ["AmendWizardCorrectedCasillaPayload", "WorkAmendWizardResult"]
