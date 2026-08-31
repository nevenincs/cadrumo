"""Strict JSON roundtrip test for :class:`PullResult` and its leaf records.

The discipline rule (``aeat-quality-gates``) requires a dedicated
``model_dump_json`` → ``model_validate_json`` test for every persistence-
shaped pydantic model that flows over the wire. ``PullResult`` is the
Google Sheets pull adapter's wire shape — :func:`compute_from_pull`
consumes one directly and the CLI ``aeat config google sync calc pull``
verb persists it as JSON. The export→pull→compute integration test
exercises the full pipeline; this module pins the JSON boundary
independently so a field renamed-out or save-dropped regression
surfaces immediately.

Coverage:

- Every leaf record (``OperatorEdit``, ``BindingEdit``, ``RelationEdit``,
  ``RowSetCellEdit``, ``RowSetEdit``, ``PullMetadata``) is populated to
  a non-default state.
- Strict pydantic equality (``round_tripped == original``) is asserted
  across the boundary.
- An anti-tautology proof test mutates the on-disk JSON to drop a
  required field and asserts the reload raises ``ValidationError``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.casilla_id import CasillaId, validated_casilla_id
from ..calc_sheets_pull_records import (
    BindingEdit,
    MetadataMatchState,
    OperatorEdit,
    PullMetadata,
    PullResult,
    RelationEdit,
    RowSetCellEdit,
    RowSetEdit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_M100_CASILLA_0001: CasillaId = validated_casilla_id("modelo-100-casilla-0001", surface="_M100_CASILLA_0001")
_M100_CASILLA_0002: CasillaId = validated_casilla_id("modelo-100-casilla-0002", surface="_M100_CASILLA_0002")
_M100_CASILLA_0003: CasillaId = validated_casilla_id("modelo-100-casilla-0003", surface="_M100_CASILLA_0003")
_M100_CASILLA_0004: CasillaId = validated_casilla_id("modelo-100-casilla-0004", surface="_M100_CASILLA_0004")


def _populated_pull_result() -> PullResult:
    """A PullResult with every defaultable field populated to a non-default value.

    Avoids numeric-shape strings (e.g. ``"04"``) in the str-valued
    fixtures because :class:`BindingEdit.value` and
    :class:`OperatorEdit.value` carry a Decimal | str | bool | None
    union whose wire JSON serialisation cannot statically distinguish
    a ``Decimal("4")`` from the string ``"04"``. The runtime path in
    :func:`compute_from_pull` handles the ambiguity at the dispatch
    site; the wire roundtrip cannot. Use unambiguously non-numeric
    strings (alpha tokens, alphanumerics, special chars) so the union
    resolution is deterministic and the test asserts strict equality.
    """

    return PullResult(
        spreadsheet_id="spreadsheet-fixture-001",
        operator_edits=(
            OperatorEdit(
                casilla_id=_M100_CASILLA_0001,
                display_number="0001",
                label="Casilla 0001",
                value=Decimal("1234.56"),
            ),
            OperatorEdit(
                casilla_id=_M100_CASILLA_0002,
                display_number="0002",
                label="Casilla 0002",
                value="text-shape",  # unambiguous str path
            ),
            OperatorEdit(
                casilla_id=_M100_CASILLA_0003,
                display_number="0003",
                label="Casilla 0003",
                value=True,  # bool path
            ),
            OperatorEdit(
                casilla_id=_M100_CASILLA_0004,
                display_number="0004",
                label="Casilla 0004",
                value=None,
            ),
        ),
        binding_edits=(
            BindingEdit(binding="binding.modelo-100.ccaa-code", value="ES-CT"),
            BindingEdit(binding="binding.modelo-100.gross-amount", value=Decimal("9876.54")),
            BindingEdit(binding="binding.modelo-100.unset", value=None),
        ),
        relation_edits=(
            RelationEdit(
                relation="relation.cross.prior-period",
                value=Decimal("42.00"),
                provenance="local_filing",
                source_modelo="130",
                source_filing_year=2024,
                source_periods=("1T", "2T", "3T"),
                source_casilla_ids=("19",),
                legal_refs=("ley-35-2006:art-99",),
                source_refs=("boe-modelo-130-2024-form",),
                resolved_at=datetime(2025, 4, 10, 12, 0, 0, tzinfo=UTC),
            ),
            RelationEdit(relation="relation.cross.unset", value=None),
        ),
        row_set_edits=(
            RowSetEdit(
                grouping="detalle-actividades",
                cells=(
                    RowSetCellEdit(binding="binding.detalle.code", row_index=1, value="alpha-A01"),
                    RowSetCellEdit(binding="binding.detalle.amount", row_index=1, value=Decimal("100.00")),
                    RowSetCellEdit(binding="binding.detalle.amount", row_index=2, value=Decimal("200.00")),
                    RowSetCellEdit(binding="binding.detalle.note", row_index=3, value=None),
                ),
            ),
            RowSetEdit(grouping="detalle-empty"),
        ),
        metadata=PullMetadata(
            modelo_id="100",
            revision_id="2024-y-siguientes",
            filing_year=2024,
            period="0A",
            engine_version="v1.2.3",
            registry_sha="0123456789abcdef" * 4,  # 64-char SHA shape
            exported_at="2025-04-15T10:30:00+00:00",
        ),
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=42,
    )


def test_pull_result_json_roundtrip_preserves_strict_equality() -> None:
    """Build a populated PullResult, push through the JSON cycle, assert equality.

    The model_dump_json/model_validate_json pair IS the boundary the
    Google Sheets pull adapter relies on for persistence; this test
    pins that the wire shape survives the round-trip with zero field
    loss and exact value preservation (including the Decimal | str |
    bool | None union on edit values and the metadata_match Literal).
    """

    original = _populated_pull_result()
    encoded = original.model_dump_json()
    roundtripped = PullResult.model_validate_json(encoded)
    assert roundtripped == original


def test_pull_result_json_roundtrip_preserves_decimal_precision() -> None:
    """Decimal values must not collapse to float across the JSON boundary."""

    original = _populated_pull_result()
    encoded = original.model_dump_json()
    roundtripped = PullResult.model_validate_json(encoded)
    # Pull the gross-amount binding edit back out and assert it is still
    # a Decimal with the original textual representation (not 9876.54
    # printed via repr but the exact two-place form pydantic decoded).
    gross = next(edit for edit in roundtripped.binding_edits if edit.binding == "binding.modelo-100.gross-amount")
    assert isinstance(gross.value, Decimal)
    assert gross.value == Decimal("9876.54")
    # And the first row-set cell with a Decimal value:
    detalle = roundtripped.row_set_edits[0]
    amount_cell = next(
        cell for cell in detalle.cells if cell.binding == "binding.detalle.amount" and cell.row_index == 1
    )
    assert isinstance(amount_cell.value, Decimal)
    assert amount_cell.value == Decimal("100.00")
    # Relation provenance fields recovered from developer metadata must
    # round-trip strictly: the apply adapter writes provenance / source
    # year / periods / resolved_at; the pull adapter must read them back.
    prior = next(edit for edit in roundtripped.relation_edits if edit.relation == "relation.cross.prior-period")
    assert prior.provenance == "local_filing"
    assert prior.source_modelo == "130"
    assert prior.source_filing_year == 2024
    assert prior.source_periods == ("1T", "2T", "3T")
    assert prior.source_casilla_ids == ("19",)
    assert prior.legal_refs == ("ley-35-2006:art-99",)
    assert prior.source_refs == ("boe-modelo-130-2024-form",)
    assert prior.resolved_at == datetime(2025, 4, 10, 12, 0, 0, tzinfo=UTC)


def test_pull_result_round_trip_dropped_required_field_raises() -> None:
    """Anti-tautology proof: mutate the JSON to drop a required field and
    assert pydantic refuses to reconstitute the model. If this ever
    passes silently, the roundtrip-vs-broken-payload contract is
    tautological and every other roundtrip in the suite is weakened.
    """

    original = _populated_pull_result()
    encoded = json.loads(original.model_dump_json())
    # Drop the metadata.modelo_id field — the strict frozen pydantic
    # config rejects partial PullMetadata; the load MUST fail.
    del encoded["metadata"]["modelo_id"]
    mutated = json.dumps(encoded)
    with pytest.raises(ValidationError):
        PullResult.model_validate_json(mutated)


def test_binding_edit_numeric_shape_string_coerces_to_decimal_on_json_reload() -> None:
    """Document the known wire-ambiguity caveat.

    JSON cannot statically distinguish a numeric-shape string
    ``"04"`` from a Decimal — pydantic serialises Decimal as a JSON
    string and the union resolver picks Decimal first when reloading.
    Operators relying on CCAA-shape strings flowing through the wire
    intact should set up an enum binding (``binding.typed_enum`` on
    the snapshot) so the runtime dispatch in
    :func:`compute_from_pull._enum_binding_text` routes the str-form
    explicitly. This test pins the documented behaviour so a future
    fix (e.g. discriminated union, custom JSON encoder) updates the
    test alongside the model.
    """

    edit = BindingEdit(binding="binding.modelo-100.ccaa-code", value="04")
    encoded = edit.model_dump_json()
    roundtripped = BindingEdit.model_validate_json(encoded)
    # The wire JSON cannot distinguish "04" the string from Decimal(4)
    # the number; the union resolver picks Decimal.
    assert roundtripped.value == Decimal("4")


def test_pull_result_round_trip_extra_field_raises() -> None:
    """Anti-tautology proof: extra keys are rejected by extra='forbid'.

    The strict-frozen config rejects unknown keys; a save that
    silently dropped a field plus a load that silently accepted an
    unknown one would yield a false-positive roundtrip. Pin that
    extras still fail loudly.
    """

    original = _populated_pull_result()
    encoded = json.loads(original.model_dump_json())
    encoded["unexpected_field"] = "smuggled-in"
    mutated = json.dumps(encoded)
    with pytest.raises(ValidationError):
        PullResult.model_validate_json(mutated)


def test_operator_edit_rejects_generic_casilla_key() -> None:
    """The pull adapter exposes the canonical casilla_id key, not a second casilla dialect."""

    with pytest.raises(ValidationError):
        OperatorEdit.model_validate(
            {
                "casilla": _M100_CASILLA_0001,
                "display_number": "0001",
                "label": "Casilla 0001",
                "value": "1234.56",
            },
        )
