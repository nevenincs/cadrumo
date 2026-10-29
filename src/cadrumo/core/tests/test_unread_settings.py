"""A name in a family the settings own that no setting reads is refused, naming the name and never its value.

Every case drives the real :class:`~core.config.Settings` loader against a real
process environment, so the refusal is proved where an operator meets it. The
removed names are the ones an operator's shell profile or ``env/.env`` may
still carry from the settings that once read them.
"""

from __future__ import annotations

import tomllib

import pytest

from ...tests.inventory import REPO_ROOT
from ..config import Settings
from ..errors.error_codes import resolve_error_message
from ..external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ..unread_settings import (
    UnreadSettingError,
    require_no_unread_setting_names,
    unread_setting_names,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Names the model settings once read and nothing reads now.
_RETIRED_NAMES = (
    "CADRUMO_LLM_DEFAULT_MAX_TOKENS",
    "CADRUMO_LLM_DEFAULT_TEMPERATURE",
    "CADRUMO_LLM_LOCAL_INFERENCE_CONCURRENCY",
    "CADRUMO_LLM_MODEL_RUNTIME_MEMORY_FLOOR_BYTES",
    "CADRUMO_LLM_OLLAMA_NUM_CTX",
    "CADRUMO_LLM_OPENAI_API_KEY",
)

#: A value no message may carry; it stands for a secret an unread name was meant to hold.
_VALUE = "synthetic-value-that-must-not-be-printed"


@pytest.mark.parametrize("name", _RETIRED_NAMES)
def test_a_retired_name_in_the_environment_is_refused_and_its_value_is_never_printed(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(name, _VALUE)

    with pytest.raises(UnreadSettingError) as refused:
        Settings()

    error = refused.value
    assert error.names == (name,)
    assert name in str(error)
    assert "Not a setting Cadrumo reads" in str(error)
    assert _VALUE not in str(error)
    assert _VALUE not in repr(error.context)


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_the_refusal_names_the_setting_in_every_language_and_never_its_value(
    locale: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CADRUMO_LLM_OLLAMA_NUM_CTX", _VALUE)
    monkeypatch.setenv("CADRUMO_LLM_PROVIDER", _VALUE)

    with pytest.raises(UnreadSettingError) as refused:
        Settings()

    sentence = resolve_error_message(refused.value, locale=locale)
    assert "CADRUMO_LLM_OLLAMA_NUM_CTX, CADRUMO_LLM_PROVIDER" in sentence
    assert "2" in sentence
    assert _VALUE not in sentence
    assert "{names}" not in sentence
    assert "{count}" not in sentence


def test_a_name_is_refused_whatever_its_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("cadrumo_llm_model", _VALUE)

    with pytest.raises(UnreadSettingError) as refused:
        Settings()

    assert refused.value.names == ("CADRUMO_LLM_MODEL",)


def test_the_settings_of_the_family_still_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """The positive control: the refusal is the unread name, not the family."""
    monkeypatch.setenv("CADRUMO_LLM_VISION_READ_TIMEOUT_S", "123")
    monkeypatch.setenv("cadrumo_llm_default_timeout_s", "45")

    settings = Settings()

    assert settings.cadrumo_llm_vision_read_timeout_s == 123
    assert settings.cadrumo_llm_default_timeout_s == 45


def test_an_empty_value_configures_nothing_and_is_not_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CADRUMO_LLM_OLLAMA_NUM_CTX", "")

    Settings()


def test_a_name_outside_the_owned_families_is_left_to_its_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """The check stops at the families the settings own whole: other prefixes belong to other readers."""
    contract = tomllib.loads((REPO_ROOT / "native" / "application-environment.toml").read_text(encoding="utf-8"))
    monkeypatch.setenv(contract["agent"]["prefix"] + "PORT", "0")

    Settings()


def test_the_unread_names_are_those_in_an_owned_family_that_no_setting_reads() -> None:
    read = {"CADRUMO_LLM_DEFAULT_TIMEOUT_S", "CADRUMO_TOKEN_DIR"}

    assert unread_setting_names(
        ["cadrumo_llm_gone", "CADRUMO_LLM_DEFAULT_TIMEOUT_S", "CADRUMO_UNRELATED", "CADRUMO_LLM_ALSO_GONE"], read
    ) == ("CADRUMO_LLM_ALSO_GONE", "CADRUMO_LLM_GONE")
    assert unread_setting_names(["CADRUMO_LLM_DEFAULT_TIMEOUT_S"], read) == ()
    assert unread_setting_names(["CADRUMO_UNRELATED_NAME"], read, prefixes=("CADRUMO_UNRELATED_",)) == (
        "CADRUMO_UNRELATED_NAME",
    )
    require_no_unread_setting_names(["CADRUMO_LLM_DEFAULT_TIMEOUT_S"], read)
    with pytest.raises(UnreadSettingError):
        require_no_unread_setting_names(["CADRUMO_LLM_GONE"], read)
