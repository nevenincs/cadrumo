"""The source disagreements a declaration states, and the door that lists and answers them.

A calculation that finds two sources stating different amounts for one figure
withholds its checking, export and filing until the operator answers it. The
form states each disagreement as a line that carries a finding id and the
answer it offers; the application lists the answers already given. This module
holds the TUI's side of that journey: the door a host binds to the runtime, and
the entries the screen draws by joining the form's lines with the answers.

Every sentence an entry shows is served by the application. The TUI adds only
the chrome around them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ....application.modelo.credit_resolution_contracts import (
    CreditResolutionListProjection,
    CreditResolutionMutationProjection,
    CreditResolutionRowProjection,
)
from ....application.modelo.work_form_declaration_facts import ModeloFormResolutionAnswer
from ....application.modelo.work_form_issue_lines import ModeloFormIssueLine
from ....core.external_constants import OutputLanguage
from ....domain.modelos.credit_resolution import CreditResolutionState
from ..refusal.served import ServedRefusalV1, ServedWordsV1, served_refusal


class ModeloDisagreementsDoorV1(Protocol):
    """What a host binds to one declaration so the TUI can list and answer its disagreements.

    Each method runs a registered operation to its settlement and blocks, so the
    screen calls it off the event loop. A transport failure raises the client's
    refusal; for an answer, it means the answer may have been stored.
    """

    def list_answers(self, calculation_revision_id: str, language: OutputLanguage) -> CreditResolutionListProjection:
        """Read every answer the declaration holds, active and taken back."""
        ...

    def accept(
        self, calculation_revision_id: str, finding_id: str, reason: str, language: OutputLanguage
    ) -> CreditResolutionMutationProjection:
        """Accept the amount the calculation used for one disagreement, giving the operator's reason."""
        ...

    def revoke(
        self, calculation_revision_id: str, finding_id: str, expected_revision_id: str, language: OutputLanguage
    ) -> CreditResolutionMutationProjection:
        """Take back the active answer to one disagreement, guarded by the revision it is stored at."""
        ...


@dataclass(frozen=True, slots=True)
class DisagreementEntryV1:
    """One disagreement as the screen lists it: the form's line, the answer held for it, or both.

    ``line`` is ``None`` for an answer the current form no longer states;
    ``answer`` is ``None`` for a disagreement nobody has answered yet.
    """

    finding_id: str
    line: ModeloFormIssueLine | None
    answer: CreditResolutionRowProjection | None

    @property
    def offers_accept(self) -> bool:
        """Whether the form offers to accept the amount in use for this disagreement."""
        return self.line is not None and self.line.resolution_answer is ModeloFormResolutionAnswer.ACCEPT

    @property
    def offers_revoke(self) -> bool:
        """Whether the form offers to take back an answer the application will accept taking back."""
        return (
            self.line is not None
            and self.line.resolution_answer is ModeloFormResolutionAnswer.REVOKE
            and self.answer is not None
            and self.answer.state is CreditResolutionState.ACTIVE
            and self.answer.revocable
        )


def disagreement_entries(
    lines: tuple[ModeloFormIssueLine, ...], answers: tuple[CreditResolutionRowProjection, ...]
) -> tuple[DisagreementEntryV1, ...]:
    """Join the form's disagreement lines with the answers held, then add the answers no line states.

    Lines keep the form's order. An answer with no line follows them in the
    order the application listed it.
    """
    held = {answer.finding_id: answer for answer in answers}
    stated: list[DisagreementEntryV1] = []
    seen: set[str] = set()
    for line in lines:
        finding_id = line.finding_id
        if finding_id is None or finding_id in seen:
            continue
        seen.add(finding_id)
        stated.append(DisagreementEntryV1(finding_id=finding_id, line=line, answer=held.get(finding_id)))
    unstated = [
        DisagreementEntryV1(finding_id=answer.finding_id, line=None, answer=answer)
        for answer in answers
        if answer.finding_id not in seen
    ]
    return (*stated, *unstated)


def refusal_to_show(projection: CreditResolutionMutationProjection) -> ServedRefusalV1 | None:
    """The refusal an answer came back with, as the application worded it; ``None`` when it served no words.

    The registry's own sentence for the refusal's code stands in when the
    projection carries none.
    """
    refusal = projection.refusal
    if refusal is None:
        return None
    if refusal.refusal_words is not None and refusal.refusal_words_language is not None:
        return ServedRefusalV1(
            refusal_words=ServedWordsV1(words=refusal.refusal_words, language=refusal.refusal_words_language)
        )
    return served_refusal(None, refusal_code=refusal.code)


def committed(projection: CreditResolutionMutationProjection) -> bool:
    """Whether the application stored the answer: it accepted or took back, and did not refuse."""
    return projection.outcome != "refused" and projection.resolution is not None


__all__ = [
    "DisagreementEntryV1",
    "ModeloDisagreementsDoorV1",
    "committed",
    "disagreement_entries",
    "refusal_to_show",
]
