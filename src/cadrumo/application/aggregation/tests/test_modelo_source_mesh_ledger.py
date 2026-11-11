"""Source mesh parity tests for existing ledger-backed modelo bindings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    newest_authored_edition,
    revision_serving_period,
)
from ....domain.invoices.models import Invoice
from ....domain.iva.classification import TransactionKind
from ....domain.iva.oss import OssIossRegime
from ....domain.iva.schema import EUMemberState, IvaCategory, IvaRateKind
from ....domain.iva.schema import InvoiceKind as InvoiceKind
from ....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from ....domain.transactions.classification_effects import fields_refused_by_classification
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..iva_ledger import (
    IvaLedgerAggregationIssueReason,
)
from ..oss_ioss import OssIossLedgerCandidate, aggregate_oss_ioss_bindings
from ..oss_ioss_resolver import OssIossLedgerSourceResolver
from ..source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceResolution,
)
from .iva_authority_support import aggregate_iva_ledger_observations
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryInvoiceCatalogueRepository,
    InMemoryProrrataRegisterRepository,
    InMemoryTransactionCatalogueRepository,
    domestic_iva_invoice,
    empty_catalogue_read_ports,
    empty_invoice_repository,
    empty_prorrata_repository,
    exempt_intracommunity_invoice,
    ledger_iva_resolver,
    ledger_source_mesh_revision,
    m303_revision,
    prior_m303_snapshot_ref,
)
from .ledger_transaction_support import (
    iva_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_HORIZON = filing_year_envelope().horizon
_YEAR = newest_authored_edition("100")
_M303_HORIZON_REVISION = str(revision_serving_period("303", _HORIZON, "1T").id)


def _apart_from_the_bank_date_advisory(
    resolution: CalculationSourceResolution,
) -> list[CalculationSourceDiagnostic]:
    """These rows state no operation date, so the fallback advisory is true of each of them."""
    return [item for item in resolution.diagnostics if item.reason != "iva_row_placed_on_movement_date"]


def test_iva_source_mesh_resolver_resolves_general_sale_and_purchase() -> None:
    revision = ledger_source_mesh_revision("303", _M303_HORIZON_REVISION)
    tx_repo = InMemoryTransactionCatalogueRepository(
        bucket_id=BUCKET_ID,
    )
    incoming = iva_transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    outgoing = iva_transaction(
        "purchase-general",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("60.50"),
        taxable_base=Decimal("50.00"),
        iva_amount=Decimal("10.50"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((incoming, outgoing)))

    resolution = ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=_HORIZON,
            period=Period.from_year_and_code(_HORIZON, "1T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values  # non-empty: at least one IVA binding resolved
    assert set(resolution.source_transaction_ids) == {
        incoming.transaction_id,
        outgoing.transaction_id,
    }
    assert _apart_from_the_bank_date_advisory(resolution) == []
    assert {item.source_ref for item in resolution.provenance} == {
        f"transaction:{incoming.transaction_id}",
        f"transaction:{outgoing.transaction_id}",
    }


def test_iva_source_mesh_resolver_carries_prorrata_apportionment_provenance() -> None:
    revision = ledger_source_mesh_revision("303", _M303_HORIZON_REVISION)
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    prorrata_repo = InMemoryProrrataRegisterRepository(bucket_id=BUCKET_ID)
    outgoing = iva_transaction(
        "purchase-prorrata-general",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("60.50"),
        taxable_base=Decimal("50.00"),
        iva_amount=Decimal("10.50"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((outgoing,)))
    prorrata_repo.save(
        ProrrataRegister(
            entries=(
                ProrrataRegisterEntry(
                    ejercicio=_HORIZON,
                    regime=ProrrataRegisterRegime.from_registry("general"),
                    especial_transition=None,
                    provisional_percentage=Decimal("80"),
                    provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
                    source_observation_ref=f"303:{_HORIZON - 1}:4T",
                    source_registry_snapshot_refs=(prior_m303_snapshot_ref(),),
                ),
            ),
        ),
    )

    resolution = ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=prorrata_repo,
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=_HORIZON,
            period=Period.from_year_and_code(_HORIZON, "1T"),
            revision=revision,
        ),
    )

    prorrata_provenance = [
        item for item in resolution.provenance if item.source_ref.startswith("prorrata-apportionment:")
    ]
    assert len(prorrata_provenance) == 1
    provenance = prorrata_provenance[0]
    assert provenance.resolved_binding_source is BindingSourceKind.LEDGER_IVA_AGGREGATION
    assert provenance.source_ref == (
        f"prorrata-apportionment:{_HORIZON}:general:"
        f"percentage:80:provenance:carried_prior_definitiva:source-observation:303:{_HORIZON - 1}:4T"
    )
    assert provenance.source_casilla_ids == ()
    assert provenance.legal_refs
    assert provenance.source_refs


def _resolve_invoices_alone(*invoices: Invoice, code: str = "1T") -> CalculationSourceResolution:
    """Resolve ``code`` of the newest Renta exercise over these invoices with no transaction ledger at all."""
    invoice_repo = InMemoryInvoiceCatalogueRepository()
    invoice_repo.save(build_invoice_catalogue(invoices))
    return ledger_iva_resolver(
        transaction_repository=InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID),
        invoice_repository=invoice_repo,
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, code),
            revision=m303_revision(),
        ),
    )


def test_iva_source_mesh_declares_an_issued_invoice_without_a_ledger_movement() -> None:
    """The invoice is the IVA source (LIVA art. 75, art. 164): no movement is needed to declare it.

    An unpaid sale devengues on its operation and is repercutida all the same;
    the bank movement is payment evidence, not the source of the cuota.
    """
    invoice = domestic_iva_invoice(
        "LAURA-1T-SALE",
        kind=InvoiceKind.ISSUED,
        issued_at=date(_YEAR, 2, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
    )

    resolution = _resolve_invoices_alone(invoice)

    assert resolution.binding_values["modelo-303-iva-repercutido-general-base"] == Decimal("10000.00")
    assert resolution.binding_values["modelo-303-iva-repercutido-general-cuota"] == Decimal("2100.00")
    assert resolution.source_transaction_ids == ()
    assert [item.source_ref for item in resolution.provenance] == [f"invoice:{invoice.invoice_id}"]


def _received(number: str, base: str, cuota: str) -> Invoice:
    return domestic_iva_invoice(
        number,
        kind=InvoiceKind.RECEIVED,
        issued_at=date(_YEAR, 2, 10),
        taxable_base=Decimal(base),
        iva_amount=Decimal(cuota),
    )


def test_iva_source_mesh_deducts_a_received_invoice_below_the_investment_threshold() -> None:
    """Below the art. 108 threshold a domestic purchase is current soportado on its own invoice.

    3005.05 is one cent under the 3005.06 fact; an acquisition that small
    cannot be a bien de inversion, so the invoice grounds its own deduction
    family and needs no linked movement.
    """
    invoice = _received("PURCHASE-BELOW-THRESHOLD", "3005.05", "631.06")

    resolution = _resolve_invoices_alone(invoice)

    assert resolution.binding_values["modelo-303-iva-soportado-interiores-base"] == Decimal("3005.05")
    assert resolution.binding_values["modelo-303-iva-soportado-interiores-cuota"] == Decimal("631.06")
    assert all(diagnostic.reason != "iva_selected_scope_evidence_failure" for diagnostic in resolution.diagnostics)


def test_iva_source_mesh_withholds_a_received_invoice_at_the_threshold_without_deduction_authority() -> None:
    """At the threshold the invoice cannot tell current soportado from a bien de inversion.

    The threshold applies strictly below ("sea inferior a"), so 3005.06 itself
    needs a classified authority. Without one the cuota reaches no SOPORTADO
    row, and the withholding is named rather than silent.
    """
    invoice = _received("PURCHASE-AT-THRESHOLD", "3005.06", "631.06")

    resolution = _resolve_invoices_alone(invoice)

    assert not any(resolution.binding_values.values())
    (finding,) = [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "iva_selected_scope_evidence_failure"
    ]
    assert finding.source_ref == f"invoice:{invoice.invoice_id}"
    assert "invoice_deduction_family_unresolved" in finding.message


def test_iva_source_mesh_resolver_attributes_a_q1_operation_invoiced_in_q2_to_q1() -> None:
    """Period attribution follows the art. 75 devengo date, not the issue date.

    RD 1619/2012 art. 11 lets this B2B invoice be issued on 10 April for an
    operation performed on 28 March, so the record is lawful. Its cuota is
    devengada in Q1: it must be declared while calculating Q1 and must NOT be
    declared while calculating Q2. Both quarters are asserted, because a change
    that moved every invoice one quarter earlier would satisfy the Q1 half alone.
    """
    invoice = domestic_iva_invoice(
        "LAURA-Q1-OPERATION-INVOICED-IN-Q2",
        kind=InvoiceKind.ISSUED,
        issued_at=date(_YEAR, 4, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        operation_date=date(_YEAR, 3, 28),
    )

    q1_resolution = _resolve_invoices_alone(invoice, code="1T")
    assert q1_resolution.binding_values["modelo-303-iva-repercutido-general-cuota"] == Decimal("2100.00")
    assert [item.source_ref for item in q1_resolution.provenance] == [f"invoice:{invoice.invoice_id}"]

    # Q2 holds the issue date and nothing else: the operation devengued in Q1.
    q2_resolution = _resolve_invoices_alone(invoice, code="2T")
    assert not any(q2_resolution.binding_values.values())
    assert q2_resolution.provenance == ()


def _resolve_laura_first_quarter_sale(
    *, operation_date: date | None = None
) -> tuple[Transaction, CalculationSourceResolution]:
    """Resolve the one issued sale, optionally declaring its operation date."""
    revision = m303_revision()
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    invoice_repo = InMemoryInvoiceCatalogueRepository()
    transaction = iva_transaction(
        "laura-1t-sale",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("12100.00"),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        booked_date=date(_YEAR, 2, 10),
    )
    invoice = domestic_iva_invoice(
        "LAURA-1T-SALE",
        kind=InvoiceKind.ISSUED,
        issued_at=date(_YEAR, 2, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        linked_transaction_ids=(transaction.transaction_id,),
        operation_date=operation_date,
    )
    tx_repo.save(TransactionCatalogue.from_transactions((transaction,)))
    invoice_repo.save(build_invoice_catalogue((invoice,)))

    return transaction, ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, "1T"),
            revision=revision,
        ),
    )


def test_iva_source_mesh_resolver_declares_the_invoice_when_its_payment_movement_is_linked() -> None:
    """The linked movement is payment evidence; the declared figure and its citation are the invoice's."""
    _transaction, resolution = _resolve_laura_first_quarter_sale()

    assert resolution.binding_values["modelo-303-iva-repercutido-general-cuota"] == Decimal("2100.00")
    (provenance,) = resolution.provenance
    assert provenance.source_ref.startswith("invoice:")
    assert resolution.source_transaction_ids == ()
    # The invoice records no fecha de operacion, so its Q1 placement rests on
    # the issue date. LIVA art. 75.Uno binds devengo to the operation date, so
    # the substitution is disclosed rather than passed off as a determination.
    (devengo,) = _apart_from_the_bank_date_advisory(resolution)
    assert devengo.reason == "devengo_date_proxy_attribution"
    assert "LAURA-1T-SALE" in devengo.message


def test_iva_source_mesh_resolver_raises_no_devengo_advisory_when_the_operation_date_is_recorded() -> None:
    """The other direction of the proxy advisory, on the real resolve path.

    Same fixture as the accept case above with one field added. An advisory
    that fires on every invoice would be indistinguishable from one that fires
    correctly, so the declared-date case is asserted silent as explicitly as
    the proxy case is asserted noisy.
    """
    _, resolution = _resolve_laura_first_quarter_sale(operation_date=date(_YEAR, 2, 5))

    assert resolution.binding_values["modelo-303-iva-repercutido-general-cuota"] == Decimal("2100.00")
    assert _apart_from_the_bank_date_advisory(resolution) == []


def test_iva_source_mesh_resolver_routes_domestic_reverse_charge_to_box_13_and_37_net_zero() -> None:
    """A ``DOMESTIC_REVERSE_CHARGE`` operation is now CONSUMED, not surfaced as a gap.

    Inversión del sujeto pasivo interior (Ley 37/1992 art. 84.Uno.2): the
    recipient self-assesses both an IVA devengado entry (official casilla 13,
    ``modelo-303-iva-autorepercutido-interior-devengado-cuota``) AND a matching
    IVA deducible entry (official casilla 37,
    ``modelo-303-iva-autorepercutido-interior-deducible-cuota``). Before the
    flow-fix the application classifier left the observation on its
    direction-only ``SOPORTADO`` flow, no binding selected it, and the
    unconsumed-declarable-IVA advisory surfaced it as an unrouted cuota-bearing
    gap. Now the classifier
    recomputes the flow via :func:`derive_flow_for_classification`, routing the
    reverse-charge category to ``INVERSION_SUJETO_PASIVO``; the two new bindings
    consume it (each resolves the 42.00 self-assessed cuota), so the pair nets
    to zero in the M303 resultado and the advisory no longer fires.
    """
    revision = ledger_source_mesh_revision("303", _M303_HORIZON_REVISION)
    tx_repo = InMemoryTransactionCatalogueRepository(
        bucket_id=BUCKET_ID,
    )
    # A consumed domestic sale (matches the repercutido-general binding) ...
    domestic_sale = iva_transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    # ... plus a reverse-charge operation now routed to box 13 + 37.
    # Self-assessed IVA: the bank gross equals the base (no IVA charged on the
    # invoice); the cuota is self-assessed.
    #
    # OUTGOING, because boxes 13 and 37 belong to the RECIPIENT of an art.
    # 84.Uno.2 operation and this fixture is written for the recipient. It was
    # INCOMING -- a sale the taxpayer ISSUED -- which is the supplier's side and
    # contradicts the docstring above. The fixture passed anyway only because the
    # flow derivation discarded invoice direction for reverse-charge categories,
    # so both sides collapsed onto the recipient's treatment. Once direction is
    # honoured the two stop being interchangeable and the fixture has to name
    # which side it means.
    reverse_charge = iva_transaction(
        "domestic-reverse-charge",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("200.00"),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        iva_category=IvaCategory("domestic_reverse_charge"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((domestic_sale, reverse_charge)))

    resolution = ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=_HORIZON,
            period=Period.from_year_and_code(_HORIZON, "1T"),
            revision=revision,
        ),
    )

    # The reverse-charge observation is now CONSUMED: the unconsumed-declarable-IVA
    # advisory no longer flags it once the binding routes its self-assessed cuota.
    unconsumed_diagnostics = [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.source_kind == "ledger_iva_aggregation" and reverse_charge.transaction_id in diagnostic.message
    ]
    assert unconsumed_diagnostics == []
    # Both the devengado (box 13) and deducible (box 37) bindings carry the
    # self-assessed 42.00 cuota, so the pair nets to zero in the resultado.
    devengado = resolution.binding_values["modelo-303-iva-autorepercutido-interior-devengado-cuota"]
    deducible = resolution.binding_values["modelo-303-iva-autorepercutido-interior-deducible-cuota"]
    assert devengado == Decimal("42.00")
    assert deducible == Decimal("42.00")
    assert devengado - deducible == Decimal("0")
    # The reverse-charge transaction is recorded in the resolved provenance set,
    # not discarded as an unsupported observation.
    assert reverse_charge.transaction_id in resolution.source_transaction_ids


def test_iva_source_mesh_resolver_does_not_flag_cuota_less_by_law_observation() -> None:
    """A cuota-less-by-law observation must NOT fire the advisory.

    An ``INTRA_COMMUNITY_SUPPLY`` repercutido operation is an entrega
    intracomunitaria exenta (Ley 37/1992 art. 25): it bears zero M303 cuota and
    correctly matches no ``ledger_iva_aggregation`` cuota binding. Before the
    refinement the advisory false-fired on it (any unconsumed declarable
    observation was flagged); after, it must be silent because the category is
    cuota-less by law. This guards against the false-positive that surfaced an
    unactionable "modelling gap" for a category that simply has no cuota.
    """
    revision = ledger_source_mesh_revision("303", _M303_HORIZON_REVISION)
    tx_repo = InMemoryTransactionCatalogueRepository(
        bucket_id=BUCKET_ID,
    )
    domestic_sale = iva_transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    exempt_supply = iva_transaction(
        "intra-community-supply",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("242.00"),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        iva_category=IvaCategory("intra_community_supply"),
        counterparty_country="DE",
    )
    tx_repo.save(TransactionCatalogue.from_transactions((domestic_sale, exempt_supply)))

    resolution = ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=_HORIZON,
            period=Period.from_year_and_code(_HORIZON, "1T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values
    cuota_less_diagnostics = [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.source_kind == "ledger_iva_aggregation" and exempt_supply.transaction_id in diagnostic.message
    ]
    assert cuota_less_diagnostics == []


def test_iva_source_mesh_resolver_surfaces_no_unconsumed_diagnostic_when_all_consumed() -> None:
    """The converse case: an all-consumed IVA observation set surfaces ZERO unconsumed diagnostics.

    This is the anti-tautology guard for the advisory above: only observations no
    binding selects produce the diagnostic. A domestic sale matched by the
    repercutido-general binding must leave ``diagnostics`` empty.
    """
    revision = ledger_source_mesh_revision("303", _M303_HORIZON_REVISION)
    tx_repo = InMemoryTransactionCatalogueRepository(
        bucket_id=BUCKET_ID,
    )
    domestic_sale = iva_transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((domestic_sale,)))

    resolution = ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=_HORIZON,
            period=Period.from_year_and_code(_HORIZON, "1T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values
    assert _apart_from_the_bank_date_advisory(resolution) == []


def test_iva_source_mesh_resolver_summarizes_out_of_period_personal_source_diagnostic() -> None:
    revision = ledger_source_mesh_revision("303", _M303_HORIZON_REVISION)
    tx_repo = InMemoryTransactionCatalogueRepository(
        bucket_id=BUCKET_ID,
    )
    personal_q2 = iva_transaction(
        "personal-q2",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        booked_date=date(_HORIZON, 4, 10),
    ).model_copy(
        update={
            "business_classification": BusinessClassification.PERSONAL,
            **dict.fromkeys(fields_refused_by_classification(BusinessClassification.PERSONAL)),
        }
    )
    catalogue = TransactionCatalogue.from_transactions((personal_q2,))
    tx_repo.save(catalogue)

    raw_aggregation = aggregate_iva_ledger_observations(catalogue, period=Period.from_year_and_code(_HORIZON, "1T"))
    assert [issue.reason for issue in raw_aggregation.issues] == [IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD]

    resolution = ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=_HORIZON,
            period=Period.from_year_and_code(_HORIZON, "1T"),
            revision=revision,
        ),
    )

    assert len(resolution.diagnostics) == 1
    diagnostic = resolution.diagnostics[0]
    assert diagnostic.reason == "source_issue"
    assert diagnostic.source_kind == "ledger_iva_aggregation"
    assert diagnostic.resolver_id == "ledger_iva_aggregation"
    assert diagnostic.out_of_window_count == 1
    assert diagnostic.out_of_window_min_filing_date == date(_HORIZON, 4, 10)
    assert diagnostic.out_of_window_max_filing_date == date(_HORIZON, 4, 10)
    assert "outside the requested period" in diagnostic.message
    assert personal_q2.transaction_id not in resolution.source_transaction_ids


def test_iva_source_mesh_resolver_keeps_in_period_missing_fact_diagnostic() -> None:
    revision = ledger_source_mesh_revision("303", _M303_HORIZON_REVISION)
    tx_repo = InMemoryTransactionCatalogueRepository(
        bucket_id=BUCKET_ID,
    )
    missing_rate = iva_transaction(
        "business-missing-rate",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    ).model_copy(update={"iva_rate": None})
    catalogue = TransactionCatalogue.from_transactions((missing_rate,))
    tx_repo.save(catalogue)

    raw_aggregation = aggregate_iva_ledger_observations(catalogue, period=Period.from_year_and_code(_HORIZON, "1T"))
    assert [issue.reason for issue in raw_aggregation.issues] == [IvaLedgerAggregationIssueReason.MISSING_IVA_RATE]

    resolution = ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=_HORIZON,
            period=Period.from_year_and_code(_HORIZON, "1T"),
            revision=revision,
        ),
    )

    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == ["iva_selected_scope_evidence_failure"]
    assert resolution.diagnostics[0].source_ref == f"transaction:{missing_rate.transaction_id}"
    assert resolution.diagnostics[0].message == "selected-scope IVA evidence failure: missing_iva_rate"


def test_oss_source_mesh_resolver_matches_candidate_binding_aggregation() -> None:
    revision = ledger_source_mesh_revision("369", "esquema-union")
    candidates = (
        OssIossLedgerCandidate(
            ledger_id="oss-ledger-1",
            transaction_date=date(_YEAR, 7, 15),
            regime=OssIossRegime("union_scheme"),
            destination_member_state=EUMemberState.from_registry("de"),
            rate_kind=IvaRateKind("general"),
            invoice_direction=InvoiceKind.ISSUED,
            transaction_kind=TransactionKind("oss_union_services"),
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("19.00"),
        ),
    )

    aggregated = aggregate_oss_ioss_bindings(revision, candidates)
    resolution = OssIossLedgerSourceResolver(
        ports=empty_catalogue_read_ports(),
        candidates=candidates,
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="369",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, "4T"),
            revision=revision,
        ),
    )

    assert {binding_id: resolution.binding_values[binding_id] for binding_id in aggregated} == aggregated
    assert resolution.source_transaction_ids == ("oss-ledger-1",)
    assert resolution.diagnostics == ()
    assert tuple(item.source_ref for item in resolution.provenance) == ("transaction:oss-ledger-1",)


def test_oss_source_mesh_resolver_surfaces_advisory_for_unrouted_observation() -> None:
    """A non-zero OSS line with no table on the revision surfaces an advisory.

    A goods line needs its state of dispatch to choose between the return's goods
    tables, and an invoice does not record one. Its base and cuota would otherwise
    silently vanish from the M369, so the resolver MUST emit an
    ``unrouted_observation`` advisory rather than drop it (no-silent-under-declaration).
    """
    revision = ledger_source_mesh_revision("369", "esquema-union")
    candidates = (
        OssIossLedgerCandidate(
            ledger_id="oss-it-unrouted",
            transaction_date=date(_YEAR, 7, 15),
            regime=OssIossRegime("union_scheme"),
            destination_member_state=EUMemberState.from_registry("it"),
            rate_kind=IvaRateKind("general"),
            invoice_direction=InvoiceKind.ISSUED,
            transaction_kind=TransactionKind("oss_union_goods_distance_sale"),
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("22.00"),
        ),
    )

    resolution = OssIossLedgerSourceResolver(
        ports=empty_catalogue_read_ports(),
        candidates=candidates,
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="369",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, "4T"),
            revision=revision,
        ),
    )

    unrouted = [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "unrouted_observation"
        and diagnostic.source_kind == "ledger_oss_aggregation"
        and "oss-it-unrouted" in diagnostic.message
    ]
    assert len(unrouted) == 1, "an IT-destination goods line with no table must surface one advisory"
    # The advisory is non-blocking: the resolution still resolves the (zero) DE
    # binding value and records the candidate so calculate succeeds.
    assert resolution.binding_values.get("modelo-369-union-de-services-21pct") == Decimal("0")


def test_a_non_es_invoice_carrying_spanish_cuota_is_declared() -> None:
    """A foreign counterparty does not mean the operation carried no Spanish IVA.

    An invoice to a foreign customer can carry ordinary domestic cuota -- goods
    that never leave the pais, a service localised here, a non-established
    consumer. The counterparty's country is not a proxy for "carries Spanish
    IVA": the invoice's own cuota lines are declared like the domestic case.
    """
    invoice = domestic_iva_invoice(
        "DE-1T-SALE",
        kind=InvoiceKind.ISSUED,
        issued_at=date(_YEAR, 2, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        counterparty_country="DE",
        counterparty_tax_id="DE345678901",
    )

    resolution = _resolve_invoices_alone(invoice)

    assert resolution.binding_values["modelo-303-iva-repercutido-general-base"] == Decimal("10000.00")
    assert resolution.binding_values["modelo-303-iva-repercutido-general-cuota"] == Decimal("2100.00")


def test_an_exempt_intracommunity_invoice_does_not_trip_the_widened_screen() -> None:
    """Positive control: a non-ES invoice without cuota is not refused.

    An entrega intracomunitaria exenta is the commonest non-ES invoice there
    is, and it carries no cuota at all. Declaring a foreign customer's Spanish
    cuota must not start refusing those, or it would block correct filings far
    more often than it catches wrong ones.
    """
    revision = m303_revision()
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    invoice_repo = InMemoryInvoiceCatalogueRepository()
    exempt = exempt_intracommunity_invoice(
        "DE-1T-EXEMPT",
        kind=InvoiceKind.ISSUED,
        issued_at=date(_YEAR, 2, 10),
        taxable_base=Decimal("10000.00"),
    )
    invoice_repo.save(build_invoice_catalogue((exempt,)))

    resolution = ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, "1T"),
            revision=revision,
        ),
    )

    assert resolution.resolver_id == "ledger_iva_aggregation"
