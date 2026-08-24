"""Terminal-precondition contracts for every Google-auth refusal producer."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from datetime import UTC, datetime
from types import ModuleType

import pytest
from google.oauth2.credentials import Credentials

from .....core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .....core.config import override_settings
from .....core.errors import TerminalPreconditionErrorMixin
from .....tests.env_scope import scoped_env_var
from .. import _active_profile as active_profile_module
from .. import _impersonation as impersonation_module
from .. import _oauth_flow as oauth_flow_module
from .._active_profile import resolve_active_profile
from .._errors import GoogleAuthError, GoogleAuthPreconditionCondition, GoogleAuthProfileUnboundError
from .._impersonation import GoogleAuthAdcUnavailableError, GoogleImpersonationConfig, resolve_impersonated_credentials
from .._oauth_flow import (
    _decode_email_from_id_token,
    _raise_local_server_error,
    check_unsecured_mode_safety,
    credentials_to_records,
    require_interactive_terminal,
)
from .._records import REQUIRED_SCOPES

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@dataclass(frozen=True)
class _CarrierContract:
    condition: GoogleAuthPreconditionCondition
    facts: tuple[tuple[str, str], ...]
    provenance: ActionEvidenceProvenance
    outcome: NoRecoveryOutcome


def _contract(
    condition: GoogleAuthPreconditionCondition,
    facts: tuple[tuple[str, str], ...],
    provenance: ActionEvidenceProvenance,
    outcome: NoRecoveryOutcome,
) -> _CarrierContract:
    return _CarrierContract(condition, facts, provenance, outcome)


# This is a complete, source-level contract for the 1 active-profile, 15 OAuth,
# and 4 impersonation GoogleAuthError producers. Values are AST expressions, not
# merely fact keys, so a polarity or dynamic-expression mutation is observable.
_AUTH_FAILURE_TOTALITY: dict[str, _CarrierContract] = {
    "_active_profile:resolve_active_profile:GoogleAuthProfileUnboundError:no active AEAT profile bound for Google OAuth": _contract(
        GoogleAuthPreconditionCondition.ACTIVE_PROFILE_RESOLVED,
        (("active_profile_resolved", "False"),),
        ActionEvidenceProvenance.APPLICATION_STATE,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    "_oauth_flow:require_interactive_terminal:GoogleAuthNonInteractiveError:google OAuth refused: interactive browser consent requires a controlling terminal": _contract(
        GoogleAuthPreconditionCondition.INTERACTIVE_TERMINAL_AVAILABLE,
        (("interactive_terminal_available", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_oauth_flow:check_unsecured_mode_safety:GoogleAuthUnsecuredModeRefusedError:google OAuth refused: secret store is unsecured and the active profile carries a real NIF": _contract(
        GoogleAuthPreconditionCondition.CREDENTIAL_STORE_SECURED,
        (("secret_store_secured", "False"), ("tax_id_present", "True")),
        ActionEvidenceProvenance.APPLICATION_STATE,
        NoRecoveryOutcome.SAFETY,
    ),
    "_oauth_flow:resolve_active_tax_id:GoogleAuthProfileUnboundError:google OAuth refused: active profile bucket manifest could not be resolved": _contract(
        GoogleAuthPreconditionCondition.PROFILE_IDENTITY_RESOLVED,
        (("profile_bucket_present", "False"),),
        ActionEvidenceProvenance.APPLICATION_STATE,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    "_oauth_flow:resolve_active_tax_id:GoogleAuthProfileUnboundError:google OAuth refused: active profile record could not be resolved": _contract(
        GoogleAuthPreconditionCondition.PROFILE_IDENTITY_RESOLVED,
        (("profile_record_present", "False"),),
        ActionEvidenceProvenance.APPLICATION_STATE,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    "_oauth_flow:credentials_to_records:GoogleAuthScopeInsufficientError:consent screen returned without granting required scopes: {value}": _contract(
        GoogleAuthPreconditionCondition.REQUIRED_SCOPES_GRANTED,
        (("required_scopes_granted", "False"), ("missing_scope_count", "len(missing)")),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_oauth_flow:_run_local_server:GoogleAuthNetworkError:google-auth-oauthlib not importable: {value}": _contract(
        GoogleAuthPreconditionCondition.OAUTHLIB_AVAILABLE,
        (("oauthlib_available", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_oauth_flow:_run_local_server:GoogleAuthNetworkError:OAuth client config refused: {value}": _contract(
        GoogleAuthPreconditionCondition.OAUTH_CLIENT_CONFIG_VALID,
        (("oauth_client_config_valid", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_oauth_flow:_run_local_server:GoogleAuthLoopbackBindError:loopback receiver failed to bind: {value}": _contract(
        GoogleAuthPreconditionCondition.LOOPBACK_RECEIVER_BOUND,
        (("loopback_receiver_bound", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_oauth_flow:_raise_local_server_error:GoogleAuthBrowserOpenError:OS browser launcher refused: {value}": _contract(
        GoogleAuthPreconditionCondition.BROWSER_LAUNCHER_AVAILABLE,
        (("browser_launcher_available", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_oauth_flow:_raise_local_server_error:GoogleAuthNetworkError:OAuth endpoint unreachable: {value}": _contract(
        GoogleAuthPreconditionCondition.OAUTH_ENDPOINT_REACHABLE,
        (("oauth_endpoint_reachable", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_oauth_flow:_raise_local_server_error:GoogleAuthNetworkError:OAuth local server flow failed: {value}": _contract(
        GoogleAuthPreconditionCondition.OAUTH_FLOW_COMPLETED,
        (("oauth_flow_completed", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_oauth_flow:_decode_email_from_id_token:GoogleAuthScopeInsufficientError:Google did not return an id_token; the OAuth consent did not include the openid+email scopes": _contract(
        GoogleAuthPreconditionCondition.IDENTITY_ASSERTION_PRESENT,
        (("id_token_present", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_oauth_flow:_decode_email_from_id_token:GoogleAuthNetworkError:google-auth id_token module not importable: {value}": _contract(
        GoogleAuthPreconditionCondition.IDENTITY_ASSERTION_VERIFIER_AVAILABLE,
        (("id_token_verifier_available", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_oauth_flow:_decode_email_from_id_token:GoogleAuthNetworkError:id_token verification failed: {value}": _contract(
        GoogleAuthPreconditionCondition.IDENTITY_ASSERTION_VERIFIED,
        (("id_token_verified", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_oauth_flow:_decode_email_from_id_token:GoogleAuthScopeInsufficientError:id_token verified but carries no `email` claim": _contract(
        GoogleAuthPreconditionCondition.IDENTITY_EMAIL_PRESENT,
        (("id_token_email_present", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_impersonation:resolve_impersonated_credentials:GoogleAuthAdcUnavailableError:google-auth is not importable: {value}": _contract(
        GoogleAuthPreconditionCondition.ADC_CLIENT_AVAILABLE,
        (("adc_client_available", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_impersonation:resolve_impersonated_credentials:GoogleAuthAdcUnavailableError:Application Default Credentials not found: {value}": _contract(
        GoogleAuthPreconditionCondition.ADC_AVAILABLE,
        (("adc_available", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_impersonation:resolve_impersonated_credentials:GoogleAuthImpersonationRefusedError:IAM refused to mint an impersonated token for {value}: {value}": _contract(
        GoogleAuthPreconditionCondition.IAM_CREDENTIAL_MINTED,
        (("iam_token_minted", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
    "_impersonation:_ensure_source_credential_is_fresh:GoogleAuthAdcStaleError:Application Default Credentials could not be refreshed: {value}": _contract(
        GoogleAuthPreconditionCondition.ADC_SOURCE_FRESH,
        (("adc_source_fresh", "False"),),
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.SAFETY,
    ),
}

_AUTH_PRODUCER_MODULES: tuple[ModuleType, ...] = (
    active_profile_module,
    oauth_flow_module,
    impersonation_module,
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
    parts: list[str] = []
    for part in node.values:
        parts.append(part.value if isinstance(part, ast.Constant) else "{value}")
    return "".join(parts)


def _google_auth_carriers() -> dict[str, ast.Call]:
    carriers: dict[str, ast.Call] = {}
    for module in _AUTH_PRODUCER_MODULES:
        tree = ast.parse(inspect.getsource(module))

        class Visitor(ast.NodeVisitor):
            def __init__(self, module_name: str) -> None:
                self.module_name = module_name
                self.owner = "<module>"

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                prior_owner = self.owner
                self.owner = node.name
                self.generic_visit(node)
                self.owner = prior_owner

            def visit_Call(self, node: ast.Call) -> None:
                error_type = _call_name(node.func)
                if error_type is not None and error_type.startswith("GoogleAuth") and error_type.endswith("Error"):
                    assert node.args
                    key = f"{self.module_name}:{self.owner}:{error_type}:{_message_identity(node.args[0])}"
                    assert key not in carriers, f"duplicate Google auth failure carrier {key}"
                    carriers[key] = node
                self.generic_visit(node)

        Visitor(module.__name__.rsplit('.', maxsplit=1)[-1]).visit(tree)
    return carriers


def _precondition(call: ast.Call) -> ast.Call:
    value = next((keyword.value for keyword in call.keywords if keyword.arg == "precondition_verdict"), None)
    assert isinstance(value, ast.Call)
    assert _call_name(value.func) == "google_auth_no_action_verdict"
    return value


def _keyword(call: ast.Call, name: str) -> ast.expr:
    value = next((keyword.value for keyword in call.keywords if keyword.arg == name), None)
    assert value is not None, f"missing {name}"
    return value


def _condition(precondition: ast.Call) -> GoogleAuthPreconditionCondition:
    value = _keyword(precondition, "condition")
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == "GoogleAuthPreconditionCondition"
    return GoogleAuthPreconditionCondition[value.attr]


def _fact_expressions(precondition: ast.Call) -> tuple[tuple[str, str], ...]:
    facts = _keyword(precondition, "facts")
    assert isinstance(facts, ast.Dict)
    values: list[tuple[str, str]] = []
    for key, value in zip(facts.keys, facts.values, strict=True):
        assert isinstance(key, ast.Constant) and isinstance(key.value, str)
        values.append((key.value, ast.unparse(value)))
    return tuple(values)


def _enum_keyword(precondition: ast.Call, name: str, enum: type[ActionEvidenceProvenance] | type[NoRecoveryOutcome]):
    value = _keyword(precondition, name)
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == enum.__name__
    return enum[value.attr]


def _assert_terminal_contract(
    error: GoogleAuthError,
    *,
    condition: GoogleAuthPreconditionCondition,
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


def test_google_auth_failure_totality_uses_one_canonical_no_action_projection() -> None:
    observed = _google_auth_carriers()

    assert set(observed) == set(_AUTH_FAILURE_TOTALITY)
    for key, carrier in observed.items():
        expected = _AUTH_FAILURE_TOTALITY[key]
        precondition = _precondition(carrier)
        assert _condition(precondition) is expected.condition
        assert _fact_expressions(precondition) == expected.facts
        assert _enum_keyword(precondition, "provenance", ActionEvidenceProvenance) is expected.provenance
        assert _enum_keyword(precondition, "outcome", NoRecoveryOutcome) is expected.outcome


def test_google_auth_modules_never_construct_verdict_or_evidence_locally() -> None:
    """Google auth delegates terminal construction to application.operator_actions."""
    for module in (*_AUTH_PRODUCER_MODULES, __import__("cadrumo.adapters.outbound.google._errors", fromlist=["*"])):
        tree = ast.parse(inspect.getsource(module))
        constructed = {
            _call_name(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _call_name(node.func) in {"PreconditionVerdict", "ConditionEvidence"}
        }
        assert not constructed, module.__name__


def test_google_auth_producers_do_not_offer_interactive_profile_creation() -> None:
    """Profile creation belongs to CLI/profile custody, not these auth refusal producers."""
    producer_source = "\n".join(inspect.getsource(module).lower() for module in _AUTH_PRODUCER_MODULES)
    assert "profile create" not in producer_source
    assert "profile_create" not in producer_source


def test_active_profile_refusal_has_an_exact_operator_decision_verdict(tmp_path) -> None:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None),
        pytest.raises(GoogleAuthProfileUnboundError) as raised,
    ):
        resolve_active_profile()

    _assert_terminal_contract(
        raised.value,
        condition=GoogleAuthPreconditionCondition.ACTIVE_PROFILE_RESOLVED,
        facts={"active_profile_resolved": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_unsecured_real_tax_id_refusal_has_an_exact_safety_verdict() -> None:
    with (
        override_settings(cadrumo_secret_store_backend="unsecured"),
        pytest.raises(GoogleAuthError) as raised,
    ):
        check_unsecured_mode_safety("any-profile", "12345678Z")

    _assert_terminal_contract(
        raised.value,
        condition=GoogleAuthPreconditionCondition.CREDENTIAL_STORE_SECURED,
        facts={"secret_store_secured": False, "tax_id_present": True},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.SAFETY,
    )


def test_scope_refusal_has_an_exact_runtime_safety_verdict() -> None:
    with pytest.raises(GoogleAuthError) as raised:
        credentials_to_records(
            refresh_token="refresh-token",
            token_uri="https://oauth2.googleapis.com/token",
            account_email="operator@example.test",
            granted_scopes=(),
            issued_at=datetime(2026, 8, 24, tzinfo=UTC),
        )

    _assert_terminal_contract(
        raised.value,
        condition=GoogleAuthPreconditionCondition.REQUIRED_SCOPES_GRANTED,
        facts={"required_scopes_granted": False, "missing_scope_count": len(REQUIRED_SCOPES)},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.SAFETY,
    )


@pytest.mark.parametrize(
    ("upstream", "condition", "facts"),
    [
        (
            RuntimeError("webbrowser launcher refused"),
            GoogleAuthPreconditionCondition.BROWSER_LAUNCHER_AVAILABLE,
            {"browser_launcher_available": False},
        ),
        (
            RuntimeError("transport connection refused"),
            GoogleAuthPreconditionCondition.OAUTH_ENDPOINT_REACHABLE,
            {"oauth_endpoint_reachable": False},
        ),
    ],
)
def test_local_oauth_external_refusals_have_exact_runtime_safety_verdicts(
    upstream: RuntimeError,
    condition: GoogleAuthPreconditionCondition,
    facts: dict[str, bool],
) -> None:
    with pytest.raises(GoogleAuthError) as raised:
        _raise_local_server_error(upstream)

    assert raised.value.__cause__ is upstream
    _assert_terminal_contract(
        raised.value,
        condition=condition,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.SAFETY,
    )


def test_missing_identity_assertion_has_an_exact_runtime_safety_verdict() -> None:
    credentials = Credentials(token="short-lived-access-token")
    with pytest.raises(GoogleAuthError) as raised:
        _decode_email_from_id_token(credentials, audience="desktop-client.apps.googleusercontent.com")

    _assert_terminal_contract(
        raised.value,
        condition=GoogleAuthPreconditionCondition.IDENTITY_ASSERTION_PRESENT,
        facts={"id_token_present": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.SAFETY,
    )


def test_unavailable_adc_has_an_exact_runtime_safety_verdict() -> None:
    config = GoogleImpersonationConfig(target_principal="aeat-export@example-project.iam.gserviceaccount.com")
    with (
        scoped_env_var("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/path/does-not-exist.json"),
        pytest.raises(GoogleAuthAdcUnavailableError) as raised,
    ):
        resolve_impersonated_credentials(config)

    _assert_terminal_contract(
        raised.value,
        condition=GoogleAuthPreconditionCondition.ADC_AVAILABLE,
        facts={"adc_available": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.SAFETY,
    )


def test_noninteractive_refusal_has_an_exact_runtime_safety_verdict() -> None:
    with pytest.raises(GoogleAuthError) as raised:
        require_interactive_terminal()

    _assert_terminal_contract(
        raised.value,
        condition=GoogleAuthPreconditionCondition.INTERACTIVE_TERMINAL_AVAILABLE,
        facts={"interactive_terminal_available": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.SAFETY,
    )
