"""Unit tests for the error-code registry."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from click.exceptions import Exit
from pydantic import ValidationError
from typer.main import get_command

from ..auth.certificate import AeatSessionExpiredError
from ..browser.session import BrowserError
from ..cli import app
from ..observability._errors import RunContextMissingError
from ..portals._errors import PortalIntegrityError
from ..review._errors import ReviewKindReservedError
from . import (
    ERROR_REGISTRY,
    DeprecatedAliasError,
    ErrorCategory,
    ErrorCode,
    MovedAliasError,
    WorkspaceLockedError,
    register,
    render_error_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


def _sample_code(code: str) -> ErrorCode:
    return ErrorCode(
        code=code,
        category=ErrorCategory.ERROR,
        default_message_es="Error de ejemplo.",
        default_message_en="Sample error.",
        default_message_hu="Minta hiba.",
        default_suggestion="aeat modelos list",
        retryable=False,
        runbook_id=None,
    )


def test_error_code_model_is_frozen() -> None:
    code = _sample_code("ERROR_TEST_SAMPLE")
    with pytest.raises((ValidationError, TypeError)):
        code.code = "ERROR_TEST_MUTATED"  # type: ignore[misc]


def test_duplicate_registration_raises_clear_error() -> None:
    existing = next(iter(ERROR_REGISTRY.values()))
    duplicate = ErrorCode(
        code=existing.code,
        category=ErrorCategory.FAIL,
        default_message_es="Error duplicado.",
        default_message_en="Duplicate error.",
        default_message_hu="Duplikalt hiba.",
        default_suggestion=None,
        retryable=False,
        runbook_id=None,
    )
    with pytest.raises(ValueError, match="duplicate ErrorCode registration"):
        register(duplicate)


def test_suggestions_parse_as_valid_cli_commands() -> None:
    command = get_command(app)
    top_level = {registered.name for registered in app.registered_commands if registered.name is not None}
    top_level.update({registered.name for registered in app.registered_groups if registered.name is not None})

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
        (WorkspaceLockedError, "LOCKED"),
        (lambda: ReviewKindReservedError("queue", "tracked by issue #230"), "REFUSED"),
        (AeatSessionExpiredError, "AUTH"),
        (PortalIntegrityError, "INTEGRITY"),
        (BrowserError, "FAIL"),
        (RunContextMissingError, "INTERNAL"),
        (DeprecatedAliasError, "[deprecated]"),
        (MovedAliasError, "[moved]"),
    ],
)
def test_rendered_prefixes_are_grep_stable(
    error_factory: Callable[[], Exception],
    expected_prefix: str,
) -> None:
    rendered = render_error_text(error_factory())
    first_line = rendered.splitlines()[0]
    if expected_prefix.startswith("["):
        assert first_line.startswith(f"{expected_prefix} ")
    else:
        assert first_line.startswith(f"{expected_prefix}: ")
