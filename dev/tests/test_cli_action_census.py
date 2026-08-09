"""Real-source contract tests for the CLI action candidate census."""

from __future__ import annotations

import pytest

from dev.cli_action_census import COMMAND_LITERAL_ALIAS, CandidateRecord, census

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def records() -> tuple[CandidateRecord, ...]:
    """Read the real pinned source tree once for this module's assertions."""
    return census("HEAD")


def test_census_records_are_stably_ordered_and_keyed_to_source_symbols(
    records: tuple[CandidateRecord, ...],
) -> None:
    """The current production tree produces reproducible, disposition-safe keys."""
    first = records
    second = census("HEAD")

    first_keys = tuple(record.key for record in first)
    second_keys = tuple(record.key for record in second)

    assert first_keys == second_keys
    assert first_keys == tuple(sorted(first_keys))
    assert len(set(first_keys)) == len(first_keys)
    assert all(record.path.startswith("src/cadrumo/") for record in first)
    assert all(record.enclosing_symbol for record in first)
    assert all(record.role and record.alias and record.action_identity for record in first)


def test_census_observes_real_definition_producer_and_command_literal_sites(
    records: tuple[CandidateRecord, ...],
) -> None:
    """The live corpus demonstrates the three distinct discovery roles."""
    keys = {record.key for record in records}

    assert (
        "src/cadrumo/core/json_contract.py",
        "Notice",
        "definition",
        "suggestion",
        "<none>",
    ) in keys
    assert any(
        record.role == "producer"
        and record.alias == "suggestion"
        and record.action_identity == "aeat config profile create NAME"
        and record.path == "src/cadrumo/application/workflow/_models.py"
        for record in records
    )


def test_census_observes_workflow_detail_map_next_action_producers(
    records: tuple[CandidateRecord, ...],
) -> None:
    """Workflow detail dictionaries remain first-class action producers."""
    workflow_path = "src/cadrumo/application/workflow/_engine.py"

    assert {
        (
            workflow_path,
            "WorkflowEngine._load_and_build_draft",
            "producer",
            "next_action",
            "_DRAFT_BUILD_REFUSED_NEXT_ACTION",
        ),
        (
            workflow_path,
            "WorkflowEngine._abort_if_draft_not_ready",
            "producer",
            "next_action",
            "_VERIFICATION_REPORT_NEXT_ACTION",
        ),
        (
            workflow_path,
            "WorkflowEngine._stage_validating_draft",
            "producer",
            "next_action",
            "_VERIFICATION_REPORT_NEXT_ACTION",
        ),
    }.issubset({record.key for record in records})
    assert any(
        record.role == "command_literal"
        and record.alias == COMMAND_LITERAL_ALIAS
        and record.action_identity == "aeat config profile create NAME"
        for record in records
    )
