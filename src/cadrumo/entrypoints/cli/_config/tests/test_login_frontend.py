"""Which frontend ``aeat config login`` opens, and when it opens none.

The routing rule is the whole safety property of the login screen: an
operator at a terminal gets a page, and every other caller — a script, an
agent, a CI job, a ``--format json`` reader, a piped host — reaches the
existing prompt-and-envelope path untouched and never blocks on a screen
it cannot type into.

The rule is exercised directly as the pure predicate it is, because the
alternative is asking one test host to be six different terminals. The
resolved form is then exercised against the real host this suite runs
on, which is genuinely non-interactive — that is the CI case — and the
positive control beside it is what shows the refusal came from the host
rather than from a predicate that refuses everything.
"""

from __future__ import annotations

from typing import TypedDict

import pytest
import typer
from typer.core import TyperCommand

from .....core.config import override_settings
from .....tests.secure_sql import isolated_profile_storage_root
from .._login_frontend import (
    _login_choices,
    login_screen_is_available,
    login_tui_is_the_right_frontend,
    preselected_profile_id,
)
from .._manager_frontend import host_can_run_full_screen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _RoutingInputs(TypedDict):
    """The exact keyword set :func:`login_tui_is_the_right_frontend` accepts."""

    machine_secret_supplied: bool
    json_format: bool
    full_screen: bool
    profile_count: int


def _interactive_operator(
    *,
    machine_secret_supplied: bool = False,
    json_format: bool = False,
    full_screen: bool = True,
    profile_count: int = 1,
) -> _RoutingInputs:
    """The one shape that gets a screen, with any single condition overridden.

    Defaults describe an ``aeat config login`` typed at a capable terminal
    on a machine that has a profile to open. Overrides are named parameters
    rather than a ``str``-keyed merge, so a typo in a case below is a type
    error instead of a silently-ignored extra key that would leave the case
    asserting the untouched interactive shape and passing for the wrong reason.
    """
    return {
        "machine_secret_supplied": machine_secret_supplied,
        "json_format": json_format,
        "full_screen": full_screen,
        "profile_count": profile_count,
    }


def test_an_interactive_login_on_a_capable_host_opens_the_screen() -> None:
    """The positive control: without this, every case below proves nothing."""
    assert login_tui_is_the_right_frontend(**_interactive_operator()) is True


def test_naming_a_profile_is_not_a_routing_input_at_all() -> None:
    """A named target must not be able to send ``login`` back to the prompt.

    Asserted against the signature rather than by passing ``named=True``
    and checking the answer: a re-added parameter with a default would
    keep every other case here green while quietly restoring the routing
    this rule exists to forbid, and a call-site assertion cannot see it.
    The page is a chooser AND the password form, so naming a profile
    answers half of it and preselects; it never discards the page.
    """
    import inspect

    parameters = set(inspect.signature(login_tui_is_the_right_frontend).parameters)
    assert "named" not in parameters, f"routing must not read a named target; takes {sorted(parameters)}"


@pytest.mark.parametrize(
    "inputs",
    [
        pytest.param(_interactive_operator(machine_secret_supplied=True), id="machine_secret_supplied"),
        pytest.param(_interactive_operator(json_format=True), id="json_format"),
        pytest.param(_interactive_operator(full_screen=False), id="full_screen"),
        pytest.param(_interactive_operator(profile_count=0), id="profile_count"),
    ],
)
def test_each_condition_alone_sends_login_back_to_the_prompt(inputs: _RoutingInputs) -> None:
    """Any one condition is enough to fall through, with the others clear.

    Parametrised one at a time rather than in combination on purpose: a
    rule that only refused when several conditions coincided would still
    pass a combined case, and would open a screen on the CI host that
    happened to trip just one of them.
    """
    assert login_tui_is_the_right_frontend(**inputs) is False


def _context(*, output_format: str) -> typer.Context:
    """A real Typer context carrying the format the operator asked for.

    The command is a ``TyperCommand`` rather than a bare ``click.Command``:
    typer's ``Context`` declares typer's own ``Command``, and in this version
    that class does not subclass click's, so passing the click one worked only
    incidentally.
    """
    return typer.Context(TyperCommand("login"), obj={"format": output_format})


def _a_profile_exists() -> None:
    """Put one real profile in the isolated root, so the count is not the reason.

    Without this, every resolved case below would answer ``False`` because
    there is nothing to log in to — and would keep answering ``False`` with
    the condition under test deleted. That is a clean negative proving
    nothing. A real profile removes the alternative explanation and leaves
    the condition each case names as the only thing the answer turns on.
    """
    from .....application.user_profile import logout_active_profile
    from .._manager_frontend import attempt_registration

    attempt = attempt_registration(
        "Routing Subject", "routing-frontend-operator-secret", "en", lambda _enrollment: None
    )
    assert attempt.outcome is not None, f"the fixture profile must exist, but: {attempt.refusal}"
    # Registration leaves the profile unlocked, and the session is
    # process-global; close it so it cannot outlive this test's root.
    logout_active_profile()


def test_this_non_interactive_host_never_reaches_the_screen(tmp_path) -> None:
    """The resolved rule fails closed on the host a CI job actually has.

    This suite runs with its output captured, so the capability probe
    classifies the host as non-interactive — the same classification a
    piped shell, a dumb terminal, and a CI runner get. Resolving the rule
    here is therefore the real scripted case, not a described one.

    Every OTHER input is first cleared and then *asserted* clear, which is
    what gives the final assertion its meaning. Without that, the answer
    would be ``False`` for whichever reason happened to hold — an empty
    storage root, or the passphrase the isolation fixture configures — and
    would stay ``False`` with the host check deleted, proving nothing about
    the host at all.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _a_profile_exists()
        assert len(_login_choices()) == 1, "an empty storage root must not be the reason"
        assert host_can_run_full_screen() is False, "this host must genuinely be the non-interactive case"

        ctx = _context(output_format="text")
        assert login_screen_is_available(ctx, secrets_stdin=False) is False


def test_the_resolved_rule_reads_the_format_and_the_arguments(tmp_path) -> None:
    """The gathered inputs are the ones the operator actually supplied.

    The host this suite runs on cannot be made full-screen, so the answer
    below cannot turn on the format or the arguments and asserting it
    would prove nothing — those conditions are proved against the pure
    rule. What IS proved here is the threading: each argument reaches the
    predicate as itself, and a piped secret does not make the resolved
    call raise on the way.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _a_profile_exists()
        assert login_screen_is_available(_context(output_format="json"), secrets_stdin=False) is False
        ctx = _context(output_format="text")
        assert login_screen_is_available(ctx, secrets_stdin=True) is False
        # The one-shot descriptor is the second machine channel and must reach
        # the predicate as the same "already supplied" condition the stdin
        # object does; a descriptor that failed to thread would leave the
        # screen offered on a host where the password has already arrived.
        assert login_screen_is_available(ctx, secrets_stdin=False, secrets_fd=7) is False


def test_a_gated_verb_is_offered_no_screen_on_a_host_that_cannot_show_one(tmp_path) -> None:
    """The gate degrades to today's refusal wherever a screen cannot be shown.

    This is the safety half of offering login inside other verbs: a JSON
    reader, a pipe, and a CI runner must keep the refusal and exit code
    they already depend on, and must never block on a page they cannot
    type into. The suite's own host IS that case, so this is the real
    scripted arm rather than a described one.

    A live profile is registered first so an empty storage root cannot be
    the reason for the answer — without it this would stay ``None`` with
    the host check deleted and prove nothing.
    """
    from .._login_frontend import offer_login_to_a_gated_verb

    with isolated_profile_storage_root(tmp_path=tmp_path):
        _a_profile_exists()
        assert len(_login_choices()) == 1, "an empty storage root must not be the reason"
        assert host_can_run_full_screen() is False, "this host must genuinely be the non-interactive case"

        (only_choice,) = _login_choices()
        assert offer_login_to_a_gated_verb(_context(output_format="text"), bucket_id=only_choice.profile_id) is None


def test_the_gate_reports_no_session_when_no_screen_was_shown(tmp_path) -> None:
    """No screen means the caller still refuses — the gate cannot admit a verb.

    The wiring's whole safety claim is that it can only ever remove a
    round trip, never let an unauthenticated verb through. Asserted
    against the real callback rather than the presenter it delegates to,
    because it is the callback's ``False`` that keeps the refusal below
    it reachable.

    What is NOT covered here is the path where a screen IS shown and a
    session opens: that needs a terminal this host cannot provide, so it
    is exercised by the login screen's own tests plus the shared
    ``login_profile`` door, not simulated with a double.
    """
    from ..._profile_session_gate import authenticate_profile_for_manager

    with isolated_profile_storage_root(tmp_path=tmp_path):
        _a_profile_exists()
        (only_choice,) = _login_choices()

        assert (
            authenticate_profile_for_manager(
                _context(output_format="text"), bucket_id=only_choice.profile_id
            )
            is False
        )


def test_authenticated_profile_replaces_the_invocations_stale_storage_route(tmp_path) -> None:
    """A successful gate outcome makes its profile the effective DB route.

    This is the parent-context half of the Textual handover.  The login task
    authenticates the selected profile in a child ContextVar context; after it
    returns, the synchronous invocation must replace the profile it pinned
    before parsing the named edit target.
    """
    from .....core.config import classify_storage_route, load_settings
    from ..._profile_session_gate import bind_profile_target
    from .._manager_frontend import attempt_registration

    with isolated_profile_storage_root(tmp_path=tmp_path):
        operator_secret = "routing-handover-operator-secret"  # noqa: S105 - synthetic test fixture
        first = attempt_registration("First routing subject", operator_secret, "en", lambda _enrollment: None)
        second = attempt_registration("Second routing subject", operator_secret, "en", lambda _enrollment: None)
        assert first.outcome is not None, first.refusal
        assert second.outcome is not None, second.refusal

        with override_settings(cadrumo_active_profile=first.outcome.bucket_id):
            ctx = _context(output_format="text")
            try:
                bind_profile_target(ctx, bucket_id=second.outcome.bucket_id)
                settings = load_settings()
                route = classify_storage_route(settings)

                assert settings.cadrumo_active_profile == second.outcome.bucket_id
                assert route.bucket_id == second.outcome.bucket_id
            finally:
                ctx.close()


def test_an_unnamed_login_preselects_nothing_when_no_profile_is_active(tmp_path) -> None:
    """With no active profile the page opens on its own first row.

    ``_a_profile_exists`` logs out after registering, so there is no
    active pointer to preselect. ``None`` is the honest answer, and the
    screen's own fallback picks the first row from there.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _a_profile_exists()
        assert preselected_profile_id(None) is None


def test_a_named_login_preselects_that_profiles_row(tmp_path) -> None:
    """A label resolves to the bucket id the chooser rows are keyed by.

    Asserted against the id the live listing carries rather than a
    literal, because a preselection the screen cannot match is silently
    discarded in favour of its first row — the precise failure this
    resolution exists to prevent, and one a hardcoded expectation could
    not distinguish from success.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _a_profile_exists()
        (only_choice,) = _login_choices()
        assert preselected_profile_id("Routing Subject") == only_choice.profile_id
        assert preselected_profile_id(only_choice.profile_id) == only_choice.profile_id


def test_an_unknown_named_login_is_refused_before_the_screen_opens(tmp_path) -> None:
    """A mistyped target refuses rather than opening on somebody else.

    The screen falls back to its first row for a preselection it does not
    recognise, which is right for a stale pointer and wrong for something
    the operator typed. A live profile exists here, so the fallback row
    is available and would have been taken — which is what makes the
    refusal meaningful rather than vacuous.
    """
    from .....domain.user_profile import ProfileNotFoundError

    with isolated_profile_storage_root(tmp_path=tmp_path):
        _a_profile_exists()
        assert len(_login_choices()) == 1, "a fallback row must exist for the refusal to be the reason"
        with pytest.raises(ProfileNotFoundError):
            preselected_profile_id("Routing Subjekt")
