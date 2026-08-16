"""Real-source contract tests for the CLI action candidate census."""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from ..quality.cli_action_census import (
    COMMAND_LITERAL_ALIAS,
    CandidateRecord,
    DiscoveryKind,
    DiscoveryTrigger,
    DiscoveryTriggerKind,
    FixedPointNotClosedError,
    FixedPointSources,
    UnknownCluster,
    admit_alias,
    admit_discoveries,
    census,
    close_fixed_point,
    dump_fixed_point_state,
    fixed_point_pass_from_sources,
    initial_fixed_point_state,
    load_fixed_point_state,
    main,
)

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


def _fixed_point_sources() -> FixedPointSources:
    """An explicit production corpus exercising each direct evidence edge once."""
    return FixedPointSources.from_entries(
        (
            (
                "src/cadrumo/application/refusal.py",
                """
class Refusal:
    recovery_hint: str

    def render(self) -> str:
        return tr(self.recovery_hint)


def refuse(suggestion: str) -> None:
    raise RefusalBoundary(suggestion=suggestion)


context = {"recovery": Refusal.recovery_hint}


def projected(context: dict[str, str]) -> str:
    return tr(context["recovery"])


COMMAND = "aeat config profile create NAME"
""",
            ),
            (
                "src/cadrumo/locales/en.yml",
                "operator_command: aeat config profile create NAME\n",
            ),
        ),
    )


def test_fixed_point_observes_evidence_linked_cluster_kinds_and_requires_admission() -> None:
    """One pass reports typed evidence; it never silently expands scan inputs."""
    state = initial_fixed_point_state("synthetic")
    result = fixed_point_pass_from_sources(state, _fixed_point_sources())

    assert {record.kind for record in result.discoveries} == set(DiscoveryKind)
    assert all(record.path.startswith("src/cadrumo/") for record in result.discoveries)
    assert all(record.enclosing_symbol for record in result.discoveries)
    assert all(record.trigger.token for record in result.discoveries)
    assert all(record.trigger.kind in set(DiscoveryTriggerKind) for record in result.discoveries)
    assert "recovery" not in state.admitted_aliases
    with pytest.raises(FixedPointNotClosedError, match="action_alias:recovery"):
        close_fixed_point(result)


def test_cluster_admission_rescans_to_closure_without_promoting_generic_tokens() -> None:
    """Acknowledging evidence never turns model, helper, or result labels into aliases."""
    state = initial_fixed_point_state("synthetic")
    first = fixed_point_pass_from_sources(state, _fixed_point_sources())
    admitted = admit_discoveries(state, first.discoveries)
    second = fixed_point_pass_from_sources(admitted, _fixed_point_sources())
    repeated = fixed_point_pass_from_sources(admitted, _fixed_point_sources())

    assert admitted.admitted_aliases == state.admitted_aliases
    assert len(second.candidates) == len(first.candidates)
    generic_tokens = {record.token for record in first.discoveries if record.kind is not DiscoveryKind.ACTION_ALIAS}
    assert generic_tokens.isdisjoint(admitted.admitted_aliases)
    state_document = dump_fixed_point_state(admitted)
    assert dump_fixed_point_state(load_fixed_point_state(state_document)) == state_document
    assert second.newly_observed == ()
    assert close_fixed_point(second) is second
    assert asdict(second.state) == asdict(repeated.state)
    assert tuple(record.key for record in second.discoveries) == tuple(record.key for record in repeated.discoveries)


def test_explicit_evidenced_alias_promotion_expands_the_next_pass_and_reopens() -> None:
    """Only an observed ACTION_ALIAS token can expand vocabulary and reveal new edges."""
    initial = initial_fixed_point_state("synthetic")
    first = fixed_point_pass_from_sources(initial, _fixed_point_sources())
    acknowledged = admit_discoveries(initial, first.discoveries)
    promoted = admit_alias(acknowledged, "recovery", first.discoveries)
    expanded = fixed_point_pass_from_sources(promoted, _fixed_point_sources())

    assert "recovery" in promoted.admitted_aliases
    assert len(expanded.candidates) > len(first.candidates)
    assert any(
        record.kind is DiscoveryKind.HELPER and record.enclosing_symbol == "projected"
        for record in expanded.newly_observed
    )
    assert any(
        record.kind is DiscoveryKind.RENDERER and record.enclosing_symbol == "projected"
        for record in expanded.newly_observed
    )
    with pytest.raises(FixedPointNotClosedError, match="helper:projected"):
        close_fixed_point(expanded)
    with pytest.raises(ValueError, match="unobserved action alias"):
        admit_alias(acknowledged, "message", first.discoveries)


def test_unknown_semantic_cluster_is_reported_and_cannot_be_auto_admitted() -> None:
    """A semantic finding outside the typed vocabulary keeps closure open."""
    initial = initial_fixed_point_state("synthetic")
    first = fixed_point_pass_from_sources(initial, _fixed_point_sources())
    admitted = admit_discoveries(initial, first.discoveries)
    cluster_name = "operator-warning-prose"
    seed_name = "suggestion"
    unknown = UnknownCluster(
        kind="manual-rag-cluster",
        token=cluster_name,
        path="src/cadrumo/entrypoints/cli/_errors.py",
        enclosing_symbol="render_error",
        line=1,
        column=0,
        trigger=DiscoveryTrigger(
            kind=DiscoveryTriggerKind.SEED,
            token=seed_name,
            path="src/cadrumo/entrypoints/cli/_errors.py",
            enclosing_symbol="render_error",
            line=1,
            column=0,
        ),
    )
    result = fixed_point_pass_from_sources(admitted, _fixed_point_sources(), semantic_observations=(unknown,))

    assert result.unknown_clusters == (unknown,)
    with pytest.raises(FixedPointNotClosedError, match="unknown:manual-rag-cluster:operator-warning-prose"):
        close_fixed_point(result)


def test_fixed_point_requires_direct_local_flow_and_yaml_scalar_evidence() -> None:
    """Nested scopes, unrelated sinks, and YAML comments cannot fabricate discoveries."""
    sources = FixedPointSources.from_entries(
        (
            (
                "src/cadrumo/application/directness.py",
                """
def outer() -> None:
    suggestion = "ordinary prose"
    print(", ".join(["ordinary", "text"]))

    def nested() -> str:
        return tr(suggestion)


def unrelated() -> None:
    suggestion = "ordinary prose"
    print("not a recovery renderer")
""",
            ),
            (
                "src/cadrumo/locales/en.yml",
                "# aeat config profile create NAME\ncaption: ordinary prose\n",
            ),
        ),
    )

    result = fixed_point_pass_from_sources(initial_fixed_point_state("synthetic"), sources)

    assert not any(record.enclosing_symbol == "outer" for record in result.discoveries)
    assert any(
        record.kind is DiscoveryKind.HELPER and record.enclosing_symbol == "outer.nested"
        for record in result.discoveries
    )
    assert any(
        record.kind is DiscoveryKind.RENDERER and record.enclosing_symbol == "outer.nested"
        for record in result.discoveries
    )
    assert not any(record.enclosing_symbol == "unrelated" for record in result.discoveries)
    assert not any(record.kind is DiscoveryKind.LOCALE_FAMILY for record in result.discoveries)
    assert all(record.trigger.path == record.path for record in result.discoveries)
    assert all(record.trigger.enclosing_symbol == record.enclosing_symbol for record in result.discoveries)


def test_fixed_point_state_is_strict_and_explicit_admission_reopens_on_new_source() -> None:
    """Persisted state is exact v1 evidence and a new direct edge keeps closure open."""
    initial = initial_fixed_point_state("synthetic")
    baseline = fixed_point_pass_from_sources(initial, _fixed_point_sources())
    admitted = admit_discoveries(initial, baseline.discoveries)
    state_document = dump_fixed_point_state(admitted)

    assert load_fixed_point_state(state_document) == admitted
    with pytest.raises(ValueError, match="exactly"):
        load_fixed_point_state(state_document | {"unreviewed": True})

    reopened = fixed_point_pass_from_sources(
        admitted,
        FixedPointSources.from_entries(
            (
                (
                    "src/cadrumo/application/reopened.py",
                    """
def new_refusal(suggestion: str) -> None:
    raise RefusalBoundary(suggestion=suggestion)
""",
                ),
            ),
        ),
    )

    assert reopened.newly_observed
    with pytest.raises(FixedPointNotClosedError, match="refusal_site:RefusalBoundary"):
        close_fixed_point(reopened)


def test_default_json_output_remains_the_s01_candidate_contract(capsys: pytest.CaptureFixture[str]) -> None:
    """Opt-in fixed-point diagnostics do not alter the census's machine-readable output."""
    assert main(["HEAD", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert set(payload) == {"revision", "candidate_count", "candidates"}
    assert payload["candidate_count"] == len(payload["candidates"])
