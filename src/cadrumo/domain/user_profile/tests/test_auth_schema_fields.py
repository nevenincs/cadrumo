"""Shape tests for the AEAT authentication section of the profile schema.

The section exists so an authentication mode's credential inputs live on
the encrypted profile rather than in a dotenv file: a second profile on
the same machine carries its own credentials, and an operator setting up
through the TUI can supply them at all. Two properties therefore have to
hold and are pinned here. No field sits in a class the policy table
treats as plaintext at rest. And no field is ``required``, because the
requirement is conditional on the chosen provider - a certificate needs
neither Cl@ve field - so a hard schema requirement would refuse every
certificate profile.

The three Cl@ve credential inputs declare ``secret``, which is what
makes the manager and status surfaces mask them. Before that they sat at
``identity`` and masked only because their descriptions contain the word
"credential" - a property of the prose, not of the schema.
"""

from __future__ import annotations

import pytest

from ....core import AuthProviderKind
from ....core.classification import AtRestTreatment, SensitivityClass, default_policy_for
from .. import ProfileSchemaDefinition, load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


AUTH_FIELD_KEYS: frozenset[str] = frozenset({"provider", "dni_nie", "numero_soporte", "fecha_validez"})
CONTRASTE_FIELD_KEYS: frozenset[str] = frozenset({"numero_soporte", "fecha_validez"})
CREDENTIAL_FIELD_KEYS: frozenset[str] = frozenset({"dni_nie", "numero_soporte", "fecha_validez"})


@pytest.fixture
def schema() -> ProfileSchemaDefinition:
    return load_user_profile_schema()


def test_no_auth_field_declares_a_plaintext_at_rest_class(
    schema: ProfileSchemaDefinition,
) -> None:
    """No auth field may declare a class the policy table calls plaintext.

    This pinned ``identity`` on every field until the Cl@ve credential
    inputs were raised to ``secret``, and justified it as "what routes it
    into ciphertext at rest". That justification was wrong, so it is not
    restated here: a profile value's at-rest class comes from the
    ``cadrumo.application.user_profile.value`` secure-object namespace,
    which is ``identity`` whatever the field declares. The field's own
    class is read by the masking authority and by nothing else.

    What the declaration must still not do is describe credential-bearing
    material as plaintext-safe, so the assertion reads the real policy
    table rather than naming one permitted member - which is what let the
    ``secret`` raise look like a violation of a rule it does not break.
    """

    section = schema.section("auth")
    plaintext = sorted(
        field.key
        for field in section.fields
        if default_policy_for(field.sensitivity).at_rest is not AtRestTreatment.CIPHERTEXT_REQUIRED
    )
    assert not plaintext, f"auth fields declare a plaintext-at-rest class: {plaintext}"
    assert default_policy_for(section.sensitivity).at_rest is AtRestTreatment.CIPHERTEXT_REQUIRED


def test_the_clave_credential_inputs_declare_secret(
    schema: ProfileSchemaDefinition,
) -> None:
    """The three Cl@ve credential inputs are ``secret`` by declaration.

    DISCRIMINATING, and the schema half of the masking guarantee: the
    masking authority masks a field the schema classes ``secret``, so
    this declaration is what keeps the DNI/NIE and both contraste forms
    off the manager and status surfaces. They previously masked only
    because their descriptions contain "credential", which made the
    confidentiality of a credential a property of its prose - reword the
    description and the value renders in the clear.

    ``provider`` is deliberately excluded. It holds which authentication
    mode the taxpayer uses, a closed enum whose values the schema
    publishes anyway; knowing it confers no authentication capability, so
    it is not ``secret`` material.
    """

    section = schema.section("auth")
    declared = {field.key for field in section.fields if field.sensitivity is SensitivityClass.SECRET}
    assert declared == CREDENTIAL_FIELD_KEYS


def test_auth_section_carries_the_provider_and_every_clave_credential(
    schema: ProfileSchemaDefinition,
) -> None:
    """The section carries the provider choice, the identity, and both
    forms of contraste. ``dni_nie`` is separate from ``identity.tax_id``
    because a credential input and a taxpayer identifier are different
    things that happen to carry equal values today."""

    section = schema.section("auth")
    assert {field.key for field in section.fields} == AUTH_FIELD_KEYS
    assert schema.field("auth.dni_nie").type.value == "string"


def test_both_contraste_forms_have_a_home_on_the_profile(
    schema: ProfileSchemaDefinition,
) -> None:
    """Cl@ve asks a NIE holder for the numero de soporte and a DNI
    holder for the validity date, reading exactly one of the two. Only
    the NIE half was declared at first, so a DNI holder had no home for
    theirs and had to fall back to the environment. Both are declared
    now, and the date is date-typed so it renders as the ISO token the
    AEAT form is given."""

    assert CONTRASTE_FIELD_KEYS < AUTH_FIELD_KEYS
    assert schema.field("auth.numero_soporte").type.value == "string"
    assert schema.field("auth.fecha_validez").type.value == "date"


def test_auth_provider_enum_covers_every_supported_provider_kind(
    schema: ProfileSchemaDefinition,
) -> None:
    """The declared provider set is the core :class:`AuthProviderKind`
    catalogue, not a hand-listed copy of it. Pinning it against the enum
    means a provider added to the code without a schema value fails
    here rather than silently becoming unselectable on a profile."""

    field = schema.field("auth.provider")
    assert field.type.value == "enum"
    assert set(field.enum_values) == {kind.value for kind in AuthProviderKind}


def test_no_auth_field_is_unconditionally_required(
    schema: ProfileSchemaDefinition,
) -> None:
    """Requirement is conditional on the mode: a Cl@ve provider needs
    both Cl@ve fields, the certificate provider needs neither. The
    conditional refusal lives in the authentication path; the schema
    must not pre-empt it with a blanket requirement that would refuse
    every certificate profile at write time."""

    section = schema.section("auth")
    assert not [field.key for field in section.fields if field.required]


def test_auth_section_is_not_effective_dated(
    schema: ProfileSchemaDefinition,
) -> None:
    """Credentials are current-state, not a dated fiscal fact: the
    profile holds the credential in use, and a superseded one is
    replaced rather than retained under an earlier effective date."""

    section = schema.section("auth")
    assert section.effective_dated is False
    assert not [field.key for field in section.fields if field.effective_dated]
