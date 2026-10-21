"""Environment isolation must hand back explicitly overridden non-Settings slots."""

from __future__ import annotations

import os

import pytest

from .env_scope import isolated_aeat_env

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CACHE_VARIABLE = "CADRUMO_DEV_CACHE_ROOT"


@pytest.mark.parametrize("prior", [None, "operator-cache"])
@pytest.mark.parametrize("raises", [False, True])
def test_explicit_development_override_restores_ambient_state(
    monkeypatch: pytest.MonkeyPatch, prior: str | None, *, raises: bool
) -> None:
    if prior is None:
        monkeypatch.delenv(_CACHE_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(_CACHE_VARIABLE, prior)

    def exercise() -> None:
        with isolated_aeat_env(**{_CACHE_VARIABLE: "test-cache"}):
            assert os.environ[_CACHE_VARIABLE] == "test-cache"
            if raises:
                raise RuntimeError("scope interrupted")

    if raises:
        with pytest.raises(RuntimeError, match="scope interrupted"):
            exercise()
    else:
        exercise()

    assert os.environ.get(_CACHE_VARIABLE) == prior


def test_nested_development_overrides_restore_each_enclosing_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_CACHE_VARIABLE, "operator-cache")
    with isolated_aeat_env(**{_CACHE_VARIABLE: "outer-cache"}):
        with isolated_aeat_env(**{_CACHE_VARIABLE: "inner-cache"}):
            assert os.environ[_CACHE_VARIABLE] == "inner-cache"
        assert os.environ[_CACHE_VARIABLE] == "outer-cache"
    assert os.environ[_CACHE_VARIABLE] == "operator-cache"
