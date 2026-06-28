"""Pure projection of the wizard descriptor catalogue into the ``PROFILE_KEYS`` registry shape.

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

from collections.abc import Iterator, Sequence

from ...core.i18n import Translatable as tr
from ...domain.contribuyente._keys import ProfileKey, ProfileKeyRequirement
from ._errors import WizardCompileError
from ._models import WizardCondition, WizardFlow, WizardQuestion, WizardVisibility


def compile_profile_keys(flows: Sequence[WizardFlow]) -> tuple[ProfileKey, ...]:
    """Project the wizard catalogue into the ``PROFILE_KEYS`` shape.

    Args:
        flows: The wizard catalogue to walk.

    Returns:
        A tuple of :class:`ProfileKey` records, one per distinct
        ``WizardQuestion.profile_key``. None-bound questions are
        skipped.
    """
    by_id = {question.id: question for question in _iter_catalogue_questions(flows)}
    keys: dict[str, ProfileKey] = {}
    for question in _iter_catalogue_questions(flows):
        if question.profile_key is None:
            continue
        _reject_duplicate_profile_key(question, keys)
        keys[question.profile_key] = _compile_one(question, by_id)
    return tuple(keys.values())


def _iter_catalogue_questions(flows: Sequence[WizardFlow]) -> Iterator[WizardQuestion]:
    """Flatten flow -> section -> question into a single question stream."""
    for flow in flows:
        for section in flow.sections:
            yield from section.questions


def _reject_duplicate_profile_key(question: WizardQuestion, keys: dict[str, ProfileKey]) -> None:
    if question.profile_key in keys:
        raise WizardCompileError(
            f"wizard compile duplicate profile_key {question.profile_key!r}",
            context={"profile_key": question.profile_key, "question_id": question.id},
        )


def _compile_one(
    question: WizardQuestion,
    by_id: dict[str, WizardQuestion],
) -> ProfileKey:
    requirement = (
        ProfileKeyRequirement.REQUIRED
        if question.required and question.visible_when is None
        else ProfileKeyRequirement.OPTIONAL
    )
    # The ``required_when_*`` pair expresses a *conditional requirement*:
    # the key is REQUIRED only while its gate predicate holds. It is
    # meaningful solely for a question that is itself ``required`` —
    # a ``required=False`` gated question is optional whether or not
    # its visibility gate is satisfied, so it carries no conditional
    # requirement. Emitting the pair for an optional gated question
    # wrongly promotes it to required as soon as the gate matches.
    required_when_key: str | None = None
    required_when_value: str | None = None
    if question.required and question.visible_when is not None:
        required_when_key, required_when_value = _resolve_condition(question.visible_when, by_id)
    if question.profile_key is None:
        raise WizardCompileError(
            f"question {question.id!r} reached _compile_one without a profile_key",
            context={"question_id": question.id},
        )
    return ProfileKey(
        key=question.profile_key,
        requirement=requirement,
        description=tr(f"profile.keys.{question.profile_key}"),
        required_when_key=required_when_key,
        required_when_value=required_when_value,
    )


def _resolve_condition(
    condition: WizardCondition | WizardVisibility,
    by_id: dict[str, WizardQuestion],
) -> tuple[str | None, str | None]:
    """Resolve a ``visible_when`` gate into the ``required_when_*`` pair.

    The ``ProfileKey`` registry expresses a conditional requirement as a
    single parent-key / parent-value pair. Only a single-clause
    ``equals`` :class:`WizardCondition` maps to that shape. A
    multi-clause :class:`WizardVisibility` disjunction and a
    ``contains`` checkbox-membership clause have no single-pair
    representation, so the conditional-requirement projection is left
    empty; the key is still emitted as ``OPTIONAL``.
    """
    if isinstance(condition, WizardVisibility):
        return None, None
    if condition.equals is None:
        return None, None
    parent = by_id.get(condition.question_id)
    if parent is None or parent.profile_key is None:
        return None, None
    return parent.profile_key, condition.equals


def _register_compiled_keys() -> None:
    """Register compiled PROFILE_KEYS into the domain registry at import time.

    Called once when this module is first imported. The domain's
    :func:`~aeat.domain.contribuyente._keys.register_profile_keys` receives the
    compiled tuple so the domain layer never needs to import application
    modules to populate its registry.
    """
    from ...domain.contribuyente._keys import register_profile_keys
    from . import _catalogue  # local import to avoid circular dependency at module level

    register_profile_keys(compile_profile_keys(_catalogue.WIZARD_FLOWS))


_register_compiled_keys()

__all__ = ["compile_profile_keys"]
