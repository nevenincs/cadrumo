"""Compatibility contract for the official companion's Hatchling build hook."""

from __future__ import annotations

import importlib.util
from types import ModuleType
from typing import Generic, TypeVar

import pytest

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _hook_module() -> ModuleType:
    path = REPO_ROOT / "packaging" / "cadrumo_data_official" / "hatch_build.py"
    spec = importlib.util.spec_from_file_location("cadrumo_data_official_hatch_build_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hook_module_loads_with_one_parameter_nongeneric_hatchling_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The admitted newer isolated backend exposes a reduced generic contract."""
    import hatchling.builders.config as builder_config_module
    import hatchling.builders.hooks.plugin.interface as hook_interface_module

    class CurrentBuilderConfig:
        """Model Hatchling's concrete current configuration type."""

    CurrentBuilderConfigType = TypeVar("CurrentBuilderConfigType")

    class CurrentBuildHookInterface(Generic[CurrentBuilderConfigType]):
        """Model Hatchling's one-parameter current build-hook interface."""

    monkeypatch.setattr(builder_config_module, "BuilderConfig", CurrentBuilderConfig)
    monkeypatch.setattr(hook_interface_module, "BuildHookInterface", CurrentBuildHookInterface)

    hook = _hook_module()

    assert hook.CustomBuildHook.__orig_bases__ == (CurrentBuildHookInterface[CurrentBuilderConfig],)
