"""Registered payload for the guided ``aeat app modelo work amend-wizard`` command.

The amendment wizard walks an operator through correcting an already-filed
return in plain language, then calls the same
:func:`~aeat.application.modelo.amend_modelo_revision` composition path
:mod:`_modelo.py`'s ``work amend`` verb uses. This module documents the JSON
transport shape only; the wizard's step-by-step prompting and amendment
delegation live in :mod:`_modelo_amend_wizard_cli`.
"""

from __future__ import annotations

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
    same :func:`~aeat.application.modelo.amend_modelo_revision` path) plus the
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
    bucket_id: str
    modelo: str
    filing_year: int
    period: str
    filed_at: str
    filed_by: str
    status: str
    external_evidence: ExternalEvidencePayload | None = None
    corrected_casillas: tuple[AmendWizardCorrectedCasillaPayload, ...] = ()
    export_next_action: str


__all__ = ["AmendWizardCorrectedCasillaPayload", "WorkAmendWizardResult"]
