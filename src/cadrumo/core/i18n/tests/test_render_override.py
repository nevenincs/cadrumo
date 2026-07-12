"""Verify the i18n renderer observes ``override_settings``.

Pinning the override flow at the call site documents that the
language-resolution pipeline picks up the override exactly the way it
used to pick up ``AEAT_OUTPUT_LANGUAGE`` env writes. No env-var
manipulation here — the test exercises the in-process override only.
"""

from __future__ import annotations

import logging

import pytest

from ...config import override_settings
from .. import _render
from .._render import output_language

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_output_language_observes_explicit_override() -> None:
    """An ``override_settings(aeat_output_language=...)`` value beats
    the default Spanish fallback and is treated as an explicit
    operator choice — matching the previous env-var-based precedence."""

    with override_settings(aeat_output_language="ca"):
        assert output_language() == "ca"


def test_output_language_ignores_invalid_override_then_falls_back() -> None:
    """A value outside :data:`SUPPORTED_OUTPUT_LANGUAGES` is treated as
    not-set; the resolver continues to the profile / settings-default
    fallback chain rather than returning the invalid code."""

    with override_settings(aeat_output_language="zz"):
        # "zz" is not in SUPPORTED_OUTPUT_LANGUAGES; the explicit
        # branch normalises to None and falls through. The final
        # branch hits the default fallback (Spanish) when no profile
        # is configured.
        assert output_language() == "es"


# ---------------------------------------------------------------------------
# contract/contract — DEFAULT_OUTPUT_LANGUAGE constant routes every "es" fallback
# ---------------------------------------------------------------------------


def test_default_output_language_equals_es() -> None:
    """DEFAULT_OUTPUT_LANGUAGE is the canonical Spanish fallback constant.

    After contract every ``"es"`` fallback string in _cached_output_language is
    replaced by this constant. Locking its value here ensures accidental
    changes fail loudly and that the module exports it.
    """
    from .._render import DEFAULT_OUTPUT_LANGUAGE

    assert DEFAULT_OUTPUT_LANGUAGE == "es"


def test_default_output_language_exported_in_all() -> None:
    """DEFAULT_OUTPUT_LANGUAGE is part of the module's public surface (__all__)."""
    from .. import _render

    assert "DEFAULT_OUTPUT_LANGUAGE" in _render.__all__


def test_fallback_language_is_default_output_language() -> None:
    """When output_language() falls back, it returns DEFAULT_OUTPUT_LANGUAGE.

    An invalid ``aeat_output_language`` that normalises to None must
    still produce a result equal to DEFAULT_OUTPUT_LANGUAGE so the
    constant is the single source of truth for the fallback code.
    """
    from .._render import DEFAULT_OUTPUT_LANGUAGE

    with override_settings(aeat_output_language="zz"):
        result = output_language()
    assert result == DEFAULT_OUTPUT_LANGUAGE


def test_locale_load_failure_is_logged_with_traceback(caplog: pytest.LogCaptureFixture) -> None:
    """A missing locale file falls back, but leaves a debug traceback."""

    with caplog.at_level(logging.DEBUG, logger="aeat.core.i18n._render"):
        rendered = _render._lookup_translation("not-supported-locale", "cli.missing.key", default="fallback")

    assert rendered == "fallback"
    records = [
        record
        for record in caplog.records
        if record.name == "aeat.core.i18n._render" and "unable to load locale" in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None
    assert "FileNotFoundError" in records[-1].getMessage()


def test_profile_language_resolver_failure_logs_type_not_secret_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Resolver exceptions fall back without placing raw exception text in the message."""

    prior_resolver = _render._profile_language_resolver

    def raising_resolver() -> str | None:
        raise RuntimeError("oauth_refresh_token=abc-secret-xyz")

    try:
        _render.register_profile_language_resolver(raising_resolver)
        with caplog.at_level(logging.DEBUG, logger="aeat.core.i18n._render"):
            resolved = _render._active_profile_output_language()
    finally:
        _render._profile_language_resolver = prior_resolver

    assert resolved is None
    records = [
        record
        for record in caplog.records
        if record.name == "aeat.core.i18n._render" and "active-profile output language" in record.getMessage()
    ]
    assert records
    message = records[-1].getMessage()
    assert "RuntimeError" in message
    assert "abc-secret-xyz" not in message
    assert records[-1].exc_info is not None


def test_interpolation_failure_is_logged_without_values(caplog: pytest.LogCaptureFixture) -> None:
    """Format failures preserve fallback output and do not log interpolation values."""

    with caplog.at_level(logging.DEBUG, logger="aeat.core.i18n._render"):
        rendered = _render._interpolate(
            "test.format.failure",
            "{amount:.2f}",
            {"amount": "abc-secret-xyz"},
        )

    assert rendered == "{amount:.2f}"
    records = [
        record
        for record in caplog.records
        if record.name == "aeat.core.i18n._render" and "unable to interpolate locale key" in record.getMessage()
    ]
    assert records
    message = records[-1].getMessage()
    assert "test.format.failure" in message
    assert "ValueError" in message
    assert "abc-secret-xyz" not in message
    assert records[-1].exc_info is not None
