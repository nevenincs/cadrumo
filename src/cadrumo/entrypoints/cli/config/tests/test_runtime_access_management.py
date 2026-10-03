"""CLI access controls declare protected input and safe typed output."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr, ValidationError

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operator_surface.command_ports import ProfileAuthenticationPosture
from cadrumo.application.runtime.profile_access import RuntimeSessionsLocked
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_projections import PublicAccessSession
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from cadrumo.core.period import Period
from cadrumo.entrypoints.cli._command_shared_contracts import SchemaState
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError

from ...tests.cli_runner import invoke_cached_cli
from ..runtime_access_management import ProfileResumeSecrets, _lock_result, _resume_password, _session_payload
from ..runtime_access_management_payloads import (
    ConfigProfileAutomationChangeResult,
    ConfigProfileAutomationCreateResult,
    ConfigProfileAutomationDecisionResult,
    ConfigProfileAutomationDenyResult,
    ConfigProfileAutomationInspectResult,
    ConfigProfileAutomationListResult,
    ConfigProfileLockResult,
    ConfigProfileResumeResult,
    ConfigProfileSessionsResult,
)
from ..runtime_access_management_specs import RUNTIME_ACCESS_MANAGEMENT_COMMAND_SPECS
from ..secure_input import (
    clear_staged_machine_secret_payloads,
    select_machine_secret_channel,
    stage_machine_secret_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_live_specs_have_distinct_management_doors_and_no_password_argument() -> None:
    specs = {item.key: item for item in RUNTIME_ACCESS_MANAGEMENT_COMMAND_SPECS}
    assert set(specs) == {
        "config_profile_automation",
        "config_profile_sessions",
        "config_profile_automation_list",
        "config_profile_automation_create",
        "config_profile_automation_change",
        "config_profile_automation_inspect",
        "config_profile_automation_approve",
        "config_profile_automation_decline",
        "config_profile_automation_deny",
        "config_profile_lock",
        "config_profile_resume",
    }
    for key, result_type in {
        "config_profile_sessions": ConfigProfileSessionsResult,
        "config_profile_automation_list": ConfigProfileAutomationListResult,
        "config_profile_automation_create": ConfigProfileAutomationCreateResult,
        "config_profile_automation_change": ConfigProfileAutomationChangeResult,
        "config_profile_automation_inspect": ConfigProfileAutomationInspectResult,
        "config_profile_automation_approve": ConfigProfileAutomationDecisionResult,
        "config_profile_automation_decline": ConfigProfileAutomationDecisionResult,
        "config_profile_automation_deny": ConfigProfileAutomationDenyResult,
        "config_profile_lock": ConfigProfileLockResult,
        "config_profile_resume": ConfigProfileResumeResult,
    }.items():
        spec = specs[key]
        assert spec.result_schema.state is SchemaState.TARGET
        assert spec.result_schema.target is not None
        assert spec.result_schema.target.qualname == result_type.__name__
        assert "password" not in {item.name for item in spec.parameters}
        assert "passphrase" not in {item.name for item in spec.parameters}
        assert result_type.model_json_schema()
    resume = specs["config_profile_resume"]
    assert resume.profile_authentication is ProfileAuthenticationPosture.SELF_AUTHENTICATING
    assert resume.machine_secret is not None
    assert tuple(field.name for field in resume.machine_secret.variants[0].fields) == ("passphrase",)
    assert {item.name for item in resume.parameters} == {
        "grant",
        "secrets_stdin",
        "secrets_fd",
        "output_language",
    }
    create = specs["config_profile_automation_create"]
    assert create.profile_authentication is ProfileAuthenticationPosture.SELF_AUTHENTICATING
    assert create.machine_secret is not None
    assert tuple(field.name for field in create.machine_secret.variants[0].fields) == ("proposal",)
    change = specs["config_profile_automation_change"]
    assert change.profile_authentication is ProfileAuthenticationPosture.RESUME_FALLBACK
    assert change.machine_secret is not None
    assert tuple(field.name for field in change.machine_secret.variants[0].fields) == ("proposal",)


def test_session_payload_flattens_periods_and_reports_remaining_access() -> None:
    profile_id = uuid4()
    destination_id = uuid4()
    instant = datetime(2026, 9, 27, 12, tzinfo=UTC)
    session = PublicAccessSession(
        session_id=uuid4(),
        profile_id=profile_id,
        client_id=uuid4(),
        parent_session_id=None,
        grant_id=uuid4(),
        key_id=uuid4(),
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=AccessScope(
            operations=frozenset({"user-profile.field-mutation"}),
            actions=frozenset({AccessAction.SUBMIT}),
            disclosures=frozenset(
                {
                    DisclosurePermission(
                        destination_id=destination_id,
                        projection_id="profile.view",
                        category=DisclosureCategory.PROFILE_VALUES,
                    )
                }
            ),
            periods=frozenset({Period.from_year_and_code(2026, "3T")}),
            allow_period_independent=False,
            allow_delegation=False,
        ),
        expires_at=instant + timedelta(seconds=70),
    )
    projected = _session_payload(session, instant=instant)
    assert projected.profile_id == profile_id
    assert projected.remaining_seconds == 70
    assert projected.scope.periods is not None
    assert {(item.filing_year, item.code) for item in projected.scope.periods} == {(2026, "3T")}
    document = ConfigProfileSessionsResult(profile_id=profile_id, sessions=(projected,)).model_dump(mode="json")
    assert document["sessions"][0]["scope"]["disclosures"][0]["destination_id"] == str(destination_id)
    assert not {"secret", "password", "credential", "dek"} & document["sessions"][0].keys()


def test_resume_password_consumes_staged_bounded_secret_once() -> None:
    proof_text = "synthetic-resume-proof"
    selection = select_machine_secret_channel(secrets_stdin=True, secrets_fd=None)
    assert selection is not None
    try:
        stage_machine_secret_payload(ProfileResumeSecrets(passphrase=SecretStr(proof_text)))
        proof = _resume_password(secrets_stdin=True, secrets_fd=None)
        assert proof == proof_text.encode("utf-8")
        proof[:] = bytes(len(proof))
        assert not any(proof)
        with pytest.raises(ValidationError):
            ProfileResumeSecrets.model_validate({"passphrase": proof_text, "surplus": "not accepted"})
    finally:
        clear_staged_machine_secret_payloads()


@pytest.mark.parametrize(
    ("path", "tokens"),
    (
        (("sessions",), ("--output-language",)),
        (("automation", "list"), ("--output-language",)),
        (("automation", "deny"), ("key", "grant", "all")),
        (("lock",), ("--all", "--session")),
        (("resume",), ("--grant", "--secrets-stdin", "--secrets-fd")),
    ),
)
def test_live_parser_exposes_only_declared_management_options(path: tuple[str, ...], tokens: tuple[str, ...]) -> None:
    result = invoke_cached_cli(("config", "profile", *path, "--help"))
    assert result.exit_code == 0, result.output
    assert all(token in result.output for token in tokens)
    assert "--password" not in result.output


def test_resume_rejects_malformed_grant_before_any_runtime_admission() -> None:
    result = invoke_cached_cli(("config", "profile", "resume", "--grant", "not-a-uuid"))
    assert result.exit_code != 0


class _LockClient(RuntimeFrontendClient):
    """Explicit CLI presentation fault port; native authority has separate tests."""

    def __init__(self) -> None:
        self._profile_id = uuid4()
        self._frontend = OperationFrontendProjection.CLI
        self._session_id = uuid4()
        self.calls: list[str] = []
        self.cascade: tuple[UUID, ...] = ()

    @override
    def lock(self, *, timeout: float = 5) -> RuntimeSessionsLocked:
        self.calls.append("current")
        return self._locked((self.session_id,))

    @override
    def revoke_session(self, target_session_id: UUID, *, timeout: float = 5) -> RuntimeSessionsLocked:
        self.calls.append(f"selected:{target_session_id}")
        return self._locked(self.cascade)

    @override
    def deny_automation(
        self, kind: AutomationDenialKind, *, target_id: UUID | None = None, timeout: float = 10
    ) -> AutomationDenialReceipt:
        self.calls.append(kind.value)
        return AutomationDenialReceipt(
            request_id=uuid4(),
            profile_id=self.profile_id,
            access_denied=True,
            cleanup_pending=False,
            revision=3,
            profile_lock_generation=1,
        )

    @staticmethod
    def _locked(session_ids: tuple[UUID, ...]) -> RuntimeSessionsLocked:
        return RuntimeSessionsLocked(
            request_id=uuid4(), runtime_boot_id=uuid4(), connection_id=uuid4(), session_ids=session_ids
        )


def test_selected_session_lock_preserves_exact_requested_target_and_returned_cascade() -> None:
    client = _LockClient()
    target = uuid4()
    child = uuid4()
    client.cascade = (target, child)
    result = _lock_result(client, all_sessions=False, session=target)
    assert client.calls == [f"selected:{target}"]
    assert result.scope == "selected"
    assert result.target_session_id == target
    assert result.session_ids == (target, child)
    assert result.denial is None
    assert ConfigProfileLockResult.model_validate_json(result.model_dump_json()) == result


def test_lock_selectors_are_mutually_exclusive_and_default_remains_current() -> None:
    client = _LockClient()
    with pytest.raises(CliRefusedBoundaryError):
        _lock_result(client, all_sessions=True, session=uuid4())
    assert client.calls == []
    current_id = client.session_id
    current = _lock_result(client, all_sessions=False, session=None)
    assert current.scope == "current"
    assert current.target_session_id is None
    assert current.session_ids == (current_id,)
    assert client.calls == ["current"]
    global_result = _lock_result(client, all_sessions=True, session=None)
    assert global_result.scope == "profile"
    assert global_result.denial is not None
    assert client.calls[-1] == AutomationDenialKind.PROFILE_LOCK.value
