"""Composition gates for connected source-census proof authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core import BindingSourceKind
from cadrumo.core._calculation_route import ModeloCalculationRouteId
from cadrumo.domain.invoices import Invoice, InvoiceLine, IvaRate, PaymentStatus, derive_invoice_id
from cadrumo.domain.iva import InvoiceKind, IvaCategory

from ..live_proof import (
    ConnectedProofCompositionError,
    ConnectedProofFixture,
    _live_authority_for_fixtures,
    _selected_fixtures,
    canonical_live_connected_proof_authority,
    connected_candidate_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BUCKET_ID = "34900000-0000-4000-8000-000000000160"


def _m349_fixture(*, amount: Decimal = Decimal("731.25")) -> ConnectedProofFixture:
    issued_at = date(2026, 2, 12)
    invoice_id = derive_invoice_id(
        kind=InvoiceKind.ISSUED,
        invoice_number="S160-001",
        issued_at=issued_at,
        counterparty_tax_id="DE123456789",
        currency="EUR",
        grand_total=amount,
    )
    invoice = Invoice(
        invoice_id=invoice_id,
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        invoice_number="S160-001",
        issued_at=issued_at,
        counterparty_name="Synthetic EU Operator",
        counterparty_tax_id="DE123456789",
        counterparty_country="DE",
        base_total=amount,
        iva_total=Decimal("0"),
        grand_total=amount,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Synthetic intra-community supply",
                quantity=Decimal("1"),
                unit_price=amount,
                subtotal=amount,
                iva_rate=IvaRate.RATE_0,
                iva_amount=Decimal("0"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
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
        invoice=invoice,
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


def test_m349_fixture_runs_real_ingress_resolver_destination_and_encrypted_revision(tmp_path: Path) -> None:
    fixture = _m349_fixture()
    with _live_authority_for_fixtures(tmp_path, (fixture,)) as authority:
        expectation = authority.independent_expectations[0]
        revision = authority.calculation_revisions.load().revisions[expectation.connection.calculation_revision_id]

        assert revision.casilla_values[fixture.expected_casilla_id] == fixture.expected_casilla_value
        assert any(
            row.resolver_id == fixture.resolver_id
            and row.resolved_binding_source is fixture.source_kind
            and row.source_ref == fixture.source_ref
            for row in revision.source_provenance
        )
