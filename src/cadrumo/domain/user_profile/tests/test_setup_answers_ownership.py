"""Ownership contract for the typed setup-answers model."""

import pytest

from ..setup_answers import SetupAnswers

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_setup_answers_canonical_home_is_user_profile_domain() -> None:
    assert SetupAnswers.__module__ == "cadrumo.domain.user_profile.setup_answers"
