"""CLI selection seam for interactive profile presentation."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from ....application.user_profile import ProfileRecoveryEnrollment, ProfileRegistrationOutcome
    from ....core.presentation import FormPage
    from ....entrypoints.tui.secret.registration import RegistrationAttempt


_ROUTING_META_KEYS = frozenset(
    {
        "ctx",
        "profile_name",
        "quiet",
        "accept_defaults",
        "tui",
        "secrets_stdin",
        "secrets_fd",
        "recovery_handoff_fd",
        "recovery_verification_fd",
    }
)


def _field_value_was_supplied(value: object) -> bool:
    """Return whether a parsed wizard value represents an explicit flag."""
    if value is None:
        return False
    if isinstance(value, list | tuple):
        items = cast(list[object] | tuple[object, ...], value)
        return any(str(item) for item in items)
    return True


def has_explicit_profile_fields(kwargs: Mapping[str, object]) -> bool:
    """Whether parsed wizard kwargs contain a field the caller supplied."""
    return any(_field_value_was_supplied(value) for key, value in kwargs.items() if key not in _ROUTING_META_KEYS)


def manager_is_the_right_frontend(
    *,
    mode: str,
    scripted: bool,
    explicit_fields: bool,
    full_screen: bool,
    tui_requested: bool = False,
) -> bool:
    """Whether this invocation selects the dedicated profile manager."""
    del mode
    return not (scripted or explicit_fields) and (tui_requested or full_screen)


def host_can_run_full_screen() -> bool:
    """Whether this host can host a full-screen application."""
    from ....application.flows import detect_frontend_capability
    from ....core.flows import FrontendCapability

    return detect_frontend_capability() is FrontendCapability.FULL_SCREEN


def present_profile_manager(*, label: str | None = None) -> None:
    """Open the profile manager for the active profile."""
    from ....application.user_profile.manager_projection import (
        open_active_profile_manager_projection,
        profile_manager_field_value_refusal,
    )
    from ....entrypoints.tui.profile.overview import run_profile_manager_tui

    manager = open_active_profile_manager_projection(label=label)
    run_profile_manager_tui(
        manager.inspect(),
        persist=manager.replace_field,
        validate=profile_manager_field_value_refusal,
    )


def present_form(
    page: FormPage,
    *,
    rebuild: Callable[[Mapping[str, str]], FormPage] | None = None,
) -> Mapping[str, str] | None:
    """Show one editable field page and return what the operator committed."""
    from ....entrypoints.tui.components.form_screen import active_form_presenter, run_form_tui

    presenter = active_form_presenter()
    if presenter is not None:
        return presenter(page, rebuild)
    from ....core.i18n import tr

    return run_form_tui(page, translate=tr, rebuild=rebuild)


def attempt_registration(
    label: str,
    passphrase: str,
    output_language: str,
    recovery_handover: Callable[[ProfileRecoveryEnrollment], str],
) -> RegistrationAttempt:
    """Create one profile, reporting an expected refusal as presentation data."""
    from ....application.user_profile import ProfileRegistrationError, register_profile_with_credentials
    from ....domain.user_profile import UserProfileFact
    from ....entrypoints.tui.secret.registration import (
        RecoveryHandoverCancelledError,
        RegistrationAttempt,
        RegistrationRefusal,
    )

    try:
        outcome = register_profile_with_credentials(
            label=label,
            passphrase=passphrase,
            facts=(UserProfileFact(path="preferences.output_language", value=output_language),),
            recovery_handover=recovery_handover,
        )
    except RecoveryHandoverCancelledError:
        return RegistrationAttempt(
            expected_refusal=RegistrationRefusal(
                message_key="cli.config.profile.create_recovery_verification_cancelled",
            )
        )
    except ProfileRegistrationError as refusal:
        if refusal.translated_message is None:
            raise
        return RegistrationAttempt(
            expected_refusal=RegistrationRefusal(
                message_key=refusal.translated_message,
                context=tuple((refusal.context or {}).items()),
            )
        )
    return RegistrationAttempt(outcome=outcome)


def present_registration(*, suggested_name: str | None = None) -> ProfileRegistrationOutcome | None:
    """Run the credential-first registration screen."""
    from ....core import assess_profile_password
    from ....entrypoints.tui.secret.registration import run_registration_tui

    return run_registration_tui(
        assess=assess_profile_password,
        register=attempt_registration,
        suggested_name=suggested_name,
    )


__all__ = [
    "attempt_registration",
    "has_explicit_profile_fields",
    "host_can_run_full_screen",
    "manager_is_the_right_frontend",
    "present_form",
    "present_profile_manager",
    "present_registration",
]
