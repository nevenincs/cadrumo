"""Source mesh parity tests for existing ledger-backed modelo bindings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.aggregation import BindingSourceKind
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....domain.iva.classification import TransactionKind
from ....domain.iva.oss import OssIossRegime
from ....domain.iva.schema import EUMemberState, IvaCategory, IvaRateKind
from ....domain.iva.schema import InvoiceKind as CatalogueInvoiceKind
from ....domain.iva.schema import InvoiceKind as IvaInvoiceKind
from ....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import TransactionCatalogue
from .._preconditions import AggregationPreconditionCondition
from ..errors import (
    AggregationValidationError,
)
from ..iva_ledger import (
    IvaLedgerAggregationIssueReason,
)
from ..oss_ioss import OssIossLedgerCandidate, OssIossLedgerSourceResolver, aggregate_oss_ioss_bindings
from ..source_mesh import (
    CalculationSourceContext,
    CalculationSourceResolution,
)
from .iva_authority_support import aggregate_iva_ledger_observations
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryTransactionCatalogueRepository,
    _domestic_iva_invoice,
    _empty_catalogue_read_ports,
    _exempt_intracommunity_invoice,
    _InMemoryInvoiceCatalogueRepository,
    _InMemoryProrrataRegisterRepository,
    _ledger_iva_resolver,
    _m303_revision,
    _prior_m303_snapshot_ref,
    _revision,
    empty_invoice_repository,
    empty_prorrata_repository,
)
from .ledger_transaction_support import (
    iva_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_iva_source_mesh_resolver_resolves_general_sale_and_purchase() -> None:
    revision = _revision("303", "2022")
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

    resolution = _ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values  # non-empty: at least one IVA binding resolved
    assert set(resolution.source_transaction_ids) == {
        incoming.transaction_id,
        outgoing.transaction_id,
    }
    assert resolution.diagnostics == ()
    assert {item.source_ref for item in resolution.provenance} == {
        f"transaction:{incoming.transaction_id}",
        f"transaction:{outgoing.transaction_id}",
    }


def test_iva_source_mesh_resolver_carries_prorrata_apportionment_provenance() -> None:
    revision = _revision("303", "2022")
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    prorrata_repo = _InMemoryProrrataRegisterRepository(bucket_id=BUCKET_ID)
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
                    ejercicio=2026,
                    regime=ProrrataRegisterRegime.from_registry("general"),
                    especial_transition=None,
                    provisional_percentage=Decimal("80"),
                    provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
                    source_observation_ref="303:2025:4T",
                    source_registry_snapshot_refs=(_prior_m303_snapshot_ref(),),
                ),
            ),
        ),
    )

    resolution = _ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=prorrata_repo,
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
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
        "prorrata-apportionment:2026:general:"
        "percentage:80:provenance:carried_prior_definitiva:source-observation:303:2025:4T"
    )
    assert provenance.source_casilla_ids == ()
    assert provenance.legal_refs
    assert provenance.source_refs


def test_iva_source_mesh_resolver_refuses_m303_invoice_domestic_iva_without_transaction_ledger() -> None:
    revision = _m303_revision()
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    invoice_repo = _InMemoryInvoiceCatalogueRepository()
    invoice = _domestic_iva_invoice(
        "LAURA-1T-SALE",
        kind=CatalogueInvoiceKind.ISSUED,
        issued_at=date(2025, 2, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
    )
    invoice_repo.save(build_invoice_catalogue((invoice,)))

    with pytest.raises(AggregationValidationError) as exc_info:
        _ledger_iva_resolver(
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            prorrata_register_repository=empty_prorrata_repository(),
        ).resolve(
            CalculationSourceContext(
                bucket_id=BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                revision=revision,
            ),
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["reason"] == "invoice_domestic_iva_not_in_transaction_ledger"
    assert exc_info.value.context["period"] == "1T"
    verdict = exc_info.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == AggregationPreconditionCondition.INVOICE_LEDGER_COMPLETE.value
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values["invoice_count"] == 1


def test_iva_source_mesh_withholds_received_invoice_without_deduction_authority() -> None:
    """A received invoice reaches no SOPORTADO row until classified authority exists."""
    revision = _m303_revision()
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    invoice_repo = _InMemoryInvoiceCatalogueRepository()
    invoice = _domestic_iva_invoice(
        "PURCHASE-WITHOUT-DEDUCTION-AUTHORITY",
        kind=CatalogueInvoiceKind.RECEIVED,
        issued_at=date(2025, 2, 10),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    invoice_repo.save(build_invoice_catalogue((invoice,)))

    with pytest.raises(AggregationValidationError) as refusal:
        _ledger_iva_resolver(
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            prorrata_register_repository=empty_prorrata_repository(),
        ).resolve(
            CalculationSourceContext(
                bucket_id=BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                revision=revision,
            ),
        )

    # The ledger carries none of the invoice's cuota, so withholding it silently
    # would under-declare; the filing is refused and names the invoice.
    assert refusal.value.context is not None
    assert refusal.value.context["reason"] == "invoice_deduction_authority_missing_from_transaction_ledger"
    assert refusal.value.context["invoice_ids"] == (invoice.invoice_id,)
    assert refusal.value.context["invoice_cuota_exceeding_ledger"] == "21.00"


def test_iva_source_mesh_resolver_attributes_a_q1_operation_invoiced_in_q2_to_q1() -> None:
    """Period attribution follows the art. 75 devengo date, not the issue date.

    RD 1619/2012 art. 11 lets this B2B invoice be issued on 10 April for an
    operation performed on 28 March, so the record is lawful. Its cuota is
    devengada in Q1: the domestic-IVA screen must see it while calculating Q1
    and must NOT see it while calculating Q2. Both quarters are asserted,
    because a change that moved every invoice one quarter earlier would satisfy
    the Q1 half alone.
    """
    revision = _m303_revision()
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    invoice_repo = _InMemoryInvoiceCatalogueRepository()
    invoice = _domestic_iva_invoice(
        "LAURA-Q1-OPERATION-INVOICED-IN-Q2",
        kind=CatalogueInvoiceKind.ISSUED,
        issued_at=date(2025, 4, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        operation_date=date(2025, 3, 28),
    )
    invoice_repo.save(build_invoice_catalogue((invoice,)))

    def _resolve(code: str) -> CalculationSourceResolution:
        return _ledger_iva_resolver(
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            prorrata_register_repository=empty_prorrata_repository(),
        ).resolve(
            CalculationSourceContext(
                bucket_id=BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=Period.from_year_and_code(2025, code),
                revision=revision,
            ),
        )

    with pytest.raises(AggregationValidationError) as exc_info:
        _resolve("1T")
    assert exc_info.value.context is not None
    assert exc_info.value.context["period"] == "1T"
    assert exc_info.value.context["invoice_ids"] == (invoice.invoice_id,)

    # Q2 holds the issue date and nothing else: the invoice already devengo'd.
    q2_resolution = _resolve("2T")
    assert q2_resolution.diagnostics == ()
    assert exc_info.value.context["invoice_count"] == "1"
    assert exc_info.value.context["invoice_domestic_iva_excess_by_binding"] == {
        "modelo-303-iva-repercutido-general-cuota": "2100.00",
    }


def test_iva_source_mesh_resolver_accepts_m303_invoice_domestic_iva_when_transaction_ledger_matches() -> None:
    revision = _m303_revision()
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    invoice_repo = _InMemoryInvoiceCatalogueRepository()
    transaction = iva_transaction(
        "laura-1t-sale",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("12100.00"),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        booked_date=date(2025, 2, 10),
    )
    invoice = _domestic_iva_invoice(
        "LAURA-1T-SALE",
        kind=CatalogueInvoiceKind.ISSUED,
        issued_at=date(2025, 2, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        linked_transaction_ids=(transaction.transaction_id,),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((transaction,)))
    invoice_repo.save(build_invoice_catalogue((invoice,)))

    resolution = _ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values["modelo-303-iva-repercutido-general-cuota"] == Decimal("2100.00")
    assert resolution.source_transaction_ids == (transaction.transaction_id,)
    # The invoice records no fecha de operacion, so its Q1 placement rests on
    # the issue date. LIVA art. 75.Uno binds devengo to the operation date, so
    # the substitution is disclosed rather than passed off as a determination.
    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == ["devengo_date_proxy_attribution"]
    assert "LAURA-1T-SALE" in resolution.diagnostics[0].message


def test_iva_source_mesh_resolver_raises_no_devengo_advisory_when_the_operation_date_is_recorded() -> None:
    """The other direction of the proxy advisory, on the real resolve path.

    Same fixture as the accept case above with one field added. An advisory
    that fires on every invoice would be indistinguishable from one that fires
    correctly, so the declared-date case is asserted silent as explicitly as
    the proxy case is asserted noisy.
    """
    revision = _m303_revision()
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    invoice_repo = _InMemoryInvoiceCatalogueRepository()
    transaction = iva_transaction(
        "laura-1t-sale",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("12100.00"),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        booked_date=date(2025, 2, 10),
    )
    invoice = _domestic_iva_invoice(
        "LAURA-1T-SALE",
        kind=CatalogueInvoiceKind.ISSUED,
        issued_at=date(2025, 2, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        linked_transaction_ids=(transaction.transaction_id,),
        operation_date=date(2025, 2, 5),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((transaction,)))
    invoice_repo.save(build_invoice_catalogue((invoice,)))

    resolution = _ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values["modelo-303-iva-repercutido-general-cuota"] == Decimal("2100.00")
    assert resolution.diagnostics == ()


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
    revision = _revision("303", "2022")
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

    resolution = _ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
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
    revision = _revision("303", "2022")
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

    resolution = _ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
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
    revision = _revision("303", "2022")
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

    resolution = _ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values
    assert resolution.diagnostics == ()


def test_iva_source_mesh_resolver_summarizes_out_of_period_personal_source_diagnostic() -> None:
    revision = _revision("303", "2022")
    tx_repo = InMemoryTransactionCatalogueRepository(
        bucket_id=BUCKET_ID,
    )
    personal_q2 = iva_transaction(
        "personal-q2",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        booked_date=date(2026, 4, 10),
    ).model_copy(update={"business_classification": BusinessClassification.PERSONAL})
    catalogue = TransactionCatalogue.from_transactions((personal_q2,))
    tx_repo.save(catalogue)

    raw_aggregation = aggregate_iva_ledger_observations(catalogue, period=Period.from_year_and_code(2026, "1T"))
    assert [issue.reason for issue in raw_aggregation.issues] == [IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD]

    resolution = _ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=revision,
        ),
    )

    assert len(resolution.diagnostics) == 1
    diagnostic = resolution.diagnostics[0]
    assert diagnostic.reason == "source_issue"
    assert diagnostic.source_kind == "ledger_iva_aggregation"
    assert diagnostic.resolver_id == "ledger_iva_aggregation"
    assert diagnostic.out_of_window_count == 1
    assert diagnostic.out_of_window_min_filing_date == date(2026, 4, 10)
    assert diagnostic.out_of_window_max_filing_date == date(2026, 4, 10)
    assert "outside the requested period" in diagnostic.message
    assert personal_q2.transaction_id not in resolution.source_transaction_ids


def test_iva_source_mesh_resolver_keeps_in_period_missing_fact_diagnostic() -> None:
    revision = _revision("303", "2022")
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

    raw_aggregation = aggregate_iva_ledger_observations(catalogue, period=Period.from_year_and_code(2026, "1T"))
    assert [issue.reason for issue in raw_aggregation.issues] == [IvaLedgerAggregationIssueReason.MISSING_IVA_RATE]

    resolution = _ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=revision,
        ),
    )

    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == ["iva_selected_scope_evidence_failure"]
    assert resolution.diagnostics[0].source_ref == f"transaction:{missing_rate.transaction_id}"
    assert resolution.diagnostics[0].message == "selected-scope IVA evidence failure: missing_iva_rate"


def test_oss_source_mesh_resolver_matches_candidate_binding_aggregation() -> None:
    revision = _revision("369", "esquema-union")
    candidates = (
        OssIossLedgerCandidate(
            ledger_id="oss-ledger-1",
            transaction_date=date(2025, 7, 15),
            regime=OssIossRegime("union_scheme"),
            destination_member_state=EUMemberState.from_registry("de"),
            rate_kind=IvaRateKind("general"),
            invoice_direction=IvaInvoiceKind.ISSUED,
            transaction_kind=TransactionKind("oss_union_services"),
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("19.00"),
        ),
    )

    aggregated = aggregate_oss_ioss_bindings(revision, candidates)
    resolution = OssIossLedgerSourceResolver(
        ports=_empty_catalogue_read_ports(),
        candidates=candidates,
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="369",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values == aggregated
    assert resolution.source_transaction_ids == ("oss-ledger-1",)
    assert resolution.diagnostics == ()
    assert tuple(item.source_ref for item in resolution.provenance) == ("transaction:oss-ledger-1",)


def test_oss_source_mesh_resolver_surfaces_advisory_for_unrouted_observation() -> None:
    """A non-zero OSS line routed to no binding surfaces a non-blocking advisory.

    The esquema-union revision binds DE/FR union services and DE goods-distance;
    no binding selects an IT destination. An IT-destination candidate matches no
    binding; its base/cuota would otherwise silently vanish from the M369 form,
    so the resolver MUST emit an ``unrouted_observation`` advisory rather than
    dropping it (no-silent-under-declaration).
    """
    revision = _revision("369", "esquema-union")
    candidates = (
        OssIossLedgerCandidate(
            ledger_id="oss-it-unrouted",
            transaction_date=date(2025, 7, 15),
            regime=OssIossRegime("union_scheme"),
            destination_member_state=EUMemberState.from_registry("it"),
            rate_kind=IvaRateKind("general"),
            invoice_direction=IvaInvoiceKind.ISSUED,
            transaction_kind=TransactionKind("oss_union_services"),
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("22.00"),
        ),
    )

    resolution = OssIossLedgerSourceResolver(
        ports=_empty_catalogue_read_ports(),
        candidates=candidates,
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="369",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
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
    assert len(unrouted) == 1, "an IT-destination OSS line routed to no binding must surface one advisory"
    # The advisory is non-blocking: the resolution still resolves the (zero) DE
    # binding value and records the candidate so calculate succeeds.
    assert resolution.binding_values.get("modelo-369-union-de-services-21pct") == Decimal("0")


def test_the_screen_now_catches_a_non_es_invoice_carrying_spanish_cuota() -> None:
    """A foreign counterparty does not mean the operation carried no Spanish IVA.

    The screen filtered on the counterparty's COUNTRY, which was standing in
    for "carries Spanish IVA" and is a poor proxy for it. An invoice to a
    foreign customer can carry ordinary domestic cuota -- goods that never
    leave the país, a service localised here, a non-established consumer --
    and every one of those was exempt from the screen, which is precisely the
    under-declaration the screen exists to catch.

    Same figures as the domestic refusal case above; only the counterparty's
    country differs. Before this, changing that one field was enough to walk
    the invoice past the guard.
    """
    revision = _m303_revision()
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    invoice_repo = _InMemoryInvoiceCatalogueRepository()
    invoice = _domestic_iva_invoice(
        "DE-1T-SALE",
        kind=CatalogueInvoiceKind.ISSUED,
        issued_at=date(2025, 2, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        counterparty_country="DE",
        counterparty_tax_id="DE345678901",
    )
    invoice_repo.save(build_invoice_catalogue((invoice,)))

    with pytest.raises(AggregationValidationError) as exc_info:
        _ledger_iva_resolver(
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            prorrata_register_repository=empty_prorrata_repository(),
        ).resolve(
            CalculationSourceContext(
                bucket_id=BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                revision=revision,
            ),
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["reason"] == "invoice_domestic_iva_not_in_transaction_ledger"


def test_an_exempt_intracommunity_invoice_does_not_trip_the_widened_screen() -> None:
    """Positive control: widening the screen must not refuse the ordinary EU case.

    An entrega intracomunitaria exenta is the commonest non-ES invoice there
    is, and it carries no cuota at all. Dropping the country filter must not
    start refusing those, or the widening would block correct filings far more
    often than it catches wrong ones.

    It passes for a structural reason rather than by luck: the screen compares
    only lines carrying a positive cuota, so a zero-cuota invoice contributes
    no observation whatever its counterparty's country. That is why removing
    the country proxy widens WHICH invoices are considered without widening
    what is actually compared.
    """
    revision = _m303_revision()
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    invoice_repo = _InMemoryInvoiceCatalogueRepository()
    exempt = _exempt_intracommunity_invoice(
        "DE-1T-EXEMPT",
        kind=CatalogueInvoiceKind.ISSUED,
        issued_at=date(2025, 2, 10),
        taxable_base=Decimal("10000.00"),
    )
    invoice_repo.save(build_invoice_catalogue((exempt,)))

    resolution = _ledger_iva_resolver(
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
            revision=revision,
        ),
    )

    assert resolution.resolver_id == "ledger_iva_aggregation"
