"""Descriptor models for the schema-driven wizard.

The five strict frozen pydantic v2 records below compose a closed,
declarative description of an operator-facing configuration flow.
``WizardFlow`` is a tuple of ``WizardSection``s; a section is a tuple
of ``WizardQuestion``s; each question binds zero-or-one
``profile_key`` to the profile registry, declares exactly one
``WizardWidget`` kind, and carries the prompt copy and the optional
``WizardCondition`` that gates its visibility. The descriptor is the
single source of truth: the runtime, the Typer command factory, and
the ``compile_profile_keys`` projection all read off these records.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from ...core.i18n import Translatable as tr
from ...core.models import STRICT_FROZEN_CONFIG


class WizardWidget(StrEnum):
    """Closed taxonomy of input primitives the wizard runtime supports."""

    TEXT = "text"
    SECRET = "secret"  # noqa: S105 - this is the public widget-kind token, not a credential
    CONFIRM = "confirm"
    SELECT = "select"
    CHECKBOX = "checkbox"
    PATH = "path"
    INTEGER = "integer"


class WizardCondition(BaseModel):
    """Single-clause predicate naming one earlier question.

    The predicate names an earlier question by id and tests its
    canonical-token answer (``"true"`` / ``"false"`` for booleans,
    raw string for SELECT/TEXT, comma-joined token set for CHECKBOX).
    Exactly one of two clause kinds is set:

    * ``equals`` — the answer must equal this literal token. Used for
      SELECT and CONFIRM gates (``entity-type == "legal_entity"``).
    * ``contains`` — the answer, split on commas into a token set,
      must contain this literal token. Used for CHECKBOX gates
      (``irpf-income-categories`` includes ``actividad_economica``).
    """

    model_config = STRICT_FROZEN_CONFIG

    question_id: str = Field(min_length=1)
    equals: str | None = None
    contains: str | None = None

    @model_validator(mode="after")
    def _validate_exactly_one_clause(self) -> WizardCondition:
        """Exactly one of ``equals`` / ``contains`` must be declared."""
        declared = [name for name, value in (("equals", self.equals), ("contains", self.contains)) if value is not None]
        if len(declared) != 1:
            raise ValueError(
                f"WizardCondition on {self.question_id!r} must declare exactly one of "
                f"'equals' / 'contains'; got {declared or ['none']}",
            )
        return self


class WizardVisibility(BaseModel):
    """Disjunction of :class:`WizardCondition` clauses.

    A question is visible when *any* clause is satisfied. A single-
    clause visibility is the common case; a multi-clause visibility
    expresses "asked when A or B" (e.g. ``activity`` is collected for
    a legal entity *or* for a natural person who declared an economic
    activity).
    """

    model_config = STRICT_FROZEN_CONFIG

    any_of: tuple[WizardCondition, ...] = Field(min_length=1)


class WizardChoice(BaseModel):
    """One entry in a SELECT or CHECKBOX widget's closed-set choices."""

    model_config = STRICT_FROZEN_CONFIG

    value: str = Field(min_length=1)
    label: tr
    description: tr | None = None


class WizardQuestion(BaseModel):
    """One operator-facing question in a wizard flow."""

    model_config = STRICT_FROZEN_CONFIG

    id: str = Field(min_length=1)
    profile_key: str | None = None
    widget: WizardWidget
    prompt: tr
    help: tr | None = None
    choices: tuple[WizardChoice, ...] = ()
    default: str | None = None
    required: bool = True
    visible_when: WizardCondition | WizardVisibility | None = None
    answer_type: type[str] | type[bool] | type[int] | type[Path]


class WizardSection(BaseModel):
    """One grouped sequence of questions inside a flow."""

    model_config = STRICT_FROZEN_CONFIG

    id: str = Field(min_length=1)
    title: tr
    questions: tuple[WizardQuestion, ...] = Field(min_length=1)


class WizardFlow(BaseModel):
    """The top-level descriptor for a single wizard surface."""

    model_config = STRICT_FROZEN_CONFIG

    id: str = Field(min_length=1)
    title: tr
    description: tr
    sections: tuple[WizardSection, ...] = Field(min_length=1)
    answers_model: type[BaseModel]

    @model_validator(mode="after")
    def _validate_translatable_prefix(self) -> WizardFlow:
        """Every ``Translatable`` in the flow must start with ``wizard.<flow.id>.``."""
        expected = f"wizard.{self.id}."
        offenders: list[str] = []
        for value, location in _walk_translatables(self):
            if not str(value).startswith(expected):
                offenders.append(f"{location}={value!r}")
        if offenders:
            raise ValueError(
                f"WizardFlow {self.id!r} carries Translatable values that do not start with "
                f"{expected!r}: {', '.join(offenders)}",
            )
        return self

    @model_validator(mode="after")
    def _validate_unique_question_ids(self) -> WizardFlow:
        """Question ids must be unique across the entire flow."""
        seen: set[str] = set()
        duplicates: list[str] = []
        for section in self.sections:
            for question in section.questions:
                if question.id in seen:
                    duplicates.append(question.id)
                seen.add(question.id)
        if duplicates:
            raise ValueError(f"WizardFlow {self.id!r} has duplicate question ids: {', '.join(sorted(duplicates))}")
        return self

    @model_validator(mode="after")
    def _validate_visible_when_targets(self) -> WizardFlow:
        """Every ``visible_when`` clause must name an earlier question.

        A multi-clause :class:`WizardVisibility` is checked clause by
        clause: every named question must precede the gated question
        so the runtime has the parent answer in hand when it evaluates
        visibility.

        This invariant is enforced a second time, over a different model, by
        :meth:`~application.flows.definition.FlowDefinition._validate_visible_when_targets`.
        The two exist because the models differ, not by oversight: every
        ``WizardFlow`` is bridged into a ``FlowDefinition``, but
        ``attach_descendant_group`` then splices in pages authored directly in
        ``FlowPage`` vocabulary that no ``WizardFlow`` ever contained, so the
        flows-side check covers content this one cannot see. This one runs at
        catalogue-authoring time, before the bridge, and names the offending
        QUESTIONS rather than the bridged pages.

        Change the rule here and the sibling silently keeps enforcing the old
        one; they are linked by this note and nothing else.
        """
        seen: dict[str, int] = {}
        index = 0
        for section in self.sections:
            for question in section.questions:
                seen[question.id] = index
                index += 1

        order = 0
        bad: list[str] = []
        for section in self.sections:
            for question in section.questions:
                for condition in iter_conditions(question.visible_when):
                    target_index = seen.get(condition.question_id)
                    if target_index is None or target_index >= order:
                        bad.append(f"{question.id}->{condition.question_id}")
                order += 1
        if bad:
            raise ValueError(
                f"WizardFlow {self.id!r} has visible_when references that do not resolve "
                f"to earlier questions: {', '.join(bad)}",
            )
        return self


def iter_conditions(
    visible_when: WizardCondition | WizardVisibility | None,
) -> tuple[WizardCondition, ...]:
    """Return every :class:`WizardCondition` clause in a ``visible_when``.

    Normalises the three shapes ``visible_when`` can take — ``None``
    (no gate), a bare :class:`WizardCondition` (single clause), or a
    :class:`WizardVisibility` (OR of clauses) — into a flat tuple so
    consumers iterate one uniform sequence.
    """
    if visible_when is None:
        return ()
    if isinstance(visible_when, WizardCondition):
        return (visible_when,)
    return visible_when.any_of


def _walk_translatables(flow: WizardFlow) -> list[tuple[tr, str]]:
    """Yield every ``Translatable`` in ``flow`` with a dotted-path location."""
    result: list[tuple[tr, str]] = []
    result.append((flow.title, f"{flow.id}.title"))
    result.append((flow.description, f"{flow.id}.description"))
    for section in flow.sections:
        result.append((section.title, f"{flow.id}.{section.id}.title"))
        for question in section.questions:
            result.append((question.prompt, f"{flow.id}.{section.id}.{question.id}.prompt"))
            if question.help is not None:
                result.append((question.help, f"{flow.id}.{section.id}.{question.id}.help"))
            for choice in question.choices:
                result.append((choice.label, f"{flow.id}.{section.id}.{question.id}.choices.{choice.value}.label"))
                if choice.description is not None:
                    result.append(
                        (
                            choice.description,
                            f"{flow.id}.{section.id}.{question.id}.choices.{choice.value}.description",
                        ),
                    )
    return result


__all__ = [
    "WizardChoice",
    "WizardCondition",
    "WizardFlow",
    "WizardQuestion",
    "WizardSection",
    "WizardVisibility",
    "WizardWidget",
    "iter_conditions",
]
