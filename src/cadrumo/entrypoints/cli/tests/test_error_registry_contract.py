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
from ....core.errors import ErrorCategory, render_error_text
from ....core.observability import RunContextMissingError
from ....domain.portals import PortalIntegrityError

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("error_factory", "expected_prefix"),
    [
        (LiveSubmitForbiddenError, "Locked."),
        (lambda: ReviewKindReservedError("queue", "tracked separately"), "Refused."),
        (AeatSessionExpiredError, "Auth."),
        (PortalIntegrityError, "Integrity."),
        (BrowserError, "Failed."),
        (RunContextMissingError, "Internal."),
    ],
)
def test_rendered_prefixes_are_grep_stable(
    error_factory: Callable[[], Exception],
    expected_prefix: str,
) -> None:
    """Each representative exception renders with the sentence-case prefix
    canonicalised by ``_category_text_prefix``."""
    rendered = render_error_text(error_factory())
    first_line = rendered.splitlines()[0]
    assert first_line.startswith(f"{expected_prefix} ")


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
