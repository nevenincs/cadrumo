"""A journalled request may not carry a field whose name says it holds a secret.

The credential-free journal keeps secrets out structurally: the storage policy
says what may be persisted, and an ephemeral secret travels a separate channel
that never reaches the journal at all. On top of that sits a NAME tripwire, for
the case those controls cannot see -- a field added to a journalled request
whose name plainly states what it holds.

The tripwire enumerates the bad, which is the weak direction, and it had fallen
behind this codebase's own vocabulary. The certificate path spells its material
``cert``, ``certificate``, ``pem`` and ``private``; the Cl@ve factors are a
``pin`` and a one-time code. Matching is on whole ``_``-separated tokens, so
``certificate_pem``, ``clave_pin`` and ``otp_code`` each split into tokens the
set did not hold and would have journalled their own names unchallenged.

Two things these tests hold that a longer word list alone would not. Whole-token
matching must stay whole-token, because ordinary fields contain these letters --
``spinner_visible`` is a real field on a real view model and contains "pin". And
``clave`` must stay OFF the list: it names the Cl@ve authentication system, but
AEAT also spells an operation key ``clave``, and ``clave``/``clave_operacion``/
``clave_declarado`` are real fields on the detail rows an amendment journals.
Adding it would refuse a lawful M184 or M347 amendment to catch a credential
nothing names that way.
"""

from __future__ import annotations

import pytest

from ....application.modelo.operation_definitions import ModeloWorkAmendRequest
from ..registry_schema_validation import strict_model_json_schema, validate_credential_free_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Credential words this codebase's own auth surfaces use, which the tripwire
#: did not hold. Named individually rather than swept from the source, so each
#: is a stated decision rather than whatever a scan happened to find.
_NEWLY_REFUSED = (
    "certificate_pem",
    "cert_chain",
    "private_material",
    "clave_pin",
    "otp_code",
    "totp_seed",
    "auth_challenge",
    "request_nonce",
    "password_salt",
    "jwt_assertion",
)

#: Ordinary field names that merely CONTAIN a forbidden word. Every one is a
#: real field on a real model in this tree, so a matcher that widened to
#: substrings would take working operations down rather than catch a secret.
_MUST_STILL_PASS = (
    "spinner_visible",
    "clave",
    "clave_operacion",
    "clave_declarado",
    "certificado_digital_label",
    "pinned_revision_id",
)


def _schema(field_name: str) -> dict[str, object]:
    """One published schema carrying exactly the field under test."""
    return {"properties": {field_name: {"type": "string"}}}


@pytest.mark.parametrize("field_name", _NEWLY_REFUSED)
def test_a_field_naming_credential_material_is_refused(field_name: str) -> None:
    """Each word the tripwire had missed, refused through the real validator."""
    with pytest.raises(ValueError, match="forbidden security meaning"):
        validate_credential_free_schema(_schema(field_name))


@pytest.mark.parametrize("field_name", _MUST_STILL_PASS)
def test_an_ordinary_field_that_merely_contains_one_is_admitted(field_name: str) -> None:
    """The control, and the more important half.

    Every refusal above would also be produced by a matcher that simply banned
    these letters anywhere, and such a matcher would refuse ``spinner_visible``
    and every ``clave``-bearing detail row. Separating the two states is what
    says the tripwire reads tokens rather than substrings.
    """
    validate_credential_free_schema(_schema(field_name))


def test_the_words_the_original_set_already_held_are_still_refused() -> None:
    """Extending a list must not reorganise it into dropping what it had."""
    for field_name in ("session_token", "api_key", "password", "wrapped_secret"):
        with pytest.raises(ValueError, match="forbidden security meaning"):
            validate_credential_free_schema(_schema(field_name))


def test_the_real_amend_request_still_publishes_a_credential_free_schema() -> None:
    """The end-to-end control: a registered request that journals ``clave`` fields.

    ``ModeloWorkAmendRequest`` carries detail rows whose wire mirrors declare
    ``clave``, ``clave_operacion`` and ``clave_declarado``, and it is stored
    under the credential-free journal policy. If the tripwire ever refused
    those, amending an M184 or M347 would stop working -- and it would fail at
    registry build, not at the operator, which is why this is worth pinning
    beside the word list rather than left to the registry's own construction.
    """
    validate_credential_free_schema(strict_model_json_schema(ModeloWorkAmendRequest))
