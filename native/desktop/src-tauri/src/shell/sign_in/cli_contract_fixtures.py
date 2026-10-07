"""Produce Rust test inputs with the canonical CLI models and error renderer.

Run with the repository Python environment; --check detects producer drift.
No runtime, profile, receipt, credential, or application build is required.
"""

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.sign_in import SignInPresence, SignInStatus
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.application.user_profile.login_session import ProfileLoginThrottledError
from cadrumo.application.user_profile.registration import ProfileRegistrationError
from cadrumo.application.user_profile.sign_in_refusals import SignInRefusal
from cadrumo.application.wizard.results import ConfigProfileCreateResult, ProfileWizardStatus
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import render_error_json
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.json_contract import EnvelopeStatus, Notice, NoticeSeverity, SchemaEnvelope
from cadrumo.entrypoints.cli._modelo_rendering import advisory_notice
from cadrumo.entrypoints.cli.config.custody_payloads import (
    ConfigLoginResult,
    ConfigLogoutResult,
    ConfigSignInStatusResult,
)
from cadrumo.entrypoints.cli.config.profile_list_payloads import ConfigListResult, ProfilePointerPayload
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError


def documents() -> dict[str, object]:
    """Exercise producer casing, stringified contexts and typed result defaults."""
    profile = "11111111-1111-4111-8111-111111111111"
    stamp = datetime(2026, 10, 5, 12, tzinfo=UTC)
    cases: dict[str, object] = {}

    def failure(name: str, leaf: str, error: Exception) -> None:
        cases[name] = json.loads(render_error_json(error, command=f"config.{leaf}", active_profile="Test profile"))

    def frontend_failure(name: str, code: str, sign_in: SignInRefusal | None = None) -> None:
        error = RuntimeFrontendRefusedError(code, sign_in=sign_in)
        # config.custody._login_through_the_prompt forwards this exact context.
        failure(name, "login", CliRefusedBoundaryError(error.reason, context=error.context))

    frontend_failure("credential-rejected", AutomationCustodyCode.CREDENTIAL_REJECTED.value)
    frontend_failure(
        "runtime-throttled",
        AccessDenialCode.AUTHENTICATION_REQUIRED.value,
        SignInRefusal(reason="throttled", remaining_seconds=23),
    )
    frontend_failure("authentication-required", AccessDenialCode.AUTHENTICATION_REQUIRED.value)
    failure("direct-throttled", "login", ProfileLoginThrottledError(remaining_seconds=7))
    failure("runtime-unavailable", "sign-in-status", RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE))
    failure("runtime-untrusted", "sign-in-status", RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED))
    failure("logout-refused", "logout", CliRefusedBoundaryError(context={"reason": "absent"}))

    for presence in SignInPresence:
        status = SignInStatus(
            presence=presence,
            idle_deadline=stamp if presence is SignInPresence.PRESENT else None,
            absolute_deadline=stamp + timedelta(hours=1) if presence is SignInPresence.PRESENT else None,
        )
        cases[f"status-{presence.value}"] = SchemaEnvelope(
            command="config.sign-in-status",
            active_profile="Test profile",
            status=EnvelopeStatus.SUCCESS,
            result=ConfigSignInStatusResult(profile_id=profile, status=status),
        ).model_dump(mode="json")
    for persisted in (True, False):
        cases[f"login-{str(persisted).lower()}"] = SchemaEnvelope(
            command="config.login",
            active_profile="Test profile",
            status=EnvelopeStatus.SUCCESS if persisted else EnvelopeStatus.WARNING,
            result=ConfigLoginResult(
                profile_id=profile,
                active_profile="Test profile",
                authenticated_at=stamp,
                idle_deadline=stamp + timedelta(hours=1),
                absolute_deadline=stamp + timedelta(hours=2),
                session_persisted=persisted,
                already_authenticated=False,
            ),
        ).model_dump(mode="json")
    for automation in (True, False, None):
        cases[f"logout-{str(automation).lower()}"] = SchemaEnvelope(
            command="config.logout",
            active_profile="Test profile",
            status=EnvelopeStatus.SUCCESS,
            result=ConfigLogoutResult(
                logged_out_profile="Test profile",
                already_logged_out=False,
                human_receipt_revoked=True,
                receipt_removed=True,
                keychain_removed=True,
                automation_enabled=automation,
            ),
        ).model_dump(mode="json")
    other = "22222222-2222-4222-8222-222222222222"
    rows = [
        ProfilePointerPayload(name="Another profile", bucket_id=other, active=False),
        ProfilePointerPayload(name="Test profile", bucket_id=profile, active=True),
    ]
    cases["profile-list"] = SchemaEnvelope(
        command="config.profile.list",
        active_profile="Test profile",
        status=EnvelopeStatus.SUCCESS,
        result=ConfigListResult(active_profile="Test profile", profiles=rows),
    ).model_dump(mode="json")
    cases["profile-list-empty"] = SchemaEnvelope(
        command="config.profile.list",
        active_profile=None,
        status=EnvelopeStatus.SUCCESS,
        result=ConfigListResult(active_profile=None, profiles=[]),
    ).model_dump(mode="json")
    # config.profile_list_cli reports a degraded or concurrent observation as
    # no rows under this notice.
    cases["profile-list-incoherent"] = SchemaEnvelope(
        command="config.profile.list",
        active_profile=None,
        status=EnvelopeStatus.WARNING,
        result=ConfigListResult(active_profile=None, profiles=[]),
        notices=[
            advisory_notice(
                "config.profile.list.incoherent_observation",
                "The profile listing could not be trusted.",
                context={"outcome": "degraded", "detail": ""},
            )
        ],
    ).model_dump(mode="json")
    cases["profile-create"] = SchemaEnvelope(
        command="config.profile.create",
        active_profile="Test profile",
        status=EnvelopeStatus.WARNING,
        result=ConfigProfileCreateResult(
            profile_name="Test profile",
            status=ProfileWizardStatus.CREATED,
            active_profile="Test profile",
        ),
        notices=[
            Notice(code="PROFILE_LOGIN_REQUIRED", severity=NoticeSeverity.WARNING, message="Sign in to the profile.")
        ],
    ).model_dump(mode="json")
    # registration._refuse_a_label_already_taken raises exactly this.
    failure(
        "profile-create-taken",
        "profile.create",
        ProfileRegistrationError(
            translated_message="application.user_profile.errors.profile_already_exists",
            context={"profile": "Test profile"},
        ),
    )
    failure(
        "profile-create-short-password",
        "profile.create",
        ProfileRegistrationError(
            translated_message="application.user_profile.errors.profile_password_too_few_scalars",
            context={"reason": "too_few_scalars", "scalar_count": 5, "utf8_byte_count": 5, "minimum_scalars": 8},
        ),
    )
    failure("profile-create-boundary", "profile.create", CliRefusedBoundaryError())
    return cases


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = Path(__file__).with_suffix(".json")
    with override_settings(cadrumo_output_language=OutputLanguage.EN):
        rendered = json.dumps(documents(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.check:
        if target.read_text(encoding="utf-8") != rendered:
            raise SystemExit("CLI contract fixtures are stale; regenerate before running the Rust contract tests")
        sys.stdout.write("CLI contract fixtures match canonical producers\n")
    else:
        target.write_text(rendered, encoding="utf-8", newline="\n")
