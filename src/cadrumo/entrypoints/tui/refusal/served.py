"""A refusal as the backend serves it, and its ways out in served order.

The TUI words none of this. The verdict snapshot names the actions and
carries the words and target operations served for each of them, and the
sentence saying there is no way out; the refusal sentence comes from the
backend beside it. This module reads them from the snapshot and invents none.

:func:`served_refusal` is the one place a recorded stop becomes a served
refusal, whatever surface shows it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from ....application.operations.error_detail import (
    OperationErrorDetailKind,
    OperationErrorDetailV1,
    operation_catalogue_refusal_words,
    served_words_language,
)
from ....application.operator_actions.projection import ActionArgumentSnapshot, PreconditionVerdictSnapshot
from ....core.errors.error_codes import declared_error_codes_by_qualname, get_registered_error_code_by_code
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.identifier_grammar import NamespacedId
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.operator_action_enums import ActionConditionality

type RefusalWayRoleV1 = Literal["primary", "alternative"]


class ServedWordsV1(BaseModel):
    """One finished sentence the backend served and the language it is in."""

    model_config = STRICT_FROZEN_CONFIG

    words: Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
    language: OutputLanguage


class ServedRefusalV1(BaseModel):
    """What a refusal panel is given: the served refusal sentence and the verdict that settled the refusal.

    The verdict carries the words served for each way out and the sentence
    served for a refusal with no way out.
    """

    model_config = STRICT_FROZEN_CONFIG

    refusal_words: ServedWordsV1 | None = None
    verdict: PreconditionVerdictSnapshot | None = None

    @property
    def no_recovery_words(self) -> ServedWordsV1 | None:
        """The sentence the verdict served for a refusal with no way out, when it served one."""
        verdict = self.verdict
        if verdict is None or verdict.no_recovery_outcome is None:
            return None
        return _served(verdict.no_recovery_words, verdict.no_recovery_words_language)

    @property
    def sentence(self) -> str | None:
        """The served refusal sentence alone, for a surface that can show only one line of text."""
        return None if self.refusal_words is None else self.refusal_words.words


@dataclass(frozen=True, slots=True)
class RefusalWayV1:
    """One served way out of a refusal, with the words served for it when there are any."""

    role: RefusalWayRoleV1
    action_id: NamespacedId
    argument_bindings: tuple[ActionArgumentSnapshot, ...]
    missing_argument_names: tuple[str, ...]
    conditionality: ActionConditionality
    words: ServedWordsV1 | None
    target_operation_ids: tuple[str, ...]

    @property
    def conditional(self) -> bool:
        """Whether the action was served as needing arguments before it can run."""
        return self.conditionality is ActionConditionality.REQUIRES_ARGUMENTS or bool(self.missing_argument_names)


def _served(words: str | None, language: OutputLanguage | None) -> ServedWordsV1 | None:
    """The words a snapshot served, bound to their language, or ``None`` when it served none."""
    if words is None or language is None:
        return None
    return ServedWordsV1(words=words, language=language)


def refusal_ways(refusal: ServedRefusalV1) -> tuple[RefusalWayV1, ...]:
    """Return the primary way out, then the alternatives exactly as served.

    Never sorted, filtered or deduplicated; none at all beside a no-recovery
    outcome, which is shown only as its served words.
    """
    verdict = refusal.verdict
    if verdict is None or verdict.no_recovery_outcome is not None:
        return ()
    ways: list[RefusalWayV1] = []
    if verdict.action_id is not None:
        ways.append(
            RefusalWayV1(
                role="primary",
                action_id=verdict.action_id,
                argument_bindings=verdict.argument_bindings,
                missing_argument_names=verdict.missing_argument_names,
                conditionality=verdict.conditionality,
                words=_served(verdict.action_words, verdict.action_words_language),
                target_operation_ids=verdict.target_operation_ids,
            )
        )
    for alternative in verdict.alternative_actions:
        ways.append(
            RefusalWayV1(
                role="alternative",
                action_id=alternative.action_id,
                argument_bindings=alternative.argument_bindings,
                missing_argument_names=alternative.missing_argument_names,
                conditionality=alternative.conditionality,
                words=_served(alternative.action_words, alternative.action_words_language),
                target_operation_ids=alternative.target_operation_ids,
            )
        )
    return tuple(ways)


def _recorded_words(detail: OperationErrorDetailV1) -> ServedWordsV1 | None:
    """The sentence the detail served, or for a detail recorded before sentences were served, its error's own."""
    if detail.refusal_words is not None and detail.refusal_words_language is not None:
        return ServedWordsV1(words=detail.refusal_words, language=detail.refusal_words_language)
    if detail.kind is not OperationErrorDetailKind.REGISTERED_ERROR or detail.error_code is None:
        return None
    key = detail.message_key or get_registered_error_code_by_code(detail.error_code).message_key
    words, language = operation_catalogue_refusal_words(detail.error_code, key, detail.context_mapping())
    return ServedWordsV1(words=words, language=language)


def _registry_words(refusal_code: str) -> ServedWordsV1 | None:
    """The registry's public sentence for a refusal code, when the registry declares one.

    A settled refusal that recorded no detail keeps only its code, so only a
    code whose registered message is itself the public sentence can be worded.
    """
    for error_code in declared_error_codes_by_qualname().values():
        if error_code.code == refusal_code and error_code.public_message_from_registry:
            language = served_words_language()
            return ServedWordsV1(words=tr(error_code.message_key, locale=language.value), language=language)
    return None


def served_refusal(detail: OperationErrorDetailV1 | None, *, refusal_code: str | None = None) -> ServedRefusalV1 | None:
    """Return the refusal a stopped operation or act served, or ``None`` when it served nothing to show.

    The sentence is the one the detail served; without a detail it is the
    registry's public sentence for ``refusal_code``, when there is one. The
    verdict is the one the detail recorded, so its ways out are the served ones.
    """
    words: ServedWordsV1 | None = None
    verdict: PreconditionVerdictSnapshot | None = None
    if detail is not None:
        words = _recorded_words(detail)
        recorded = detail.precondition_verdict()
        verdict = None if recorded is None else PreconditionVerdictSnapshot.from_verdict(recorded)
    if words is None and refusal_code is not None:
        words = _registry_words(refusal_code)
    if words is None and verdict is None:
        return None
    return ServedRefusalV1(refusal_words=words, verdict=verdict)


__all__ = [
    "RefusalWayRoleV1",
    "RefusalWayV1",
    "ServedRefusalV1",
    "ServedWordsV1",
    "refusal_ways",
    "served_refusal",
]
