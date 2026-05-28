"""Verify the i18n renderer observes ``override_settings``.

Pinning the override flow at the call site documents that the
language-resolution pipeline picks up the override exactly the way it
used to pick up ``AEAT_OUTPUT_LANGUAGE`` env writes. No env-var
manipulation here — the test exercises the in-process override only.
"""

from __future__ import annotations

import pytest

from ..config import override_settings
from ._render import output_language

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


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
# S117/S118 — DEFAULT_OUTPUT_LANGUAGE constant routes every "es" fallback
# ---------------------------------------------------------------------------


def test_default_output_language_equals_es() -> None:
    """DEFAULT_OUTPUT_LANGUAGE is the canonical Spanish fallback constant.

    After S117 every ``"es"`` fallback string in _cached_output_language is
    replaced by this constant. Locking its value here ensures accidental
    changes fail loudly and that the module exports it.
    """
    from ._render import DEFAULT_OUTPUT_LANGUAGE

    assert DEFAULT_OUTPUT_LANGUAGE == "es"


def test_default_output_language_exported_in_all() -> None:
    """DEFAULT_OUTPUT_LANGUAGE is part of the module's public surface (__all__)."""
    from . import _render

    assert "DEFAULT_OUTPUT_LANGUAGE" in _render.__all__


def test_fallback_language_is_default_output_language() -> None:
    """When output_language() falls back, it returns DEFAULT_OUTPUT_LANGUAGE.

    An invalid ``aeat_output_language`` that normalises to None must
    still produce a result equal to DEFAULT_OUTPUT_LANGUAGE so the
    constant is the single source of truth for the fallback code.
    """
    from ._render import DEFAULT_OUTPUT_LANGUAGE

    with override_settings(aeat_output_language="zz"):
        result = output_language()
    assert result == DEFAULT_OUTPUT_LANGUAGE
