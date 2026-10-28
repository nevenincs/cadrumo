"""Typer command factory for wizard flows.

``build_wizard_command(flow)`` returns a Typer-compatible callable
whose signature is composed at construction time from the flow's
questions plus three fixed mode flags (``--profile``,
``--quiet``, ``--accept-defaults``). The closure runs the flow and
persists the typed answers.

Flag derivation per question kind:

* ``TEXT`` / ``SECRET`` / ``PATH`` → ``--<question-id>`` ``str``
  option (``Path`` for ``PATH``);
* ``INTEGER`` → ``--<question-id>`` ``int`` option;
* ``CONFIRM`` → ``--<question-id>/--no-<question-id>`` boolean pair;
* ``SELECT`` → ``--<question-id>`` option with
  ``click.Choice([c.value for c in choices])``;
* ``CHECKBOX`` → repeated ``--<question-id>`` option that accumulates
  a ``list[str]``.

An interactive walk projects the one-shot wizard catalogue into a
substrate :class:`~cadrumo.application.flows.definition.FlowDefinition`
(via :func:`~cadrumo.application.flows.wizard_projection.flow_definition_from_wizard_flow`)
and drives it through an injected frontend runner: the full-screen
Textual frontend where the host supports it, degrading to the line-mode
frontend otherwise, and refusing instructively on a non-interactive
host. The application default renders the line frontend (a same-layer
``application.flows`` primitive); the CLI entrypoint injects the
capability-selecting runner that reaches the full-screen inbound adapter.
The committed answers are then replayed through the same scripted
projection the ``--quiet`` / ``--accept-defaults`` paths use, so the
persisted typed model is produced identically regardless of frontend.
"""

from __future__ import annotations

import typing
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...core.errors.hierarchy import CadrumoError
    from ...core.json_contract import Notice
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.user_profile.values import UserProfileFact

import contextlib

import typer
from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails

from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ...core.flows import CheckpointAvailability, FlowMode
from ...core.i18n.render import tr
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ..flows.definition import FlowDefinition, FlowPage, FlowSection
from ..flows.engine import start_flow, visible_sequence
from ..flows.errors import FlowAnswerError, FlowSubmitError
from ..flows.scripted import run_scripted_flow
from ..flows.wizard_projection import flow_definition_from_wizard_flow
from ._format_hints import attach_format_hints
from .command_parameters import (
    canonical_from_flag_value,
    flag_name,
    mode_parameters,
    question_parameters,
    required_flag_questions,
    wizard_command_metadata,
)
from .command_success import ccaa_was_defaulted, emit_wizard_success, next_step_command_for_profile_values
from .descendant_group import attach_descendant_group
from .errors import (
    WizardEditUnsupportedConsoleError,
    WizardMissingFlagError,
    WizardPreconditionCondition,
    WizardUnsupportedConsoleError,
    WizardValidationError,
    wizard_no_action_verdict,
)
from .flow_validators import attach_taxpayer_projection_validator
from .models import WizardFlow
from .patch_edit import (
    WizardPatchPersister,
    apply_profile_patch,
    format_missing_flags,
    refuse_foral_ccaa,
    require_filing_baseline,
)
from .persistence import WizardPersistMode
from .setup_legal_validators import attach_setup_legal_validators


def _translation_context(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return STR_KEYED_MAPPING_ADAPTER.validate_python(value)


#: Which substrate :class:`FlowMode` each wizard verb drives. ``create``
#: registers a fresh profile, ``edit`` modifies an existing one.
_FLOW_MODE_BY_WIZARD_MODE: dict[WizardPersistMode, FlowMode] = {
    "create": FlowMode.CREATE,
    "edit": FlowMode.MODIFY,
}

#: Neither setup mode offers a checkpoint.  Credential registration owns
#: profile creation, and profile edits must never leave a half-applied fact
#: set behind.
_SETUP_CHECKPOINT: dict[FlowMode, CheckpointAvailability] = {
    FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
    FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
}


# KWARGS-RATIONALE-flow-runner: keyword-only frontend seam injected by the caller.


def _missing_required_flags(
    flow: WizardFlow,
    canonical: dict[str, str],
) -> tuple[str, ...]:
    """Return the question ids whose canonical-token value is missing."""
    missing: list[str] = []
    for question in required_flag_questions(flow):
        if question.id not in canonical or not canonical[question.id]:
            if question.default is not None and question.default:
                canonical[question.id] = question.default
            else:
                missing.append(question.id)
    return tuple(missing)


def setup_flow_definition(
    flow: WizardFlow,
    *,
    attach_descendants: bool = True,
    operation: PinnedAuthorityOperation,
) -> FlowDefinition:
    """Bridge and decorate the wizard flow into the shared substrate definition.

    The single projected :class:`FlowDefinition` every frontend drives:
    the substrate bridge, format hints, setup legal validators, the
    flow-scope taxpayer-construction validator, and -- for CREATE -- the
    descendant repeating group, applied in one place so no caller can
    diverge on the definition it runs.

    The taxpayer-construction validator is attached before the descendant
    group so it enrols the top-level pages only: repeating-group answers
    serialise through the descendant fact path, not the taxpayer
    projection.

    ``attach_descendants`` gates the descendant group. It is spliced for
    CREATE (where the facts-as-checkpoint store seeds and re-seeds the group)
    and withheld for MODIFY. Modify-mode seeding cannot instantiate the
    repeating group: the modify frontend seeds render-time page defaults over
    a fresh :func:`~cadrumo.application.flows.engine.start_flow` state, and instance
    pages are generated dynamically from the group's count rather than being
    static items the default-seed mechanism can reach. Rendering the group
    unseeded would show an operator's existing descendants as an empty group
    whose commit -- via the namespace-replacing clearing guard -- would then
    silently erase them. So MODIFY withholds the group and the command
    surfaces the descendant door instead of a silently-lossy surface.

    """
    definition = attach_taxpayer_projection_validator(
        attach_setup_legal_validators(
            attach_format_hints(flow_definition_from_wizard_flow(flow, checkpoint=_SETUP_CHECKPOINT)),
        ),
    )
    if attach_descendants:
        definition = attach_descendant_group(definition, operation=operation)
    return definition


def _force_pages_visible(definition: FlowDefinition, page_ids: frozenset[str]) -> FlowDefinition:
    """Project the named pages as unconditionally visible for one scripted walk.

    An explicitly-supplied flag is an unambiguous declaration of intent, so
    its gated question must be collected even when its ``visible_when`` gate
    would otherwise hide it. Stripping the gate on exactly the named pages
    reproduces the retired runner's ``force_visible`` law: the scripted
    driver then walks and demands the page like any other visible one, while
    every other gate keeps governing prompting normally.
    """
    if not page_ids:
        return definition
    new_sections: list[FlowSection] = []
    for section in definition.sections:
        new_items = tuple(
            item.model_copy(update={"visible_when": None})
            if isinstance(item, FlowPage) and item.id in page_ids and item.visible_when is not None
            else item
            for item in section.items
        )
        new_sections.append(section.model_copy(update={"items": new_items}))
    return definition.model_copy(update={"sections": tuple(new_sections)})


def _project_scripted_answers(
    definition: FlowDefinition,
    canonical: Mapping[str, str],
    *,
    mode: FlowMode,
) -> tuple[list[str], dict[str, str]]:
    """Project the canonical dict into the driver's visible-sequence order.

    :func:`~cadrumo.application.flows.scripted.run_scripted_flow` consumes an ordered
    queue, one token per visible page, re-evaluating visibility after each
    commit. This mirrors that walk over the DEFINITION (so a substrate-only
    page keeps its true walk position) and emits each page's canonical token,
    or its descriptor default / blank when the operator supplied none, so the
    positional queue stays aligned with every gate the driver will observe.

    Returns the ordered token queue plus the same tokens keyed by page id —
    the intended answer set, used to re-derive the wizard's localized
    refusal when the substrate rejects an answer or blocks submission.
    """
    base = start_flow(definition, mode=mode)
    answers: dict[str, str] = {}
    tokens: list[str] = []
    while True:
        target = next(
            (
                entry
                for entry in visible_sequence(definition, base.model_copy(update={"answers": dict(answers)}))
                if entry.key not in answers
            ),
            None,
        )
        if target is None:
            return tokens, answers
        raw = canonical.get(target.key, target.page.default or "")
        tokens.append(raw)
        answers[target.key] = raw


def _answers_model_from_canonical(flow: WizardFlow, committed: Mapping[str, str]) -> BaseModel:
    """Coerce a page-keyed committed-answer map into the typed answers model.

    Every visible page commits during a walk (even blank), so a question the
    walk visited carries a key in ``committed`` and a gate-hidden question is
    absent. Each present answer is re-validated through its widget validator
    and parsed into the declared answer type — the exact projection the
    retired runner applied post-walk — so the persisted typed model is
    produced identically regardless of the frontend (scripted, line, or
    full-screen) that produced ``committed``.
    """
    from .persistence import parse_canonical
    from .widgets import validate_widget_answer

    typed: dict[str, object] = {}
    for section in flow.sections:
        for question in section.questions:
            if question.id not in committed:
                continue
            validated = validate_widget_answer(question, committed[question.id])
            typed[question.id.replace("-", "_")] = parse_canonical(question, validated)
    return flow.answers_model.model_validate(typed)


def _run_scripted_walk(
    flow: WizardFlow,
    canonical: dict[str, str],
    *,
    mode: WizardPersistMode,
    explicit_question_ids: frozenset[str],
    operation: PinnedAuthorityOperation,
) -> BaseModel:
    """Drive a non-interactive walk through the shared flow substrate.

    Builds the same projected definition the interactive frontends drive,
    forces every explicitly-supplied gated question visible for this walk,
    projects the canonical dict into the driver's visible-sequence token
    order, and runs the scripted intent driver. The committed answers are
    then coerced through the one projection every frontend shares, so a
    non-interactive create is answer-for-answer identical to an interactive
    one.

    The substrate is the sole authority for the persisted answers (parity
    with the interactive frontends). A substrate refusal — a rejected answer
    or a blocked submission — is re-surfaced through the wizard's own
    localized answer-model validation so the operator still reads the precise
    flag-named date / decimal / cross-field message, not the substrate's
    generic verdict. That fallback only ever raises; if the model unexpectedly
    validates, the substrate refusal stands.
    """
    flow_mode = _FLOW_MODE_BY_WIZARD_MODE[mode]
    definition = _force_pages_visible(
        setup_flow_definition(flow, attach_descendants=mode == "create", operation=operation),
        explicit_question_ids,
    )
    tokens, intended = _project_scripted_answers(definition, canonical, mode=flow_mode)
    defaults = {
        question.id: question.default or ""
        for section in flow.sections
        for question in section.questions
        if question.default is not None
    }
    try:
        state, _projection = run_scripted_flow(definition, tokens, mode=flow_mode, defaults=defaults)
    except (FlowAnswerError, FlowSubmitError):
        _answers_model_from_canonical(flow, intended)
        raise
    return _answers_model_from_canonical(flow, dict(state.answers))


def _collect_flag_values(
    flow: WizardFlow,
    kwargs: dict[str, object],
) -> dict[str, str]:
    """Project the closure's keyword arguments into the canonical-token dict."""
    canonical: dict[str, str] = {}
    for section in flow.sections:
        for question in section.questions:
            field_name = question.id.replace("-", "_")
            raw = kwargs.get(field_name)
            canonical_value = canonical_from_flag_value(question, raw)
            if canonical_value is not None:
                canonical[question.id] = canonical_value
    return canonical


_COLEGIO_CONCERTADO_PROFILE_PATH = "withholding.colegio_concertado"


def _colegio_concertado_profile_value(kwargs: Mapping[str, object]) -> dict[str, str]:
    """Project the explicit Modelo 111 header attestation, if supplied.

    This scalar deliberately sits outside the setup flow.  A flow confirm
    requires a default and would turn an unasked legal header declaration into
    a guessed yes or no.  The public profile create/edit verbs still need a
    typed way to record it, so this is a single named mapping rather than a
    generic profile-fact writer.
    """
    supplied = kwargs.get("colegio_concertado")
    if supplied is None:
        return {}
    if not isinstance(supplied, bool):
        raise TypeError("colegio_concertado must be a parsed boolean")
    return {_COLEGIO_CONCERTADO_PROFILE_PATH: "true" if supplied else "false"}


def _colegio_concertado_from_profile_values(values: Mapping[str, str]) -> bool | None:
    """Recover the single typed header flag from the command's scalar projection."""
    value = values.get(_COLEGIO_CONCERTADO_PROFILE_PATH)
    if value is None:
        return None
    if value not in ("true", "false") or len(values) != 1:
        raise InternalInvariantError("invalid wizard header scalar projection")
    return value == "true"


def scripted_profile_facts(
    flow: WizardFlow,
    kwargs: Mapping[str, object],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[UserProfileFact, ...]:
    """Project a scripted ``create``'s field flags into initial profile facts.

    Creation is the credential door's authority, not this flow's: a profile
    exists only once a passphrase has wrapped its DEK. That leaves the field
    flags of a scripted ``config profile create`` with nowhere to land, because
    the flow's own create arm is retired and its patch arm is bound to ``edit``
    and to an already-authenticated session. This is the seam between the two.
    The projection is deliberately PURE -- it writes nothing and opens no
    session, so the caller hands the result to the registration door and the
    facts are published inside the create transaction that already holds the
    record session, rather than through a second unlock afterwards.

    A refused value refuses HERE, before the caller registers anything, so a
    foral CCAA token costs the operator no profile to correct afterwards.

    The foral check is not redundant with the question validators. Dropping it
    does still refuse -- the widget validator behind the CCAA question raises
    too -- but it refuses as a generic wizard-validation failure instead of the
    domain refusal that names the Concierto Económico and the foral tax office
    the operator actually has to file with. The flow's own command body calls
    it for the same reason. It runs first so the good message wins.

    No filing-baseline check applies. A profile created this way is born
    ``INCOMPLETE`` on purpose, so demanding the full filing baseline would
    refuse the very state the create door exists to produce.

    Args:
        flow: The setup flow whose questions name the accepted flags.
        kwargs: The verb's parsed keyword arguments, keyed by parameter name.
        operation: Caller-owned pinned authority operation used for all
            operation-scoped catalogue checks.

    Returns:
        The supplied flags as facts, empty when the caller named none.
    """
    from ...domain.user_profile.values import UserProfileFact
    from .persistence import profile_values_from_patch

    canonical = _collect_flag_values(flow, dict(kwargs))
    refuse_foral_ccaa(canonical, canonical, operation=operation)
    profile_values = profile_values_from_patch(flow, canonical)
    profile_values.update(_colegio_concertado_profile_value(kwargs))
    if not profile_values:
        return ()
    return tuple(UserProfileFact(path=path, value=value) for path, value in profile_values.items())


def _run_patch_edit(
    flow: WizardFlow,
    explicit_flags: dict[str, str],
    *,
    scalar_profile_values: Mapping[str, str],
    profile_id: str,
    operation: PinnedAuthorityOperation,
    patch_persister: WizardPatchPersister | None = None,
) -> tuple[dict[str, str], bool]:
    """Persist a non-interactive ``edit`` as a true patch.

    Only the flags the operator named on the command line are written;
    every other stored field is left untouched. No full-flow walk, no
    ``SetupAnswers`` model construction, no descriptor-default seeding.
    """
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import record_to_path_values

    if patch_persister is not None:
        return patch_persister(
            profile_id=profile_id,
            supplied=explicit_flags,
            colegio_concertado=_colegio_concertado_from_profile_values(scalar_profile_values),
        )

    profile_decode_context = operation.profile_decode_context()
    record = ProfileRecordRepository.for_current_session(
        profile_id,
        profile_decode_context=profile_decode_context,
    ).load(profile_id)
    published = apply_profile_patch(
        flow=flow,
        profile_id=profile_id,
        expected_revision=record.record_revision,
        expected_content_digest=record.content_digest,
        supplied=explicit_flags,
        colegio_concertado=_colegio_concertado_from_profile_values(scalar_profile_values),
        operation=operation,
    )
    merged_values = record_to_path_values(published)
    return merged_values, published.record_revision != record.record_revision


def _seed_default_answers(flow: WizardFlow, canonical: dict[str, str]) -> dict[str, str]:
    """Overlay explicit canonical answers on the flow's declared defaults."""
    seeded: dict[str, str] = {
        question.id: question.default or ""
        for section in flow.sections
        for question in section.questions
        if question.default is not None
    }
    seeded.update(canonical)
    return seeded


def _persist_full_flow_answers(
    flow: WizardFlow,
    answers: BaseModel,
    *,
    profile_id: str,
    operation: PinnedAuthorityOperation,
) -> dict[str, str]:
    """Validate and persist one completed full-flow answer model."""
    from ...domain.user_profile.values import UserProfileFact
    from ..user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import record_to_path_values
    from .persistence import project_answers, serialise_answers

    profile_values = serialise_answers(flow, answers)
    profile_decode_context = operation.profile_decode_context()
    record = ProfileRecordRepository.for_current_session(
        profile_id,
        profile_decode_context=profile_decode_context,
    ).load(profile_id)
    values = record_to_path_values(record)
    values.update({path: value for path, value in profile_values.items() if value})
    require_filing_baseline(flow, project_answers(flow, values))
    from ...domain.deadlines.profiles import taxpayer_profile_from_mapping

    taxpayer_profile_from_mapping(values, tax_id_default=values.get("identity.tax_id", ""))
    apply_profile_fact_changes(
        profile_id=profile_id,
        changes=tuple(UserProfileFact(path=path, value=value) for path, value in profile_values.items() if value),
        door=ProfileFactWriteDoor.ANSWERS,
        profile_decode_context=profile_decode_context,
    )
    return values


def _run_full_flow(
    flow: WizardFlow,
    canonical: dict[str, str],
    *,
    quiet: bool,
    accept_defaults: bool,
    profile_name: str,
    profile_id: str,
    mode: WizardPersistMode,
    operation: PinnedAuthorityOperation,
    explicit_question_ids: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Walk the full wizard flow and persist the resulting answer set.

    This is the full-flow path for an edit. Create is refused before any
    console or checkpoint can be opened because credential registration owns
    profile creation.

    ``explicit_question_ids`` names the questions whose flag the
    operator supplied on a non-interactive command line. Such a
    question is collected even when its ``visible_when`` gate would
    hide it, so an explicitly-given flag value is always honoured.

    """
    from ..user_profile.registration import ProfileRegistrationError

    if mode == "create":
        raise ProfileRegistrationError(
            "wizard profile creation is unavailable; register with credentials before setup",
        )

    if accept_defaults:
        canonical = _seed_default_answers(flow, canonical)

    if quiet:
        missing = _missing_required_flags(flow, canonical)
        if missing:
            missing_flags = format_missing_flags(missing)
            raise WizardMissingFlagError(
                translated_message="application.wizard.errors.quiet_missing_flags",
                context={
                    "flow_id": flow.id,
                    "missing": missing,
                    "missing_flags": missing_flags,
                },
                precondition_verdict=wizard_no_action_verdict(
                    condition=WizardPreconditionCondition.REQUIRED_FLAGS_SUPPLIED,
                    facts={
                        "required_flags_supplied": False,
                        "missing_flag_count": len(missing),
                    },
                    provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            )
        answers = _run_scripted_walk(
            flow,
            canonical,
            mode=mode,
            explicit_question_ids=explicit_question_ids,
            operation=operation,
        )
    elif accept_defaults:
        answers = _run_scripted_walk(
            flow,
            canonical,
            mode=mode,
            explicit_question_ids=explicit_question_ids,
            operation=operation,
        )
    else:
        # There is no interactive walk here any more. An operator at a
        # capable terminal was already diverted to the profile manager
        # before this command ran, so reaching this branch means the host
        # cannot present a screen at all.  The terminal verdict records that
        # factual capability refusal without prescribing a replacement flow.
        if mode == "edit":
            raise WizardEditUnsupportedConsoleError(
                translated_message="wizard.errors.unsupported_console_edit",
                context={"profile_name": profile_name},
                precondition_verdict=wizard_no_action_verdict(
                    condition=WizardPreconditionCondition.INTERACTIVE_CONSOLE_AVAILABLE,
                    facts={"interactive_console_available": False},
                    provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                    outcome=NoRecoveryOutcome.SAFETY,
                ),
            )
        raise WizardUnsupportedConsoleError(
            translated_message="wizard.errors.unsupported_console",
            precondition_verdict=wizard_no_action_verdict(
                condition=WizardPreconditionCondition.INTERACTIVE_CONSOLE_AVAILABLE,
                facts={"interactive_console_available": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )

    # `create` writes the full answer set. An interactive `edit` writes a
    # patch scoped to the pages the operator actually answered
    # (``supplied_question_ids``); the full serialisation here feeds the
    # filing-baseline survival check and the success payload.
    return _persist_full_flow_answers(flow, answers, profile_id=profile_id, operation=operation)


def _enter_requested_output_language(kwargs: dict[str, object], language_stack: contextlib.ExitStack) -> None:
    """Apply a command-line output-language override for the command body."""
    from ...core.config import override_settings

    requested_language = kwargs.get("output_language")
    if isinstance(requested_language, str) and requested_language in SUPPORTED_OUTPUT_LANGUAGES:
        language_stack.enter_context(override_settings(cadrumo_output_language=requested_language))


def _render_error_inside_language_override(exc: CadrumoError) -> None:
    """Freeze a translated Cadrumo error message before locale overrides unwind."""
    translated_key = exc.translated_message
    if not isinstance(translated_key, str) or not translated_key:
        return

    context = _translation_context(getattr(exc, "context", None))
    rendered = tr(translated_key, **context)
    exc.args = (rendered, *exc.args[1:])
    exc.translated_message = None


def _require_profile_name(flow: WizardFlow, raw_profile_name: object) -> str:
    """Return a stripped profile name or raise the wizard missing-flag error."""
    if isinstance(raw_profile_name, str) and raw_profile_name.strip():
        return raw_profile_name.strip()
    raise WizardMissingFlagError(
        translated_message="application.wizard.errors.profile_flag_required",
        context={"flow_id": flow.id, "missing": ("profile_name",)},
        precondition_verdict=wizard_no_action_verdict(
            condition=WizardPreconditionCondition.PROFILE_NAME_SUPPLIED,
            facts={"profile_name_supplied": False},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


def _resolve_profile_id_for_mode(flow: WizardFlow, mode: WizardPersistMode, profile_name: str) -> str:
    """Resolve or mint the immutable profile id for the requested wizard mode.

    A ``create`` always addresses a fresh capsule, so a label already bound to
    a committed capsule is refused here rather than minting an id that could
    never be published. The refusal is an early, operator-facing one over the
    same committed-label projection the resolver below reads; the race-free
    authority remains the custody service's check under the custody-root lock,
    which still backstops this one. A genuinely new label mints a fresh id.

    Any other mode addresses an existing capsule, and the resolution below is
    itself the registration check: an unresolvable label falls through to the
    missing-flag refusal.
    """
    from ...domain.user_profile.values import new_profile_id
    from ..workflow.profile_bucket_scan import read_profile_bucket

    if mode == "create":
        _require_profile_label_available(
            flow,
            profile_name,
            label_is_registered=read_profile_bucket(profile_name) is not None,
        )
        return new_profile_id()

    pointer = read_profile_bucket(profile_name)
    if pointer is not None:
        return pointer.bucket_id
    raise WizardMissingFlagError(
        translated_message="application.wizard.errors.profile_flag_required",
        context={"flow_id": flow.id, "missing": ("profile_name",)},
        precondition_verdict=wizard_no_action_verdict(
            condition=WizardPreconditionCondition.PROFILE_NAME_SUPPLIED,
            facts={"profile_name_supplied": False},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


def _require_profile_label_available(
    flow: WizardFlow,
    profile_name: str,
    *,
    label_is_registered: bool,
) -> None:
    """Refuse create when the committed-label projection already owns a label.

    The caller resolves the persistence fact; this deterministic policy owns
    the operator-facing precondition and remains independent of bucket access.
    """
    if not label_is_registered:
        return
    raise WizardValidationError(
        translated_message="application.wizard.errors.profile_label_taken",
        context={"flow_id": flow.id, "label": profile_name},
        precondition_verdict=wizard_no_action_verdict(
            condition=WizardPreconditionCondition.PROFILE_LABEL_AVAILABLE,
            facts={"profile_registration_available": False},
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


def _resolve_profile_target_for_mode(
    flow: WizardFlow,
    mode: WizardPersistMode,
    raw_profile_name: object,
) -> tuple[str, str]:
    """Resolve the display label and immutable id addressed by a wizard verb.

    An explicit name keeps the existing create/edit resolver contract. An
    omitted edit addresses the active profile, matching the profile manager and
    the root authentication gate that precedes this command. Create has no
    existing subject to inherit and therefore retains its missing-name refusal.
    """
    if isinstance(raw_profile_name, str) and raw_profile_name.strip():
        profile_name = raw_profile_name.strip()
        return profile_name, _resolve_profile_id_for_mode(flow, mode, profile_name)
    if mode == "create":
        profile_name = _require_profile_name(flow, raw_profile_name)
        return profile_name, _resolve_profile_id_for_mode(flow, mode, profile_name)

    from ...core.bucket_pointer import require_active_bucket_id
    from ..user_profile.login_session import resolve_login_target

    target = resolve_login_target(require_active_bucket_id())
    return target.label, target.bucket_id


def _seed_output_language_from_environment(canonical: dict[str, str]) -> None:
    """Use CADRUMO_OUTPUT_LANGUAGE when the operator omitted the explicit flag."""
    from ...core.config import load_settings

    if "output-language" in canonical:
        return

    env_lang = load_settings().cadrumo_output_language
    if isinstance(env_lang, str) and env_lang in SUPPORTED_OUTPUT_LANGUAGES:
        canonical["output-language"] = env_lang


# ``SetupAnswers`` field names whose free-text value fails an ISO-8601 date or
# a decimal validator. Keyed on the pydantic error ``loc`` leaf so the raw
# English validator ``msg`` never reaches operator output.
_WIZARD_INVALID_DATE_FIELDS: frozenset[str] = frozenset(
    {
        "taxpayer_marriage_date",
        "activity_start_date",
        "irpf_special_regime_start_date",
    }
)
_WIZARD_INVALID_DECIMAL_FIELDS: frozenset[str] = frozenset(
    {
        "incn_prior_12_months",
    }
)
_WIZARD_ERROR_FIELD_KEYS: dict[str, str] = {
    **{field: "wizard.errors.invalid_date" for field in _WIZARD_INVALID_DATE_FIELDS},
    **{field: "wizard.errors.invalid_decimal" for field in _WIZARD_INVALID_DECIMAL_FIELDS},
}

# Cross-field model-validator refusals report an empty ``loc``, so they are
# routed on the stable pydantic error ``type`` (a ``PydanticCustomError`` token
# raised by ``SetupAnswers``). Each maps to its localized detail key plus the
# primary and condition fields whose flags fill the message.
_WIZARD_ERROR_TYPE_KEYS: dict[str, tuple[str, str, str]] = {
    "spouse_tax_id_required_joint": (
        "wizard.errors.spouse_tax_id_required_joint",
        "spouse_tax_id",
        "taxation_type",
    ),
    "eu_eea_country_required": (
        "wizard.errors.eu_eea_country_required",
        "spouse_eu_eea_country",
        "spouse_eu_eea_resident",
    ),
}


def _wizard_field_flags(flow: WizardFlow) -> dict[str, str]:
    """Return answers-model field names mapped to their CLI flag names."""
    return {
        question.id.replace("-", "_"): flag_name(question)
        for section in flow.sections
        for question in section.questions
    }


def _validation_location_flag(location: tuple[object, ...], field_flags: dict[str, str]) -> str:
    """Render a pydantic location tuple as a flag-oriented field path."""
    path: list[str] = []
    for part in location:
        if part == "__root__":
            continue
        if isinstance(part, str):
            path.append(field_flags.get(part, part))
        else:
            path.append(str(part))
    return ".".join(path)


def _validation_leaf_field(location: tuple[object, ...]) -> str:
    """Return the trailing model field name from a pydantic location tuple."""
    for part in reversed(location):
        if isinstance(part, str) and part != "__root__":
            return part
    return ""


def _stringify_wizard_error_input(value: object) -> str:
    """Render the rejected input value for the ``got`` message context."""
    if value is None:
        return ""
    return str(value)


def _format_wizard_validation_error(flow: WizardFlow, item: ErrorDetails) -> tuple[str | None, str | None]:
    """Render one pydantic validation entry as a localized detail plus its flag.

    The detail is built entirely from a translation-key mapping: cross-field
    model-validator refusals route on the stable pydantic error ``type``, and
    free-text date/decimal value errors route on the failing field's ``loc``
    leaf. The raw pydantic ``msg`` (library English) is never spliced into
    operator output. An entry with no mapped key returns a ``None`` detail so
    the caller falls back to the localized generic message; the failing flag is
    still returned for the ``param_hint``.
    """
    field_flags = _wizard_field_flags(flow)
    error_type = item.get("type", "")
    cross_field = _WIZARD_ERROR_TYPE_KEYS.get(error_type)
    if cross_field is not None:
        key, primary_field, condition_field = cross_field
        primary_flag = field_flags.get(primary_field, primary_field)
        condition_flag = field_flags.get(condition_field, condition_field)
        return tr(key, flag=primary_flag, condition_flag=condition_flag), primary_flag

    location = tuple(item.get("loc", ()))
    field_flag = _validation_location_flag(location, field_flags) or None
    if error_type == "value_error":
        field_key = _WIZARD_ERROR_FIELD_KEYS.get(_validation_leaf_field(location))
        if field_key is not None:
            got = _stringify_wizard_error_input(item.get("input"))
            return tr(field_key, flag=field_flag or _validation_leaf_field(location), got=got), field_flag
    return None, field_flag


def _wizard_validation_bad(flow: WizardFlow, error: ValidationError) -> typer.BadParameter:
    """Convert leaked wizard answer validation into a specific CLI refusal."""
    rendered = [_format_wizard_validation_error(flow, item) for item in error.errors()]
    mapped_details = [detail for detail, _flag in rendered if detail is not None]
    details = (
        "; ".join(mapped_details) if mapped_details else tr("application.wizard.errors.command_input_invalid_fallback")
    )
    message = tr("application.wizard.errors.command_input_invalid", details=details)
    first_flag = next((flag for _detail, flag in rendered if (flag is not None and flag)), None)
    if first_flag is not None:
        return typer.BadParameter(message, param_hint=f"'{first_flag}'")
    return typer.BadParameter(message)


def _run_wizard_persistence_path(
    flow: WizardFlow,
    mode: WizardPersistMode,
    canonical: dict[str, str],
    explicit_flags: dict[str, str],
    *,
    scalar_profile_values: Mapping[str, str],
    quiet: bool,
    accept_defaults: bool,
    profile_name: str,
    profile_id: str,
    operation: PinnedAuthorityOperation,
    patch_persister: WizardPatchPersister | None = None,
) -> tuple[dict[str, str], bool]:
    """Dispatch to patch-edit or full-flow persistence.

    Returns the resulting values and whether a record revision was published.
    The full-flow path always writes; only the patch path can be a no-op.
    """
    # The one explicit non-wizard scalar is a complete patch on its own.  It
    # must not be swallowed by the interactive flow, whose catalogue correctly
    # has no defaultable question for this legal declaration.
    non_interactive = quiet or accept_defaults or bool(scalar_profile_values)
    if mode == "edit" and non_interactive:
        return _run_patch_edit(
            flow,
            explicit_flags,
            scalar_profile_values=scalar_profile_values,
            profile_id=profile_id,
            operation=operation,
            patch_persister=patch_persister,
        )

    return _run_full_flow(
        flow,
        canonical,
        quiet=quiet,
        accept_defaults=accept_defaults,
        profile_name=profile_name,
        profile_id=profile_id,
        mode=mode,
        operation=operation,
        explicit_question_ids=frozenset(explicit_flags),
    ), True


#: The routing projection's default suggestion: a profile carrying no
#: fiscal-residency classification that redirects it elsewhere. Public
#: because a consumer projecting this same guidance onto another surface
#: (the profile manager) needs to tell "the ordinary default applies" from
#: "this profile earned a specific next step" without re-deriving the
#: comparison.
def _execute_wizard_command(
    flow: WizardFlow,
    mode: WizardPersistMode,
    *,
    kwargs: dict[str, object],
    operation: PinnedAuthorityOperation,
    invocation_notices: Callable[[], Sequence[Notice]],
    patch_persister: WizardPatchPersister | None = None,
) -> None:
    """Run the wizard command body after Typer has parsed dynamic flags."""
    profile_name, profile_id = _resolve_profile_target_for_mode(
        flow,
        mode,
        kwargs.pop("profile_name"),
    )
    quiet = bool(kwargs.pop("quiet", False))
    accept_defaults = bool(kwargs.pop("accept_defaults", False))
    canonical = _collect_flag_values(flow, kwargs)
    explicit_flags: dict[str, str] = dict(canonical)
    scalar_profile_values = _colegio_concertado_profile_value(kwargs)

    _seed_output_language_from_environment(canonical)
    # Freeze the final-envelope disclosure notices in the command-level output
    # language now, BEFORE the interactive walk can activate a mid-walk
    # override that shadows this language by the time the envelope is emitted.
    # The envelope is a command-level disclosure, not walk content, so it must
    # render in the language the command entered with — the same pre-render
    # discipline the error path uses for a translated refusal.
    modify_no_resume_message = tr("application.wizard.notices.modify_no_resume")
    modify_descendants_message = tr("application.wizard.notices.modify_descendants_via_door")
    refuse_foral_ccaa(canonical, explicit_flags, operation=operation)
    try:
        profile_values, record_changed = _run_wizard_persistence_path(
            flow,
            mode,
            canonical,
            explicit_flags,
            scalar_profile_values=scalar_profile_values,
            quiet=quiet,
            accept_defaults=accept_defaults,
            profile_name=profile_name,
            profile_id=profile_id,
            operation=operation,
            patch_persister=patch_persister,
        )
    except ValidationError as exc:
        raise _wizard_validation_bad(flow, exc) from exc
    # Every interactive modify run carries the LOUD staged-only disclosure on
    # its final envelope: mid-flow save/resume is unavailable and an
    # interrupted modify discards its staged edits. Non-interactive patch
    # edits (`--quiet` / `--accept-defaults`) stage nothing, so the notice is
    # scoped to the interactive walk.
    interactive_modify = mode == "edit" and not (quiet or accept_defaults or scalar_profile_values)
    default_ccaa_value = next(
        (
            question.default
            for section in flow.sections
            for question in section.questions
            if question.id == "tax-residence-ccaa"
        ),
        None,
    )
    next_command = next_step_command_for_profile_values(profile_values, operation=operation)
    emit_wizard_success(
        mode,
        profile_name,
        record_changed=record_changed,
        next_command=next_command,
        ccaa_defaulted=ccaa_was_defaulted(
            mode,
            explicit_flags,
            profile_values,
            non_interactive=quiet or accept_defaults,
            default_ccaa_value=default_ccaa_value,
        ),
        modify_no_resume=interactive_modify,
        modify_no_resume_message=modify_no_resume_message,
        modify_descendants_via_door=interactive_modify,
        modify_descendants_message=modify_descendants_message,
        default_ccaa_value=default_ccaa_value,
        invocation_notices=invocation_notices,
    )


def build_wizard_command(
    flow: WizardFlow,
    *,
    mode: WizardPersistMode,
    operation: PinnedAuthorityOperation,
    invocation_notices: Callable[[], Sequence[Notice]] = tuple,
    patch_persister: WizardPatchPersister | None = None,
) -> Callable[..., None]:
    """Return a Typer-compatible callable that runs ``flow``.

    The returned closure carries one parameter per question in the
    flow (typed and annotated for Typer to derive a CLI flag) plus the
    three mode flags.

    ``mode`` binds the closure to a single wizard verb. ``"create"``
    refuses a name that already has a manifest; ``"edit"`` refuses a
    name that has none. Both refusals fire before the wizard prompts,
    so an operator is never walked through 40-odd questions only to
    have the persistence step reject the work.

    There is no interactive walk: an operator at a capable terminal is
    diverted to the profile manager before this command runs, so what is
    left here is the programmatic contract — flags in, JSON envelope out.
    An invocation that supplies neither ``--quiet``/``--accept-defaults``
    nor the values it needs is refused with the flag form named.
    """
    question_params = question_parameters(flow, operation=operation)
    mode_params = mode_parameters(flow, mode=mode)
    parameters = (*mode_params, *question_params)
    signature, annotations = wizard_command_metadata(parameters)

    def _command(**kwargs: object) -> None:
        from ...core.errors.hierarchy import CadrumoError

        with contextlib.ExitStack() as _language_stack:
            # When the operator supplies `--output-language` on the
            # command line, that language must drive every operator-
            # facing string this command renders — including a
            # creation-time refusal raised before the profile exists
            # (e.g. a missing `--activity` under `--quiet`). The flag
            # value is already parsed; apply it as a settings override
            # for the whole command body so the error boundary renders
            # in the requested language rather than falling back to the
            # default. The override unwinds when the command returns.
            _enter_requested_output_language(kwargs, _language_stack)
            try:
                _execute_wizard_command(
                    flow,
                    mode,
                    kwargs=kwargs,
                    operation=operation,
                    invocation_notices=invocation_notices,
                    patch_persister=patch_persister,
                )
            except CadrumoError as exc:
                # Pre-render translated_message INSIDE the override so the
                # error boundary's renderer (which runs after the ExitStack
                # unwinds) sees the already-localised string. Without this
                # the override is gone by the time render_error_text fires,
                # and the refusal falls back to the default language.
                _render_error_inside_language_override(exc)
                raise

    # CAST-RATIONALE-WIZARD-COMMAND-INJECT: Typer resolves CLI parameters
    # from ``__signature__`` at decoration time; the cast to ``Any`` is the
    # only way to assign a dynamically-built ``inspect.Signature`` without
    # mypy complaining about the ``Callable`` type being immutable.  The
    # runtime object is always the real ``_command`` function — the cast
    # only widens the static view so the attribute assignments below are
    # accepted by the type checker.
    typed = typing.cast(typing.Any, _command)
    typed.__signature__ = signature
    typed.__annotations__ = annotations
    typed.__name__ = flow.id
    typed.__doc__ = tr(f"wizard.{flow.id}.description")
    typed.__wizard_flow__ = flow
    return _command
