"""Real-behavior tests for the MODIFY-mode staging-honesty surfacing.

Modify stages answers in flow state only and commits once at review, so
two honesty surfaces must be LOUD, never silent:

1. THE SAVE ATTEMPT — the substrate's per-mode checkpoint declaration
   makes save-and-exit UNAVAILABLE in modify, so the review renders the
   substrate's ``flows.review.save_unavailable`` refusal and never offers
   the save action. Driven here through the real
   :class:`~cadrumo.application.flows.LineFlowFrontend` over a definition
   carrying the setup flow's own checkpoint declaration.
2. THE ENVELOPE — every interactive modify run's final envelope carries
   an info :class:`Notice` (``config.profile.edit.modify_no_resume``)
   stating mid-flow save/resume is unavailable and an interrupted modify
   discards its staged edits, regardless of whether a save was attempted.

Finding (reported to the coordinator): the substrate refusal copy
(``flows.review.save_unavailable``) communicates that save-and-exit is
unavailable and the flow must be finished in one sitting; the fuller
"discards staged edits / create-only" disclosure is carried by the
envelope notice (surface 2). The two are distinct operator moments (the
in-walk save attempt vs the final envelope), so the envelope notice is not
redundant with the substrate copy.

Coordinated transient: ``application.wizard.notices.modify_no_resume``
lands in the coordinator's serialized locale pass right after this code
commits. The envelope tests assert the notice CODE and message KEY
IDENTITY (``tr(<key>)``), holding against the humanised fallback now and
the landed string later.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from io import StringIO
from pathlib import Path

import click
import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput
from pydantic import BaseModel

from ....core.config import override_settings
from ....core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from ....core.i18n import tr
from ....core.json_contract import NoticeSeverity
from ....tests.secure_sql import isolated_profile_storage_root
from ...flows import (
    CopyRef,
    FlowDefinition,
    FlowPage,
    FlowSection,
    LineFlowFrontend,
    checkpoint_available,
    flow_definition_from_wizard_flow,
)
from .._catalogue import SETUP_FLOW
from .._commands import (
    _MODIFY_DESCENDANTS_DOOR_CODE,
    _MODIFY_NO_RESUME_CODE,
    _SETUP_CHECKPOINT,
    _emit_wizard_success,
    _setup_flow_definition,
)
from .._descendant_group import DESCENDANT_ADOPTION_VALIDATOR_ID, DESCENDANTS_COUNT_PAGE_ID, DESCENDANTS_GROUP_ID
from .test_setup_flow_frontend import _invoke_interactive, _tokens_with_substitutions
from .test_setup_runtime import _scripted_answers_for_individual_declaration

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODIFY_NO_RESUME_MESSAGE = tr("application.wizard.notices.modify_no_resume")
_SAVE_UNAVAILABLE_MESSAGE = tr("flows.review.save_unavailable", mode=FlowMode.MODIFY.value)


# ── surface 1: the save attempt renders the substrate refusal ────────────


def _one_page_definition() -> FlowDefinition:
    """A one-required-page definition carrying the setup flow's checkpoint.

    Reuses ``_SETUP_CHECKPOINT`` (MODIFY UNAVAILABLE) — the setup flow's own
    per-mode declaration — so the rendered refusal is driven by the real
    posture the flow ships, not a synthetic one.
    """

    class _Answers(BaseModel):
        pass

    prompt = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="wizard.setup.title")
    return FlowDefinition(
        id="flows.modify.probe",
        title=prompt,
        description=prompt,
        sections=(
            FlowSection(
                id="s",
                title=prompt,
                items=(FlowPage(id="p_a", widget=FlowWidgetKind.TEXT, prompt=prompt, answer_type=str),),
            ),
        ),
        answers_model=_Answers,
        checkpoint=dict(_SETUP_CHECKPOINT),
    )


def test_modify_review_renders_save_unavailable_refusal() -> None:
    """The modify review surface renders the substrate save-unavailable refusal.

    Answer one page, reach review, submit. The rendered output must carry
    the substrate ``save_unavailable`` refusal — the operator is told save
    is unavailable at exactly the moment they would reach for it. That the
    save action itself is not offered is proven structurally by
    :func:`test_setup_flow_declares_modify_checkpoint_unavailable` (the
    refusal copy embeds the action phrase, so a text-absence check on the
    action title would be unsound).
    """
    buffer = StringIO()
    with create_pipe_input() as pipe:
        pipe.send_text("alpha\r\r")
        frontend = LineFlowFrontend(_one_page_definition(), input=pipe, output=PlainTextOutput(buffer))
        state, _projection = frontend.run(mode=FlowMode.MODIFY)

    rendered = buffer.getvalue()
    assert dict(state.answers) == {"p_a": "alpha"}
    assert _SAVE_UNAVAILABLE_MESSAGE in rendered


def test_setup_flow_declares_modify_checkpoint_unavailable() -> None:
    """The bridged setup definition declares MODIFY save UNAVAILABLE, CREATE AVAILABLE.

    The no-op checkpoint is a per-mode declaration on the definition (never
    a silent implementation detail), which is what drives the substrate
    refusal above.
    """
    definition = flow_definition_from_wizard_flow(SETUP_FLOW, checkpoint=_SETUP_CHECKPOINT)

    assert definition.checkpoint[FlowMode.MODIFY] is CheckpointAvailability.UNAVAILABLE
    assert checkpoint_available(definition, FlowMode.MODIFY) is False
    assert checkpoint_available(definition, FlowMode.CREATE) is True


# ── surface 2: the final envelope carries the info notice ────────────────


@pytest.fixture
def _json_context() -> Iterator[None]:
    with click.Context(click.Command("probe"), obj={"json": True}):
        yield


def test_edit_envelope_carries_modify_no_resume_notice(
    capsys: pytest.CaptureFixture[str],
    _json_context: None,
) -> None:
    """An interactive modify run's envelope carries the info staging-honesty notice."""
    _emit_wizard_success("edit", "probe-profile", modify_no_resume=True)

    document = json.loads(capsys.readouterr().out)
    codes = {notice["code"]: notice for notice in document["notices"]}
    assert _MODIFY_NO_RESUME_CODE in codes
    notice = codes[_MODIFY_NO_RESUME_CODE]
    assert notice["severity"] == NoticeSeverity.INFO.value
    assert notice["message"] == _MODIFY_NO_RESUME_MESSAGE


def test_envelope_omits_modify_notice_when_not_requested(
    capsys: pytest.CaptureFixture[str],
    _json_context: None,
) -> None:
    """The notice is scoped to interactive modify; a plain create omits it."""
    _emit_wizard_success("create", "probe-profile", modify_no_resume=False)

    document = json.loads(capsys.readouterr().out)
    codes = {notice["code"] for notice in document["notices"]}
    assert _MODIFY_NO_RESUME_CODE not in codes


# ── surface 3: the descendant group is withheld from modify mode ─────────


def test_modify_definition_carries_no_descendant_pages() -> None:
    """MODIFY withholds the descendant group; CREATE splices it in.

    Modify-mode seeding cannot instantiate the repeating group, so rendering
    it would show an operator's descendants as an empty group whose commit
    silently erases them. The gate is the mode-aware splice: the CREATE
    definition carries the count page, the group, and the adoption cross-field
    validator; the MODIFY definition carries none of them.
    """
    create_definition = _setup_flow_definition(SETUP_FLOW, attach_descendants=True)
    modify_definition = _setup_flow_definition(SETUP_FLOW, attach_descendants=False)

    create_familia = next(section for section in create_definition.sections if section.id == "familia")
    modify_familia = next(section for section in modify_definition.sections if section.id == "familia")
    create_ids = {item.id for item in create_familia.items}
    modify_ids = {item.id for item in modify_familia.items}

    assert {DESCENDANTS_COUNT_PAGE_ID, DESCENDANTS_GROUP_ID} <= create_ids
    assert DESCENDANT_ADOPTION_VALIDATOR_ID in create_definition.flow_validator_ids
    assert DESCENDANTS_COUNT_PAGE_ID not in modify_ids
    assert DESCENDANTS_GROUP_ID not in modify_ids
    assert DESCENDANT_ADOPTION_VALIDATOR_ID not in modify_definition.flow_validator_ids


def test_edit_envelope_carries_descendants_via_door_notice(
    capsys: pytest.CaptureFixture[str],
    _json_context: None,
) -> None:
    """An interactive modify run points the operator at the descendiente door.

    The group is withheld from modify mode, so the surface can never be
    silently absent: the final envelope carries an info notice naming the
    dedicated descendant-management command as its suggestion.
    """
    _emit_wizard_success("edit", "probe-profile", modify_descendants_via_door=True)

    document = json.loads(capsys.readouterr().out)
    codes = {notice["code"]: notice for notice in document["notices"]}
    assert _MODIFY_DESCENDANTS_DOOR_CODE in codes
    notice = codes[_MODIFY_DESCENDANTS_DOOR_CODE]
    assert notice["severity"] == NoticeSeverity.INFO.value
    assert notice["suggestion"] == "aeat config profile descendiente"


def test_create_envelope_omits_descendants_via_door_notice(
    capsys: pytest.CaptureFixture[str],
    _json_context: None,
) -> None:
    """The door notice is scoped to interactive modify; a create omits it."""
    _emit_wizard_success("create", "probe-profile", modify_descendants_via_door=False)

    document = json.loads(capsys.readouterr().out)
    codes = {notice["code"] for notice in document["notices"]}
    assert _MODIFY_DESCENDANTS_DOOR_CODE not in codes


@pytest.mark.parametrize(
    ("profile_language", "foreign_language"),
    [("en", "es"), ("es", "en")],
    ids=["en-profile", "es-profile"],
)
def test_interactive_edit_command_surfaces_the_staging_honesty_notice(
    profile_language: str,
    foreign_language: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The real interactive edit command surfaces the staging-honesty message.

    A profile is created, then re-walked with an edit script; the modify
    run's text output must carry the staging-honesty message so an operator
    who never pressed save still learns staged edits are discarded on an
    interrupted modify.

    Language provenance is the sharp half of the assertion: the profile
    chooses its language on the flow's first page, and the profile is the
    output-language authority for every later command, so the notice must
    render in the PROFILE's language and specifically NOT in the other
    locale. Both directions are pinned — the ``es-profile`` case is the
    operator's originally reported shape (a Spanish profile must never see
    the English notice). The expected strings are computed at use time
    under explicit overrides; an import-time constant renders in whatever
    locale happens to be ambient at collection and asserts the wrong
    authority.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        create_tokens = _tokens_with_substitutions(
            _scripted_answers_for_individual_declaration(),
            activity="Software development",
            output_language=profile_language,
        )
        _invoke_interactive("create", create_tokens, ["operator"])
        capsys.readouterr()

        edit_tokens = _tokens_with_substitutions(
            _scripted_answers_for_individual_declaration(),
            activity="Barbería",
            output_language=profile_language,
        )
        _invoke_interactive("edit", edit_tokens, ["operator"])
        output = capsys.readouterr().out

    with override_settings(cadrumo_output_language=profile_language):
        profile_language_message = tr("application.wizard.notices.modify_no_resume")
    with override_settings(cadrumo_output_language=foreign_language):
        foreign_language_message = tr("application.wizard.notices.modify_no_resume")

    assert profile_language_message in output
    assert foreign_language_message not in output
