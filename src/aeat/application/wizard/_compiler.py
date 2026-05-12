"""Pure projection of the wizard descriptor catalogue into the legacy
``PROFILE_KEYS`` registry shape.

``compile_profile_keys`` walks every :class:`WizardFlow` in the
catalogue, emits one :class:`ProfileKey` per distinct
``WizardQuestion.profile_key``, and derives the requirement flag plus
the conditional `required_when_*` pair from the question's
``required`` and ``visible_when`` declarations. The function is
import-time pure: it performs no file I/O, no environment lookups,
and no side effects, so :data:`PROFILE_KEYS` can be assigned to its
output at module-load time.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...core.i18n import Translatable
from ...domain.profile._keys import ProfileKey, ProfileKeyRequirement
from ._errors import WizardCompileError
from ._models import WizardCondition, WizardFlow, WizardQuestion


def compile_profile_keys(flows: Sequence[WizardFlow]) -> tuple[ProfileKey, ...]:
    """Project the wizard catalogue into the legacy ``PROFILE_KEYS`` shape.

    Args:
        flows: The wizard catalogue to walk.

    Returns:
        A tuple of :class:`ProfileKey` records, one per distinct
        ``WizardQuestion.profile_key``. None-bound questions are
        skipped.

    Raises:
        WizardCompileError: When two profile-bound questions across the
            catalogue declare the same ``profile_key``.
    """

    by_id: dict[str, WizardQuestion] = {}
    for flow in flows:
        for section in flow.sections:
            for question in section.questions:
                by_id[question.id] = question

    keys: dict[str, ProfileKey] = {}
    for flow in flows:
        for section in flow.sections:
            for question in section.questions:
                if question.profile_key is None:
                    continue
                if question.profile_key in keys:
                    raise WizardCompileError(
                        f"duplicate profile_key {question.profile_key!r}",
                        context={"profile_key": question.profile_key, "question_id": question.id},
                    )
                keys[question.profile_key] = _compile_one(question, by_id)
    return tuple(keys.values())


def _compile_one(
    question: WizardQuestion,
    by_id: dict[str, WizardQuestion],
) -> ProfileKey:
    requirement = (
        ProfileKeyRequirement.REQUIRED
        if question.required and question.visible_when is None
        else ProfileKeyRequirement.OPTIONAL
    )
    required_when_key: str | None = None
    required_when_value: str | None = None
    if question.visible_when is not None:
        required_when_key, required_when_value = _resolve_condition(question.visible_when, by_id)
    assert question.profile_key is not None
    return ProfileKey(
        key=question.profile_key,
        requirement=requirement,
        description=Translatable(f"profile.keys.{question.profile_key}"),
        required_when_key=required_when_key,
        required_when_value=required_when_value,
    )


def _resolve_condition(
    condition: WizardCondition,
    by_id: dict[str, WizardQuestion],
) -> tuple[str | None, str | None]:
    parent = by_id.get(condition.question_id)
    if parent is None or parent.profile_key is None:
        return None, None
    return parent.profile_key, condition.equals


__all__ = ["compile_profile_keys"]
