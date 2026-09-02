"""Closed producer census for the root CLI action migration."""

from __future__ import annotations

import ast
import inspect
from collections.abc import Iterable
from types import ModuleType

import pytest

from .. import _app_diagnostics as diagnostics_module
from .. import _app_diagnostics_telemetry as telemetry_module
from .. import _app_live as live_module
from .. import _log_levels as log_levels_module
from ..config import _archive_reconcile as maintenance_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


_MODULES: tuple[ModuleType, ...] = (
    log_levels_module,
    diagnostics_module,
    telemetry_module,
    maintenance_module,
    live_module,
)

# Every direct Notice construction in the five owned modules.  The LLM helper
# deliberately has a dynamic code argument; its four callers are asserted
# separately so a new notice cannot hide behind that one shared constructor.
_NOTICE_PRODUCERS: dict[str, set[tuple[str, str, str | None]]] = {
    "cadrumo.entrypoints.cli._app_diagnostics": {
        ("_llm_no_run_data_notice", "code", "operator.ledger.classify"),
        ("diagnostics_run_health", "'diagnostics.run_health.session_stale'", None),
        ("diagnostics_run_health", "'diagnostics.run_health.no_session'", None),
        ("diagnostics_errors", "'diagnostics.errors.no_failures'", None),
    },
    "cadrumo.entrypoints.cli._app_diagnostics_telemetry": {
        ("diagnostics_telemetry_flush", "'diagnostics.telemetry.flush.dry_run'", None),
        ("diagnostics_telemetry_flush", "'diagnostics.telemetry.flush.consent_refused'", None),
        ("diagnostics_telemetry_flush", "'diagnostics.telemetry.flush.no_endpoint'", None),
    },
    "cadrumo.entrypoints.cli.config._archive_reconcile": {
        ("_reconcile_notices", "'config.profile.archive.reconcile.nothing_to_reconcile'", None),
        ("_reconcile_notices", "'config.profile.archive.reconcile.cleared'", None),
        ("_reconcile_notices", "'config.profile.archive.reconcile.failures'", "operator.profile.archive.reconcile"),
    },
    "cadrumo.entrypoints.cli._app_live": {
        ("_filed_discover_notices", "'live.filed.discover.register_options_scope_unconfirmed'", None),
        ("_filed_discover_notices", "'live.filed.discover.no_taxpayer_specific_denominator'", None),
        ("_limit_reached_notice", "'live.filed.limit_reached'", "operator.live.filed.pull_all"),
        ("_filed_pull_all_notices", "'live.filed.pull_all.pairs_refused'", "operator.live.filed.pull_all"),
        ("_filed_pull_all_notices", "'live.filed.pull_all.no_taxpayer_specific_denominator'", None),
        ("_skipped_casilla_notice", "'live.filed.pull.casillas_not_enrolled'", None),
    },
}

_LLM_NOTICE_CALLERS = {
    ("diagnostics_run_health", "'diagnostics.run_health.no_run_data'"),
    ("diagnostics_runs", "'diagnostics.runs.no_run_data'"),
    ("diagnostics_latency", "'diagnostics.latency.no_run_data'"),
    ("diagnostics_llm_usage", "'diagnostics.llm_usage.no_run_data'"),
}

_NATIVE_PARSE_VALIDATION_CARRIERS = {
    ("_verify_expected", "tr('cli.app.live.verify.expected_values_error')"),
    ("_live_period_option", "f'invalid AEAT period {period!r} for year {year}'"),
    ("_required_live_period_option", "'--period is required'"),
    ("filed_pull_cmd", "tr('cli.app.live.filed.pull_dry_run_single_mode_error')"),
    ("filed_pull_cmd", "'--period and --expediente are only valid for one --modelo with --year'"),
}


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((item.value for item in call.keywords if item.arg == name), None)


def _functions(module: ModuleType) -> Iterable[ast.FunctionDef]:
    tree = ast.parse(inspect.getsource(module))
    yield from (node for node in tree.body if isinstance(node, ast.FunctionDef))


def _action_id(call: ast.Call) -> str | None:
    action = _keyword(call, "action")
    if action is None:
        return None
    references = [
        candidate
        for candidate in ast.walk(action)
        if isinstance(candidate, ast.Call) and _call_name(candidate.func) == "ActionReference"
    ]
    assert len(references) <= 1
    if not references:
        return None
    value = _keyword(references[0], "action_id")
    assert isinstance(value, ast.Constant) and isinstance(value.value, str)
    return value.value


def test_root_cli_notice_producer_census_is_exact() -> None:
    observed: dict[str, set[tuple[str, str, str | None]]] = {}
    for module in _MODULES:
        producers: set[tuple[str, str, str | None]] = set()
        for function in _functions(module):
            for call in ast.walk(function):
                if isinstance(call, ast.Call) and _call_name(call.func) == "Notice":
                    code = _keyword(call, "code")
                    assert code is not None
                    producers.add((function.name, ast.unparse(code), _action_id(call)))
        if producers:
            observed[module.__name__] = producers

    assert observed == _NOTICE_PRODUCERS


def test_llm_guidance_callers_and_native_option_shape_exclusions_are_exact() -> None:
    llm_callers: set[tuple[str, str]] = set()
    for function in _functions(diagnostics_module):
        for call in ast.walk(function):
            if isinstance(call, ast.Call) and _call_name(call.func) == "_llm_no_run_data_notice":
                code = _keyword(call, "code")
                assert code is not None
                llm_callers.add((function.name, ast.unparse(code)))
    assert llm_callers == _LLM_NOTICE_CALLERS

    parse_carriers: set[tuple[str, str]] = set()
    for function in _functions(live_module):
        for call in ast.walk(function):
            if isinstance(call, ast.Call) and _call_name(call.func) == "BadParameter":
                assert len(call.args) == 1
                parse_carriers.add((function.name, ast.unparse(call.args[0])))
    assert parse_carriers == _NATIVE_PARSE_VALIDATION_CARRIERS

    log_level_calls = {
        (function.name, _call_name(call.func))
        for function in _functions(log_levels_module)
        for call in ast.walk(function)
        if isinstance(call, ast.Call)
        and _call_name(call.func) in {"LogLevelResolutionError", "_invalid_environment_log_level_error"}
    }
    assert log_level_calls == {
        ("_invalid_environment_log_level_error", "LogLevelResolutionError"),
        ("resolve_log_level", "LogLevelResolutionError"),
        ("resolve_log_level", "_invalid_environment_log_level_error"),
    }


@pytest.mark.parametrize("code", sorted(code for _, code in _LLM_NOTICE_CALLERS))
def test_llm_no_run_notices_resolve_the_catalogue_action_at_runtime(code: str) -> None:
    notice = diagnostics_module._llm_no_run_data_notice(code=code)

    assert notice.action is not None
    assert notice.action.model_dump(mode="json") == {
        "action": {
            "action_id": "operator.ledger.classify",
            "target_command_key": "ledger.classify",
            "cli_path": ["app", "ledger", "classify"],
        },
        "argument_bindings": [],
    }


def test_owned_root_cli_sources_have_no_authored_recovery_prose_or_verdict_constructors() -> None:
    forbidden_recovery_phrases = (
        "Run an LLM-assisted classification",
        "re-run with a higher --limit or none",
        "Re-run to retry",
        "Run this command again once the cause is resolved",
    )
    forbidden_constructors = {
        "ConditionEvidence",
        "PreconditionVerdict",
        "ResolvedActionReference",
        "ResolvedPreconditionAction",
    }

    for module in _MODULES:
        source = inspect.getsource(module)
        assert not any(phrase in source for phrase in forbidden_recovery_phrases), module.__name__
        tree = ast.parse(source)
        constructors = {
            _call_name(call.func)
            for call in ast.walk(tree)
            if isinstance(call, ast.Call) and _call_name(call.func) in forbidden_constructors
        }
        assert not constructors, module.__name__
