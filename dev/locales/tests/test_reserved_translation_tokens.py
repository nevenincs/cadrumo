"""Reserved translation-token detector controls."""

import pytest

from .test_locale_translation_honesty import _reserved_token_offenders

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_reserved_token_offender_detection_discriminates() -> None:
    assert _reserved_token_offenders({"a.b": "x %{locale} y", "c.d": "x %{subject} y"}) == ["a.b"]
    assert _reserved_token_offenders({"c.d": "x {default} y"}) == ["c.d"]
    assert _reserved_token_offenders({"c.d": "plain prose"}) == []
