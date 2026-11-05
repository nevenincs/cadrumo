"""A canonical persona's profile facts, and the canonical estimación directa normal, general-IVA taxpayer beneath them.

A persona's answers are read through the core persona reader, the production
setup flow assigns each answer its profile path and the profile patch judge
refuses what the patch operation would refuse. A suite that needs only the tax
axis of the electricista persona beneath its own identity, dates or scenario
facts takes the persona's facts and states the rest itself; a fact a suite
states replaces the persona's value for that path, unless the suite's fact is dated, which
stands beside the persona's undated one.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from functools import cache
from typing import Final

from cadrumo.application.user_profile.section_rows import next_section_row_index, section_row_facts
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.application.wizard.imputation_election import YEAR_QUESTION_ID
from cadrumo.application.wizard.patch_edit import validate_profile_patch
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.tests.personas import IdentityRef, Persona, ProfileValue, YearEnvelope, read_persona


def _submitted(persona: Persona, value: ProfileValue, envelope: YearEnvelope) -> str:
    """Render one ``[profile]`` value as the profile patch takes it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, tuple):
        return ",".join(value)
    if isinstance(value, IdentityRef):
        return persona.identity(value)
    return value.resolve(envelope).isoformat()


def _patch_answers(persona: Persona, envelope: YearEnvelope) -> dict[str, str]:
    """Every wizard answer the persona's patch submits: its answers, then its elections and their year."""
    answers = {answer.question_id: _submitted(persona, answer.value, envelope) for answer in persona.profile}
    years = {str(election.year.resolve(envelope)) for election in persona.elections}
    if len(years) > 1:
        raise ValueError(f"{persona.id}: one patch states one election year, found {sorted(years)}")
    answers.update((election.question, election.value) for election in persona.elections)
    answers.update((YEAR_QUESTION_ID, year) for year in years)
    return answers


def persona_profile_facts(persona_id: str) -> tuple[UserProfileFact, ...]:
    """The facts a persona's profile holds: its answers through the patch judge, its fields and its activity rows."""
    with bundled_indexed_authority().operation() as operation:
        support = operation.supported_filing_years()
        envelope = YearEnvelope(floor=support.floor, horizon=support.horizon)
        persona = read_persona(persona_id, envelope=envelope)
        flow = build_setup_flow(operation)
        changes = validate_profile_patch(
            flow=flow,
            current_values={},
            setup_state=ProfileSetupState.INCOMPLETE,
            supplied=_patch_answers(persona, envelope),
            colegio_concertado=None,
            operation=operation,
        )
        facts = [fact for fact in changes if fact.value is not None]
        facts.extend(UserProfileFact(path=field.path, value=field.value) for field in persona.fields)
        sections = {section.key: section for section in operation.profile_schema().sections}
        for activity in persona.activities:
            section = sections["activities"]
            index = next_section_row_index(section.key, (fact.path for fact in facts))
            facts.extend(section_row_facts(section, row_index=index, values=dict(activity.values)))
        return tuple(facts)


DIRECTA_NORMAL_PERSONA: Final = "autonomo-electricista"
"""The canonical estimación directa normal autónomo with general IVA."""

COLEGIO_CONCERTADO_ATTESTATION: Final = UserProfileFact(path="withholding.colegio_concertado", value=False)
"""The Modelo 111 header attestation a natural-person filer states; the persona leaves it outside its answers."""

_ACTIVITY_ROWS: Final = "activities."


@cache
def _persona_facts(persona_id: str) -> tuple[UserProfileFact, ...]:
    return persona_profile_facts(persona_id)


def _omitted(path: str, without: Collection[str]) -> bool:
    return any(path == name or (name.endswith(".") and path.startswith(name)) for name in without)


def persona_facts_beneath(
    stated: Iterable[UserProfileFact] = (),
    *,
    without: Collection[str] = (),
    persona_id: str = DIRECTA_NORMAL_PERSONA,
) -> tuple[UserProfileFact, ...]:
    """Return the persona's facts, then ``stated``, which replaces the persona's facts at every path it states.

    A stated fact replaces the persona's at its path whether it is dated or not, so a dated fact leaves the
    path undeclared outside its window rather than standing beside the persona's undated value.

    ``persona_id`` names the persona; it defaults to the canonical estimación directa normal one.

    A suite that states an ``activities.`` path the persona does not state
    states its own activity rows, so the persona's rows are left out. ``without`` names the paths, or
    the ``section.`` prefixes, of a variant that omits what the persona states and the caller does not restate.
    """
    stated = tuple(stated)
    paths = {fact.path for fact in stated}
    base = _persona_facts(persona_id)
    persona_paths = {fact.path for fact in base}
    own_activity_rows = any(path.startswith(_ACTIVITY_ROWS) and path not in persona_paths for path in paths)
    kept = tuple(
        fact
        for fact in base
        if fact.path not in paths
        and not _omitted(fact.path, without)
        and not (own_activity_rows and fact.path.startswith(_ACTIVITY_ROWS))
    )
    return (*kept, *stated)


def persona_fact_strings(
    stated: Mapping[str, str] | None = None,
    *,
    without: Collection[str] = (),
    persona_id: str = DIRECTA_NORMAL_PERSONA,
) -> dict[str, str]:
    """Return the persona's facts, with the colegio-concertado attestation and ``stated``, as the string values a profile seed takes."""
    facts = persona_facts_beneath(
        (
            COLEGIO_CONCERTADO_ATTESTATION,
            *(UserProfileFact(path=path, value=value) for path, value in (stated or {}).items()),
        ),
        without=without,
        persona_id=persona_id,
    )
    return {fact.path: str(fact.value).lower() if isinstance(fact.value, bool) else str(fact.value) for fact in facts}


def directa_normal_tax_id() -> str:
    """Return the identifier the canonical estimación directa normal persona states."""
    return next(str(fact.value) for fact in _persona_facts(DIRECTA_NORMAL_PERSONA) if fact.path == "identity.tax_id")
