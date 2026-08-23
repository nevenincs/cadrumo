"""Verify the i18n renderer observes ``override_settings``.

Pinning the override flow at the call site documents that the
language-resolution pipeline picks up the override exactly the way it
used to pick up ``CADRUMO_OUTPUT_LANGUAGE`` env writes. No env-var
manipulation here — the test exercises the in-process override only.
"""

from __future__ import annotations

import logging

import pytest

from ...config import override_settings
from ...external_constants import SUPPORTED_OUTPUT_LANGUAGES
from .. import DEFAULT_OUTPUT_LANGUAGE, _render
from .._render import output_language

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_output_language_observes_explicit_override() -> None:
    """An ``override_settings(cadrumo_output_language=...)`` value beats
    the default Spanish fallback and is treated as an explicit
    operator choice — matching the previous env-var-based precedence."""

    with override_settings(cadrumo_output_language="ca"):
        assert output_language() == "ca"


def test_output_language_ignores_invalid_override_then_falls_back() -> None:
    """A value outside :data:`SUPPORTED_OUTPUT_LANGUAGES` is treated as
    not-set; the resolver continues to the profile / settings-default
    fallback chain rather than returning the invalid code."""

    with override_settings(cadrumo_output_language="zz"):
        # "zz" is not in SUPPORTED_OUTPUT_LANGUAGES; the explicit
        # branch normalises to None and falls through. The final
        # branch hits the default fallback (Spanish) when no profile
        # is configured.
        assert output_language() == "es"


# ---------------------------------------------------------------------------
# contract/contract — DEFAULT_OUTPUT_LANGUAGE constant routes every "es" fallback
# ---------------------------------------------------------------------------


def test_default_output_language_equals_es() -> None:
    """The public i18n facade exports the canonical Spanish fallback constant.

    After contract every ``"es"`` fallback string in _cached_output_language is
    replaced by this constant. Locking its value here ensures accidental
    changes fail loudly and that the public facade resolves the renderer's
    authority rather than defining a second value.
    """
    assert DEFAULT_OUTPUT_LANGUAGE == "es"
    assert DEFAULT_OUTPUT_LANGUAGE == _render.DEFAULT_OUTPUT_LANGUAGE


def test_default_output_language_exported_in_all() -> None:
    """DEFAULT_OUTPUT_LANGUAGE is part of the i18n facade's public surface."""
    from .. import __all__ as public_exports

    assert "DEFAULT_OUTPUT_LANGUAGE" in public_exports


def test_fallback_language_is_default_output_language() -> None:
    """When output_language() falls back, it returns DEFAULT_OUTPUT_LANGUAGE.

    An invalid ``cadrumo_output_language`` that normalises to None must
    still produce a result equal to DEFAULT_OUTPUT_LANGUAGE so the
    constant is the single source of truth for the fallback code.
    """
    with override_settings(cadrumo_output_language="zz"):
        result = output_language()
    assert result == DEFAULT_OUTPUT_LANGUAGE


def test_stale_product_identity_normalises_without_corrupting_machine_or_authority_names() -> None:
    """The renderer distinguishes product, command, machine, and authority names."""
    from ...product_identity import normalise_product_identity_references

    rendered = normalise_product_identity_references(
        "Cadrumo prepares the draft for AEAT; run cadrumo\n"
        "app modelo work calculate or cadrumo manual fetch. Install cadrumo; "
        "launch cadrumo-helper; read cadrumo://status; set CADRUMO_OUTPUT_LANGUAGE.",
    )

    assert rendered == (
        "Cadrumo prepares the draft for AEAT; run aeat\n"
        "app modelo work calculate or aeat manual fetch. Install cadrumo; "
        "launch cadrumo-helper; read cadrumo://status; set CADRUMO_OUTPUT_LANGUAGE."
    )


def test_live_translation_normalises_a_stale_executable_reference() -> None:
    """``tr`` projects the canonical executable onto what it renders.

    Asserted on an INTERPOLATED value rather than on catalogue prose. The
    shipped catalogues already say ``aeat``, so no live key can exercise the
    normaliser -- a test pinned to one would pass whether or not ``tr`` still
    called it, and would red on any wording edit. Normalisation runs after
    interpolation, so a stale reference supplied as an argument travels the
    real render path and must come back canonical.
    """
    rendered = _render.tr(
        "cli.config.auth.unknown_provider",
        provider="cadrumo app modelo",
        locale="es",
    )

    # ``app modelo`` deliberately, not ``config auth``: this key's own text
    # already says "aeat config auth --help", so asserting THAT is satisfied by
    # the catalogue whether or not the normaliser ran. Only a phrase the
    # argument alone can produce makes the positive direction bite.
    assert "aeat app modelo" in rendered
    assert "cadrumo app modelo" not in rendered


def test_locale_load_failure_is_logged_with_traceback(caplog: pytest.LogCaptureFixture) -> None:
    """A missing locale file falls back, but leaves a debug traceback."""

    with caplog.at_level(logging.DEBUG, logger="cadrumo.core.i18n._render"):
        rendered = _render._lookup_translation("not-supported-locale", "cli.missing.key", default="fallback")

    assert rendered == "fallback"
    records = [
        record
        for record in caplog.records
        if record.name == "cadrumo.core.i18n._render" and "unable to load locale" in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None
    assert "FileNotFoundError" in records[-1].getMessage()


def test_profile_language_resolver_returning_an_unsupported_code_falls_back() -> None:
    """A resolver answering a code this build does not ship resolves to ``None``.

    The registered resolver reports whatever the active profile holds, and the
    supported set is owned here rather than by the profile schema — so the two
    can legitimately disagree, most obviously when a shipped locale is retired
    while a profile written under the older set still names it. Normalising an
    unrecognised code to ``None`` is what lets resolution continue to the
    settings default instead of asking the renderer for a catalogue that is not
    there.
    """
    prior_resolver = _render._profile_language_resolver

    try:
        _render.register_profile_language_resolver(lambda: "zz")
        assert _render._active_profile_output_language() is None

        supported = next(iter(SUPPORTED_OUTPUT_LANGUAGES))
        _render.register_profile_language_resolver(lambda: supported)
        assert _render._active_profile_output_language() == supported
    finally:
        _render._profile_language_resolver = prior_resolver


def test_profile_language_resolver_failure_logs_type_not_secret_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Resolver exceptions fall back without placing raw exception text in the message."""

    prior_resolver = _render._profile_language_resolver

    def raising_resolver() -> str | None:
        raise RuntimeError("oauth_refresh_token=abc-secret-xyz")

    try:
        _render.register_profile_language_resolver(raising_resolver)
        with caplog.at_level(logging.DEBUG, logger="cadrumo.core.i18n._render"):
            resolved = _render._active_profile_output_language()
    finally:
        _render._profile_language_resolver = prior_resolver

    assert resolved is None
    records = [
        record
        for record in caplog.records
        if record.name == "cadrumo.core.i18n._render" and "active-profile output language" in record.getMessage()
    ]
    assert records
    message = records[-1].getMessage()
    assert "RuntimeError" in message
    assert "abc-secret-xyz" not in message
    assert records[-1].exc_info is not None


def test_interpolation_failure_is_logged_without_values(caplog: pytest.LogCaptureFixture) -> None:
    """Format failures preserve fallback output and do not log interpolation values."""

    with caplog.at_level(logging.DEBUG, logger="cadrumo.core.i18n._render"):
        rendered = _render._interpolate(
            "test.format.failure",
            "{amount:.2f}",
            {"amount": "abc-secret-xyz"},
        )

    assert rendered == "{amount:.2f}"
    records = [
        record
        for record in caplog.records
        if record.name == "cadrumo.core.i18n._render" and "unable to interpolate locale key" in record.getMessage()
    ]
    assert records
    message = records[-1].getMessage()
    assert "test.format.failure" in message
    assert "ValueError" in message
    assert "abc-secret-xyz" not in message
    assert records[-1].exc_info is not None
