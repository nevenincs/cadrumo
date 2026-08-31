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

from collections.abc import Mapping
from decimal import Decimal

import pytest

from .....application.storage.calc_sheets.engine import CALC_SHEETS_ENGINE_VERSION
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.schema_input_kind import InputKind
from ...storage.errors import OutboundStorageConflictError, OutboundStorageValidationError
from ..calc_sheets_pull import compute_from_pull
from ..calc_sheets_pull_records import (
    BindingEdit,
    MetadataMatchState,
    OperatorEdit,
    PullMetadata,
    PullResult,
    RelationEdit,
)
from ._calc_sheets_support import modelo_130_2025_1t_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M303_PRINTED_RESULT_REFERENCE_CASILLA: CasillaId = validated_casilla_id(
    "69",
    surface="_M303_PRINTED_RESULT_REFERENCE_CASILLA",
)


def _modelo_303_snapshot():
    from datetime import date

    return bundled_authority().snapshot("303", filing_year=2025, period="1T", on=date(2025, 4, 1))


def _matching_metadata(snapshot) -> PullMetadata:
    """Build a PullMetadata that matches the snapshot's registry-SHA stamp."""

    from .....application.storage.calc_sheets.engine import registry_sha

    return PullMetadata(
        modelo_id=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
        engine_version=CALC_SHEETS_ENGINE_VERSION,
        registry_sha=registry_sha(snapshot),
    )


def _stale_metadata(snapshot) -> PullMetadata:
    return PullMetadata(
        modelo_id=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
        engine_version=CALC_SHEETS_ENGINE_VERSION,
        registry_sha="0" * 16,
    )


def _operator_edits_for(snapshot, values: Mapping[CasillaId, Decimal | str | None]) -> tuple[OperatorEdit, ...]:
    """Build OperatorEdit tuples covering every manual / bound casilla.

    `values` is keyed by casilla id; missing casillas get a `None` value
    (which compute_from_pull defaults to Decimal('0')).
    """

    edits: list[OperatorEdit] = []
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind in (InputKind.COMPUTED, InputKind.INFORMATIONAL):
            continue
        edits.append(
            OperatorEdit(
                casilla_id=casilla.id,
                display_number=casilla.number,
                label=casilla.label,
                value=values.get(casilla.id),
            ),
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
    snapshot = modelo_130_2025_1t_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=_operator_edits_for(snapshot, {}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_stale_metadata(snapshot),
        metadata_match=MetadataMatchState.STALE,
        cells_read=0,
    )

    with pytest.raises(OutboundStorageConflictError, match=r"metadata_match=<MetadataMatchState\.STALE") as raised:
        compute_from_pull(snapshot, pull)

    assert raised.value.translated_message == "adapters.google.calc_sheets.errors.workbook_snapshot_mismatch"
    assert raised.value.context is not None
    assert raised.value.context["spreadsheet_id"] == "test-id"
    assert not hasattr(raised.value, "suggestion")


def test_compute_from_pull_refuses_prechange_engine_even_with_matching_verdict() -> None:
    """The compute defense cannot be bypassed with a forged matching verdict."""

    snapshot = modelo_130_2025_1t_snapshot()
    pull = PullResult(
        spreadsheet_id="prechange-engine-test-id",
        operator_edits=_operator_edits_for(snapshot, {}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_matching_metadata(snapshot).model_copy(update={"engine_version": "calc-sheets/0.1.0"}),
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=0,
    )

    with pytest.raises(OutboundStorageConflictError) as raised:
        compute_from_pull(snapshot, pull)

    assert raised.value.context is not None
    assert raised.value.context["workbook_engine_version"] == "calc-sheets/0.1.0"
    assert raised.value.context["expected_engine_version"] == CALC_SHEETS_ENGINE_VERSION


def test_compute_from_pull_refuses_printed_number_operator_edit_reference() -> None:
    snapshot = _modelo_303_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=(
            *_operator_edits_for(snapshot, {}),
            OperatorEdit(
                casilla_id=_M303_PRINTED_RESULT_REFERENCE_CASILLA,
                display_number="69",
                label="Printed reference for iva.resultado",
                value=Decimal("0"),
            ),
        ),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_matching_metadata(snapshot),
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=1,
    )

    with pytest.raises(OutboundStorageValidationError, match=r"canonical input casilla\.id"):
        compute_from_pull(snapshot, pull)


def test_compute_from_pull_refuses_missing_metadata() -> None:
    snapshot = modelo_130_2025_1t_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=_operator_edits_for(snapshot, {}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_stale_metadata(snapshot),
        metadata_match=MetadataMatchState.MISSING,
        cells_read=0,
    )

    with pytest.raises(OutboundStorageConflictError, match=r"metadata_match=<MetadataMatchState\.MISSING"):
        compute_from_pull(snapshot, pull)


def test_compute_from_pull_refuses_contradictory_matching_metadata_verdict() -> None:
    """A MATCHES verdict cannot override metadata that no longer binds to the snapshot."""

    snapshot = modelo_130_2025_1t_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=_operator_edits_for(snapshot, {_M130_INGRESOS_CASILLA: Decimal("100")}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_stale_metadata(snapshot),
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=1,
    )

    with pytest.raises(OutboundStorageConflictError) as raised:
        compute_from_pull(snapshot, pull)

    assert raised.value.context is not None
    assert raised.value.context["workbook_registry_sha"] == "0" * 16
    assert raised.value.context["snapshot_registry_sha"] == _matching_metadata(snapshot).registry_sha
    assert raised.value.translated_message == "adapters.google.calc_sheets.errors.workbook_snapshot_mismatch"


def test_compute_from_pull_runs_against_matching_snapshot() -> None:
    """Happy path: matching metadata + zero inputs returns a valid result."""

    snapshot = modelo_130_2025_1t_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=_operator_edits_for(snapshot, {}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_matching_metadata(snapshot),
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=0,
    )

    result = compute_from_pull(snapshot, pull)

    # Modelo 130 has computed casillas (rendimiento neto, pago fraccionado,
    # diferencia, resultado final). With zero inputs the chain evaluates
    # consistently to zero.
    assert result.modelo == "130"
    assert result.revision == snapshot.revision.id


def test_compute_from_pull_coerces_string_operator_values_to_decimal() -> None:
    """Operator values arriving as strings (Sheets text-format cells) parse cleanly."""

    snapshot = modelo_130_2025_1t_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=_operator_edits_for(snapshot, {_M130_INGRESOS_CASILLA: "10000.50"}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_matching_metadata(snapshot),
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=1,
    )

    result = compute_from_pull(snapshot, pull)

    assert result.modelo == "130"
    # Casilla 01 ("Ingresos") is a bound casilla fed via operator edits;
    # the string "10000.50" must arrive at the runtime as Decimal("10000.50").
    casilla_01_obs = next(obs for obs in result.observations if obs.casilla_id == _M130_INGRESOS_CASILLA)
    assert casilla_01_obs.value == Decimal("10000.50")


@pytest.mark.parametrize("raw_value", ("not-a-number", "NaN", "Infinity", "-Infinity"))
def test_compute_from_pull_refuses_malformed_or_non_finite_string(raw_value: str) -> None:
    """An explicit malformed spreadsheet edit cannot silently replace a financial input with zero."""

    snapshot = modelo_130_2025_1t_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=_operator_edits_for(snapshot, {_M130_INGRESOS_CASILLA: raw_value}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_matching_metadata(snapshot),
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=1,
    )

    with pytest.raises(OutboundStorageValidationError, match="must be a finite decimal") as raised:
        compute_from_pull(snapshot, pull)

    assert raised.value.context == {"input_key": _M130_INGRESOS_CASILLA, "value": raw_value}


def test_compute_from_pull_normalizes_european_numeric_string() -> None:
    """A Sheets text cell using Spanish separators preserves the intended amount."""
    snapshot = modelo_130_2025_1t_snapshot()
    pull = PullResult(
        spreadsheet_id="test-id",
        operator_edits=_operator_edits_for(snapshot, {_M130_INGRESOS_CASILLA: "1.234,56"}),
        binding_edits=_binding_edits_for(snapshot),
        relation_edits=_relation_edits_for(snapshot),
        metadata=_matching_metadata(snapshot),
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=1,
    )

    result = compute_from_pull(snapshot, pull)

    casilla_01_obs = next(obs for obs in result.observations if obs.casilla_id == _M130_INGRESOS_CASILLA)
    assert casilla_01_obs.value == Decimal("1234.56")
