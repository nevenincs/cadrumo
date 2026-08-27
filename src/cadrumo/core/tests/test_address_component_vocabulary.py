"""Every address-scoped producer key names its component from the one vocabulary.

The vocabulary exists because AEAT reuses one address grammar across forms while
NOT reusing one address shape: Modelo 210 wants the municipio's INE code, Modelo
360 wants its name. Merging the shapes would be a false equivalence, so the flat
per-party members stay. What this gate prevents is the other drift -- a later
modelo spelling the same official component ``street_name`` beside
``nombre_via``, so that one AEAT field acquires two registry names and neither is
reachable from the other.
"""

from __future__ import annotations

import pytest

from .. import (
    FilingProducerKey,
)
from .._address_components import (
    FOREIGN_ADDRESS_COMPONENTS,
    FOREIGN_ADDRESS_INFIX,
    SPANISH_ADDRESS_COMPONENTS,
    SPANISH_ADDRESS_INFIXES,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _address_members() -> tuple[tuple[FilingProducerKey, str, frozenset[str]], ...]:
    """Return every address-scoped key with its leaf and the vocabulary it must use."""
    found: list[tuple[FilingProducerKey, str, frozenset[str]]] = []
    for member in FilingProducerKey:
        parts = member.value.split(".")
        leaf = parts[-1]
        if FOREIGN_ADDRESS_INFIX in parts:
            found.append((member, leaf, FOREIGN_ADDRESS_COMPONENTS))
        elif SPANISH_ADDRESS_INFIXES & set(parts):
            found.append((member, leaf, SPANISH_ADDRESS_COMPONENTS))
    return tuple(found)


def test_every_address_scoped_key_names_a_canonical_component() -> None:
    """No address key may invent a component name outside the vocabulary."""
    members = _address_members()
    assert members, "the enum must declare address-scoped producer keys for this gate to bite"

    offending = sorted(
        f"{member.value!r} uses leaf {leaf!r}" for member, leaf, vocabulary in members if leaf not in vocabulary
    )
    assert offending == [], (
        "address-scoped producer key(s) name a component outside the canonical vocabulary in "
        "core._address_components. Add the component there if AEAT really prints it, rather than "
        "spelling an existing one a second way:\n  " + "\n  ".join(offending)
    )


def test_the_two_vocabularies_stay_disjoint_where_it_matters() -> None:
    """The coded and free-text shapes must not blur into each other.

    ``postal_code`` is deliberately the ONE overlap: both shapes carry a postal
    code and neither meaning is at risk. The components that encode the
    difference -- the coded municipio and provincia against the free-text region
    and country code -- must never appear in the other's vocabulary, because that
    is exactly the substitution that would let a region name reach a two-digit
    numeric slot.
    """
    coded_only = {"codigo_ine_municipio", "codigo_provincia", "tipo_via", "nombre_via"}
    free_only = {"region", "country_code", "street", "city"}

    assert coded_only <= SPANISH_ADDRESS_COMPONENTS
    assert free_only <= FOREIGN_ADDRESS_COMPONENTS
    assert not (coded_only & FOREIGN_ADDRESS_COMPONENTS)
    assert not (free_only & SPANISH_ADDRESS_COMPONENTS)


def test_the_municipio_axis_keeps_both_real_variants() -> None:
    """Both the INE code and the name are real, and both must remain nameable.

    Modelo 210 prints "Código INE del Municipio" in five numeric characters;
    Modelo 360 prints "Nombre del municipio" in thirty alphanumeric ones. Keeping
    only one would force the other modelo to either misuse it or invent a name,
    which is the drift this vocabulary exists to stop.
    """
    assert "codigo_ine_municipio" in SPANISH_ADDRESS_COMPONENTS
    assert "nombre_municipio" in SPANISH_ADDRESS_COMPONENTS
    assert "codigo_provincia" in SPANISH_ADDRESS_COMPONENTS
    assert "provincia" in SPANISH_ADDRESS_COMPONENTS
