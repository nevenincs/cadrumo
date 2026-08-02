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


_ROUTING_META_KEYS = frozenset({"ctx", "profile_name", "quiet", "accept_defaults"})


def _field_value_was_supplied(value: object) -> bool:
    """Return whether a parsed wizard value represents an explicit flag.

    Typer materialises repeated options with an empty list when the operator
    did not pass them. An empty collection is therefore a parser default, not
    an explicit field value; non-empty collections and every scalar value
    (including ``False`` and ``0``) are explicit.
    """
    if value is None:
        return False
    if isinstance(value, list | tuple):
        return any(str(item) for item in value)
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

    # Strip before deciding blank-versus-value. An exact `!= ""` test persists a
    # whitespace-only submission as a VALUE, while every reader treats it as
    # blank — and a reader that adopts on blank then restamps the path as
    # app-owned, converting the operator's write into one the app may overwrite
    # freely thereafter. The two surfaces have to agree on what spaces mean, and
    # this is the boundary that decides it.
    fact = UserProfileFact(path=path, value=value.strip() or None)
    workflow_state_repository().update(lambda state: set_active_field(state, fact))
    return build_active_profile_overview(label=label)


def _active_profile_manager_storage(
    *,
    label: str | None = None,
) -> tuple[ProfileOverview, Callable[[str, str], ProfileOverview]]:
    """Bind one manager session to one resolved encrypted-store handle.

    A manager edits many fields while the same active-profile storage session is
    open.  Resolving the storage route afresh for the workflow write, profile
    write, and post-write read on every edit repeatedly rebuilds ``Settings``
    and normalises every configured path.  Keep one secure repository and the
    canonical schema for the lifetime of this screen; the repository still
    performs the same encrypted SQL writes, validation, revision checks, and
    audit-event commit for every edit.

    The returned overview is still rebuilt from a post-commit database read.
    That preserves the manager's no-optimistic-render contract while avoiding
    only repeated route discovery, not persistence or integrity verification.
    """
    from ....adapters.persistence.storage import secure_object_repository_for_active_bucket
    from ....application.user_profile import ProfileRepository, build_profile_overview, set_active_field
    from ....application.workflow import WorkflowStateRepository
    from ....core import require_active_bucket_id
    from ....domain.user_profile import UserProfileFact, load_user_profile_schema

    profile_id = require_active_bucket_id()
    secure_objects = secure_object_repository_for_active_bucket()
    schema = load_user_profile_schema()
    profiles = ProfileRepository(secure_objects=secure_objects, schema=schema)
    workflow = WorkflowStateRepository(objects=secure_objects)

    def _overview() -> ProfileOverview:
        aggregate = profiles.load(profile_id)
        return build_profile_overview(
            aggregate.record,
            label=label if label is not None else aggregate.label,
            schema=schema,
        )

    def _persist(path: str, value: str) -> ProfileOverview:
        fact = UserProfileFact(path=path, value=value.strip() or None)
        workflow.update(
            lambda state: set_active_field(
                state,
                fact,
                secure_objects=secure_objects,
                schema=schema,
            ),
        )
        return _overview()

    return _overview(), _persist


def present_profile_manager(*, label: str | None = None) -> None:
    """Open the manager on the active profile and run it to completion.

    The manager persists each edit as it is made, so there is nothing to
    return: by the time this call comes back, every change the operator
    made is already on the encrypted record.
    """
    from ....adapters.inbound.tui import run_profile_manager_tui
    from ._manager_actions import manager_actions

    overview, persist = _active_profile_manager_storage(label=label)
    run_profile_manager_tui(
        overview,
        persist=persist,
        actions=manager_actions(),
    )


def present_form(
    page: FormPage,
    *,
    rebuild: Callable[[Mapping[str, str]], FormPage] | None = None,
) -> Mapping[str, str] | None:
    """Show one editable field page and return what the operator committed.

    ``None`` means they left without committing, which every caller treats
    as "make no change" rather than as an error.

    How the page is shown depends on who is asking. Reached from the
    command line there is no application yet, so one is started for it.
    Reached from inside the profile manager there already is one, and a
    second cannot be started from a running event loop — so the manager
    binds a presenter that opens the page on itself, and this call finds
    it. Callers say what they want shown and stay out of that decision.
    """
    from ....adapters.inbound.tui import active_form_presenter, run_form_tui

    presenter = active_form_presenter()
    if presenter is not None:
        return presenter(page, rebuild)
    return run_form_tui(page, rebuild=rebuild)


def attempt_registration(label: str, passphrase: str, output_language: str) -> RegistrationAttempt:
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
    from ....domain.user_profile import UserProfileFact

    try:
        outcome = register_profile_with_credentials(
            label=label,
            passphrase=passphrase,
            facts=(UserProfileFact(path="preferences.output_language", value=output_language),),
        )
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
    "has_explicit_profile_fields",
    "host_can_run_full_screen",
    "manager_is_the_right_frontend",
    "persist_active_profile_field",
    "present_form",
    "present_profile_manager",
    "present_registration",
]
