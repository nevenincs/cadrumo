"""Descriptor models for the schema-driven wizard.

The five strict frozen pydantic v2 records below compose a closed,
declarative description of an operator-facing configuration flow.
``WizardFlow`` is a tuple of ``WizardSection``s; a section is a tuple
of ``WizardQuestion``s; each question binds zero-or-one
``profile_key`` to the legacy registry, declares exactly one
``WizardWidget`` kind, and carries the prompt copy and the optional
``WizardCondition`` that gates its visibility. The descriptor is the
single source of truth: the runtime, the Typer command factory, and
the ``compile_profile_keys`` projection all read off these records.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

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
