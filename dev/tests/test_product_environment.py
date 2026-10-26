"""The shared child-process scrub removes product and interpreter state, and only that."""

from __future__ import annotations

import os

import pytest

from dev.product_environment import ambient_product_settings_removed, clean_product_env

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_UNRELATED = {"PATH": "/usr/bin", "HOME": "/home/user", "TERM": "xterm"}


def test_ambient_product_settings_removed_drops_current_and_former_prefixes_case_insensitively() -> None:
    environ = {
        **_UNRELATED,
        "CADRUMO_LOCAL_STORAGE_ROOT": "/store",
        "cadrumo_output_language": "es",
        "AEAT_LOCAL_STORAGE_ROOT": "/former",
        "PYTHONPATH": "/checkout/src",
    }

    cleaned = ambient_product_settings_removed(environ)

    assert cleaned == {**_UNRELATED, "PYTHONPATH": "/checkout/src"}


def test_clean_product_env_also_drops_interpreter_selection() -> None:
    environ = {
        **_UNRELATED,
        "CADRUMO_AUTHORITY_ROOT": "/authority",
        "PYTHONPATH": "/checkout/src",
        "PYTHONHOME": "/home-python",
        "PYTHONUSERBASE": "/userbase",
        "VIRTUAL_ENV": "/venv",
        "CONDA_PREFIX": "/conda",
        "CONDA_DEFAULT_ENV": "base",
        "UV_PROJECT_ENVIRONMENT": "/uv",
    }

    assert clean_product_env(environ) == _UNRELATED


def test_scrub_reads_the_process_environment_by_default_and_never_mutates_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CADRUMO_OUTPUT_LANGUAGE", "ca")
    monkeypatch.setenv("VIRTUAL_ENV", "/venv")

    cleaned = clean_product_env()

    assert "CADRUMO_OUTPUT_LANGUAGE" not in cleaned
    assert "VIRTUAL_ENV" not in cleaned
    assert ambient_product_settings_removed().get("VIRTUAL_ENV") == "/venv"
    assert os.environ["CADRUMO_OUTPUT_LANGUAGE"] == "ca"
