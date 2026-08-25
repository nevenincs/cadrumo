"""Complete terminal-precondition contracts for wizard refusal producers."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from ....core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.errors import TerminalPreconditionErrorMixin
from ... import user_profile as user_profile_module
from ... import workflow as workflow_module
from ...user_profile import ProfileRegistrationError
from ...workflow import WorkflowState
from .. import _commands as commands_module
from .. import _persistence as persistence_module
from .. import _status as status_module
from .._catalogue import SETUP_FLOW
from .._commands import _require_profile_name, _resolve_profile_id_for_mode, _run_full_flow, _run_patch_edit
from .._errors import (
    WizardEditUnsupportedConsoleError,
    WizardError,
    WizardMissingFlagError,
    WizardPreconditionCondition,
    WizardValidationError,
)
from .._status import WizardStatusError, _next_wizard_action, load_active_taxpayer_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True)
class _CarrierContract:
    condition: WizardPreconditionCondition
    facts: tuple[tuple[str, str], ...]
    provenance: ActionEvidenceProvenance
    outcome: NoRecoveryOutcome


def _contract(
    condition: WizardPreconditionCondition,
    facts: tuple[tuple[str, str], ...],
    provenance: ActionEvidenceProvenance,
    outcome: NoRecoveryOutcome,
) -> _CarrierContract:
    return _CarrierContract(condition, facts, provenance, outcome)


# This exact source-level census includes only operator-reachable status and
# command-boundary refusals. Compiler and widget-validation invariants remain
# outside the census because they do not carry terminal operator outcomes.
_WIZARD_FAILURE_TOTALITY: dict[str, _CarrierContract] = {
    "_status:load_active_taxpayer_profile:WizardStatusError:1": _contract(
        WizardPreconditionCondition.ACTIVE_PROFILE_AVAILABLE,
        (("active_profile_record_available", "False"),),
        ActionEvidenceProvenance.APPLICATION_STATE,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    "_status:load_active_taxpayer_profile:WizardStatusError:2": _contract(
        WizardPreconditionCondition.ACTIVE_PROFILE_TAX_ID_DECLARED,
        (("active_profile_tax_id_declared", "False"),),
        ActionEvidenceProvenance.APPLICATION_STATE,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    "_commands:_run_patch_edit:WizardMissingFlagError:1": _contract(
        WizardPreconditionCondition.FILING_BASELINE_COMPLETE,
        (("filing_baseline_complete", "False"), ("missing_flag_count", "len(missing_baseline)")),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    "_commands:_run_full_flow:WizardMissingFlagError:1": _contract(
        WizardPreconditionCondition.REQUIRED_FLAGS_SUPPLIED,
        (("required_flags_supplied", "False"), ("missing_flag_count", "len(missing)")),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    "_commands:_run_full_flow:WizardEditUnsupportedConsoleError:1": _contract(
        WizardPreconditionCondition.INTERACTIVE_CONSOLE_AVAILABLE,
        (("interactive_console_available", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_commands:_run_full_flow:WizardUnsupportedConsoleError:1": _contract(
        WizardPreconditionCondition.INTERACTIVE_CONSOLE_AVAILABLE,
        (("interactive_console_available", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_commands:_run_full_flow:WizardMissingFlagError:2": _contract(
        WizardPreconditionCondition.FILING_BASELINE_COMPLETE,
        (("filing_baseline_complete", "False"), ("missing_flag_count", "len(missing_baseline)")),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    "_commands:_require_profile_name:WizardMissingFlagError:1": _contract(
        WizardPreconditionCondition.PROFILE_NAME_SUPPLIED,
        (("profile_name_supplied", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    "_commands:_resolve_profile_id_for_mode:WizardValidationError:1": _contract(
        WizardPreconditionCondition.PROFILE_LABEL_AVAILABLE,
        (("profile_registration_available", "False"),),
        ActionEvidenceProvenance.APPLICATION_STATE,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    "_commands:_resolve_profile_id_for_mode:WizardMissingFlagError:1": _contract(
        WizardPreconditionCondition.PROFILE_NAME_SUPPLIED,
        (("profile_name_supplied", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
}

_WIZARD_PRODUCER_MODULES: tuple[ModuleType, ...] = (status_module, commands_module)


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _wizard_carriers() -> dict[str, ast.Call]:
    carriers: dict[str, ast.Call] = {}
    error_names = {
        "WizardStatusError",
        "WizardMissingFlagError",
        "WizardValidationError",
        "WizardEditUnsupportedConsoleError",
        "WizardUnsupportedConsoleError",
    }
    for module in _WIZARD_PRODUCER_MODULES:
        tree = ast.parse(inspect.getsource(module))

        class Visitor(ast.NodeVisitor):
            def __init__(self, module_name: str) -> None:
                self.module_name = module_name
                self.owner = "<module>"
                self.occurrences: dict[tuple[str, str], int] = {}

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                prior_owner = self.owner
                self.owner = node.name if prior_owner == "<module>" else f"{prior_owner}.{node.name}"
                self.generic_visit(node)
                self.owner = prior_owner

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                prior_owner = self.owner
                self.owner = node.name if prior_owner == "<module>" else f"{prior_owner}.{node.name}"
                self.generic_visit(node)
                self.owner = prior_owner

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self.visit_FunctionDef(node)

            def visit_Call(self, node: ast.Call) -> None:
                error_name = _call_name(node.func)
                if error_name in error_names:
                    verdict = next(
                        (keyword.value for keyword in node.keywords if keyword.arg == "precondition_verdict"),
                        None,
                    )
                    if verdict is not None:
                        identity = (self.owner, error_name)
                        occurrence = self.occurrences.get(identity, 0) + 1
                        self.occurrences[identity] = occurrence
                        key = f"{self.module_name}:{self.owner}:{error_name}:{occurrence}"
                        assert key not in carriers, f"duplicate wizard terminal carrier {key}"
                        carriers[key] = node
                self.generic_visit(node)

        Visitor(module.__name__.rsplit(".", maxsplit=1)[-1]).visit(tree)
    return carriers


def _keyword(call: ast.Call, name: str) -> ast.expr:
    value = next((keyword.value for keyword in call.keywords if keyword.arg == name), None)
    assert value is not None, f"missing {name}"
    return value


def _precondition(call: ast.Call) -> ast.Call:
    value = _keyword(call, "precondition_verdict")
    assert isinstance(value, ast.Call)
    assert _call_name(value.func) == "wizard_no_action_verdict"
    return value


def _condition(precondition: ast.Call) -> WizardPreconditionCondition:
    value = _keyword(precondition, "condition")
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == "WizardPreconditionCondition"
    return WizardPreconditionCondition[value.attr]


def _fact_expressions(precondition: ast.Call) -> tuple[tuple[str, str], ...]:
    facts = _keyword(precondition, "facts")
    assert isinstance(facts, ast.Dict)
    values: list[tuple[str, str]] = []
    for key, value in zip(facts.keys, facts.values, strict=True):
        assert isinstance(key, ast.Constant) and isinstance(key.value, str)
        values.append((key.value, ast.unparse(value)))
    return tuple(values)


def _enum_keyword(
    precondition: ast.Call,
    name: str,
    enum: type[ActionEvidenceProvenance] | type[NoRecoveryOutcome],
):
    value = _keyword(precondition, name)
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == enum.__name__
    return enum[value.attr]


def _assert_terminal_contract(
    error: WizardError,
    *,
    condition: WizardPreconditionCondition,
    facts: dict[str, str | int | bool],
    provenance: ActionEvidenceProvenance,
    outcome: NoRecoveryOutcome,
) -> None:
    assert isinstance(error, TerminalPreconditionErrorMixin)
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition.value
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.missing_argument_names == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is outcome
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.condition_id == condition.value
    assert evidence.evidence_id == f"{condition.value}.observation"
    assert evidence.provenance is provenance
    assert dict(evidence.values) == facts


def test_wizard_terminal_carrier_totality_is_exact_and_mutation_sensitive() -> None:
    observed = _wizard_carriers()

    assert set(observed) == set(_WIZARD_FAILURE_TOTALITY)
    for key, carrier in observed.items():
        expected = _WIZARD_FAILURE_TOTALITY[key]
        precondition = _precondition(carrier)
        assert _condition(precondition) is expected.condition
        assert _fact_expressions(precondition) == expected.facts
        assert _enum_keyword(precondition, "provenance", ActionEvidenceProvenance) is expected.provenance
        assert _enum_keyword(precondition, "outcome", NoRecoveryOutcome) is expected.outcome


def test_wizard_preconditions_delegate_to_one_public_constructor_without_local_command_prose() -> None:
    errors_module = __import__("cadrumo.application.wizard._errors", fromlist=["*"])
    for module in (*_WIZARD_PRODUCER_MODULES, errors_module):
        tree = ast.parse(inspect.getsource(module))
        constructed = {
            _call_name(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _call_name(node.func) in {"PreconditionVerdict", "ConditionEvidence"}
        }
        assert not constructed, module.__name__

    delegates = [
        module.__name__
        for module in (*_WIZARD_PRODUCER_MODULES, errors_module)
        for node in ast.walk(ast.parse(inspect.getsource(module)))
        if isinstance(node, ast.Call) and _call_name(node.func) == "no_action_precondition_verdict"
    ]
    assert delegates == [errors_module.__name__]

    tree = ast.parse(inspect.getsource(status_module))
    next_action = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_next_wizard_action"
    )
    literal_strings = {
        node.value.lower()
        for node in ast.walk(next_action)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not any("aeat " in value for value in literal_strings)
    assert "operator.profile.create" not in literal_strings


def test_wizard_production_has_no_executable_profile_create_recommendation_or_save_resume_emitter() -> None:
    """Custody has retired the wizard's create/checkpoint continuation path."""
    wizard_root = Path(__file__).parent.parent
    production_sources = {path.name: path.read_text(encoding="utf-8") for path in wizard_root.glob("*.py")}

    executable_recommendations = {
        filename for filename, source in production_sources.items() if "aeat config profile create" in source.lower()
    }
    assert not executable_recommendations

    commands_source = production_sources["_commands.py"]
    assert "_emit_save_exit_notice" not in commands_source
    assert "_SAVE_EXIT_RESUME_CODE" not in commands_source
    assert "setup_saved_resume_later" not in commands_source
    assert "save_exit_persisted" not in commands_source
    assert "ProfileFactsCheckpointStore" not in commands_source


def test_wizard_status_next_action_declares_only_the_registered_resolved_login_action() -> None:
    source = inspect.getsource(status_module)
    tree = ast.parse(source)
    function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_next_wizard_action"
    )
    action_ids = {
        node.args[0].value
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and _call_name(node.func) == "declare_next_action"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert action_ids == {"operator.auth.login"}
    assert (
        _next_wizard_action(
            has_profile=False,
            missing_required=(),
            missing_enrolment=(),
            auth_provider="",
            login_ready=False,
        )
        is None
    )


def test_missing_active_profile_has_an_exact_application_state_operator_decision_verdict() -> None:
    with pytest.raises(WizardStatusError) as raised:
        load_active_taxpayer_profile(WorkflowState())

    _assert_terminal_contract(
        raised.value,
        condition=WizardPreconditionCondition.ACTIVE_PROFILE_AVAILABLE,
        facts={"active_profile_record_available": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_missing_active_tax_id_has_an_exact_application_state_operator_decision_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(status_module, "record_to_path_values", lambda _record: {})
    monkeypatch.setattr(status_module, "resolve_active_bucket_id", lambda: "profile-id")
    monkeypatch.setattr(status_module, "_grounded_tax_id_requirement", lambda: "Tax identifier")
    state = SimpleNamespace(active_profile_record=lambda: object())

    with pytest.raises(WizardStatusError) as raised:
        load_active_taxpayer_profile(state)

    _assert_terminal_contract(
        raised.value,
        condition=WizardPreconditionCondition.ACTIVE_PROFILE_TAX_ID_DECLARED,
        facts={"active_profile_tax_id_declared": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_missing_profile_name_has_an_exact_runtime_operator_decision_verdict() -> None:
    with pytest.raises(WizardMissingFlagError) as raised:
        _require_profile_name(SETUP_FLOW, None)

    _assert_terminal_contract(
        raised.value,
        condition=WizardPreconditionCondition.PROFILE_NAME_SUPPLIED,
        facts={"profile_name_supplied": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_quiet_missing_required_flags_has_an_exact_runtime_operator_decision_verdict() -> None:
    missing = commands_module._missing_required_flags(SETUP_FLOW, {})
    assert missing

    with pytest.raises(WizardMissingFlagError) as raised:
        _run_full_flow(
            SETUP_FLOW,
            {},
            quiet=True,
            accept_defaults=False,
            profile_name="Existing profile",
            profile_id="profile-id",
            mode="edit",
        )

    _assert_terminal_contract(
        raised.value,
        condition=WizardPreconditionCondition.REQUIRED_FLAGS_SUPPLIED,
        facts={"required_flags_supplied": False, "missing_flag_count": len(missing)},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_missing_filing_baseline_has_an_exact_runtime_operator_decision_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the edit boundary after its read projection, before any write."""

    class _Repository:
        @staticmethod
        def for_current_session(_profile_id: str) -> SimpleNamespace:
            return SimpleNamespace(load=lambda _profile_id: object())

    monkeypatch.setattr(user_profile_module, "ProfileRecordRepository", _Repository)
    monkeypatch.setattr(user_profile_module, "record_to_path_values", lambda _record: {})
    monkeypatch.setattr(persistence_module, "profile_values_from_patch", lambda _flow, _flags: {})
    monkeypatch.setattr(persistence_module, "project_answers", lambda _flow, _values: {})
    monkeypatch.setattr(commands_module, "_missing_filing_baseline_flags", lambda _flow, _answers: ("a", "b"))

    with pytest.raises(WizardMissingFlagError) as raised:
        _run_patch_edit(SETUP_FLOW, {}, profile_id="profile-id")

    _assert_terminal_contract(
        raised.value,
        condition=WizardPreconditionCondition.FILING_BASELINE_COMPLETE,
        facts={"filing_baseline_complete": False, "missing_flag_count": 2},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_taken_profile_label_has_an_exact_application_state_operator_decision_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workflow_module, "read_profile_bucket", lambda _label: object())

    with pytest.raises(WizardValidationError) as raised:
        _resolve_profile_id_for_mode(SETUP_FLOW, "create", "Taken profile")

    _assert_terminal_contract(
        raised.value,
        condition=WizardPreconditionCondition.PROFILE_LABEL_AVAILABLE,
        facts={"profile_registration_available": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_edit_without_an_interactive_console_has_an_exact_runtime_safety_verdict() -> None:
    with pytest.raises(WizardEditUnsupportedConsoleError) as raised:
        _run_full_flow(
            SETUP_FLOW,
            {},
            quiet=False,
            accept_defaults=False,
            profile_name="Existing profile",
            profile_id="profile-id",
            mode="edit",
        )

    _assert_terminal_contract(
        raised.value,
        condition=WizardPreconditionCondition.INTERACTIVE_CONSOLE_AVAILABLE,
        facts={"interactive_console_available": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.SAFETY,
    )


def test_interactive_profile_create_remains_custody_refused_before_console_handling() -> None:
    """Current custody rejects create; neither status nor wizard offers it as recovery."""
    with pytest.raises(ProfileRegistrationError):
        _run_full_flow(
            SETUP_FLOW,
            {},
            quiet=False,
            accept_defaults=False,
            profile_name="New profile",
            profile_id="profile-id",
            mode="create",
        )
