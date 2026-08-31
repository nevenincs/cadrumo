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

The two contraste inputs declare ``secret``, which is what makes the
manager and status surfaces mask them. Before that every auth field sat
at ``identity`` and masked only because their descriptions contain the
word "credential" - a property of the prose, not of the schema.

``dni_nie`` is deliberately NOT among them, and the distinction is the
subject of this module. It carries the same identifier as
``identity.tax_id``, which renders in the clear one section above, so
masking it concealed a value already on the same screen. More
importantly it is not authentication material: it NAMES the taxpayer,
where the contraste PROVES possession of their document. ``SECRET`` is
declared for "long-lived authentication material" and ``IDENTITY``
names the NIF explicitly, so classing the DNI/NIE ``secret`` also
dropped ``nif-hash`` - the one redaction rule that hashes a NIF - from
the policy resolved for that field.
"""

from __future__ import annotations

import pytest

from ....core.auth_provider import AuthProviderKind
from ....core.classification import AtRestTreatment, SensitivityClass, default_policy_for
from ..schema import ProfileSchemaDefinition
from ._schema_loader_fixtures import function_scoped_schema  # noqa: F401

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


AUTH_FIELD_KEYS: frozenset[str] = frozenset(
    {"provider", "clave_movil_route", "dni_nie", "numero_soporte", "fecha_validez"},
)
CONTRASTE_FIELD_KEYS: frozenset[str] = frozenset({"numero_soporte", "fecha_validez"})


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


def test_only_the_contraste_inputs_declare_secret(
    schema: ProfileSchemaDefinition,
) -> None:
    """Exactly the two contraste inputs are ``secret`` by declaration.

    DISCRIMINATING in both directions, and the schema half of the masking
    guarantee: the masking authority masks a field the schema classes
    ``secret``, so this set equality is what keeps both contraste forms
    off the manager and status surfaces AND what keeps the DNI/NIE on
    them. They previously masked only because their descriptions contain
    "credential", which made the confidentiality of a credential a
    property of its prose - reword the description and the value renders
    in the clear.

    Two fields are deliberately excluded, for the same underlying reason:
    neither confers any authentication capability. ``provider`` holds
    which mode the taxpayer uses, a closed enum whose values the schema
    publishes anyway. ``dni_nie`` NAMES the taxpayer - it is the same
    identifier ``identity.tax_id`` renders in the clear one section
    above - where the contraste PROVES possession of the physical
    document. An attacker holding a DNI/NIE and nothing else cannot
    authenticate; the contraste and a PIN this profile never stores are
    what stand between them and a session.
    """

    section = schema.section("auth")
    declared = {field.key for field in section.fields if field.sensitivity is SensitivityClass.SECRET}
    assert declared == CONTRASTE_FIELD_KEYS
    assert schema.field("auth.dni_nie").sensitivity is SensitivityClass.IDENTITY


def test_auth_section_carries_the_provider_and_every_clave_credential(
    schema: ProfileSchemaDefinition,
) -> None:
    """The section carries the provider choice, the identity, and both
    forms of contraste. ``dni_nie`` stays a field of its own rather than
    being derived from ``identity.tax_id``: the two carry equal values on
    every profile the shipped paths accept, but collapsing them would
    turn the divergence refusal into a structural impossibility and
    foreclose a legal entity authenticating through a natural person's
    Cl@ve, which nothing in the schema has decided."""

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
