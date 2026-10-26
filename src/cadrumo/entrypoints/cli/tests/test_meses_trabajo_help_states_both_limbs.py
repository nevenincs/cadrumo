"""Every operator-facing description of MESES_TRABAJO must state both Art. 81.1 limbs.

Art. 81.1 grants the deducción por maternidad to a child under three AND,
independently of age, to an adopción/acogimiento inside its own entry-date
window (:meth:`~domain.contribuyente.DescendantInfo.art_81_1_entry_window_meses`).
Before this module, every operator-facing description of the
``MESES_TRABAJO`` question -- the guided wizard's prompt and help -- scoped
the question to "the child under three" alone. An operator answering exactly
as asked entered ``0`` for a five-year-old adoptee and received nothing: the
entry-date window was reachable only by an operator who contradicted the
prompt.

A third surface this module originally covered, the calculate-time
``--meses-trabajo-con-hijo-menor-3`` flag's own help text, was RETIRED
outright rather than re-scoped: the flag was a second, unvalidated
authority over casilla 0611 with a free-form hijo id no descendant record
answered to, and the active profile's descendiente records are now the sole
source. Its help key and coverage here went with it.

These are pure locale-catalogue checks: no registry snapshot, no CLI
invocation, no calculate path. Grounded on STRUCTURE (does the copy mention
the entry-date route at all), never on the exact rendered sentence, so a
future rewording does not need to keep pace with a hardcoded string.
"""

from __future__ import annotations

import pytest

from ....core.i18n.render import tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")

_KEYS = (
    "wizard.setup.descendientes.meses-madre-trabajo.prompt",
    "wizard.setup.descendientes.meses-madre-trabajo.help",
)

#: A marker proving the copy names the entry-date route, one recognisable
#: substring per locale. Deliberately loose (a word fragment, not a full
#: sentence) so translators keep latitude in phrasing.
_ENTRY_DATE_MARKER = {
    "en": "entry-date",
    "es": "fecha de entrada",
    "ca": "data d'entrada",
    "hu": "belép",
}

_SURFACES = [(locale, key) for key in _KEYS for locale in _LOCALES]


@pytest.mark.parametrize(("locale", "key"), _SURFACES)
def test_the_copy_names_the_entry_date_route(locale: str, key: str) -> None:
    """No locale's copy may scope the question to age alone."""
    text = tr(key, locale=locale)
    marker = _ENTRY_DATE_MARKER[locale]
    assert marker.lower() in text.lower(), (
        f"{locale}/{key}: copy does not mention the adopción/acogimiento entry-date route "
        f"(expected {marker!r} somewhere in the text); an operator answering only about age "
        f"cannot discover the second limb. Got: {text!r}"
    )


@pytest.mark.parametrize(("locale", "key"), _SURFACES)
def test_the_copy_is_non_empty_and_locale_specific(locale: str, key: str) -> None:
    """Every surface must actually resolve, so a missing catalogue leaf cannot masquerade as a pass."""
    text = tr(key, locale=locale)
    assert text.strip(), f"{locale}/{key}: resolved to empty text"
