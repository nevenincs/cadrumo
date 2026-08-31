"""Complete terminal-precondition contracts for AEAT browser carriers."""

from __future__ import annotations

import ast
import asyncio
import inspect
from dataclasses import dataclass
from types import ModuleType
from typing import override

import pytest
from playwright.async_api import async_playwright

from ......core.config import Settings
from ......core.errors.hierarchy import TerminalPreconditionErrorMixin
from ......core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .. import evasion as evasion_module
from .. import factory as factory_module
from .. import session as session_module
from ..errors import (
    BrowserError,
    BrowserEvasionError,
    BrowserPreconditionCondition,
)
from ..evasion import _raise_playwright_stealth_unavailable
from ..profile import Profile
from ..session import BrowserSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@dataclass(frozen=True)
class _CarrierContract:
    condition: BrowserPreconditionCondition
    facts: tuple[tuple[str, str], ...]
    outcome: NoRecoveryOutcome


def _contract(
    condition: BrowserPreconditionCondition,
    facts: tuple[tuple[str, str], ...],
    outcome: NoRecoveryOutcome,
) -> _CarrierContract:
    return _CarrierContract(condition, facts, outcome)


# Complete source-level contract for every BrowserError carrier in the current
# scope.  Fact values remain AST expressions so dynamic checks and polarities
# cannot silently drift while retaining the same mapping keys.
_BROWSER_FAILURE_TOTALITY: dict[str, _CarrierContract] = {
    "factory:_SharedPlaywrightRuntimeOwner.close:BrowserError:Playwright runtime stop failed": _contract(
        BrowserPreconditionCondition.RUNTIME_STOPPABLE,
        (("playwright_runtime_stoppable", "False"),),
        NoRecoveryOutcome.SAFETY,
    ),
    "factory:DefaultBrowserSession._stop_playwright_runtime:BrowserError:Playwright runtime stop failed": _contract(
        BrowserPreconditionCondition.RUNTIME_STOPPABLE,
        (("playwright_runtime_stoppable", "False"),),
        NoRecoveryOutcome.SAFETY,
    ),
    "factory:_start_playwright:BrowserError:Browser optional extra is unavailable": _contract(
        BrowserPreconditionCondition.OPTIONAL_EXTRA_AVAILABLE,
        (("browser_extra_available", "False"),),
        NoRecoveryOutcome.SAFETY,
    ),
    "factory:_start_playwright:BrowserError:Playwright runtime start failed": _contract(
        BrowserPreconditionCondition.RUNTIME_STARTABLE,
        (("playwright_runtime_startable", "False"),),
        NoRecoveryOutcome.SAFETY,
    ),
    "session:BrowserSession.create_context:BrowserError:Browser session already owns a live browser": _contract(
        BrowserPreconditionCondition.SESSION_AVAILABLE,
        (("browser_session_available", "False"),),
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    "session:BrowserSession.create_context:BrowserError:Browser context preparation failed": _contract(
        BrowserPreconditionCondition.CONTEXT_CREATABLE,
        (("browser_context_creatable", "False"),),
        NoRecoveryOutcome.SAFETY,
    ),
    "session:BrowserSession._launch_chromium:BrowserError:Browser launch failed": _contract(
        BrowserPreconditionCondition.BROWSER_LAUNCHABLE,
        (("browser_launchable", "False"),),
        NoRecoveryOutcome.SAFETY,
    ),
    "session:BrowserSession._create_playwright_context:BrowserError:Browser context creation failed": _contract(
        BrowserPreconditionCondition.CONTEXT_CREATABLE,
        (
            ("browser_context_creatable", "False"),
            ("storage_state_supplied", "'storage_state' in context_kwargs"),
            ("provisioner_supplied", "'client_certificates' in context_kwargs"),
        ),
        NoRecoveryOutcome.SAFETY,
    ),
    "session:BrowserSession._apply_evasion:BrowserError:Browser evasion setup failed": _contract(
        BrowserPreconditionCondition.EVASION_APPLIED,
        (("browser_evasion_applied", "False"),),
        NoRecoveryOutcome.SAFETY,
    ),
    "session:BrowserSession.navigate:BrowserError:Navigated browser page content is unreadable": _contract(
        BrowserPreconditionCondition.PAGE_CONTENT_READABLE,
        (("browser_page_content_readable", "False"),),
        NoRecoveryOutcome.SAFETY,
    ),
    "session:BrowserSession._close_browser_locked:BrowserError:Failed to close retained browser": _contract(
        BrowserPreconditionCondition.BROWSER_CLOSEABLE,
        (("browser_closeable", "False"),),
        NoRecoveryOutcome.SAFETY,
    ),
    "evasion:_raise_playwright_stealth_unavailable:BrowserEvasionError:Browser evasion support is unavailable": _contract(
        BrowserPreconditionCondition.EVASION_SUPPORT_AVAILABLE,
        (("browser_evasion_support_available", "False"),),
        NoRecoveryOutcome.SAFETY,
    ),
}

_BROWSER_PRODUCER_MODULES: tuple[ModuleType, ...] = (
    factory_module,
    session_module,
    evasion_module,
)


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _message_identity(node: ast.expr) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    assert isinstance(node, ast.JoinedStr)
    return "".join(
        part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else "{value}"
        for part in node.values
    )


def _browser_error_carriers() -> dict[str, ast.Call]:
    carriers: dict[str, ast.Call] = {}
    for module in _BROWSER_PRODUCER_MODULES:
        tree = ast.parse(inspect.getsource(module))

        class Visitor(ast.NodeVisitor):
            def __init__(self, module_name: str) -> None:
                self.module_name = module_name
                self.owner = "<module>"

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
                error_type = _call_name(node.func)
                if error_type in {"BrowserError", "BrowserEvasionError"}:
                    assert node.args
                    key = f"{self.module_name}:{self.owner}:{error_type}:{_message_identity(node.args[0])}"
                    assert key not in carriers, f"duplicate browser failure carrier {key}"
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
    assert _call_name(value.func) == "browser_no_action_verdict"
    return value


def _condition(precondition: ast.Call) -> BrowserPreconditionCondition:
    value = _keyword(precondition, "condition")
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == "BrowserPreconditionCondition"
    return BrowserPreconditionCondition[value.attr]


def _fact_expressions(precondition: ast.Call) -> tuple[tuple[str, str], ...]:
    facts = _keyword(precondition, "facts")
    assert isinstance(facts, ast.Dict)
    values: list[tuple[str, str]] = []
    for key, value in zip(facts.keys, facts.values, strict=True):
        assert isinstance(key, ast.Constant) and isinstance(key.value, str)
        values.append((key.value, ast.unparse(value)))
    return tuple(values)


def _outcome(precondition: ast.Call) -> NoRecoveryOutcome:
    value = _keyword(precondition, "outcome")
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == "NoRecoveryOutcome"
    return NoRecoveryOutcome[value.attr]


def _assert_terminal_contract(
    error: BrowserError,
    *,
    condition: BrowserPreconditionCondition,
    facts: dict[str, str | int | bool],
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
    assert evidence.provenance is ActionEvidenceProvenance.RUNTIME_OBSERVATION
    assert dict(evidence.values) == facts


def test_browser_failure_totality_uses_one_canonical_no_action_projection() -> None:
    observed = _browser_error_carriers()

    assert set(observed) == set(_BROWSER_FAILURE_TOTALITY)
    for key, carrier in observed.items():
        expected = _BROWSER_FAILURE_TOTALITY[key]
        precondition = _precondition(carrier)
        assert _condition(precondition) is expected.condition
        assert _fact_expressions(precondition) == expected.facts
        assert _outcome(precondition) is expected.outcome


def test_browser_producers_have_no_direct_verdict_constructor_or_authored_recovery_command() -> None:
    """The browser boundary delegates construction and carries factual failures only."""
    errors_module = __import__("cadrumo.adapters.outbound.aeat.browser.errors", fromlist=["*"])
    for module in (*_BROWSER_PRODUCER_MODULES, errors_module):
        source = inspect.getsource(module).lower()
        assert "playwright install" not in source
        assert "playwright-doctor" not in source
        assert "str(exc)" not in source
        tree = ast.parse(inspect.getsource(module))
        constructed = {
            _call_name(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _call_name(node.func) in {"PreconditionVerdict", "ConditionEvidence"}
        }
        assert not constructed, module.__name__

    delegate_calls = [
        (module.__name__, _call_name(node.func))
        for module in (*_BROWSER_PRODUCER_MODULES, errors_module)
        for node in ast.walk(ast.parse(inspect.getsource(module)))
        if isinstance(node, ast.Call) and _call_name(node.func) == "no_action_precondition_verdict"
    ]
    assert delegate_calls == [(errors_module.__name__, "no_action_precondition_verdict")]


def test_missing_evasion_support_has_an_exact_runtime_safety_verdict() -> None:
    cause = ImportError("playwright-stealth is unavailable")
    with pytest.raises(BrowserEvasionError) as raised:
        _raise_playwright_stealth_unavailable(cause)

    assert raised.value.__cause__ is cause
    _assert_terminal_contract(
        raised.value,
        condition=BrowserPreconditionCondition.EVASION_SUPPORT_AVAILABLE,
        facts={"browser_evasion_support_available": False},
        outcome=NoRecoveryOutcome.SAFETY,
    )


@pytest.mark.asyncio
async def test_page_content_failure_has_an_exact_runtime_safety_verdict() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        page.on("load", lambda _page: asyncio.create_task(page.close()))
        session = BrowserSession(
            playwright=playwright,
            settings=Settings(),
            profile=Profile(name="terminal-precondition"),
        )

        try:
            with pytest.raises(BrowserError) as raised:
                await session.navigate(page, "data:text/html,<html><body>detached</body></html>")
        finally:
            await context.close()
            await session.close()
            await browser.close()

    _assert_terminal_contract(
        raised.value,
        condition=BrowserPreconditionCondition.PAGE_CONTENT_READABLE,
        facts={"browser_page_content_readable": False},
        outcome=NoRecoveryOutcome.SAFETY,
    )
