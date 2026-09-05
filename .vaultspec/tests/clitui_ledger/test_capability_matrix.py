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
import re
from collections.abc import Callable
from copy import copy
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from importlib import import_module
from pathlib import Path
from typing import Final, cast

import pytest
from dev.quality import clitui_ledger_capability_matrix as matrix_module
from dev.quality.clitui_ledger_capability_matrix import (
    ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
    LEDGER_REGISTRY_ROUTE_CENSUS_ROOT,
    LEDGER_TUI_HOLD_UNTIL_GATE,
    LEDGER_TUI_SUPPORTED_SURFACE_CENSUS_ROOT,
    LEDGER_UNION_DENOMINATOR_ROOT,
    SCHEMA_VERSION,
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
    GateAssessmentV1,
    InitialCliOwnership,
    LedgerAcceptanceRecordAnchorV1,
    LedgerCampaignControlsV1,
    LedgerCapabilityAxis,
    LedgerCapabilityEffect,
    LedgerCapabilityIdentityV1,
    LedgerCapabilityMatrixV1,
    LedgerCapabilityRowV1,
    LedgerDenominatorSnapshotV1,
    LedgerGapClass,
    LedgerGate,
    LedgerGateClosureReceiptV1,
    LedgerLiveCensusReportV1,
    LedgerMatrixAcceptanceAttestationV1,
    LedgerRegistryDestinationStatus,
    LedgerRegistryRouteCensusV1,
    LedgerTuiSupportedSurfaceCensusV1,
    LedgerUnionCapabilityRowV1,
    LedgerUnionDenominatorV1,
    LedgerUnionReviewSnapshotV1,
    LedgerUnionRowReviewAttestationV1,
    LedgerUnionRowReviewRuling,
    LedgerUnionSourceObservationV1,
    ReviewRuling,
    SemanticHomeStatus,
    SurfaceCapabilityState,
    build_ledger_capability_matrix,
    build_ledger_registry_route_census,
    build_ledger_tui_supported_surface_census,
    build_ledger_union_denominator,
    evaluate_ledger_capability_gate,
    evaluate_ledger_capability_gates,
    ledger_capability_matrix_source_digest,
    ledger_gate_closure_receipt_id,
    ledger_registry_route_census_bytes,
    ledger_registry_source_files,
    ledger_registry_source_set_digest,
    ledger_tui_supported_surface_census_bytes,
    ledger_tui_supported_surface_source_files,
    ledger_tui_supported_surface_source_set_digest,
    ledger_union_denominator_bytes,
    ledger_union_denominator_digest,
    reopened_gates_for_currentness,
    reopened_gates_for_denominator_drift,
    validate_ledger_matrix_currentness,
)
from pydantic import BaseModel, ValidationError

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.transport_locus import TransportLocus, TransportRole, TransportShape
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.entrypoints.cli._app_ledger_command_specs import LEDGER_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_OBSERVED_AT: Final[datetime] = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
_LATER_OBSERVED_AT: Final[datetime] = datetime(2026, 9, 4, 12, 1, tzinfo=UTC)
_SUBJECT_ID: Final[str] = "subject.ledger.matrix"
_CENSUS_ID: Final[str] = "census.ledger.baseline"
_ROW_ID: Final[str] = "ledger.entries.list"
_SUBJECT_DIGEST: Final[str] = "sha256:" + "a" * 64
_REGISTRY_ROUTE_DIGEST: Final[str] = "sha256:20b2d2df5558b2a3fdbd1eab6e9f781a973e93c6211e211f8e679cf7b4782aca"
_REGISTRY_SOURCE_DIGEST: Final[str] = "sha256:194a9f26ddfbae6c5d7f265ffe58f50964fbe2fcd02a5670fa19845dead5cf6d"
_TUI_CENSUS_DIGEST: Final[str] = "sha256:ce8316795e12434b915bca29b29f42e4ac66a1b3a9738e2899643598c3376380"
_TUI_SOURCE_DIGEST: Final[str] = "sha256:23f6690df3fef9b9a0131f5bdbba1c6daf7ae2c462b3262cf6b2b77b570143e6"
_UNION_DIGEST: Final[str] = "sha256:2895cbcff0d09c7562c314413984fdb360f3cb7cbffbe0d0cc754fc252ac4ca5"
_ROW_REVIEW_DIGEST: Final[str] = "sha256:953cc5d70c492640bc81a04426a9d5fc5abaa012a21ad65f22197cb8b76a07cf"
_ROW_REVIEW_ATTESTATION_DIGEST: Final[str] = "sha256:1df9648852ee481066107ea1d9665b4c364b4616f95679905257ac56445ab148"
_UNSET: Final[object] = object()
_REFERENCE_PATH: Final[Path] = (
    Path(__file__).resolve().parents[3] / ".vault" / "reference" / "2026-09-04-clitui-ledger-reference.md"
)
_MATRIX_CONTRACT_COORDINATE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\| `evidence\.baseline\.matrix_contract` \| `(?P<locator>[^`]+)` \| "
    r"`(?P<digest>sha256:[0-9a-f]{64})` \|",
    re.MULTILINE,
)


def _published_matrix_contract_digest(path: Path = _REFERENCE_PATH) -> str:
    """Read the unique human publication coordinate without duplicating its digest."""
    matches = tuple(_MATRIX_CONTRACT_COORDINATE_PATTERN.finditer(path.read_text(encoding="utf-8")))
    if len(matches) != 1:
        raise AssertionError(f"expected one matrix-contract publication coordinate, found {len(matches)}")
    locator = matches[0].group("locator").strip()
    if locator != "dev/quality/clitui_ledger_capability_matrix.py:22":
        raise AssertionError(f"matrix-contract publication locator drifted: {locator!r}")
    return cast(str, matches[0].group("digest"))


@cache
def _registry_census() -> LedgerRegistryRouteCensusV1:
    return build_ledger_registry_route_census()


@cache
def _tui_census() -> LedgerTuiSupportedSurfaceCensusV1:
    return build_ledger_tui_supported_surface_census()


@cache
def _union_denominator() -> LedgerUnionDenominatorV1:
    return build_ledger_union_denominator(registry=_registry_census(), tui=_tui_census())


def _refreshed_union_digest(union: LedgerUnionDenominatorV1, **updates: object) -> LedgerUnionDenominatorV1:
    candidate = union.model_copy(update={**updates, "digest": ""})
    return candidate.model_copy(update={"digest": candidate.calculated_digest})


def _refreshed_union_review(
    union: LedgerUnionDenominatorV1,
    *,
    rows: tuple[LedgerUnionCapabilityRowV1, ...],
) -> LedgerUnionDenominatorV1:
    refreshed_rows = tuple(row.model_copy(update={"review_digest": row.calculated_review_digest}) for row in rows)
    candidate = union.model_copy(
        update={
            "rows": refreshed_rows,
            "reviewed_row_count": len(refreshed_rows),
            "row_review_digest": "",
            "digest": "",
        }
    )
    candidate = candidate.model_copy(update={"row_review_digest": candidate.calculated_row_review_digest})
    attestation = candidate.row_review_attestation.model_copy(
        update={
            "reviewed_union_basis_digest": candidate.calculated_review_basis_digest,
            "row_review_digest": candidate.row_review_digest,
            "reviewed_row_count": candidate.reviewed_row_count,
            "digest": "",
        }
    )
    attestation = attestation.model_copy(update={"digest": attestation.calculated_digest})
    candidate = candidate.model_copy(update={"row_review_attestation": attestation})
    return candidate.model_copy(update={"digest": candidate.calculated_digest})


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
    assert union.schema_version == 4
    assert len(union.observations) == 761
    assert len(union.rows) == 694
    assert union.selection_accounting.model_dump() == {
        "observation_count": 761,
        "selected_edges": 770,
        "one_to_many_observations": 4,
        "one_to_many_extra_edges": 9,
        "multi_observation_rows": 59,
        "duplicate_selection_edges": 76,
        "final_rows": 694,
    }
    assert [(item.source.value, item.observation_count) for item in union.source_digests] == [
        ("artifact_product", 6),
        ("backend_only", 64),
        ("cli_endpoint", 78),
        ("cli_suboperation", 50),
        ("missing_product", 10),
        ("registry_route", 546),
        ("supported_surface", 7),
    ]
    assert union.digest == _UNION_DIGEST
    assert union.reviewed_row_count == 694
    assert union.row_review_digest == _ROW_REVIEW_DIGEST
    assert union.row_review_attestation.digest == _ROW_REVIEW_ATTESTATION_DIGEST
    assert ledger_union_denominator_digest(union) == _UNION_DIGEST
    assert ledger_union_denominator_bytes(union).startswith(b"cadrumo:ledger-union-denominator:v4\x00")


def test_union_holds_every_tui_applicable_row_until_g3_without_holding_non_applicable_rows() -> None:
    union = _union_denominator()

    tui_decisions = {
        row.capability_id: next(decision for decision in row.applicability if decision.axis is LedgerCapabilityAxis.TUI)
        for row in union.rows
    }
    applicable = tuple(
        row_id for row_id, decision in tui_decisions.items() if decision.applicability is ApplicabilityState.APPLICABLE
    )
    not_applicable = tuple(
        row_id
        for row_id, decision in tui_decisions.items()
        if decision.applicability is ApplicabilityState.NOT_APPLICABLE
    )

    assert len(applicable) == 680
    assert len(not_applicable) == 14
    assert all(
        union.rows[index].tui_hold_until is LEDGER_TUI_HOLD_UNTIL_GATE
        for index in range(len(union.rows))
        if union.rows[index].capability_id in applicable
    )
    assert all(
        union.rows[index].tui_hold_until is None
        for index in range(len(union.rows))
        if union.rows[index].capability_id in not_applicable
    )
    assert [(route.destination, route.reachability) for route in union.tui_census.routes] == [
        ("ledger.classification", "component_only"),
        ("ledger.entries", "component_only"),
        ("ledger.evidence", "component_only"),
        ("ledger.import", "component_only"),
        ("ledger.overview", "installed"),
        ("ledger.reconciliation", "component_only"),
        ("ledger.review", "component_only"),
    ]


@pytest.mark.parametrize("mutation", ["missing_applicable", "held_not_applicable"])
def test_union_hold_validation_rejects_row_drift_even_with_a_refreshed_digest(mutation: str) -> None:
    union = _union_denominator()
    rows = list(union.rows)
    if mutation == "missing_applicable":
        index = next(
            index
            for index, row in enumerate(rows)
            if next(
                decision for decision in row.applicability if decision.axis is LedgerCapabilityAxis.TUI
            ).applicability
            is ApplicabilityState.APPLICABLE
        )
        rows[index] = rows[index].model_copy(update={"tui_hold_until": None})
    else:
        index = next(
            index
            for index, row in enumerate(rows)
            if next(
                decision for decision in row.applicability if decision.axis is LedgerCapabilityAxis.TUI
            ).applicability
            is ApplicabilityState.NOT_APPLICABLE
        )
        rows[index] = rows[index].model_copy(update={"tui_hold_until": LEDGER_TUI_HOLD_UNTIL_GATE})
    candidate = _refreshed_union_digest(union, rows=tuple(rows))

    with pytest.raises(ValidationError, match="TUI hold"):
        LedgerUnionDenominatorV1.model_validate(candidate.model_dump(mode="python"))


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
        "cli_endpoint",
        "cli_suboperation",
    }
    assert "ledger.classify.auto_split.reject" not in rows
    assert {source.value for source in rows["ledger.classification.rule_add"].sources} == {
        "backend_only",
        "cli_endpoint",
    }
    assert len(rows["ledger.classification.rule_apply"].source_observation_ids) == 3
    assert len(rows["ledger.counterparty.record"].source_observation_ids) == 2
    assert len(rows["ledger.export.flat"].source_observation_ids) == 2
    assert len(rows["ledger.llm.apply_split"].source_observation_ids) == 4
    assert rows["ledger.rule.apply.preview"].effect is LedgerCapabilityEffect.PROPOSAL
    assert rows["ledger.classification.rule_apply"].effect is LedgerCapabilityEffect.MUTATION


def test_union_effect_decisions_cover_persistent_llm_queries_provenance_and_download() -> None:
    rows = {row.capability_id: row for row in _union_denominator().rows}
    for capability_id in (
        "ledger.llm.apply",
        "ledger.llm.apply_saturated",
        "ledger.llm.apply_split",
        "ledger.llm.apply_evidence_classification",
        "ledger.llm.reject",
        "ledger.llm.review_decision",
    ):
        assert rows[capability_id].effect is LedgerCapabilityEffect.MUTATION
    for capability_id in (
        "ledger.llm.diagnostics",
        "ledger.field_change.provenance",
        "ledger.fx.provenance",
        "ledger.import.normalization_provenance",
        "ledger.manual_override.provenance",
        "ledger.transaction.review_query",
        "ledger.workspace.project",
    ):
        assert rows[capability_id].effect is LedgerCapabilityEffect.QUERY
    assert rows["ledger.evidence.download"].effect is LedgerCapabilityEffect.ARTIFACT_QUERY


def test_union_refuses_unknown_non_registry_identity_and_effect_collision() -> None:
    with pytest.raises(ValueError, match="unadjudicated non-registry"):
        matrix_module._effect_for("ledger.transaction.future", frozenset({DenominatorSourceKind.CLI_ENDPOINT}))
    overlapping = matrix_module._EXPLICIT_QUERY_CAPABILITIES & matrix_module._EXPLICIT_MUTATION_CAPABILITIES
    assert not overlapping


@pytest.mark.parametrize(
    "source",
    [
        DenominatorSourceKind.CLI_ENDPOINT,
        DenominatorSourceKind.CLI_SUBOPERATION,
        DenominatorSourceKind.BACKEND_ONLY,
        DenominatorSourceKind.MISSING_PRODUCT,
        DenominatorSourceKind.ARTIFACT_PRODUCT,
        DenominatorSourceKind.SUPPORTED_SURFACE,
    ],
)
def test_each_non_registry_source_addition_reopens_semantic_adjudication(
    source: DenominatorSourceKind,
) -> None:
    observations = (
        *_union_denominator().observations,
        LedgerUnionSourceObservationV1(
            source=source,
            observation_id=f"mutation:{source.value}",
            capability_ids=("ledger.transaction.create",),
        ),
    )
    with pytest.raises(ValueError, match=r"added=.*mutation"):
        matrix_module._validate_non_registry_observation_adjudication(observations)


@pytest.mark.parametrize("mutation", ["duplicate", "removed", "changed", "reordered"])
def test_observation_adjudication_refuses_identity_and_selection_drift(mutation: str) -> None:
    observations = list(_union_denominator().observations)
    if mutation == "duplicate":
        observations.append(observations[0])
        expected = "identities must be unique"
    elif mutation == "removed":
        observations.pop(
            next(i for i, item in enumerate(observations) if item.source is not DenominatorSourceKind.REGISTRY_ROUTE)
        )
        expected = "removed="
    else:
        index = next(
            i for i, item in enumerate(observations) if item.observation_id == "cli_endpoint:app_ledger_export"
        )
        original = observations[index]
        capability_ids = (
            ("ledger.transaction.create",) if mutation == "changed" else tuple(reversed(original.capability_ids))
        )
        observations[index] = original.model_copy(update={"capability_ids": capability_ids})
        expected = "changed_selections"
    with pytest.raises(ValueError, match=expected):
        matrix_module._validate_non_registry_observation_adjudication(tuple(observations))


def test_serialized_union_refuses_cross_source_relabel_with_refreshed_aggregate_digest() -> None:
    union = _union_denominator()
    observations = list(union.observations)
    index = next(i for i, item in enumerate(observations) if item.observation_id == "cli_endpoint:app_ledger_add")
    observations[index] = observations[index].model_copy(update={"source": DenominatorSourceKind.MISSING_PRODUCT})
    observations.sort(key=lambda item: (item.source.value, item.observation_id))
    candidate = _refreshed_union_digest(union, observations=tuple(observations))
    with pytest.raises(ValidationError, match="observation adjudication drifted"):
        LedgerUnionDenominatorV1.model_validate(candidate.model_dump(mode="python"))


@pytest.mark.parametrize("mutation", ["rename", "add", "remove", "duplicate", "source", "selection"])
def test_serialized_union_refuses_registry_observation_drift_with_refreshed_digest(mutation: str) -> None:
    union = _union_denominator()
    observations = list(union.observations)
    index = next(i for i, item in enumerate(observations) if item.source is DenominatorSourceKind.REGISTRY_ROUTE)
    original = observations[index]
    if mutation == "rename":
        observations[index] = original.model_copy(update={"observation_id": original.observation_id + "_renamed"})
    elif mutation == "add":
        observations.append(original.model_copy(update={"observation_id": original.observation_id + "_added"}))
    elif mutation == "remove":
        observations.pop(index)
    elif mutation == "duplicate":
        observations.append(original)
    elif mutation == "source":
        observations[index] = original.model_copy(update={"source": DenominatorSourceKind.CLI_ENDPOINT})
    else:
        observations[index] = original.model_copy(update={"capability_ids": ("ledger.transaction.create",)})
    observations.sort(key=lambda item: (item.source.value, item.observation_id))
    candidate = _refreshed_union_digest(union, observations=tuple(observations))
    with pytest.raises(ValidationError):
        LedgerUnionDenominatorV1.model_validate(candidate.model_dump(mode="python"))


@pytest.mark.parametrize("mutation", ["membership", "sources"])
def test_serialized_union_recomputes_row_observation_authority(mutation: str) -> None:
    union = _union_denominator()
    rows = list(union.rows)
    index = next(i for i, row in enumerate(rows) if row.capability_id == "ledger.transaction.create")
    row = rows[index]
    if mutation == "membership":
        rows[index] = row.model_copy(update={"source_observation_ids": row.source_observation_ids[1:]})
        expected = "observations drifted"
    else:
        rows[index] = row.model_copy(update={"sources": frozenset({DenominatorSourceKind.CLI_ENDPOINT})})
        expected = "sources drifted"
    candidate = _refreshed_union_digest(union, rows=tuple(rows))
    with pytest.raises(ValidationError, match=expected):
        LedgerUnionDenominatorV1.model_validate(candidate.model_dump(mode="python"))


def test_serialized_union_recomputes_source_digest_after_aggregate_digest_refresh() -> None:
    union = _union_denominator()
    source_digests = list(union.source_digests)
    source_digests[0] = source_digests[0].model_copy(update={"digest": "sha256:" + "0" * 64})
    candidate = _refreshed_union_digest(union, source_digests=tuple(source_digests))
    with pytest.raises(ValidationError, match="source counts or digests drifted"):
        LedgerUnionDenominatorV1.model_validate(candidate.model_dump(mode="python"))


def test_provenance_queries_and_evidence_download_require_provenance_applicability() -> None:
    rows = {row.capability_id: row for row in _union_denominator().rows}
    for capability_id in (
        "ledger.evidence.download",
        "ledger.export.provenance",
        "ledger.field_change.provenance",
        "ledger.fx.provenance",
        "ledger.import.normalization_provenance",
        "ledger.manual_override.provenance",
    ):
        row = rows[capability_id]
        provenance = next(item for item in row.applicability if item.axis is LedgerCapabilityAxis.PROVENANCE)
        assert provenance.applicability is ApplicabilityState.APPLICABLE
        assert LedgerGapClass.PROVENANCE in row.gap_classes
        assert any("normalization" in proof and "lineage" in proof for proof in row.proof_requirements)


def test_serialized_union_refuses_provenance_applicability_contradiction() -> None:
    payload = _union_denominator().model_dump(mode="python")
    rows = list(payload["rows"])
    index = next(i for i, row in enumerate(rows) if row["capability_id"] == "ledger.export.provenance")
    changed_row = dict(rows[index])
    decisions = list(changed_row["applicability"])
    provenance_index = next(i for i, item in enumerate(decisions) if item["axis"] is LedgerCapabilityAxis.PROVENANCE)
    changed_decision = dict(decisions[provenance_index])
    changed_decision["applicability"] = ApplicabilityState.NOT_APPLICABLE
    changed_decision["proof"] = AxisProofState.NOT_APPLICABLE
    changed_decision["proof_requirement"] = (
        "No independent proof obligation applies because this axis is not applicable."
    )
    decisions[provenance_index] = changed_decision
    changed_row["applicability"] = tuple(decisions)
    rows[index] = changed_row
    payload["rows"] = tuple(rows)
    with pytest.raises(ValidationError, match="applicability drifted"):
        LedgerUnionDenominatorV1.model_validate(payload)


def test_union_denominator_retains_every_registry_route_unit_and_tui_reachability_split() -> None:
    union = _union_denominator()
    registry_rows = [row for row in union.rows if "registry_route" in {source.value for source in row.sources}]
    rows = {row.capability_id: row for row in union.rows}

    assert len(registry_rows) == 546
    assert len({row.capability_id for row in registry_rows}) == 546
    assert sum("direct registry destination" in blocker for row in registry_rows for blocker in row.blockers) == 510
    assert sum("application sidecar" in blocker for row in registry_rows for blocker in row.blockers) == 3
    assert sum("no registry destination" in blocker for row in registry_rows for blocker in row.blockers) == 33
    assert rows["ledger.workspace.read"].tui_routes == ("ledger.overview",)
    assert "reachability" not in {gap.value for gap in rows["ledger.workspace.read"].gap_classes}
    prepared_import = rows["ledger.import.prepare"]
    assert prepared_import.sources == {DenominatorSourceKind.BACKEND_ONLY}
    assert prepared_import.semantic_home.owner == (
        "cadrumo.application.ledger.import_preparation:prepare_ledger_import_command"
    )
    assert prepared_import.semantic_home_status is SemanticHomeStatus.PLANNED
    assert prepared_import.effect is LedgerCapabilityEffect.QUERY
    assert prepared_import.tui_routes == ()
    assert prepared_import.gap_classes == {LedgerGapClass.PRODUCT, LedgerGapClass.PROOF}
    assert prepared_import.primary_gap_class is LedgerGapClass.PRODUCT
    assert prepared_import.secondary_gap_classes == (LedgerGapClass.PROOF,)
    assert prepared_import.tui_hold_until is None
    assert {
        decision.axis: (decision.applicability, decision.proof)
        for decision in prepared_import.applicability
    } == {
        LedgerCapabilityAxis.ARTIFACT: (ApplicabilityState.NOT_APPLICABLE, AxisProofState.NOT_APPLICABLE),
        LedgerCapabilityAxis.BACKEND: (ApplicabilityState.APPLICABLE, AxisProofState.UNPROVEN),
        LedgerCapabilityAxis.CLI: (ApplicabilityState.NOT_APPLICABLE, AxisProofState.NOT_APPLICABLE),
        LedgerCapabilityAxis.COMPOSITION: (ApplicabilityState.NOT_APPLICABLE, AxisProofState.NOT_APPLICABLE),
        LedgerCapabilityAxis.PROOF: (ApplicabilityState.APPLICABLE, AxisProofState.UNPROVEN),
        LedgerCapabilityAxis.PROVENANCE: (ApplicabilityState.NOT_APPLICABLE, AxisProofState.NOT_APPLICABLE),
        LedgerCapabilityAxis.REGISTRY: (ApplicabilityState.NOT_APPLICABLE, AxisProofState.NOT_APPLICABLE),
        LedgerCapabilityAxis.TUI: (ApplicabilityState.NOT_APPLICABLE, AxisProofState.NOT_APPLICABLE),
    }
    assert "ledger.import.prepare" not in matrix_module._BACKEND_DIRECT_PROOF_GAPS
    assert "ledger.import.source" not in {
        row.capability_id for row in union.rows if row.tui_routes == ("ledger.overview",)
    }
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


def test_union_row_review_is_exhaustive_conservative_and_digest_bound() -> None:
    union = _union_denominator()

    assert isinstance(union.row_review_attestation, LedgerUnionRowReviewAttestationV1)
    assert union.row_review_attestation.ruling is LedgerUnionRowReviewRuling.COMPLETE_WITH_OPEN_GAPS
    assert union.row_review_attestation.reviewed_union_basis_digest == union.calculated_review_basis_digest
    assert union.row_review_attestation.row_review_digest == union.calculated_row_review_digest
    assert union.row_review_attestation.reviewed_row_count == len(union.rows) == 694
    assert all(row.review_digest == row.calculated_review_digest for row in union.rows)
    assert all(
        decision.proof
        is (
            AxisProofState.UNPROVEN
            if decision.applicability is ApplicabilityState.APPLICABLE
            else AxisProofState.NOT_APPLICABLE
        )
        for row in union.rows
        for decision in row.applicability
    )
    assert all(decision.proof_requirement for row in union.rows for decision in row.applicability)
    assert all(frozenset((row.primary_gap_class, *row.secondary_gap_classes)) == row.gap_classes for row in union.rows)


def test_union_row_review_preserves_registry_destination_and_tui_hold_cohorts() -> None:
    union = _union_denominator()

    destination_counts = {
        status: sum(row.registry_destination_status is status for row in union.rows)
        for status in LedgerRegistryDestinationStatus
    }
    assert destination_counts == {
        LedgerRegistryDestinationStatus.NOT_APPLICABLE: 148,
        LedgerRegistryDestinationStatus.DIRECT: 510,
        LedgerRegistryDestinationStatus.APPLICATION_SIDECAR: 3,
        LedgerRegistryDestinationStatus.DESTINATIONLESS: 33,
    }
    assert sum(row.primary_gap_class is LedgerGapClass.AUTHORITY for row in union.rows) == 112
    assert sum(row.primary_gap_class is LedgerGapClass.REGISTRY for row in union.rows) == 546
    assert sum(row.primary_gap_class is LedgerGapClass.PRODUCT for row in union.rows) == 35
    assert sum(row.primary_gap_class is LedgerGapClass.ARTIFACT for row in union.rows) == 1
    assert sum(row.primary_gap_class is LedgerGapClass.COMPOSITION for row in union.rows) == 0
    assert sum(row.primary_gap_class is LedgerGapClass.PROOF for row in union.rows) == 0
    assert sum(row.tui_hold_until is LEDGER_TUI_HOLD_UNTIL_GATE for row in union.rows) == 681
    assert sum(row.tui_hold_until is None for row in union.rows) == 13


def test_artifact_input_review_is_derived_from_every_live_local_file_or_directory_parameter() -> None:
    observations = matrix_module._derive_ledger_cli_artifact_input_observations()
    cli_derived = frozenset(
        capability_id for observation in observations for capability_id in observation.capability_ids
    )
    expected = matrix_module._artifact_input_capabilities()
    rows = {row.capability_id: row for row in _union_denominator().rows}

    assert observations == matrix_module._EXPECTED_LEDGER_CLI_ARTIFACT_INPUT_OBSERVATIONS
    assert len(observations) == 8
    assert len(cli_derived) == 29
    assert len(expected) == 31
    assert (
        frozenset({"ledger.evidence.replace", "ledger.import.source"})
        == matrix_module._REVIEWED_ADDITIONAL_ARTIFACT_INPUT_CAPABILITIES
    )
    assert {
        "ledger.evidence.add",
        "ledger.evidence.batch",
        "ledger.evidence.replace",
        "ledger.inventory.closing_authority.record",
    } <= expected
    assert {
        "ledger.classification.bulk_csv",
        "ledger.import",
        "ledger.import.directory",
        "ledger.import.dry_run",
        "ledger.import.file",
        "ledger.import.provider_auto",
        "ledger.import.provider_csv",
        "ledger.import.provider_n26",
        "ledger.import.provider_ofx_qfx",
        "ledger.import.provider_pdf",
        "ledger.import.provider_pdf_n26",
        "ledger.import.provider_xlsx_excel",
        "ledger.import.source",
        "ledger.import.verify",
        "ledger.invoice.import",
    } <= expected
    for capability_id in expected:
        row = rows[capability_id]
        artifact = next(item for item in row.applicability if item.axis is LedgerCapabilityAxis.ARTIFACT)
        assert artifact.applicability is ApplicabilityState.APPLICABLE
        assert artifact.proof is AxisProofState.UNPROVEN
        assert "readability" in artifact.proof_requirement
        assert LedgerGapClass.ARTIFACT in row.gap_classes
        assert any("artifact input" in blocker for blocker in row.blockers)
    assert rows["ledger.import.source"].primary_gap_class is LedgerGapClass.ARTIFACT


@pytest.mark.parametrize("mutation", ["removed", "added", "changed"])
def test_artifact_input_authority_refuses_commandspec_metadata_drift(mutation: str) -> None:
    specs = list(LEDGER_COMMAND_SPECS)
    if mutation in {"removed", "changed"}:
        spec_index = next(index for index, spec in enumerate(specs) if spec.key == "app_ledger_evidence_add")
        spec = specs[spec_index]
        parameter_index = next(
            index for index, parameter in enumerate(spec.parameters) if parameter.name == "source_path"
        )
        parameters = list(spec.parameters)
        parameters[parameter_index] = (
            replace(
                parameters[parameter_index],
                transport_locus=TransportLocus.NONE,
                transport_shape=TransportShape.NOT_APPLICABLE,
                transport_role=TransportRole.NOT_APPLICABLE,
            )
            if mutation == "removed"
            else replace(parameters[parameter_index], transport_shape=TransportShape.DIRECTORY)
        )
        specs[spec_index] = replace(spec, parameters=tuple(parameters))
    else:
        spec_index = next(index for index, spec in enumerate(specs) if spec.key == "app_ledger_add")
        spec = specs[spec_index]
        parameters = list(spec.parameters)
        parameters[0] = replace(
            parameters[0],
            transport_locus=TransportLocus.LOCAL_IN,
            transport_shape=TransportShape.FILE,
            transport_role=TransportRole.PRIMARY,
        )
        specs[spec_index] = replace(spec, parameters=tuple(parameters))

    observations = matrix_module._derive_ledger_cli_artifact_input_observations(tuple(specs))

    with pytest.raises(ValueError, match="CommandSpec metadata or semantic mapping drifted"):
        matrix_module._validate_artifact_input_capabilities(observations)


def test_artifact_input_authority_refuses_semantic_selection_mapping_drift() -> None:
    def changed_selection(observation_id: str) -> tuple[str, ...]:
        if observation_id == "cli_endpoint:app_ledger_evidence_add":
            return ("ledger.evidence.batch",)
        return matrix_module._selection_for_observation(observation_id)

    observations = matrix_module._derive_ledger_cli_artifact_input_observations(
        selection_for_observation=changed_selection
    )

    with pytest.raises(ValueError, match="CommandSpec metadata or semantic mapping drifted"):
        matrix_module._validate_artifact_input_capabilities(observations)


def test_serialized_union_refuses_suppressed_artifact_input_after_all_digests_are_refreshed() -> None:
    union = _union_denominator()
    rows = list(union.rows)
    index = next(index for index, row in enumerate(rows) if row.capability_id == "ledger.import.source")
    row = rows[index]
    decisions = list(row.applicability)
    artifact_index = next(index for index, item in enumerate(decisions) if item.axis is LedgerCapabilityAxis.ARTIFACT)
    decisions[artifact_index] = decisions[artifact_index].model_copy(
        update={
            "applicability": ApplicabilityState.NOT_APPLICABLE,
            "proof": AxisProofState.NOT_APPLICABLE,
            "proof_requirement": "No independent proof obligation applies because this axis is not applicable.",
        }
    )
    rows[index] = row.model_copy(update={"applicability": tuple(decisions)})
    candidate = _refreshed_union_review(union, rows=tuple(rows))

    with pytest.raises(ValidationError, match="applicability drifted"):
        LedgerUnionDenominatorV1.model_validate(candidate.model_dump(mode="python"))


def test_tui_route_review_covers_every_applicable_row_and_no_backend_helper() -> None:
    union = _union_denominator()
    applicable = [
        row
        for row in union.rows
        if next(item for item in row.applicability if item.axis is LedgerCapabilityAxis.TUI).applicability
        is ApplicabilityState.APPLICABLE
    ]
    not_applicable = [row for row in union.rows if row not in applicable]

    assert len(applicable) == 680
    assert all(row.tui_routes for row in applicable)
    assert len(not_applicable) == 14
    assert all(not row.tui_routes for row in not_applicable)
    assert {route for row in applicable for route in row.tui_routes} == {
        "ledger.classification",
        "ledger.entries",
        "ledger.evidence",
        "ledger.import",
        "ledger.overview",
        "ledger.reconciliation",
        "ledger.review",
    }
    assert {
        route: sum(route in row.tui_routes for row in union.rows)
        for route in {
            "ledger.classification",
            "ledger.entries",
            "ledger.evidence",
            "ledger.import",
            "ledger.overview",
            "ledger.reconciliation",
            "ledger.review",
        }
    } == {
        "ledger.classification": 9,
        "ledger.entries": 31,
        "ledger.evidence": 21,
        "ledger.import": 13,
        "ledger.overview": 1,
        "ledger.reconciliation": 588,
        "ledger.review": 17,
    }
    assert sum(LedgerGapClass.REACHABILITY in row.gap_classes for row in union.rows) == 679
    assert all(
        LedgerGapClass.REACHABILITY in row.gap_classes for row in applicable if row.tui_routes != ("ledger.overview",)
    )
    assert [row.capability_id for row in applicable if row.tui_routes == ("ledger.overview",)] == [
        "ledger.workspace.read",
    ]
    assert next(row for row in union.rows if row.capability_id == "ledger.transaction.invoice_link").tui_routes == (
        "ledger.reconciliation",
    )


def test_serialized_union_refuses_supported_surface_selection_outside_its_destination_route_after_remint() -> None:
    union = _union_denominator()
    observations = list(union.observations)
    observation_index = next(
        index
        for index, observation in enumerate(observations)
        if observation.observation_id == "supported_surface:ledger.reconciliation:component_only"
    )
    supported_observation = observations[observation_index]
    observations[observation_index] = supported_observation.model_copy(
        update={"capability_ids": ("ledger.transaction.list",)}
    )
    rows = list(union.rows)
    for capability_id in ("ledger.transaction.invoice_link", "ledger.transaction.list"):
        row_index = next(index for index, row in enumerate(rows) if row.capability_id == capability_id)
        row = rows[row_index]
        source_observation_ids = set(row.source_observation_ids)
        if capability_id == "ledger.transaction.invoice_link":
            source_observation_ids.remove(supported_observation.observation_id)
            sources = row.sources - {DenominatorSourceKind.SUPPORTED_SURFACE}
        else:
            source_observation_ids.add(supported_observation.observation_id)
            sources = row.sources
        rows[row_index] = row.model_copy(
            update={
                "source_observation_ids": tuple(sorted(source_observation_ids)),
                "sources": sources,
            }
        )
    source_digests = list(union.source_digests)
    source_index = next(
        index for index, item in enumerate(source_digests) if item.source is DenominatorSourceKind.SUPPORTED_SURFACE
    )
    supported_observations = tuple(
        observation for observation in observations if observation.source is DenominatorSourceKind.SUPPORTED_SURFACE
    )
    source_digests[source_index] = source_digests[source_index].model_copy(
        update={
            "digest": matrix_module._union_source_digest(
                DenominatorSourceKind.SUPPORTED_SURFACE,
                supported_observations,
                union.registry_census,
                union.tui_census,
            )
        }
    )
    candidate_basis = union.model_copy(
        update={
            "observations": tuple(observations),
            "source_digests": tuple(source_digests),
        }
    )
    candidate = _refreshed_union_review(candidate_basis, rows=tuple(rows))

    assert candidate.digest == candidate.calculated_digest
    assert candidate.row_review_digest == candidate.calculated_row_review_digest
    assert candidate.row_review_attestation.digest == candidate.row_review_attestation.calculated_digest
    with pytest.raises(ValidationError, match="destination is absent from selected row TUI routes"):
        LedgerUnionDenominatorV1.model_validate(candidate.model_dump(mode="python"))


@pytest.mark.parametrize("mutation", ["add", "remove", "change", "unknown", "reorder", "duplicate"])
def test_exhaustive_tui_route_authority_refuses_mapping_drift(mutation: str) -> None:
    adjudication = list(matrix_module._EXPLICIT_TUI_ROUTE_ADJUDICATION)
    if mutation == "add":
        adjudication.append(("ledger.future", ("ledger.entries",)))
        adjudication.sort(key=lambda item: item[0])
    elif mutation == "remove":
        adjudication.pop(0)
    elif mutation == "duplicate":
        adjudication.insert(1, adjudication[0])
    elif mutation == "change":
        capability_id, _routes = adjudication[0]
        adjudication[0] = (capability_id, ("ledger.review",))
    elif mutation == "unknown":
        capability_id, _routes = adjudication[0]
        adjudication[0] = (capability_id, ("ledger.future",))
    else:
        adjudication[0], adjudication[1] = adjudication[1], adjudication[0]

    with pytest.raises(ValueError, match="TUI route adjudication"):
        matrix_module._validate_tui_route_adjudication(tuple(adjudication))


@pytest.mark.parametrize(
    "routes",
    [
        (),
        ("ledger.review",),
        ("ledger.future",),
        ("ledger.overview", "ledger.review"),
    ],
    ids=["remove", "change", "unknown", "add"],
)
def test_serialized_union_refuses_tui_route_drift_after_all_digests_are_refreshed(
    routes: tuple[str, ...],
) -> None:
    union = _union_denominator()
    rows = list(union.rows)
    index = next(index for index, row in enumerate(rows) if row.capability_id == "ledger.workspace.read")
    rows[index] = rows[index].model_copy(update={"tui_routes": routes})
    candidate = _refreshed_union_review(union, rows=tuple(rows))

    with pytest.raises(ValidationError, match=r"TUI routes drifted|destination is absent from selected row TUI routes"):
        LedgerUnionDenominatorV1.model_validate(candidate.model_dump(mode="python"))


def test_installed_overview_route_refuses_non_query_effects() -> None:
    with pytest.raises(ValueError, match="Overview route is read-only"):
        matrix_module._tui_routes_for("ledger.workspace.read", LedgerCapabilityEffect.MUTATION)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("owner", "semantic home drifted"),
        ("home_status", "semantic home drifted"),
        ("applicability", "applicability drifted"),
        ("primary_gap", "primary_gap_class drifted"),
        ("proof", "applicability drifted"),
        ("next_action", "next_action drifted"),
        ("registry_status", "registry_destination_status drifted"),
        ("tui_routes", "TUI routes drifted"),
    ],
)
def test_union_review_refuses_reclassification_even_after_every_review_digest_is_refreshed(
    mutation: str,
    expected: str,
) -> None:
    union = _union_denominator()
    rows = list(union.rows)
    index = next(
        index
        for index, row in enumerate(rows)
        if row.registry_destination_status is LedgerRegistryDestinationStatus.DIRECT
    )
    row = rows[index]
    if mutation == "owner":
        row = row.model_copy(
            update={"semantic_home": row.semantic_home.model_copy(update={"owner": "cadrumo.example:owner"})}
        )
    elif mutation == "home_status":
        row = row.model_copy(update={"semantic_home_status": SemanticHomeStatus.EXISTING})
    elif mutation == "applicability":
        decisions = list(row.applicability)
        decisions[0] = decisions[0].model_copy(update={"rationale": "A different but non-placeholder rationale."})
        row = row.model_copy(update={"applicability": tuple(decisions)})
    elif mutation == "primary_gap":
        row = row.model_copy(
            update={
                "primary_gap_class": LedgerGapClass.PROOF,
                "secondary_gap_classes": tuple(
                    sorted(row.gap_classes - {LedgerGapClass.PROOF}, key=lambda item: item.value)
                ),
            }
        )
    elif mutation == "proof":
        decisions = list(row.applicability)
        applicable_index = next(
            index for index, decision in enumerate(decisions) if decision.applicability is ApplicabilityState.APPLICABLE
        )
        decisions[applicable_index] = decisions[applicable_index].model_copy(update={"proof": AxisProofState.PARTIAL})
        row = row.model_copy(update={"applicability": tuple(decisions)})
    elif mutation == "next_action":
        row = row.model_copy(update={"next_action": "Use a different closure action."})
    elif mutation == "registry_status":
        row = row.model_copy(
            update={"registry_destination_status": LedgerRegistryDestinationStatus.APPLICATION_SIDECAR}
        )
    else:
        row = row.model_copy(update={"tui_routes": ("ledger.entries",)})
    rows[index] = row
    candidate = _refreshed_union_review(union, rows=tuple(rows))

    with pytest.raises(ValidationError, match=expected):
        LedgerUnionDenominatorV1.model_validate(candidate.model_dump(mode="python"))


@pytest.mark.parametrize(
    ("field_name", "value", "expected"),
    [
        ("reviewed_row_count", 692, "reviewed row coverage"),
        ("row_review_digest", "sha256:" + "0" * 64, "aggregate row-review digest"),
    ],
)
def test_union_review_refuses_incomplete_or_stale_coverage(
    field_name: str,
    value: object,
    expected: str,
) -> None:
    union = _union_denominator()
    candidate = _refreshed_union_digest(union, **{field_name: value})

    with pytest.raises(ValidationError, match=expected):
        LedgerUnionDenominatorV1.model_validate(candidate.model_dump(mode="python"))


def test_union_review_refuses_stale_row_digest_after_outer_digest_refresh() -> None:
    union = _union_denominator()
    rows = list(union.rows)
    rows[0] = rows[0].model_copy(update={"review_digest": "sha256:" + "0" * 64})
    candidate = _refreshed_union_digest(union, rows=tuple(rows))

    with pytest.raises(ValidationError, match="row review digest is stale"):
        LedgerUnionDenominatorV1.model_validate(candidate.model_dump(mode="python"))


def test_union_review_refuses_rebound_attestation_after_outer_digest_refresh() -> None:
    union = _union_denominator()
    attestation = union.row_review_attestation.model_copy(
        update={"reviewed_union_basis_digest": "sha256:" + "0" * 64, "digest": ""}
    )
    attestation = attestation.model_copy(update={"digest": attestation.calculated_digest})
    candidate = _refreshed_union_digest(union, row_review_attestation=attestation)

    with pytest.raises(ValidationError, match="attestation does not bind"):
        LedgerUnionDenominatorV1.model_validate(candidate.model_dump(mode="python"))


def test_existing_union_semantic_homes_resolve_exact_live_symbols_and_types() -> None:
    existing_rows = [
        row for row in _union_denominator().rows if row.semantic_home_status is SemanticHomeStatus.EXISTING
    ]

    assert len(existing_rows) == 4
    for row in existing_rows:
        module_name, owner_name = row.semantic_home.owner.split(":", maxsplit=1)
        module = import_module(module_name)
        assert hasattr(module, owner_name)
        assert hasattr(module, row.semantic_home.command_type)
        assert hasattr(module, row.semantic_home.result_type)


def test_existing_semantic_home_validation_refuses_signature_drift() -> None:
    declaration = next(
        item
        for item in matrix_module._LEDGER_BACKEND_OPERATION_DECLARATIONS
        if item.capability_id == "ledger.export.flat"
    )

    def drifted(command: int) -> str:
        raise AssertionError

    with pytest.raises(ValueError, match="request signature drifted"):
        matrix_module._validate_existing_semantic_home(declaration, owner_callable=drifted)


@pytest.mark.parametrize(
    "mutation", ["operation", "source"], ids=["omitted-public-operation", "omitted-current-source"]
)
def test_backend_census_refuses_an_omitted_public_import_preparation_operation(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    if mutation == "operation":
        monkeypatch.setattr(
            matrix_module,
            "_LEDGER_BACKEND_OPERATION_DECLARATIONS",
            tuple(
                declaration
                for declaration in matrix_module._LEDGER_BACKEND_OPERATION_DECLARATIONS
                if declaration.capability_id != "ledger.import.prepare"
            ),
        )
        expected = "public backend operation is omitted: ledger.import.prepare"
    else:
        monkeypatch.setattr(
            matrix_module,
            "_LEDGER_BACKEND_OPERATION_SOURCE_PATHS",
            tuple(
                path
                for path in matrix_module._LEDGER_BACKEND_OPERATION_SOURCE_PATHS
                if path != "src/cadrumo/application/ledger/import_preparation.py"
            ),
        )
        expected = "public backend operation source is omitted: src/cadrumo/application/ledger/import_preparation.py"

    with pytest.raises(ValueError, match=re.escape(expected)):
        build_ledger_union_denominator(registry=_registry_census(), tui=_tui_census())


@pytest.mark.parametrize(
    "mutation", ["missing_row", "duplicate_observation", "wrong_sources", "wrong_effect", "stale_digest"]
)
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
        rows = list(payload["rows"])
        index = next(index for index, row in enumerate(rows) if row["capability_id"] == "ledger.transaction.create")
        changed = dict(rows[index])
        changed["sources"] = frozenset({DenominatorSourceKind.CLI_ENDPOINT})
        rows[index] = changed
        payload["rows"] = tuple(rows)
        expected = "sources drifted"
    elif mutation == "wrong_effect":
        rows = list(payload["rows"])
        index = next(index for index, row in enumerate(rows) if row["capability_id"] == "ledger.llm.apply")
        changed = dict(rows[index])
        changed["effect"] = LedgerCapabilityEffect.PROPOSAL
        rows[index] = changed
        payload["rows"] = tuple(rows)
        expected = "effect drifted"
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
        tui_hold_until=LEDGER_TUI_HOLD_UNTIL_GATE if tui_applicable else None,
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
    accepted_gate_closure_receipts: tuple[LedgerGateClosureReceiptV1, ...] = (),
    accepted_denominator: LedgerDenominatorSnapshotV1 | None = None,
    current_denominator: LedgerDenominatorSnapshotV1 | None = None,
    accepted_union_review: LedgerUnionReviewSnapshotV1 | None = None,
    current_union_review: LedgerUnionReviewSnapshotV1 | None = None,
    accepted_authority_dispositions: AuthorityDispositionSnapshotV1 | None = None,
    current_authority_dispositions: AuthorityDispositionSnapshotV1 | None = None,
    current_subjects: tuple[EvidenceSubjectSnapshotV1, ...] = (_SUBJECT,),
    ruling: ReviewRuling = ReviewRuling.ACCEPT,
) -> LedgerCapabilityMatrixV1:
    """Build a digest-bound matrix and attestation around the supplied rows."""
    live_report = report if report is not None else _report(tuple(row.identity.row_id for row in rows))
    accepted = accepted_denominator if accepted_denominator is not None else _snapshot(live_report)
    current = current_denominator if current_denominator is not None else _snapshot(live_report)
    accepted_union = (
        accepted_union_review
        if accepted_union_review is not None
        else LedgerUnionReviewSnapshotV1.from_union(_union_denominator())
    )
    current_union = (
        current_union_review
        if current_union_review is not None
        else LedgerUnionReviewSnapshotV1.from_union(_union_denominator())
    )
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
        schema_version=SCHEMA_VERSION,
        controls=controls_value,
        accepted_denominator=accepted,
        current_denominator=current,
        accepted_union_review=accepted_union,
        current_union_review=current_union,
        accepted_authority_dispositions=accepted_authority,
        current_authority_dispositions=current_authority,
        current_subjects=current_subjects,
        rows=rows,
        campaign_evidence=evidence,
        accepted_gate_closure_receipts=accepted_gate_closure_receipts,
    )
    attestation_matrix_basis_digest = LedgerCapabilityMatrixV1.calculate_attestation_matrix_basis_digest(
        schema_version=SCHEMA_VERSION,
        controls=controls_value,
        accepted_denominator=accepted,
        current_denominator=current,
        accepted_union_review=accepted_union,
        current_union_review=current_union,
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
        matrix_digest=attestation_matrix_basis_digest,
        denominator_digest=current.digest,
        denominator_revision=current.revision,
        union_review=current_union,
        review_subject_id=_SUBJECT.subject_id,
        review_subject_revision=_SUBJECT.revision,
        review_subject_digest=_SUBJECT.digest,
        review_subject_observed_at=_SUBJECT.observed_at,
        attested_at=_OBSERVED_AT,
    )
    return LedgerCapabilityMatrixV1(
        schema_version=SCHEMA_VERSION,
        controls=controls_value,
        accepted_denominator=accepted,
        current_denominator=current,
        accepted_union_review=accepted_union,
        current_union_review=current_union,
        accepted_authority_dispositions=accepted_authority,
        current_authority_dispositions=current_authority,
        current_subjects=current_subjects,
        rows=rows,
        campaign_evidence=evidence,
        accepted_gate_closure_receipts=accepted_gate_closure_receipts,
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
                "matrix_digest": candidate.attestation_matrix_basis_digest,
                "denominator_digest": candidate.current_denominator.digest,
                "denominator_revision": candidate.current_denominator.revision,
                "union_review": candidate.current_union_review,
            }
        )
        candidate = candidate.model_copy(update={"acceptance_attestation": attestation})
    return candidate


def _accepted_gate_receipts(matrix: LedgerCapabilityMatrixV1) -> tuple[LedgerGateClosureReceiptV1, ...]:
    """Build a complete ordered G0--G3 receipt chain for a currently frozen matrix."""
    attestation = matrix.acceptance_attestation
    return tuple(
        LedgerGateClosureReceiptV1(
            receipt_id=ledger_gate_closure_receipt_id(gate),
            gate=gate,
            matrix_closure_basis_digest=matrix.gate_closure_basis_digest(gate),
            acceptance_attestation_digest=attestation.calculated_digest,
        )
        for gate in tuple(LedgerGate)[:-1]
    )


def _matrix_with_accepted_gate_receipts(matrix: LedgerCapabilityMatrixV1) -> LedgerCapabilityMatrixV1:
    """Record a receipt set that the frozen independent acceptance attestation binds."""
    receipt_identities = tuple((ledger_gate_closure_receipt_id(gate), gate) for gate in tuple(LedgerGate)[:-1])
    attestation = matrix.acceptance_attestation.model_copy(
        update={
            "closure_receipt_set_digest": LedgerCapabilityMatrixV1.calculate_gate_closure_receipt_set_digest(
                receipt_identities
            )
        }
    )
    attested = _matrix_with(matrix, acceptance_attestation=attestation)
    return _matrix_with(attested, accepted_gate_closure_receipts=_accepted_gate_receipts(attested))


def _matrix_with_authorized_hold_lift(matrix: LedgerCapabilityMatrixV1) -> LedgerCapabilityMatrixV1:
    """Record current G0--G3 acceptance, then make the one authorized hold transition."""
    frozen = _matrix_with_accepted_gate_receipts(matrix)
    controls = frozen.controls.model_copy(update={"tui_implementation_hold_active": False})
    return _matrix_with(frozen, controls=controls)


def _acceptance_record_anchor(
    matrix: LedgerCapabilityMatrixV1,
    *,
    reviewer: str | None = None,
    observed_at: datetime = _OBSERVED_AT,
) -> tuple[LedgerAcceptanceRecordAnchorV1, tuple[EvidenceSubjectSnapshotV1, ...]]:
    """Build an externally observed acceptance record for one frozen fixture state."""
    attestation = matrix.acceptance_attestation
    subject_id = "subject.ledger.acceptance_record"
    locator = "reference://clitui-ledger/acceptance-record"
    provisional_subject = _subject(
        subject_id=subject_id,
        revision="acceptance-record-rev-1",
        digest="sha256:" + "0" * 64,
        observed_at=observed_at,
        locator=locator,
    )

    def make_anchor(subject: EvidenceSubjectSnapshotV1) -> LedgerAcceptanceRecordAnchorV1:
        return LedgerAcceptanceRecordAnchorV1(
            coordinate=_evidence(
                "evidence.acceptance_record.independent_review",
                EvidenceRole.INDEPENDENT_ENGINEERING_REVIEW,
                frozenset(LedgerCapabilityAxis),
                subject=subject,
                claim="The external acceptance record freezes the accepted gate authority.",
            ),
            acceptance_attestation_digest=attestation.calculated_digest,
            attestation_id=attestation.attestation_id,
            reviewer=attestation.reviewer if reviewer is None else reviewer,
            attested_at=attestation.attested_at,
            matrix_basis_digest=attestation.matrix_digest,
            denominator_digest=attestation.denominator_digest,
            denominator_revision=attestation.denominator_revision,
            union_review=attestation.union_review,
            review_subject_id=attestation.review_subject_id,
            review_subject_revision=attestation.review_subject_revision,
            review_subject_digest=attestation.review_subject_digest,
            review_subject_observed_at=attestation.review_subject_observed_at,
        )

    # The content digest excludes snapshot fields, so one provisional coordinate
    # can calculate the immutable external subject which then binds it exactly.
    draft = LedgerAcceptanceRecordAnchorV1.model_construct(
        coordinate=_evidence(
            "evidence.acceptance_record.independent_review",
            EvidenceRole.INDEPENDENT_ENGINEERING_REVIEW,
            frozenset(LedgerCapabilityAxis),
            subject=provisional_subject,
            claim="The external acceptance record freezes the accepted gate authority.",
        ),
        acceptance_attestation_digest=attestation.calculated_digest,
        attestation_id=attestation.attestation_id,
        reviewer=attestation.reviewer if reviewer is None else reviewer,
        attested_at=attestation.attested_at,
        matrix_basis_digest=attestation.matrix_digest,
        denominator_digest=attestation.denominator_digest,
        denominator_revision=attestation.denominator_revision,
        union_review=attestation.union_review,
        review_subject_id=attestation.review_subject_id,
        review_subject_revision=attestation.review_subject_revision,
        review_subject_digest=attestation.review_subject_digest,
        review_subject_observed_at=attestation.review_subject_observed_at,
    )
    subject = _subject(
        subject_id=subject_id,
        revision="acceptance-record-rev-1",
        digest=draft.calculated_subject_digest,
        observed_at=observed_at,
        locator=locator,
    )
    return make_anchor(subject), (subject,)


def _reminted_live_union() -> LedgerUnionDenominatorV1:
    """Produce a valid later row-review observation, not a stale model copy."""
    union = _union_denominator()
    attestation_payload = union.row_review_attestation.model_dump(mode="python", exclude={"digest"})
    attestation_payload["reviewed_at"] = _LATER_OBSERVED_AT
    provisional_attestation = union.row_review_attestation.model_construct(
        **attestation_payload,
        digest="",
    )
    attestation = LedgerUnionRowReviewAttestationV1(
        **provisional_attestation.model_dump(mode="python", exclude={"digest"}),
        digest=provisional_attestation.calculated_digest,
    )
    provisional_union = union.model_copy(update={"row_review_attestation": attestation, "digest": ""})
    return LedgerUnionDenominatorV1(
        **provisional_union.model_dump(mode="python", exclude={"digest"}),
        digest=provisional_union.calculated_digest,
    )


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
    if LedgerCapabilityAxis.TUI in replacements:
        tui_applicable = replacements[LedgerCapabilityAxis.TUI].applicability is ApplicabilityState.APPLICABLE
        updates["tui_hold_until"] = LEDGER_TUI_HOLD_UNTIL_GATE if tui_applicable else None
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
    union: LedgerUnionDenominatorV1 | object | None = _UNSET,
    acceptance_anchor: LedgerAcceptanceRecordAnchorV1 | object | None = _UNSET,
    acceptance_subjects: tuple[EvidenceSubjectSnapshotV1, ...] | object = _UNSET,
):
    """Evaluate explicit observations; only omitted fixture inputs get defaults."""
    observed = report if report is not None else _report(tuple(row.identity.row_id for row in matrix.rows))
    observed_union = _union_denominator() if union is _UNSET else union
    if acceptance_anchor is _UNSET:
        try:
            canonical = LedgerCapabilityMatrixV1.model_validate(matrix.model_dump(mode="python"))
        except (TypeError, ValueError, ValidationError):
            selected_anchor: LedgerAcceptanceRecordAnchorV1 | None = None
            selected_anchor_subjects: tuple[EvidenceSubjectSnapshotV1, ...] = ()
        else:
            selected_anchor, selected_anchor_subjects = _acceptance_record_anchor(canonical)
    else:
        selected_anchor = cast(LedgerAcceptanceRecordAnchorV1 | None, acceptance_anchor)
        selected_anchor_subjects = (
            () if acceptance_subjects is _UNSET else cast(tuple[EvidenceSubjectSnapshotV1, ...], acceptance_subjects)
        )
    return evaluate_ledger_capability_gate(
        matrix,
        gate,
        observed_census=observed,
        observed_subjects=subjects,
        observed_union=cast(LedgerUnionDenominatorV1 | None, observed_union),
        acceptance_record_anchor=selected_anchor,
        observed_acceptance_subjects=selected_anchor_subjects,
    )


def _assert_synthetic_matrix_is_not_current(assessment: object) -> None:
    """Keep legacy one-row predicate fixtures honest under mandatory live-union binding."""
    candidate = cast(GateAssessmentV1, assessment)
    assert not candidate.closed
    assert "matrix row identities do not exactly equal the observed live reviewed union" in candidate.blockers


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
    _assert_synthetic_matrix_is_not_current(
        _evaluate(reordered, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=report)
    )


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

    _assert_synthetic_matrix_is_not_current(_evaluate(_matrix(), LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE))
    blockers = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers

    assert "the Ledger TUI implementation hold is not recorded and active" in blockers


def test_g0_rejects_a_removed_observed_capability() -> None:
    first = _row()
    second = _row("ledger.reconciliation.match", prefix="reconciliation_match")
    accepted_report = _report((_ROW_ID, "ledger.reconciliation.match"))
    matrix = _matrix(rows=(first, second), report=accepted_report)
    removed_report = _report((_ROW_ID,))

    _assert_synthetic_matrix_is_not_current(
        _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=accepted_report)
    )
    blockers = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=removed_report).blockers

    assert "accepted denominator capability missing from current census: ledger.reconciliation.match" in blockers


def test_g0_rejects_same_id_denominator_source_classification_drift() -> None:
    def streams_with_owner(owner: DenominatorSourceKind) -> tuple[CensusStreamObservationV1, ...]:
        return tuple(_stream(source, (_ROW_ID,) if source is owner else ()) for source in DenominatorSourceKind)

    accepted_report = _report(streams=streams_with_owner(DenominatorSourceKind.CLI_ENDPOINT))
    drifted_report = _report(streams=streams_with_owner(DenominatorSourceKind.BACKEND_ONLY))
    matrix = _matrix(report=accepted_report)

    _assert_synthetic_matrix_is_not_current(
        _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=accepted_report)
    )
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

    _assert_synthetic_matrix_is_not_current(
        _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=baseline)
    )
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

    _assert_synthetic_matrix_is_not_current(
        _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=baseline)
    )
    blockers = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=drifted).blockers

    assert any(expected in blocker for blocker in blockers)


def test_g0_rejects_a_missing_census_stream_at_the_gate_boundary() -> None:
    baseline = _report()
    invalid = baseline.model_copy(update={"streams": baseline.streams[:-1]})
    matrix = _matrix(report=baseline)

    _assert_synthetic_matrix_is_not_current(
        _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=baseline)
    )
    blockers = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=invalid).blockers

    assert blockers == ("live census validation failed at <root>: value_error",)


def test_g0_accepts_explicit_reviewed_zero_census_streams() -> None:
    report = _report()
    matrix = _matrix(report=report)

    assert all(not stream.capability_ids and stream.reviewed_zero for stream in report.streams[1:])
    _assert_synthetic_matrix_is_not_current(
        _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, report=report)
    )


def test_currentness_requires_nonempty_observed_subjects() -> None:
    matrix = _matrix()

    currentness = validate_ledger_matrix_currentness(
        matrix,
        observed_census=_report(),
        observed_subjects=(),
        observed_union=_union_denominator(),
    )

    assert "live evidence-subject observation is empty" in currentness
    assert "matrix evidence subject no longer observed: subject.ledger.matrix" in currentness
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
        observed_union=_union_denominator(),
    )
    changed_errors = validate_ledger_matrix_currentness(
        matrix,
        observed_census=_report(),
        observed_subjects=(changed,),
        observed_union=_union_denominator(),
    )

    assert "live evidence-subject observation contains duplicate identities" in duplicate_errors
    assert "evidence subject freshness drifted: subject.ledger.matrix" in changed_errors


def test_currentness_revalidates_a_malformed_copied_subject_without_value_leakage() -> None:
    malformed = _SUBJECT.model_copy(update={"digest": "subject-secret-not-a-digest"})

    errors = validate_ledger_matrix_currentness(
        _matrix(),
        observed_census=_report(),
        observed_subjects=(malformed,),
        observed_union=_union_denominator(),
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
        observed_union=_union_denominator(),
    )
    second = validate_ledger_matrix_currentness(
        malformed_matrix,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
        observed_union=_union_denominator(),
    )
    assessments = evaluate_ledger_capability_gates(
        malformed_matrix,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
        observed_union=_union_denominator(),
    )

    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE))
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


def test_matrix_rows_require_the_same_fail_closed_tui_hold_partition_as_the_union() -> None:
    applicable = _row()
    not_applicable = _row("ledger.entries.projection", tui_applicable=False, prefix="entries_projection")

    assert applicable.tui_hold_until is LEDGER_TUI_HOLD_UNTIL_GATE
    assert not_applicable.tui_hold_until is None

    missing = applicable.model_copy(update={"tui_hold_until": None})
    held = not_applicable.model_copy(update={"tui_hold_until": LEDGER_TUI_HOLD_UNTIL_GATE})
    for candidate in (missing, held):
        with pytest.raises(ValidationError, match="TUI hold"):
            LedgerCapabilityRowV1.model_validate(candidate.model_dump(mode="python"))


def test_matrix_rows_reject_a_hold_that_targets_any_gate_other_than_g3() -> None:
    candidate = _row().model_copy(update={"tui_hold_until": LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS})

    with pytest.raises(ValidationError, match="TUI hold"):
        LedgerCapabilityRowV1.model_validate(candidate.model_dump(mode="python"))


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
        observed_union=_union_denominator(),
    )

    assert not assessments[0].closed
    assert any("immutable initial CLI ownership drifted" in blocker for blocker in assessments[0].blockers)
    assert not assessments[1].closed
    assert any("immutable initial CLI ownership drifted" in blocker for blocker in assessments[1].blockers)


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

    _assert_synthetic_matrix_is_not_current(_evaluate(_matrix(), LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE))
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

    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE))
    blockers = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers

    assert expected in blockers


def test_g0_accepts_only_the_canonical_owner_and_digest_bound_accept_ruling() -> None:
    matrix = _matrix()

    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE))

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

    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE))
    blockers = _evaluate(candidate, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE).blockers

    assert f"{_ROW_ID}: composition lacks exact baseline evidence" in blockers


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
    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE))


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

    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE))
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

    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS))
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

    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS))
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
    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS))
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

    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS))
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
    candidate = _matrix_with_authorized_hold_lift(_matrix(rows=(mutated,)))

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
    assert "the Ledger TUI implementation hold remains active" in assessment.blockers


def test_g4_refuses_a_premature_hold_lift_without_an_accepted_g3_receipt() -> None:
    matrix = _matrix_with(
        _matrix(),
        controls=LedgerCampaignControlsV1(
            sole_ledger_parity_plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
            tui_implementation_hold_recorded=True,
            tui_implementation_hold_active=False,
        ),
    )

    assessment = _evaluate(matrix, LedgerGate.G4_TUI_ADMISSION_AND_PARITY)

    assert not assessment.closed
    assert "the Ledger TUI implementation hold lacks a current accepted G3 closure receipt" in assessment.blockers


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
    matrix = _matrix_with_authorized_hold_lift(_matrix())
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
    candidate = _matrix_with_authorized_hold_lift(_matrix(rows=(row,)))

    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G4_TUI_ADMISSION_AND_PARITY))
    blockers = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).blockers

    assert f"{_ROW_ID}: TUI is not proven and installed" in blockers


def test_g4_rejects_a_tui_row_without_the_installed_annotation() -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    row = _row_with_assessments(
        matrix.rows[0],
        {},
        annotations=frozenset({CapabilityAnnotation.DELEGATING}),
    )
    candidate = _matrix_with_authorized_hold_lift(_matrix(rows=(row,)))

    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G4_TUI_ADMISSION_AND_PARITY))
    blockers = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).blockers

    assert f"{_ROW_ID}: TUI is not marked installed" in blockers


@pytest.mark.parametrize(
    "role",
    [
        pytest.param(EvidenceRole.TUI_PARITY, id="parity"),
        pytest.param(EvidenceRole.TUI_REACHABILITY, id="reachability"),
        pytest.param(EvidenceRole.MATRIX_PUBLICATION, id="publication"),
    ],
)
def test_g4_requires_each_campaign_wide_tui_evidence_role(role: EvidenceRole) -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    campaign_evidence = tuple(coordinate for coordinate in matrix.campaign_evidence if coordinate.role is not role)
    candidate = _matrix_with_authorized_hold_lift(_matrix(campaign_evidence=campaign_evidence))

    _assert_synthetic_matrix_is_not_current(_evaluate(matrix, LedgerGate.G4_TUI_ADMISSION_AND_PARITY))
    blockers = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).blockers

    assert f"campaign-wide {role.value} evidence is missing" in blockers


def test_g4_preserves_explicitly_empty_campaign_evidence() -> None:
    candidate = _matrix_with_authorized_hold_lift(_matrix(campaign_evidence=()))

    blockers = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).blockers

    assert {
        "campaign-wide tui_parity evidence is missing",
        "campaign-wide tui_reachability evidence is missing",
        "campaign-wide matrix_publication evidence is missing",
    } <= set(blockers)


def test_g4_scans_findings_for_every_applicable_axis_on_every_row() -> None:
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
    clean = _matrix_with_authorized_hold_lift(_matrix())
    _assert_synthetic_matrix_is_not_current(_evaluate(clean, LedgerGate.G4_TUI_ADMISSION_AND_PARITY))
    candidate = _matrix_with_authorized_hold_lift(_matrix(rows=(first, second)))

    blockers = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY).blockers

    assert sum("blocking" in blocker for blocker in blockers) == 2 * len(LedgerCapabilityAxis)
    assert blockers.count(f"{first.identity.row_id}: blocking product finding remains") == len(LedgerCapabilityAxis)
    assert blockers.count(f"{second.identity.row_id}: blocking product finding remains") == len(LedgerCapabilityAxis)


def test_ordered_post_g3_hold_lift_preserves_accepted_history_and_allows_g4() -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    anchor, acceptance_subjects = _acceptance_record_anchor(matrix)

    individual_g0 = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE)
    individual_g4 = _evaluate(matrix, LedgerGate.G4_TUI_ADMISSION_AND_PARITY)
    ordered = evaluate_ledger_capability_gates(
        matrix,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
        observed_union=_union_denominator(),
        acceptance_record_anchor=anchor,
        observed_acceptance_subjects=acceptance_subjects,
    )

    assert not individual_g0.closed
    assert "the Ledger TUI implementation hold is not recorded and active" in individual_g0.blockers
    assert not individual_g4.closed
    assert all(not assessment.closed for assessment in ordered)


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("forged_basis", id="forged-basis"),
        pytest.param("forged_attestation_digest", id="forged-attestation-digest"),
        pytest.param("wrong_order", id="wrong-order"),
    ],
)
def test_g4_refuses_forged_or_wrong_order_gate_closure_receipts(mutation: str) -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    receipts = matrix.accepted_gate_closure_receipts
    if mutation == "forged_basis":
        receipts = (
            *receipts[:-1],
            receipts[-1].model_copy(update={"matrix_closure_basis_digest": "sha256:" + "b" * 64}),
        )
    elif mutation == "forged_attestation_digest":
        receipts = (
            *receipts[:-1],
            receipts[-1].model_copy(update={"acceptance_attestation_digest": "sha256:" + "c" * 64}),
        )
    else:
        receipts = tuple(reversed(receipts))
    candidate = _matrix_with(matrix, accepted_gate_closure_receipts=receipts)

    assessment = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY)

    assert not assessment.closed
    assert len(assessment.blockers) == 1
    assert assessment.blockers[0].startswith("matrix validation failed at ")


def test_g4_requires_an_external_acceptance_record_for_an_accepted_g3_receipt() -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())

    assessment = evaluate_ledger_capability_gate(
        matrix,
        LedgerGate.G4_TUI_ADMISSION_AND_PARITY,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
        observed_union=_union_denominator(),
    )

    assert not assessment.closed
    assert "accepted G3 closure requires a current external acceptance record anchor" in assessment.blockers


def test_receipt_identity_is_a_gate_derived_constant_even_after_full_internal_remint() -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    anchor, acceptance_subjects = _acceptance_record_anchor(matrix)
    reminted_id = "receipt.ledger.reminted"
    identities = tuple(
        (
            reminted_id if receipt.gate is LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS else receipt.receipt_id,
            receipt.gate,
        )
        for receipt in matrix.accepted_gate_closure_receipts
    )
    attestation = matrix.acceptance_attestation.model_copy(
        update={
            "closure_receipt_set_digest": LedgerCapabilityMatrixV1.calculate_gate_closure_receipt_set_digest(identities)
        }
    )
    provisional = matrix.model_copy(update={"acceptance_attestation": attestation})
    receipts = tuple(
        LedgerGateClosureReceiptV1.model_construct(
            receipt_id=reminted_id
            if receipt.gate is LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS
            else receipt.receipt_id,
            gate=receipt.gate,
            matrix_closure_basis_digest=provisional.gate_closure_basis_digest(receipt.gate),
            acceptance_attestation_digest=attestation.calculated_digest,
        )
        for receipt in provisional.accepted_gate_closure_receipts
    )
    fully_reminted = provisional.model_copy(update={"accepted_gate_closure_receipts": receipts})
    fully_reminted = fully_reminted.model_copy(update={"matrix_digest": fully_reminted.calculated_matrix_digest})

    assessment = _evaluate(
        fully_reminted,
        LedgerGate.G4_TUI_ADMISSION_AND_PARITY,
        acceptance_anchor=anchor,
        acceptance_subjects=acceptance_subjects,
    )

    assert not assessment.closed
    assert assessment.blockers == ("matrix validation failed at accepted_gate_closure_receipts.3: value_error",)


def test_g4_refuses_a_fully_recomputed_attestation_time_remint_against_the_external_anchor() -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    anchor, acceptance_subjects = _acceptance_record_anchor(matrix)
    attestation = matrix.acceptance_attestation.model_copy(update={"attested_at": _LATER_OBSERVED_AT})
    provisional = _matrix_with(matrix, acceptance_attestation=attestation, bind_attestation=False)
    receipts = _accepted_gate_receipts(provisional)
    reminted = _matrix_with(provisional, accepted_gate_closure_receipts=receipts, bind_attestation=False)

    assert LedgerCapabilityMatrixV1.model_validate(reminted.model_dump(mode="python")) == reminted
    assessment = _evaluate(
        reminted,
        LedgerGate.G4_TUI_ADMISSION_AND_PARITY,
        acceptance_anchor=anchor,
        acceptance_subjects=acceptance_subjects,
    )

    assert not assessment.closed
    assert "acceptance record anchor does not bind the current acceptance attestation" in assessment.blockers


@pytest.mark.parametrize("mutation", ["missing", "stale_subject", "rebound_anchor", "wrong_coordinate"])
def test_g4_refuses_missing_stale_or_rebound_external_acceptance_authority(mutation: str) -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    anchor, acceptance_subjects = _acceptance_record_anchor(matrix)
    if mutation == "missing":
        selected_anchor = None
        selected_subjects: tuple[EvidenceSubjectSnapshotV1, ...] = ()
    elif mutation == "stale_subject":
        selected_anchor = anchor
        selected_subjects = (acceptance_subjects[0].model_copy(update={"revision": "acceptance-record-rev-2"}),)
    elif mutation == "rebound_anchor":
        selected_anchor, _ = _acceptance_record_anchor(matrix, reviewer="fabricated-reviewer")
        selected_subjects = acceptance_subjects
    else:
        selected_anchor = anchor.model_copy(
            update={"coordinate": anchor.coordinate.model_copy(update={"locator": "reference://wrong"})}
        )
        selected_subjects = acceptance_subjects

    assessment = evaluate_ledger_capability_gate(
        matrix,
        LedgerGate.G4_TUI_ADMISSION_AND_PARITY,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
        observed_union=_union_denominator(),
        acceptance_record_anchor=selected_anchor,
        observed_acceptance_subjects=selected_subjects,
    )

    assert not assessment.closed
    assert assessment.blockers
    assert any(
        "acceptance record anchor" in blocker or "external acceptance" in blocker for blocker in assessment.blockers
    )


def test_receipt_serialization_and_matrix_digest_mutations_fail_closed() -> None:
    base = _matrix()
    frozen = _matrix_with_accepted_gate_receipts(base)
    lifted = _matrix_with_authorized_hold_lift(base)
    stale_digest = lifted.model_copy(update={"matrix_digest": frozen.matrix_digest})

    serialized = lifted.model_dump(mode="json")
    assessment = _evaluate(stale_digest, LedgerGate.G4_TUI_ADMISSION_AND_PARITY)

    assert serialized["accepted_gate_closure_receipts"][-1]["gate"] == LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS
    assert frozen.matrix_digest != base.matrix_digest
    assert lifted.matrix_digest != frozen.matrix_digest
    assert not assessment.closed
    assert assessment.blockers == ("matrix validation failed at <root>: value_error",)


def test_g4_refuses_receipts_when_the_bound_acceptance_attestation_is_not_accepting() -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    attestation = matrix.acceptance_attestation.model_copy(update={"ruling": ReviewRuling.REJECT})
    candidate = _matrix_with(matrix, acceptance_attestation=attestation)

    assessment = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY)

    assert not assessment.closed
    assert assessment.blockers == ("matrix validation failed at <root>: value_error",)


@pytest.mark.parametrize(
    ("field", "value", "bind_attestation"),
    [
        pytest.param("attested_at", _LATER_OBSERVED_AT, True, id="attested-at"),
        pytest.param("reviewer", "fabricated-reviewer", True, id="reviewer"),
        pytest.param("attestation_id", "attestation.ledger.reminted", True, id="identity"),
        pytest.param("matrix_digest", "sha256:" + "d" * 64, False, id="matrix-basis"),
    ],
)
def test_g4_refuses_each_reminted_bound_attestation_fact(
    field: str,
    value: datetime | str,
    bind_attestation: bool,
) -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    attestation = matrix.acceptance_attestation.model_copy(update={field: value})
    candidate = _matrix_with(matrix, acceptance_attestation=attestation, bind_attestation=bind_attestation)

    assessment = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY)

    assert not assessment.closed
    assert assessment.blockers == ("matrix validation failed at <root>: value_error",)


def test_receipt_reviewer_is_not_an_unbound_mutable_authority_claim() -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    payload = matrix.model_dump(mode="python")
    receipts = list(payload["accepted_gate_closure_receipts"])
    receipts[-1]["reviewer"] = "fabricated-reviewer"
    payload["accepted_gate_closure_receipts"] = tuple(receipts)

    with pytest.raises(ValidationError, match="extra_forbidden"):
        LedgerCapabilityMatrixV1.model_validate(payload)


def test_receipt_identity_change_cannot_be_reminted_by_recomputing_attestation() -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    receipts = (
        *matrix.accepted_gate_closure_receipts[:-1],
        matrix.accepted_gate_closure_receipts[-1].model_copy(update={"receipt_id": "receipt.ledger.reminted"}),
    )
    identities = tuple((receipt.receipt_id, receipt.gate) for receipt in receipts)
    attestation = matrix.acceptance_attestation.model_copy(
        update={
            "closure_receipt_set_digest": LedgerCapabilityMatrixV1.calculate_gate_closure_receipt_set_digest(identities)
        }
    )
    candidate = _matrix_with(
        matrix,
        accepted_gate_closure_receipts=receipts,
        acceptance_attestation=attestation,
    )

    assessment = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY)

    assert not assessment.closed
    assert assessment.blockers == ("matrix validation failed at accepted_gate_closure_receipts.3: value_error",)


def test_matrix_drift_invalidates_receipt_and_relocks_ordered_gates() -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    drift = _evidence(
        "evidence.campaign.receipt_matrix_drift",
        EvidenceRole.MATRIX_PUBLICATION,
        frozenset(LedgerCapabilityAxis),
    )
    candidate = _matrix_with(matrix, campaign_evidence=(*matrix.campaign_evidence, drift))

    g4 = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY)
    ordered = evaluate_ledger_capability_gates(
        candidate,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
        observed_union=_union_denominator(),
    )

    assert not g4.closed
    assert g4.blockers == ("matrix validation failed at <root>: value_error",)
    assert all(not assessment.closed for assessment in ordered)


def test_denominator_and_observed_census_drift_invalidate_receipts_and_relock() -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    drifted_report = _report(revision="census-rev-2", observed_at=_LATER_OBSERVED_AT)
    drifted_denominator = _snapshot(drifted_report)
    candidate = _matrix_with(
        matrix,
        current_denominator=drifted_denominator,
        current_authority_dispositions=_authority_snapshot(drifted_denominator, matrix.rows),
    )

    stale_matrix_g4 = _evaluate(candidate, LedgerGate.G4_TUI_ADMISSION_AND_PARITY, report=drifted_report)
    observed_census_g4 = _evaluate(matrix, LedgerGate.G4_TUI_ADMISSION_AND_PARITY, report=drifted_report)
    ordered = evaluate_ledger_capability_gates(
        candidate,
        observed_census=drifted_report,
        observed_subjects=(_SUBJECT,),
        observed_union=_union_denominator(),
    )

    assert not stale_matrix_g4.closed
    assert stale_matrix_g4.blockers == ("matrix validation failed at <root>: value_error",)
    assert not observed_census_g4.closed
    assert any("denominator" in blocker for blocker in observed_census_g4.blockers)
    assert all(not assessment.closed for assessment in ordered)


def test_active_pre_g3_evaluation_uses_normal_gate_predicates() -> None:
    matrix = _matrix()

    g0 = _evaluate(matrix, LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE)
    g1 = _evaluate(matrix, LedgerGate.G1_SEMANTIC_AUTHORITY_RECOVERY)
    g2 = _evaluate(matrix, LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS)
    g3 = _evaluate(matrix, LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS)
    g4 = _evaluate(matrix, LedgerGate.G4_TUI_ADMISSION_AND_PARITY)

    assert all(not assessment.closed for assessment in (g0, g1, g2, g3))
    assert "the Ledger TUI implementation hold remains active" in g4.blockers


def test_ordered_evaluation_never_allows_a_later_gate_to_close() -> None:
    matrix = _matrix_with_authorized_hold_lift(_matrix())
    drifted_report = _report((_ROW_ID, "ledger.entries.export"))

    assessments = evaluate_ledger_capability_gates(
        matrix,
        observed_census=drifted_report,
        observed_subjects=(_SUBJECT,),
        observed_union=_union_denominator(),
    )

    assert len(assessments) == 5
    assert not assessments[0].closed
    for assessment in assessments[1:-1]:
        assert not assessment.closed
        assert any("new live denominator capability" in blocker for blocker in assessment.blockers)
    assert not assessments[-1].closed
    assert any("denominator" in blocker for blocker in assessments[-1].blockers)


def test_ordered_evaluation_reopens_later_gates_after_a_malformed_subject() -> None:
    malformed_subject = _SUBJECT.model_copy(update={"digest": "subject-secret-not-a-digest"})

    assessments = evaluate_ledger_capability_gates(
        _matrix(),
        observed_census=_report(),
        observed_subjects=(malformed_subject,),
        observed_union=_union_denominator(),
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


def test_gate_reopening_accepts_only_the_unchanged_reviewed_union_and_external_anchor() -> None:
    matrix = build_ledger_capability_matrix()
    assert matrix.live_union is not None

    assert (
        reopened_gates_for_currentness(
            matrix,
            observed_census=matrix_module._matrix_live_report(matrix.live_union),
            observed_subjects=matrix.current_subjects,
            observed_union=matrix.live_union,
        )
        == frozenset()
    )


def test_absent_live_reviewed_union_relocks_every_gate() -> None:
    matrix = _matrix_with_accepted_gate_receipts(_matrix())
    anchor, acceptance_subjects = _acceptance_record_anchor(matrix)

    reopened = reopened_gates_for_currentness(
        matrix,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
        observed_union=None,
        acceptance_record_anchor=anchor,
        observed_acceptance_subjects=acceptance_subjects,
    )
    assessments = evaluate_ledger_capability_gates(
        matrix,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
        observed_union=None,
        acceptance_record_anchor=anchor,
        observed_acceptance_subjects=acceptance_subjects,
    )

    assert reopened == frozenset(LedgerGate)
    assert all(not assessment.closed for assessment in assessments)
    assert all("live reviewed union observation is missing" in assessment.blockers for assessment in assessments)


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("reused_identity_observation", id="new-or-reused-observation"),
        pytest.param("semantic_review", id="home-effect-applicability-gap-proof-route-hold-registry-status"),
        pytest.param("missing_review", id="missing-row-review"),
        pytest.param("evidence_subject", id="evidence-currentness"),
        pytest.param("missing_anchor", id="missing-accepted-anchor"),
    ],
)
def test_any_reviewed_state_or_acceptance_drift_relocks_g0_through_g4(mutation: str) -> None:
    matrix = _matrix_with_accepted_gate_receipts(_matrix())
    anchor, acceptance_subjects = _acceptance_record_anchor(matrix)
    observed_union: LedgerUnionDenominatorV1 | None = _union_denominator()
    subjects = (_SUBJECT,)
    selected_anchor: LedgerAcceptanceRecordAnchorV1 | None = anchor
    selected_anchor_subjects = acceptance_subjects

    if mutation == "reused_identity_observation":
        observations = list(observed_union.observations)
        observations[0] = observations[0].model_copy(update={"capability_ids": (observed_union.rows[1].capability_id,)})
        observed_union = observed_union.model_copy(update={"observations": tuple(observations)})
    elif mutation == "semantic_review":
        row = observed_union.rows[0]
        decisions = list(row.applicability)
        backend_index = next(
            index for index, decision in enumerate(decisions) if decision.axis is LedgerCapabilityAxis.BACKEND
        )
        decisions[backend_index] = decisions[backend_index].model_copy(
            update={
                "applicability": ApplicabilityState.NOT_APPLICABLE,
                "proof": AxisProofState.NOT_APPLICABLE,
                "proof_requirement": "reminted artifact/provenance proof",
            }
        )
        rows = list(observed_union.rows)
        rows[0] = row.model_copy(
            update={
                "semantic_home": row.semantic_home.model_copy(update={"owner": "application.ledger.reminted"}),
                "semantic_home_status": SemanticHomeStatus.EXISTING,
                "effect": LedgerCapabilityEffect.QUERY,
                "applicability": tuple(decisions),
                "gap_classes": frozenset({LedgerGapClass.PRODUCT}),
                "primary_gap_class": LedgerGapClass.PRODUCT,
                "secondary_gap_classes": (),
                "proof_requirements": ("reminted artifact/provenance proof",),
                "tui_routes": ("ledger.entries",),
                "tui_hold_until": None,
                "registry_destination_status": LedgerRegistryDestinationStatus.NOT_APPLICABLE,
            }
        )
        observed_union = observed_union.model_copy(update={"rows": tuple(rows)})
    elif mutation == "missing_review":
        observed_union = observed_union.model_copy(update={"row_review_attestation": None})
    elif mutation == "evidence_subject":
        subjects = (_subject(revision="matrix-rev-2", digest="sha256:" + "b" * 64),)
    else:
        selected_anchor = None
        selected_anchor_subjects = ()

    reopened = reopened_gates_for_currentness(
        matrix,
        observed_census=_report(),
        observed_subjects=subjects,
        observed_union=observed_union,
        acceptance_record_anchor=selected_anchor,
        observed_acceptance_subjects=selected_anchor_subjects,
    )
    assessments = evaluate_ledger_capability_gates(
        matrix,
        observed_census=_report(),
        observed_subjects=subjects,
        observed_union=observed_union,
        acceptance_record_anchor=selected_anchor,
        observed_acceptance_subjects=selected_anchor_subjects,
    )

    assert reopened == frozenset(LedgerGate)
    assert all(not assessment.closed for assessment in assessments)


def test_a_fully_reminted_union_and_receipt_chain_cannot_replace_the_external_anchor() -> None:
    accepted = _matrix_with_accepted_gate_receipts(_matrix())
    old_anchor, old_acceptance_subjects = _acceptance_record_anchor(accepted)
    reminted_live_union = _reminted_live_union()
    reminted_review = LedgerUnionReviewSnapshotV1.from_union(reminted_live_union)
    reminted = _matrix_with_accepted_gate_receipts(
        _matrix(
            accepted_union_review=reminted_review,
            current_union_review=reminted_review,
        )
    )
    new_anchor, new_acceptance_subjects = _acceptance_record_anchor(reminted)

    stale_reopened = reopened_gates_for_currentness(
        reminted,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
        observed_union=reminted_live_union,
        acceptance_record_anchor=old_anchor,
        observed_acceptance_subjects=old_acceptance_subjects,
    )
    current_reopened = reopened_gates_for_currentness(
        reminted,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
        observed_union=reminted_live_union,
        acceptance_record_anchor=new_anchor,
        observed_acceptance_subjects=new_acceptance_subjects,
    )

    assert reminted.accepted_union_review == reminted.current_union_review == reminted_review
    assert stale_reopened == frozenset(LedgerGate)
    assert current_reopened == frozenset(LedgerGate)


@pytest.mark.parametrize("malformed", ["union", "anchor"])
def test_production_currentness_evaluators_fail_closed_for_malformed_external_inputs(malformed: str) -> None:
    matrix = _matrix_with_accepted_gate_receipts(_matrix())
    anchor, acceptance_subjects = _acceptance_record_anchor(matrix)
    union: LedgerUnionDenominatorV1 | None = _union_denominator()
    selected_anchor: LedgerAcceptanceRecordAnchorV1 | None = anchor
    if malformed == "union":
        union = union.model_copy(update={"digest": "sha256:" + "b" * 64})
    else:
        selected_anchor = anchor.model_copy(update={"reviewer": "fabricated-reviewer"})

    reopened = reopened_gates_for_currentness(
        matrix,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
        observed_union=union,
        acceptance_record_anchor=selected_anchor,
        observed_acceptance_subjects=acceptance_subjects,
    )
    assessments = evaluate_ledger_capability_gates(
        matrix,
        observed_census=_report(),
        observed_subjects=(_SUBJECT,),
        observed_union=union,
        acceptance_record_anchor=selected_anchor,
        observed_acceptance_subjects=acceptance_subjects,
    )

    assert reopened == frozenset(LedgerGate)
    assert all(not assessment.closed for assessment in assessments)


def test_canonical_matrix_builds_every_reviewed_union_row_deterministically() -> None:
    first = build_ledger_capability_matrix()
    second = build_ledger_capability_matrix()
    union = _union_denominator()

    assert len(first.rows) == 694 == union.reviewed_row_count
    assert {row.identity.row_id for row in first.rows} == {row.capability_id for row in union.rows}
    assert first.current_denominator.capability_ids == {row.capability_id for row in union.rows}
    assert first.current_union_review.capability_ids == tuple(row.capability_id for row in union.rows)
    assert first.live_union == union
    assert first.matrix_digest == second.matrix_digest
    assert LedgerCapabilityMatrixV1.model_validate(first.model_dump(mode="python")) == first
    assert first.acceptance_attestation.ruling is ReviewRuling.REJECT
    assert first.accepted_gate_closure_receipts == ()


@pytest.mark.parametrize("identity_mutation", ["subset", "extra", "duplicate"])
def test_canonical_matrix_refuses_row_identity_mismatch_even_after_digest_remint(identity_mutation: str) -> None:
    matrix = build_ledger_capability_matrix()
    rows = list(matrix.rows)
    if identity_mutation == "subset":
        rows.pop()
    elif identity_mutation == "extra":
        exemplar = rows[-1]
        extra_id = f"{exemplar.identity.row_id}.unexpected"
        rows.append(
            exemplar.model_copy(
                update={
                    "identity": LedgerCapabilityIdentityV1(
                        capability_id=extra_id,
                        operation_id=extra_id,
                        suboperation_id=extra_id,
                    )
                }
            )
        )
    else:
        rows.append(rows[-1])
    provisional = matrix.model_copy(update={"rows": tuple(rows)})
    reminted = provisional.model_copy(update={"matrix_digest": provisional.calculated_matrix_digest})

    expected = "duplicate row identities" if identity_mutation == "duplicate" else "current complete denominator"
    with pytest.raises(ValidationError, match=expected):
        LedgerCapabilityMatrixV1.model_validate(reminted.model_dump(mode="python"))


def test_matrix_contract_source_digest_normalizes_checkout_newlines(tmp_path: Path) -> None:
    lf = tmp_path / "matrix-lf.py"
    crlf = tmp_path / "matrix-crlf.py"
    lf.write_bytes(b"first\nsecond\n")
    crlf.write_bytes(b"first\r\nsecond\r\n")

    assert ledger_capability_matrix_source_digest(lf) == ledger_capability_matrix_source_digest(crlf)
    crlf.write_bytes(b"first\r\nchanged\r\n")
    assert ledger_capability_matrix_source_digest(lf) != ledger_capability_matrix_source_digest(crlf)
    assert ledger_capability_matrix_source_digest().startswith("sha256:")


def test_human_matrix_contract_coordinate_matches_live_source_digest() -> None:
    """The reference coordinate must publish the digest the contract computes."""
    assert _published_matrix_contract_digest() == ledger_capability_matrix_source_digest()


def test_g0_refuses_a_small_fixture_without_a_live_union_identity_observation() -> None:
    assessment = _evaluate(_matrix(), LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, union=None)

    assert not assessment.closed
    assert "live reviewed union observation is missing" in assessment.blockers


def test_g0_refuses_a_small_matrix_against_the_complete_observed_union() -> None:
    """A complete review snapshot must not let a fixture bypass row identity equality."""
    assessment = _evaluate(_matrix(), LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE, union=_union_denominator())

    assert not assessment.closed
    assert "matrix row identities do not exactly equal the observed live reviewed union" in assessment.blockers
    assert "matrix denominator identities do not exactly equal the observed live reviewed union" in assessment.blockers
    assert "matrix live reviewed union is missing" in assessment.blockers


def test_currentness_requires_the_persisted_and_observed_live_unions_to_match() -> None:
    matrix = build_ledger_capability_matrix()
    candidate = _matrix_with(matrix, live_union=None)

    errors = validate_ledger_matrix_currentness(
        candidate,
        observed_census=matrix_module._matrix_live_report(_union_denominator()),
        observed_subjects=candidate.current_subjects,
        observed_union=_union_denominator(),
    )

    assert errors == ["matrix live reviewed union is missing"]


def test_canonical_matrix_losslessly_projects_reviewed_gap_and_surface_cohorts() -> None:
    matrix = build_ledger_capability_matrix()
    union_rows = {row.capability_id: row for row in _union_denominator().rows}
    matrix_rows = {row.identity.row_id: row for row in matrix.rows}

    assert set(matrix_rows) == set(union_rows)
    assert {row_id for row_id, row in matrix_rows.items() if CapabilityAnnotation.CLI_OWNED in row.annotations} == {
        row_id for row_id, row in union_rows.items() if LedgerGapClass.AUTHORITY in row.gap_classes
    }
    assert {
        row_id for row_id, row in matrix_rows.items() if CapabilityAnnotation.COMPONENT_ONLY in row.annotations
    } == {row_id for row_id, row in union_rows.items() if LedgerGapClass.REACHABILITY in row.gap_classes}
    assert {row_id for row_id, row in matrix_rows.items() if CapabilityAnnotation.INSTALLED in row.annotations} == {
        "ledger.workspace.read",
    }
    preparation = matrix_rows["ledger.import.prepare"]
    assert preparation.annotations == frozenset()
    assert preparation.tui_hold_until is None
    assert preparation.assessment(LedgerCapabilityAxis.BACKEND).surface_state is SurfaceCapabilityState.ABSENT
    assert preparation.assessment(LedgerCapabilityAxis.CLI).surface_state is SurfaceCapabilityState.NOT_APPLICABLE
    assert preparation.assessment(LedgerCapabilityAxis.TUI).surface_state is SurfaceCapabilityState.NOT_APPLICABLE
    for row_id, reviewed in union_rows.items():
        matrix_row = matrix_rows[row_id]
        assert {finding.gap_class for finding in matrix_row.findings} == reviewed.gap_classes
        assert all(finding.description == " ".join(reviewed.blockers) for finding in matrix_row.findings)
        assert matrix_row.authority_migration.initial_cli_ownership is (
            InitialCliOwnership.CLI_OWNED
            if LedgerGapClass.AUTHORITY in reviewed.gap_classes
            else InitialCliOwnership.NOT_CLI_OWNED
        )


def test_matrix_projection_cohort_mutations_follow_the_reviewed_row_not_axis_defaults() -> None:
    union = _union_denominator()
    subject = matrix_module._matrix_subject(union)
    component_review = next(row for row in union.rows if row.capability_id == "ledger.transaction.list")
    installed_review = next(row for row in union.rows if row.capability_id == "ledger.workspace.read")

    without_reachability = component_review.model_copy(
        update={"gap_classes": component_review.gap_classes - {LedgerGapClass.REACHABILITY}}
    )
    with_reachability = installed_review.model_copy(
        update={"gap_classes": installed_review.gap_classes | {LedgerGapClass.REACHABILITY}}
    )

    assert (
        CapabilityAnnotation.COMPONENT_ONLY
        not in matrix_module._matrix_row_from_union(without_reachability, subject).annotations
    )
    assert (
        CapabilityAnnotation.INSTALLED
        not in matrix_module._matrix_row_from_union(with_reachability, subject).annotations
    )
    assert (
        CapabilityAnnotation.COMPONENT_ONLY
        in matrix_module._matrix_row_from_union(with_reachability, subject).annotations
    )
