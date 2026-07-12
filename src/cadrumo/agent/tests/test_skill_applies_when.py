"""Coverage gate: every shipped skill declares a valid structured ``applies_when``.

The skill selection predicate was historically prose inside the ``description``
frontmatter field, which a router, an MCP guided prompt, or an eval scenario could
not query deterministically. Each skill now lifts that predicate into a structured
``applies_when`` field parsed and validated at load time. This gate asserts the lift
is complete and honest: every shipped skill enumerates through the validating
loader (so a missing, malformed, or invalid predicate fails loudly), every profile
fact a predicate names is a real :class:`TaxpayerProfile` field, and the frontmatter
name matches the skill directory. A companion test proves the validation has teeth,
so the gate is not tautological.
"""

from __future__ import annotations

import pytest

from .. import iter_skill_documents, iter_skill_metadata
from .._skill_metadata import (
    SkillAppliesWhen,
    SkillMetadataError,
    parse_skill_metadata,
    profile_fact_names,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_every_shipped_skill_declares_a_valid_applies_when() -> None:
    # ``iter_skill_metadata`` validates a predicate that is present and raises on
    # a malformed one, but it deliberately TOLERATES a missing predicate so the
    # tree stays loadable while the lifts land. This gate - not the loader - is
    # the strict presence enforcer: every shipped skill must declare the field.
    metadata = list(iter_skill_metadata())
    assert metadata, "no skills shipped under _data/agent/skills"

    # One metadata per shipped SKILL.md - no skill silently skipped.
    document_count = sum(1 for _ in iter_skill_documents())
    assert len(metadata) == document_count

    missing = [entry.name for entry in metadata if entry.applies_when is None]
    assert not missing, "skills ship without a structured applies_when predicate (lift them from prose):\n" + "\n".join(
        missing,
    )


def test_every_predicate_declares_at_least_one_axis() -> None:
    # The schema forbids an empty predicate, but assert it at the corpus level so
    # a skill cannot ship an inert ``applies_when: {}`` that selects nothing.
    for entry in iter_skill_metadata():
        applies_when: SkillAppliesWhen | None = entry.applies_when
        if applies_when is None:
            continue  # presence is enforced by the gate above
        gated = (
            bool(applies_when.profile_facts)
            or applies_when.workflow_phase is not None
            or applies_when.temporal_trigger is not None
            or applies_when.always
        )
        assert gated, f"skill '{entry.name}' declares an empty applies_when predicate"


def test_every_profile_fact_predicate_names_a_real_taxpayer_fact() -> None:
    valid_facts = profile_fact_names()
    offenders: list[str] = []
    for entry in iter_skill_metadata():
        if entry.applies_when is None:
            continue
        for predicate in entry.applies_when.profile_facts:
            if predicate.fact not in valid_facts:
                offenders.append(f"{entry.name}: '{predicate.fact}'")
    assert not offenders, "skills name profile facts that are not TaxpayerProfile fields:\n" + "\n".join(offenders)


def test_invalid_applies_when_is_rejected() -> None:
    # Anti-tautology proof: the coverage gate can fail. A frontmatter naming a
    # fact that is not a real TaxpayerProfile field must be refused, so a genuine
    # regression (a typo'd fact, a missing predicate) reds this suite rather than
    # slipping through.
    bogus_fact = (
        "---\n"
        "name: probe\n"
        "description: y\n"
        "applies_when:\n"
        "  profile_facts:\n"
        "    - fact: not_a_real_fact\n"
        "      match: present\n"
        "---\n"
    )
    with pytest.raises(SkillMetadataError):
        parse_skill_metadata(bogus_fact)

    empty_predicate = "---\nname: probe\ndescription: y\napplies_when: {}\n---\n"
    with pytest.raises(SkillMetadataError):
        parse_skill_metadata(empty_predicate)
