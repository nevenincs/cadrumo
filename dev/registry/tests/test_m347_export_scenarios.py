"""Populated export scenarios preserve resolved rows and threshold exclusion."""

from decimal import Decimal

import pytest

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.runtime import ModeloOperatorProfile, schema_provider_from_authority
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.submission.models import ModeloDraftStatus

from ..compiler.authority import compiled_bundled_authority
from ..edition_export_scenarios import edition_export_scenarios
from ..edition_round_trip import SYNTHETIC_TAX_ID, _PayloadSink

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.mark.parametrize("revision_id", ["2011-2024", "2025-y-siguientes"])
def test_populated_scenario_exports_both_parties_and_excludes_below_threshold(revision_id: str) -> None:
    scenario = edition_export_scenarios("347")[revision_id]
    assert scenario.inputs["modelo-347-declarante-numero-personas-entidades"] == Decimal(2)
    assert scenario.inputs["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("24200")
    authority = compiled_bundled_authority()
    with validating_governed_facts(authority):
        provider = schema_provider_from_authority(
            authority, modelos=("347",), filing_year=scenario.period.filing_year, period=scenario.period
        )
        draft = build_draft(
            modelo="347",
            period=scenario.period,
            profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Ejemplo ficticio"),
            inputs=scenario.inputs,
            schema_provider=provider,
        )
        assert draft.snapshot_ref.revision_id == revision_id
        sink = _PayloadSink()
        export_draft(
            draft.model_copy(update={"status": ModeloDraftStatus.APROBADO}),
            payload_consumer=sink,
            producer_snapshot=scenario.producer_snapshot(),
            schema_provider=provider,
        )
    assert sink.payload
    assert b"12345678Z" in sink.payload
    assert b"87654321X" in sink.payload
    assert b"Proveedor ficticio Ana" in sink.payload
    assert b"Cliente ficticio Luis" in sink.payload
    assert b"22222222J" not in sink.payload  # Below the annual declaration threshold.
    assert b"11111111H" not in sink.payload  # This scenario excludes the rental family.
