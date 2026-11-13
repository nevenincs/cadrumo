"""Where a declaration stands on the filing journey, decided once for every frontend.

Four steps, each decided from facts the form and the lifecycle already carry:
fill in (no field still needs the filer and no value is still assumed), calculate
(a calculation exists and nothing changed since), check (the current calculation is
verified and nothing blocks filing) and record filing (the declaration is recorded
as filed). The first step not done is the current one.

Nothing here is inferred beyond those facts. A step is never shown done because
its signal is missing: an unverified calculation is simply not checked, and a
verification that found something to resolve sends the filer to what it found
rather than back to verifying. A page that does not apply this period holds
nothing to do, so it neither keeps filling in open nor is counted.

What only a frontend holds is not stated here: whether it keeps changes not yet
applied, and whether an apply it submitted was refused for a prerequisite. The
journey states the answer for each case, and the frontend picks the one its own
state calls for: :attr:`ModeloFormJourney.steps_while_changes_held` while changes
stand unapplied, and :attr:`ModeloFormJourney.held_prerequisite_next_step` while
a refused apply's prerequisite still stands.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from .work_form_field_vocabulary import ModeloFormAddressV1, ModeloFormStanding
from .work_form_header import form_recorded
from .work_form_issue_lines import ModeloFormVerdict, form_verdict
from .work_form_models import ModeloWorkForm, section_fields
from .work_form_next_step import (
    ModeloFormNextStep,
    awaiting_the_check,
    blocking_count,
    form_next_step,
    held_prerequisite_step,
    inapplicable_pages,
    to_do_counts,
)


class ModeloFormStep(StrEnum):
    """The steps of filing one declaration, in order."""

    FILL = "fill"
    CALCULATE = "calculate"
    REVIEW = "review"
    FILE = "file"


class ModeloFormStepStatus(StrEnum):
    """How far one step has got."""

    DONE = "done"
    CURRENT = "current"
    BLOCKED = "blocked"
    PENDING = "pending"


class ModeloFormStepState(BaseModel):
    """One step and how far it has got."""

    model_config = STRICT_FROZEN_CONFIG

    step: ModeloFormStep
    status: ModeloFormStepStatus


class ModeloFormFirstAttention(BaseModel):
    """The first box that needs the filer, on a page that applies this period."""

    model_config = STRICT_FROZEN_CONFIG

    address: ModeloFormAddressV1
    #: The official page holding the box; ``None`` for a calculation detail or an answer no page takes.
    page_id: str | None = None


class ModeloFormJourney(BaseModel):
    """The journey's state, the next action it offers, and where the filer starts."""

    model_config = STRICT_FROZEN_CONFIG

    #: The four steps as the form and the lifecycle leave them.
    steps: tuple[ModeloFormStepState, ...]
    #: The steps while the frontend holds changes not yet applied: nothing is done until they are applied.
    steps_while_changes_held: tuple[ModeloFormStepState, ...]
    #: The one action offered next, without what only a frontend adds (changes held, a refused apply).
    next_step: ModeloFormNextStep
    #: The next step while a refused apply's retained prerequisite still stands: resolving it, from the findings.
    held_prerequisite_next_step: ModeloFormNextStep
    #: The first box that needs the filer; ``None`` once the declaration is recorded as filed or nothing does.
    first_attention: ModeloFormFirstAttention | None = None
    #: What the last check concluded, in the form's language.
    verdict: ModeloFormVerdict


def form_journey(form: ModeloWorkForm, *, verified: bool, filed: bool) -> ModeloFormJourney:
    """Place a declaration on the filing journey from its form and lifecycle facts.

    A declaration recorded as filed is done whatever its form still marks. A
    verified one is not sent back to filling in the boxes verification already
    accepted, but an assumed value still keeps filling in open: only the filer
    can say it is right. Every step shows whether it is done, wherever it sits;
    the first step not done is the current one.
    """
    recorded = form_recorded(form, filed=filed)
    step = form_next_step(form, verified=verified, filed=recorded)
    return ModeloFormJourney(
        steps=_steps(form, verified=verified, filed=recorded, changes_held=False),
        steps_while_changes_held=_steps(form, verified=verified, filed=recorded, changes_held=True),
        next_step=step,
        held_prerequisite_next_step=held_prerequisite_step(step),
        first_attention=None if recorded else _first_attention(form),
        verdict=form_verdict(form, form.language),
    )


def _steps(form: ModeloWorkForm, *, verified: bool, filed: bool, changes_held: bool) -> tuple[ModeloFormStepState, ...]:
    counts = to_do_counts(form)
    blocked = counts.blocked
    blocking = blocking_count(form)
    clean = not changes_held
    done = {
        ModeloFormStep.FILL: clean and _filling_is_done(filed, verified, counts.needs_input, counts.default_to_confirm),
        ModeloFormStep.CALCULATE: clean and _calculation_is_done(form, filed),
        ModeloFormStep.REVIEW: clean and _review_is_done(filed, verified, blocked, blocking),
        ModeloFormStep.FILE: clean and filed,
    }
    return _step_states(done, blocked=blocked, blocking=blocking, awaiting=awaiting_the_check(form), form=form)


def _filling_is_done(filed: bool, verified: bool, to_fill: int, assumed: int) -> bool:
    return filed or ((verified or to_fill == 0) and assumed == 0)


def _calculation_is_done(form: ModeloWorkForm, filed: bool) -> bool:
    return form.calculation_revision_id is not None and (filed or not form.calculation_out_of_date)


def _review_is_done(filed: bool, verified: bool, blocked: int, blocking: int) -> bool:
    return filed or (verified and blocked == 0 and blocking == 0)


def _step_states(
    done: Mapping[ModeloFormStep, bool], *, blocked: int, blocking: int, awaiting: int, form: ModeloWorkForm
) -> tuple[ModeloFormStepState, ...]:
    steps: list[ModeloFormStepState] = []
    current_found = False
    for step in ModeloFormStep:
        if done[step]:
            steps.append(ModeloFormStepState(step=step, status=ModeloFormStepStatus.DONE))
        elif not current_found:
            current_found = True
            is_blocked = step is ModeloFormStep.REVIEW and (
                blocked > 0 or blocking > awaiting or form.verification is VerificationCompletenessStatus.BLOCKED
            )
            status = ModeloFormStepStatus.BLOCKED if is_blocked else ModeloFormStepStatus.CURRENT
            steps.append(ModeloFormStepState(step=step, status=status))
        else:
            steps.append(ModeloFormStepState(step=step, status=ModeloFormStepStatus.PENDING))
    return tuple(steps)


def _first_attention(form: ModeloWorkForm) -> ModeloFormFirstAttention | None:
    """The first box standing on the filer, in reading order, on a page that applies this period."""
    set_aside = inapplicable_pages(form)
    for page in form.pages:
        if page.id in set_aside:
            continue
        for section in page.sections:
            for field in section_fields(section):
                if field.standing is ModeloFormStanding.NEEDS_YOU:
                    return ModeloFormFirstAttention(address=field.address, page_id=page.id)
    detail_fields = [*form.working_figures, *(item.field for item in form.unplaced), *form.answers]
    for field in detail_fields:
        if field.standing is ModeloFormStanding.NEEDS_YOU:
            return ModeloFormFirstAttention(address=field.address)
    return None


__all__ = [
    "ModeloFormFirstAttention",
    "ModeloFormJourney",
    "ModeloFormStep",
    "ModeloFormStepState",
    "ModeloFormStepStatus",
    "form_journey",
]
