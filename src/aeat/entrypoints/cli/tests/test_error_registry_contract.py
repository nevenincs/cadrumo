"""Contract tests for the CLI-facing error registry.

Asserts that every suggestion string in
:data:`aeat.core.errors.ERROR_REGISTRY` parses as a valid CLI command,
that representative exceptions render with the grep-stable prefix
expected by operators, and that every
:class:`aeat.core.errors.ErrorCategory` (other than the generic
``ERROR``) is exercised by a probe.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from click.exceptions import Exit

# ``typer.main.get_command`` materialises the app against typer's *vendored*
# click (``typer._click``), so the resulting group is a ``typer.core.TyperGroup``
# and needs a vendored ``Context`` — it is NOT an instance of top-level
# ``click.Group``. Walk the command tree with the vendored types to match.
from typer._click.core import Context as TyContext
from typer.core import TyperGroup
from typer.main import get_command

from ....adapters.outbound.aeat.auth.certificate import AeatSessionExpiredError
from ....adapters.outbound.aeat.browser.session import BrowserError
from ....application.review._errors import ReviewKindReservedError
from ....core.access_gate import LiveSubmitForbiddenError
from ....core.errors import (
    ERROR_REGISTRY,
    ErrorCategory,
    render_error_text,
)
from ....core.observability._errors import RunContextMissingError
from ....domain.portals._errors import PortalIntegrityError
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_suggestions_parse_as_valid_cli_commands() -> None:
    """Every registered ``default_suggestion`` parses against the live Click context."""
    command = get_command(app)
    # Heavy subcommand groups are registered lazily, so the materialized
    # Click group's ``list_commands`` — not the Typer ``registered_*``
    # lists — is the canonical top-level command inventory.
    assert isinstance(command, TyperGroup)
    top_level = set(command.list_commands(TyContext(command)))

    suggestions = [code.default_suggestion for code in ERROR_REGISTRY.values() if code.default_suggestion is not None]
    assert suggestions

    for suggestion in suggestions:
        tokens = suggestion.split()
        assert tokens[0] == "aeat"
        if len(tokens) > 1 and not tokens[1].startswith("-"):
            assert tokens[1] in top_level
        try:
            command.make_context("aeat", tokens[1:], resilient_parsing=False)
        except Exit as exc:
            assert exc.exit_code == 0


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
    """Every :class:`~aeat.core.errors.ErrorCategory` member except ``ERROR`` is exercised above."""
    probed = {
        ErrorCategory.LOCKED,
        ErrorCategory.REFUSED,
        ErrorCategory.AUTH,
        ErrorCategory.INTEGRITY,
        ErrorCategory.FAIL,
        ErrorCategory.INTERNAL,
    }
    assert probed == set(ErrorCategory) - {ErrorCategory.ERROR}
