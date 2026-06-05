"""Unit tests for the error-code registry."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...access_gate import LiveSubmitForbiddenError
from ...i18n import tr
from ...i18n._render import UnmatchedPlaceholderError
from ...logging import SecretScrubbingFilter, configure_logging
from ...observability._errors import RunContextMissingError, RunTracePersistenceError
from .. import (
    ERROR_REGISTRY,
    ErrorCategory,
    ErrorCode,
    get_registered_error_code,
    register,
    render_error_json,
    render_error_text,
)
from .._registry import _DEFERRED_BIND, _flush_deferred_binds
from .._registry import logger as _registry_logger

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _sample_code(code: str) -> ErrorCode:
    return ErrorCode(
        code=code,
        category=ErrorCategory.ERROR,
        message_key="errors.error.sample_error",
        default_suggestion="aeat modelos list",
        retryable=False,
        runbook_id=None,
    )


def test_error_code_model_is_frozen() -> None:
    code = _sample_code("ERROR_TEST_SAMPLE")
    with pytest.raises((ValidationError, TypeError), match=r"frozen|Instance is frozen|attribute"):
        code.code = "ERROR_TEST_MUTATED"


def test_duplicate_registration_raises_clear_error() -> None:
    existing = next(iter(ERROR_REGISTRY.values()))
    duplicate = ErrorCode(
        code=existing.code,
        category=ErrorCategory.FAIL,
        message_key="errors.fail.duplicate_error",
        default_suggestion=None,
        retryable=False,
        runbook_id=None,
    )
    with pytest.raises(ValueError, match="duplicate ErrorCode registration"):
        register(duplicate)


def test_messages_do_not_leak_sphinx_role_markup() -> None:
    """Verify that resolved messages do not contain Sphinx markup roles."""
    for code in ERROR_REGISTRY.values():
        for locale in ("es", "en", "ca", "hu"):
            message = tr(code.message_key, locale=locale)
            assert ":mod:" not in message
            assert ":meth:" not in message
            assert ":func:" not in message
            assert ":class:" not in message
            assert ":data:" not in message


def test_messages_do_not_contain_known_broken_fragments() -> None:
    """Verify that resolved messages do not contain known broken fragments."""
    disallowed_fragments = (
        "Error de no configured proveedor.",
        "No configured szolgaltato hiba.",
        "Error de no soportado financiero origen.",
        "Error de aeat en vivo read no enabled.",
        "Aeat elo read nem enabled hiba.",
        "Error de aeat inicio de sesion assertion.",
        "Aeat bejelentkezes assertion hiba.",
        "Error de artefacto no recognised.",
        "Artefaktum nem recognised hiba.",
        "Error de proveedor no implemented.",
        "Szolgaltato nem implemented hiba.",
        "Error de no extractor registered.",
        "No kinyero registered hiba.",
        "Error de sitio health.",
        "Oldal health hiba.",
        "Error de presentacion draft.",
        "Beadas draft hiba.",
        "Error de l l m",
        "Raised when a ``manifest.",
        "Raised when persisted JSONL or trace.",
        "Raised when a repository operation fails (not-found, integrity, etc.",
        "Error de flujo de trabajo aborted.",
        "Munkafolyamat aborted hiba.",
    )
    for code in ERROR_REGISTRY.values():
        for locale in ("es", "en", "ca", "hu"):
            message = tr(code.message_key, locale=locale)
            for fragment in disallowed_fragments:
                assert fragment not in message


def test_deferred_bind_flushes_on_get_registered_error_code() -> None:
    """bind_error_code defers silently when _DECLARED_CODE_BY_QUALNAME is unavailable.

    Simulates the circular-import window by manually placing a registered
    class into _DEFERRED_BIND, clearing its .code attribute, then verifying
    that get_registered_error_code rebinds it correctly.  This is the path
    that prevents the ValueError crash seen by Inés / Diego when parallel
    agent __pycache__ writes produced a stale pyc for registry/_core.py.
    """

    # UnmatchedPlaceholderError is registered in registry/_core.py.
    # Confirm it is already correctly bound in normal operation.
    code_before = get_registered_error_code(UnmatchedPlaceholderError)
    assert code_before.code == "INTERNAL_I18N_UNMATCHED_PLACEHOLDER"

    # Simulate the deferred state: remove from _CLASS_CODE_REGISTRY and
    # add to _DEFERRED_BIND (as if __init_subclass__ fired mid-init).
    from .._registry import _CLASS_CODE_REGISTRY

    saved_code = _CLASS_CODE_REGISTRY.pop(UnmatchedPlaceholderError, None)
    _DEFERRED_BIND.add(UnmatchedPlaceholderError)

    try:
        # _flush_deferred_binds should rebind the class without raising.
        _flush_deferred_binds()
        assert UnmatchedPlaceholderError not in _DEFERRED_BIND, "class should have been flushed out of _DEFERRED_BIND"
        assert UnmatchedPlaceholderError in _CLASS_CODE_REGISTRY, "class should have been added to _CLASS_CODE_REGISTRY"
        rebound = get_registered_error_code(UnmatchedPlaceholderError)
        assert rebound.code == "INTERNAL_I18N_UNMATCHED_PLACEHOLDER"
    finally:
        # Restore invariant regardless of assertion outcome.
        if saved_code is not None:
            _CLASS_CODE_REGISTRY[UnmatchedPlaceholderError] = saved_code
        _DEFERRED_BIND.discard(UnmatchedPlaceholderError)


def test_bind_error_code_refusal_carries_diagnostic_hints() -> None:
    """The bind-refusal message tells the operator how to act on it.

    Authority: 2026-06-03-cross-domain-continuity-audit Finding 1.
    During the lint-zero session three peer-WIP collisions surfaced
    the bare ``AeatError subclass ... is missing a declared ErrorCode
    registry entry`` ValueError. The original text gave no signal that
    the state could be transient (a peer mid-edit), so an operator
    could chase it as a defect in their own working tree. This test
    pins the two hints the refusal MUST carry: a registry-side fix
    direction for the genuine-new-class case, and a peer-WIP signal
    pointing the operator at ``git status`` for the collision case.
    """

    from .. import AeatError

    # bind_error_code fires from __init_subclass__ during class
    # creation, so the diagnostic ValueError lands on the ``class``
    # statement itself. Wrap the declaration in pytest.raises.
    with pytest.raises(ValueError) as exc_info:

        class _UnregisteredDiagnosticTestError(AeatError):
            """Synthetic subclass with no registry entry; used by this test only."""

        del _UnregisteredDiagnosticTestError  # unreachable when ValueError fires

    message = str(exc_info.value)
    assert "missing a declared ErrorCode registry entry" in message
    assert "git status" in message, "the peer-WIP hint must be present"
    assert "peer agent" in message, "the peer-WIP context must be explicit"


def test_core_error_prefixes_are_grep_stable() -> None:
    """Stable upper-case category identifiers survive in JSON; rendered text uses sentence case."""

    for error_factory, expected_category, expected_text_prefix in (
        (LiveSubmitForbiddenError, "LOCKED", "Locked."),
        (RunContextMissingError, "INTERNAL", "Internal."),
        (lambda: RunTracePersistenceError(operation="test", path=Path("runs")), "FAIL", "Failed."),
    ):
        error = error_factory()
        assert error.code.category.value == expected_category
        rendered_json = render_error_json(error)
        assert f'"category":"{expected_category}"' in rendered_json
        rendered_text = render_error_text(error)
        assert rendered_text.startswith(f"{expected_text_prefix} ")


# ---------------------------------------------------------------------------
# contract — error-registry logger carries SecretScrubbingFilter
# ---------------------------------------------------------------------------


def test_error_registry_logger_is_module_level() -> None:
    """_registry.logger is a module-level Logger, not created inline."""

    assert isinstance(_registry_logger, logging.Logger), (
        f"Expected a logging.Logger instance; got {type(_registry_logger)!r}"
    )
    assert _registry_logger.name == "aeat.core.errors._registry", f"Logger name mismatch: {_registry_logger.name!r}"


def test_error_registry_debug_log_scrubs_sensitive_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """resolve_output_language debug record must not leak i18n exception detail with token shapes.

    The registry logger uses logging.getLogger(__name__) to avoid the
    circular import through aeat.core.logging.configure_logging → config →
    aeat.core.errors.  SecretScrubbingFilter is attached to the root logger
    by configure_logging(); we ensure it is present before capturing.
    """

    configure_logging()
    root = logging.getLogger()
    if not any(isinstance(f, SecretScrubbingFilter) for f in root.filters):
        root.addFilter(SecretScrubbingFilter())  # ensure filter present in test isolation

    sensitive_fragment = "oauth_refresh_token=abc-secret-xyz"
    with caplog.at_level(logging.DEBUG, logger=_registry_logger.name):
        _registry_logger.debug(
            "resolve_output_language: i18n resolution failed; falling back to 'es' (%s)",
            sensitive_fragment,
        )

    assert caplog.records, "No debug records captured — logger propagation may be broken"

    record = caplog.records[-1]
    rendered = record.getMessage()
    assert "abc-secret-xyz" not in rendered, (
        f"Sensitive token fragment survived scrubbing in debug record; got: {rendered!r}"
    )
    assert "<redacted>" in rendered, f"Expected '<redacted>' marker in scrubbed record; got: {rendered!r}"


def test_error_registry_debug_log_scrubs_nif_in_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """NIF-shaped values in the debug log arg position are scrubbed by the root filter."""

    configure_logging()
    root = logging.getLogger()
    if not any(isinstance(f, SecretScrubbingFilter) for f in root.filters):
        root.addFilter(SecretScrubbingFilter())

    nif = "12345678Z"
    with caplog.at_level(logging.DEBUG, logger=_registry_logger.name):
        _registry_logger.debug(
            "resolve_output_language: resolution failed for tax_id=%s",
            nif,
        )

    assert caplog.records, "No debug records captured"

    record = caplog.records[-1]
    rendered = record.getMessage()
    assert nif not in rendered, f"NIF {nif!r} was not scrubbed in debug record; got: {rendered!r}"
    assert "<redacted>" in rendered, f"Expected '<redacted>' in scrubbed debug record; got: {rendered!r}"
