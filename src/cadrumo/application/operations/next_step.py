"""The step a refused operation serves for putting the refusal right.

A refusal can name one thing the filer does next: creating a declaration that
does not exist yet, calculating one that has no calculation, or opening one
whose own form says what it still lacks. The step says which of the three, which
declaration it concerns and the words that offer it, so a frontend does what it
already knows for that kind and keeps no table of operator action identifiers.
The kind is closed; an address that cannot be run is refused when the step is
built.

The words are in the language the refusal's own sentence is in
(``refusal_words_language`` of the error detail that carries the step): the
detail words both when it is built.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from ...core.external_constants import OutputLanguage
from ...core.filing_year import FourDigitYear
from ...core.identity.hex_ids import WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

_Token = Annotated[str, StringConstraints(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9]+$")]
_Words = Annotated[str, StringConstraints(min_length=1, max_length=512)]


class OperationCreateWorkStepV1(BaseModel):
    """Create the declaration of one modelo, filing year and period."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["create_work"] = "create_work"
    modelo: _Token
    filing_year: FourDigitYear
    period_code: _Token
    words: _Words


class OperationCalculateWorkStepV1(BaseModel):
    """Calculate the declaration one work unit holds."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["calculate_work"] = "calculate_work"
    work_unit_id: WorkUnitId
    words: _Words


class OperationOpenWorkStepV1(BaseModel):
    """Open the declaration one work unit holds, where its own form says what it still lacks."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["open_work"] = "open_work"
    work_unit_id: WorkUnitId
    words: _Words


type OperationNextStepV1 = Annotated[
    OperationCreateWorkStepV1 | OperationCalculateWorkStepV1 | OperationOpenWorkStepV1,
    Field(discriminator="kind"),
]
"""The step a refusal serves: a closed kind, the declaration it concerns, and the words that offer it."""


type OperationNextStepWording = Callable[[OutputLanguage], OperationNextStepV1]
"""A step still to be worded: given the language of the refusal's own sentence, the step in that language."""


class OperationNextStepErrorMixin:
    """Carry the step a refusal serves, beside whatever else the error carries.

    It is mixed in ahead of the error's other mixins, so the error keeps its own
    registered code and typed verdict; the step is the one the producer chose
    where it raised, never derived from the verdict afterwards. It is held
    unworded and worded when the refusal's detail is built, in the language of
    that detail's own sentence.
    """

    def __init__(self, *args: object, next_step: OperationNextStepWording | None = None, **kwargs: object) -> None:
        """Initialize the parent error and retain the step's wording."""
        parent_init: Callable[..., None] = super().__init__
        parent_init(*args, **kwargs)
        self._operation_next_step = next_step

    def operation_next_step(self, language: OutputLanguage) -> OperationNextStepV1 | None:
        """The step the refusal serves worded in ``language``, or ``None`` when it names none."""
        return None if self._operation_next_step is None else self._operation_next_step(language)


def error_next_step(error: BaseException, language: OutputLanguage) -> OperationNextStepV1 | None:
    """The step ``error`` serves worded in ``language``, or ``None`` for an error that carries none."""
    if isinstance(error, OperationNextStepErrorMixin):
        return error.operation_next_step(language)
    return None


__all__ = [
    "OperationCalculateWorkStepV1",
    "OperationCreateWorkStepV1",
    "OperationNextStepErrorMixin",
    "OperationNextStepV1",
    "OperationNextStepWording",
    "OperationOpenWorkStepV1",
    "error_next_step",
]
