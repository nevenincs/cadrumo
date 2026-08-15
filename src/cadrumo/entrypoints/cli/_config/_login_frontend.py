"""Capability-selecting presenter for ``aeat config login``.

``login`` serves two callers through one verb. A script, an agent, or a
CI job pipes the secret in, configures the headless secret channel, or
reads the JSON envelope, and wants no screen at all. An operator at a
terminal wants to be shown which profiles exist, pick one, and type its
password — the same page they met when the profile was created.

Only the second gets a screen, and the split is decided here rather than
in the command body so the rule is one pure predicate that can be
exercised without a terminal a test host cannot provide.

Naming a target is NOT part of that split. The page is a chooser AND the
password form, and naming a profile answers only the chooser half, so a
named target preselects its row instead of discarding the page. Routing
on it used to send the commonest interactive invocation —
``aeat config login <profile>`` — to a line prompt, and that prompt is
strictly worse than the page it skipped: with no callback supplied,
``login_profile`` falls through to the storage substrate's own resolver,
which ends at a bare :func:`getpass.getpass` carrying an untranslated
English prompt and an *echoing* fallback whenever it cannot control the
terminal. Every other custody secret in this package is read through
``prompt_secret_no_echo``, which promotes that failure to a refusal.

Every arm that genuinely cannot show a screen still falls through to the
existing path untouched: the same ``--secrets-stdin`` channel, the same
headless secret, the same non-interactive refusal.

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
    machine_secret_supplied: bool,
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

    - ``machine_secret_supplied`` — the password has already arrived on a
      bounded machine channel, either the stdin object or the one-shot
      descriptor; there is nothing left to type. The two are one condition
      here because the screen's question is "has the factor been supplied",
      not "through which pipe".
    - ``headless_secret`` — ``CADRUMO_SECRET_PASSPHRASE`` is the sanctioned
      non-interactive channel and supplies the factor without any prompt.
    - ``json_format`` — a machine is reading; a screen would write over
      the envelope it is waiting for.
    - ``full_screen`` — a piped, dumb-terminal, or CI host has no screen
      to show, and this is the check that keeps it from blocking on one.
    - ``profile_count`` — with nothing registered there is nothing to log
      in to, and the existing path already refuses that with the envelope
      and exit code a caller expects.

    A named target is deliberately absent from that set: it answers which
    profile, which the page accepts as a preselection, and it leaves the
    password — the whole reason the page exists — still to be typed. See
    :func:`preselected_profile_id`.
    """
    return not (machine_secret_supplied or headless_secret or json_format or not full_screen or profile_count == 0)


def login_screen_is_available(ctx: typer.Context, *, secrets_stdin: bool, secrets_fd: int | None = None) -> bool:
    """Resolve the routing predicate against this host and this storage root.

    Kept separate from the predicate it feeds so the rule stays pure and
    only the gathering of its inputs touches the environment.
    """
    from .. import _headless_secret_channel_active
    from ._manager_frontend import host_can_run_full_screen

    return login_tui_is_the_right_frontend(
        machine_secret_supplied=secrets_stdin or secrets_fd is not None,
        headless_secret=_headless_secret_channel_active(),
        json_format=_format_of(ctx) == "json",
        full_screen=host_can_run_full_screen(),
        profile_count=len(_login_choices()),
    )


def preselected_profile_id(name: str | None) -> str | None:
    """Which row the screen opens on, for an optionally-named target.

    An unnamed invocation opens on the active profile, which is what the
    operator almost always means and what the page already defaults to.

    A named one goes through
    :func:`~cadrumo.application.user_profile.resolve_login_target` — the
    very resolver ``login_profile`` applies to the same argument on the
    prompt arm, rather than a second reading of it here. That matters
    beyond tidiness: it is what makes the screen agree with the prompt on
    the surrounding whitespace it tolerates, on a bare sandbox short name
    being unknown rather than implicitly namespaced, and on the exact
    refusal an unknown target renders.

    An unknown target is therefore refused HERE, before the screen opens.
    The page falls back to its first row for a preselection it does not
    recognise, which is right for a stale pointer but wrong for something
    the operator typed: a mistyped label would otherwise open somebody
    else's profile with no sign the name had been ignored.
    """
    from ....application.user_profile import resolve_login_target
    from ....core import resolve_active_bucket_id

    if name is None:
        return resolve_active_bucket_id()
    return resolve_login_target(name).bucket_id


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


def present_login(*, preselected: str | None) -> ProfileLoginOutcome | None:
    """Run the login screen and return the session it opened, or ``None``.

    ``None`` means the operator left without logging in, which the caller
    reports as a refusal rather than a success: ``login`` is a
    precondition verb, so an exit code saying it worked when no session
    was minted is the one answer a script must never be given.

    ``preselected`` is required rather than defaulted so the caller states
    which row opens selected. It carried the active profile implicitly
    before a named target could reach this screen at all; leaving that as
    a default would have let a caller silently drop the operator's named
    target and land on the active profile instead — the exact misroute
    :func:`preselected_profile_id` exists to prevent.
    """
    from ....adapters.inbound.tui import run_login_tui

    return run_login_tui(
        choices=_login_choices(),
        authenticate=attempt_login,
        preselected=preselected,
    )


def offer_login_to_a_gated_verb(ctx: typer.Context, *, bucket_id: str) -> ProfileLoginOutcome | None:
    """Present the login screen to a verb that met the session gate.

    Returns the session the operator opened, or ``None`` when no screen
    could be shown or they left without unlocking — in both cases the
    caller falls back to the refusal it would have raised anyway, so a
    verb never proceeds unauthenticated and a caller that cannot show a
    screen keeps its exact refusal and exit code.

    The gate exists because the alternative costs the operator two extra
    commands and buys nothing: refusing, having them run ``login``, and
    having them retype the invocation the CLI already parsed asks for the
    same single passphrase this screen asks for. What it does NOT do is
    unlock without an authentication act — that implicit unlock is what
    the login-session decision retired, and this is its opposite: a page
    that names the profile and demands the secret.

    The screen opens on the profile the verb was already addressing, so
    the common case is a password and nothing else. The chooser stays
    live because the operator who discovers at the gate that they are on
    the wrong profile would otherwise have to leave, switch, and come
    back; the caller is responsible for re-pointing the active profile
    when they do pick another one.
    """
    if not login_screen_is_available(ctx, secrets_stdin=False):
        return None
    return present_login(preselected=preselected_profile_id(bucket_id))


__all__ = [
    "attempt_login",
    "login_screen_is_available",
    "login_tui_is_the_right_frontend",
    "offer_login_to_a_gated_verb",
    "preselected_profile_id",
    "present_login",
]
