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

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from ....adapters.inbound.tui import FormPage, RegistrationAttempt
    from ....application.user_profile import ProfileOverview, ProfileRegistrationOutcome
    from ....core.json_contract import Notice
    from ....domain.user_profile import ProfileFieldDefinition, ProfileValueRefusalKind, UserProfileRecord


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


def _profile_next_action_notice(record: UserProfileRecord) -> Notice | None:
    """The next-step advisory for a profile the routing projection singles out.

    Reuses the SAME classification the scripted wizard's own success line
    already renders --
    :func:`~cadrumo.application.wizard.profile_next_step_modelo` -- so the
    manager and the registration screen it opens onto never grow a second
    opinion about what a fiscal-residency classification implies.
    Registration itself declares no tax facts: a profile is born with only a
    label and a passphrase, so this can only ever fire once the operator has
    answered the fiscal-residency question, whether in the manager session
    opened straight from registration or a later ``edit``. There is no
    separate hook to wire on the registration screen itself, because at that
    moment there is nothing yet to project.

    Silent for the ordinary default: every profile the projection does not
    single out is not a discovery worth a banner, so it renders no notice at
    all rather than repeating a generic default on every page. The message
    names the routed MODELO rather than the wizard's ready-made CLI command
    line: the shared :class:`~cadrumo.core.json_contract.Notice` structurally
    refuses an embedded executable ``aeat ...`` invocation outside its typed
    ``action`` projection, which resolves against the live operator-surface
    catalogue this module does not own.
    """
    from ....application.user_profile import record_to_path_values
    from ....application.wizard import profile_next_step_modelo
    from ....core.i18n import tr
    from ....core.json_contract import Notice, NoticeSeverity

    modelo = profile_next_step_modelo(record_to_path_values(record))
    if modelo is None:
        return None
    return Notice(
        severity=NoticeSeverity.INFO,
        code="config.profile.manager.next_step_modelo",
        message=tr(
            "flows.manager.next_step_modelo",
            default="This profile's declared facts route it to Modelo {modelo}.",
            modelo=modelo,
        ),
        context={"modelo": modelo},
    )


def _overview_notices(record: UserProfileRecord) -> tuple[Notice, ...]:
    """Every advisory the manager's landing page reports for one record.

    Starts from
    :func:`~cadrumo.entrypoints.cli._config._status_frontend.build_active_profile_notices`
    -- the one advisory set this surface shares with the read-only status
    page -- and layers the routing projection's next-step hint on top, scoped
    to the manager's own overview: the status page is a separate read-only
    projection this module does not build.
    """
    from ._status_frontend import build_active_profile_notices

    notices = build_active_profile_notices(record)
    next_action = _profile_next_action_notice(record)
    return (*notices, next_action) if next_action is not None else notices


def build_active_profile_overview(*, label: str | None = None) -> ProfileOverview:
    """Build the manager's page for whichever profile is currently active."""
    from ....application.user_profile import CommittedProfileRepository, ProfileRecordRepository, build_profile_overview
    from ....core import require_active_bucket_id

    profile_id = require_active_bucket_id()
    record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
    overview = build_profile_overview(
        record,
        label=label if label is not None else CommittedProfileRepository().load(profile_id).label,
    )
    return overview.model_copy(update={"notices": _overview_notices(record)})


def persist_active_profile_field(path: str, value: str, *, label: str | None = None) -> ProfileOverview:
    """Write one profile field and return the page as storage now holds it.

    A blank submission clears the fact rather than storing an empty string,
    so "I did not mean to set this" and "this is empty" stay one state
    instead of drifting into two.

    The page is rebuilt by re-reading the record rather than by patching
    the previous view: the edit door may normalise or refuse a value, and
    the operator must see what was actually stored.
    """
    from ....application.user_profile import ProfileFactWriteDoor, apply_profile_fact_changes
    from ....core import require_active_bucket_id
    from ....domain.user_profile import UserProfileFact

    # Strip before deciding blank-versus-value. An exact `!= ""` test persists a
    # whitespace-only submission as a VALUE, while every reader treats it as
    # blank — and a reader that adopts on blank then restamps the path as
    # app-owned, converting the operator's write into one the app may overwrite
    # freely thereafter. The two surfaces have to agree on what spaces mean, and
    # this is the boundary that decides it.
    fact = UserProfileFact(path=path, value=value.strip() or None)
    apply_profile_fact_changes(
        profile_id=require_active_bucket_id(),
        changes=(fact,),
        door=ProfileFactWriteDoor.MANAGER_FIELD,
    )
    return build_active_profile_overview(label=label)


def _refusal_sentence(kind: ProfileValueRefusalKind, *, value: str, accepted: str) -> str:
    """Word one refusal verdict for an operator, in their output language.

    The DECISION is the schema's and is never restated here — this turns a
    verdict into copy. Two layers are involved because they answer different
    questions: :func:`~cadrumo.domain.user_profile.profile_value_refusal`
    says whether a value may be stored, in one sentence written once for the
    issue reports a developer reads, while an operator needs that in the
    language their page is written in. Keying on the KIND rather than on the
    message text is what keeps the two independent — the domain may reword
    its diagnostic without silently un-localising the dialog.

    A match over literal keys rather than a kind-to-key table, so the locale
    scaffold's ``tr()`` scan can see every key this can ask for. The match is
    exhaustive over :class:`ProfileValueRefusalKind` and deliberately has no
    fallback arm: a kind added to the domain rule must be given words here,
    and a silent English fallback would let it ship unnoticed.
    """
    from ....core.i18n import tr
    from ....domain.user_profile import ProfileValueRefusalKind

    match kind:
        case ProfileValueRefusalKind.ENUM:
            return tr("flows.manager.edit.refused.enum", value=value, accepted=accepted)
        case ProfileValueRefusalKind.DATE:
            return tr("flows.manager.edit.refused.date", value=value)
        case ProfileValueRefusalKind.NUMERIC:
            return tr("flows.manager.edit.refused.numeric", value=value, accepted=accepted)
        case ProfileValueRefusalKind.BOOLEAN:
            return tr("flows.manager.edit.refused.boolean", value=value)
        case ProfileValueRefusalKind.EMAIL:
            return tr("flows.manager.edit.refused.email", value=value)


def profile_field_value_refusal(path: str, value: str) -> str | None:
    """Why the profile schema would refuse ``value`` at ``path``, or ``None``.

    The manager's edit dialog asks this before it closes, so a value the
    record will not take is refused at the box the operator typed it into
    rather than after a storage round trip. It must therefore judge exactly
    what the write door judges, and it does so by building the very fact the
    door would build: the fact carrier is what promotes ``"true"`` to a real
    :class:`bool` and ``"1978-03-15"`` to a :class:`datetime.date`, so asking
    the schema about the raw string instead would answer a different
    question and disagree with storage on precisely the values that matter.

    A blank is not this door's business — it is a clear, which the required
    field guard and the write door judge — and an unparseable fact is left
    to the write door too, since a path the fact carrier itself rejects is a
    surface defect rather than a value the operator can fix.
    """
    from pydantic import ValidationError

    from ....domain.user_profile import (
        UserProfileFact,
        UserProfileNotFoundError,
        load_user_profile_schema,
        profile_value_refusal,
        section_field_key,
    )

    stripped = value.strip()
    if not stripped:
        return None
    try:
        declared = load_user_profile_schema().field(section_field_key(path))
        coerced = UserProfileFact(path=path, value=stripped).value
    except (UserProfileNotFoundError, ValidationError):
        # A path the schema does not declare, or one the fact carrier will
        # not accept, is the surface offering a row it should not have. The
        # write door refuses it as an unknown field and says so; guessing a
        # value-shaped refusal here would name the wrong fault.
        return None
    refusal = profile_value_refusal(declared, coerced)
    if refusal is None:
        return None
    return _refusal_sentence(refusal.kind, value=stripped, accepted=_accepted_clause(declared))


def _accepted_clause(field: ProfileFieldDefinition) -> str:
    """What this field accepts, as data rather than as a sentence.

    Only the two kinds whose accepted set is DECLARED carry content: an
    enum's tokens and a numeric field's bounds are things the operator
    cannot guess and that differ per field. Every other kind's shape is
    fixed and already stated by its own message.

    Rendered as bare tokens and numerals, never as prose, because it is
    substituted into a translated sentence: a clause worded here would
    arrive in English inside a Spanish refusal, and building the sentence
    out of translated fragments instead would leave every catalogue holding
    half-phrases nobody can order correctly.
    """
    from ....domain.user_profile import NUMERIC_PROFILE_FIELD_TYPES, ProfileFieldType

    if field.type is ProfileFieldType.ENUM:
        return ", ".join(field.enum_values)
    if field.type not in NUMERIC_PROFILE_FIELD_TYPES:
        return ""
    minimum, maximum = field.minimum, field.maximum
    if minimum is not None and maximum is not None:
        return f" ({minimum} - {maximum})"
    if minimum is not None:
        return f" (>= {minimum})"
    if maximum is not None:
        return f" (<= {maximum})"
    return ""


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

    The page after an edit is projected from the
    :class:`~cadrumo.domain.user_profile.UserProfileRecord` the write path
    committed, not from a second read of it. That is still post-commit truth
    -- the record is returned only once the write succeeded, so the
    no-optimistic-render contract holds -- but it retires a full aggregate
    decrypt of data this process had just encrypted and stored, which was
    roughly a third of the persist half at a well-populated profile. That the
    committed record equals what a fresh load yields is proved, not assumed,
    by ``test_saved_record_is_byte_equivalent_to_a_fresh_load`` and its paired
    divergence-catcher.

    The manifest label is resolved once for the session rather than per edit.
    Only a rename moves it, and the manager exposes no rename action, so it
    cannot drift while this screen is open.
    """
    from ....application.user_profile import (
        CommittedProfileRepository,
        ProfileFactWriteDoor,
        ProfileRecordRepository,
        apply_profile_fact_changes,
        build_profile_overview,
    )
    from ....core import require_active_bucket_id
    from ....domain.user_profile import UserProfileFact, load_user_profile_schema

    profile_id = require_active_bucket_id()
    schema = load_user_profile_schema()
    profiles = ProfileRecordRepository.for_current_session(profile_id)

    opening = profiles.load(profile_id)
    resolved_label = label if label is not None else CommittedProfileRepository().load(profile_id).label

    def _page(record: UserProfileRecord) -> ProfileOverview:
        overview = build_profile_overview(record, label=resolved_label, schema=schema)
        return overview.model_copy(update={"notices": _overview_notices(record)})

    def _persist(path: str, value: str) -> ProfileOverview:
        fact = UserProfileFact(path=path, value=value.strip() or None)
        applied = apply_profile_fact_changes(
            profile_id=profile_id,
            changes=(fact,),
            door=ProfileFactWriteDoor.MANAGER_FIELD,
        )
        return _page(applied)

    return _page(opening), _persist


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
        validate=profile_field_value_refusal,
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
        ProfileRecoveryEnrollment,
        ProfileRegistrationError,
        register_profile_with_credentials,
    )
    from ....core.errors import resolve_error_message
    from ....domain.user_profile import UserProfileFact

    # The full-screen door shows the words itself, so the enrollment rides
    # the attempt back to the screen; the screen owns the wipe.
    captured: list[ProfileRecoveryEnrollment] = []

    try:
        outcome = register_profile_with_credentials(
            label=label,
            passphrase=passphrase,
            facts=(UserProfileFact(path="preferences.output_language", value=output_language),),
            recovery_handover=captured.append,
        )
    except ProfileRegistrationError as refusal:
        return _Attempt(refusal=resolve_error_message(refusal))
    return _Attempt(outcome=outcome, enrollment=captured[0] if captured else None)


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
    from ....core import assess_profile_password

    return run_registration_tui(
        assess=assess_profile_password,
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
    "profile_field_value_refusal",
]
