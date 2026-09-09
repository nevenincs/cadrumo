"""Contract tests for the CLI-facing error registry.

Asserts that representative exceptions render with the grep-stable prefix
expected by operators, and that every
:class:`cadrumo.core.errors.ErrorCategory` (other than the generic
``ERROR``) is exercised by a probe.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ....adapters.outbound.aeat.auth.errors import AeatSessionExpiredError
from ....adapters.outbound.aeat.browser.session import BrowserError
from ....application.review.errors import FilterParseError
from ....core.access_gate.errors import LiveSubmitForbiddenError
from ....core.config import override_settings
from ....core.errors.error_codes import ErrorCategory, render_error_text
from ....core.errors.hierarchy import DecimalFormatError
from ....core.i18n.render import tr
from ....core.observability.errors import RunContextMissingError
from ....domain.portals.errors import PortalIntegrityError

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("error_factory", "category"),
    [
        (DecimalFormatError, ErrorCategory.ERROR),
        (LiveSubmitForbiddenError, ErrorCategory.LOCKED),
        (lambda: FilterParseError("queue=", reason="empty-value"), ErrorCategory.REFUSED),
        (AeatSessionExpiredError, ErrorCategory.AUTH),
        (PortalIntegrityError, ErrorCategory.INTEGRITY),
        (BrowserError, ErrorCategory.FAIL),
        (RunContextMissingError, ErrorCategory.INTERNAL),
    ],
)
@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
def test_rendered_prefixes_are_catalogue_derived(
    error_factory: Callable[[], Exception],
    category: ErrorCategory,
    locale: str,
) -> None:
    """Each registered category renders from its selected locale key."""
    with override_settings(cadrumo_output_language=locale):
        rendered = render_error_text(error_factory())
    first_line = rendered.splitlines()[0]
    prefix = tr(f"errors.prefix.{category.value.lower()}", locale=locale)
    assert prefix != f"errors.prefix.{category.value.lower()}"
    assert first_line.startswith(f"{prefix} ")


def test_every_error_category_has_a_cli_prefix_probe() -> None:
    """Every :class:`~cadrumo.core.errors.ErrorCategory` member except ``ERROR`` is exercised above."""
    probed = {
        ErrorCategory.LOCKED,
        ErrorCategory.REFUSED,
        ErrorCategory.AUTH,
        ErrorCategory.INTEGRITY,
        ErrorCategory.FAIL,
        ErrorCategory.INTERNAL,
    }
    assert probed == set(ErrorCategory) - {ErrorCategory.ERROR}


def _object_member(document: dict[str, object], key: str) -> dict[str, object]:
    value = document[key]
    assert isinstance(value, dict), f"{key!r} is not a JSON object: {value!r}"
    return {str(member_key): member_value for member_key, member_value in value.items()}
