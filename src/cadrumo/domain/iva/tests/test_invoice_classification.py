"""Tests for the reusable IVA classification record."""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path
from typing import Any, cast, override

import pytest
from pydantic import ValidationError

from ....core.directory_scan import scan_directory
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ...calculations.registry.authority import bundled_authority
from ...calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ...invoices.enums import IvaRate
from ..classification import InvoiceKind
from ..deduction_facts import IvaDeductionClassificationProvenance
from ..flow import IvaFlowDirection, IvaSettlementSide
from ..invoice_classification import (
    IvaInvoiceClassification,
    classify_invoice_line_for_iva,
)
from ..schema import IvaCashAccountingTreatment, IvaCategory, IvaLedgerObservationRole, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_classify_issued_invoice_at_each_rate_slot_resolves_to_repercutido() -> None:
    cases: tuple[tuple[IvaRate, IvaCategory, IvaRateKind], ...] = (
        (IvaRate.RATE_0, IvaCategory.DOMESTIC_ZERO, IvaRateKind.ZERO),
        (IvaRate.RATE_4, IvaCategory.DOMESTIC_SUPER_REDUCED, IvaRateKind.SUPER_REDUCED),
        (IvaRate.RATE_10, IvaCategory.DOMESTIC_REDUCED, IvaRateKind.REDUCED),
        (IvaRate.RATE_21, IvaCategory.DOMESTIC_GENERAL, IvaRateKind.GENERAL),
        (IvaRate.EXEMPT, IvaCategory.DOMESTIC_EXEMPT, IvaRateKind.EXEMPT),
    )

    for iva_rate, expected_category, expected_kind in cases:
        classification = classify_invoice_line_for_iva(iva_rate=iva_rate, invoice_kind=InvoiceKind.ISSUED)
        assert classification.category is expected_category, iva_rate
        assert classification.rate_kind is expected_kind, iva_rate
        assert classification.flow_direction is IvaFlowDirection.REPERCUTIDO, iva_rate
        assert classification.settlement_sides == frozenset({IvaSettlementSide.DEVENGADA}), iva_rate


def test_classify_received_invoice_resolves_to_soportado() -> None:
    for iva_rate in (IvaRate.RATE_0, IvaRate.RATE_4, IvaRate.RATE_10, IvaRate.RATE_21, IvaRate.EXEMPT):
        classification = classify_invoice_line_for_iva(iva_rate=iva_rate, invoice_kind=InvoiceKind.RECEIVED)
        assert classification.flow_direction is IvaFlowDirection.SOPORTADO, iva_rate
        assert classification.settlement_sides == frozenset({IvaSettlementSide.DEDUCIBLE}), iva_rate


def test_classify_invoice_rejects_not_subject_rate() -> None:
    """NOT_SUBJECT operations are out of scope of IVA — the standard-case
    helper rejects them so callers explicitly handle them via
    IvaCategory.OPERACION_NO_SUJETA."""
    with pytest.raises(ValueError, match="NOT_SUBJECT"):
        classify_invoice_line_for_iva(iva_rate=IvaRate.NOT_SUBJECT, invoice_kind=InvoiceKind.ISSUED)


def test_classification_record_contributes_to_devengada_for_repercutido() -> None:
    classification = classify_invoice_line_for_iva(iva_rate=IvaRate.RATE_21, invoice_kind=InvoiceKind.ISSUED)
    assert classification.contributes_to_devengada is True
    assert classification.contributes_to_deducible is False
    assert classification.is_reverse_charge is False


def test_classification_record_contributes_to_deducible_for_soportado() -> None:
    classification = classify_invoice_line_for_iva(iva_rate=IvaRate.RATE_21, invoice_kind=InvoiceKind.RECEIVED)
    assert classification.contributes_to_devengada is False
    assert classification.contributes_to_deducible is True
    assert classification.is_reverse_charge is False


def test_classification_record_contributes_to_both_sides_for_autorepercutido() -> None:
    """Reverse-charge operations contribute to BOTH cornerstones on the
    same operation (LIVA art 84.Uno.2). Callers construct the record
    directly for these cases."""
    classification = IvaInvoiceClassification(
        category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        settlement_sides=frozenset({IvaSettlementSide.DEVENGADA, IvaSettlementSide.DEDUCIBLE}),
    )
    assert classification.contributes_to_devengada is True
    assert classification.contributes_to_deducible is True
    assert classification.is_reverse_charge is True


def test_classification_record_validates_settlement_sides_against_flow() -> None:
    """Constructor must reject inconsistent (flow_direction,
    settlement_sides) pairs — guards against drift between the two
    fields."""
    with pytest.raises(ValueError, match="does not match flow_direction"):
        IvaInvoiceClassification(
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            settlement_sides=frozenset(
                {IvaSettlementSide.DEDUCIBLE},  # ← doesn't match REPERCUTIDO
            ),
        )


def test_classification_record_is_frozen() -> None:
    classification = classify_invoice_line_for_iva(iva_rate=IvaRate.RATE_21, invoice_kind=InvoiceKind.ISSUED)
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        classification.flow_direction = IvaFlowDirection.SOPORTADO


def test_classification_for_reverse_charge_category_with_inconsistent_flow_rejected() -> None:
    """Even if the IvaCategory says reverse-charge, the constructor
    only accepts INVERSION_SUJETO_PASIVO when settlement_sides has both — the
    cross-check is on (flow, sides), not on category."""
    with pytest.raises(ValueError, match="does not match flow_direction"):
        IvaInvoiceClassification(
            category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            settlement_sides=frozenset({IvaSettlementSide.DEVENGADA}),  # missing deducible
        )


# ---------------------------------------------------------------------------
# Ledger → modelo bridge: invoice_line_to_iva_observation
# ---------------------------------------------------------------------------


def test_invoice_line_to_iva_observation_builds_repercutido_record_for_issued() -> None:
    from datetime import date
    from decimal import Decimal

    from ..invoice_classification import invoice_line_to_iva_observation

    obs = invoice_line_to_iva_observation(
        invoice_id="inv-001",
        issued_at=date(2025, 6, 15),
        invoice_kind=InvoiceKind.ISSUED,
        iva_rate=IvaRate.RATE_21,
        base_amount=Decimal("1000"),
        iva_amount=Decimal("210"),
        deduction_fact_kind=None,
        deduction_provenance=None,
    )
    assert isinstance(obs, IvaLedgerObservation)
    assert obs.ledger_id == "inv-001"
    assert obs.transaction_date == date(2025, 6, 15)
    assert obs.category is IvaCategory.DOMESTIC_GENERAL
    assert obs.rate_kind is IvaRateKind.GENERAL
    assert obs.flow_direction is IvaFlowDirection.REPERCUTIDO
    assert obs.base_amount == Decimal("1000")
    assert obs.iva_amount == Decimal("210")


def test_invoice_observation_carries_the_rate_the_line_charged_not_its_tier_default() -> None:
    """A 2 % foodstuffs line reaches the modelo bridge as 2 %, and is discriminable from 4 %.

    ``applied_rate`` was deliberately unset on this path while an invoice line
    carried a rate SLOT rather than a number. The RD-ley 4/2024 food slots ended
    that: ``RATE_2`` names its own rate, so the number is measured rather than
    inferred, and withholding it drops the line out of every rate-specific box
    on the annual return -- the 2 % line missing from the 2 % box.

    The 4 % case is the discriminator, not padding. Both slots share the
    super-reducido tier, so an implementation that resolved the TIER instead of
    the slot would return 4 % for both and this test would still see a populated
    field. Only the pair distinguishes "carries its own rate" from "carries
    something".
    """
    from datetime import date

    from ..invoice_classification import invoice_line_to_iva_observation

    in_window = date(2024, 11, 15)
    two_percent = invoice_line_to_iva_observation(
        invoice_id="inv-2pct",
        issued_at=in_window,
        invoice_kind=InvoiceKind.ISSUED,
        iva_rate=IvaRate.RATE_2,
        base_amount=Decimal("100"),
        iva_amount=Decimal("2"),
        deduction_fact_kind=None,
        deduction_provenance=None,
    )
    four_percent = invoice_line_to_iva_observation(
        invoice_id="inv-4pct",
        issued_at=in_window,
        invoice_kind=InvoiceKind.ISSUED,
        iva_rate=IvaRate.RATE_4,
        base_amount=Decimal("100"),
        iva_amount=Decimal("4"),
        deduction_fact_kind=None,
        deduction_provenance=None,
    )

    assert two_percent.applied_rate == Decimal("0.02")
    assert four_percent.applied_rate == Decimal("0.04")
    assert two_percent.rate_kind is four_percent.rate_kind is IvaRateKind.SUPER_REDUCED
    assert two_percent.applied_rate != four_percent.applied_rate, (
        "both slots share the super-reducido tier, so a tier-resolved applied_rate would collapse them "
        "and the 2 % line would be indistinguishable from a 4 % one at the annual return"
    )


def test_invoice_sourced_rows_reach_their_own_rate_specific_box() -> None:
    """Mutation proof: an invoice-derived 2 % line lands in the 2 % box, not nowhere.

    Asserting ``applied_rate == 0.02`` says nothing about whether anything reads
    it. This drives the real production resolver over the real invoice bridge,
    against the per-rate box shape Modelo 390 uses, and separates the two
    outcomes that matter: each row reaching its own box, and neither absorbing
    the other's.

    The pre-change behaviour is what makes this load-bearing. Both observations
    carried ``applied_rate=None``, which matches NO rate-specific binding, so
    both boxes resolved to zero -- the lines vanished rather than being
    misfiled. A silent drop is invisible to every totals check, which is why
    nothing failed while it was happening.
    """
    from datetime import date

    from ....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
    from ...calculations.registry.ledger_iva_bindings import resolve_ledger_iva_aggregation_binding_values
    from ...calculations.registry.schema import DataBindingDefinition, ModeloRevision
    from ...calculations.registry.schema_references import PeriodSelector
    from ..invoice_classification import invoice_line_to_iva_observation

    def _rate_box(binding_id: str, rate: Decimal) -> DataBindingDefinition:
        return DataBindingDefinition(
            id=binding_id,
            source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
            selector={
                "categories": (IvaCategory.DOMESTIC_SUPER_REDUCED,),
                "rate_kinds": (IvaRateKind.SUPER_REDUCED,),
                "flow_direction": IvaFlowDirection.REPERCUTIDO,
                "observation_roles": (IvaLedgerObservationRole.SETTLEMENT,),
                "cash_accounting_treatments": (
                    IvaCashAccountingTreatment.NONE,
                    IvaCashAccountingTreatment.TAXPAYER_REGIME,
                    IvaCashAccountingTreatment.SUPPLIER_REGIME,
                ),
                "applied_rates": (rate,),
                "fact": "base_amount_sum",
            },
            aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
            legal_refs=("ley-37-1992:art-91",),
            source_refs=("aeat-dr-390-2025",),
        )

    in_window = date(2024, 11, 15)
    rows = tuple(
        cast(Any, invoice_line_to_iva_observation)(
            invoice_id=f"inv-{slot.name}",
            issued_at=in_window,
            invoice_kind=InvoiceKind.ISSUED,
            iva_rate=slot,
            base_amount=base,
            iva_amount=Decimal("1"),
            deduction_fact_kind=None,
            deduction_provenance=None,
        )
        for slot, base in ((IvaRate.RATE_2, Decimal("100.00")), (IvaRate.RATE_4, Decimal("250.00")))
    )
    revision = ModeloRevision(
        id="2010-y-siguientes",
        localization_key="test.schema.revision.2010-y-siguientes.label",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        legal_refs=("ley-37-1992:art-91",),
        source_refs=("aeat-dr-390-2025",),
        bindings=(
            _rate_box("m390-super-reducido-2pct", Decimal("0.02")),
            _rate_box("m390-super-reducido-4pct", Decimal("0.04")),
        ),
    )

    resolved = resolve_ledger_iva_aggregation_binding_values(revision, rows)

    assert resolved["m390-super-reducido-2pct"] == Decimal("100.00")
    assert resolved["m390-super-reducido-4pct"] == Decimal("250.00")

    # The pre-change arm, asserted rather than described: strip the rate the way
    # this path used to leave it and both boxes go to zero. Without this the
    # test above could pass against a resolver that ignored applied_rate
    # entirely and matched on tier alone -- it would then put 350 in each box,
    # which the equalities catch, but a resolver that dropped BOTH rows would
    # need this arm to be distinguishable from a genuine empty period.
    unrated = tuple(row.model_copy(update={"applied_rate": None}) for row in rows)
    dropped = resolve_ledger_iva_aggregation_binding_values(revision, unrated)

    assert dropped["m390-super-reducido-2pct"] == Decimal("0")
    assert dropped["m390-super-reducido-4pct"] == Decimal("0")


def test_invoice_line_to_iva_observation_builds_soportado_record_for_received() -> None:
    from datetime import date
    from decimal import Decimal

    from ..invoice_classification import invoice_line_to_iva_observation

    obs = invoice_line_to_iva_observation(
        invoice_id="bill-77",
        issued_at=date(2025, 7, 1),
        invoice_kind=InvoiceKind.RECEIVED,
        iva_rate=IvaRate.RATE_10,
        base_amount=Decimal("500"),
        iva_amount=Decimal("50"),
        deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            source_locator="invoice:bill-77",
            evidence_digest="a" * 64,
        ),
    )
    assert obs.flow_direction is IvaFlowDirection.SOPORTADO
    assert obs.category is IvaCategory.DOMESTIC_REDUCED
    assert obs.rate_kind is IvaRateKind.REDUCED
    assert obs.deduction_fact_kind is IvaDeductionFactKind.DOMESTIC_CURRENT


def test_invoice_line_to_iva_observation_refuses_received_input_without_exact_authority() -> None:
    """A received invoice cannot become deductible IVA by a domestic-current default."""
    from datetime import date

    from ..invoice_classification import invoice_line_to_iva_observation

    with pytest.raises(TypeError, match=r"deduction_fact_kind|deduction_provenance"):
        cast(Any, invoice_line_to_iva_observation)(
            invoice_id="bill-without-authority",
            issued_at=date(2025, 7, 1),
            invoice_kind=InvoiceKind.RECEIVED,
            iva_rate=IvaRate.RATE_10,
            base_amount=Decimal("500"),
            iva_amount=Decimal("50"),
        )
    with pytest.raises(ValidationError, match="exact deduction authority"):
        invoice_line_to_iva_observation(
            invoice_id="bill-explicitly-unclassified",
            issued_at=date(2025, 7, 1),
            invoice_kind=InvoiceKind.RECEIVED,
            iva_rate=IvaRate.RATE_10,
            base_amount=Decimal("500"),
            iva_amount=Decimal("50"),
            deduction_fact_kind=None,
            deduction_provenance=None,
        )


def test_invoice_line_to_iva_observation_rejects_non_decimal_amounts() -> None:
    from datetime import date

    from ..invoice_classification import invoice_line_to_iva_observation

    with pytest.raises(ValidationError, match=r"base_amount|iva_amount|Decimal|decimal"):
        invoice_line_to_iva_observation(
            invoice_id="inv-bad",
            issued_at=date(2025, 6, 15),
            invoice_kind=InvoiceKind.ISSUED,
            iva_rate=IvaRate.RATE_21,
            base_amount=cast(Decimal, "1000"),
            iva_amount=cast(Decimal, "210"),
            deduction_fact_kind=None,
            deduction_provenance=None,
        )


def test_invoice_line_observation_feeds_modelo_303_binding_resolver_end_to_end() -> None:
    """The full ledger → substrate → modelo registry chain: build
    observations from invoice metadata via invoice_line_to_iva_observation,
    feed them to resolve_ledger_iva_aggregation_binding_values, get
    binding totals back."""
    from datetime import date
    from decimal import Decimal

    from ...calculations.registry.ledger_iva_bindings import resolve_ledger_iva_aggregation_binding_values
    from ..invoice_classification import invoice_line_to_iva_observation

    m303 = bundled_authority().modelo("303")
    revision = m303.revisions["2022"]

    # Two issued + one received line, all standard-case domestic
    observations = (
        invoice_line_to_iva_observation(
            invoice_id="inv-1",
            issued_at=date(2025, 1, 15),
            invoice_kind=InvoiceKind.ISSUED,
            iva_rate=IvaRate.RATE_21,
            base_amount=Decimal("1000"),
            iva_amount=Decimal("210"),
            deduction_fact_kind=None,
            deduction_provenance=None,
        ),
        invoice_line_to_iva_observation(
            invoice_id="inv-2",
            issued_at=date(2025, 1, 20),
            invoice_kind=InvoiceKind.ISSUED,
            iva_rate=IvaRate.RATE_10,
            base_amount=Decimal("500"),
            iva_amount=Decimal("50"),
            deduction_fact_kind=None,
            deduction_provenance=None,
        ),
        invoice_line_to_iva_observation(
            invoice_id="bill-1",
            issued_at=date(2025, 2, 10),
            invoice_kind=InvoiceKind.RECEIVED,
            iva_rate=IvaRate.RATE_21,
            base_amount=Decimal("400"),
            iva_amount=Decimal("84"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_provenance=IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                source_locator="invoice:bill-1",
                evidence_digest="b" * 64,
            ),
        ),
    )
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    # Routing wiring: each per-rate single-observation result threads the
    # originating observation's iva_amount through the resolver. The
    # assertions read the iva_amount off the source observation rather
    # than carrying a hand-written literal, so a future author changing
    # a synthetic input cannot accidentally make the test agree with a
    # silently-broken resolver. Arithmetic of base_amount vs iva_amount
    # is verified against AEAT authority through the workbook parity
    # tests in the calculations registry.
    assert result["modelo-303-iva-repercutido-general-cuota"] == observations[0].iva_amount
    assert result["modelo-303-iva-repercutido-reducido-cuota"] == observations[1].iva_amount
    assert result["modelo-303-iva-soportado-interiores-cuota"] == observations[2].iva_amount


def test_invoice_iva_bridge_callers_supply_explicit_deduction_authority_or_refuse() -> None:
    """The invoice bridge may not regain an implicit received-IVA default."""
    source_root = Path(__file__).parents[3]
    intentional_refusals = {
        (
            "domain/iva/tests/test_invoice_classification.py",
            "test_invoice_line_to_iva_observation_refuses_received_input_without_exact_authority",
        )
    }
    bridge_calls: list[tuple[str, str | None, set[str]]] = []
    observation_calls: list[tuple[str, int, set[str]]] = []

    for path in scan_directory(source_root, pattern="*.py", recursive=True):
        source = path.read_text(encoding="utf-8")
        if "invoice_line_to_iva_observation" not in source and "IvaLedgerObservation(" not in source:
            continue
        tree = ast.parse(source, filename=str(path))
        relative_path = path.relative_to(source_root).as_posix()

        class Visitor(ast.NodeVisitor):
            current_function: str | None = None
            relative_path: str

            @override
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                previous = self.current_function
                self.current_function = node.name
                self.generic_visit(node)
                self.current_function = previous

            @override
            def visit_Call(self, node: ast.Call) -> None:
                keyword_names = {keyword.arg for keyword in node.keywords if keyword.arg is not None}
                if isinstance(node.func, ast.Name) and node.func.id == "invoice_line_to_iva_observation":
                    bridge_calls.append((self.relative_path, self.current_function, keyword_names))
                if isinstance(node.func, ast.Name) and node.func.id == "IvaLedgerObservation":
                    observation_calls.append((self.relative_path, node.lineno, keyword_names))
                self.generic_visit(node)

        visitor = Visitor()
        visitor.relative_path = relative_path
        visitor.visit(tree)

    # Non-vacuity: prove the walk actually reached both the production bridge
    # caller and the exempted refusal proof, rather than pinning a tally that
    # every new call site would have to bump.
    scanned = {(relative_path, function_name) for relative_path, function_name, _ in bridge_calls}
    assert any(path == "application/aggregation/_modelo_bindings.py" for path, _ in scanned), (
        "the bridge scan never reached the production caller"
    )
    assert intentional_refusals <= scanned, "the exempted refusal proof was not scanned"
    for relative_path, function_name, keyword_names in bridge_calls:
        if (relative_path, function_name) in intentional_refusals:
            continue
        assert {"deduction_fact_kind", "deduction_provenance"} <= keyword_names, (
            f"{relative_path}:{function_name} constructs invoice IVA without explicit deduction authority"
        )
    production_observation_paths = {
        "domain/iva/_invoice_classification.py",
        "application/aggregation/_modelo_bindings.py",
    }
    for relative_path, lineno, keyword_names in observation_calls:
        if relative_path in production_observation_paths:
            assert {"deduction_fact_kind", "deduction_provenance"} <= keyword_names, (
                f"{relative_path}:{lineno} constructs IVA without explicit deduction authority"
            )
