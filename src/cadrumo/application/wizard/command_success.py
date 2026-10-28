"""Success output for wizard commands."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...core.json_contract import Notice, ResolvedNoticeAction
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .results import ConfigProfileCreateResult, ConfigProfileEditResult, ProfileWizardStatus


from ...core.errors.hierarchy import InternalInvariantError
from ...core.i18n.render import tr
from ...core.modelo import Modelo
from .persistence import WizardPersistMode

DEFAULT_PROFILE_NEXT_COMMAND = "aeat app modelo work create"


def profile_next_step_modelo(
    profile_values: dict[str, str],
    *,
    operation: PinnedAuthorityOperation,
) -> str | None:
    """The modelo id the routing projection singles out, or ``None`` for the default.

    The one canonical classification a taxpayer's declared facts route
    through — currently a single rule (IRNR non-residents route to Modelo
    210, TRLIRNR RDLeg 5/2004 Art. 2) — ``None`` for every profile the
    projection does not single out. This is the PRIMARY authority;
    :func:`next_step_command_for_profile_values` derives its CLI command
    text from it rather than repeating the classification, so a consumer
    whose channel cannot carry command prose (the shared
    :class:`~cadrumo.core.json_contract.Notice` structurally forbids an
    embedded executable ``aeat ...`` invocation outside its typed action
    projection) can still word its own sentence around the routed modelo.

    Args:
        profile_values: Dotted-path fact values as the wizard's canonical
            question-id keys, or the equivalent
            :func:`~cadrumo.application.user_profile.projections.record_to_path_values`
            projection of a :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`
            — the two share the same ``taxpayer_type.fiscal_residency`` key.
        operation: Caller-owned pinned authority operation used to classify the
            fiscal-residency token.
    """
    fiscal_residency = profile_values.get("taxpayer_type.fiscal_residency", "").strip().lower()
    from ...domain.calculations.registry.renta_codes_catalogue import fiscal_residency_requires_country

    if fiscal_residency_requires_country(fiscal_residency, authority=operation):
        return Modelo("210").value
    return None


def next_step_command_for_profile_values(
    profile_values: dict[str, str],
    *,
    operation: PinnedAuthorityOperation,
) -> str:
    """Resolve the CLI command a profile's declared facts point at next.

    Derived from :func:`profile_next_step_modelo`, the canonical
    classification, falling back to :data:`DEFAULT_PROFILE_NEXT_COMMAND` when
    it singles out no modelo. Consumed by the scripted wizard's own success
    line, which renders the command as text.
    """
    modelo = profile_next_step_modelo(profile_values, operation=operation)
    if modelo is None:
        return DEFAULT_PROFILE_NEXT_COMMAND
    return f"aeat app modelo describe {modelo}"


def ccaa_was_defaulted(
    mode: WizardPersistMode,
    explicit_flags: dict[str, str],
    profile_values: dict[str, str],
    *,
    non_interactive: bool,
    default_ccaa_value: str | None,
) -> bool:
    """Return True when the comunidad autónoma was assumed, not chosen.

    The wizard descriptor defaults ``tax-residence-ccaa`` to Madrid for a
    resident-IRPF profile. That default is applied silently on the
    non-interactive create paths (``--quiet`` / ``--accept-defaults``)
    when the operator omits ``--tax-residence-ccaa`` — precisely the case
    that lands a Madrid-based autonomic calculation without the operator
    knowing. The signal is therefore: a non-interactive ``create`` where
    the operator supplied no CCAA flag yet the persisted profile carries
    the Madrid default. An explicitly-supplied CCAA (including an explicit
    ``madrid``) sits in ``explicit_flags`` and is excluded; the interactive
    path prompts for the value and is likewise excluded, as is ``edit``
    (whose CCAA already exists on the profile).
    """
    return (
        mode == "create"
        and non_interactive
        and "tax-residence-ccaa" not in explicit_flags
        and default_ccaa_value is not None
        and profile_values.get("tax_residence.ccaa") == default_ccaa_value
    )


_MODIFY_NO_RESUME_CODE = "config.profile.edit.modify_no_resume"
_MODIFY_DESCENDANTS_DOOR_CODE = "config.profile.edit.descendants_via_door"


def _selected_profile_label() -> str | None:
    """Return the label of the profile the selection pointer names, if any.

    A pointer naming a capsule whose label cannot be read leaves the spine
    unset rather than guessing: the anchor exists to identify a profile, and a
    wrong identity is worse than an absent one.
    """
    from ...core.logging import get_logger
    from ..user_profile.profile_pointer import observe_active_profile_pointer
    from ..workflow.profile_bucket_scan import read_profile_bucket_by_id

    # This runs after the record has been written, so it must not be able to
    # fail the verb: the edit is already durable, and reporting a refusal for a
    # committed change is worse than reporting it without the spine anchor.
    try:
        pointer = observe_active_profile_pointer()
        if pointer.bucket_id is None:
            return None
        selected = read_profile_bucket_by_id(pointer.bucket_id)
    except Exception:
        get_logger(__name__).debug("active-profile label resolution failed for the wizard spine", exc_info=True)
        return None
    return None if selected is None else selected.label


def emit_wizard_success(
    mode: WizardPersistMode,
    profile_name: str,
    *,
    record_changed: bool = True,
    next_command: str = DEFAULT_PROFILE_NEXT_COMMAND,
    ccaa_defaulted: bool = False,
    modify_no_resume: bool = False,
    modify_no_resume_message: str | None = None,
    modify_descendants_via_door: bool = False,
    modify_descendants_message: str | None = None,
    default_ccaa_value: str | None = None,
    invocation_notices: Callable[[], Sequence[Notice]] = tuple,
) -> None:
    """Emit the success payload in JSON or tabular CLI form.

    The post-create / post-edit next-step hint rides on the envelope
    ``notices`` channel (an ``info``-severity :class:`Notice` whose
    ``suggestion`` is the follow-on command) rather than as a bespoke
    ``next`` payload field, so next-step guidance is uniform with every
    other command's notices.

    ``ccaa_defaulted`` requests an additional ``warning``-severity
    :class:`Notice` disclosing that no comunidad autónoma was chosen and
    that Madrid was assumed for the profile — so the operator learns the
    autonomic deductions and autonomic tax scale are being computed for
    Madrid rather than the value being applied silently.

    ``modify_no_resume`` requests an ``info``-severity :class:`Notice`
    stating that mid-flow save/resume is unavailable in modify mode and an
    interrupted modify discards its staged edits. It rides the final
    envelope of every interactive modify run regardless of whether the
    operator attempted a save — the LOUD, never-silent honesty disclosure
    the persistence model binds modify to.

    ``modify_no_resume_message`` carries the message pre-rendered in the
    command-level output language. The final envelope is a command-level
    disclosure, so it must render in the language the command entered with,
    not a mid-walk output-language switch that shadows it by the time this
    emit runs; the caller freezes the string before the walk and passes it
    here. ``None`` falls back to resolving it now (the direct, walk-less
    callers).

    ``invocation_notices`` supplies the notices the invoking frontend staged
    for this invocation, such as an authentication that could not be kept for
    the next process. This emitter reaches the envelope directly rather than
    through the frontend's own funnel, so without it those notices were lost
    on every edit. It is called only here, on success, so a refused command
    leaves them for the frontend's error path.
    """
    from ...core.click_context import json_output_requested
    from ..operator_output.emit import emit_operator_json_success
    from .results import ConfigProfileCreateResult, ConfigProfileEditResult, ProfileWizardStatus

    def _success_status() -> tuple[ProfileWizardStatus, str]:
        """Keep machine status and localized verb keys paired."""
        if mode == "create":
            return ProfileWizardStatus.CREATED, "wizard.commands.status.created"
        if record_changed:
            return ProfileWizardStatus.UPDATED, "wizard.commands.status.updated"
        return ProfileWizardStatus.UNCHANGED, "wizard.commands.status.unchanged"

    def _success_messages() -> tuple[str, str, str]:
        """Resolve all user-visible disclosures in the active language."""
        no_resume = (
            modify_no_resume_message
            if modify_no_resume_message is not None
            else tr("application.wizard.notices.modify_no_resume")
        )
        descendants = (
            modify_descendants_message
            if modify_descendants_message is not None
            else tr("application.wizard.notices.modify_descendants_via_door")
        )
        ccaa = (
            tr("application.wizard.notices.ccaa_defaulted", ccaa=default_ccaa_value)
            if ccaa_defaulted and default_ccaa_value is not None
            else ""
        )
        return no_resume, descendants, ccaa

    # Keep the closed machine token separate from the localized text verb.
    status_token, verb_key = _success_status()
    verb = tr(verb_key)
    resolved_modify_no_resume_message, resolved_modify_descendants_message, ccaa_message = _success_messages()
    notices = _wizard_success_notices(
        mode,
        next_command=next_command,
        modify_no_resume=modify_no_resume,
        modify_no_resume_message=resolved_modify_no_resume_message,
        modify_descendants_via_door=modify_descendants_via_door,
        modify_descendants_message=resolved_modify_descendants_message,
        modify_descendants_action=_resolved_descendientes_action(),
        ccaa_defaulted=ccaa_defaulted,
        ccaa_message=ccaa_message,
        ccaa_value=default_ccaa_value,
    )
    # Populate the envelope-spine active_profile identity anchor. The wizard
    # sits below the CLI transport's emit_envelope funnel (it cannot import
    # it — layering), so it must resolve the label itself. On create the
    # newly-created profile IS the active one, so its name is the label. On
    # edit the edited profile is not necessarily the active one, so the label
    # is read from the selection pointer rather than assumed or left unset:
    # every other command reports the active profile on this spine, and an
    # unset one read as "no profile is active" while one plainly was.
    notices = [*notices, *invocation_notices()]
    active_profile = profile_name if mode == "create" else _selected_profile_label()
    result: ConfigProfileCreateResult | ConfigProfileEditResult = (
        ConfigProfileCreateResult(
            profile_name=profile_name,
            status=status_token,
            active_profile=active_profile,
        )
        if mode == "create"
        else ConfigProfileEditResult(profile_name=profile_name, status=status_token)
    )
    if json_output_requested():
        command_path = "config.profile.create" if mode == "create" else "config.profile.edit"
        # emit_operator_json_success is the one sanctioned direct route to
        # the envelope: it resolves and prepends the sandbox-active notice
        # itself, so this call site cannot forget it (there is no other way
        # to reach SchemaEnvelope for this result from here).
        emit_operator_json_success(command_path, result, notices=notices, active_profile=active_profile)
        return

    _echo_wizard_success_text(
        mode,
        profile_name,
        verb=verb,
        next_command=next_command,
        result=result,
        disclosures=(
            (modify_no_resume, resolved_modify_no_resume_message),
            (modify_descendants_via_door, resolved_modify_descendants_message),
            (ccaa_defaulted, ccaa_message),
        ),
    )


def _echo_wizard_text(lines: list[str], *, payload: object) -> None:
    """Render wizard text lines through the output boundary and emit them.

    The single place this module's operator-facing text crosses into stdout.
    Every identifier-bearing success disclosure funnels through here, so the
    sandbox banner, the redaction pass and the reveal-identifiers resolution
    are applied once rather than once per emitter. Two emitters each holding a
    private copy of the render-and-echo pair is how one of them came to bypass
    the boundary while its sibling did not.
    """
    import typer as _typer

    from ...core.output_rendering import render_command_output
    from ..operator_output.sandbox_notice import sandbox_banner_line, sandbox_notice_for_active_bucket

    sandbox_notice = sandbox_notice_for_active_bucket()
    if sandbox_notice is not None:
        lines.insert(0, sandbox_banner_line(sandbox_notice))
    rendered = render_command_output(format_name="text", payload=payload, lines=lines)
    _typer.echo(rendered.text)


def _echo_wizard_success_text(
    mode: WizardPersistMode,
    profile_name: str,
    *,
    verb: str,
    next_command: str,
    result: ConfigProfileCreateResult | ConfigProfileEditResult,
    disclosures: tuple[tuple[bool, str], ...],
) -> None:
    """Render the success payload as tab-separated operator text.

    Every disclosure that rides the notices channel is repeated here: the
    envelope renders ``notices`` only in JSON mode, so one left off these
    lines would be visible to automation and invisible to the operator
    running the verb plainly.
    """
    lines = [
        f"{tr('application.wizard.output_labels.profile')}\t{profile_name}",
        f"{tr('application.wizard.output_labels.status')}\t{verb}",
    ]
    if mode == "create":
        lines.append(f"{tr('application.wizard.output_labels.active_profile')}\t{profile_name}")
    lines.append(f"{tr('application.wizard.output_labels.next')}\t{next_command}")
    lines.extend(message for enabled, message in disclosures if enabled)
    _echo_wizard_text(lines, payload=result)


def _resolved_descendientes_action() -> ResolvedNoticeAction | None:
    """Resolve the typed descendiente door for the success notice.

    The catalogue entry fails closed on an unknown id, so the notice's
    executable action always names a live verb or the emission refuses —
    the failure mode the old literal-command message could not have.
    """
    from ..operator_actions.catalogue import next_action

    return next_action("operator.profile.descendiente")


def _wizard_success_notices(
    mode: WizardPersistMode,
    *,
    next_command: str,
    modify_no_resume: bool,
    modify_no_resume_message: str,
    modify_descendants_via_door: bool,
    modify_descendants_message: str,
    modify_descendants_action: ResolvedNoticeAction | None = None,
    ccaa_defaulted: bool,
    ccaa_message: str,
    ccaa_value: str | None,
) -> list[Notice]:
    """Build the success envelope's notices: the next step plus each disclosure.

    Every message arrives pre-rendered because the final envelope is a
    command-level disclosure and must render in the language the command
    entered with, not one a mid-walk output-language switch left behind.
    """
    from ...core.json_contract import Notice, NoticeSeverity

    verb_key = "create" if mode == "create" else "edit"
    # The next-step hint is text-surface only. ``Notice`` reserves executable
    # command identity for its typed action projection, which models a
    # PRECONDITION-FAILURE recovery - a failed condition, its evidence, its
    # conditionality - and has no member that means "this succeeded, here is a
    # reasonable next verb". Carrying the bare label without its command would
    # emit a notice reading "Next:" and nothing else, which is worse than
    # emitting none, so the JSON channel omits it entirely rather than shipping
    # an empty gesture. ``next_command`` still renders on the text surface.
    _ = next_command
    notices: list[Notice] = []
    if modify_no_resume:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code=_MODIFY_NO_RESUME_CODE,
                message=modify_no_resume_message,
            ),
        )
    if modify_descendants_via_door:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code=_MODIFY_DESCENDANTS_DOOR_CODE,
                message=modify_descendants_message,
                action=modify_descendants_action,
            ),
        )
    if ccaa_defaulted:
        if ccaa_value is None:
            raise InternalInvariantError("CCAA default disclosure requires the operation-scoped default token")
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=f"config.profile.{verb_key}.ccaa_defaulted",
                message=ccaa_message,
                context={"assumed_ccaa": ccaa_value},
            ),
        )
    return notices
