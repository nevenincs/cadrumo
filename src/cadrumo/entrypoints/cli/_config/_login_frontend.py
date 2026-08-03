"""Capability-selecting presenter for ``aeat config login``.

``login`` serves two callers through one verb. A script, an agent, or a
CI job names the profile, pipes the secret in, or configures the headless
secret channel, and wants a JSON envelope with no screen at all. An
operator at a terminal typing ``aeat config login`` on its own wants to
be shown which profiles exist, pick one, and type its password — the same
page they met when the profile was created.

Only the second gets a screen, and the split is decided here rather than
in the command body so the rule is one pure predicate that can be
exercised without a terminal a test host cannot provide. Every arm that
is not that exact bare interactive invocation falls through to the
existing path untouched: the same ``getpass`` prompt, the same
``--secrets-stdin`` channel, the same non-interactive refusal.

This seam also owns the translation between the application's refusal
exceptions and the text the screen shows, which is what keeps the adapter
tier from having to import — and recognise — the application's error
types.

See Also:
    :func:`~cadrumo.application.user_profile.login_profile`
        The one door both arms drive. It owns target resolution, the
        previous session's close, the idempotent no-op, the failed-attempt
        backoff, the unwrap, and the session it mints; nothing here
        re-implements any of that.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._common import _format_of

if TYPE_CHECKING:
    import typer

    from ....adapters.inbound.tui import LoginAttempt, LoginChoice
    from ....application.user_profile import ProfileLoginOutcome


def login_tui_is_the_right_frontend(
    *,
    named: bool,
    secrets_stdin: bool,
    headless_secret: bool,
    json_format: bool,
    full_screen: bool,
    profile_count: int,
) -> bool:
    """Whether this ``login`` invocation should open the screen.

    Pure, so the routing rule is provable without a terminal.

    Degradation is total rather than graceful: every condition below
    means some other caller has already answered the question the screen
    exists to ask, so the screen would either strand their answer or
    block a host that cannot type into it.

    - ``named`` — the operator already said which profile, so the chooser
      has nothing to choose and today's prompt is the shorter path.
    - ``secrets_stdin`` — the password has already arrived on the bounded
      stdin channel; there is nothing left to type.
    - ``headless_secret`` — ``CADRUMO_SECRET_PASSPHRASE`` is the sanctioned
      non-interactive channel and supplies the factor without any prompt.
    - ``json_format`` — a machine is reading; a screen would write over
      the envelope it is waiting for.
    - ``full_screen`` — a piped, dumb-terminal, or CI host has no screen
      to show, and this is the check that keeps it from blocking on one.
    - ``profile_count`` — with nothing registered there is nothing to log
      in to, and the existing path already refuses that with the envelope
      and exit code a caller expects.
    """
    return not (named or secrets_stdin or headless_secret or json_format or not full_screen or profile_count == 0)


def login_screen_is_available(ctx: typer.Context, *, name: str | None, secrets_stdin: bool) -> bool:
    """Resolve the routing predicate against this host and this storage root.

    Kept separate from the predicate it feeds so the rule stays pure and
    only the gathering of its inputs touches the environment.
    """
    from .. import _headless_secret_channel_active
    from ._manager_frontend import host_can_run_full_screen

    return login_tui_is_the_right_frontend(
        named=name is not None,
        secrets_stdin=secrets_stdin,
        headless_secret=_headless_secret_channel_active(),
        json_format=_format_of(ctx) == "json",
        full_screen=host_can_run_full_screen(),
        profile_count=len(_login_choices()),
    )


def _login_choices() -> tuple[LoginChoice, ...]:
    """The live profiles, in the order the operator sees them.

    Read through the plaintext manifest scan, which is the only listing
    available before anything is unlocked — the whole point of this screen
    is that no bucket is open yet.
    """
    from ....adapters.inbound.tui import LoginChoice
    from ....application.workflow import list_profile_buckets

    return tuple(
        LoginChoice(profile_id=pointer.bucket_id, label=pointer.label)
        for pointer in sorted(list_profile_buckets().values(), key=lambda pointer: pointer.label.casefold())
    )


def attempt_login(profile_id: str, passphrase: str) -> LoginAttempt:
    """Unlock one profile, reporting a refusal as text rather than raising.

    Classifying a refusal is the application layer's job and displaying it
    is the screen's; translating between the two is this seam's.

    The guarded surface is deliberately the refusal family rather than a
    single wrong-password class: a throttled attempt, an unknown target,
    and a locked keychain are all things the operator can act on from the
    page they are standing on, and each carries its own message. An error
    outside that family is a defect, not an operator state, and is left to
    propagate so it is not laundered into a refusal line.
    """
    from ....adapters.inbound.tui import LoginAttempt
    from ....adapters.persistence.storage import SecretStoreError
    from ....application.user_profile import (
        ProfileLoginThrottledError,
        login_profile,
    )
    from ....core.errors import resolve_error_message
    from ....domain.user_profile import ProfileNotFoundError

    try:
        outcome = login_profile(name=profile_id, passphrase_callback=lambda: passphrase)
    except (SecretStoreError, ProfileLoginThrottledError, ProfileNotFoundError) as refusal:
        # The error's own translated message, not a re-derived one: the
        # layer that refused is the one that knows why, and a second
        # wording here would drift from the one the non-TUI arm renders.
        return LoginAttempt(refusal=resolve_error_message(refusal))
    return LoginAttempt(outcome=outcome)


def present_login() -> ProfileLoginOutcome | None:
    """Run the login screen and return the session it opened, or ``None``.

    ``None`` means the operator left without logging in, which the caller
    reports as a refusal rather than a success: ``login`` is a
    precondition verb, so an exit code saying it worked when no session
    was minted is the one answer a script must never be given.
    """
    from ....adapters.inbound.tui import run_login_tui
    from ....core import resolve_active_bucket_id

    return run_login_tui(
        choices=_login_choices(),
        authenticate=attempt_login,
        preselected=resolve_active_bucket_id(),
    )


__all__ = [
    "attempt_login",
    "login_screen_is_available",
    "login_tui_is_the_right_frontend",
    "present_login",
]
