"""The IVA ledger refuses stored registry values the operation's pinned authority does not accept.

Every row here is first admitted through the real ``Transaction`` constructor and
then handed back the way a store would return a row admitted under an authority
that has since retired one of its tokens: ``model_construct`` with the stale
value, so no admission runs. Each stale value used to be read as its nearest
ordinary meaning -- criterio de caja, an exempt intra-community acquirer, a
volume exclusion -- or to crash at an untyped boundary. Each pair below asserts
the refusal for the stale row and the unchanged result for the admitted one.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....core.prorrata_exclusions import Art104TresExclusion
from ....core.prorrata_register import ProrrataProvisionalProvenance
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.ledger_iva_bindings import resolve_ledger_iva_aggregation_binding_values
from ....domain.calculations.registry.prorrata_register_catalogue import especial_prorrata_register_regime
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.prorrata import InputClassification
from ....domain.iva.schema import (
    EUMemberState,
    IvaCashAccountingPaymentEvidence,
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
)
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..errors import UnacceptedLedgerRegistryValueError
from ..iva_ledger import (
    IvaLedgerAggregation,
    IvaLedgerAggregationIssueReason,
    IvaLedgerProrrataApportionment,
    resolve_iva_ledger_binding_values,
)
from ..modelo_bindings import LedgerIvaAggregationSourceResolver, _selected_scope_iva_evidence_diagnostics
from .iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PERIOD = Period.from_year_and_code(2026, "2T")
_BOOKED = date(2026, 4, 15)
_UNACCEPTED = IvaLedgerAggregationIssueReason.UNACCEPTED_REGISTRY_VALUE
_CASILLA_59_BASE: BindingId = "modelo-303-casilla-59-entregas-intracomunitarias-base"


@cache
def _modelo_303_revision() -> ModeloRevision:
    return published_snapshot("303", filing_year=2026, period="2T").revision


def _raw(provider_id: str, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=_BOOKED,
        value_date=_BOOKED,
        amount=amount,
        currency="EUR",
        counterparty="Contraparte",
        description=f"stale-token {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 16, 9, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _row(
    provider_id: str,
    *,
    direction: TransactionDirection = TransactionDirection.INCOMING,
    category: str = "domestic_general",
    base: Decimal = Decimal("1000.00"),
    rate: Decimal = Decimal("0.21"),
    business: BusinessClassification = BusinessClassification.BUSINESS,
    **extra: object,
) -> Transaction:
    """Admit one classified EUR row through the real constructor."""
    iva = (base * rate).quantize(Decimal("0.01"))
    fields: dict[str, object] = {
        "raw": _raw(provider_id, base + iva),
        "direction": direction,
        "group_label": None,
        "source_jurisdiction": "ES",
        "business_classification": business,
        "taxable_base": base,
        "iva_rate": rate,
        "iva_amount": iva,
        "iva_category": IvaCategory(category),
        "lifecycle_state": TransactionLifecycleState.ACTIVE,
        "classified_at": datetime(2026, 4, 16, 10, 0, tzinfo=UTC),
        "classified_by": "manual",
    }
    if direction is TransactionDirection.OUTGOING:
        fields["deduction_fact_kind"] = IvaDeductionFactKind.from_registry("domestic_current")
        fields["deduction_provenance"] = IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
            source_locator=f"invoice:{provider_id}",
            evidence_digest="a" * 64,
        )
    fields.update(extra)
    return Transaction.model_validate(fields)


def _stale(row: Transaction, **fields: object) -> Transaction:
    """Hand the row back carrying a value no admission re-checked, as a stale stored row arrives."""
    values = {name: getattr(row, name) for name in Transaction.model_fields} | fields
    return Transaction.model_construct(_fields_set=row.model_fields_set | set(fields), **values)


def _aggregate(*rows: Transaction) -> IvaLedgerAggregation:
    """Aggregate rows as a store hands them back: the catalogue does not re-admit them either."""
    catalogue = TransactionCatalogue.model_construct(transactions={row.transaction_id: row for row in rows})
    return aggregate_iva_ledger_observations(catalogue, period=_PERIOD)


def _assert_refused(aggregation: IvaLedgerAggregation, row: Transaction, *, field: str, value: str) -> None:
    assert aggregation.observations == (), f"a row carrying an unaccepted {field} must not feed the calculation"
    assert [(issue.transaction_id, issue.reason) for issue in aggregation.issues] == [(row.transaction_id, _UNACCEPTED)]
    detail = aggregation.issues[0].detail
    assert field in detail, detail
    assert value in detail, detail


def _cash_sale(provider_id: str) -> Transaction:
    return _row(
        provider_id,
        cash_accounting_treatment=IvaCashAccountingTreatment("taxpayer_regime"),
        operation_date=date(2026, 3, 20),
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=_BOOKED,
                taxable_base=Decimal("1000.00"),
                iva_amount=Decimal("210.00"),
            ),
        ),
    )


def test_an_undeclared_cash_accounting_treatment_is_refused_not_settled_on_collection() -> None:
    admitted = _cash_sale("cash-admitted")
    accepted = _aggregate(admitted)
    assert accepted.issues == ()
    assert [observation.base_amount for observation in accepted.observations] == [Decimal("1000.00")]

    stale = _stale(admitted, cash_accounting_treatment=IvaCashAccountingTreatment("retired_regime"))
    _assert_refused(_aggregate(stale), stale, field="cash_accounting_treatment", value="retired_regime")


def test_an_undeclared_treatment_on_a_row_outside_the_calculation_does_not_block_it() -> None:
    """A personal row feeds no IVA, so its unusable treatment is not this calculation's finding."""
    personal = _stale(
        _row("cash-personal", business=BusinessClassification.PERSONAL),
        cash_accounting_treatment=IvaCashAccountingTreatment("retired_regime"),
    )

    aggregation = _aggregate(personal)

    assert [issue.reason for issue in aggregation.issues] == [IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION]


def test_incoherent_cash_accounting_evidence_is_a_typed_finding_not_an_untyped_crash() -> None:
    """A criterio-de-caja row with no operation date used to raise a bare ``ValueError`` in the split."""
    stale = _stale(_cash_sale("cash-no-devengo"), operation_date=None)

    aggregation = _aggregate(stale)

    assert aggregation.observations == ()
    assert [(issue.transaction_id, issue.reason) for issue in aggregation.issues] == [
        (stale.transaction_id, IvaLedgerAggregationIssueReason.CASH_ACCOUNTING_EVIDENCE_INCOHERENT),
    ]
    assert "operation_date" in aggregation.issues[0].detail


def test_settlement_evidence_on_an_ordinary_row_is_refused() -> None:
    ordinary = _stale(
        _row("ordinary-with-evidence"),
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=_BOOKED,
                taxable_base=Decimal("500.00"),
                iva_amount=Decimal("105.00"),
            ),
        ),
    )

    aggregation = _aggregate(ordinary)

    assert [issue.reason for issue in aggregation.issues] == [
        IvaLedgerAggregationIssueReason.CASH_ACCOUNTING_EVIDENCE_INCOHERENT
    ]


def _intracom_supply(provider_id: str, identified_in: str) -> Transaction:
    return _row(
        provider_id,
        category="intra_community_supply",
        base=Decimal("5000.00"),
        rate=Decimal("0"),
        counterparty_country="DE",
        counterparty_identification_state=EUMemberState.from_registry(identified_in),
    )


def test_an_undeclared_identification_state_does_not_pass_the_art_25_gate() -> None:
    """The gate compared only with the Spanish token, so any other token exempted the supply."""
    admitted = _intracom_supply("intracom-admitted", "de")
    accepted = _aggregate(admitted)
    assert accepted.issues == ()
    binding_values = resolve_ledger_iva_aggregation_binding_values(_modelo_303_revision(), accepted.observations)
    assert binding_values[_CASILLA_59_BASE] == Decimal("5000.00")

    stale = _stale(admitted, counterparty_identification_state=EUMemberState.from_registry("xx"))
    refused = _aggregate(stale)

    _assert_refused(refused, stale, field="counterparty_identification_state", value="xx")
    assert resolve_ledger_iva_aggregation_binding_values(_modelo_303_revision(), refused.observations).get(
        _CASILLA_59_BASE, Decimal("0")
    ) == Decimal("0")


def test_an_identification_state_is_judged_only_where_the_gate_reads_it() -> None:
    """A domestic supply never reads the identification state, so a stale one changes nothing."""
    admitted = _row("domestic-identified", counterparty_identification_state=EUMemberState.from_registry("de"))
    stale = _stale(admitted, counterparty_identification_state=EUMemberState.from_registry("xx"))

    assert _aggregate(stale).observations == _aggregate(admitted).observations
    assert _aggregate(stale).issues == ()


def _exempt_supply(provider_id: str) -> Transaction:
    return _row(
        provider_id,
        category="domestic_exempt",
        rate=Decimal("0"),
        exemption_article=IvaExemptionArticle("art_20_uno_8"),
    )


def test_an_undeclared_exemption_article_is_a_finding_not_a_payload_boundary_crash() -> None:
    admitted = _exempt_supply("exempt-admitted")
    accepted = _aggregate(admitted)
    assert accepted.issues == ()
    assert [observation.exemption_article for observation in accepted.observations] == [
        IvaExemptionArticle("art_20_uno_8")
    ]

    stale = _stale(admitted, exemption_article=IvaExemptionArticle("art_20_uno_99"))
    _assert_refused(_aggregate(stale), stale, field="exemption_article", value="art_20_uno_99")


def test_an_exemption_article_outside_a_domestic_exempt_row_is_refused() -> None:
    stale = _stale(_row("taxed-with-article"), exemption_article=IvaExemptionArticle("art_20_uno_8"))

    aggregation = _aggregate(stale)

    assert aggregation.observations == ()
    assert [issue.reason for issue in aggregation.issues] == [_UNACCEPTED]
    assert "art_20_uno_8" in aggregation.issues[0].detail
    assert "domestic_general" in aggregation.issues[0].detail


def _purchase(provider_id: str, classification: str) -> Transaction:
    return _row(
        provider_id,
        direction=TransactionDirection.OUTGOING,
        input_classification=InputClassification.from_registry(classification),
    )


def test_an_undeclared_input_classification_is_refused_before_it_reaches_apportionment() -> None:
    admitted = _purchase("purchase-admitted", "exclusively_deductible")
    accepted = _aggregate(admitted)
    assert accepted.issues == ()
    assert [observation.input_classification for observation in accepted.observations] == [
        InputClassification.from_registry("exclusively_deductible")
    ]

    stale = _stale(admitted, input_classification=InputClassification.from_registry("retired_classification"))
    _assert_refused(_aggregate(stale), stale, field="input_classification", value="retired_classification")


def test_apportionment_refuses_an_undeclared_classification_with_a_typed_refusal() -> None:
    """The especial partition used to fail with a bare ``KeyError`` naming only the token."""
    admitted = _purchase("purchase-especial", "exclusively_deductible")
    observation = _aggregate(admitted).observations[0]
    stale_observation = observation.model_copy(
        update={"input_classification": InputClassification.from_registry("retired_classification")},
    )
    with bundled_indexed_authority().operation() as operation:
        apportionment = IvaLedgerProrrataApportionment(
            percentage=Decimal("73"),
            provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
            regime=especial_prorrata_register_regime(authority=operation),
        )
        unapportioned = resolve_iva_ledger_binding_values(_modelo_303_revision(), (observation,), operation=operation)
        especial = resolve_iva_ledger_binding_values(
            _modelo_303_revision(),
            (observation,),
            prorrata_apportionment=apportionment,
            operation=operation,
        )
        with pytest.raises(UnacceptedLedgerRegistryValueError) as refusal:
            resolve_iva_ledger_binding_values(
                _modelo_303_revision(),
                (stale_observation,),
                prorrata_apportionment=apportionment,
                operation=operation,
            )

    # Art. 106.Uno: an exclusively-deductible input deducts in full whatever the
    # common percentage, so the especial routing leaves every value as it was.
    assert especial == unapportioned
    assert any(value == Decimal("210.00") for value in especial.values())
    context = refusal.value.context
    assert context is not None
    assert context["field"] == "input_classification"
    assert context["value"] == "retired_classification"
    assert context["transaction_id"] == admitted.transaction_id


def test_an_undeclared_art_104_tres_exclusion_is_refused_not_dropped_from_the_volume() -> None:
    """Any non-empty tag used to take the operation out of both terms of the prorrata."""
    admitted = _row(
        "excluded-admitted",
        art_104_tres_exclusion=Art104TresExclusion("foreign_permanent_establishment"),
    )
    accepted = _aggregate(admitted)
    assert accepted.issues == ()
    assert accepted.art_104_tres_excluded_ledger_ids == (admitted.transaction_id,)
    assert accepted.observations == _aggregate(_row("excluded-admitted")).observations

    stale = _stale(admitted, art_104_tres_exclusion=Art104TresExclusion("retired_exclusion"))
    refused = _aggregate(stale)

    _assert_refused(refused, stale, field="art_104_tres_exclusion", value="retired_exclusion")
    assert refused.art_104_tres_excluded_ledger_ids == ()
    assert refused.unclassified_output_ledger_ids == (stale.transaction_id,)


def test_an_auto_derived_art_104_tres_exclusion_cannot_be_carried_on_a_row() -> None:
    stale = _stale(
        _row("auto-derived-tag"),
        art_104_tres_exclusion=Art104TresExclusion("non_subject_art_7"),
    )

    aggregation = _aggregate(stale)

    assert [issue.reason for issue in aggregation.issues] == [_UNACCEPTED]
    assert "non_subject_art_7" in aggregation.issues[0].detail
    assert aggregation.art_104_tres_excluded_ledger_ids == ()


def test_the_refusal_reaches_the_calculation_as_a_blocking_evidence_marker() -> None:
    """The source mesh carries the finding as the durable marker verification refuses on."""
    stale = _stale(_cash_sale("cash-marker"), cash_accounting_treatment=IvaCashAccountingTreatment("retired_regime"))

    diagnostics = _selected_scope_iva_evidence_diagnostics(
        _aggregate(stale).issues,
        resolver_id=LedgerIvaAggregationSourceResolver.resolver_id,
    )

    assert [(diagnostic.reason, diagnostic.source_ref) for diagnostic in diagnostics] == [
        ("iva_selected_scope_evidence_failure", f"transaction:{stale.transaction_id}"),
    ]
    assert "cash_accounting_treatment" in diagnostics[0].message
    assert "retired_regime" in diagnostics[0].message
