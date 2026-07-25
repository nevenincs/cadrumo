"""Capability-selecting presenter for the profile manager.

This is the entrypoint seam that lets ``aeat config profile create`` and
``edit`` open the full-screen profile manager on a capable terminal, while
the scripted arms of those same verbs (``--quiet`` / ``--accept-defaults``,
and any invocation carrying explicit field flags) run the programmatic
path and emit a JSON envelope.

The split matters. An operator at a real terminal wants the manager: their
whole profile on one page, every field editable, nothing gated. A script
or an agent wants flags and an envelope, with no screen at all. Both are
the same verb because they are the same intent; only the presentation
differs, which is exactly the distinction this module owns and neither the
application layer nor the manager screen needs to know about.

There is no third route. The paged interactive walk these verbs used to
fall back to is retired, so a host that can present neither the manager
nor a screen at all is refused with the flag form named.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from ....adapters.inbound.tui import FormPage, RegistrationAttempt
    from ....application.user_profile import ProfileOverview, ProfileRegistrationOutcome


def manager_is_the_right_frontend(
    *,
    mode: str,
    scripted: bool,
    explicit_fields: bool,
    full_screen: bool,
) -> bool:
    """Whether this invocation should open the manager instead of the wizard.

    Pure, so the routing rule can be exercised directly rather than only
    through a terminal that a test host cannot provide.

    **Every** interactive invocation on a capable host gets the manager.
    There is exactly one interactive surface for managing a profile, and
    the paged setup flow is not it — leaving the old flow reachable for
    some interactive invocations meant two competing answers to the same
    question, which is the parallel-authority failure the architecture
    rules exist to prevent. A supplied profile name does NOT change this:
    it prefills the registration screen's name field.

    What still belongs to the flow is the genuinely non-interactive
    contract, which is a different thing rather than a competing screen:

    - ``scripted`` (``--quiet`` / ``--accept-defaults``) explicitly asks
      for the headless path and its JSON envelope.
    - ``explicit_fields`` means the caller already knows what to set;
      opening a screen would strand those values.
    - a host that cannot go full-screen has no manager to show.
    """
    return not (scripted or explicit_fields or not full_screen)


def host_can_run_full_screen() -> bool:
    """Whether this host can host a full-screen Textual application.

    Reuses the flow substrate's capability probe rather than re-deriving
    terminal detection, so the manager and the paged flow agree about what
    counts as an interactive host.
    """
    from ....application.flows import detect_frontend_capability
    from ....core.flows import FrontendCapability

    return detect_frontend_capability() is FrontendCapability.FULL_SCREEN


def build_active_profile_overview(*, label: str | None = None) -> ProfileOverview:
    """Build the manager's page for whichever profile is currently active."""
    from ....application.user_profile import ProfileRepository, build_profile_overview
    from ....core import require_active_bucket_id

    aggregate = ProfileRepository().load(require_active_bucket_id())
    return build_profile_overview(
        aggregate.record,
        label=label if label is not None else aggregate.label,
    )


def persist_active_profile_field(path: str, value: str, *, label: str | None = None) -> ProfileOverview:
    """Write one profile field and return the page as storage now holds it.

    A blank submission clears the fact rather than storing an empty string,
    so "I did not mean to set this" and "this is empty" stay one state
    instead of drifting into two.

    The page is rebuilt by re-reading the record rather than by patching
    the previous view: the edit door may normalise or refuse a value, and
    the operator must see what was actually stored.
    """
    from ....application.user_profile import set_active_field
    from ....application.workflow import workflow_state_repository
    from ....domain.user_profile import UserProfileFact

    fact = UserProfileFact(path=path, value=value if value != "" else None)
    workflow_state_repository().update(lambda state: set_active_field(state, fact))
    return build_active_profile_overview(label=label)


def present_profile_manager(*, label: str | None = None) -> None:
    """Open the manager on the active profile and run it to completion.

    The manager persists each edit as it is made, so there is nothing to
    return: by the time this call comes back, every change the operator
    made is already on the encrypted record.
    """
    from ....adapters.inbound.tui import run_profile_manager_tui

    run_profile_manager_tui(
        build_active_profile_overview(label=label),
        persist=lambda path, value: persist_active_profile_field(path, value, label=label),
    )


def present_form(
    page: FormPage,
    *,
    rebuild: Callable[[Mapping[str, str]], FormPage] | None = None,
) -> Mapping[str, str] | None:
    """Show one editable field page and return what the operator committed.

    ``None`` means they left without committing, which every caller treats
    as "make no change" rather than as an error.
    """
    from ....adapters.inbound.tui import run_form_tui

    return run_form_tui(page, rebuild=rebuild)


def attempt_registration(label: str, passphrase: str) -> RegistrationAttempt:
    """Create one profile, reporting a refusal as text rather than raising.

    Classifying a refusal is the application layer's job and displaying it
    is the screen's; translating between the two is this seam's. That is
    what keeps the screen from having to import — and recognise — the
    application's exception types.
    """
    from ....adapters.inbound.tui import RegistrationAttempt as _Attempt
    from ....application.user_profile import (
        ProfileAlreadyRegisteredError,
        ProfileRegistrationError,
        register_profile_with_credentials,
    )

    try:
        outcome = register_profile_with_credentials(label=label, passphrase=passphrase)
    except (ProfileRegistrationError, ProfileAlreadyRegisteredError) as refusal:
        return _Attempt(refusal=str(refusal))
    return _Attempt(outcome=outcome)


def present_registration(*, suggested_name: str | None = None) -> ProfileRegistrationOutcome | None:
    """Run the credential-first registration screen.

    ``suggested_name`` prefills the name field from a profile name given on
    the command line. It is a prefill, not a commitment: the operator can
    still change it, because the screen is where the decision is made.

    Returns the created profile, or ``None`` when the operator left without
    creating one — an ordinary outcome the caller reports as a no-op rather
    than an error.
    """
    from ....adapters.inbound.tui import run_registration_tui
    from ....application.user_profile import assess_passphrase

    return run_registration_tui(
        assess=assess_passphrase,
        register=attempt_registration,
        suggested_name=suggested_name,
    )


__all__ = [
    "attempt_registration",
    "build_active_profile_overview",
    "host_can_run_full_screen",
    "manager_is_the_right_frontend",
    "persist_active_profile_field",
    "present_form",
    "present_profile_manager",
    "present_registration",
]
