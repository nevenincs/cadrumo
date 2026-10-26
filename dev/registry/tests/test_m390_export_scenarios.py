"""Annual export scenarios carry their resolved neutral envelope election."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.filing.runtime import ModeloOperatorProfile, schema_provider_from_authority
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.filing.errors import FilingExportError
from cadrumo.domain.submission.models import ModeloDraftStatus

from ..compiler.authority import compiled_bundled_authority
from ..edition_export_scenarios import edition_export_scenarios
from ..edition_round_trip import SYNTHETIC_TAX_ID

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@dataclass(slots=True)
class PayloadCapture:
    """Accept only the real exporter's validated in-memory payload."""

    payload: bytes = b""

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        """Retain validated bytes without writing a plaintext export file."""
        self.payload = payload.payload


@pytest.mark.parametrize("revision_id", ("2022", "2023", "2024", "2025"))
def test_neutral_m390_scenario_exports_and_missing_election_still_refuses(revision_id: str) -> None:
    """Each real annual envelope exports, while unresolved election consumes nothing."""
    scenario = edition_export_scenarios("390")[revision_id]
    authority = compiled_bundled_authority()
    with validating_governed_facts(authority):
        provider = schema_provider_from_authority(
            authority, modelos=("390",), filing_year=scenario.period.filing_year, period=scenario.period
        )
        producer = scenario.producer_snapshot()
        assert scenario.inputs == {}
        assert producer.elections.result_disposition is ResultDisposition.NEGATIVA
        assert producer.elections.prior_domiciliation is PriorDomiciliationElection.KEEP
        assert producer.selected_account is None
        assert scenario.product_software_identity_factory is not None
        software = scenario.product_software_identity_factory()
        draft = build_draft(
            modelo="390",
            period=scenario.period,
            profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Ejemplo ficticio"),
            inputs=scenario.inputs,
            schema_provider=provider,
        ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
        assert draft.snapshot_ref.revision_id == revision_id
        sink = PayloadCapture()

        export_draft(
            draft,
            payload_consumer=sink,
            producer_snapshot=producer,
            prior_domiciliation_election=scenario.prior_domiciliation_election,
            product_software_identity=software,
            schema_provider=provider,
        )

        assert sink.payload.startswith(f"<T3900{scenario.period.filing_year:04d}0A0000><AUX>".encode("ascii"))
        assert sink.payload[92:96] == b"C390"
        assert sink.payload[100:109] == b"Y0000001S"
        assert scenario.prior_domiciliation_election is producer.elections.prior_domiciliation
        refused_sink = PayloadCapture()
        with pytest.raises(FilingExportError, match="only with a resolved prior domiciliation election"):
            export_draft(
                draft,
                payload_consumer=refused_sink,
                producer_snapshot=producer,
                product_software_identity=software,
                schema_provider=provider,
            )
        assert refused_sink.payload == b""
