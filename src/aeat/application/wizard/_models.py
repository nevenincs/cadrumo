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

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core.i18n import Translatable


class WizardWidget(StrEnum):
    """Closed taxonomy of input primitives the wizard runtime supports."""

    TEXT = "text"
    SECRET = "secret"  # noqa: S105
    CONFIRM = "confirm"
    SELECT = "select"
    CHECKBOX = "checkbox"
    PATH = "path"
    INTEGER = "integer"


class WizardCondition(BaseModel):
    """Single-clause equality predicate gating a question's visibility.

    The predicate names an earlier question by id and compares the
    canonical-token answer (``"true"`` / ``"false"`` for booleans,
    raw string for everything else) against a literal ``equals`` value.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    question_id: str = Field(min_length=1)
    equals: str


class WizardChoice(BaseModel):
    """One entry in a SELECT or CHECKBOX widget's closed-set choices."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    value: str = Field(min_length=1)
    label: Translatable
    description: Translatable | None = None


class WizardQuestion(BaseModel):
    """One operator-facing question in a wizard flow."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    profile_key: str | None = None
    widget: WizardWidget
    prompt: Translatable
    help: Translatable | None = None
    choices: tuple[WizardChoice, ...] = ()
    default: str | None = None
    required: bool = True
    visible_when: WizardCondition | None = None
    answer_type: type[str] | type[bool] | type[int] | type[Path]


class WizardSection(BaseModel):
    """One grouped sequence of questions inside a flow."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    title: Translatable
    questions: tuple[WizardQuestion, ...] = Field(min_length=1)


class WizardFlow(BaseModel):
    """The top-level descriptor for a single wizard surface."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    title: Translatable
    description: Translatable
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
                f"{expected!r}: {', '.join(offenders)}"
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
        """Every ``visible_when.question_id`` must resolve to an earlier question."""

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
                condition = question.visible_when
                if condition is not None:
                    target_index = seen.get(condition.question_id)
                    if target_index is None or target_index >= order:
                        bad.append(f"{question.id}->{condition.question_id}")
                order += 1
        if bad:
            raise ValueError(
                f"WizardFlow {self.id!r} has visible_when references that do not resolve "
                f"to earlier questions: {', '.join(bad)}"
            )
        return self


def _walk_translatables(flow: WizardFlow) -> list[tuple[Translatable, str]]:
    """Yield every ``Translatable`` in ``flow`` with a dotted-path location."""

    result: list[tuple[Translatable, str]] = []
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
                        )
                    )
    return result
