"""Blank optional filing slots do not imply failed value extraction."""

from decimal import Decimal

import pytest

from ......core.casilla_value_kind import CasillaValueKind
from ......domain.calculations.registry.authority import bundled_indexed_authority
from ......domain.calculations.registry.export import resolve_export_layout
from ......domain.calculations.registry.export_parse import parse_filed_payload
from ......domain.calculations.registry.schema_exports import ExportLayoutDefinition, ExportRecordDefinition
from ......domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..declarations_observations import submitted_file_coverage_for_casillas
from ..schema import ObservedCasillaValue

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize(
    ("optional_declared", "drop_optional", "drop_zero", "expected"),
    [
        (False, False, False, 1.0),
        (True, False, False, 1.0),
        (True, True, False, 0.5),
        (True, False, True, 0.5),
    ],
)
def test_optional_slot_coverage(optional_declared: bool, drop_optional: bool, drop_zero: bool, expected: float) -> None:
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("303", filing_year=filing_year_envelope().horizon, period="3T")
        resolved = resolve_export_layout(snapshot)
        optional = resolved.fields_by_casilla["169"][0].model_copy(update={"offset": 1})
        # The slot is an enumerated integer: a declared value is one the edition's own design admits.
        assert optional.allowed_values is not None
        optional_token = (
            optional.allowed_values[0].encode().rjust(optional.length or 0, b"0")
            if optional_declared
            else b"0" * (optional.length or 0)
        )
        amount = next(
            field
            for field in resolved.fields_by_id.values()
            if (field.casilla_id is not None and field.casilla_id) and field.data_type == "decimal"
        ).model_copy(update={"offset": 6})
        layout = ExportLayoutDefinition(
            id="optional-coverage-proof",
            legal_refs=optional.legal_refs,
            source_refs=optional.source_refs,
            records=(
                ExportRecordDefinition(
                    id="coverage",
                    record_type="coverage",
                    order=0,
                    encoding="iso-8859-1",
                    line_ending="none",
                    fields=(optional, amount),
                ),
            ),
        )
        snapshot = snapshot.model_copy(
            update={"revision": snapshot.revision.model_copy(update={"export_layouts": (layout,)})}
        )
        assert amount.length is not None
        body = optional_token + b"0" * amount.length
        parsed = parse_filed_payload(layout, body)
        assert any(field.value == Decimal(0) for field in parsed.fields)
        observations = tuple(
            ObservedCasillaValue(
                casilla_id=field.casilla_id,
                value=str(field.value),
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator=field.source_locator,
                confidence=1.0,
            )
            for field in parsed.fields
            if (field.casilla_id is not None and field.casilla_id)
            and field.value is not None
            and not (drop_optional and field.casilla_id == "169")
            and not (drop_zero and field.casilla_id == amount.casilla_id)
        )
        assert (
            submitted_file_coverage_for_casillas(
                snapshot=snapshot, body=body, casillas=observations, operation=operation
            )
            == expected
        )
