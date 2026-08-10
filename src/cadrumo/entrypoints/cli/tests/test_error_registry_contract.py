"""Contract tests for the CLI-facing error registry.

Asserts that representative exceptions render with the grep-stable prefix
expected by operators, and that every
:class:`cadrumo.core.errors.ErrorCategory` (other than the generic
``ERROR``) is exercised by a probe.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ....adapters.outbound.aeat.auth.certificate import AeatSessionExpiredError
from ....adapters.outbound.aeat.browser.session import BrowserError
from ....application.review import ReviewKindReservedError
from ....core.access_gate import LiveSubmitForbiddenError
from ....core.config import override_settings
from ....core.errors import DecimalFormatError, ErrorCategory, render_error_text
from ....core.i18n import tr
from ....core.observability import RunContextMissingError
from ....domain.portals import PortalIntegrityError

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("error_factory", "category"),
    [
        (DecimalFormatError, ErrorCategory.ERROR),
        (LiveSubmitForbiddenError, ErrorCategory.LOCKED),
        (lambda: ReviewKindReservedError("queue", "tracked separately"), ErrorCategory.REFUSED),
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
