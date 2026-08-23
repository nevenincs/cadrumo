"""Composition gates for connected source-census proof authority."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core import BindingSourceKind, IntracomOperationType
from cadrumo.core._calculation_route import ModeloCalculationRouteId
from cadrumo.domain.invoices import PaymentStatus, derive_invoice_id
from cadrumo.domain.iva import InvoiceKind, IvaCategory

from ..live_proof import (
    ConnectedProofCompositionError,
    ConnectedProofFixture,
    _ephemeral_connected_proof_material,
    _require_unique_primary,
    _selected_fixtures,
    canonical_live_connected_proof_authority,
    connected_candidate_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BUCKET_ID = "34900000-0000-4000-8000-000000000160"


def _m349_fixture(
    *,
    amount: Decimal = Decimal("731.25"),
    counterparty_name: str = "Synthetic EU Operator",
) -> ConnectedProofFixture:
    issued_at = date(2026, 2, 12)
    invoice_id = derive_invoice_id(
        kind=InvoiceKind.ISSUED,
        invoice_number="S160-001",
        issued_at=issued_at,
        counterparty_tax_id="DE123456789",
        currency="EUR",
        grand_total=amount,
    )
    return ConnectedProofFixture(
        candidate_id="proof.m349.collectible-invoice",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        resolver_id="invoice_catalogue",
        source_ref=f"collectible_invoice:{invoice_id}",
        entrypoint_id="cli",
        command_id="modelo.work.calculate",
        route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
        canonical_cli_path=("app", "modelo", "work", "calculate"),
        destination_identities=(("binding_source", "349", "collectible_invoice"),),
        modelo="349",
        revision_id="2020-y-siguientes",
        filing_year=2026,
        period="1T",
        expected_casilla_id="decl.importe-operaciones",
        expected_casilla_value=amount,
        invoice_bucket_id=_BUCKET_ID,
        invoice_kind=InvoiceKind.ISSUED,
        invoice_number="S160-001",
        invoice_issued_at=issued_at,
        invoice_counterparty_name=counterparty_name,
        invoice_counterparty_tax_id="DE123456789",
        invoice_counterparty_country="DE",
        invoice_taxable_base=amount,
        invoice_iva_rate=Decimal("0"),
        invoice_currency="EUR",
        invoice_payment_status=PaymentStatus.PENDING,
        invoice_iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        invoice_operation_type=IntracomOperationType.E,
    )


def test_current_zero_connected_census_requires_no_fixture_or_storage() -> None:
    assert connected_candidate_ids() == ()
    with canonical_live_connected_proof_authority(Path.cwd()) as authority:
        assert authority is None


def test_connected_detection_is_independent_of_typed_census_claim(tmp_path: Path) -> None:
    census = tmp_path / "census.toml"
    census.write_text(
        "schema_version = 1\ncensus_id = 'source-domain-to-casilla-connectivity'\n"
        "[[entries]]\ncandidate_id = 'mutated.claim'\ndisposition = 'connected'\n",
        encoding="utf-8",
    )

    assert connected_candidate_ids(census) == ("mutated.claim",)
    with pytest.raises(ConnectedProofCompositionError, match="lack independent proof fixtures"):
        _selected_fixtures(("mutated.claim",))


def test_m349_fixture_runs_real_ingress_resolver_destination_and_encrypted_revision() -> None:
    fixture = _m349_fixture()
    with _ephemeral_connected_proof_material((fixture,)) as (revisions, expectations, database_path):
        expectation = expectations[0]
        revision = revisions.load().revisions[expectation.connection.calculation_revision_id]

        assert database_path.is_file()
        assert revision.casilla_values[fixture.expected_casilla_id] == fixture.expected_casilla_value
        assert any(
            row.resolver_id == fixture.resolver_id
            and row.resolved_binding_source is fixture.source_kind
            and row.source_ref == fixture.source_ref
            for row in revision.source_provenance
        )
    assert not database_path.exists()


def test_m349_source_mutation_changes_encrypted_revision_and_primary_fingerprint() -> None:
    observed: list[tuple[str, str]] = []
    fixtures = (
        _m349_fixture(counterparty_name="Synthetic EU Operator Alpha"),
        _m349_fixture(counterparty_name="Synthetic EU Operator Beta"),
    )
    assert fixtures[0].source_ref == fixtures[1].source_ref
    for fixture in fixtures:
        with _ephemeral_connected_proof_material((fixture,)) as (revisions, expectations, _database_path):
            expectation = expectations[0]
            revision = revisions.load().revisions[expectation.connection.calculation_revision_id]
            primary = next(row for row in revision.source_provenance if row.source_ref == fixture.source_ref)
            assert primary.fingerprint is not None
            observed.append((revision.calculation_revision_id, primary.fingerprint))

    assert observed[0][0] != observed[1][0]
    assert observed[0][1] != observed[1][1]


def test_m349_fixture_refuses_duplicate_matching_primary_provenance() -> None:
    fixture = _m349_fixture()
    with _ephemeral_connected_proof_material((fixture,)) as (revisions, expectations, _database_path):
        revision = revisions.load().revisions[expectations[0].connection.calculation_revision_id]
        primary = next(row for row in revision.source_provenance if row.source_ref == fixture.source_ref)
        ambiguous = revision.model_copy(update={"source_provenance": (primary, primary)})

        with pytest.raises(ConnectedProofCompositionError, match="no unique expected primary provenance"):
            _require_unique_primary(ambiguous, fixture)


def test_m349_fixture_refuses_a_missing_primary_source_identity() -> None:
    fixture = replace(_m349_fixture(), source_ref="collectible_invoice:absent")

    with (
        pytest.raises(ConnectedProofCompositionError, match="no unique expected primary provenance"),
        _ephemeral_connected_proof_material((fixture,)),
    ):
        pass
