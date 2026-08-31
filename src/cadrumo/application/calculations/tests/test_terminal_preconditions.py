"""Exact terminal-precondition proof for calculation safety refusals."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import ModuleType
from typing import TYPE_CHECKING

import pytest

from ....core import ObservedHeaderFact
from ....core.result_disposition import ResultDisposition
from ....core.modelo import Modelo
from ....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.period import Period
from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import TerminalPreconditionErrorMixin
from ....core.resources import bundled_path
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....domain.calculations.registry.loader import load_registry_tree
from ....domain.calculations.registry.temporal import select_revision
from ....domain.iva_compensation.filed_derivation import M303CompensationAvailableDerivation, M303_COMPENSATION_AVAILABLE_CASILLA, M303_COMPENSATION_GENERADA_CASILLA, M303_COMPENSATION_POSTERIOR_CASILLA, M303_COMPENSATION_RESULTADO_CASILLA
from ....tests.secure_sql import isolated_runtime_profile
from .. import _m303_carry_ingress as m303_module
from .. import errors as errors_module
from .. import observations_repository as observations_module
from .._m303_carry_ingress import M303CarryIngressError, _resolve_available_compensation_formula_id
from ..errors import CalculationRefusalPrecondition, ObservationEvidenceDisplacementError
from ..observations_repository import (
    CalculationObservationRepository,
    ObservationSourceKind,
    ResultDispositionProjection,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED_AT = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")


@dataclass(frozen=True)
class _CarrierContract:
    condition: CalculationRefusalPrecondition
    facts: tuple[tuple[str, str], ...]
    provenance: ActionEvidenceProvenance
    outcome: NoRecoveryOutcome


def _contract(condition: CalculationRefusalPrecondition, facts: tuple[tuple[str, str], ...]) -> _CarrierContract:
    return _CarrierContract(
        condition=condition,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.SAFETY,
    )


# Every terminal attachment in the two calculation producers. The source
# expressions are retained rather than reduced to keys so a polarity/value
# mutation cannot pass the proof accidentally.
_TERMINAL_CARRIER_TOTALITY: dict[str, _CarrierContract] = {
    "_m303_carry_ingress:_resolve_result_disposition:M303CarryIngressError:1": _contract(
        CalculationRefusalPrecondition.M303_CARRY_DISPOSITION_CONSISTENT,
        (
            ("source_kind", "str(envelope.source_kind)"),
            ("typed_disposition", "str(supplied.disposition)"),
            ("header_disposition", "str(header_projection.disposition)"),
        ),
    ),
    "_m303_carry_ingress:_resolve_result_disposition:M303CarryIngressError:2": _contract(
        CalculationRefusalPrecondition.M303_CARRY_DISPOSITION_CONSISTENT,
        (
            ("source_kind", "str(envelope.source_kind)"),
            ("typed_disposition", "str(supplied.disposition)"),
            ("header_disposition", "str(header_projection.disposition)"),
        ),
    ),
    "_m303_carry_ingress:_assert_result_sign_compatible:M303CarryIngressError:1": _contract(
        CalculationRefusalPrecondition.M303_CARRY_DISPOSITION_CONSISTENT,
        (
            ("disposition", "str(disposition)"),
            ("resultado", "str(resultado)"),
            ("casilla_id", "str(M303_COMPENSATION_RESULTADO_CASILLA)"),
        ),
    ),
    "_m303_carry_ingress:_require_supplied_pair_matches_derivation:M303CarryIngressError:1": _contract(
        CalculationRefusalPrecondition.M303_CARRY_DERIVATION_CONSISTENT,
        (
            ("supplied_available", "str(current_available)"),
            ("derived_available", "str(derivation.available)"),
            ("basis", "str(derivation.basis)"),
        ),
    ),
    "_m303_carry_ingress:_require_supplied_pair_matches_derivation:M303CarryIngressError:2": _contract(
        CalculationRefusalPrecondition.M303_CARRY_DERIVATION_CONSISTENT,
        (
            ("supplied_available", "str(current_available)"),
            ("supplied_generated", "str(current_generated)"),
            ("derived_generated", "str(derivation.generated)"),
            ("basis", "str(derivation.basis)"),
        ),
    ),
    "_m303_carry_ingress:_resolve_available_compensation_formula_id:M303CarryIngressError:1": _contract(
        CalculationRefusalPrecondition.M303_CARRY_MATCHES_REGISTRY_FORMULA,
        (
            ("formula_id", "str(formula.id)"),
            ("derivation_operands", "','.join((str(item) for item in derivation.operand_refs))"),
            ("registry_operands", "','.join((str(item) for item in expected_operands))"),
        ),
    ),
    "observations_repository:_refuse_official_evidence_displacement:ObservationEvidenceDisplacementError:1": _contract(
        CalculationRefusalPrecondition.OFFICIAL_EVIDENCE_PRESERVED,
        (
            ("modelo", "str(observation.modelo)"),
            ("filing_year", "str(observation.filing_year)"),
            ("period", "str(observation.period)"),
            ("existing_source_kind", "existing.source_kind.value"),
            ("incoming_source_kind", "payload.source_kind.value"),
        ),
    ),
    "observations_repository:_refuse_official_evidence_displacement:ObservationEvidenceDisplacementError:2": _contract(
        CalculationRefusalPrecondition.OFFICIAL_EVIDENCE_PRESERVED,
        (
            ("modelo", "str(observation.modelo)"),
            ("filing_year", "str(observation.filing_year)"),
            ("period", "str(observation.period)"),
            ("existing_source_kind", "existing.source_kind.value"),
            ("incoming_source_kind", "payload.source_kind.value"),
        ),
    ),
}

_TERMINAL_PRODUCER_MODULES: tuple[ModuleType, ...] = (m303_module, observations_module)


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _keyword(call: ast.Call, name: str) -> ast.expr:
    value = next((keyword.value for keyword in call.keywords if keyword.arg == name), None)
    assert value is not None, f"missing {name}"
    return value


def _function_assignments(function: ast.FunctionDef) -> dict[str, ast.expr]:
    assignments: dict[str, ast.expr] = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
    return assignments


def _precondition_builder(value: ast.expr, assignments: dict[str, ast.expr]) -> ast.Call:
    if isinstance(value, ast.Name):
        value = assignments[value.id]
    assert isinstance(value, ast.Call)
    assert _call_name(value.func) == "calculation_no_recovery_verdict"
    return value


def _condition(builder: ast.Call) -> CalculationRefusalPrecondition:
    assert builder.args
    value = builder.args[0]
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == "CalculationRefusalPrecondition"
    return CalculationRefusalPrecondition[value.attr]


def _fact_expressions(builder: ast.Call) -> tuple[tuple[str, str], ...]:
    facts = _keyword(builder, "facts")
    assert isinstance(facts, ast.Dict)
    values: list[tuple[str, str]] = []
    for key, value in zip(facts.keys, facts.values, strict=True):
        assert isinstance(key, ast.Constant) and isinstance(key.value, str)
        values.append((key.value, ast.unparse(value)))
    return tuple(values)


def _terminal_carriers() -> dict[str, ast.Call]:
    carriers: dict[str, ast.Call] = {}
    error_names = {"M303CarryIngressError", "ObservationEvidenceDisplacementError"}
    for module in _TERMINAL_PRODUCER_MODULES:
        tree = ast.parse(inspect.getsource(module))
        for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
            assignments = _function_assignments(function)
            occurrences: dict[str, int] = {}
            calls = sorted(
                (
                    node
                    for node in ast.walk(function)
                    if isinstance(node, ast.Call)
                    and _call_name(node.func) in error_names
                    and any(keyword.arg == "precondition_verdict" for keyword in node.keywords)
                ),
                key=lambda node: node.lineno,
            )
            for call in calls:
                error_name = _call_name(call.func)
                assert error_name is not None
                occurrences[error_name] = occurrences.get(error_name, 0) + 1
                _precondition_builder(_keyword(call, "precondition_verdict"), assignments)
                key = (
                    f"{module.__name__.rsplit('.', maxsplit=1)[-1]}:{function.name}:"
                    f"{error_name}:{occurrences[error_name]}"
                )
                assert key not in carriers, f"duplicate calculation terminal carrier {key}"
                carriers[key] = call
    return carriers


def _assert_exact_terminal_contract(
    error: M303CarryIngressError | ObservationEvidenceDisplacementError,
    *,
    condition: CalculationRefusalPrecondition,
    facts: dict[str, str],
) -> None:
    assert isinstance(error, TerminalPreconditionErrorMixin)
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition.value
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.missing_argument_names == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.SAFETY
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.condition_id == condition.value
    assert evidence.evidence_id == f"{condition.value}.observation"
    assert evidence.provenance is ActionEvidenceProvenance.RUNTIME_OBSERVATION
    assert dict(evidence.values) == facts


def _m303_observation(values: dict[CasillaId, Decimal]) -> RegistryModeloObservation:
    observations = tuple(
        CasillaObservation(
            casilla_id=casilla_id,
            value=value,
            formula_id=None,
            operand_refs=(),
            operand_casilla_refs=(),
            operand_values=(),
            legal_refs=("ley-37-1992:art-21",),
            source_refs=("aeat-iva-2025",),
        )
        for casilla_id, value in values.items()
    )
    return RegistryModeloObservation(
        modelo=Modelo.M303.value,
        filing_year=_PERIOD.filing_year,
        period=_PERIOD.registry_token,
        observations=observations,
    )


def _header(disposition: ResultDisposition) -> ObservedHeaderFact:
    return ObservedHeaderFact(
        header_key="declaration_type",
        value=disposition.value,
        source_artefact_kind="submitted_file",
        source_locator=f"m303-submitted-file:{disposition.value}",
    )


def _plain_m303_observation() -> RegistryModeloObservation:
    return _m303_observation(
        {
            M303_COMPENSATION_POSTERIOR_CASILLA: Decimal("7.00"),
            M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-20.00"),
        }
    )


def _seed_official_observation(repository: CalculationObservationRepository) -> None:
    repository.save(
        repository.prepare_observation_envelope(
            _plain_m303_observation(),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_CAPTURED_AT,
            source_metadata={"aeat_expediente_id": "202530300000001Z"},
        )
    )


def test_calculation_terminal_carrier_totality_is_exact_and_mutation_sensitive() -> None:
    observed = _terminal_carriers()

    assert set(observed) == set(_TERMINAL_CARRIER_TOTALITY)
    for key, carrier in observed.items():
        expected = _TERMINAL_CARRIER_TOTALITY[key]
        function = next(
            node
            for node in ast.walk(
                ast.parse(
                    inspect.getsource(
                        next(
                            module
                            for module in _TERMINAL_PRODUCER_MODULES
                            if module.__name__.endswith(key.split(":")[0])
                        )
                    )
                )
            )
            if isinstance(node, ast.FunctionDef) and node.name == key.split(":")[1]
        )
        builder = _precondition_builder(_keyword(carrier, "precondition_verdict"), _function_assignments(function))
        assert _condition(builder) is expected.condition
        assert _fact_expressions(builder) == expected.facts
        assert expected.provenance is ActionEvidenceProvenance.RUNTIME_OBSERVATION
        assert expected.outcome is NoRecoveryOutcome.SAFETY
        assert not any(keyword.arg == "outcome" for keyword in builder.keywords)


def test_calculation_terminal_preconditions_have_one_canonical_no_action_authority() -> None:
    modules = (*_TERMINAL_PRODUCER_MODULES, errors_module)
    for module in modules:
        tree = ast.parse(inspect.getsource(module))
        constructed = {
            _call_name(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _call_name(node.func) in {"PreconditionVerdict", "ConditionEvidence"}
        }
        assert not constructed, module.__name__

    direct_canonical_calls = {
        module.__name__
        for module in modules
        for node in ast.walk(ast.parse(inspect.getsource(module)))
        if isinstance(node, ast.Call) and _call_name(node.func) == "no_action_precondition_verdict"
    }
    assert direct_canonical_calls == {errors_module.__name__}

    helper = next(
        node
        for node in ast.parse(inspect.getsource(errors_module)).body
        if isinstance(node, ast.FunctionDef) and node.name == "calculation_no_recovery_verdict"
    )
    defaults = {
        argument.arg: default
        for argument, default in zip(helper.args.kwonlyargs, helper.args.kw_defaults, strict=True)
        if default is not None
    }
    outcome_default = defaults["outcome"]
    assert isinstance(outcome_default, ast.Attribute)
    assert ast.unparse(outcome_default) == "NoRecoveryOutcome.SAFETY"
    canonical = next(
        node
        for node in ast.walk(helper)
        if isinstance(node, ast.Call) and _call_name(node.func) == "no_action_precondition_verdict"
    )
    assert ast.unparse(_keyword(canonical, "provenance")) == "ActionEvidenceProvenance.RUNTIME_OBSERVATION"
    assert ast.unparse(_keyword(canonical, "outcome")) == "outcome"


def test_m303_disposition_contradiction_has_an_exact_safety_verdict(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        with pytest.raises(M303CarryIngressError) as raised:
            repository.prepare_observation_envelope(
                _plain_m303_observation(),
                source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
                captured_at=_CAPTURED_AT,
                source_headers=(_header(ResultDisposition.COMPENSACION),),
                result_disposition=ResultDispositionProjection(
                    disposition=ResultDisposition.DEVOLUCION,
                    provenance_kind="source_header",
                    provenance_locator="m303-submitted-file:devolucion",
                ),
                normalize_m303_carry=True,
            )

    _assert_exact_terminal_contract(
        raised.value,
        condition=CalculationRefusalPrecondition.M303_CARRY_DISPOSITION_CONSISTENT,
        facts={
            "source_kind": ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE.value,
            "typed_disposition": ResultDisposition.DEVOLUCION.value,
            "header_disposition": ResultDisposition.COMPENSACION.value,
        },
    )


def test_m303_derived_carry_contradiction_has_an_exact_safety_verdict(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        with pytest.raises(M303CarryIngressError) as raised:
            repository.prepare_observation_envelope(
                _m303_observation(
                    {
                        M303_COMPENSATION_POSTERIOR_CASILLA: Decimal("7.00"),
                        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-20.00"),
                        M303_COMPENSATION_AVAILABLE_CASILLA: Decimal("99.00"),
                    }
                ),
                source_kind=ObservationSourceKind.APP_FILING,
                captured_at=_CAPTURED_AT,
                result_disposition=ResultDispositionProjection(
                    disposition=ResultDisposition.COMPENSACION,
                    provenance_kind="app_filing",
                    provenance_locator="filed-revision:2025:1T",
                ),
                normalize_m303_carry=True,
            )

    _assert_exact_terminal_contract(
        raised.value,
        condition=CalculationRefusalPrecondition.M303_CARRY_DERIVATION_CONSISTENT,
        facts={"supplied_available": "99.00", "derived_available": "27.00", "basis": "resultado"},
    )


def test_m303_registry_formula_contradiction_has_an_exact_safety_verdict() -> None:
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(candidate for candidate in modelos if candidate.id == Modelo.M303.value)
    revision = select_revision(
        modelo,
        filing_year=_PERIOD.filing_year,
        period=_PERIOD.registry_token,
    )
    formula = next(item for item in revision.formulas if item.target_casilla_id == M303_COMPENSATION_AVAILABLE_CASILLA)
    contradictory_derivation = M303CompensationAvailableDerivation(
        available=Decimal("27.00"),
        generated=Decimal("20.00"),
        basis="generated",
        operand_refs=(M303_COMPENSATION_POSTERIOR_CASILLA, M303_COMPENSATION_RESULTADO_CASILLA),
        operand_values=(Decimal("7.00"), Decimal("20.00")),
    )

    with pytest.raises(M303CarryIngressError) as raised:
        _resolve_available_compensation_formula_id(revision, contradictory_derivation)

    _assert_exact_terminal_contract(
        raised.value,
        condition=CalculationRefusalPrecondition.M303_CARRY_MATCHES_REGISTRY_FORMULA,
        facts={
            "formula_id": str(formula.id),
            "derivation_operands": ",".join(
                (str(M303_COMPENSATION_POSTERIOR_CASILLA), str(M303_COMPENSATION_RESULTADO_CASILLA))
            ),
            "registry_operands": ",".join(
                (str(M303_COMPENSATION_POSTERIOR_CASILLA), str(M303_COMPENSATION_GENERADA_CASILLA))
            ),
        },
    )


@pytest.mark.parametrize("source_kind", (ObservationSourceKind.OPERATOR_MANUAL, ObservationSourceKind.APP_FILING))
def test_both_real_observation_repository_displacement_branches_have_exact_safety_verdicts(
    tmp_path: Path,
    source_kind: ObservationSourceKind,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        _seed_official_observation(repository)

        with pytest.raises(ObservationEvidenceDisplacementError) as raised:
            repository.prepare_observation_envelope(
                _plain_m303_observation(),
                source_kind=source_kind,
                captured_at=_CAPTURED_AT + timedelta(days=1),
            )

    _assert_exact_terminal_contract(
        raised.value,
        condition=CalculationRefusalPrecondition.OFFICIAL_EVIDENCE_PRESERVED,
        facts={
            "modelo": Modelo.M303.value,
            "filing_year": str(_PERIOD.filing_year),
            "period": _PERIOD.registry_token,
            "existing_source_kind": ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE.value,
            "incoming_source_kind": source_kind.value,
        },
    )
