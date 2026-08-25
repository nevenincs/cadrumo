"""Focused unit tests for wizard.persistence canonical-token helpers.

`_persistence` ships helpers that gate the canonical-token round-trip
between typed answers models and the profile-record string-dict
storage:

- ``_canonicalise(question, value)`` — typed value → canonical token.
- ``parse_canonical(question, raw)`` — canonical token → typed value.
- ``_resolve_canonical(question, values)`` — choose the token to
  project (values entry vs. descriptor default).

Currently exercised only indirectly through the
``test_persist_answers_round_trip_via_project_answers`` integration
test. A regression in any branch (swapping bool ``"true"`` ↔
``"false"`` renderings, returning ``Path("")`` instead of ``Path()``,
or skipping the descriptor-default fallback in `_resolve_canonical`)
would silently corrupt every operator's persisted wizard answers.

Tests here pin each helper's documented branch behaviour;
assertions are round-trip-contract assertions, not calculation
tautologies.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from ....core.i18n import Translatable as tr
from ...workflow.errors import WorkflowInputMismatchError
from ...workflow.state_models import WorkflowState
from ..models import WizardChoice, WizardFlow, WizardQuestion, WizardSection, WizardWidget
from ..persistence import _canonicalise, _resolve_canonical, parse_canonical, persist_patch

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _question(
    *,
    answer_type: type[str] | type[bool] | type[int] | type[Path] = str,
    profile_key: str | None = None,
    default: str | None = None,
    choices: tuple[WizardChoice, ...] = (),
    widget: WizardWidget = WizardWidget.TEXT,
) -> WizardQuestion:
    """Build a minimal WizardQuestion with wizard.test.* prefixed prompt."""
    return WizardQuestion(
        id="example",
        profile_key=profile_key,
        widget=widget,
        prompt=tr("wizard.test.example.prompt"),
        choices=choices,
        default=default,
        answer_type=answer_type,
    )


class _PatchAnswers(BaseModel):
    example: str = ""


def _flow(question: WizardQuestion) -> WizardFlow:
    return WizardFlow(
        id="test",
        title=tr("wizard.test.title"),
        description=tr("wizard.test.description"),
        sections=(
            WizardSection(
                id="section",
                title=tr("wizard.test.section.title"),
                questions=(question,),
            ),
        ),
        answers_model=_PatchAnswers,
    )


# ---------------------------------------------------------------------------
# _canonicalise
# ---------------------------------------------------------------------------


def test_canonicalise_none_returns_empty_string() -> None:
    question = _question(answer_type=str)
    assert _canonicalise(question, None) == ""


def test_canonicalise_bool_returns_lowercase_token() -> None:
    question = _question(answer_type=bool, widget=WizardWidget.CONFIRM)
    for value, expected in ((True, "true"), (False, "false")):
        assert _canonicalise(question, value) == expected


def test_canonicalise_path_returns_str_form() -> None:
    question = _question(answer_type=Path, widget=WizardWidget.PATH)
    path_value = Path("project/data/example.txt")
    assert _canonicalise(question, path_value) == str(path_value)


def test_canonicalise_int_returns_decimal_string() -> None:
    question = _question(answer_type=int, widget=WizardWidget.INTEGER)
    assert _canonicalise(question, 42) == "42"


def test_canonicalise_str_passes_through_unchanged() -> None:
    question = _question(answer_type=str)
    assert _canonicalise(question, "madrid") == "madrid"


def test_canonicalise_empty_string_passes_through_as_empty() -> None:
    question = _question(answer_type=str)
    assert _canonicalise(question, "") == ""


# ---------------------------------------------------------------------------
# parse_canonical
# ---------------------------------------------------------------------------


def test_parse_canonical_bool_declared_tokens_return_bool() -> None:
    question = _question(answer_type=bool, widget=WizardWidget.CONFIRM)
    for raw_value, expected in (("true", True), ("false", False)):
        assert parse_canonical(question, raw_value) is expected


def test_parse_canonical_bool_non_true_token_returns_false() -> None:
    """Any token other than the exact ``"true"`` literal is treated as
    False; this guards against partial-match drift (e.g., accepting
    ``"True"`` or ``"TRUE"`` would silently corrupt the round-trip)."""
    question = _question(answer_type=bool, widget=WizardWidget.CONFIRM)
    assert parse_canonical(question, "True") is False
    assert parse_canonical(question, "") is False
    assert parse_canonical(question, "yes") is False


def test_parse_canonical_int_returns_int_value() -> None:
    question = _question(answer_type=int, widget=WizardWidget.INTEGER)
    assert parse_canonical(question, "42") == 42
    assert parse_canonical(question, "-7") == -7


def test_parse_canonical_int_empty_string_returns_zero() -> None:
    """Empty canonical token short-circuits to 0 rather than raising
    ValueError — supports the "field never collected" round-trip
    where the persisted dict has no value for this question."""
    question = _question(answer_type=int, widget=WizardWidget.INTEGER)
    assert parse_canonical(question, "") == 0


def test_parse_canonical_path_returns_path_value() -> None:
    question = _question(answer_type=Path, widget=WizardWidget.PATH)
    assert parse_canonical(question, "project/data/example.txt") == Path("project/data/example.txt")


def test_parse_canonical_path_empty_string_returns_empty_path() -> None:
    """Empty canonical token returns ``Path()`` rather than
    ``Path("")`` — ``Path()`` is the canonical no-path sentinel."""
    question = _question(answer_type=Path, widget=WizardWidget.PATH)
    assert parse_canonical(question, "") == Path()


def test_parse_canonical_str_passes_through_unchanged() -> None:
    question = _question(answer_type=str)
    assert parse_canonical(question, "madrid") == "madrid"


def test_parse_canonical_str_empty_string_passes_through_as_empty() -> None:
    question = _question(answer_type=str)
    assert parse_canonical(question, "") == ""


# ---------------------------------------------------------------------------
# _resolve_canonical
# ---------------------------------------------------------------------------


def test_resolve_canonical_returns_values_entry_when_profile_key_matches() -> None:
    question = _question(answer_type=str, profile_key="tax.residence.ccaa", default="madrid")
    values = {"tax.residence.ccaa": "cataluna"}

    assert _resolve_canonical(question, values) == "cataluna"


def test_resolve_canonical_falls_back_to_descriptor_default_when_key_absent() -> None:
    """profile_key set but key absent from values → descriptor default."""
    question = _question(answer_type=str, profile_key="tax.residence.ccaa", default="madrid")
    values = {"unrelated.key": "value"}

    assert _resolve_canonical(question, values) == "madrid"


def test_resolve_canonical_falls_back_to_descriptor_default_when_profile_key_none() -> None:
    """profile_key=None means the question is non-persistent; resolve
    falls straight through to the descriptor default."""
    question = _question(answer_type=str, profile_key=None, default="madrid")
    values = {"any.key": "value"}

    assert _resolve_canonical(question, values) == "madrid"


def test_resolve_canonical_returns_none_when_no_profile_key_and_no_default() -> None:
    """profile_key=None + default=None → returns None (no projection)."""
    question = _question(answer_type=str, profile_key=None, default=None)

    assert _resolve_canonical(question, {}) is None


# ---------------------------------------------------------------------------
# optional-CONFIRM three-state round-trip (LIS Art. 29 new-entity contract)
# ---------------------------------------------------------------------------


def test_parse_canonical_optional_bool_blank_projects_to_undeclared() -> None:
    """An optional CONFIRM (``required=False``, no ``visible_when``) must
    project a blank canonical to the empty string, not to ``False``.

    This is the typed boundary that preserves the three-state
    invariant: a profile whose operator never declared the boolean
    fact must reload with the typed projection at ``None``, never
    collapsed onto declared-``False``. If ``parse_canonical`` ever
    returns ``False`` here, the serialise → persist → reload cycle
    materialises a ``"false"`` token and the downstream LIS Art. 29
    gate misreads every undeclared-quiet-create profile as a positive
    no-override declaration.
    """

    question = WizardQuestion(
        id="example",
        profile_key="taxpayer_type.new_entity_first_two_profit_periods",
        widget=WizardWidget.CONFIRM,
        prompt=tr("wizard.test.example.prompt"),
        required=False,
        answer_type=bool,
    )
    assert parse_canonical(question, "") == ""


def test_parse_canonical_optional_bool_declared_tokens_project_to_bool() -> None:
    """A positively-declared optional CONFIRM still projects to ``True``
    or ``False`` — the blank-aware branch must only fire for blank."""

    question = WizardQuestion(
        id="example",
        profile_key="taxpayer_type.new_entity_first_two_profit_periods",
        widget=WizardWidget.CONFIRM,
        prompt=tr("wizard.test.example.prompt"),
        required=False,
        answer_type=bool,
    )
    for raw_value, expected in (("true", True), ("false", False)):
        assert parse_canonical(question, raw_value) is expected


def test_canonicalise_blank_string_for_optional_bool_stays_blank() -> None:
    """``_canonicalise`` must round-trip the undeclared sentinel as the
    empty canonical so the persistence-layer ``if value`` filter drops
    it and the fact does not land in storage."""

    question = WizardQuestion(
        id="example",
        profile_key="taxpayer_type.new_entity_first_two_profit_periods",
        widget=WizardWidget.CONFIRM,
        prompt=tr("wizard.test.example.prompt"),
        required=False,
        answer_type=bool,
    )
    assert _canonicalise(question, "") == ""


def test_persist_patch_rejects_unknown_question_id() -> None:
    """A supplied patch flag that is not declared by the flow must fail closed."""

    flow = _flow(_question(profile_key="tax.id"))

    with pytest.raises(WorkflowInputMismatchError) as excinfo:
        persist_patch(flow, {"missing-question": "12345678Z"}, state=WorkflowState())

    assert excinfo.value.translated_message == "application.wizard.errors.persist_patch_unknown_question_id"
    assert excinfo.value.context == {"question_id": "missing-question"}
