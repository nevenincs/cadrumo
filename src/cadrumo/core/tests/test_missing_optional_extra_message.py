"""A missing optional extra tells the operator which extra and how to get it.

The refusal used to render the generic internal-error text, which named
neither the extra nor the feature: an operator who reached a gated boundary
was told an internal error had occurred and had nothing to act on. The
registered code now owns its own key, so this gate reads what the error
boundary actually renders rather than the registry row.
"""

from __future__ import annotations

import pytest

from ..errors.error_codes import get_registered_error_code, resolve_error_message
from ..optional_extras import OPTIONAL_EXTRAS, MissingOptionalExtraError, OptionalExtra

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LOCALES = ("en", "es", "ca", "hu")


@pytest.mark.parametrize("extra", OPTIONAL_EXTRAS, ids=lambda item: item.extra)
@pytest.mark.parametrize("locale", _LOCALES)
def test_the_refusal_names_the_extra_its_feature_and_the_install_command(
    extra: OptionalExtra,
    locale: str,
) -> None:
    """Every extra renders its own identity, feature label and install command."""
    rendered = resolve_error_message(MissingOptionalExtraError(extra), locale=locale)

    assert extra.extra in rendered, f"the refusal must name the extra: {rendered}"
    assert extra.feature in rendered, f"the refusal must name the feature: {rendered}"
    assert f"pip install cadrumo[{extra.extra}]" in rendered, (
        f"the refusal must name the install command for the extra: {rendered}"
    )


def test_the_refusal_is_not_the_generic_internal_error_text() -> None:
    """The registered code no longer borrows the catch-all core message key.

    Without this the message key could regress to ``error_cadrumo_core``
    while every assertion above still passed on a fixture, because that key
    renders a sentence that happens to contain none of the tokens checked
    here only by accident. Pin the key itself.
    """
    code = get_registered_error_code(MissingOptionalExtraError(OPTIONAL_EXTRAS[0]))

    assert code.code == "ERROR_OPTIONAL_EXTRA_MISSING"
    assert code.message_key == "errors.error.error_optional_extra_missing"
