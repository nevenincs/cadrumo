"""Complete terminal-precondition contracts for aggregation refusals."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import override

import pytest

from ....core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.period import Period
from ....core.aggregation import BindingSourceKind
from ....core.errors.hierarchy import TerminalPreconditionErrorMixin
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ledger_bindings import IvaLedgerObservation
from ....domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.flow import derive_flow_for_classification
from ....domain.iva.schema import IvaCashAccountingTreatment, IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ....tests.secure_sql import isolated_runtime_profile
from .. import _modelo_bindings as modelo_bindings_module
from .. import _service as service_module
from .._modelo_bindings import RetencionesAggregationSourceResolver, _raise_if_screened_invoice_iva_would_be_silent
from .._preconditions import AggregationPreconditionCondition, aggregation_no_recovery_verdict
from .._retencion_observations_repository import RetencionObservationRepository
from .._service import _SUPPORTED_PER_MODELO_MODELOS, provider_for_modelo
from .._source_mesh import CalculationSourceContext
from ..errors import AggregationError, AggregationUnsupportedModeloError, AggregationValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True)
class _CarrierContract:
    condition: AggregationPreconditionCondition
    facts: tuple[tuple[str, str], ...]
    provenance: ActionEvidenceProvenance
    outcome: NoRecoveryOutcome


def _contract(
    condition: AggregationPreconditionCondition,
    facts: tuple[tuple[str, str], ...],
) -> _CarrierContract:
    return _CarrierContract(
        condition=condition,
        facts=facts,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


# Complete source-level contract for the two dispatch, two IVA-ledger, and one
# retenciones terminal attachments.  Fact values are AST expressions rather
# than just keys, so a dynamic calculation or boolean polarity cannot drift.
_AGGREGATION_FAILURE_TOTALITY: dict[str, _CarrierContract] = {
    "_service:provider_for_modelo:1": _contract(
        AggregationPreconditionCondition.PER_MODELO_MODELO_SUPPORTED,
        (("modelo", "modelo"), ("supported_modelos", "'|'.join(_SUPPORTED_PER_MODELO_MODELOS)")),
    ),
    "_service:provider_for_modelo:2": _contract(
        AggregationPreconditionCondition.PER_MODELO_MODELO_SUPPORTED,
        (("modelo", "modelo"), ("supported_modelos", "'|'.join(_SUPPORTED_PER_MODELO_MODELOS)")),
    ),
    "_modelo_bindings:_raise_if_screened_invoice_iva_would_be_silent:1": _contract(
        AggregationPreconditionCondition.INVOICE_LEDGER_COMPLETE,
        (
            ("modelo", "str(context.modelo)"),
            ("filing_year", "str(context.filing_year)"),
            ("period", "context.period.registry_token"),
            ("source_kind", "'ledger_iva_aggregation'"),
            ("invoice_count", "len(missing_invoice_ids)"),
            ("missing_binding_count", "0"),
        ),
    ),
    "_modelo_bindings:_raise_if_screened_invoice_iva_would_be_silent:2": _contract(
        AggregationPreconditionCondition.INVOICE_LEDGER_COMPLETE,
        (
            ("modelo", "str(context.modelo)"),
            ("filing_year", "str(context.filing_year)"),
            ("period", "context.period.registry_token"),
            ("source_kind", "'ledger_iva_aggregation'"),
            ("invoice_count", "len(screened.invoice_ids)"),
            ("missing_binding_count", "len(missing_binding_values)"),
        ),
    ),
    "_modelo_bindings:RetencionesAggregationSourceResolver.resolve:1": _contract(
        AggregationPreconditionCondition.RETENCIONES_OBSERVATIONS_PRESENT,
        (
            ("modelo", "str(context.modelo)"),
            ("filing_year", "str(context.filing_year)"),
            ("period", "context.period.registry_token"),
            ("source_kind", "'retenciones_aggregation'"),
        ),
    ),
}

_ATTACHMENT_MODULES: tuple[ModuleType, ...] = (service_module, modelo_bindings_module)


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _aggregation_carriers() -> dict[str, ast.Call]:
    carriers: dict[str, ast.Call] = {}
    for module in _ATTACHMENT_MODULES:
        tree = ast.parse(inspect.getsource(module))

        class Visitor(ast.NodeVisitor):
            def __init__(self, module_name: str) -> None:
                self.module_name = module_name
                self.owner = "<module>"
                self.occurrence: dict[str, int] = {}

            @override
            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                prior_owner = self.owner
                self.owner = node.name if prior_owner == "<module>" else f"{prior_owner}.{node.name}"
                self.generic_visit(node)
                self.owner = prior_owner

            @override
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                prior_owner = self.owner
                self.owner = node.name if prior_owner == "<module>" else f"{prior_owner}.{node.name}"
                self.generic_visit(node)
                self.owner = prior_owner

            @override
            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                prior_owner = self.owner
                self.owner = node.name if prior_owner == "<module>" else f"{prior_owner}.{node.name}"
                self.generic_visit(node)
                self.owner = prior_owner

            @override
            def visit_Call(self, node: ast.Call) -> None:
                if _call_name(node.func) in {"AggregationUnsupportedModeloError", "AggregationValidationError"}:
                    verdict = next(
                        (keyword.value for keyword in node.keywords if keyword.arg == "precondition_verdict"),
                        None,
                    )
                    if verdict is not None:
                        site = f"{self.module_name}:{self.owner}"
                        occurrence = self.occurrence.get(site, 0) + 1
                        self.occurrence[site] = occurrence
                        key = f"{site}:{occurrence}"
                        assert key not in carriers, f"duplicate aggregation terminal carrier {key}"
                        carriers[key] = node
                self.generic_visit(node)

        Visitor(module.__name__.rsplit(".", maxsplit=1)[-1]).visit(tree)
    return carriers


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def _precondition(call: ast.Call) -> ast.Call:
    value = _keyword(call, "precondition_verdict")
    assert isinstance(value, ast.Call)
    assert _call_name(value.func) == "aggregation_no_recovery_verdict"
    return value


def _condition(precondition: ast.Call) -> AggregationPreconditionCondition:
    value = precondition.args[0]
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == "AggregationPreconditionCondition"
    return AggregationPreconditionCondition[value.attr]


def _fact_expressions(precondition: ast.Call) -> tuple[tuple[str, str], ...]:
    facts = _keyword(precondition, "facts")
    assert isinstance(facts, ast.Dict)
    values: list[tuple[str, str]] = []
    for key, value in zip(facts.keys, facts.values, strict=True):
        assert isinstance(key, ast.Constant) and isinstance(key.value, str)
        values.append((key.value, ast.unparse(value)))
    return tuple(values)


def _normalized_outcome(precondition: ast.Call) -> NoRecoveryOutcome:
    value = _keyword(precondition, "outcome")
    if value is None:
        default = inspect.signature(aggregation_no_recovery_verdict).parameters["outcome"].default
        assert isinstance(default, NoRecoveryOutcome)
        return default
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == "NoRecoveryOutcome"
    return NoRecoveryOutcome[value.attr]


def _helper_provenance() -> ActionEvidenceProvenance:
    tree = ast.parse(inspect.getsource(__import__("cadrumo.application.aggregation._preconditions", fromlist=["*"])))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node.func) == "no_action_precondition_verdict"
    ]
    assert len(calls) == 1
    value = _keyword(calls[0], "provenance")
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == "ActionEvidenceProvenance"
    return ActionEvidenceProvenance[value.attr]


def _assert_terminal_contract(
    error: AggregationError,
    *,
    condition: AggregationPreconditionCondition,
    facts: dict[str, str | int | bool | Decimal],
) -> None:
    assert isinstance(error, TerminalPreconditionErrorMixin)
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition.value
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.missing_argument_names == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.condition_id == condition.value
    assert evidence.evidence_id == f"{condition.value}.observation"
    assert evidence.provenance is ActionEvidenceProvenance.APPLICATION_STATE
    assert dict(evidence.values) == facts


def test_aggregation_terminal_attachment_totality_is_exact_and_mutation_sensitive() -> None:
    observed = _aggregation_carriers()

    assert set(observed) == set(_AGGREGATION_FAILURE_TOTALITY)
    for key, carrier in observed.items():
        expected = _AGGREGATION_FAILURE_TOTALITY[key]
        precondition = _precondition(carrier)
        assert _condition(precondition) is expected.condition
        assert _fact_expressions(precondition) == expected.facts
        assert _helper_provenance() is expected.provenance
        assert _normalized_outcome(precondition) is expected.outcome


def test_aggregation_preconditions_use_the_shared_mixin_and_single_canonical_constructor() -> None:
    assert issubclass(AggregationError, TerminalPreconditionErrorMixin)
    preconditions_module = __import__("cadrumo.application.aggregation._preconditions", fromlist=["*"])
    errors_module = __import__("cadrumo.application.aggregation.errors", fromlist=["*"])
    modules = (*_ATTACHMENT_MODULES, preconditions_module, errors_module)
    for module in modules:
        tree = ast.parse(inspect.getsource(module))
        constructed = {
            _call_name(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _call_name(node.func) in {"PreconditionVerdict", "ConditionEvidence"}
        }
        assert not constructed, module.__name__

    delegates = [
        module.__name__
        for module in modules
        for node in ast.walk(ast.parse(inspect.getsource(module)))
        if isinstance(node, ast.Call) and _call_name(node.func) == "no_action_precondition_verdict"
    ]
    assert delegates == [preconditions_module.__name__]


def test_unsupported_modelo_has_an_exact_application_state_operator_decision_verdict() -> None:
    with pytest.raises(AggregationUnsupportedModeloError) as raised:
        provider_for_modelo(" 347 ")

    _assert_terminal_contract(
        raised.value,
        condition=AggregationPreconditionCondition.PER_MODELO_MODELO_SUPPORTED,
        facts={"modelo": " 347 ", "supported_modelos": "|".join(_SUPPORTED_PER_MODELO_MODELOS)},
    )


@pytest.mark.parametrize("refusal", ["uncovered_deduction", "unmatched_ledger"])
def test_invoice_ledger_refusals_have_exact_application_state_operator_decision_verdicts(
    refusal: str,
) -> None:
    context = CalculationSourceContext(
        bucket_id="operator",
        modelo="303",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        revision=bundled_authority().snapshot("303", filing_year=2025, period="1T").revision,
    )
    expected_facts: dict[str, str | int | bool | Decimal]
    if refusal == "uncovered_deduction":
        invoice = Invoice.model_validate(
            {
                "kind": InvoiceKind.RECEIVED,
                "invoice_number": "INV-UNLINKED",
                "issued_at": date(2025, 4, 1),
                "counterparty_name": "Proveedor SL",
                "counterparty_tax_id": "B12345674",
                "counterparty_country": "ES",
                "base_total": Decimal("100.00"),
                "iva_total": Decimal("21.00"),
                "grand_total": Decimal("121.00"),
                "currency": "EUR",
                "lines": (
                    InvoiceLine(
                        description="Servicios profesionales",
                        quantity=Decimal("1"),
                        unit_price=Decimal("100.00"),
                        subtotal=Decimal("100.00"),
                        iva_rate=IvaRate.RATE_21,
                        iva_amount=Decimal("21.00"),
                    ),
                ),
                "payment_status": PaymentStatus.PAID,
            },
        )
        screened = modelo_bindings_module._ScreenedInvoiceIva(deduction_authority_missing=(invoice,))
        expected_facts = {
            "modelo": "303",
            "filing_year": "2025",
            "period": "1T",
            "source_kind": "ledger_iva_aggregation",
            "invoice_count": 1,
            "missing_binding_count": 0,
        }
    else:
        screened = modelo_bindings_module._ScreenedInvoiceIva(
            observations=(
                IvaLedgerObservation(
                    ledger_id="invoice-unmatched",
                    transaction_date=date(2025, 4, 1),
                    category=IvaCategory.DOMESTIC_GENERAL,
                    rate_kind=IvaRateKind.GENERAL,
                    flow_direction=derive_flow_for_classification(
                        category=IvaCategory.DOMESTIC_GENERAL,
                        invoice_direction=InvoiceKind.ISSUED,
                    ),
                    cash_accounting_treatment=IvaCashAccountingTreatment.NONE,
                    base_amount=Decimal("100.00"),
                    iva_amount=Decimal("21.00"),
                    observation_role=IvaLedgerObservationRole.SETTLEMENT,
                ),
            ),
            invoice_ids=("invoice-unmatched",),
        )
        expected_facts = {
            "modelo": "303",
            "filing_year": "2025",
            "period": "1T",
            "source_kind": "ledger_iva_aggregation",
            "invoice_count": 1,
            "missing_binding_count": 1,
        }
    with pytest.raises(AggregationValidationError) as raised:
        _raise_if_screened_invoice_iva_would_be_silent(
            context=context,
            screened_bindings=modelo_bindings_module._INVOICE_LEDGER_SCREEN_BINDINGS["303"],
            screened=screened,
            transaction_binding_values={},
            prorrata_apportionment=None,
        )

    _assert_terminal_contract(
        raised.value,
        condition=AggregationPreconditionCondition.INVOICE_LEDGER_COMPLETE,
        facts=expected_facts,
    )


def test_missing_retenciones_observations_has_an_exact_application_state_operator_decision_verdict(
    tmp_path: Path,
) -> None:
    context = CalculationSourceContext(
        bucket_id="operator",
        modelo="111",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision=ModeloRevision(
            id="test-111-terminal-preconditions",
            localization_key="test.schema.revision.test-111-terminal-preconditions.label",
            valid_from=date(2026, 1, 1),
            period_selector=PeriodSelector(year_from=2026, periods=("1T",)),
            legal_refs=("ley-35-2006:art-99",),
            source_refs=("test-terminal-preconditions",),
            bindings=(
                DataBindingDefinition(
                    id="test-111-retenciones-binding",
                    source=BindingSourceKind.RETENCIONES_AGGREGATION,
                    selector={
                        "target_casilla_id": "decl.total-perceptores",
                        "fact": "perceptor_count_distinct",
                    },
                    legal_refs=("ley-35-2006:art-99",),
                    source_refs=("test-terminal-preconditions",),
                ),
            ),
        ),
    )

    with isolated_runtime_profile(tmp_path=tmp_path), pytest.raises(AggregationValidationError) as raised:
        RetencionesAggregationSourceResolver(retencion_repository=RetencionObservationRepository()).resolve(context)

    _assert_terminal_contract(
        raised.value,
        condition=AggregationPreconditionCondition.RETENCIONES_OBSERVATIONS_PRESENT,
        facts={
            "modelo": "111",
            "filing_year": "2026",
            "period": "1T",
            "source_kind": "retenciones_aggregation",
        },
    )
