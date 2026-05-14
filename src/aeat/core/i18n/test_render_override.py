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
