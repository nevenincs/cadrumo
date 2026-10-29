"""A missing optional extra is refused plainly, without a remedy command.

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
def test_the_refusal_states_the_missing_component_and_names_no_command(
    extra: OptionalExtra,
    locale: str,
) -> None:
    """Every extra renders a plain refusal that names no install command."""
    rendered = resolve_error_message(MissingOptionalExtraError(extra), locale=locale)

    assert rendered.strip(), "the refusal must render a message"
    assert "pip" not in rendered.lower(), f"the refusal must name no command: {rendered}"
    assert "cadrumo[" not in rendered, f"the refusal must name no command: {rendered}"


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
