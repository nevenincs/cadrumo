"""Exact lowercase search aliases never become general spelling exemptions."""

import pytest

from ..signal_spelling import spellcheck_catalogues
from ..signal_spelling_enrollment import is_project_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class EmptyDictionary:
    def lookup(self, word: str) -> bool:
        return False


@pytest.fixture(autouse=True)
def dictionaries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "dev.locales.signal_spelling.load_dictionaries",
        lambda _repository: {locale: EmptyDictionary() for locale in ("en", "es", "ca", "hu")},
    )


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
@pytest.mark.parametrize(
    "key,alias,typo",
    [
        ("desktop.ledger.category_keywords.cuotas_autonomos_ss", "tgss", "tgsss"),
        ("desktop.ledger.category_keywords.hardware_amortizable", "pc", "pcx"),
        ("desktop.ledger.category_keywords.suministros_home_office_internet", "adsl", "adsll"),
        ("desktop.ledger.category_keywords.vehiculo_mantenimiento", "itv", "itvv"),
        ("desktop.palette.keywords.copy_link", "cadrumo", "cadrmmo"),
        ("desktop.palette.keywords.copy_link", "url", "urll"),
        ("desktop.palette.keywords.messages", "dehu", "dehhu"),
        ("navigation.view.panel.python.keywords", "repl", "replx"),
        ("navigation.view.reference.keywords", "boe", "boee"),
        ("navigation.view.terminal.keywords", "tui", "tuii"),
    ],
)
def test_attested_name_alias_keeps_near_misses_and_adjacent_prose_checked(
    locale: str, key: str, alias: str, typo: str, tmp_path
) -> None:
    assert not is_project_spelling(locale, alias)
    spelling, inventory, _findings = spellcheck_catalogues(
        {key}, {locale: {key: f"{alias} {typo} misspeling"}}, tmp_path
    )

    assert set(spelling[(locale, key)]) == {typo, "misspeling"}
    assert inventory["spelling_unknown_words"] == 2


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
@pytest.mark.parametrize(
    "key",
    [
        "application.test.key",
        "desktop.ledger.category.cuotas_autonomos_ss",
        "desktop.palette.label",
        "desktop.palette.keyword.copy_link",
        "navigation.view.terminal.label",
        "parallel:docs/example.md:line[1]",
    ],
)
def test_aliases_stay_unknown_in_ordinary_prose_labels_and_similar_paths(locale: str, key: str, tmp_path) -> None:
    value = "tgss pc adsl itv cadrumo url dehu repl boe tui"
    spelling, _inventory, _findings = spellcheck_catalogues({key}, {locale: {key: value}}, tmp_path)

    assert set(spelling[(locale, key)]) == set(value.split())


@pytest.mark.parametrize(
    "key",
    [
        "desktop.ledger.category_keywords.cuotas_autonomos_ss",
        "desktop.palette.keywords.copy_link",
        "navigation.view.terminal.keywords",
    ],
)
def test_alias_rule_does_not_casefold_or_guess_other_abbreviations(key: str, tmp_path) -> None:
    value = "tGsS uRl deHu Repl boee unknownabbr"
    spelling, _inventory, _findings = spellcheck_catalogues({key}, {"es": {key: value}}, tmp_path)

    assert set(spelling[("es", key)]) == set(value.split())
