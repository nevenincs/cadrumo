"""The continuity tier of the localization cascade must actually be REACHED.

The cascade resolves a casilla's text through an ordered chain: the exact
revision-occurrence key first, then the stable ``continuidad_id`` key shared
across revisions, then the same chain again in Spanish. The continuity tier had
never fired — not for one casilla, in any revision, in any locale — because
resolution advanced on the absence of a KEY while the locale scaffold emits an
occurrence key for every casilla in every revision. The first key always
existed, so the chain always stopped at index zero.

WHY A MEMBERSHIP TEST CANNOT GUARD THIS, and why these tests are shaped the way
they are. Asserting "the chain contains a continuity key" passes today and
passed throughout the entire period the tier was dead: the key was emitted, it
was simply never consulted. Asserting "a casilla declares a continuidad_id"
passes just as vacuously — one modelo carries 231 such stamps that served no
localisation at all. **The only assertion that distinguishes a working tier from
a dead one is that a resolution DEMONSTRABLY came from it**, so that is what is
asserted here, through the production accessors rather than a reimplementation
of the chain.

WHY THE WITNESS IS DERIVED. Naming a casilla would pin today's catalogue: the
witness must be a casilla whose occurrence key carries no value in some locale
while its continuity key does, and translating that occurrence key — an ordinary
improvement — would retire it. So the witness is searched for at runtime and its
absence is reported as a specific, actionable red rather than a silent pass.

WHAT IS NOT ASSERTED. Not a count of witnesses, nor which casillas they are:
both are properties of the catalogue on this date rather than of the cascade.
Not the Spanish backstop's behaviour beyond one control, because it lives in the
outer loop and was never affected — that it kept working throughout is precisely
why the inner defect went unseen for so long.
"""

from __future__ import annotations

from typing import NamedTuple

import pytest

from .....core.i18n import lookup_translation, lookup_translation_entry
from ..authority import bundled_authority
from ..modelo_localization import resolve_modelo_localization
from ..schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


#: Spanish is the mandatory source, so the outer-loop backstop makes it a poor
#: place to observe the inner chain. The tier is visible only in a locale that
#: can legitimately lack a value.
_TARGET_LOCALES = ("en", "ca", "hu")


class _Witness(NamedTuple):
    """One casilla field whose text can only come from the continuity tier."""

    modelo_id: str
    revision_id: str
    casilla_id: str
    field: str
    locale: str
    keys: tuple[str, ...]
    continuity_value: str


def _chain_for(casilla: CasillaDefinition, field: str) -> tuple[str, ...]:
    """The ordered key chain the production accessors resolve for this field.

    ``help`` is derived from the label chain exactly as
    :meth:`CasillaDefinition.get_help` derives it, rather than restated, so the
    two cannot drift into testing different chains.
    """
    keys = tuple(casilla.localization_keys)
    if field == "label":
        return keys
    return tuple(f"{key.removesuffix('.label')}.help" for key in keys)


def _witnesses() -> list[_Witness]:
    """Every casilla field that reaches its continuity key, derived at runtime.

    A witness needs a chain of at least two keys, no value on the occurrence
    key in the target locale, and a real value on a later key. That is the
    exact shape the tier exists to serve.
    """
    found: list[_Witness] = []
    for modelo in bundled_authority().modelos:
        for revision_id, revision in modelo.revisions.items():
            for casilla in revision.casillas:
                for field in ("label", "help"):
                    keys = _chain_for(casilla, field)
                    if len(keys) < 2:
                        continue
                    for locale in _TARGET_LOCALES:
                        if lookup_translation(keys[0], locale=locale) is not None:
                            continue
                        later = next(
                            (
                                value
                                for key in keys[1:]
                                if (value := lookup_translation(key, locale=locale)) is not None
                            ),
                            None,
                        )
                        if later is None:
                            continue
                        found.append(
                            _Witness(
                                modelo_id=modelo.id,
                                revision_id=revision_id,
                                casilla_id=casilla.id,
                                field=field,
                                locale=locale,
                                keys=keys,
                                continuity_value=later,
                            ),
                        )
    return found


def _contested_chains() -> list[tuple[tuple[str, ...], str, str, str]]:
    """Chains where occurrence and continuity BOTH carry text, and disagree.

    Derived independently of the witnesses above, because the two populations
    are disjoint by construction: a witness needs an EMPTY occurrence key and
    this control needs a populated one. Requiring the two values to differ is
    what makes the control discriminating — identical text would satisfy the
    assertion under either resolution order.
    """
    contested: list[tuple[tuple[str, ...], str, str, str]] = []
    for modelo in bundled_authority().modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                for field in ("label", "help"):
                    keys = _chain_for(casilla, field)
                    if len(keys) < 2:
                        continue
                    for locale in ("es", *_TARGET_LOCALES):
                        occurrence = lookup_translation(keys[0], locale=locale)
                        continuity = next(
                            (
                                value
                                for key in keys[1:]
                                if (value := lookup_translation(key, locale=locale)) is not None
                            ),
                            None,
                        )
                        if occurrence is not None and continuity is not None and occurrence != continuity:
                            contested.append((keys, locale, occurrence, continuity))
    return contested


def _casilla(witness: _Witness) -> CasillaDefinition:
    revision = bundled_authority().modelo(witness.modelo_id).revisions[witness.revision_id]
    return next(casilla for casilla in revision.casillas if casilla.id == witness.casilla_id)


def test_the_catalogue_still_offers_a_continuity_witness() -> None:
    """Anti-vacuity, and the honest failure when the population empties.

    If every occurrence key becomes translated this reds — correctly, because
    the reachability below can then no longer be demonstrated from the shipped
    catalogue. That is a real state change worth an author's attention, not a
    regression to paper over: the next step would be a synthetic proof, never
    deleting this gate.
    """
    assert _witnesses(), (
        "no casilla field in any modelo resolves through its continuity key, so the tests below "
        "cannot demonstrate that the continuity tier is reachable. Either every occurrence key is "
        "now translated (a real improvement — replace this witness with a synthetic proof) or the "
        "cascade has regressed to stopping at the first EXISTING key"
    )


def test_the_continuity_tier_is_reached_through_the_production_accessor() -> None:
    """The assertion this whole module exists for: the tier actually fires.

    Driven through :meth:`CasillaDefinition.get_label` / ``get_help`` rather
    than through the resolver directly, because a resolver that advanced
    correctly while the accessors passed it a truncated chain would satisfy a
    resolver-level test and still leave the tier dead.
    """
    witness = _witnesses()[0]
    casilla = _casilla(witness)

    resolved = casilla.get_label(witness.locale) if witness.field == "label" else casilla.get_help(witness.locale)

    assert resolved == witness.continuity_value, (
        f"{witness.modelo_id}/{witness.revision_id} casilla {witness.casilla_id!r} {witness.field} in "
        f"{witness.locale!r} has no value on its occurrence key, so it must resolve through the "
        f"continuity tier; got {resolved!r}"
    )


def test_the_occurrence_key_still_wins_when_it_carries_a_value() -> None:
    """Positive control: advancing must not start overriding the specific tier.

    The chain is ordered most-specific first for a reason — a revision that
    authors its own wording must keep it. A resolver that advanced past a
    populated key, or that consulted the tiers in the wrong order, would pass
    the reachability test above and silently replace every revision-specific
    label with its shared ancestor.
    """
    contested = _contested_chains()
    assert contested, (
        "no casilla field carries a value on BOTH its occurrence and its continuity key with the two "
        "differing, so nothing here can distinguish occurrence-wins from continuity-wins and this "
        "control is vacuous"
    )
    keys, locale, occurrence_value, continuity_value = contested[0]

    resolved = resolve_modelo_localization(keys, locale=locale)

    assert resolved == occurrence_value, (
        f"the revision-specific value for {keys[0]!r} was replaced by its shared ancestor "
        f"{continuity_value!r}; the chain must stay most-specific-first"
    )


def test_a_valueless_key_does_not_stop_the_chain() -> None:
    """The mechanism itself, stated independently of any particular casilla.

    A key present in the catalogue but carrying no value must not terminate
    resolution. Asserted directly on the resolver with a real valueless key
    taken from the catalogue, so it is the shipped data's own shape rather than
    a constructed one — and it holds even if every casilla witness above is
    later translated away.
    """
    witness = _witnesses()[0]
    valueless_key = witness.keys[0]
    present, value = lookup_translation_entry(valueless_key, locale=witness.locale)
    assert present and value is None, f"{valueless_key!r} is no longer the present-but-valueless shape this test needs"

    resolved = resolve_modelo_localization(witness.keys, locale=witness.locale)

    # Equality, not merely non-None. A chain that stopped here would still
    # return text -- the Spanish backstop in the outer loop supplies it -- so
    # asserting "something came back" passes with the tier dead. What proves
    # the chain advanced is that the text is the one only a later key holds.
    assert resolved == witness.continuity_value, (
        f"resolution stopped at {valueless_key!r}, which exists but carries no value; "
        f"got {resolved!r} instead of the later key's {witness.continuity_value!r}"
    )


def test_the_spanish_backstop_still_serves_an_untranslated_locale() -> None:
    """Control on the outer loop, which this change deliberately did not touch.

    A casilla with Spanish text and no value anywhere in the requested locale's
    chain must still resolve to the Spanish text. This is what kept the defect
    invisible, and it must keep working.
    """
    casilla = next(
        candidate
        for modelo in bundled_authority().modelos
        for revision in modelo.revisions.values()
        for candidate in revision.casillas
        if all(lookup_translation(key, locale="hu") is None for key in _chain_for(candidate, "label"))
        and any(lookup_translation(key, locale="es") is not None for key in _chain_for(candidate, "label"))
    )

    assert casilla.get_label("hu") == casilla.get_label("es")
