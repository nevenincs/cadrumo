"""Shape tests for the AEAT authentication section of the profile schema.

The section exists so an authentication mode's credential inputs live on
the encrypted profile rather than in a dotenv file: a second profile on
the same machine carries its own credentials, and an operator setting up
through the TUI can supply them at all. Two properties therefore have to
hold and are pinned here. Every field sits at ``identity`` sensitivity,
which is what routes it into ciphertext at rest. And no field is
``required``, because the requirement is conditional on the chosen
provider - a certificate needs neither Cl@ve field - so a hard schema
requirement would refuse every certificate profile.
"""

from __future__ import annotations

import pytest

from ....core import AuthProviderKind
from ....core.classification import SensitivityClass
from .. import ProfileSchemaDefinition, load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


AUTH_FIELD_KEYS: frozenset[str] = frozenset({"provider", "dni_nie", "numero_soporte"})


@pytest.fixture
def schema() -> ProfileSchemaDefinition:
    return load_user_profile_schema()


def test_auth_section_persists_at_identity_sensitivity(
    schema: ProfileSchemaDefinition,
) -> None:
    """A numero de soporte is a credential input, so the whole section
    is classified ``identity`` and reaches the encrypted store. A drift
    to ``operational`` would put a credential in a queryable plaintext
    class."""

    section = schema.section("auth")
    assert section.sensitivity is SensitivityClass.IDENTITY
    assert all(field.sensitivity is SensitivityClass.IDENTITY for field in section.fields)


def test_auth_section_carries_the_provider_and_both_clave_credentials(
    schema: ProfileSchemaDefinition,
) -> None:
    """The section carries exactly the provider choice and the two
    Cl@ve credential halves. ``dni_nie`` is separate from
    ``identity.tax_id`` because the person authenticating is not always
    the taxpayer the profile describes."""

    section = schema.section("auth")
    assert {field.key for field in section.fields} == AUTH_FIELD_KEYS
    for field_key in sorted(AUTH_FIELD_KEYS - {"provider"}):
        field = schema.field(f"auth.{field_key}")
        assert field.type.value == "string"


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
