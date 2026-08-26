"""Graph-declared payload for the guided ``aeat app modelo work amend-wizard`` command.

The amendment wizard walks an operator through correcting an already-filed
return in plain language, then calls the same
:func:`~application.modelo.amend_modelo_revision` composition path
:mod:`~entrypoints.cli._modelo`'s ``work amend`` verb uses. This module documents the JSON
transport shape only; the wizard's step-by-step prompting and amendment
delegation live in :mod:`~entrypoints.cli._modelo_amend_wizard_cli`. Every payload here is an
:class:`OutputSchema` subclass referenced on the JSON-contract surface.
"""

from __future__ import annotations

from pydantic import Field

from cadrumo.domain.calculations.registry.ids import LegalRefId, SourceRefId

from ...core import CasillaId
from ...core.identity import FilingRecordId
from ...core.json_contract import OutputSchema
from ...domain.modelos import CalculationRevisionAmendmentKind, M303RectificativaMotive
from ._modelo_payloads import ModeloRecordPayload


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


class WorkAmendWizardResult(ModeloRecordPayload):
    """Successful ``aeat app modelo work amend-wizard`` result payload.

    Derives from the canonical :class:`ModeloRecordPayload` (the same
    projection ``work amend`` and every other filing-record surface use)
    instead of redeclaring its identity, timestamp, and lifecycle fields as
    bare strings: an out-of-range filing year, a malformed timestamp, an
    unknown status/kind, or an oversized notes string is refused rather than
    accepted. Adds the wizard-specific ``corrected_casillas`` audit trail;
    the amendment wizard never writes a fichero-BOE itself.
    ``amends_filing_record_id`` is narrowed to required: every amendment
    wizard result amends a prior filing record by definition.
    """

    operation: str = "modelo.work.amend_wizard"
    amendment_kind: CalculationRevisionAmendmentKind
    m303_rectificativa_motive: M303RectificativaMotive | None
    amendment_reason: str = Field(min_length=1, max_length=500)
    amends_filing_record_id: FilingRecordId
    corrected_casillas: tuple[AmendWizardCorrectedCasillaPayload, ...] = ()


__all__ = ["AmendWizardCorrectedCasillaPayload", "WorkAmendWizardResult"]
