"""Payload for the guided ``aeat app modelo work wizard`` command.

The wizard walks an operator through a work unit's outstanding manual-input
casillas and bindings/relations in plain language, then calls the same
:func:`~application.modelo.calculate_modelo_work_revision` composition
path :mod:`_modelo_work_calculate_cli` uses. This module documents the JSON
transport shape only; the wizard's step-by-step prompting and calculation
delegation live in :mod:`_modelo_work_wizard_cli`. Every payload here is an
:class:`OutputSchema` subclass exposed through the command specification.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ...core import CasillaId
from ...core.json_contract import OutputSchema
from ...core.text_bounds import NonEmptyStr
from ...domain.calculations.registry.ids import LegalRefId, SourceRefId
from ._modelo_revision_payload_parts import CalculationRevisionCommandProjectionFields

#: Closed set of CLI input channels a wizard step resolves to: a direct
#: ``--casilla`` override, a registry ``--binding`` override, or a
#: ``--relation`` override.
WizardPromptChannel = Literal["casilla", "binding", "relation"]


class WizardPromptedCasillaPayload(OutputSchema):
    """One manual-input casilla the wizard prompted for, with the answer given.

    Carries the same grounding parity (``legal_refs`` / ``source_refs``) the
    ``casilla`` discovery command exposes -- required, non-empty, exactly as
    :class:`~cadrumo.domain.calculations.registry.CasillaDefinition` requires
    -- so a scripted or JSON-mode caller can audit exactly what was asked and
    what was answered, without needing a live terminal.
    """

    casilla_id: CasillaId
    number: str
    label: NonEmptyStr
    channel: WizardPromptChannel
    """Either ``casilla`` (a direct ``--casilla`` override) or ``binding``/``relation``."""
    key: NonEmptyStr
    """The ``--casilla`` / ``--binding`` / ``--relation`` key supplied to the calculation."""
    value: NonEmptyStr
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    help_text: str | None = None


class WorkWizardResult(CalculationRevisionCommandProjectionFields):
    """Successful ``aeat app modelo work wizard`` result payload.

    Mirrors the shape of :class:`~entrypoints.cli._modelo_payloads.WorkCalculateResult`
    (the wizard composes the exact same calculation path, and both share the
    compact persisted-revision projection) plus the
    ``prompted_casillas`` audit trail of what the wizard asked and what the
    operator (or the scripted answer queue) supplied.
    """

    operation: str = "modelo.work.wizard"
    saved: bool = True
    saved_confirmation: str
    prompted_casillas: tuple[WizardPromptedCasillaPayload, ...] = ()


__all__ = ["WizardPromptedCasillaPayload", "WorkWizardResult"]
