"""Complete terminal-precondition contracts for aggregation refusals."""

from __future__ import annotations

import ast
import inspect
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from types import ModuleType
from typing import override

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ....core.aggregation import AggregationCaptureKind
from ....core.errors.hierarchy import TerminalPreconditionErrorMixin
from ....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....tests.terminal_precondition_ast import call_name, fact_expressions
from .. import errors as errors_module
from .. import modelo_bindings_invoice_iva, preconditions
from .. import modelo_bindings_retenciones as modelo_bindings_retenciones_module
from .. import service as service_module
from ..errors import AggregationError, AggregationUnsupportedModeloError, RetencionesWindowEmptyError
from ..modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from ..preconditions import AggregationPreconditionCondition, aggregation_no_recovery_verdict
from ..retencion_observations_repository import RetencionObservationPorts
from ..retenciones import RetencionObservation
from ..service import provider_for_modelo, supported_per_modelo_modelos
from ..source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


@dataclass(frozen=True)
class _CarrierContract:
    condition: AggregationPreconditionCondition
    facts: tuple[tuple[str, str], ...]
    provenance: ActionEvidenceProvenance
    outcome: NoRecoveryOutcome


class _EmptyRetencionObservationRepository:
    """Application-port fake for the terminal empty-observation precondition."""

    def load_observations(self, modelo: str, period: Period) -> tuple[RetencionObservation, ...]:
        return ()

    def load_annual_source_observations(self, source_modelo: str, filing_year: int) -> tuple[RetencionObservation, ...]:
        del source_modelo, filing_year
        return ()

    def load_source_observations_through_year(
        self,
        source_modelo: str,
        last_filing_year: int,
    ) -> tuple[RetencionObservation, ...]:
        del source_modelo, last_filing_year
        return ()

    def replace_observations(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observations: Sequence[RetencionObservation],
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        del modelo, filing_year, period, observations, source_kind, captured_at, source_metadata


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


# Complete source-level contract for the dispatch and retenciones terminal
# attachments.  Fact values are AST expressions rather than just keys, so a
# dynamic calculation or boolean polarity cannot drift.
_AGGREGATION_FAILURE_TOTALITY: dict[str, _CarrierContract] = {
    "service:provider_for_modelo:1": _contract(
        AggregationPreconditionCondition.PER_MODELO_MODELO_SUPPORTED,
        (("modelo", "modelo"), ("supported_modelos", "'|'.join(supported)")),
    ),
    "modelo_bindings_retenciones:_empty_window_refusal:1": _contract(
        AggregationPreconditionCondition.RETENCIONES_OBSERVATIONS_PRESENT,
        (
            ("modelo", "str(context.modelo)"),
            ("filing_year", "str(context.filing_year)"),
            ("period", "context.period.registry_token"),
            ("source_kind", "'retenciones_aggregation'"),
        ),
    ),
}

_ATTACHMENT_MODULES: tuple[ModuleType, ...] = (
    service_module,
    modelo_bindings_invoice_iva,
    modelo_bindings_retenciones_module,
)


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
                if call_name(node.func) in {
                    "AggregationUnsupportedModeloError",
                    "AggregationValidationError",
                    "RetencionesWindowEmptyError",
                }:
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
    assert call_name(value.func) == "aggregation_no_recovery_verdict"
    return value


def _condition(precondition: ast.Call) -> AggregationPreconditionCondition:
    value = precondition.args[0]
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == "AggregationPreconditionCondition"
    return AggregationPreconditionCondition[value.attr]


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
    tree = ast.parse(inspect.getsource(preconditions))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and call_name(node.func) == "no_action_precondition_verdict"
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
        assert fact_expressions(precondition) == expected.facts
        assert _helper_provenance() is expected.provenance
        assert _normalized_outcome(precondition) is expected.outcome


def test_aggregation_preconditions_use_the_shared_mixin_and_single_canonical_constructor() -> None:
    assert issubclass(AggregationError, TerminalPreconditionErrorMixin)
    modules = (*_ATTACHMENT_MODULES, preconditions, errors_module)
    for module in modules:
        tree = ast.parse(inspect.getsource(module))
        constructed = {
            call_name(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and call_name(node.func) in {"PreconditionVerdict", "ConditionEvidence"}
        }
        assert not constructed, module.__name__

    delegates = [
        module.__name__
        for module in modules
        for node in ast.walk(ast.parse(inspect.getsource(module)))
        if isinstance(node, ast.Call) and call_name(node.func) == "no_action_precondition_verdict"
    ]
    assert delegates == [preconditions.__name__]


def test_unsupported_modelo_has_an_exact_application_state_operator_decision_verdict() -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        with pytest.raises(AggregationUnsupportedModeloError) as raised:
            provider_for_modelo(" 347 ", operation=_authority_operation_for_test)

        _assert_terminal_contract(
            raised.value,
            condition=AggregationPreconditionCondition.PER_MODELO_MODELO_SUPPORTED,
            facts={
                "modelo": " 347 ",
                "supported_modelos": "|".join(supported_per_modelo_modelos(operation=_authority_operation_for_test)),
            },
        )


def test_missing_retenciones_observations_has_an_exact_application_state_operator_decision_verdict() -> None:
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
                BindingDefinition(
                    id="test-111-retenciones-binding",
                    provider={
                        "kind": "retenciones_aggregation",
                        **{
                            "target_casilla_id": "decl.total-perceptores",
                            "fact": "perceptor_count_distinct",
                        },
                    },
                    value={"data_type": "money", "channel": "decimal"},
                    legal_refs=("ley-35-2006:art-99",),
                    source_refs=("test-terminal-preconditions",),
                ),
            ),
        ),
    )

    with pytest.raises(RetencionesWindowEmptyError) as raised:
        RetencionesAggregationSourceResolver(
            ports=RetencionObservationPorts(repository=_EmptyRetencionObservationRepository()),
        ).resolve(context)

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
