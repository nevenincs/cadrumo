"""Tests for shared pytest environment isolation helpers."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from .env import temporary_env

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _unique_env_name() -> str:
    return f"AEAT_TEST_TEMPORARY_ENV_{uuid4().hex.upper()}"


def test_temporary_env_restores_missing_variable() -> None:
    name = _unique_env_name()

    assert name not in os.environ
    with temporary_env(**{name: "inside"}):
        assert os.environ[name] == "inside"

    assert name not in os.environ


def test_temporary_env_restores_existing_variable_after_error() -> None:
    name = _unique_env_name()
    os.environ[name] = "before"

    try:
        with pytest.raises(RuntimeError, match="forced exit"), temporary_env(**{name: "inside"}):
            assert os.environ[name] == "inside"
            raise RuntimeError("forced exit")

        assert os.environ[name] == "before"
    finally:
        os.environ.pop(name, None)
