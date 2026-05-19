"""Contract tests for ``compute_from_pull``.

The pull adapter exposes ``compute_from_pull`` so the operator can
locally re-evaluate a workbook's calculations after pulling. The
function maps each ``PullResult`` edit family back to the runtime's
``inputs`` / ``binding_values`` / ``enum_binding_values`` /
``relation_values`` mappings, then invokes the registry formula
runtime against the supplied snapshot.

These tests guard the mapping shape (None coercion, string-to-Decimal,
enum routing) and the ``metadata_match`` refusal path that prevents
computing against a workbook whose registry-SHA stamp does not match
the snapshot.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.resources import resources
from ...outbound.storage._errors import OutboundStorageConflictError
from ._calc_sheets_pull import (
    BindingEdit,
    OperatorEdit,
    PullMetadata,
    PullResult,
    RelationEdit,
    compute_from_pull,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def _modelo_130_snapshot():
    from datetime import date

    return resources().modelos.authority.snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))


def _matching_metadata(snapshot) -> PullMetadata:
    """Build a PullMetadata that matches the snapshot's registry-SHA stamp."""

    from ....application.storage.calc_sheets._engine import _registry_sha

    return PullMetadata(
        modelo_id=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
        engine_version="calc-sheets/0.1.0",
        registry_sha=_registry_sha(snapshot),
    )


def _stale_metadata(snapshot) -> PullMetadata:
    return PullMetadata(
        modelo_id=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
        engine_version="calc-sheets/0.1.0",
        registry_sha="0" * 16,
    )


def _operator_edits_for(snapshot, values: dict[str, Decimal | str | None]) -> tuple[OperatorEdit, ...]:
    """Build OperatorEdit tuples covering every manual / bound casilla.

    `values` is keyed by casilla id; missing casillas get a `None` value
    (which compute_from_pull defaults to Decimal('0')).
    """

    edits: list[OperatorEdit] = []
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind in ("computed", "informational"):
            continue
        edits.append(
            OperatorEdit(
                casilla=casilla.id,
                casilla_number=casilla.number,
                label=casilla.label,
                value=values.get(casilla.id),
            )
        )
    return tuple(edits)


def _binding_edits_for(snapshot) -> tuple[BindingEdit, ...]:
    return tuple(BindingEdit(binding=binding.id, value=Decimal("0")) for binding in snapshot.revision.bindings)


def _relation_edits_for(snapshot) -> tuple[RelationEdit, ...]:
    """Build RelationEdit tuples for relations active in the snapshot period.

    The runtime rejects unknown relation_values (relations whose
    ``target_periods`` exclude the snapshot's period). Filter here so
    the test fixture matches the runtime's active-relation contract.
    """

    return tuple(
        RelationEdit(relation=relation.id, value=Decimal("0"))
        for relation in snapshot.revision.relations
        if not relation.target_periods or snapshot.period in relation.target_periods
    )


def test_compute_from_pull_refuses_stale_workbook() -> None:
    snapshot = _modelo_130_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=_operator_edits_for(snapshot, {}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_stale_metadata(snapshot),
        metadata_match="stale",
        cells_read=0,
    )

    with pytest.raises(OutboundStorageConflictError, match="metadata_match='stale'"):
        compute_from_pull(snapshot, pull)


def test_compute_from_pull_refuses_missing_metadata() -> None:
    snapshot = _modelo_130_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=_operator_edits_for(snapshot, {}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_stale_metadata(snapshot),
        metadata_match="missing",
        cells_read=0,
    )

    with pytest.raises(OutboundStorageConflictError, match="metadata_match='missing'"):
        compute_from_pull(snapshot, pull)


def test_compute_from_pull_runs_against_matching_snapshot() -> None:
    """Happy path: matching metadata + zero inputs returns a valid result."""

    snapshot = _modelo_130_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=_operator_edits_for(snapshot, {}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_matching_metadata(snapshot),
        metadata_match="matches",
        cells_read=0,
    )

    result = compute_from_pull(snapshot, pull)

    # Modelo 130 has computed casillas (rendimiento neto, pago fraccionado,
    # diferencia, resultado final). With zero inputs the chain evaluates
    # consistently to zero.
    assert result.modelo == "130"
    assert result.revision == "2019-y-siguientes"


def test_compute_from_pull_coerces_string_operator_values_to_decimal() -> None:
    """Operator values arriving as strings (Sheets text-format cells) parse cleanly."""

    snapshot = _modelo_130_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=_operator_edits_for(snapshot, {"01": "10000.50"}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_matching_metadata(snapshot),
        metadata_match="matches",
        cells_read=1,
    )

    result = compute_from_pull(snapshot, pull)

    assert result.modelo == "130"
    # Casilla 01 ("Ingresos") should reach the runtime as Decimal("10000.50").
    # The downstream casilla 03 (rendimiento neto = 01 - 02) should
    # therefore evaluate to 10000.50 - 0 = 10000.50.
    casilla_03_value = next(entry.value for entry in result.entries if entry.target == "03")
    assert casilla_03_value == Decimal("10000.50")


def test_compute_from_pull_coerces_malformed_string_to_zero() -> None:
    """Malformed string values default to Decimal('0') rather than crashing."""

    snapshot = _modelo_130_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=_operator_edits_for(snapshot, {"01": "not-a-number"}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_matching_metadata(snapshot),
        metadata_match="matches",
        cells_read=1,
    )

    result = compute_from_pull(snapshot, pull)

    casilla_03_value = next(entry.value for entry in result.entries if entry.target == "03")
    assert casilla_03_value == Decimal("0")
