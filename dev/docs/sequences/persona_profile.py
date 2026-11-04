"""The canonical persona a docs sandbox or seed recipe takes its profile from.

The sandbox profile and the profile-setup frames of the seed recipes state the
facts of one catalogue persona (``dev/fixtures/personas``) instead of restating
them. The persona is read through the catalogue reader under the registry's
supported filing-year envelope, so a year token resolves exactly as it does for
every other consumer of the catalogue.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from cadrumo.application.user_profile.section_rows import section_row_facts
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.application.wizard.patch_edit import validate_profile_patch
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.entrypoints.tests.persona_materialisation import patch_answers, submitted_answer, year_envelope
from cadrumo.tests.personas import Persona, PersonaDate, ProfileAnswer, YearEnvelope, YearToken, read_persona

__all__ = ["SANDBOX_PERSONA_ID", "pinned_persona", "profile_option_arguments", "sandbox_profile_facts"]

#: The catalogue persona the docs sandbox profile holds before any frame runs.
SANDBOX_PERSONA_ID: str = "autonomo-fontanero"


@contextmanager
def pinned_persona(persona_id: str) -> Generator[tuple[Persona, YearEnvelope]]:
    """Read ``persona_id`` under the pinned authority's supported filing-year envelope."""
    with bundled_indexed_authority().operation() as operation:
        envelope = year_envelope(operation)
        yield read_persona(persona_id, envelope=envelope), envelope


def sandbox_profile_facts(persona_id: str = SANDBOX_PERSONA_ID) -> tuple[UserProfileFact, ...]:
    """Return the profile facts the persona's wizard answers and schema fields state.

    The answers pass through the wizard patch judge, so each fact is exactly what
    a ``config profile edit`` of the same answers would persist.
    """
    with bundled_indexed_authority().operation() as operation:
        envelope = year_envelope(operation)
        persona = read_persona(persona_id, envelope=envelope)
        changes = validate_profile_patch(
            flow=build_setup_flow(operation),
            current_values={},
            setup_state=ProfileSetupState.INCOMPLETE,
            supplied=dict(patch_answers(persona, envelope)),
            colegio_concertado=None,
            operation=operation,
        )
        schema = operation.profile_decode_context().schema
        stated = [change for change in changes if change.value is not None]
        stated.extend(UserProfileFact(path=field.path, value=field.value) for field in persona.fields)
        # Rows of the repeatable ``activities`` section take consecutive indices in file order, as
        # the row mutation allocates them on a profile that holds none.
        section = schema.section("activities")
        for index, activity in enumerate(persona.activities):
            stated.extend(section_row_facts(section, row_index=index, values=dict(activity.values)))
    return tuple(stated)


def profile_option_arguments(
    persona: Persona, envelope: YearEnvelope, question_ids: tuple[str, ...]
) -> tuple[str, ...]:
    """Render the persona's answers to ``question_ids`` as ``config profile edit`` options.

    A boolean answer is the question's on/off flag, a list answer repeats the
    option once per member, and every other answer is the option with its value.
    An entry ``question=<year token>:<MM>-<DD>`` instead states a scenario date
    the persona does not hold (a taxpayer whose activity began in the horizon
    year, say), resolved under the registry's year envelope.
    """
    by_question: dict[str, ProfileAnswer] = {answer.question_id: answer for answer in persona.profile}
    arguments: list[str] = []
    for entry in question_ids:
        question_id, separator, scenario_date = entry.partition("=")
        if separator:
            arguments.extend((f"--{question_id}", _scenario_date(scenario_date, envelope=envelope)))
            continue
        answer = by_question.get(question_id)
        if answer is None:
            raise ValueError(f"persona {persona.id} gives no answer to {question_id!r}")
        if isinstance(answer.value, bool):
            arguments.append(f"--{question_id}" if answer.value else f"--no-{question_id}")
        elif isinstance(answer.value, tuple):
            for member in answer.value:
                arguments.extend((f"--{question_id}", _quoted(member)))
        else:
            arguments.extend((f"--{question_id}", _quoted(submitted_answer(persona, answer.value, envelope))))
    return tuple(arguments)


def _scenario_date(text: str, *, envelope: YearEnvelope) -> str:
    """Resolve ``<year token>:<MM>-<DD>`` (``horizon:01-01``) to an ISO date under ``envelope``."""
    token, _, month_day = text.partition(":")
    month, _, day = month_day.partition("-")
    return (
        PersonaDate(year=YearToken.parse(token, where=text), month=int(month), day=int(day), biographical=True)
        .resolve(envelope)
        .isoformat()
    )


def _quoted(value: str) -> str:
    return f'"{value}"' if any(character in value for character in " \t") else value
