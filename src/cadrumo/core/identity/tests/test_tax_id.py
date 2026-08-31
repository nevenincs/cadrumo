"""Tests for :func:`~core.identity.validate_spanish_tax_id`.

The sibling :func:`~core.identity.validate_identity` parser (covered by
``test_documents.py``) returns an :class:`~core.identity.IdentityDocument`
member; ``validate_spanish_tax_id`` returns the canonical identifier string and
is the surface the encrypted master-key NIF canary, invoice counterparty checks,
the PDF sanitiser, and the registry schema scalars consume. A non-resident
heredero (or any foreigner) carries a **NIE** — an ``X``/``Y``/``Z``-led
identifier — so the canonical-string validator's NIE branch must accept the
legitimate forms and reject malformed ones with an instructive message.

The NIE check digit is derived by substituting the leading ``X``/``Y``/``Z``
with ``0``/``1``/``2`` and applying the AEAT control-letter table
``TRWAGMYFPDXBNJZSQVHLCKE`` indexed by ``number % 23`` — the same algorithm as a
NIF. The known-good check letters asserted below are computed from that table,
not copied from a validator run.

See Also:
    :mod:`~core.identity._tax_id`
        Canonical string validator and shared NIF/NIE check-letter helper under
        test.
    :mod:`~core.identity._documents`
        Document-kind parser that shares the same Spanish identifier algorithm.
    :mod:`~domain.calculations.registry._schema_scalars`
        Registry schema consumer that re-raises identity validation failures as
        registry validation errors.
"""

from __future__ import annotations

import pytest

from ...i18n import tr
from .._documents import IdentityError
from .._tax_id import nif_check_letter, validate_spanish_tax_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SUPPORTED_LOCALES = ("en", "es", "ca", "hu")

# Placeholder superset spanning every interpolation token any identity
# translation carries; str.format ignores the unused kwargs, so one dict
# renders every key without a per-key placeholder table.
_PLACEHOLDER_FILL = {
    "candidate": "X1234567L",
    "length": 8,
    "leader": "Q",
    "digits": "12345678",
    "expected": "Z",
    "got": "A",
    "body": "X1234567",
    "kind": "A",
    "alt": "J",
}


@pytest.mark.parametrize(
    ("candidate", "substituted"),
    (
        pytest.param("X1234567L", 1234567, id="x-prefix"),
        pytest.param("Y0000000Z", 10000000, id="y-zero-body"),
        pytest.param("Z0000000M", 20000000, id="z-zero-body"),
        pytest.param("Y5678901P", 15678901, id="y-nonzero-body"),
        pytest.param("Z2345678M", 22345678, id="z-nonzero-body"),
    ),
)
def test_valid_nie_forms_are_accepted(candidate: str, substituted: int) -> None:
    # The asserted check letter is derived from the AEAT table, not the
    # validator: prove the fixture's check letter is the algorithm's answer.
    assert candidate[-1] == nif_check_letter(substituted)
    assert validate_spanish_tax_id(candidate) == candidate


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        pytest.param("x1234567l", "X1234567L", id="lowercase"),
        pytest.param("  X-1234567-L  ", "X1234567L", id="punctuation-and-padding"),
        pytest.param("ESX1234567L", "X1234567L", id="foreign-iva-prefix"),
    ),
)
def test_valid_nie_forms_are_normalised(raw: str, expected: str) -> None:
    assert validate_spanish_tax_id(raw) == expected


# Every failure class the string validator can raise, paired with the
# ``errors.identity.*`` key its semantics demand. The keys are chosen to
# mirror the sibling :mod:`.._documents` parser (the canonical key set for
# these shared failure shapes) plus the string-validator-only triage classes
# (blank / 9-char length / unrecognised leading character); the expected key
# is derived from the failure semantics, never read back from the validator.
_FAILURE_CLASS_KEYS: tuple[tuple[str, str], ...] = (
    ("   ", "errors.identity.document_empty"),
    ("1234567Z", "errors.identity.tax_id_invalid_length"),
    ("123456789Z", "errors.identity.tax_id_invalid_length"),
    ("I12345678", "errors.identity.tax_id_unrecognised_leader"),
    ("123456789", "errors.identity.nif_invalid_shape"),
    ("12345678A", "errors.identity.nif_check_letter_mismatch"),
    ("K123456AL", "errors.identity.nif_invalid_shape"),
    ("K1234567D", "errors.identity.nif_check_letter_mismatch"),
    ("X123A567L", "errors.identity.nie_invalid_shape"),
    ("X1234567Z", "errors.identity.nie_check_letter_mismatch"),
    ("AB123456C", "errors.identity.cif_invalid_shape"),
    ("P1234567A", "errors.identity.cif_check_letter_mismatch_kind"),
    # A is one of the ABEH digit-control kinds, so the failure is a wrong
    # check DIGIT, not a wrong character of unsettled class. This surface
    # used to report the mixed-kind key here because it carried its own,
    # laxer copy of the leader policy.
    ("A12345670", "errors.identity.cif_check_digit_mismatch"),
    ("C1234567X", "errors.identity.cif_check_char_mismatch_mixed"),
    ("A1234567%", "errors.identity.cif_control_char_invalid"),
)


@pytest.mark.parametrize(("candidate", "expected_key"), _FAILURE_CLASS_KEYS)
def test_invalid_inputs_carry_the_expected_translated_message_key(
    candidate: str,
    expected_key: str,
) -> None:
    """Every rejection carries a localisation key, not a raw English literal.

    Asserting the ``translated_message`` key (never the rendered prose)
    proves the operator-facing message is resolved through the locale
    catalogue on the wizard/pydantic boundary rather than leaking the
    English literal the validator once raised.
    """
    with pytest.raises(IdentityError) as excinfo:
        validate_spanish_tax_id(candidate)
    assert excinfo.value.translated_message == expected_key, candidate


def test_every_failure_class_key_resolves_in_every_locale() -> None:
    """Each raised key must resolve to real prose in all four catalogues.

    Resolution returning something other than the key itself proves the
    leaf is a translated value, not a scaffold echo, in en/es/ca/hu.
    """
    expected_keys = {key for _, key in _FAILURE_CLASS_KEYS}
    for key in sorted(expected_keys):
        for locale in _SUPPORTED_LOCALES:
            rendered = tr(key, locale=locale, **_PLACEHOLDER_FILL)
            assert rendered != key, (key, locale)
            assert key not in rendered, (key, locale)
