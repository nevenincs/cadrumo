"""Exact command choice notation leaves explanatory prose under spelling review."""

from pathlib import Path

import pytest

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.domain.calculations.registry.censo_modelos import CensoModeloEventKind
from cadrumo.domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from cadrumo.domain.transactions.model_validation import validate_classified_by_shape
from cadrumo.domain.transactions.own_accounts import OwnAccountHolding

from ..signal_spelling import spellcheck_catalogues
from ..signal_tokens import filtered_translation_text, translation_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_complete_locale_choice_list_comes_from_the_command_enum() -> None:
    choices = "(" + ", ".join(language.value for language in OutputLanguage) + ")"
    filtered, excluded = filtered_translation_text(f"Response langage {choices} keeps misspeling.")
    assert translation_words(filtered) == ("Response", "langage", "keeps", "misspeling")
    assert excluded == 1


@pytest.mark.parametrize("notation", ["(es, en, ca, hhu)", "(es, en, ca, hu, fr)", "(es, en, ca)", "en ca hu"])
def test_incomplete_or_misspelled_locale_choices_remain_visible(notation: str) -> None:
    filtered, excluded = filtered_translation_text(notation)
    assert filtered == notation.replace(",", "")
    assert excluded == 0


def test_censo_choice_tokens_are_excluded_but_gloss_typos_remain_visible() -> None:
    choices = (
        f"{CensoModeloEventKind.ALTA.value} (registraton), "
        f"{CensoModeloEventKind.MODIFICACION.value} (chnage), or "
        f"{CensoModeloEventKind.BAJA.value} (deregistraton)"
    )
    filtered, excluded = filtered_translation_text(f"Period: {choices}. Check misspeling.")
    assert translation_words(filtered) == (
        "Period",
        "registraton",
        "chnage",
        "or",
        "deregistraton",
        "Check",
        "misspeling",
    )
    assert excluded == 1


@pytest.mark.parametrize("token", ["altaa", "modificaccion", "bajja"])
def test_misspelled_censo_choice_invalidates_the_structural_list(token: str) -> None:
    original = {"altaa": "alta", "modificaccion": "modificacion", "bajja": "baja"}[token]
    value = "alta (registration), modificacion (change), or baja (deregistration)".replace(original, token)
    filtered, excluded = filtered_translation_text(value)
    assert token in translation_words(filtered)
    assert excluded == 0


def test_standalone_censo_terms_and_non_choice_prose_are_not_excluded() -> None:
    words = "alta modificacion baja and alta (registration) remain prose"
    assert filtered_translation_text(words) == (words, 0)


def test_real_english_cli_help_keeps_glosses_under_spelling_review(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dictionary:
        def lookup(self, word: str) -> bool:
            return word != "chnage"

    value = tr("cli.app.modelo.bindings.period_help", locale="en").replace("(change)", "(chnage)")
    assert "chnage" in value
    monkeypatch.setattr(
        "dev.locales.signal_spelling.load_dictionaries", lambda repository: {"en": Dictionary(), "es": Dictionary()}
    )
    spelling, _inventory, _findings = spellcheck_catalogues({"help"}, {"en": {"help": value}}, Path("."))
    assert spelling == {("en", "help"): ("chnage",)}


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_amendment_and_provenance_help_mark_real_wire_values(locale: str) -> None:
    choices = tr("cli.app.modelo.work.amendment_kind_help", locale=locale)
    wizard_choices = tr("cli.app.modelo.work.amend_wizard_kind_help", locale=locale)
    for kind in CalculationRevisionAmendmentKind:
        assert f"`{kind.value}`" in choices
        assert f"`{kind.value}`" in wizard_choices
    provenance = tr("cli.ledger.classify.apply_help", locale=locale)
    assert "`llm:`" in provenance
    assert validate_classified_by_shape("llm:example") == "llm:example"
    filtered, _excluded = filtered_translation_text(f"{choices} {wizard_choices} {provenance} misspeling")
    assert "misspeling" in translation_words(filtered)
    assert not {kind.value for kind in CalculationRevisionAmendmentKind}.intersection(translation_words(filtered))
    assert "llm" not in translation_words(filtered)


@pytest.mark.parametrize("locale", ["en", "es", "ca"])
def test_account_help_marks_actual_holding_choices(locale: str) -> None:
    value = tr("cli.app.ledger.account.holding_help", locale=locale)
    for holding in OwnAccountHolding:
        assert f"`{holding.value}`" in value
