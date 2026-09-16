"""Focused unit tests for wizard.commands pure helpers.

`_commands.py` ships several small pure helpers behind the public
`build_wizard_command` Typer-binding orchestrator. The end-to-end
Typer-invocation tests exercise them only indirectly. A regression
in (for example) dropping the `visible_when is None` predicate from
`_required_flag_questions`, or returning Path objects instead of
strings from `_canonical_from_flag_value`, would silently break the
wizard's --quiet-mode validation across every operator's setup
session.

Tests here pin each helper's documented branch behaviour;
assertions are structural / mapper-contract assertions, not
calculation tautologies.
"""

from __future__ import annotations

import inspect
import typing
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

import click
import pytest
import typer
from typer.testing import CliRunner

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....core.i18n.translatable import Translatable as tr
from ....domain.calculations.registry.ccaa_catalogue import ccaa_choices, resolve_ccaa_catalogue
from ..catalogue import build_setup_flow
from ..commands import (
    SETUP_OPTION_INFOS,
    _canonical_from_flag_value,
    _flag_name,
    _format_missing_flags,
    _help_key,
    _missing_required_flags,
    _required_flag_questions,
    _wizard_command_metadata,
    build_wizard_command,
)
from ..models import WizardCondition, WizardFlow, WizardQuestion, WizardSection, WizardWidget
from .registry_setup_flow_support import EmptyAnswersBase

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _question(
    *,
    qid: str = "example",
    answer_type: type[str] | type[bool] | type[int] | type[Path] = str,
    widget: WizardWidget = WizardWidget.TEXT,
    required: bool = True,
    default: str | None = None,
    visible_when: WizardCondition | None = None,
) -> WizardQuestion:
    return WizardQuestion(
        id=qid,
        widget=widget,
        prompt=tr("wizard.test.example.prompt"),
        choices=(),
        default=default,
        required=required,
        visible_when=visible_when,
        answer_type=answer_type,
    )


def _flow(*questions: WizardQuestion) -> WizardFlow:
    return WizardFlow(
        id="test",
        title=tr("wizard.test.title"),
        description=tr("wizard.test.description"),
        sections=(
            WizardSection(
                id="main",
                title=tr("wizard.test.main.title"),
                questions=questions,
            ),
        ),
        answers_model=EmptyAnswersBase,
    )


# ---------------------------------------------------------------------------
# _flag_name
# ---------------------------------------------------------------------------


def test_flag_name_prefixes_double_dash_to_question_id() -> None:
    question = _question(qid="tax_id")
    assert _flag_name(question) == "--tax_id"


def test_tax_residence_ccaa_option_uses_short_metavar() -> None:
    """The CCAA option declares a short metavar so the help table does not
    wrap the 15-choice list mid-token inside its bracket.

    Before fix: Rich rendered the full ``[andalucia|...|murcia]`` choice
    list as one ~150-char metavar and broke it inside a token (``com``
    / ``unidad_valenciana``).
    After fix: the metavar is the compact ``CCAA`` token and choices
    are not shown in the metavar bracket.
    """

    option = SETUP_OPTION_INFOS["tax-residence-ccaa"]
    assert isinstance(option, typer.models.OptionInfo)

    assert option.metavar == "CCAA"
    assert option.show_choices is False


@pytest.fixture
def _isolated_setup_option_infos() -> Iterator[None]:
    """Restore the shared setup option registry after a test builds the wizard command.

    Building the command inserts options and mutates the shared ``OptionInfo``
    objects in place (choice type, metavar, help, panel), so both the mapping
    membership and every option's attribute state are restored, keeping each
    object's identity for the modules that hold references to it.
    """
    saved_entries = dict(SETUP_OPTION_INFOS)
    saved_state = {key: dict(vars(option)) for key, option in saved_entries.items() if option is not None}
    try:
        yield
    finally:
        SETUP_OPTION_INFOS.clear()
        SETUP_OPTION_INFOS.update(saved_entries)
        for key, state in saved_state.items():
            option = saved_entries[key]
            assert option is not None
            vars(option).clear()
            vars(option).update(state)


@pytest.mark.usefixtures("_isolated_setup_option_infos")
def test_tax_residence_ccaa_choices_match_the_ccaa_enum(authority_operation: PinnedAuthorityOperation) -> None:
    """The CCAA choice tokens are the canonical CCAA catalogue plus foral redirects.

    The foral tokens are accepted by Click so the operator receives a
    localised redirect-to-foral-Hacienda refusal rather than a generic
    "not one of" error; the wizard persistence layer rejects them via
    ``ForalRegimeError``. The choices are read from the option the command
    builder materializes for the leased setup flow, and the expectation
    comes from the registry CCAA catalogue rather than from the wizard.
    """

    build_wizard_command(build_setup_flow(authority_operation), mode="create", operation=authority_operation)
    option = SETUP_OPTION_INFOS["tax-residence-ccaa"]
    assert option is not None, "the command builder materialized no --tax-residence-ccaa option"
    choice_type = option.click_type
    assert isinstance(choice_type, click.Choice)

    expected = [member.value for member in ccaa_choices(authority=authority_operation)] + list(
        resolve_ccaa_catalogue(authority=authority_operation).foral_cli_aliases
    )
    assert list(choice_type.choices) == expected


# ---------------------------------------------------------------------------
# _help_key
# ---------------------------------------------------------------------------


def test_help_key_composes_wizard_flow_flags_question_help_key() -> None:
    flow = _flow(_question(qid="tax_id"))
    question = _question(qid="tax_id")
    assert _help_key(flow, question) == "wizard.test.flags.tax_id.help"


# ---------------------------------------------------------------------------
# _required_flag_questions
# ---------------------------------------------------------------------------


def test_required_flag_questions_includes_unconditionally_required_question() -> None:
    """A required question with no visible_when is unconditionally
    required in --quiet mode."""
    required_q = _question(qid="tax_id", required=True, visible_when=None)
    flow = _flow(required_q)

    required = _required_flag_questions(flow)

    assert len(required) == 1
    assert required[0].id == "tax_id"


def test_required_flag_questions_omits_conditionally_visible_question() -> None:
    """A required question with `visible_when` set is conditional —
    --quiet mode does NOT enforce its presence because the question
    may not be shown at all depending on earlier answers."""
    gate_q = _question(qid="declaration_type", required=True, visible_when=None)
    conditional_q = _question(
        qid="spouse_tax_id",
        required=True,
        visible_when=WizardCondition(question_id="declaration_type", equals="2"),
    )
    flow = _flow(gate_q, conditional_q)

    required = _required_flag_questions(flow)

    assert tuple(q.id for q in required) == ("declaration_type",)


def test_required_flag_questions_omits_non_required_question() -> None:
    optional_q = _question(qid="name", required=False, visible_when=None)
    required_q = _question(qid="tax_id", required=True, visible_when=None)
    flow = _flow(optional_q, required_q)

    required = _required_flag_questions(flow)

    assert tuple(q.id for q in required) == ("tax_id",)


# ---------------------------------------------------------------------------
# _missing_required_flags
# ---------------------------------------------------------------------------


def test_missing_required_flags_returns_question_id_when_no_value_and_no_default() -> None:
    flow = _flow(_question(qid="tax_id", required=True, default=None))

    missing = _missing_required_flags(flow, {})

    assert missing == ("tax_id",)


def test_missing_required_flags_backfills_descriptor_default_into_canonical() -> None:
    """When the canonical dict lacks the question's value but the
    descriptor has a default, the default is backfilled into the
    canonical dict (side effect) and the question is NOT returned
    in the missing tuple."""
    flow = _flow(_question(qid="tax_residence_ccaa", required=True, default="madrid"))
    canonical: dict[str, str] = {}

    missing = _missing_required_flags(flow, canonical)

    assert missing == ()
    assert canonical["tax_residence_ccaa"] == "madrid"


def test_missing_required_flags_omits_question_when_value_already_set() -> None:
    flow = _flow(_question(qid="tax_id", required=True, default=None))
    canonical = {"tax_id": "12345678Z"}

    missing = _missing_required_flags(flow, canonical)

    assert missing == ()


def test_missing_required_flags_treats_empty_string_value_as_missing() -> None:
    """An empty canonical value is treated as not-supplied; the
    descriptor's default (if any) is backfilled, otherwise the
    question is reported missing."""
    flow = _flow(_question(qid="tax_id", required=True, default=None))
    canonical = {"tax_id": ""}

    missing = _missing_required_flags(flow, canonical)

    assert missing == ("tax_id",)


# ---------------------------------------------------------------------------
# _format_missing_flags
# ---------------------------------------------------------------------------


def test_format_missing_flags_renders_question_ids_as_long_options() -> None:
    """A missing-flag refusal must name the actual `--flag` an operator
    types, never a raw Python identifier tuple."""

    assert _format_missing_flags(("tax-id", "activity")) == "--tax-id --activity"


def test_format_missing_flags_single_question_id() -> None:
    assert _format_missing_flags(("activity",)) == "--activity"


def test_format_missing_flags_empty_tuple_renders_empty_string() -> None:
    assert _format_missing_flags(()) == ""


# ---------------------------------------------------------------------------
# _canonical_from_flag_value
# ---------------------------------------------------------------------------


def test_canonical_from_flag_value_none_returns_none() -> None:
    question = _question()
    assert _canonical_from_flag_value(question, None) is None


def test_canonical_from_flag_value_confirm_true_returns_true_token() -> None:
    question = _question(widget=WizardWidget.CONFIRM, answer_type=bool)
    assert _canonical_from_flag_value(question, True) == "true"


def test_canonical_from_flag_value_confirm_false_returns_false_token() -> None:
    question = _question(widget=WizardWidget.CONFIRM, answer_type=bool)
    assert _canonical_from_flag_value(question, False) == "false"


def test_canonical_from_flag_value_confirm_non_bool_returns_none() -> None:
    """A CONFIRM-widget question with a non-bool Typer-parsed value is
    a parser anomaly; the helper refuses to coerce silently."""
    question = _question(widget=WizardWidget.CONFIRM, answer_type=bool)
    assert _canonical_from_flag_value(question, "true") is None


def test_canonical_from_flag_value_integer_returns_decimal_string() -> None:
    question = _question(widget=WizardWidget.INTEGER, answer_type=int)
    assert _canonical_from_flag_value(question, 42) == "42"


def test_canonical_from_flag_value_path_returns_str_form() -> None:
    question = _question(widget=WizardWidget.PATH, answer_type=Path)
    assert _canonical_from_flag_value(question, Path("project/data/example.txt")) == str(
        Path("project/data/example.txt"),
    )


def test_canonical_from_flag_value_text_widget_passes_string_through() -> None:
    question = _question(widget=WizardWidget.TEXT, answer_type=str)
    assert _canonical_from_flag_value(question, "madrid") == "madrid"


def test_canonical_from_flag_value_checkbox_joins_tokens_with_comma() -> None:
    """CHECKBOX widget aggregates a list of values into a comma-joined
    canonical token. Empty list returns None (no value supplied)."""
    question = _question(widget=WizardWidget.CHECKBOX, answer_type=str)

    assert _canonical_from_flag_value(question, ["a", "b", "c"]) == "a,b,c"
    assert _canonical_from_flag_value(question, []) is None


def test_canonical_from_flag_value_checkbox_non_iterable_returns_none() -> None:
    """A CHECKBOX-widget question with a non-iterable Typer-parsed
    value is rejected as a parser anomaly."""
    question = _question(widget=WizardWidget.CHECKBOX, answer_type=str)
    assert _canonical_from_flag_value(question, "madrid") is None


# ---------------------------------------------------------------------------
# Dynamic command signatures
# ---------------------------------------------------------------------------


def test_wizard_command_metadata_keeps_signature_and_annotations_in_lockstep() -> None:
    """Both runtime consumers receive the same public annotation objects."""
    annotation = Annotated[str, "wizard-metadata"]
    annotated = inspect.Parameter(
        "value",
        kind=inspect.Parameter.KEYWORD_ONLY,
        annotation=annotation,
    )
    unannotated = inspect.Parameter(
        "ignored",
        kind=inspect.Parameter.KEYWORD_ONLY,
    )

    signature, annotations = _wizard_command_metadata((annotated, unannotated))

    assert signature.parameters["value"].annotation is annotation
    assert annotations == {"value": annotation}


def test_build_wizard_command_exposes_resolvable_annotation_metadata() -> None:
    """Future-annotation source policy does not erase dynamic Typer metadata."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        command = build_wizard_command(
            _flow(_question(qid="activity", widget=WizardWidget.TEXT)),
            mode="create",
            operation=_authority_operation_for_test,
        )

        signature = inspect.signature(command)
        raw_annotations = inspect.get_annotations(command, eval_str=False)
        resolved_annotations = typing.get_type_hints(command, include_extras=True)

        assert tuple(raw_annotations) == tuple(signature.parameters)
        assert tuple(resolved_annotations) == tuple(signature.parameters)
        assert resolved_annotations["activity"] == signature.parameters["activity"].annotation
        assert typing.get_origin(resolved_annotations["activity"]) is typing.Annotated
        assert typing.get_args(resolved_annotations["activity"])[1].help is not None


def test_build_wizard_command_is_discoverable_by_typer() -> None:
    """Typer can register the generated signature and expose its flag."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        command = build_wizard_command(
            _flow(_question(qid="activity", widget=WizardWidget.TEXT)),
            mode="create",
            operation=_authority_operation_for_test,
        )
        app = typer.Typer()
        app.command()(command)

        result = CliRunner().invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "--activity" in result.stdout
