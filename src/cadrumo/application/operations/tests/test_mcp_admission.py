"""The recorded MCP decisions keep a shape their readers can rely on."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ..mcp_admission import (
    MCP_ADMISSION_DECISIONS,
    MCP_OVER_DECLARED_EFFECTS,
    McpAdmissionDecision,
    McpAdmissionPrerequisite,
    McpExclusionReason,
    McpRuling,
    mcp_admission_decision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _row(
    *,
    ruling: McpRuling = McpRuling.ADMITTED,
    changes_records: bool = False,
    exclusion_reason: McpExclusionReason | None = None,
    agent_facing_sibling: str | None = None,
    prerequisites: frozenset[McpAdmissionPrerequisite] = frozenset(),
    sensitive_actions: tuple[str, ...] = (),
) -> McpAdmissionDecision:
    return McpAdmissionDecision(
        definition_id="domain.thing.do",
        ruling=ruling,
        changes_records=changes_records,
        reaches_network=False,
        exclusion_reason=exclusion_reason,
        agent_facing_sibling=agent_facing_sibling,
        prerequisites=prerequisites,
        sensitive_actions=sensitive_actions,
    )


def test_decisions_are_unique_and_sorted_by_definition_id() -> None:
    identifiers = [decision.definition_id for decision in MCP_ADMISSION_DECISIONS]

    assert identifiers == sorted(set(identifiers))


def test_lookup_returns_the_recorded_row_and_refuses_an_unrecorded_operation() -> None:
    for decision in MCP_ADMISSION_DECISIONS:
        assert mcp_admission_decision(decision.definition_id) is decision

    with pytest.raises(KeyError, match="no recorded MCP decision"):
        mcp_admission_decision("domain.thing.unrecorded")


def test_every_agent_facing_sibling_is_an_admitted_row_with_nothing_outstanding() -> None:
    served = 0
    closed: list[str] = []
    for decision in MCP_ADMISSION_DECISIONS:
        if decision.agent_facing_sibling is None:
            continue
        served += 1
        sibling = mcp_admission_decision(decision.agent_facing_sibling)
        if sibling.ruling is not McpRuling.ADMITTED or sibling.prerequisites:
            closed.append(decision.definition_id)

    assert served
    assert not closed, f"projections served by a sibling that is not itself open: {closed}"


def test_every_over_declared_definition_is_recorded_as_not_changing_records() -> None:
    changing = sorted(
        definition_id
        for definition_id in MCP_OVER_DECLARED_EFFECTS
        if mcp_admission_decision(definition_id).changes_records
    )

    assert not changing, f"over-declared definitions recorded as changing records: {changing}"


def test_sensitive_actions_are_named_only_inside_admitted_definitions() -> None:
    named = {
        decision.definition_id: decision.sensitive_actions
        for decision in MCP_ADMISSION_DECISIONS
        if decision.sensitive_actions
    }

    assert named
    assert all(mcp_admission_decision(definition_id).ruling is McpRuling.ADMITTED for definition_id in named)


@pytest.mark.parametrize(
    ("build", "message"),
    [
        (lambda: _row(ruling=McpRuling.EXCLUDED), "exclusion reason"),
        (lambda: _row(exclusion_reason=McpExclusionReason.ACCESS_ADMINISTRATION), "exclusion reason"),
        (
            lambda: _row(ruling=McpRuling.EXCLUDED, exclusion_reason=McpExclusionReason.PERSON_PROJECTION),
            "agent-facing sibling",
        ),
        (lambda: _row(agent_facing_sibling="domain.thing.query"), "agent-facing sibling"),
        (
            lambda: _row(
                ruling=McpRuling.EXCLUDED,
                exclusion_reason=McpExclusionReason.PERSON_PROJECTION,
                agent_facing_sibling="domain.thing.do",
            ),
            "its own agent-facing sibling",
        ),
        (
            lambda: _row(
                ruling=McpRuling.EXCLUDED,
                exclusion_reason=McpExclusionReason.NOT_RUNNABLE,
                prerequisites=frozenset({McpAdmissionPrerequisite.FILE_EXCHANGE}),
            ),
            "no admission prerequisite",
        ),
        (
            lambda: _row(ruling=McpRuling.ADMITTED_BEHIND_APPROVAL, sensitive_actions=("remove",)),
            "only inside an admitted definition",
        ),
        (lambda: _row(sensitive_actions=("remove", "remove")), "must be unique"),
    ],
    ids=[
        "excluded-without-reason",
        "reason-without-exclusion",
        "projection-without-sibling",
        "sibling-without-projection",
        "own-sibling",
        "excluded-with-prerequisite",
        "sensitive-action-on-approval-row",
        "repeated-sensitive-action",
    ],
)
def test_a_row_whose_parts_contradict_its_ruling_is_refused(
    build: Callable[[], McpAdmissionDecision], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build()


def test_a_consistent_row_of_each_ruling_is_accepted() -> None:
    admitted = _row(prerequisites=frozenset({McpAdmissionPrerequisite.SAFEGUARD_MOVE}), sensitive_actions=("remove",))
    approval = _row(ruling=McpRuling.ADMITTED_BEHIND_APPROVAL, changes_records=True)
    projection = _row(
        ruling=McpRuling.EXCLUDED,
        exclusion_reason=McpExclusionReason.PERSON_PROJECTION,
        agent_facing_sibling="domain.thing.query",
    )

    assert admitted.sensitive_actions == ("remove",)
    assert approval.prerequisites == frozenset()
    assert projection.agent_facing_sibling == "domain.thing.query"
