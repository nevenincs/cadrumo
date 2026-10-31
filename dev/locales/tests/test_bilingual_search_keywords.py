"""Search aliases keep dictionary checks without becoming prose exemptions."""

import pytest

from ..signal_spelling import spellcheck_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class Dictionary:
    def __init__(self, known: set[str]) -> None:
        self.known = known

    def lookup(self, word: str) -> bool:
        return word in self.known


@pytest.fixture
def dictionaries(monkeypatch: pytest.MonkeyPatch) -> dict[str, Dictionary]:
    values = {
        "en": Dictionary({"shell", "logs", "google", "drive"}),
        "es": Dictionary({"compilación", "sesión"}),
        "ca": Dictionary(set()),
        "hu": Dictionary(set()),
    }
    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda _repository: values)
    return values


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
@pytest.mark.parametrize(
    "key",
    [
        "desktop.ledger.category_keywords.hardware_amortizable",
        "desktop.palette.keywords.drive_link",
        "navigation.view.panel.console.keywords",
    ],
)
def test_dictionary_backed_aliases_keep_adjacent_typos_and_unknown_inventory(
    locale: str, key: str, dictionaries: dict[str, Dictionary], tmp_path
) -> None:
    value = "shell logs google drive compilacion sesion shlel gooogle compilacionx misspeling"
    spelling, inventory, _findings = spellcheck_catalogues({key}, {locale: {key: value}}, tmp_path)

    assert set(spelling[(locale, key)]) == {"shlel", "gooogle", "compilacionx", "misspeling"}
    assert inventory["spelling_unknown_words"] == 4


@pytest.mark.parametrize("locale", ["es", "ca", "hu"])
@pytest.mark.parametrize(
    "key",
    [
        "application.test.key",
        "desktop.ledger.category.hardware_amortizable",
        "desktop.palette.label",
        "desktop.palette.keyword.console",
        "navigation.view.panel.console.label",
        "parallel:docs/guide.md:line[2]",
        "parallel:src/example.toml:language.es.keywords",
    ],
)
def test_ordinary_prose_labels_and_other_keyword_like_paths_do_not_get_alias_fallback(
    locale: str, key: str, dictionaries: dict[str, Dictionary], tmp_path
) -> None:
    spelling, _inventory, _findings = spellcheck_catalogues({key}, {locale: {key: "shell compilacion shlel"}}, tmp_path)

    assert set(spelling[(locale, key)]) == {"shell", "compilacion", "shlel"}


def test_english_alias_fallback_does_not_casefold_unrecognized_english_spellings(dictionaries, tmp_path) -> None:
    key = "desktop.palette.keywords.drive_link"
    spelling, _inventory, _findings = spellcheck_catalogues(
        {key}, {"ca": {key: "shell sHeLl drive dRiVe shlel"}}, tmp_path
    )

    assert set(spelling[("ca", key)]) == {"sHeLl", "dRiVe", "shlel"}


def test_absent_english_dictionary_cannot_approve_an_english_alias(dictionaries, tmp_path) -> None:
    dictionaries.pop("en")
    key = "desktop.palette.keywords.drive_link"
    spelling, _inventory, _findings = spellcheck_catalogues(
        {key}, {"ca": {key: "shell compilacion misspeling"}}, tmp_path
    )

    assert set(spelling[("ca", key)]) == {"shell", "misspeling"}
