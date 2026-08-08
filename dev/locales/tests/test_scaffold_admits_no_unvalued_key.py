"""No admission path may put a key into a catalogue without a value.

Four gates in this tree refuse a leaf whose value equals its own dotted key --
the translation-honesty ratchet, the dynamic-prefix coverage sweep, and two
locale-coverage gates -- and until this change the scaffold was the only thing
that produced one. A convention every consumer refuses is not a convention, and
176 such leaves reached HEAD in all four catalogues from a single registry
addition, so the placeholder was not a theoretical debt but shipped text: an
operator reading ``modelo.schema.390.casilla.continuidad.filing-year.label``
where a field label belongs.

The gates above check the catalogue's STATE. This one checks ADMISSION, which is
a different question asked at a different moment: not "does the tree carry an
echo" but "can one enter". A state gate can only be satisfied by draining, and
draining loses to the next bulk scaffold; an admission gate ends the loop.

Two honest outcomes for a key with no value, and the difference is not
cosmetic. A Modelo-schema key carries ``None`` -- the representation
``set_locale_values`` already reserves for exactly these keys, holding
inter-locale parity while the Modelo resolver applies its Spanish-source
fallback. Every other key is omitted, so the parity check reports it missing
until an author supplies real values.

**The trade this makes is deliberate and worth stating.** An unvalued key was
already a red gate before this change; it reddened the honesty ratchet instead
of the parity check. What changes is that the ratchet carries a
``_key_echo_ceiling`` that can be RAISED -- which is how 176 leaves were
committed -- while a missing key has no such knob. So the red moves from a
dismissable gate to one that can only be cleared by authoring the values, and
nothing reaches an operator in the meantime.
"""

from __future__ import annotations

import pytest

from ..manager import _MODELO_SCHEMA_PREFIX, _collect_required_leaves

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXISTING = {"cli": {"known": "a real translation", "namespace": {"child": "another"}}}

_GENERIC_KEY = "cli.app.ledger.a_key_nobody_has_valued"
_MODELO_KEY = f"{_MODELO_SCHEMA_PREFIX}390.casilla.continuidad.filing-year.label"


def _admit(*keys: str) -> dict[str, object]:
    return dict(_collect_required_leaves(set(keys), _EXISTING))


def test_an_existing_translation_is_carried_through_untouched() -> None:
    """The positive control.

    Without it, an admission path that dropped EVERY key would satisfy every
    other case in this module: "no key was echoed" is trivially true of a
    scaffold that writes nothing at all.
    """
    assert _admit("cli.known")["cli.known"] == "a real translation"


def test_no_admitted_value_is_ever_the_key_itself() -> None:
    """The property, stated over both families at once.

    Asserted as "no key maps to its own dotted path" rather than by checking the
    two families separately, so a third family added later is covered by
    construction rather than by whoever remembers this file.
    """
    admitted = _admit(_GENERIC_KEY, _MODELO_KEY, "cli.known")

    echoes = [key for key, value in admitted.items() if value == key]

    assert echoes == [], f"the scaffold admitted a self-referencing placeholder: {echoes}"


def test_an_unvalued_modelo_schema_key_is_admitted_as_an_explicit_absence() -> None:
    """``None``, because these keys have a documented Spanish-source fallback.

    Omitting them instead would break inter-locale key parity, which is the one
    thing the Modelo catalogue's null convention exists to hold.
    """
    admitted = _admit(_MODELO_KEY)

    assert _MODELO_KEY in admitted, "a Modelo-schema key must stay present to hold key parity"
    assert admitted[_MODELO_KEY] is None


def test_an_unvalued_generic_key_is_not_admitted_at_all() -> None:
    """Omitted, because ``None`` renders nothing and no fallback covers it.

    The parity check then reports it missing, which is an honest statement that
    the author still owes four values -- and unlike the echo ceiling, that
    report has no knob to raise.
    """
    assert _GENERIC_KEY not in _admit(_GENERIC_KEY, "cli.known")


def test_a_key_whose_path_bottoms_out_at_a_namespace_is_not_echoed() -> None:
    """The shape the placeholder convention was actually written for.

    A key colliding with an interior node resolves to no leaf, which is the
    branch that produced the echo. It must take the same two honest outcomes as
    a plainly absent key rather than falling back to the old behaviour.
    """
    admitted = _admit("cli.namespace")

    assert admitted.get("cli.namespace") != "cli.namespace"
    assert "cli.namespace" not in admitted
