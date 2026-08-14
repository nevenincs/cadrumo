import pytest

from ..setup_answers import SetupAnswers

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_setup_answers_canonical_home_is_core_profile() -> None:
    assert SetupAnswers.__module__ == "cadrumo.core.setup_answers"
