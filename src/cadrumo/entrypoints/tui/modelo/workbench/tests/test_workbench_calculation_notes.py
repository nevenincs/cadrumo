"""What the calculation noticed reads in the findings list in words, on the same scale, in every language.

Every reason a calculation diagnostic can carry is placed as a note on the
synthetic form, once naming a box the form prints and once naming none, and
rendered through the findings list in all four languages. No sentence may
carry a reason code, a dotted or snake-case identifier or an unrendered
placeholder, and no language other than English may fall back to the English
sentence. While the calculation is out of date the list says its notes are
from the last calculation; opened afresh, it says to calculate again to see
them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final, get_args

import pytest
from textual.pilot import Pilot
from textual.widgets import OptionList

from ......application.aggregation.source_mesh import CalculationSourceDiagnosticReason
from ......application.modelo.calculation_notes import (
    CALCULATION_NOTE_ATTENTION,
    what_locale_key,
    what_to_do_locale_key,
)
from ......application.modelo.work_form_models import (
    ModeloFormAttention,
    ModeloFormCalculationNote,
    ModeloFormIssue,
    ModeloWorkForm,
)
from ......core.config import override_settings
from ......core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ......core.i18n.render import lookup_translation
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....components.host import ScreenHostApp
from ..issues import IssueLevel, WorkbenchIssuesScreen, issue_lines
from .workbench_fixture import synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REASONS: Final[tuple[str, ...]] = tuple(str(reason) for reason in get_args(CalculationSourceDiagnosticReason))
_TOKENS: Final[Mapping[str, re.Pattern[str]]] = {
    "reason code": re.compile("|".join(re.escape(reason) for reason in _REASONS)),
    "dotted identifier": re.compile(r"\b[a-z][a-z0-9_-]*\.[a-z0-9_-]+"),
    "snake-case identifier": re.compile(r"\b[a-z]+_[a-z0-9_]+\b"),
    "placeholder": re.compile(r"%\{|\{[a-z_]+\}"),
}


async def _settle[ResultT](pilot: Pilot[ResultT], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _notes_form(*, box: str | None, casilla_id: str | None) -> ModeloWorkForm:
    notes = tuple(
        ModeloFormCalculationNote(
            reason=reason, attention=CALCULATION_NOTE_ATTENTION[reason], casilla_id=casilla_id, box=box
        )
        for reason in _REASONS
    )
    return synthetic_form(needs_input=False).model_copy(update={"calculation_notes": notes})


def _rendered(form: ModeloWorkForm, language: str) -> list[tuple[str, str, str]]:
    """Each calculation note's technical line, its location, and its message with what to do."""
    with override_settings(cadrumo_output_language=language):
        return [
            (line.technical, line.where, f"{line.message} {line.action}")
            for line in issue_lines(form)
            if line.from_calculation
        ]


def test_every_reason_has_a_place_on_the_scale() -> None:
    assert set(CALCULATION_NOTE_ATTENTION) == set(_REASONS)


def test_the_token_check_catches_a_raw_reason_and_a_placeholder() -> None:
    """Detector teeth: the checks below fail on what an unworded note would show."""
    leaks = [name for name, pattern in _TOKENS.items() if pattern.search("unresolved_binding: box {box}")]

    assert {"reason code", "snake-case identifier", "placeholder"} <= set(leaks)


@pytest.mark.parametrize("language", [str(language) for language in SUPPORTED_OUTPUT_LANGUAGES])
@pytest.mark.parametrize(("box", "casilla_id"), [("06", "06"), (None, None)])
def test_every_calculation_note_reads_in_words(language: str, box: str | None, casilla_id: str | None) -> None:
    rendered = _rendered(_notes_form(box=box, casilla_id=casilla_id), language)
    failures = [
        f"[{language}] {technical}: {name} {match.group(0)!r}"
        for technical, where, sentences in rendered
        for name, pattern in _TOKENS.items()
        for match in pattern.finditer(f"{where} {sentences}")
    ]

    assert len(rendered) == len(_REASONS)
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize(
    "language", [str(language) for language in SUPPORTED_OUTPUT_LANGUAGES if str(language) != "en"]
)
def test_no_language_falls_back_to_the_english_sentence(language: str) -> None:
    form = _notes_form(box="06", casilla_id="06")
    english = _rendered(form, "en")
    translated = _rendered(form, language)

    # The location may be the box's own label, the same in every language; the sentences may not.
    same = [
        technical
        for (technical, _, english_sentences), (_, _, sentences) in zip(english, translated, strict=True)
        if sentences == english_sentences
    ]

    assert not same


@pytest.mark.parametrize("language", [str(language) for language in SUPPORTED_OUTPUT_LANGUAGES])
def test_every_reason_has_its_own_sentences_in_every_language(language: str) -> None:
    unworded = [
        key
        for reason in _REASONS
        for key in (what_locale_key(reason), what_to_do_locale_key(reason))
        if not lookup_translation(key, locale=language)
    ]

    assert unworded == []


def test_notes_join_the_findings_on_one_scale() -> None:
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.oss_evidence_missing",
        legal_refs=("ley-37-1992:art-99",),
    )
    form = synthetic_form(needs_input=False).model_copy(
        update={
            "issues": (ModeloFormIssue(finding=finding),),
            "calculation_notes": (
                ModeloFormCalculationNote(
                    reason="unrouted_observation", attention=ModeloFormAttention.BLOCKS, durable=True
                ),
                ModeloFormCalculationNote(
                    reason="operator_override_diverges_from_computed",
                    attention=ModeloFormAttention.CONFIRM,
                    casilla_id="06",
                    box="06",
                ),
            ),
        }
    )
    with override_settings(cadrumo_output_language="en"):
        lines = issue_lines(form)

    assert [(line.level, line.from_calculation) for line in lines] == [
        (IssueLevel.BLOCKS, True),
        (IssueLevel.CONFIRM, True),
        (IssueLevel.CHECK, False),
    ]
    assert lines[0].where == "In your records"
    assert lines[0].message == "An amount from your records is not placed in any box of this declaration."
    assert lines[1].message == "The value in box 06 is the one you entered, not the one Cadrumo worked out."
    assert lines[1].key == ("casilla", "06")


async def _list_text(form: ModeloWorkForm) -> str:
    with override_settings(cadrumo_output_language="en"):
        screen = WorkbenchIssuesScreen(form)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            options = screen.query_one("#issues-list", OptionList)
            text = "\n".join(options.render_line(y).text.rstrip() for y in range(options.size.height))
            app.exit(None)
    return re.sub(r"\s+", " ", text)


def _stale(form: ModeloWorkForm) -> ModeloWorkForm:
    drift = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.STALE_CALCULATION,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.ledger_snapshot_drift_changed",
        message_facts={"modelo": "130", "filing_year": 2026, "period": "1T", "changed_count": 1},
        legal_refs=("ley-58-2003:art-120",),
    )
    return form.model_copy(update={"issues": (ModeloFormIssue(finding=drift),)})


@pytest.mark.asyncio
async def test_the_list_says_when_its_notes_are_from_an_out_of_date_calculation() -> None:
    note = ModeloFormCalculationNote(reason="oss_no_live_source", attention=ModeloFormAttention.INFO)
    form = synthetic_form(needs_input=False).model_copy(update={"calculation_notes": (note,)})

    current = await _list_text(form)
    stale = await _list_text(_stale(form))

    assert "From the last calculation. Calculate again to refresh." not in current
    assert "From the last calculation. Calculate again to refresh." in stale


@pytest.mark.asyncio
async def test_a_declaration_opened_afresh_says_to_calculate_again_to_see_the_notes() -> None:
    form = synthetic_form(needs_input=False)
    assert form.calculation_revision_id is not None

    held = await _list_text(form)
    afresh = await _list_text(form.model_copy(update={"calculation_notes_held": False}))

    assert "Calculate again to see the calculation's notes." not in held
    assert "Calculate again to see the calculation's notes." in afresh
