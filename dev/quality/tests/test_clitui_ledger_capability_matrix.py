"""Adversarial contract tests for the Ledger capability campaign matrix.

The matrix is a gate, not a status report.  These tests keep both halves of
each contract visible: a complete fixture must close the gate it claims to
close, while a representative mutation must reopen it or be refused at the
model boundary.  The fixture is deliberately small, but it exercises every
axis and every mandatory denominator source stream so that a one-row shortcut
cannot masquerade as the live campaign census.
"""

from __future__ import annotations

import json
from importlib import import_module
from collections.abc import Callable
from copy import copy
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Final, cast

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..clitui_ledger_capability_matrix import (
    ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
    LEDGER_REGISTRY_ROUTE_CENSUS_ROOT,
    LEDGER_TUI_SUPPORTED_SURFACE_CENSUS_ROOT,
    LEDGER_UNION_DENOMINATOR_ROOT,
    ApplicabilityState,
    AuthorityDispositionEntryV1,
    AuthorityDispositionSnapshotV1,
    AuthorityMigrationHistoryV1,
    AxisAssessmentV1,
    AxisProofState,
    CanonicalSemanticHomeV1,
    CapabilityAnnotation,
    CapabilityFindingV1,
    CensusStreamObservationV1,
    DenominatorSourceKind,
    EvidenceCoordinateV1,
    EvidenceKind,
    EvidenceRole,
    EvidenceSubjectSnapshotV1,
    InitialCliOwnership,
    LedgerCampaignControlsV1,
    LedgerCapabilityAxis,
    LedgerCapabilityIdentityV1,
    LedgerCapabilityMatrixV1,
    LedgerCapabilityRowV1,
    LedgerDenominatorSnapshotV1,
    LedgerGapClass,
    LedgerGate,
    LedgerLiveCensusReportV1,
    LedgerMatrixAcceptanceAttestationV1,
    LedgerRegistryRouteCensusV1,
    LedgerTuiSupportedSurfaceCensusV1,
    LedgerUnionDenominatorV1,
    ReviewRuling,
    SemanticHomeStatus,
    SurfaceCapabilityState,
    build_ledger_registry_route_census,
    build_ledger_tui_supported_surface_census,
    build_ledger_union_denominator,
    evaluate_ledger_capability_gate,
    evaluate_ledger_capability_gates,
    ledger_registry_route_census_bytes,
    ledger_registry_source_files,
    ledger_registry_source_set_digest,
    ledger_tui_supported_surface_census_bytes,
    ledger_tui_supported_surface_source_files,
    ledger_tui_supported_surface_source_set_digest,
    ledger_union_denominator_bytes,
    ledger_union_denominator_digest,
    reopened_gates_for_denominator_drift,
    validate_ledger_matrix_currentness,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_OBSERVED_AT: Final[datetime] = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
_LATER_OBSERVED_AT: Final[datetime] = datetime(2026, 9, 4, 12, 1, tzinfo=UTC)
_SUBJECT_ID: Final[str] = "subject.ledger.matrix"
_CENSUS_ID: Final[str] = "census.ledger.baseline"
_ROW_ID: Final[str] = "ledger.entries.list"
_SUBJECT_DIGEST: Final[str] = "sha256:" + "a" * 64
_REGISTRY_ROUTE_DIGEST: Final[str] = "sha256:20b2d2df5558b2a3fdbd1eab6e9f781a973e93c6211e211f8e679cf7b4782aca"
_REGISTRY_SOURCE_DIGEST: Final[str] = "sha256:194a9f26ddfbae6c5d7f265ffe58f50964fbe2fcd02a5670fa19845dead5cf6d"
_TUI_CENSUS_DIGEST: Final[str] = "sha256:c136cfe1ae3f82a239476c00e805f8c9a29e010d502e74397963cea7e6f42371"
_TUI_SOURCE_DIGEST: Final[str] = "sha256:e7337508a02ef2260e0b28205c31bb872b69f59aa51a18391ae209c21b8f9d57"
_UNION_DIGEST: Final[str] = "sha256:b694743c9edfe8c40fd7e6309b519cab353dd074dc75cd87688f144992561a7b"


@cache
def _registry_census() -> LedgerRegistryRouteCensusV1:
    return build_ledger_registry_route_census()


@cache
def _tui_census() -> LedgerTuiSupportedSurfaceCensusV1:
    return build_ledger_tui_supported_surface_census()


@cache
def _union_denominator() -> LedgerUnionDenominatorV1:
    return build_ledger_union_denominator(registry=_registry_census(), tui=_tui_census())


def _tui_source_records() -> tuple[tuple[str, bytes], ...]:
    root = Path(__file__).resolve().parents[3]
    return tuple(
        (path.resolve().relative_to(root).as_posix(), path.read_bytes())
        for path in ledger_tui_supported_surface_source_files(root)
    )


def _mutate_tui_source(relative: str, mutation: Callable[[bytes], bytes]) -> tuple[tuple[str, bytes], ...]:
    return tuple((path, mutation(body) if path == relative else body) for path, body in _tui_source_records())


def _replace_installed_return_with_unrelated_screen(body: bytes) -> bytes:
    mutated = body.replace(b"        return ledger_screen_factory(", b"        dead = ledger_screen_factory(", 1)
    return mutated.replace(b"        )(context)", b"        )(context)\n        return Screen()", 1)


def _alias_installed_screen_return(body: bytes) -> bytes:
    mutated = body.replace(b"        return ledger_screen_factory(", b"        screen = ledger_screen_factory(", 1)
    return mutated.replace(b"        )(context)", b"        )(context)\n        return screen", 1)


def test_tui_supported_surface_census_recomputes_the_published_live_digest() -> None:
    census = _tui_census()

    assert census.root == LEDGER_TUI_SUPPORTED_SURFACE_CENSUS_ROOT
    assert census.schema_version == 1
    assert census.source_set_digest == _TUI_SOURCE_DIGEST
    assert census.calculated_digest == _TUI_CENSUS_DIGEST
    assert len(census.routes) == 7
    assert [(row.destination, row.reachability) for row in census.routes] == [
        ("ledger.classification", "component_only"),
        ("ledger.entries", "component_only"),
        ("ledger.evidence", "component_only"),
        ("ledger.import", "component_only"),
        ("ledger.overview", "installed"),
        ("ledger.reconciliation", "component_only"),
        ("ledger.review", "component_only"),
    ]
    assert census.installed_outer_destination == "workbench.ledger"
    assert census.initial_internal_destination == "ledger.overview"
    assert census.message_consumers == ()
    assert census.injected_read_action_ids == (
        "operator.ledger.evidence.review.list",
        "operator.ledger.review",
    )
    assert census.installed_mutation_doors == ()
    assert len(census.cli_tui_capabilities) == 78
    assert {status for _command, status in census.cli_tui_capabilities} == {"not-implemented"}
    assert len(census.harness_files) == 6
    assert census.harness_test_functions == 65


def test_union_denominator_joins_every_raw_observation_without_double_counting() -> None:
    union = _union_denominator()

    assert union.root == LEDGER_UNION_DENOMINATOR_ROOT
    assert union.schema_version == 1
    assert len(union.observations) == 760
    assert len(union.rows) == 718
    assert [(item.source.value, item.observation_count) for item in union.source_digests] == [
        ("artifact_product", 6),
        ("backend_only", 63),
        ("cli_endpoint", 78),
        ("cli_suboperation", 50),
        ("missing_product", 10),
        ("registry_route", 546),
        ("supported_surface", 7),
    ]
    assert union.digest == _UNION_DIGEST
    assert ledger_union_denominator_digest(union) == _UNION_DIGEST
    assert ledger_union_denominator_bytes(union).startswith(b"cadrumo:ledger-union-denominator:v1\x00")


def test_union_denominator_merges_equivalent_stream_observations_and_keeps_distinct_effects() -> None:
    rows = {row.capability_id: row for row in _union_denominator().rows}

    assert {source.value for source in rows["ledger.transaction.create"].sources} == {
        "backend_only",
        "cli_endpoint",
    }
    assert {source.value for source in rows["ledger.classification.bulk_csv"].sources} == {
        "backend_only",
        "cli_suboperation",
    }
    assert {source.value for source in rows["ledger.export.csv"].sources} == {
        "artifact_product",
        "cli_suboperation",
    }
    assert {
        "ledger.classify.auto_split.reject",
        "ledger.classify.auto_split.split_preview",
        "ledger.classify.auto_split.split_apply",
        "ledger.classify.auto_split.single_preview",
        "ledger.classify.auto_split.single_apply",
    } <= rows.keys()


def test_union_denominator_retains_every_registry_route_unit_and_tui_reachability_split() -> None:
    union = _union_denominator()
    registry_rows = [row for row in union.rows if "registry_route" in {source.value for source in row.sources}]
    rows = {row.capability_id: row for row in union.rows}

    assert len(registry_rows) == 546
    assert len({row.capability_id for row in registry_rows}) == 546
    assert rows["ledger.workspace.read"].tui_routes == ("ledger.overview",)
    assert "reachability" not in {gap.value for gap in rows["ledger.workspace.read"].gap_classes}
    assert rows["ledger.transaction.list"].tui_routes == ("ledger.entries",)
    assert "reachability" in {gap.value for gap in rows["ledger.transaction.list"].gap_classes}


def test_union_denominator_has_explicit_axes_homes_proof_and_open_blockers_for_every_row() -> None:
    union = _union_denominator()

    assert all(len(row.applicability) == 8 for row in union.rows)
    assert all({decision.axis for decision in row.applicability} == set(LedgerCapabilityAxis) for row in union.rows)
    assert all(
        row.semantic_home.owner and row.semantic_home.command_type and row.semantic_home.result_type
        for row in union.rows
    )
    assert all(row.proof_requirements and row.blockers and row.next_action for row in union.rows)
    assert all(LedgerGapClass.PROOF in row.gap_classes for row in union.rows)
    assert {row.semantic_home_status for row in union.rows} == {
        SemanticHomeStatus.EXISTING,
        SemanticHomeStatus.PLANNED,
    }


def test_existing_union_semantic_homes_resolve_exact_live_symbols_and_types() -> None:
    existing_rows = [
        row for row in _union_denominator().rows if row.semantic_home_status is SemanticHomeStatus.EXISTING
    ]

    assert len(existing_rows) == 7
    for row in existing_rows:
        module_name, owner_name = row.semantic_home.owner.split(":", maxsplit=1)
        module = import_module(module_name)
        assert hasattr(module, owner_name)
        assert hasattr(module, row.semantic_home.command_type)
        assert hasattr(module, row.semantic_home.result_type)


@pytest.mark.parametrize("mutation", ["missing_row", "duplicate_observation", "wrong_sources", "stale_digest"])
def test_union_denominator_refuses_incomplete_or_stale_serialized_adjudication(mutation: str) -> None:
    union = _union_denominator()
    payload = union.model_dump(mode="python")
    if mutation == "missing_row":
        payload["rows"] = payload["rows"][:-1]
        expected = "unavailable row"
    elif mutation == "duplicate_observation":
        payload["observations"] = (*payload["observations"], payload["observations"][0])
        expected = "identities must be unique"
    elif mutation == "wrong_sources":
        first = dict(payload["rows"][0])
        first["sources"] = frozenset({DenominatorSourceKind.CLI_ENDPOINT})
        payload["rows"] = (first, *payload["rows"][1:])
        expected = "sources drifted"
    else:
        payload["digest"] = "sha256:" + "0" * 64
        expected = "digest does not match"

    with pytest.raises(ValidationError, match=expected):
        LedgerUnionDenominatorV1.model_validate(payload)


def test_tui_supported_surface_framing_is_domain_separated_unsigned_u64_big_endian() -> None:
    encoded = ledger_tui_supported_surface_census_bytes(_tui_census())
    frame = b"cadrumo:ledger-tui-supported-surface-census:v1\x00"

    assert encoded.startswith(frame)
    payload = encoded[len(frame) + 8 :]
    assert int.from_bytes(encoded[len(frame) : len(frame) + 8], byteorder="big", signed=False) == len(payload)


def test_tui_source_set_normalizes_irrelevant_record_order() -> None:
    records = _tui_source_records()

    assert ledger_tui_supported_surface_source_set_digest(source_records=reversed(records)) == _TUI_SOURCE_DIGEST


@pytest.mark.parametrize(
    ("relative", "mutation", "expected"),
    [
        pytest.param(
            "src/cadrumo/entrypoints/tui/app.py",
            lambda body: body.replace(
                b"class CadrumoTuiApp(App[AccountRecomposeRequiredV1 | None]):",
                b"class CadrumoTuiApp(App[AccountRecomposeRequiredV1 | None]):\n"
                b"    @on(LedgerRouteRequested)\n"
                b"    def arbitrary_handler_name(self, event):\n"
                b"        return event\n",
                1,
            ),
            "message",
            id="new-decorated-message-consumer",
        ),
        pytest.param(
            "src/cadrumo/entrypoints/tui/launcher.py",
            lambda body: body.replace(
                b"review_action=dependencies.ledger_review_action,",
                b"review_action=dependencies.ledger_review_action,\n"
                b"            classification_submitter=dependencies.ledger_review_action,",
                1,
            ),
            "door",
            id="new-installed-mutation-door",
        ),
        pytest.param(
            "src/cadrumo/entrypoints/tui/ledger/routes.py",
            lambda body: body.replace(
                b'    LedgerRouteV1("ledger.entries", LedgerWorkspaceArea.ENTRIES, LedgerEntriesScreen),',
                b"",
                1,
            ),
            "missing-route",
            id="missing-route",
        ),
        pytest.param(
            "src/cadrumo/entrypoints/tui/ledger/routes.py",
            lambda body: body.replace(
                b'    LedgerRouteV1("ledger.reconciliation", LedgerWorkspaceArea.RECONCILIATION, '
                b"LedgerReconciliationScreen),",
                b'    LedgerRouteV1("ledger.reconciliation", LedgerWorkspaceArea.RECONCILIATION, '
                b"LedgerReconciliationScreen),\n"
                b'    LedgerRouteV1("ledger.shadow", LedgerWorkspaceArea.RECONCILIATION, '
                b"LedgerReconciliationScreen),",
                1,
            ),
            "new-route",
            id="new-route",
        ),
        pytest.param(
            "src/cadrumo/entrypoints/tui/ledger/entries.py",
            lambda body: body.replace(b"class LedgerEntriesScreen", b"class RemovedLedgerEntriesScreen", 1),
            "missing-screen",
            id="missing-screen",
        ),
    ],
)
def test_tui_projection_detects_semantic_source_mutations(
    relative: str,
    mutation: Callable[[bytes], bytes],
    expected: str,
) -> None:
    records = _mutate_tui_source(relative, mutation)

    if expected == "missing-screen":
        with pytest.raises(ValueError, match="route/controller class is unavailable"):
            build_ledger_tui_supported_surface_census(source_records=records)
        return
    candidate = build_ledger_tui_supported_surface_census(source_records=records)
    assert candidate.calculated_digest != _TUI_CENSUS_DIGEST
    if expected == "message":
        assert candidate.message_consumers == ("LedgerRouteRequested",)
    elif expected == "door":
        assert candidate.installed_mutation_doors == ("classification_submitter",)
    elif expected == "missing-route":
        assert len(candidate.routes) == 6
    else:
        assert len(candidate.routes) == 8


def test_tui_projection_detects_new_scanned_source_file() -> None:
    records = (
        *_tui_source_records(),
        ("src/cadrumo/entrypoints/tui/new_ledger_surface.py", b'"""Synthetic source."""\n'),
    )

    candidate = build_ledger_tui_supported_surface_census(source_records=records)

    assert candidate.source_set_digest != _TUI_SOURCE_DIGEST
    assert candidate.calculated_digest != _TUI_CENSUS_DIGEST


@pytest.mark.parametrize(
    ("relative", "mutation"),
    [
        pytest.param(
            "src/cadrumo/entrypoints/tui/app.py",
            lambda body: body + b"\ndef on_ledger_route_requested(event):\n    return event\n",
            id="module-level-conventional-handler",
        ),
        pytest.param(
            "src/cadrumo/entrypoints/tui/installed_session.py",
            lambda body: body + b'\n_LEDGER_UNUSED_ACTION = "operator.ledger.unused"\n',
            id="unused-ledger-action-constant",
        ),
        pytest.param(
            "src/cadrumo/entrypoints/tui/ledger/routes.py",
            lambda body: (
                body + b'\ndef dead_route_helper():\n    return LedgerRouteV1("ledger.shadow", '
                b"LedgerWorkspaceArea.OVERVIEW, LedgerOverviewScreen)\n"
            ),
            id="dead-route-constructor",
        ),
        pytest.param(
            "src/cadrumo/entrypoints/tui/launcher.py",
            lambda body: (
                body + b"\ndef dead_ledger_factory_call(projection, action, submitter):\n"
                b"    return ledger_screen_factory(projection, review_action=action, "
                b"classification_submitter=submitter)\n"
            ),
            id="dead-same-name-factory-call",
        ),
    ],
)
def test_tui_projection_ignores_matching_syntax_outside_production_dataflow(
    relative: str,
    mutation: Callable[[bytes], bytes],
) -> None:
    candidate = build_ledger_tui_supported_surface_census(source_records=_mutate_tui_source(relative, mutation))
    baseline = _tui_census()

    assert candidate.source_set_digest != baseline.source_set_digest
    assert candidate.routes == baseline.routes
    assert candidate.message_consumers == baseline.message_consumers
    assert candidate.injected_read_action_ids == baseline.injected_read_action_ids
    assert candidate.installed_mutation_doors == baseline.installed_mutation_doors


def test_tui_projection_follows_initial_route_in_the_installed_factory_dataflow() -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/ledger/routes.py",
        lambda body: body.replace(
            b"controller.route_target(LedgerWorkspaceArea.OVERVIEW)",
            b"controller.route_target(LedgerWorkspaceArea.ENTRIES)",
            1,
        ),
    )

    candidate = build_ledger_tui_supported_surface_census(source_records=records)

    assert candidate.initial_internal_destination == "ledger.entries"
    assert tuple(row.destination for row in candidate.routes if row.reachability == "installed") == ("ledger.entries",)


def test_tui_projection_ignores_dead_overview_resolver_when_actual_return_is_an_entries_screen() -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/ledger/routes.py",
        lambda body: body.replace(
            b"        return resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.OVERVIEW))",
            b"        dead = resolve_ledger_screen(controller, "
            b"controller.route_target(LedgerWorkspaceArea.OVERVIEW))\n"
            b"        return LedgerEntriesScreen(controller)",
            1,
        ),
    )

    with pytest.raises(ValueError, match="root create return does not resolve one screen"):
        build_ledger_tui_supported_surface_census(source_records=records)


def test_tui_projection_ignores_dead_ledger_factory_when_actual_return_is_unrelated() -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/launcher.py",
        _replace_installed_return_with_unrelated_screen,
    )

    with pytest.raises(ValueError, match="create return does not invoke ledger_screen_factory"):
        build_ledger_tui_supported_surface_census(source_records=records)


def test_tui_projection_accepts_simple_aliases_on_both_return_dataflows() -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/launcher.py",
        _alias_installed_screen_return,
    )
    records = tuple(
        (
            relative,
            body.replace(
                b"        return resolve_ledger_screen(controller, "
                b"controller.route_target(LedgerWorkspaceArea.OVERVIEW))",
                b"        screen = resolve_ledger_screen(controller, "
                b"controller.route_target(LedgerWorkspaceArea.OVERVIEW))\n"
                b"        return screen",
                1,
            )
            if relative == "src/cadrumo/entrypoints/tui/ledger/routes.py"
            else body,
        )
        for relative, body in records
    )

    candidate = build_ledger_tui_supported_surface_census(source_records=records)

    assert candidate.initial_internal_destination == "ledger.overview"
    assert tuple(row.destination for row in candidate.routes if row.reachability == "installed") == ("ledger.overview",)


def test_tui_projection_refuses_conditionally_reassigned_route_target_alias() -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/ledger/routes.py",
        lambda body: body.replace(
            b"        return resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.OVERVIEW))",
            b"        target = LedgerWorkspaceArea.OVERVIEW\n"
            b"        if context.destination == 'dead.branch':\n"
            b"            target = LedgerWorkspaceArea.ENTRIES\n"
            b"        return resolve_ledger_screen(controller, controller.route_target(target))",
            1,
        ),
    )

    with pytest.raises(ValueError, match="not uniquely and unconditionally defined"):
        build_ledger_tui_supported_surface_census(source_records=records)


def test_tui_projection_refuses_conditionally_reassigned_installed_screen_alias() -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/launcher.py",
        lambda body: _alias_installed_screen_return(body).replace(
            b"        return screen",
            b"        if context.destination == 'dead.branch':\n            screen = Screen()\n        return screen",
            1,
        ),
    )

    with pytest.raises(ValueError, match="not uniquely and unconditionally defined"):
        build_ledger_tui_supported_surface_census(source_records=records)


@pytest.mark.parametrize(
    "replacement, message",
    [
        (b"        screen = Screen()\n        return screen", "not uniquely and unconditionally defined"),
        (b"        del screen\n        return screen", "not uniquely and unconditionally defined"),
        (b"        screen = screen\n        return screen", "not uniquely and unconditionally defined"),
    ],
)
def test_tui_projection_refuses_non_single_assignment_aliases(replacement: bytes, message: str) -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/launcher.py",
        lambda body: _alias_installed_screen_return(body).replace(b"        return screen", replacement, 1),
    )

    with pytest.raises(ValueError, match=message):
        build_ledger_tui_supported_surface_census(source_records=records)


def test_tui_projection_refuses_alias_read_before_definition() -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/launcher.py",
        lambda body: (
            _alias_installed_screen_return(body)
            .replace(b"screen = ledger_screen_factory", b"candidate = ledger_screen_factory", 1)
            .replace(b"return screen", b"screen = screen\n        return screen", 1)
        ),
    )

    with pytest.raises(ValueError, match="read before its definition"):
        build_ledger_tui_supported_surface_census(source_records=records)


@pytest.mark.parametrize(
    "binding",
    [
        b"        def screen():\n            return None\n",
        b"        async def screen():\n            return None\n",
        b"        class screen:\n            pass\n",
        b"        import screen\n",
        b"        import unrelated as screen\n",
        b"        from unrelated import screen\n",
        b"        from unrelated import value as screen\n",
    ],
)
def test_tui_projection_refuses_competing_definition_and_import_bindings(binding: bytes) -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/launcher.py",
        lambda body: _alias_installed_screen_return(body).replace(
            b"        return screen",
            binding + b"        return screen",
            1,
        ),
    )

    with pytest.raises(ValueError, match="not uniquely and unconditionally defined"):
        build_ledger_tui_supported_surface_census(source_records=records)


def test_tui_projection_ignores_differently_named_nested_body_bindings() -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/launcher.py",
        lambda body: _alias_installed_screen_return(body).replace(
            b"        return screen",
            b"        def unused_nested():\n"
            b"            screen = Screen()\n"
            b"            return screen\n"
            b"        return screen",
            1,
        ),
    )

    candidate = build_ledger_tui_supported_surface_census(source_records=records)

    assert candidate.initial_internal_destination == "ledger.overview"


@pytest.mark.parametrize(
    "definition",
    [
        b"        def helper(value=(screen := Screen())):\n            return value\n",
        b"        async def helper(value=(screen := Screen())):\n            return value\n",
        b"        helper = lambda value=(screen := Screen()): value\n",
        b"        @(screen := decorator)\n        def helper():\n            return None\n",
        b"        class Helper((screen := Base)):\n            pass\n",
        b"        @(screen := decorator)\n        class Helper:\n            pass\n",
        b"        class Helper(metaclass=(screen := Meta)):\n            pass\n",
    ],
)
def test_tui_projection_refuses_bindings_in_nested_definition_headers(definition: bytes) -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/launcher.py",
        lambda body: _alias_installed_screen_return(body).replace(
            b"        return screen",
            definition + b"        return screen",
            1,
        ),
    )

    with pytest.raises(ValueError, match="not uniquely and unconditionally defined"):
        build_ledger_tui_supported_surface_census(source_records=records)


@pytest.mark.parametrize(
    "comprehension",
    [
        b"[screen for screen in ()]",
        b"{screen for screen in ()}",
        b"{screen: screen for screen in ()}",
        b"(screen for screen in ())",
    ],
)
def test_tui_projection_accepts_comprehension_local_target_shadow(comprehension: bytes) -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/launcher.py",
        lambda body: _alias_installed_screen_return(body).replace(
            b"        return screen",
            b"        ignored = " + comprehension + b"\n        return screen",
            1,
        ),
    )

    candidate = build_ledger_tui_supported_surface_census(source_records=records)

    assert candidate.initial_internal_destination == "ledger.overview"


def test_tui_projection_accepts_comprehension_targets_in_postponed_annotations() -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/launcher.py",
        lambda body: _alias_installed_screen_return(body).replace(
            b"        return screen",
            b"        def helper(\n"
            b"            value: [screen for screen in ()],\n"
            b"        ) -> ([screen for screen in ()]):\n"
            b"            return value\n"
            b"        return screen",
            1,
        ),
    )

    candidate = build_ledger_tui_supported_surface_census(source_records=records)

    assert candidate.initial_internal_destination == "ledger.overview"


def test_tui_projection_refuses_walrus_rebinding_from_comprehension_scope() -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/launcher.py",
        lambda body: _alias_installed_screen_return(body).replace(
            b"        return screen",
            b"        ignored = [(screen := Screen()) for value in ()]\n        return screen",
            1,
        ),
    )

    with pytest.raises(ValueError, match="not uniquely and unconditionally defined"):
        build_ledger_tui_supported_surface_census(source_records=records)


def test_tui_projection_refuses_ambiguous_installed_screen_returns() -> None:
    records = _mutate_tui_source(
        "src/cadrumo/entrypoints/tui/launcher.py",
        lambda body: body.replace(
            b"    def create(context: TuiScreenContextV1) -> Screen[None]:",
            b"    def create(context: TuiScreenContextV1) -> Screen[None]:\n"
            b"        if context.destination == 'dead.branch':\n"
            b"            return Screen()",
            1,
        ),
    )

    with pytest.raises(ValueError, match="exactly one non-null return dataflow"):
        build_ledger_tui_supported_surface_census(source_records=records)


def test_tui_projection_detects_cli_tui_status_change() -> None:
    statuses = list(_tui_census().cli_tui_capabilities)
    statuses[0] = (statuses[0][0], "implemented")

    candidate = build_ledger_tui_supported_surface_census(cli_tui_capabilities=statuses)

    assert candidate.calculated_digest != _TUI_CENSUS_DIGEST
    assert {status for _command, status in candidate.cli_tui_capabilities} == {"implemented", "not-implemented"}


def test_tui_projection_refuses_reachability_classification_drift() -> None:
    census = _tui_census()
    drifted = tuple(
        row.model_copy(update={"reachability": "installed"}) if row.destination == "ledger.entries" else row
        for row in census.routes
    )

    with pytest.raises(ValidationError, match="initial internal destination must be the sole installed route"):
        LedgerTuiSupportedSurfaceCensusV1.model_validate({**census.model_dump(), "routes": drifted})


def _authority_with_first_defaulted_iva_selector(
    *, selector_update: dict[str, object] | None = None, reverse_input_order: bool = False
) -> tuple[ValidatedRegistryAuthority, tuple[str, str, str], BaseModel]:
    authority = bundled_authority()
    authority.validate_registry()
    mutated = copy(authority)
    modelos = list(authority.modelos)
    for modelo_index, modelo in enumerate(modelos):
        revisions = dict(modelo.revisions)
        for revision_id, revision in revisions.items():
            bindings = list(revision.bindings)
            for binding_index, binding in enumerate(bindings):
                if binding.source is not BindingSourceKind.LEDGER_IVA_AGGREGATION:
                    continue
                selector = binding.selector
                if not isinstance(selector, BaseModel) or "applied_rates" in selector.model_fields_set:
                    continue
                payload = selector.model_dump(mode="python", exclude_unset=True)
                if reverse_input_order:
                    payload = dict(reversed(tuple(payload.items())))
                if selector_update:
                    payload.update(selector_update)
                rebuilt = type(selector).model_validate(payload)
                bindings[binding_index] = binding.model_copy(update={"selector": rebuilt})
                revisions[revision_id] = revision.model_copy(update={"bindings": tuple(bindings)})
                modelos[modelo_index] = modelo.model_copy(update={"revisions": revisions})
                mutated.modelos = tuple(modelos)
                mutated._modelos_by_id = {item.id: item for item in mutated.modelos}
                return mutated, (modelo.id, revision.id, binding.id), selector
    raise AssertionError("no IVA selector with an omitted applied_rates default")


def test_registry_route_census_recomputes_the_published_live_authority_digest() -> None:
    census = _registry_census()

    assert census.root == LEDGER_REGISTRY_ROUTE_CENSUS_ROOT
    assert census.schema_version == 1
    assert len(census.rows) == 546
    assert len({(row.source, row.modelo_id, row.revision_id) for row in census.rows}) == 35
    assert len({row.source for row in census.rows}) == 7
    assert sum(bool(row.targets) for row in census.rows) == 510
    assert len(ledger_registry_source_files(bundled_authority())) == 130
    assert census.source_set_digest == _REGISTRY_SOURCE_DIGEST
    assert census.calculated_digest == _REGISTRY_ROUTE_DIGEST


def test_registry_projection_retains_every_typed_selector_default_and_null() -> None:
    _authority, coordinate, selector = _authority_with_first_defaulted_iva_selector()
    modelo_id, revision_id, binding_id = coordinate
    row = next(
        row
        for row in _registry_census().rows
        if (row.modelo_id, row.revision_id, row.binding_id) == (modelo_id, revision_id, binding_id)
    )
    projected = cast(dict[str, object], json.loads(row.selector_json))

    assert "applied_rates" not in selector.model_fields_set
    assert set(projected) == set(selector.__class__.model_fields) - {"source"}
    assert selector.__class__.model_fields["fact"].default == selector.fact
    assert projected["fact"] == "iva_amount_sum"
    assert projected["applied_rates"] is None
    assert projected["exemption_articles"] is None


@pytest.mark.parametrize(
    "selector_update",
    [
        pytest.param({"fact": "base_amount_sum"}, id="materialized-model-default"),
        pytest.param({"applied_rates": (Decimal("0.21"),)}, id="materialized-null"),
    ],
)
def test_registry_projection_detects_live_validated_selector_default_and_null_changes(
    selector_update: dict[str, object],
) -> None:
    authority, _coordinate, _selector = _authority_with_first_defaulted_iva_selector(selector_update=selector_update)

    assert build_ledger_registry_route_census(authority).calculated_digest != _registry_census().calculated_digest


def test_registry_projection_normalizes_irrelevant_selector_input_order() -> None:
    authority, _coordinate, _selector = _authority_with_first_defaulted_iva_selector(reverse_input_order=True)

    assert build_ledger_registry_route_census(authority).calculated_digest == _registry_census().calculated_digest


@pytest.mark.parametrize("mutation", ["selector", "applicability", "target", "section"])
def test_registry_route_digest_moves_for_each_route_fact(mutation: str) -> None:
    census = _registry_census()
    index = next(index for index, row in enumerate(census.rows) if row.targets)
    row = census.rows[index]
    if mutation == "selector":
        selector = json.loads(row.selector_json)
        selector["census_test_mutation"] = True
        changed = row.model_copy(update={"selector_json": json.dumps(selector, separators=(",", ":"), sort_keys=True)})
    elif mutation == "applicability":
        changed = row.model_copy(update={"valid_to": row.valid_from})
    else:
        target = row.targets[0]
        if mutation == "target":
            target = target.model_copy(update={"casilla_id": f"{target.casilla_id}-mutated"})
        else:
            target = target.model_copy(update={"section": (*target.section, "mutated")})
        changed = row.model_copy(update={"targets": (target, *row.targets[1:])})
    rows = (*census.rows[:index], changed, *census.rows[index + 1 :])
    candidate = LedgerRegistryRouteCensusV1.model_validate({**census.model_dump(mode="python"), "rows": rows})

    assert candidate.calculated_digest != census.calculated_digest


def test_registry_route_digest_moves_when_a_declaration_is_missing() -> None:
    census = _registry_census()
    candidate = LedgerRegistryRouteCensusV1.model_validate(
        {**census.model_dump(mode="python"), "rows": census.rows[:-1]}
    )

    assert candidate.calculated_digest != census.calculated_digest


@pytest.mark.parametrize("mutation", ["duplicate", "reordered"])
def test_registry_route_serializer_rejects_noncanonical_row_identity_order(mutation: str) -> None:
    census = _registry_census()
    rows = (
        (*census.rows, census.rows[-1])
        if mutation == "duplicate"
        else (census.rows[1], census.rows[0], *census.rows[2:])
    )
    invalid = census.model_copy(update={"rows": rows})

    with pytest.raises(ValidationError):
        ledger_registry_route_census_bytes(invalid)


@pytest.mark.parametrize(
    "mutation",
    [
        {"schema_version": 2},
        {"root": "ledger.routes"},
        {"unexpected": True},
    ],
)
def test_registry_route_census_rejects_malformed_root_schema(mutation: dict[str, object]) -> None:
    payload = {**_registry_census().model_dump(mode="python"), **mutation}

    with pytest.raises(ValidationError):
        LedgerRegistryRouteCensusV1.model_validate(payload)


def test_registry_route_census_rejects_malformed_or_noncanonical_rows() -> None:
    census = _registry_census()
    row = census.rows[0].model_dump(mode="python")
    row["selector_json"] = "{ not-json"
    payload = {**census.model_dump(mode="python"), "rows": (row, *census.rows[1:])}

    with pytest.raises(ValidationError):
        LedgerRegistryRouteCensusV1.model_validate(payload)


def test_registry_source_and_route_digests_move_for_relevant_source_drift() -> None:
    census = _registry_census()
    authority = bundled_authority()
    files = ledger_registry_source_files(authority)
    records = [
        (path.resolve().relative_to(authority.source_root.resolve()).as_posix(), path.read_bytes()) for path in files
    ]
    records[0] = (records[0][0], records[0][1] + b"\n# census drift")
    drifted_source_digest = ledger_registry_source_set_digest(authority, source_records=records)
    candidate = LedgerRegistryRouteCensusV1.model_validate(
        {**census.model_dump(mode="python"), "source_set_digest": drifted_source_digest}
    )

    assert drifted_source_digest != census.source_set_digest
    assert candidate.calculated_digest != census.calculated_digest


def _subject(
    *,
    subject_id: str = _SUBJECT_ID,
    revision: str = "matrix-rev-1",
    digest: str = _SUBJECT_DIGEST,
    observed_at: datetime = _OBSERVED_AT,
    locator: str = "reference://clitui-ledger/matrix",
) -> EvidenceSubjectSnapshotV1:
    """Build one current, bounded subject for all fixture evidence."""
    return EvidenceSubjectSnapshotV1(
        subject_id=subject_id,
        locator=locator,
        revision=revision,
        digest=digest,
        observed_at=observed_at,
    )


_SUBJECT: Final[EvidenceSubjectSnapshotV1] = _subject()


def _evidence(
    evidence_id: str,
    role: EvidenceRole,
    axes: frozenset[LedgerCapabilityAxis],
    *,
    kind: EvidenceKind | None = None,
    subject: EvidenceSubjectSnapshotV1 = _SUBJECT,
    claim: str = "The reviewed fixture proves this bounded claim.",
) -> EvidenceCoordinateV1:
    """Build a role-correct coordinate unless a test explicitly mutates it."""
    default_kinds = {
        EvidenceRole.APPLICABILITY_REVIEW: EvidenceKind.REVIEW,
        EvidenceRole.BASELINE: EvidenceKind.TEST,
        EvidenceRole.DIRECT_BACKEND_BEHAVIOR: EvidenceKind.TEST,
        EvidenceRole.ADAPTER_DETECTOR: EvidenceKind.TEST,
        EvidenceRole.CLI_SUCCESS: EvidenceKind.TEST,
        EvidenceRole.CLI_REFUSAL: EvidenceKind.TEST,
        EvidenceRole.CLI_ARTIFACT: EvidenceKind.TEST,
        EvidenceRole.TUI_PARITY: EvidenceKind.TEST,
        EvidenceRole.TUI_REACHABILITY: EvidenceKind.TEST,
        EvidenceRole.MATRIX_PUBLICATION: EvidenceKind.REFERENCE,
        EvidenceRole.INDEPENDENT_ENGINEERING_REVIEW: EvidenceKind.REVIEW,
    }
    return EvidenceCoordinateV1(
        evidence_id=evidence_id,
        kind=kind or default_kinds[role],
        role=role,
        axes=axes,
        subject_id=subject.subject_id,
        subject_revision=subject.revision,
        subject_digest=subject.digest,
        observed_at=subject.observed_at,
        locator=subject.locator,
        claim=claim,
    )


def _stream(
    source: DenominatorSourceKind,
    capability_ids: tuple[str, ...] = (),
    *,
    revision: str = "census-rev-1",
    observed_at: datetime = _OBSERVED_AT,
    scan_succeeded: bool = True,
    readable: bool = True,
    complete: bool = True,
    ambiguous: bool = False,
    reviewed_zero: bool | None = None,
) -> CensusStreamObservationV1:
    """Build a stream with its digest calculated over the observed scan."""
    zero = not capability_ids if reviewed_zero is None else reviewed_zero
    draft = CensusStreamObservationV1.model_construct(
        source=source,
        revision=revision,
        observed_at=observed_at,
        scan_succeeded=scan_succeeded,
        readable=readable,
        complete=complete,
        ambiguous=ambiguous,
        reviewed_zero=zero,
        capability_ids=capability_ids,
        digest="",
    )
    return CensusStreamObservationV1(
        source=source,
        revision=revision,
        observed_at=observed_at,
        scan_succeeded=scan_succeeded,
        readable=readable,
        complete=complete,
        ambiguous=ambiguous,
        reviewed_zero=zero,
        capability_ids=capability_ids,
        digest=draft.calculated_digest,
    )


def _report(
    capability_ids: tuple[str, ...] = (_ROW_ID,),
    *,
    census_id: str = _CENSUS_ID,
    revision: str = "census-rev-1",
    observed_at: datetime = _OBSERVED_AT,
    streams: tuple[CensusStreamObservationV1, ...] | None = None,
) -> LedgerLiveCensusReportV1:
    """Build all seven mandatory streams, using reviewed zeros where empty."""
    selected_streams = (
        streams
        if streams is not None
        else tuple(
            _stream(
                source,
                capability_ids if source is DenominatorSourceKind.CLI_ENDPOINT else (),
                revision=revision,
                observed_at=observed_at,
            )
            for source in DenominatorSourceKind
        )
    )
    draft = LedgerLiveCensusReportV1.model_construct(
        census_id=census_id,
        revision=revision,
        observed_at=observed_at,
        streams=selected_streams,
        digest="",
    )
    return LedgerLiveCensusReportV1(
        census_id=census_id,
        revision=revision,
        observed_at=observed_at,
        streams=selected_streams,
        digest=draft.calculated_digest,
    )


def _unchecked_empty_report() -> LedgerLiveCensusReportV1:
    """Build an explicitly empty report to exercise the gate's revalidation path."""
    streams = tuple(_stream(source) for source in DenominatorSourceKind)
    draft = LedgerLiveCensusReportV1.model_construct(
        census_id=_CENSUS_ID,
        revision="census-rev-empty",
        observed_at=_OBSERVED_AT,
        streams=streams,
        digest="",
    )
    return LedgerLiveCensusReportV1.model_construct(
        census_id=_CENSUS_ID,
        revision="census-rev-empty",
        observed_at=_OBSERVED_AT,
        streams=streams,
        digest=draft.calculated_digest,
    )


def _snapshot(report: LedgerLiveCensusReportV1) -> LedgerDenominatorSnapshotV1:
    """Freeze a live report into the accepted/current denominator shape."""
    return LedgerDenominatorSnapshotV1.from_live_report(report)


def _authority_snapshot(
    denominator: LedgerDenominatorSnapshotV1,
    rows: tuple[LedgerCapabilityRowV1, ...],
) -> AuthorityDispositionSnapshotV1:
    """Build the immutable initial-ownership census for a set of rows."""
    entries = tuple(
        AuthorityDispositionEntryV1(
            row_id=row.identity.row_id,
            initial_cli_ownership=row.authority_migration.initial_cli_ownership,
        )
        for row in sorted(rows, key=lambda candidate: candidate.identity.row_id)
    )
    draft = AuthorityDispositionSnapshotV1.model_construct(
        census_id=denominator.census_id,
        revision=denominator.revision,
        observed_at=denominator.observed_at,
        entries=entries,
        digest="",
    )
    return AuthorityDispositionSnapshotV1(
        census_id=denominator.census_id,
        revision=denominator.revision,
        observed_at=denominator.observed_at,
        entries=entries,
        digest=draft.calculated_digest,
    )


def _authority_snapshot_with(
    snapshot: AuthorityDispositionSnapshotV1,
    *,
    revision: str | None = None,
    observed_at: datetime | None = None,
    entries: tuple[AuthorityDispositionEntryV1, ...] | None = None,
) -> AuthorityDispositionSnapshotV1:
    """Recalculate a valid authority snapshot after one independent mutation."""
    selected_revision = snapshot.revision if revision is None else revision
    selected_observed_at = snapshot.observed_at if observed_at is None else observed_at
    selected_entries = snapshot.entries if entries is None else entries
    draft = AuthorityDispositionSnapshotV1.model_construct(
        census_id=snapshot.census_id,
        revision=selected_revision,
        observed_at=selected_observed_at,
        entries=selected_entries,
        digest="",
    )
    return AuthorityDispositionSnapshotV1(
        census_id=snapshot.census_id,
        revision=selected_revision,
        observed_at=selected_observed_at,
        entries=selected_entries,
        digest=draft.calculated_digest,
    )


def _assessment(
    axis: LedgerCapabilityAxis,
    *,
    prefix: str,
    applicable: bool = True,
    proof: AxisProofState = AxisProofState.PROVEN,
    surface_state: SurfaceCapabilityState | None = None,
    extra_evidence: tuple[EvidenceCoordinateV1, ...] = (),
) -> AxisAssessmentV1:
    """Build one reviewed axis with exact applicability and baseline evidence."""
    review = _evidence(
        f"evidence.{prefix}.applicability.{axis.value}",
        EvidenceRole.APPLICABILITY_REVIEW,
        frozenset({axis}),
    )
    if not applicable:
        return AxisAssessmentV1(
            axis=axis,
            applicability=ApplicabilityState.NOT_APPLICABLE,
            applicability_rationale="The reviewed capability has no obligation on this axis.",
            applicability_review_evidence=review,
            proof=AxisProofState.NOT_APPLICABLE,
            surface_state=(
                SurfaceCapabilityState.NOT_APPLICABLE
                if axis
                in {
                    LedgerCapabilityAxis.BACKEND,
                    LedgerCapabilityAxis.CLI,
                    LedgerCapabilityAxis.TUI,
                }
                else None
            ),
            evidence=(),
        )
    if axis in {LedgerCapabilityAxis.BACKEND, LedgerCapabilityAxis.CLI, LedgerCapabilityAxis.TUI}:
        effective_surface = surface_state or SurfaceCapabilityState.PROVEN
    else:
        effective_surface = None
    baseline = _evidence(
        f"evidence.{prefix}.baseline.{axis.value}",
        EvidenceRole.BASELINE,
        frozenset({axis}),
    )
    return AxisAssessmentV1(
        axis=axis,
        applicability=ApplicabilityState.APPLICABLE,
        applicability_rationale="The reviewed capability has an obligation on this axis.",
        applicability_review_evidence=review,
        proof=proof,
        surface_state=effective_surface,
        evidence=(baseline, *extra_evidence),
    )


def _row(
    row_id: str = _ROW_ID,
    *,
    initial_cli_ownership: InitialCliOwnership = InitialCliOwnership.CLI_OWNED,
    migration_completed: bool = True,
    tui_applicable: bool = True,
    prefix: str = "entries_list",
    findings: tuple[CapabilityFindingV1, ...] = (),
) -> LedgerCapabilityRowV1:
    """Build a complete row whose operational evidence can close every gate."""
    identity = LedgerCapabilityIdentityV1(
        capability_id=row_id.rsplit(".", maxsplit=1)[0],
        operation_id=row_id,
        suboperation_id=row_id,
    )
    backend_evidence = (
        _evidence(
            f"evidence.{prefix}.direct_backend",
            EvidenceRole.DIRECT_BACKEND_BEHAVIOR,
            frozenset({LedgerCapabilityAxis.BACKEND}),
        ),
    )
    cli_evidence = (
        _evidence(
            f"evidence.{prefix}.adapter_detector",
            EvidenceRole.ADAPTER_DETECTOR,
            frozenset({LedgerCapabilityAxis.CLI}),
        ),
        _evidence(
            f"evidence.{prefix}.cli_success",
            EvidenceRole.CLI_SUCCESS,
            frozenset({LedgerCapabilityAxis.CLI}),
        ),
        _evidence(
            f"evidence.{prefix}.cli_refusal",
            EvidenceRole.CLI_REFUSAL,
            frozenset({LedgerCapabilityAxis.CLI}),
        ),
        _evidence(
            f"evidence.{prefix}.cli_artifact",
            EvidenceRole.CLI_ARTIFACT,
            frozenset({LedgerCapabilityAxis.CLI, LedgerCapabilityAxis.ARTIFACT}),
        ),
    )
    assessments = (
        _assessment(LedgerCapabilityAxis.BACKEND, prefix=prefix, extra_evidence=backend_evidence),
        _assessment(LedgerCapabilityAxis.CLI, prefix=prefix, extra_evidence=cli_evidence),
        _assessment(
            LedgerCapabilityAxis.TUI,
            prefix=prefix,
            applicable=tui_applicable,
        ),
        _assessment(LedgerCapabilityAxis.COMPOSITION, prefix=prefix),
        _assessment(LedgerCapabilityAxis.ARTIFACT, prefix=prefix),
        _assessment(LedgerCapabilityAxis.PROVENANCE, prefix=prefix),
        _assessment(LedgerCapabilityAxis.REGISTRY, prefix=prefix),
        _assessment(LedgerCapabilityAxis.PROOF, prefix=prefix),
    )
    annotations = {CapabilityAnnotation.INSTALLED} if tui_applicable else set()
    if initial_cli_ownership is InitialCliOwnership.CLI_OWNED and migration_completed:
        annotations.add(CapabilityAnnotation.DELEGATING)
        delegates = True
    else:
        delegates = False
        if initial_cli_ownership is InitialCliOwnership.CLI_OWNED:
            annotations.add(CapabilityAnnotation.CLI_OWNED)
    return LedgerCapabilityRowV1(
        identity=identity,
        semantic_home=CanonicalSemanticHomeV1(
            owner="application.ledger",
            command_type="LedgerEntriesListCommand",
            result_type="LedgerEntriesListResult",
        ),
        assessments=assessments,
        annotations=frozenset(annotations),
        findings=findings,
        authority_migration=AuthorityMigrationHistoryV1(
            initial_cli_ownership=initial_cli_ownership,
            migration_completed=migration_completed,
        ),
        cli_delegates_to_canonical=delegates,
    )


def _campaign_evidence() -> tuple[EvidenceCoordinateV1, ...]:
    """Return the campaign-wide coordinates used by G4 and review records."""
    return (
        _evidence(
            "evidence.campaign.tui_parity",
            EvidenceRole.TUI_PARITY,
            frozenset(
                {
                    LedgerCapabilityAxis.BACKEND,
                    LedgerCapabilityAxis.CLI,
                    LedgerCapabilityAxis.TUI,
                }
            ),
        ),
        _evidence(
            "evidence.campaign.tui_reachability",
            EvidenceRole.TUI_REACHABILITY,
            frozenset({LedgerCapabilityAxis.TUI}),
        ),
        _evidence(
            "evidence.campaign.matrix_publication",
            EvidenceRole.MATRIX_PUBLICATION,
            frozenset(LedgerCapabilityAxis),
        ),
        _evidence(
            "evidence.campaign.independent_review",
            EvidenceRole.INDEPENDENT_ENGINEERING_REVIEW,
            frozenset(LedgerCapabilityAxis),
        ),
    )


def _matrix(
    rows: tuple[LedgerCapabilityRowV1, ...] = (_row(),),
    *,
    report: LedgerLiveCensusReportV1 | None = None,
    controls: LedgerCampaignControlsV1 | None = None,
    campaign_evidence: tuple[EvidenceCoordinateV1, ...] | None = None,
    accepted_denominator: LedgerDenominatorSnapshotV1 | None = None,
    current_denominator: LedgerDenominatorSnapshotV1 | None = None,
    accepted_authority_dispositions: AuthorityDispositionSnapshotV1 | None = None,
    current_authority_dispositions: AuthorityDispositionSnapshotV1 | None = None,
    current_subjects: tuple[EvidenceSubjectSnapshotV1, ...] = (_SUBJECT,),
    ruling: ReviewRuling = ReviewRuling.ACCEPT,
) -> LedgerCapabilityMatrixV1:
    """Build a digest-bound matrix and attestation around the supplied rows."""
    live_report = report if report is not None else _report(tuple(row.identity.row_id for row in rows))
    accepted = accepted_denominator if accepted_denominator is not None else _snapshot(live_report)
    current = current_denominator if current_denominator is not None else _snapshot(live_report)
    accepted_authority = (
        accepted_authority_dispositions
        if accepted_authority_dispositions is not None
        else _authority_snapshot(accepted, rows)
    )
    current_authority = (
        current_authority_dispositions
        if current_authority_dispositions is not None
        else _authority_snapshot(current, rows)
    )
    controls_value = (
        controls
        if controls is not None
        else LedgerCampaignControlsV1(
            sole_ledger_parity_plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
            tui_implementation_hold_recorded=True,
            tui_implementation_hold_active=True,
        )
    )
    evidence = campaign_evidence if campaign_evidence is not None else _campaign_evidence()
    matrix_digest = LedgerCapabilityMatrixV1.calculate_digest(
        schema_version=3,
        controls=controls_value,
        accepted_denominator=accepted,
        current_denominator=current,
        accepted_authority_dispositions=accepted_authority,
        current_authority_dispositions=current_authority,
        current_subjects=current_subjects,
        rows=rows,
        campaign_evidence=evidence,
    )
    attestation = LedgerMatrixAcceptanceAttestationV1(
        attestation_id="attestation.ledger.s02",
        reviewer="independent-engineering-reviewer",
        ruling=ruling,
        plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
        matrix_digest=matrix_digest,
        denominator_digest=current.digest,
        denominator_revision=current.revision,
        review_subject_id=_SUBJECT.subject_id,
        review_subject_revision=_SUBJECT.revision,
        review_subject_digest=_SUBJECT.digest,
        review_subject_observed_at=_SUBJECT.observed_at,
        attested_at=_OBSERVED_AT,
    )
    return LedgerCapabilityMatrixV1(
        schema_version=3,
        controls=controls_value,
        accepted_denominator=accepted,
        current_denominator=current,
        accepted_authority_dispositions=accepted_authority,
        current_authority_dispositions=current_authority,
        current_subjects=current_subjects,
        rows=rows,
        campaign_evidence=evidence,
        matrix_digest=matrix_digest,
        acceptance_attestation=attestation,
    )


def _matrix_with(
    matrix: LedgerCapabilityMatrixV1,
    *,
    recompute_digest: bool = True,
    bind_attestation: bool = True,
    **updates: object,
) -> LedgerCapabilityMatrixV1:
    """Apply a deliberate model-copy mutation and optionally rebind its digest."""
    candidate = matrix.model_copy(update=updates)
    if recompute_digest:
        candidate = candidate.model_copy(update={"matrix_digest": candidate.calculated_matrix_digest})
    if bind_attestation:
        attestation = candidate.acceptance_attestation.model_copy(
            update={
                "matrix_digest": candidate.matrix_digest,
                "denominator_digest": candidate.current_denominator.digest,
                "denominator_revision": candidate.current_denominator.revision,
            }
        )
        candidate = candidate.model_copy(update={"acceptance_attestation": attestation})
    return candidate


def _row_with_assessments(
    row: LedgerCapabilityRowV1,
    replacements: dict[LedgerCapabilityAxis, AxisAssessmentV1],
    *,
    findings: tuple[CapabilityFindingV1, ...] | None = None,
    annotations: frozenset[CapabilityAnnotation] | None = None,
    authority_migration: AuthorityMigrationHistoryV1 | None = None,
    delegates: bool | None = None,
) -> LedgerCapabilityRowV1:
    """Mutate nested axis models while keeping the model-copy attack explicit."""
    assessments = tuple(replacements.get(assessment.axis, assessment) for assessment in row.assessments)
    updates: dict[str, object] = {"assessments": assessments}
    if findings is not None:
        updates["findings"] = findings
    if annotations is not None:
        updates["annotations"] = annotations
    if authority_migration is not None:
        updates["authority_migration"] = authority_migration
    if delegates is not None:
        updates["cli_delegates_to_canonical"] = delegates
    return row.model_copy(update=updates)


def _evaluate(
    matrix: LedgerCapabilityMatrixV1,
    gate: LedgerGate,
    *,
    report: LedgerLiveCensusReportV1 | None = None,
    subjects: tuple[EvidenceSubjectSnapshotV1, ...] = (_SUBJECT,),
):
    """Evaluate a matrix against a fresh report unless a test supplies one."""
    observed = report if report is not None else _report(tuple(row.identity.row_id for row in matrix.rows))
    return evaluate_ledger_capability_gate(
        matrix,
        gate,
        observed_census=observed,
        observed_subjects=subjects,
    )


def test_a_stable_identity_keeps_the_suboperation_as_the_row_key() -> None:
    identity = LedgerCapabilityIdentityV1(
        capability_id="ledger.entries",
        operation_id="ledger.entries.list",
        suboperation_id="ledger.entries.list.page",
    )

    assert identity.row_id == "ledger.entries.list.page"
    assert identity.capability_id == "ledger.entries"


@pytest.mark.parametrize(
    ("operation_id", "suboperation_id"),
    [
        pytest.param("ledger.other.list", "ledger.other.list", id="operation-leaves-family"),
        pytest.param("ledger.entries.list", "ledger.other.list", id="suboperation-leaves-operation"),
        pytest.param("ledger.entries", "ledger.entries", id="operation-equals-family"),
    ],
)
def test_an_identity_cannot_change_family_or_operation(
    operation_id: str,
    suboperation_id: str,
) -> None:
    with pytest.raises(ValidationError, match="child"):
        LedgerCapabilityIdentityV1(
            capability_id="ledger.entries",
            operation_id=operation_id,
            suboperation_id=suboperation_id,
        )


def test_matrix_digest_is_independent_of_row_order() -> None:
    first = _row()
    second = _row("ledger.reconciliation.match", prefix="reconciliation_match")
    report = _report((_ROW_ID, "ledger.reconciliation.match"))
    matrix = _matrix(rows=(first, second), report=report)

    reordered = _matrix_with(matrix, rows=(second, first))

    assert reordered.matrix_digest == matrix.matrix_digest
    assert _evaluate(reordered, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=report).closed


def test_a_matrix_rejects_duplicate_stable_rows_before_a_gate_can_close() -> None:
    row = _row()
    report = _report((_ROW_ID,))
    denominator = _snapshot(report)
    authority = _authority_snapshot(denominator, (row,))
    with pytest.raises(ValidationError, match="duplicate row identities"):
        _matrix(
            rows=(row, row),
            report=report,
            accepted_authority_dispositions=authority,
            current_authority_dispositions=authority,
        )


def test_a_complete_census_contains_each_stream_and_explicit_zeroes() -> None:
    report = _report()

    assert {stream.source for stream in report.streams} == set(DenominatorSourceKind)
    assert len(report.streams) == 7
    assert report.capability_ids == frozenset({_ROW_ID})
    assert report.denominator_entries[0].sources == frozenset({DenominatorSourceKind.CLI_ENDPOINT})
    assert sum(not stream.capability_ids and stream.reviewed_zero for stream in report.streams) == 6
    assert report.readiness_errors == ()


def test_census_fixture_preserves_explicit_empty_inputs_instead_of_defaulting() -> None:
    with pytest.raises(ValidationError, match="every mandatory source stream"):
        _report(streams=())
    with pytest.raises(ValidationError, match="cannot be empty"):
        _report(())


def test_explicit_empty_census_streams_reopen_g0_at_the_gate_boundary() -> None:
    empty_report = _unchecked_empty_report()

    assert all(not stream.capability_ids and stream.reviewed_zero for stream in empty_report.streams)
    assessment = _evaluate(_matrix(), LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=empty_report)

    assert assessment.blockers == ("live census validation failed at <root>: value_error",)


def test_a_census_rejects_missing_or_duplicate_mandatory_streams() -> None:
    report = _report()
    missing = report.model_copy(update={"streams": report.streams[:-1]})
    duplicate = report.model_copy(update={"streams": (*report.streams[:-1], report.streams[0])})

    for candidate in (missing, duplicate):
        with pytest.raises(ValidationError, match="every mandatory source stream"):
            LedgerLiveCensusReportV1.model_validate(candidate.model_dump(mode="python"))


def test_an_empty_stream_requires_an_explicit_reviewed_zero() -> None:
    with pytest.raises(ValidationError, match="explicit reviewed zero"):
        _stream(DenominatorSourceKind.BACKEND_ONLY, reviewed_zero=False)


def test_a_nonempty_stream_cannot_claim_reviewed_zero() -> None:
    with pytest.raises(ValidationError, match="nonempty census stream"):
        _stream(DenominatorSourceKind.BACKEND_ONLY, (_ROW_ID,), reviewed_zero=True)


def test_an_unreadable_or_partial_stream_reopens_the_denominator_gate() -> None:
    report = _report()
    broken_streams = tuple(
        _stream(
            stream.source,
            stream.capability_ids,
            scan_succeeded=False if stream.source is DenominatorSourceKind.CLI_ENDPOINT else stream.scan_succeeded,
            complete=False if stream.source is DenominatorSourceKind.BACKEND_ONLY else stream.complete,
        )
        for stream in report.streams
    )
    broken = _report(streams=broken_streams)
    matrix = _matrix(report=report)

    blockers = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=broken).blockers

    assert any("did not scan successfully" in blocker for blocker in blockers)
    assert any("is partial" in blocker for blocker in blockers)


def test_a_new_live_capability_and_source_classification_are_drift() -> None:
    accepted_report = _report()
    accepted = _snapshot(accepted_report)
    added_report = _report((_ROW_ID, "ledger.entries.export"))
    added = _snapshot(added_report)

    reopened = reopened_gates_for_denominator_drift(accepted, added)

    assert reopened == frozenset(LedgerGate)
    assert any(
        "new live denominator capability" in line
        for line in _evaluate(
            _matrix(report=accepted_report),
            LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE,
            report=added_report,
        ).blockers
    )


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        pytest.param("revision", "census-rev-2", "denominator revision drifted", id="revision"),
        pytest.param("observed_at", _LATER_OBSERVED_AT, "denominator observation time drifted", id="time"),
    ],
)
def test_denominator_generation_revision_and_time_are_currentness_inputs(
    field: str,
    value: object,
    expected: str,
) -> None:
    accepted_report = _report()
    updates = {field: value}
    current_report = _report(**updates)
    matrix = _matrix(report=accepted_report)

    blockers = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=current_report).blockers

    assert expected in blockers


@pytest.mark.parametrize(
    ("recorded", "active"),
    [
        pytest.param(False, True, id="not-recorded"),
        pytest.param(True, False, id="inactive"),
    ],
)
def test_g0_rejects_each_invalid_tui_hold_state(recorded: bool, active: bool) -> None:
    controls = LedgerCampaignControlsV1(
        sole_ledger_parity_plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
        tui_implementation_hold_recorded=recorded,
        tui_implementation_hold_active=active,
    )
    matrix = _matrix(controls=controls)

    assert _evaluate(_matrix(), LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).closed
    blockers = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers

    assert blockers == ("the Ledger TUI implementation hold is not recorded and active",)


def test_g0_rejects_a_removed_observed_capability() -> None:
    first = _row()
    second = _row("ledger.reconciliation.match", prefix="reconciliation_match")
    accepted_report = _report((_ROW_ID, "ledger.reconciliation.match"))
    matrix = _matrix(rows=(first, second), report=accepted_report)
    removed_report = _report((_ROW_ID,))

    assert _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=accepted_report).closed
    blockers = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=removed_report).blockers

    assert "accepted denominator capability missing from current census: ledger.reconciliation.match" in blockers


def test_g0_rejects_same_id_denominator_source_classification_drift() -> None:
    def streams_with_owner(owner: DenominatorSourceKind) -> tuple[CensusStreamObservationV1, ...]:
        return tuple(_stream(source, (_ROW_ID,) if source is owner else ()) for source in DenominatorSourceKind)

    accepted_report = _report(streams=streams_with_owner(DenominatorSourceKind.CLI_ENDPOINT))
    drifted_report = _report(streams=streams_with_owner(DenominatorSourceKind.BACKEND_ONLY))
    matrix = _matrix(report=accepted_report)

    assert _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=accepted_report).closed
    blockers = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=drifted_report).blockers

    assert f"denominator source classification drifted: {_ROW_ID}" in blockers


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("identity", id="identity"),
        pytest.param("digest", id="digest"),
        pytest.param("revision", id="revision"),
        pytest.param("time", id="time"),
    ],
)
def test_g0_rejects_each_independent_census_generation_mutation(mutation: str) -> None:
    matrix = _matrix()
    baseline = _report()
    if mutation == "identity":
        drifted = _report(census_id="census.ledger.drifted")
        expected = "accepted and current denominator census identities differ"
    elif mutation == "digest":
        drifted = baseline.model_copy(update={"digest": "sha256:" + "c" * 64})
        expected = "live census validation failed"
    elif mutation == "revision":
        drifted = _report(revision="census-rev-2")
        expected = "denominator revision drifted"
    else:
        drifted = _report(observed_at=_LATER_OBSERVED_AT)
        expected = "denominator observation time drifted"

    assert _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=baseline).closed
    blockers = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=drifted).blockers

    assert any(expected in blocker for blocker in blockers)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        pytest.param("readable", False, "is unreadable", id="unreadable"),
        pytest.param("ambiguous", True, "is ambiguous", id="ambiguous"),
        pytest.param("scan_succeeded", False, "did not scan successfully", id="failed"),
        pytest.param("complete", False, "is partial", id="incomplete"),
    ],
)
def test_g0_rejects_each_unready_census_stream(
    field: str,
    value: bool,
    expected: str,
) -> None:
    baseline = _report()
    stream = baseline.streams[0]
    flags = {
        "scan_succeeded": stream.scan_succeeded,
        "readable": stream.readable,
        "complete": stream.complete,
        "ambiguous": stream.ambiguous,
    }
    flags[field] = value
    mutated_stream = _stream(
        stream.source,
        stream.capability_ids,
        revision=stream.revision,
        observed_at=stream.observed_at,
        **flags,
    )
    drifted = _report(streams=(mutated_stream, *baseline.streams[1:]))
    matrix = _matrix(report=baseline)

    assert _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=baseline).closed
    blockers = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=drifted).blockers

    assert any(expected in blocker for blocker in blockers)


def test_g0_rejects_a_missing_census_stream_at_the_gate_boundary() -> None:
    baseline = _report()
    invalid = baseline.model_copy(update={"streams": baseline.streams[:-1]})
    matrix = _matrix(report=baseline)

    assert _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=baseline).closed
    blockers = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=invalid).blockers

    assert blockers == ("live census validation failed at <root>: value_error",)


def test_g0_accepts_explicit_reviewed_zero_census_streams() -> None:
    report = _report()
    matrix = _matrix(report=report)

    assert all(not stream.capability_ids and stream.reviewed_zero for stream in report.streams[1:])
    assert _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=report).closed


def test_currentness_requires_nonempty_observed_subjects() -> None:
    matrix = _matrix()

    currentness = validate_ledger_matrix_currentness(
        matrix,
        observed_census=_report(),
        observed_subjects=(),
    )

    assert currentness == [
        "live evidence-subject observation is empty",
        "matrix evidence subject no longer observed: subject.ledger.matrix",
    ]
    assert not _evaluate(
        matrix,
        LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE,
        subjects=(),
    ).closed


def test_currentness_rejects_duplicate_or_changed_subject_observations() -> None:
    matrix = _matrix()
    changed = _subject(revision="matrix-rev-2", digest="sha256:" + "b" * 64)

    duplicate_errors = validate_ledger_matrix_currentness(
        matrix,
        observed_census=_report(),
        observed_subjects=(_SUBJECT, _SUBJECT),
    )
    changed_errors = validate_ledger_matrix_currentness(
        matrix,
        observed_census=_report(),
        observed_subjects=(changed,),
    )

    assert duplicate_errors == ["live evidence-subject observation contains duplicate identities"]
    assert changed_errors == ["evidence subject freshness drifted: subject.ledger.matrix"]


def test_currentness_revalidates_a_malformed_copied_subject_without_value_leakage() -> None:
    malformed = _SUBJECT.model_copy(update={"digest": "subject-secret-not-a-digest"})

    errors = validate_ledger_matrix_currentness(
        _matrix(),
        observed_census=_report(),
        observed_subjects=(malformed,),
    )

    assert errors == ["observed subjects validation failed at 0: value_error"]
    assert all("subject-secret-not-a-digest" not in error for error in errors)


def test_one_gate_revalidates_malformed_copied_subject_and_nested_authority_graph_deterministically() -> None:
    matrix = _matrix()
    malformed_subject = _SUBJECT.model_copy(update={"digest": "subject-secret-not-a-digest"})
    authority_entry = matrix.current_authority_dispositions.entries[0].model_copy(update={"row_id": "authority-secret"})
    malformed_authority = matrix.current_authority_dispositions.model_copy(update={"entries": (authority_entry,)})
    candidate = _matrix_with(matrix, current_authority_dispositions=malformed_authority)

    first = _evaluate(
        candidate,
        LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE,
        subjects=(malformed_subject,),
    ).blockers
    second = _evaluate(
        candidate,
        LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE,
        subjects=(malformed_subject,),
    ).blockers

    assert first == second
    assert first
    assert any("observed subjects validation failed" in blocker for blocker in first)
    assert any("matrix validation failed" in blocker for blocker in first)
    assert all(
        secret not in blocker for blocker in first for secret in ("subject-secret-not-a-digest", "authority-secret")
    )


def test_currentness_and_ordered_gates_reject_a_malformed_copied_nested_authority_graph() -> None:
    matrix = _matrix()
    authority_entry = matrix.current_authority_dispositions.entries[0].model_copy(update={"row_id": "authority-secret"})
    malformed_authority = matrix.current_authority_dispositions.model_copy(update={"entries": (authority_entry,)})
    malformed_matrix = matrix.model_copy(update={"current_authority_dispositions": malformed_authority})

    first = validate_ledger_matrix_currentness(
        malformed_matrix,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
    )
    second = validate_ledger_matrix_currentness(
        malformed_matrix,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
    )
    assessments = evaluate_ledger_capability_gates(
        malformed_matrix,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
    )

    assert _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).closed
    assert first == second
    assert first
    assert any("matrix validation failed" in blocker for blocker in first)
    assert all("authority-secret" not in blocker for blocker in first)
    assert len(assessments) == len(LedgerGate)
    assert all(not assessment.closed for assessment in assessments)
    assert all(assessment.blockers == tuple(first) for assessment in assessments)


def test_each_axis_has_a_reviewed_rationale_and_single_axis_applicability_proof() -> None:
    row = _row()

    assert {assessment.axis for assessment in row.assessments} == set(LedgerCapabilityAxis)
    for assessment in row.assessments:
        assert assessment.applicability_rationale
        assert assessment.applicability_review_evidence.role is EvidenceRole.APPLICABILITY_REVIEW
        assert assessment.applicability_review_evidence.axes == frozenset({assessment.axis})


def test_an_axis_cannot_hide_a_blank_rationale_or_wrong_review_axis() -> None:
    assessment = _row().assessment(LedgerCapabilityAxis.BACKEND)
    blank = assessment.model_copy(update={"applicability_rationale": "unknown"})
    wrong_axis = assessment.model_copy(
        update={
            "applicability_review_evidence": assessment.applicability_review_evidence.model_copy(
                update={"axes": frozenset({LedgerCapabilityAxis.CLI})}
            )
        }
    )

    with pytest.raises(ValidationError, match="bounded"):
        AxisAssessmentV1.model_validate(blank.model_dump(mode="python"))
    with pytest.raises(ValidationError, match="applicability-review"):
        AxisAssessmentV1.model_validate(wrong_axis.model_dump(mode="python"))


def test_non_applicable_axes_have_no_operational_proof_or_evidence() -> None:
    review = _evidence(
        "evidence.invalid.applicability.backend",
        EvidenceRole.APPLICABILITY_REVIEW,
        frozenset({LedgerCapabilityAxis.BACKEND}),
    )
    operational = _evidence(
        "evidence.invalid.operational.backend",
        EvidenceRole.BASELINE,
        frozenset({LedgerCapabilityAxis.BACKEND}),
    )

    with pytest.raises(ValidationError, match="no operational proof or evidence"):
        AxisAssessmentV1(
            axis=LedgerCapabilityAxis.BACKEND,
            applicability=ApplicabilityState.NOT_APPLICABLE,
            applicability_rationale="The backend is outside this test.",
            applicability_review_evidence=review,
            proof=AxisProofState.NOT_APPLICABLE,
            surface_state=SurfaceCapabilityState.NOT_APPLICABLE,
            evidence=(operational,),
        )


@pytest.mark.parametrize(
    ("proof", "surface_state"),
    [
        pytest.param(AxisProofState.UNPROVEN, SurfaceCapabilityState.PROVEN, id="unproven-proof"),
        pytest.param(AxisProofState.PROVEN, SurfaceCapabilityState.PARTIAL, id="partial-surface"),
        pytest.param(AxisProofState.PROVEN, SurfaceCapabilityState.ABSENT, id="absent-surface"),
    ],
)
def test_an_incomplete_applicable_axis_requires_an_affected_finding(
    proof: AxisProofState,
    surface_state: SurfaceCapabilityState,
) -> None:
    row = _row()
    backend = row.assessment(LedgerCapabilityAxis.BACKEND).model_copy(
        update={"proof": proof, "surface_state": surface_state}
    )
    incomplete = _row_with_assessments(row, {LedgerCapabilityAxis.BACKEND: backend})

    with pytest.raises(ValidationError, match="no affected-axis finding"):
        LedgerCapabilityRowV1.model_validate(incomplete.model_dump(mode="python"))


def test_a_bounded_finding_makes_an_incomplete_axis_classified_work() -> None:
    row = _row()
    backend = row.assessment(LedgerCapabilityAxis.BACKEND).model_copy(update={"proof": AxisProofState.UNPROVEN})
    finding = CapabilityFindingV1(
        finding_id="finding.entries.backend_proof",
        gap_class=LedgerGapClass.PROOF,
        affected_axes=frozenset({LedgerCapabilityAxis.BACKEND}),
        description="Direct backend behavior has not been accepted yet.",
        next_closure_action="Add a real-store backend behavior test and link its result.",
    )

    classified = _row_with_assessments(row, {LedgerCapabilityAxis.BACKEND: backend}, findings=(finding,))

    assert classified.assessment(LedgerCapabilityAxis.BACKEND).needs_finding
    assert classified.has_gap(LedgerGapClass.PROOF, axis=LedgerCapabilityAxis.BACKEND)


def test_an_all_non_applicable_row_is_not_a_denominator_placeholder() -> None:
    row = _row()
    assessments = tuple(
        assessment.model_copy(
            update={
                "applicability": ApplicabilityState.NOT_APPLICABLE,
                "proof": AxisProofState.NOT_APPLICABLE,
                "surface_state": (
                    SurfaceCapabilityState.NOT_APPLICABLE
                    if assessment.axis
                    in {
                        LedgerCapabilityAxis.BACKEND,
                        LedgerCapabilityAxis.CLI,
                        LedgerCapabilityAxis.TUI,
                    }
                    else None
                ),
                "evidence": (),
            }
        )
        for assessment in row.assessments
    )
    placeholder = row.model_copy(
        update={"assessments": assessments, "annotations": frozenset(), "cli_delegates_to_canonical": False}
    )

    with pytest.raises(ValidationError, match="content-free"):
        LedgerCapabilityRowV1.model_validate(placeholder.model_dump(mode="python"))


@pytest.mark.parametrize(
    ("role", "kind", "axes", "message"),
    [
        pytest.param(
            EvidenceRole.BASELINE,
            EvidenceKind.REVIEW,
            frozenset({LedgerCapabilityAxis.BACKEND}),
            "invalid kind",
            id="baseline-kind",
        ),
        pytest.param(
            EvidenceRole.DIRECT_BACKEND_BEHAVIOR,
            EvidenceKind.TEST,
            frozenset({LedgerCapabilityAxis.CLI}),
            "exactly",
            id="backend-axis",
        ),
        pytest.param(
            EvidenceRole.ADAPTER_DETECTOR,
            EvidenceKind.TEST,
            frozenset({LedgerCapabilityAxis.BACKEND}),
            "exactly",
            id="adapter-axis",
        ),
        pytest.param(
            EvidenceRole.TUI_PARITY,
            EvidenceKind.TEST,
            frozenset({LedgerCapabilityAxis.BACKEND}),
            "exactly",
            id="tui-parity-axes",
        ),
        pytest.param(
            EvidenceRole.INDEPENDENT_ENGINEERING_REVIEW,
            EvidenceKind.REFERENCE,
            frozenset(LedgerCapabilityAxis),
            "invalid kind",
            id="review-kind",
        ),
    ],
)
def test_evidence_enforces_role_kind_and_axis_contract(
    role: EvidenceRole,
    kind: EvidenceKind,
    axes: frozenset[LedgerCapabilityAxis],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        _evidence("evidence.invalid.role_contract", role, axes, kind=kind)


def test_evidence_currentness_binds_id_revision_digest_time_and_locator() -> None:
    coordinate = _evidence(
        "evidence.currentness.backend",
        EvidenceRole.BASELINE,
        frozenset({LedgerCapabilityAxis.BACKEND}),
    )
    drifted = _subject(locator="reference://clitui-ledger/other")

    assert coordinate.is_current_against(_SUBJECT)
    assert not coordinate.is_current_against(drifted)


def test_evidence_ids_are_unique_across_rows_and_campaign_scope() -> None:
    matrix = _matrix()
    duplicate_campaign = matrix.campaign_evidence[0].model_copy(
        update={"evidence_id": matrix.rows[0].assessments[0].applicability_review_evidence.evidence_id}
    )
    candidate = _matrix_with(matrix, campaign_evidence=(duplicate_campaign, *matrix.campaign_evidence[1:]))

    assessment = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE)

    assert not assessment.closed
    assert any("validation failed" in blocker for blocker in assessment.blockers)
    with pytest.raises(ValidationError, match="globally unique"):
        LedgerCapabilityMatrixV1.model_validate(candidate.model_dump(mode="python"))


def test_evidence_ids_are_unique_across_two_denominator_rows() -> None:
    first = _row()
    second = _row("ledger.reconciliation.match", prefix="reconciliation_match")
    matrix = _matrix(rows=(first, second))
    duplicate_review = second.assessments[0].applicability_review_evidence.model_copy(
        update={"evidence_id": first.assessments[0].applicability_review_evidence.evidence_id}
    )
    second_with_duplicate = _row_with_assessments(
        second,
        {
            LedgerCapabilityAxis.BACKEND: second.assessment(LedgerCapabilityAxis.BACKEND),
        },
    ).model_copy(
        update={
            "assessments": (
                second.assessments[0].model_copy(update={"applicability_review_evidence": duplicate_review}),
                *second.assessments[1:],
            )
        }
    )
    candidate = _matrix_with(matrix, rows=(first, second_with_duplicate))

    assessment = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE)

    assert not assessment.closed
    assert any("validation failed" in blocker for blocker in assessment.blockers)
    with pytest.raises(ValidationError, match="globally unique"):
        LedgerCapabilityMatrixV1.model_validate(candidate.model_dump(mode="python"))


def test_stale_nested_evidence_is_refused_at_the_matrix_boundary() -> None:
    matrix = _matrix()
    backend = matrix.rows[0].assessment(LedgerCapabilityAxis.BACKEND)
    stale_coordinate = backend.evidence[0].model_copy(update={"subject_digest": "sha256:" + "b" * 64})
    stale_backend = backend.model_copy(update={"evidence": (stale_coordinate, *backend.evidence[1:])})
    stale_row = _row_with_assessments(matrix.rows[0], {LedgerCapabilityAxis.BACKEND: stale_backend})
    candidate = _matrix_with(matrix, rows=(stale_row,))

    assessment = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE)

    assert not assessment.closed
    assert any("validation failed" in blocker for blocker in assessment.blockers)


def test_a_migrated_cli_owned_row_needs_direct_backend_and_adapter_detector_proof() -> None:
    row = _row()
    backend = row.assessment(LedgerCapabilityAxis.BACKEND)
    cli = row.assessment(LedgerCapabilityAxis.CLI)
    missing_backend = backend.model_copy(
        update={
            "evidence": tuple(
                item for item in backend.evidence if item.role is not EvidenceRole.DIRECT_BACKEND_BEHAVIOR
            )
        }
    )
    missing_detector = cli.model_copy(
        update={"evidence": tuple(item for item in cli.evidence if item.role is not EvidenceRole.ADAPTER_DETECTOR)}
    )
    mutated = _row_with_assessments(
        row,
        {
            LedgerCapabilityAxis.BACKEND: missing_backend,
            LedgerCapabilityAxis.CLI: missing_detector,
        },
    )
    matrix = _matrix(rows=(mutated,))

    blockers = _evaluate(matrix, LedgerGate.G1_SEMANTIC_AUTHORITY_RECOVERY).blockers

    assert any("direct backend behavior" in blocker for blocker in blockers)
    assert any("adapter detector" in blocker for blocker in blockers)


def test_an_incomplete_cli_owned_migration_retains_an_authority_finding() -> None:
    finding = CapabilityFindingV1(
        finding_id="finding.entries.cli_authority",
        gap_class=LedgerGapClass.AUTHORITY,
        affected_axes=frozenset({LedgerCapabilityAxis.CLI}),
        description="The CLI still owns query policy.",
        next_closure_action="Move the policy to the canonical application query.",
    )
    row = _row(migration_completed=False, findings=(finding,))
    row = row.model_copy(
        update={
            "annotations": frozenset({CapabilityAnnotation.CLI_OWNED, CapabilityAnnotation.INSTALLED}),
            "cli_delegates_to_canonical": False,
        }
    )
    matrix = _matrix(rows=(row,))

    assessment = _evaluate(matrix, LedgerGate.G1_SEMANTIC_AUTHORITY_RECOVERY)

    assert not assessment.closed
    assert any("migration is incomplete" in blocker for blocker in assessment.blockers)
    assert any("cli_owned annotation remains" in blocker for blocker in assessment.blockers)
    assert any("authority finding remains" in blocker for blocker in assessment.blockers)


@pytest.mark.parametrize(
    "updates",
    [
        pytest.param(
            {
                "annotations": frozenset({CapabilityAnnotation.DELEGATING, CapabilityAnnotation.INSTALLED}),
                "cli_delegates_to_canonical": False,
            },
            id="delegating-without-boolean",
        ),
        pytest.param(
            {
                "annotations": frozenset({CapabilityAnnotation.CLI_OWNED, CapabilityAnnotation.INSTALLED}),
                "cli_delegates_to_canonical": True,
            },
            id="owned-and-delegating",
        ),
    ],
)
def test_authority_annotations_and_delegation_are_consistent(
    updates: dict[str, object],
) -> None:
    row = _row().model_copy(update=updates)

    with pytest.raises(ValidationError, match=r"delegat|cli_owned"):
        LedgerCapabilityRowV1.model_validate(row.model_dump(mode="python"))


def test_erasing_initial_cli_ownership_reopens_g0_even_when_current_rows_look_clean() -> None:
    matrix = _matrix()
    row = matrix.rows[0].model_copy(
        update={
            "authority_migration": AuthorityMigrationHistoryV1(
                initial_cli_ownership=InitialCliOwnership.NOT_CLI_OWNED,
                migration_completed=False,
            ),
            "annotations": frozenset({CapabilityAnnotation.INSTALLED}),
            "cli_delegates_to_canonical": False,
        }
    )
    current_authority = _authority_snapshot(matrix.current_denominator, (row,))
    candidate = _matrix_with(matrix, rows=(row,), current_authority_dispositions=current_authority)

    assessments = evaluate_ledger_capability_gates(
        candidate,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
    )

    assert not assessments[0].closed
    assert any("immutable initial CLI ownership drifted" in blocker for blocker in assessments[0].blockers)
    assert not assessments[1].closed
    assert any("earlier gate remains open" in blocker for blocker in assessments[1].blockers)


def test_g0_rejects_authority_snapshot_membership_drift() -> None:
    first = _row()
    second = _row("ledger.reconciliation.match", prefix="reconciliation_match")
    accepted_report = _report((_ROW_ID,))
    current_report = _report((_ROW_ID, "ledger.reconciliation.match"))
    accepted_denominator = _snapshot(accepted_report)
    current_denominator = _snapshot(current_report)
    matrix = _matrix(
        rows=(first, second),
        accepted_denominator=accepted_denominator,
        current_denominator=current_denominator,
        accepted_authority_dispositions=_authority_snapshot(accepted_denominator, (first,)),
        current_authority_dispositions=_authority_snapshot(current_denominator, (first, second)),
    )

    assert _evaluate(_matrix(), LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).closed
    assert not _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).closed
    assert any(
        "new authority disposition row: ledger.reconciliation.match" in blocker
        for blocker in _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers
    )


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        pytest.param("revision", "authority-rev-2", "authority disposition revision drifted", id="revision"),
        pytest.param("observed_at", _LATER_OBSERVED_AT, "authority disposition observation time drifted", id="time"),
    ],
)
def test_g0_rejects_each_authority_snapshot_generation_mutation(
    field: str,
    value: object,
    expected: str,
) -> None:
    matrix = _matrix()
    updates = {field: value}
    drifted = _authority_snapshot_with(matrix.current_authority_dispositions, **updates)
    candidate = _matrix_with(matrix, current_authority_dispositions=drifted)

    assert _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).closed
    blockers = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers

    assert expected in blockers


def test_g0_accepts_only_the_canonical_owner_and_digest_bound_accept_ruling() -> None:
    matrix = _matrix()

    assert _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).closed

    wrong_ruling = matrix.acceptance_attestation.model_copy(
        update={"ruling": ReviewRuling.ACCEPT_WITH_REQUIRED_CHANGES}
    )
    non_accepting = matrix.model_copy(update={"acceptance_attestation": wrong_ruling})
    assert "ACCEPT attestation" in " ".join(
        _evaluate(non_accepting, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers
    )


def test_g0_rejects_a_proven_applicable_axis_without_exact_baseline_evidence() -> None:
    matrix = _matrix()
    composition = matrix.rows[0].assessment(LedgerCapabilityAxis.COMPOSITION)
    without_baseline = composition.model_copy(
        update={
            "evidence": tuple(
                coordinate for coordinate in composition.evidence if coordinate.role is not EvidenceRole.BASELINE
            )
        }
    )
    row = _row_with_assessments(matrix.rows[0], {LedgerCapabilityAxis.COMPOSITION: without_baseline})
    candidate = _matrix_with(matrix, rows=(row,))

    assert _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).closed
    blockers = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers

    assert blockers == (f"{_ROW_ID}: composition lacks exact baseline evidence",)


def test_g0_rejects_an_attestation_bound_to_an_older_matrix_digest() -> None:
    matrix = _matrix()
    changed_home = matrix.rows[0].semantic_home.model_copy(update={"result_type": "ChangedResult"})
    changed_row = matrix.rows[0].model_copy(update={"semantic_home": changed_home})
    stale_attestation = matrix.acceptance_attestation.model_copy(update={"matrix_digest": "sha256:" + "b" * 64})
    candidate = matrix.model_copy(update={"rows": (changed_row,), "acceptance_attestation": stale_attestation})

    blockers = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers

    assert any("validation failed" in blocker for blocker in blockers)
    assert all("ChangedResult" not in blocker for blocker in blockers)


def test_g0_rejects_a_wrong_owner_and_redacts_the_supplied_owner() -> None:
    matrix = _matrix()
    controls = matrix.controls.model_copy(update={"sole_ledger_parity_plan_owner": "top_secret_owner"})
    candidate = _matrix_with(matrix, controls=controls)

    first = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers
    second = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers

    assert first == second
    assert first
    assert all("top_secret_owner" not in blocker for blocker in first)
    assert all("validation failed" in blocker for blocker in first)


def test_g0_rejects_a_model_copy_with_an_empty_reviewer_deterministically() -> None:
    matrix = _matrix()
    invalid_attestation = matrix.acceptance_attestation.model_copy(update={"reviewer": ""})
    candidate = matrix.model_copy(update={"acceptance_attestation": invalid_attestation})

    first = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers
    second = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers

    assert first == second
    assert first == ("matrix validation failed at acceptance_attestation.reviewer: string_too_short",)


def test_g0_accepts_a_typed_digest_bound_accept_without_generic_review_coordinate() -> None:
    campaign_evidence = tuple(
        coordinate
        for coordinate in _campaign_evidence()
        if coordinate.role is not EvidenceRole.INDEPENDENT_ENGINEERING_REVIEW
    )
    matrix = _matrix(campaign_evidence=campaign_evidence)

    assert not matrix.has_campaign_evidence(EvidenceRole.INDEPENDENT_ENGINEERING_REVIEW)
    assert _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).closed


@pytest.mark.parametrize("attestation_mutation", ["missing", "stale", "non_accept"])
def test_generic_review_coordinate_cannot_substitute_for_a_missing_or_invalid_attestation(
    attestation_mutation: str,
) -> None:
    matrix = _matrix()
    assert matrix.has_campaign_evidence(EvidenceRole.INDEPENDENT_ENGINEERING_REVIEW)
    if attestation_mutation == "missing":
        candidate = matrix.model_copy(update={"acceptance_attestation": None})
    elif attestation_mutation == "stale":
        stale = matrix.acceptance_attestation.model_copy(update={"matrix_digest": "sha256:" + "b" * 64})
        candidate = matrix.model_copy(update={"acceptance_attestation": stale})
    else:
        non_accept = matrix.acceptance_attestation.model_copy(update={"ruling": ReviewRuling.REJECT})
        candidate = matrix.model_copy(update={"acceptance_attestation": non_accept})

    blockers = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers

    assert blockers
    assert not _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).closed
    if attestation_mutation == "non_accept":
        assert "ACCEPT attestation" in " ".join(blockers)
    elif attestation_mutation == "stale":
        assert blockers == ("matrix validation failed at <root>: value_error",)
    else:
        assert any("acceptance_attestation" in blocker for blocker in blockers)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("denominator_digest", "sha256:" + "d" * 64, id="denominator-digest"),
        pytest.param("denominator_revision", "denominator-rev-stale", id="denominator-revision"),
        pytest.param("matrix_digest", "sha256:" + "e" * 64, id="matrix-digest"),
        pytest.param("plan_owner", "attestation-secret-owner", id="plan-owner"),
        pytest.param("review_subject_id", "subject.ledger.missing", id="subject-id"),
        pytest.param("review_subject_revision", "review-rev-stale", id="subject-revision"),
        pytest.param("review_subject_digest", "sha256:" + "f" * 64, id="subject-digest"),
        pytest.param("review_subject_observed_at", _LATER_OBSERVED_AT, id="subject-time"),
    ],
)
def test_g0_rejects_each_attestation_binding_mutation(
    field: str,
    value: object,
) -> None:
    matrix = _matrix()
    attestation = matrix.acceptance_attestation.model_copy(update={field: value})
    candidate = matrix.model_copy(update={"acceptance_attestation": attestation})

    assert _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).closed
    first = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers
    second = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers

    assert first == second
    assert first
    assert any("matrix validation failed" in blocker for blocker in first)
    assert all("attestation-secret-owner" not in blocker for blocker in first)


def test_g2_requires_a_proven_backend_surface_and_direct_behavior() -> None:
    matrix = _matrix()
    backend = (
        matrix.rows[0]
        .assessment(LedgerCapabilityAxis.BACKEND)
        .model_copy(update={"surface_state": SurfaceCapabilityState.PARTIAL})
    )
    finding = CapabilityFindingV1(
        finding_id="finding.entries.backend_product",
        gap_class=LedgerGapClass.PRODUCT,
        affected_axes=frozenset({LedgerCapabilityAxis.BACKEND}),
        description="The backend surface is only partial.",
        next_closure_action="Complete and rerun the direct backend product test.",
    )
    row = _row_with_assessments(matrix.rows[0], {LedgerCapabilityAxis.BACKEND: backend}, findings=(finding,))
    candidate = _matrix_with(matrix, rows=(row,))

    blockers = _evaluate(candidate, LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS).blockers

    assert any("backend is not implemented and proven" in blocker for blocker in blockers)


def test_g2_requires_direct_backend_behavior_even_when_proof_metadata_is_proven() -> None:
    matrix = _matrix()
    backend = matrix.rows[0].assessment(LedgerCapabilityAxis.BACKEND)
    stripped = backend.model_copy(
        update={
            "evidence": tuple(
                item for item in backend.evidence if item.role is not EvidenceRole.DIRECT_BACKEND_BEHAVIOR
            )
        }
    )
    row = _row_with_assessments(matrix.rows[0], {LedgerCapabilityAxis.BACKEND: stripped})
    candidate = _matrix_with(matrix, rows=(row,))

    blockers = _evaluate(candidate, LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS).blockers

    assert any("backend lacks direct behavior evidence" in blocker for blocker in blockers)


@pytest.mark.parametrize(
    "axis",
    [
        pytest.param(LedgerCapabilityAxis.BACKEND, id="backend"),
        pytest.param(LedgerCapabilityAxis.COMPOSITION, id="composition"),
        pytest.param(LedgerCapabilityAxis.ARTIFACT, id="artifact"),
        pytest.param(LedgerCapabilityAxis.PROVENANCE, id="provenance"),
        pytest.param(LedgerCapabilityAxis.REGISTRY, id="registry"),
        pytest.param(LedgerCapabilityAxis.PROOF, id="proof"),
    ],
)
def test_g2_rejects_each_unproven_applicable_axis(axis: LedgerCapabilityAxis) -> None:
    matrix = _matrix()
    assessment = matrix.rows[0].assessment(axis).model_copy(update={"proof": AxisProofState.UNPROVEN})
    finding = CapabilityFindingV1(
        finding_id=f"finding.entries.g2.unproven_{axis.value}",
        gap_class=LedgerGapClass.PROOF,
        affected_axes=frozenset({axis}),
        description=f"The {axis.value} axis is not proven.",
        next_closure_action=f"Provide accepted {axis.value} proof.",
    )
    row = _row_with_assessments(matrix.rows[0], {axis: assessment}, findings=(finding,))
    candidate = _matrix_with(matrix, rows=(row,))

    assert _evaluate(matrix, LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS).closed
    blockers = _evaluate(candidate, LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS).blockers

    if axis is LedgerCapabilityAxis.BACKEND:
        assert f"{_ROW_ID}: backend is not implemented and proven" in blockers
    else:
        assert f"{_ROW_ID}: applicable {axis.value} axis is not proven" in blockers


@pytest.mark.parametrize(
    "gap_class",
    [
        pytest.param(LedgerGapClass.PRODUCT, id="product"),
        pytest.param(LedgerGapClass.COMPOSITION, id="composition"),
        pytest.param(LedgerGapClass.PROOF, id="proof"),
        pytest.param(LedgerGapClass.ARTIFACT, id="artifact"),
        pytest.param(LedgerGapClass.PROVENANCE, id="provenance"),
        pytest.param(LedgerGapClass.REGISTRY, id="registry"),
    ],
)
def test_g2_rejects_each_blocking_gap_class(gap_class: LedgerGapClass) -> None:
    matrix = _matrix()
    finding = CapabilityFindingV1(
        finding_id=f"finding.entries.g2.gap_{gap_class.value}",
        gap_class=gap_class,
        affected_axes=frozenset({LedgerCapabilityAxis.BACKEND}),
        description=f"A {gap_class.value} gap remains.",
        next_closure_action=f"Close the {gap_class.value} gap.",
    )
    row = _row_with_assessments(matrix.rows[0], {}, findings=(finding,))
    candidate = _matrix_with(matrix, rows=(row,))

    assert _evaluate(matrix, LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS).closed
    blockers = _evaluate(candidate, LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS).blockers

    assert f"{_ROW_ID}: {gap_class.value} finding remains" in blockers


def test_g3_requires_cli_success_refusal_and_artifact_evidence() -> None:
    matrix = _matrix()
    cli = matrix.rows[0].assessment(LedgerCapabilityAxis.CLI)
    stripped = cli.model_copy(
        update={
            "evidence": tuple(
                item
                for item in cli.evidence
                if item.role
                not in {
                    EvidenceRole.CLI_SUCCESS,
                    EvidenceRole.CLI_REFUSAL,
                    EvidenceRole.CLI_ARTIFACT,
                }
            )
        }
    )
    row = _row_with_assessments(matrix.rows[0], {LedgerCapabilityAxis.CLI: stripped})
    candidate = _matrix_with(matrix, rows=(row,))

    blockers = _evaluate(candidate, LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS).blockers

    assert any("CLI success behavior" in blocker for blocker in blockers)
    assert any("CLI refusal behavior" in blocker for blocker in blockers)
    assert any("CLI artifact behavior" in blocker for blocker in blockers)


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("surface", id="surface"),
        pytest.param("proof", id="proof"),
        pytest.param("delegation", id="delegation"),
        pytest.param("success", id="success"),
        pytest.param("refusal", id="refusal"),
        pytest.param("artifact", id="artifact"),
    ],
)
def test_g3_rejects_cli_surface_proof_delegation_and_each_behavior_contract(mutation: str) -> None:
    matrix = _matrix()
    assert _evaluate(matrix, LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS).closed
    if mutation == "delegation":
        candidate = _matrix(rows=(_row(initial_cli_ownership=InitialCliOwnership.NOT_CLI_OWNED),))
        expected = "CLI does not delegate to the canonical owner"
    else:
        cli = matrix.rows[0].assessment(LedgerCapabilityAxis.CLI)
        if mutation == "surface":
            cli = cli.model_copy(update={"surface_state": SurfaceCapabilityState.PARTIAL})
            expected = "CLI is not proven through a stable interface contract"
        elif mutation == "proof":
            cli = cli.model_copy(update={"proof": AxisProofState.UNPROVEN})
            expected = "CLI is not proven through a stable interface contract"
        else:
            role = {
                "success": EvidenceRole.CLI_SUCCESS,
                "refusal": EvidenceRole.CLI_REFUSAL,
                "artifact": EvidenceRole.CLI_ARTIFACT,
            }[mutation]
            cli = cli.model_copy(
                update={"evidence": tuple(coordinate for coordinate in cli.evidence if coordinate.role is not role)}
            )
            expected = f"CLI {mutation} behavior is not evidenced"
        findings = ()
        if mutation in {"surface", "proof"}:
            findings = (
                CapabilityFindingV1(
                    finding_id=f"finding.entries.g3.{mutation}",
                    gap_class=LedgerGapClass.PRODUCT,
                    affected_axes=frozenset({LedgerCapabilityAxis.CLI}),
                    description=f"The CLI {mutation} contract is incomplete.",
                    next_closure_action=f"Complete the CLI {mutation} contract.",
                ),
            )
        row = _row_with_assessments(matrix.rows[0], {LedgerCapabilityAxis.CLI: cli}, findings=findings)
        candidate = _matrix_with(matrix, rows=(row,))

    blockers = _evaluate(candidate, LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS).blockers

    assert any(expected in blocker for blocker in blockers)


@pytest.mark.parametrize(
    "gap_class",
    [
        pytest.param(LedgerGapClass.AUTHORITY, id="authority"),
        pytest.param(LedgerGapClass.PRODUCT, id="product"),
        pytest.param(LedgerGapClass.REACHABILITY, id="reachability"),
        pytest.param(LedgerGapClass.ARTIFACT, id="artifact"),
    ],
)
def test_g3_rejects_each_scoped_cli_gap_class(gap_class: LedgerGapClass) -> None:
    matrix = _matrix()
    finding = CapabilityFindingV1(
        finding_id=f"finding.entries.g3.gap_{gap_class.value}",
        gap_class=gap_class,
        affected_axes=frozenset({LedgerCapabilityAxis.CLI}),
        description=f"A CLI {gap_class.value} gap remains.",
        next_closure_action=f"Close the CLI {gap_class.value} gap.",
    )
    row = _row_with_assessments(matrix.rows[0], {}, findings=(finding,))
    candidate = _matrix_with(matrix, rows=(row,))

    assert _evaluate(matrix, LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS).closed
    blockers = _evaluate(candidate, LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS).blockers

    assert f"{_ROW_ID}: CLI {gap_class.value} finding remains" in blockers


def test_g4_scans_findings_on_non_tui_rows_and_other_applicable_axes() -> None:
    matrix = _matrix()
    row = matrix.rows[0]
    tui = row.assessment(LedgerCapabilityAxis.TUI).model_copy(
        update={
            "applicability": ApplicabilityState.NOT_APPLICABLE,
            "proof": AxisProofState.NOT_APPLICABLE,
            "surface_state": SurfaceCapabilityState.NOT_APPLICABLE,
            "evidence": (),
        }
    )
    finding = CapabilityFindingV1(
        finding_id="finding.entries.backend_unresolved",
        gap_class=LedgerGapClass.PRODUCT,
        affected_axes=frozenset({LedgerCapabilityAxis.BACKEND}),
        description="A backend obligation remains unresolved.",
        next_closure_action="Complete the backend operation.",
    )
    mutated = _row_with_assessments(
        row,
        {LedgerCapabilityAxis.TUI: tui},
        findings=(finding,),
        annotations=frozenset({CapabilityAnnotation.DELEGATING}),
    )
    candidate = _matrix_with(
        matrix,
        rows=(mutated,),
        controls=matrix.controls.model_copy(update={"tui_implementation_hold_active": False}),
    )

    assessment = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY)

    assert not assessment.closed
    assert any("blocking product finding" in blocker for blocker in assessment.blockers)


def test_g4_rejects_an_active_tui_hold() -> None:
    matrix = _matrix(
        controls=LedgerCampaignControlsV1(
            sole_ledger_parity_plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
            tui_implementation_hold_recorded=True,
            tui_implementation_hold_active=True,
        )
    )

    assessment = _evaluate(matrix, LedgerGate.G4_TUI_ADMISSION_AND_PARITY)

    assert not assessment.closed
    assert assessment.blockers == ("the Ledger TUI implementation hold remains active",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("proof", AxisProofState.UNPROVEN, id="proof"),
        pytest.param("surface_state", SurfaceCapabilityState.PARTIAL, id="surface"),
    ],
)
def test_g4_rejects_each_incomplete_tui_proof_or_surface(
    field: str,
    value: AxisProofState | SurfaceCapabilityState,
) -> None:
    matrix = _matrix(
        controls=LedgerCampaignControlsV1(
            sole_ledger_parity_plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
            tui_implementation_hold_recorded=True,
            tui_implementation_hold_active=False,
        )
    )
    tui = matrix.rows[0].assessment(LedgerCapabilityAxis.TUI).model_copy(update={field: value})
    finding = CapabilityFindingV1(
        finding_id=f"finding.entries.g4.tui_{field}",
        gap_class=LedgerGapClass.PRODUCT,
        affected_axes=frozenset({LedgerCapabilityAxis.TUI}),
        description=f"The TUI {field} is incomplete.",
        next_closure_action=f"Complete the TUI {field}.",
    )
    row = _row_with_assessments(
        matrix.rows[0],
        {LedgerCapabilityAxis.TUI: tui},
        findings=(finding,),
    )
    candidate = _matrix_with(matrix, rows=(row,))

    assert _evaluate(matrix, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).closed
    blockers = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).blockers

    assert f"{_ROW_ID}: TUI is not proven and installed" in blockers


def test_g4_rejects_a_tui_row_without_the_installed_annotation() -> None:
    matrix = _matrix(
        controls=LedgerCampaignControlsV1(
            sole_ledger_parity_plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
            tui_implementation_hold_recorded=True,
            tui_implementation_hold_active=False,
        )
    )
    row = _row_with_assessments(
        matrix.rows[0],
        {},
        annotations=frozenset({CapabilityAnnotation.DELEGATING}),
    )
    candidate = _matrix_with(matrix, rows=(row,))

    assert _evaluate(matrix, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).closed
    blockers = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).blockers

    assert blockers == (f"{_ROW_ID}: TUI is not marked installed",)


@pytest.mark.parametrize(
    "role",
    [
        pytest.param(EvidenceRole.TUI_PARITY, id="parity"),
        pytest.param(EvidenceRole.TUI_REACHABILITY, id="reachability"),
        pytest.param(EvidenceRole.MATRIX_PUBLICATION, id="publication"),
    ],
)
def test_g4_requires_each_campaign_wide_tui_evidence_role(role: EvidenceRole) -> None:
    controls = LedgerCampaignControlsV1(
        sole_ledger_parity_plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
        tui_implementation_hold_recorded=True,
        tui_implementation_hold_active=False,
    )
    matrix = _matrix(controls=controls)
    campaign_evidence = tuple(coordinate for coordinate in matrix.campaign_evidence if coordinate.role is not role)
    candidate = _matrix(campaign_evidence=campaign_evidence, controls=controls)

    assert _evaluate(matrix, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).closed
    blockers = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).blockers

    assert blockers == (f"campaign-wide {role.value} evidence is missing",)


def test_g4_preserves_explicitly_empty_campaign_evidence() -> None:
    controls = LedgerCampaignControlsV1(
        sole_ledger_parity_plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
        tui_implementation_hold_recorded=True,
        tui_implementation_hold_active=False,
    )
    candidate = _matrix(campaign_evidence=(), controls=controls)

    blockers = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).blockers

    assert blockers == (
        "campaign-wide tui_parity evidence is missing",
        "campaign-wide tui_reachability evidence is missing",
        "campaign-wide matrix_publication evidence is missing",
    )


def test_g4_scans_findings_for_every_applicable_axis_on_every_row() -> None:
    controls = LedgerCampaignControlsV1(
        sole_ledger_parity_plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
        tui_implementation_hold_recorded=True,
        tui_implementation_hold_active=False,
    )

    def findings(prefix: str) -> tuple[CapabilityFindingV1, ...]:
        return tuple(
            CapabilityFindingV1(
                finding_id=f"finding.{prefix}.g4.{axis.value}",
                gap_class=LedgerGapClass.PRODUCT,
                affected_axes=frozenset({axis}),
                description=f"The {axis.value} obligation remains.",
                next_closure_action=f"Close the {axis.value} obligation.",
            )
            for axis in LedgerCapabilityAxis
        )

    first = _row(findings=findings("entries"))
    second = _row("ledger.reconciliation.match", prefix="reconciliation_match", findings=findings("reconciliation"))
    clean = _matrix(controls=controls)
    assert _evaluate(clean, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).closed
    candidate = _matrix(rows=(first, second), controls=controls)

    blockers = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).blockers

    assert len(blockers) == 2 * len(LedgerCapabilityAxis)
    assert blockers.count(f"{first.identity.row_id}: blocking product finding remains") == len(LedgerCapabilityAxis)
    assert blockers.count(f"{second.identity.row_id}: blocking product finding remains") == len(LedgerCapabilityAxis)


def test_valid_controls_close_g0_through_g3_and_lifted_hold_closes_g4() -> None:
    matrix = _matrix(
        controls=LedgerCampaignControlsV1(
            sole_ledger_parity_plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
            tui_implementation_hold_recorded=True,
            tui_implementation_hold_active=False,
        )
    )

    g0 = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE)
    g1 = _evaluate(matrix, LedgerGate.G1_SEMANTIC_AUTHORITY_RECOVERY)
    g2 = _evaluate(matrix, LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS)
    g3 = _evaluate(matrix, LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS)
    g4 = _evaluate(matrix, LedgerGate.G4_TUI_ADMISSION_AND_PARITY)

    assert not g0.closed
    assert "hold is not recorded and active" in " ".join(g0.blockers)
    assert g1.closed
    assert g2.closed
    assert g3.closed
    assert g4.closed


def test_ordered_evaluation_never_allows_a_later_gate_to_close() -> None:
    matrix = _matrix(
        controls=LedgerCampaignControlsV1(
            sole_ledger_parity_plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
            tui_implementation_hold_recorded=True,
            tui_implementation_hold_active=False,
        )
    )
    drifted_report = _report((_ROW_ID, "ledger.entries.export"))

    assessments = evaluate_ledger_capability_gates(
        matrix,
        observed_census=drifted_report,
        observed_subjects=(_SUBJECT,),
    )

    assert len(assessments) == 5
    assert not assessments[0].closed
    for assessment in assessments[1:]:
        assert not assessment.closed
        assert assessment.blockers == (f"{assessment.gate.value} cannot close while an earlier gate remains open",)


def test_ordered_evaluation_reopens_later_gates_after_a_malformed_subject() -> None:
    malformed_subject = _SUBJECT.model_copy(update={"digest": "subject-secret-not-a-digest"})

    assessments = evaluate_ledger_capability_gates(
        _matrix(),
        observed_census=_report(),
        observed_subjects=(malformed_subject,),
    )

    assert len(assessments) == len(LedgerGate)
    assert not assessments[0].closed
    assert any("observed subjects validation failed" in blocker for blocker in assessments[0].blockers)
    for assessment in assessments[1:]:
        assert not assessment.closed
        assert assessment.blockers == assessments[0].blockers


def test_a_model_copy_cannot_turn_all_axes_non_applicable_and_recompute_digests() -> None:
    matrix = _matrix()
    row = matrix.rows[0]
    assessments = tuple(
        assessment.model_copy(
            update={
                "applicability": ApplicabilityState.NOT_APPLICABLE,
                "proof": AxisProofState.NOT_APPLICABLE,
                "surface_state": (
                    SurfaceCapabilityState.NOT_APPLICABLE
                    if assessment.axis
                    in {
                        LedgerCapabilityAxis.BACKEND,
                        LedgerCapabilityAxis.CLI,
                        LedgerCapabilityAxis.TUI,
                    }
                    else None
                ),
                "evidence": (),
            }
        )
        for assessment in row.assessments
    )
    invalid_row = row.model_copy(update={"assessments": assessments, "annotations": frozenset()})
    candidate = _matrix_with(matrix, rows=(invalid_row,))

    first = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers
    second = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers

    assert first == second
    assert first == ("matrix validation failed at rows.0: value_error",)


def test_a_model_copy_cannot_remove_a_census_stream_at_the_gate_boundary() -> None:
    matrix = _matrix()
    report = _report()
    invalid_report = report.model_copy(update={"streams": report.streams[:-1]})

    assessment = _evaluate(
        matrix,
        LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE,
        report=invalid_report,
    )

    assert assessment.blockers == ("live census validation failed at <root>: value_error",)


def test_invalid_gate_inputs_reopen_every_gate_when_denominator_reopening_has_no_blocker_channel() -> None:
    snapshot = _snapshot(_report())
    invalid = snapshot.model_copy(update={"entries": ()})

    assert reopened_gates_for_denominator_drift(snapshot, invalid) == frozenset(LedgerGate)
