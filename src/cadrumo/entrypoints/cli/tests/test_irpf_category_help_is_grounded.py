"""`--irpf-category` help names the law it turns on, in every locale.

Choosing an IRPF category is not a labelling preference: it decides which
article of the LIRPF the income is taxed under, and the commonest hard case is
royalties. Intellectual-property income is capital mobiliario under art. 25.4
when the taxpayer is NOT the author, and an economic activity under art. 27
when they are and carry the activity on. The option's help said only that
royalties "may be capital or economic activity depending on the underlying
activity" -- true, and no help at all to the operator deciding which.

It also promised nothing about where to look. The validator's own docstring
claimed the refusal pointed at ``aeat app ledger categories``; neither the
refusal nor the help carried the verb, so an operator was told the shape of a
valid id and never where to read the 42 that exist.

Three tests in ``test_ledger_ux_defect_cluster`` state the intended help end to
end and were failing before this. They run in one locale. These check the other
three, because ``tr`` does not raise on a missing key and a catalogue that
dropped the grounding would render a shorter sentence that still reads fine.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_LOCALES_ROOT = Path(__file__).resolve().parents[3] / "locales"

#: Tokens every locale must carry verbatim. Category ids are transport values
#: and the AEAT terms are the product's own vocabulary, so none of them
#: translates: a localised spelling would name something the parser and the
#: catalogue do not have.
_UNTRANSLATED_TOKENS = (
    "actividad_economica",
    "arrendamiento_local",
    "capital mobiliario",
    "Royalties",
    "aeat app ledger categories",
)

#: The legal grounding, checked case-insensitively because the article is
#: written differently across the four sentences ("art. 25.4 LIRPF",
#: "LIRPF art. 25.4", "LIRPF 25.4. cikke").
_GROUNDING = ("lirpf", "25.4", "27")


def _classify_help(locale: str) -> str:
    """The live `--irpf-category` help for `ledger classify` in one locale."""
    catalogue = yaml.safe_load((_LOCALES_ROOT / locale / "cli.yml").read_text(encoding="utf-8"))
    return str(catalogue["cli"]["ledger"]["classify"]["irpf_category_help"])


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_help_names_the_ids_and_the_catalogue_verb(locale: str) -> None:
    """A translated category id or verb would name something that does not exist."""
    wording = _classify_help(locale)

    missing = [token for token in _UNTRANSLATED_TOKENS if token not in wording]

    assert not missing, f"{locale} drops: {missing}"


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_help_grounds_the_royalty_split_in_the_lirpf(locale: str) -> None:
    """Both articles, because naming one turns a choice into an instruction.

    Art. 25.4 alone would read as "royalties are capital"; art. 27 alone as the
    reverse. The operator is deciding between them, so the sentence has to
    carry both or it has not helped.
    """
    normalised = _classify_help(locale).casefold()

    missing = [token for token in _GROUNDING if token not in normalised]

    assert not missing, f"{locale} does not ground the royalty split: {missing}"


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_help_states_which_side_the_author_falls_on(locale: str) -> None:
    """The distinguishing fact is authorship, and it is what art. 25.4 turns on.

    Accepted in any of the four languages because this half IS prose -- unlike
    the tokens above, it carries no identifier a parser reads.
    """
    normalised = _classify_help(locale).casefold()

    assert any(
        phrase in normalised for phrase in ("not the author", "no es el autor", "no és l'autor", "nem a szerző")
    ), f"{locale} does not say which side the author falls on"


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_two_sibling_help_keys_are_left_alone(locale: str) -> None:
    """The control: `ledger add` and `ledger update` have their own shorter help.

    Three keys share this name under different verbs. A replacement that
    matched by name rather than by content would have rewritten one of these,
    and nothing else in the tree would have noticed.
    """
    catalogue = yaml.safe_load((_LOCALES_ROOT / locale / "cli.yml").read_text(encoding="utf-8"))
    ledger = catalogue["cli"]["ledger"]

    for verb in ("add", "update"):
        wording = str(ledger[verb]["irpf_category_help"])
        assert wording.strip(), f"{locale}: ledger {verb} lost its help"
        assert "aeat app ledger categories" not in wording, f"{locale}: ledger {verb} help was overwritten"
