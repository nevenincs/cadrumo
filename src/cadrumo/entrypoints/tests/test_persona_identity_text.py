"""The replay's rendering of a persona identity reference for a profile operation."""

from __future__ import annotations

import dataclasses

import pytest

from ...tests.personas import IdentityRef, YearEnvelope, read_persona
from .persona_materialisation import PersonaMaterialisationError, identity_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: A synthetic envelope: identity rendering reads no year.
_ENVELOPE = YearEnvelope(floor=100, horizon=104)


def test_a_full_name_is_a_persons_surnames_then_given_name() -> None:
    persona = read_persona("asalariada-familia", envelope=_ENVELOPE)
    holder = persona.identities.role("asalariada.titular")

    text = identity_text(persona, IdentityRef(role="asalariada.titular", field="full_name"))

    assert text == f"{holder.primer_apellido} {holder.segundo_apellido} {holder.nombre}"


def test_any_other_field_is_the_identity_field_itself() -> None:
    persona = read_persona("asalariada-familia", envelope=_ENVELOPE)
    holder = persona.identities.role("asalariada.titular")

    assert identity_text(persona, IdentityRef(role="asalariada.titular")) == holder.value


def test_a_full_name_of_an_identity_without_a_name_is_refused() -> None:
    persona = read_persona("asalariada-familia", envelope=_ENVELOPE)
    titular = persona.identities.role("asalariada.titular")
    nameless = dataclasses.replace(titular, role="nameless", nombre=None)
    persona = dataclasses.replace(
        persona,
        identities=dataclasses.replace(persona.identities, identities=(*persona.identities.identities, nameless)),
    )

    with pytest.raises(PersonaMaterialisationError, match="no name to compose"):
        identity_text(persona, IdentityRef(role="nameless", field="full_name"))
