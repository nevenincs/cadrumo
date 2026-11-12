"""What an export says about the limits its calculation disclosed, in the filer's words.

The verification of the exported revision marks a finding as a disclosed
limitation when the calculation leaves a figure out, or rests on a value the
filer stated, and says so. An export carries the file as calculated, so its
result serves those findings' sentences beside the file: a frontend renders
them and authors none. The marker alone decides which findings are served; no
list of finding codes does.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.modelos.verification_report import VerificationReportCatalogue
from .finding_message_text import finding_message_text

_LEAD_LOCALE_KEY = "application.modelo.export_disclosure.lead"


class ModeloExportDisclosedLimitation(BaseModel):
    """One disclosed limitation of the exported calculation, as its verification worded it."""

    model_config = STRICT_FROZEN_CONFIG

    #: The finding's catalogue key, so a frontend can tell the limitations apart without parsing words.
    message_locale_key: str = Field(min_length=1)
    #: The box the finding concerns; ``None`` when it concerns the declaration as a whole.
    casilla_id: CasillaId | None = None
    #: The finding's sentence in the language the export was asked in.
    words: str = Field(min_length=1)


class ModeloExportDisclosure(BaseModel):
    """The disclosed limitations an export carries, with the sentence that introduces them."""

    model_config = STRICT_FROZEN_CONFIG

    #: One sentence saying that the export carries the limits below as they are.
    lead_words: str = Field(min_length=1)
    limitations: tuple[ModeloExportDisclosedLimitation, ...] = Field(min_length=1)


def export_disclosure(
    reports: VerificationReportCatalogue,
    *,
    calculation_revision_id: CalculationRevisionId,
    language: OutputLanguage,
) -> ModeloExportDisclosure | None:
    """Serve the disclosed limitations of the revision's latest verification, or ``None`` when it states none.

    A revision never verified discloses nothing here: the export gates decide
    whether it may be exported at all, and this reports only what a
    verification found.
    """
    runs = reports.for_calculation_revision(calculation_revision_id)
    if not runs:
        return None
    limitations = tuple(
        ModeloExportDisclosedLimitation(
            message_locale_key=finding.message_locale_key,
            casilla_id=finding.casilla_id,
            words=finding_message_text(finding, language),
        )
        for finding in runs[-1].findings
        if finding.disclosed_limitation
    )
    if not limitations:
        return None
    return ModeloExportDisclosure(lead_words=tr(_LEAD_LOCALE_KEY, locale=language.value), limitations=limitations)


__all__ = [
    "ModeloExportDisclosedLimitation",
    "ModeloExportDisclosure",
    "export_disclosure",
]
