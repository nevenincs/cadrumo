"""The refusal of a document read for want of consent to send it off this computer, and what it serves.

The agent service refuses a run with ``consent_missing`` when the role's model
runs off-host and the read carries no consent. Neither the document nor the
reader is at fault, so the refusal says what it is and serves the two remedies
as typed kinds: authorise the off-host read, or switch the role to a model that
runs on this computer. Whether a surface can offer each is the surface's own
knowledge; the backend serves the kinds and their words and nothing else.
"""

from __future__ import annotations

from typing import Final

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ..operations.next_step import (
    OperationNextStepWording,
    OperationOffHostConsentRemedyV1,
    OperationResolveOffHostConsentStepV1,
)
from ..operator_actions.models import PreconditionVerdict
from .evidence_errors import LedgerOffHostConsentRequiredError
from .preconditions import LedgerPreconditionCondition

__all__ = ["OFF_HOST_CONSENT_REQUIRED_LOCALE_KEY", "off_host_consent_required", "off_host_consent_step"]

OFF_HOST_CONSENT_REQUIRED_LOCALE_KEY: Final = "errors.refused.refused_llm_consent"
"""The refusal sentence: the read was refused because off-host transmission has no consent."""

_RESOLVE_STEP_LOCALE_KEY: Final = "application.ledger.evidence.next_step.resolve_off_host_consent"
_AUTHORISE_LOCALE_KEY: Final = "application.ledger.evidence.next_step.authorise_off_host"
_SWITCH_LOCALE_KEY: Final = "application.ledger.evidence.next_step.switch_to_local_lane"
_AUTHORISE_UNAVAILABLE_LOCALE_KEY: Final = "application.ledger.evidence.next_step.authorise_off_host_unavailable"
_SWITCH_UNAVAILABLE_LOCALE_KEY: Final = "application.ledger.evidence.next_step.switch_to_local_lane_unavailable"


def off_host_consent_step() -> OperationNextStepWording:
    """The step that offers both remedies, worded in the language of the refusal's own sentence."""

    def worded(language: OutputLanguage) -> OperationResolveOffHostConsentStepV1:
        return OperationResolveOffHostConsentStepV1(
            words=tr(_RESOLVE_STEP_LOCALE_KEY, locale=language.value),
            remedies=(
                OperationOffHostConsentRemedyV1(
                    kind="authorise_off_host",
                    words=tr(_AUTHORISE_LOCALE_KEY, locale=language.value),
                    unavailable_words=tr(_AUTHORISE_UNAVAILABLE_LOCALE_KEY, locale=language.value),
                ),
                OperationOffHostConsentRemedyV1(
                    kind="switch_to_local_lane",
                    words=tr(_SWITCH_LOCALE_KEY, locale=language.value),
                    unavailable_words=tr(_SWITCH_UNAVAILABLE_LOCALE_KEY, locale=language.value),
                ),
            ),
        )

    return worded


def off_host_consent_required(verdict: PreconditionVerdict) -> LedgerOffHostConsentRequiredError:
    """The ledger refusal carrying the agent's own verdict and the two remedies."""
    return LedgerOffHostConsentRequiredError(
        LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE.value,
        translated_message=OFF_HOST_CONSENT_REQUIRED_LOCALE_KEY,
        precondition_verdict=verdict,
        next_step=off_host_consent_step(),
    )
