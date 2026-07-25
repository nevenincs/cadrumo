"""Capability-selecting presenter for the profile manager.

This is the entrypoint seam that lets ``aeat config profile create`` and
``edit`` open the full-screen profile manager on a capable terminal, while
the scripted arms of those same verbs (``--quiet`` / ``--accept-defaults``,
and any invocation carrying explicit field flags) keep running the
non-interactive wizard path unchanged.

The split matters. An operator at a real terminal wants the manager: their
whole profile on one page, every field editable, nothing gated. A script
or an agent wants flags and a JSON envelope, with no screen at all. Both
are the same verb because they are the same intent; only the presentation
differs, which is exactly the distinction this module owns and neither the
application layer nor the manager screen needs to know about.

See Also:
    :mod:`cadrumo.entrypoints.cli._config._setup_flow_frontend`
        The sibling seam for the paged flow, same shape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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


def present_profile_manager(*, label: str | None = None) -> None:
    """Open the manager on the active profile and run it to completion.

    The manager persists each edit as it is made, so there is nothing to
    return: by the time this call comes back, every change the operator
    made is already on the encrypted record.
    """
    from ....adapters.inbound.tui import run_profile_manager_tui

    run_profile_manager_tui(build_active_profile_overview(label=label))


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

    return run_registration_tui(suggested_name=suggested_name)


__all__ = [
    "build_active_profile_overview",
    "host_can_run_full_screen",
    "manager_is_the_right_frontend",
    "present_profile_manager",
    "present_registration",
]
