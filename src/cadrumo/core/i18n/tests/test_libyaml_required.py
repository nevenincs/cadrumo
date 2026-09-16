"""The catalogue loader refuses a PyYAML build without libyaml.

The pure-Python scanner is about ten times slower on the shipped catalogues.
A silent fallback would keep every rendered message working while turning
each process start into a multi-second stall, so the loader must refuse at
import instead.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

from .. import _lazy_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_installed_pyyaml_provides_libyaml() -> None:
    """The environment the product runs in carries the C loader."""
    assert yaml.__with_libyaml__, (
        "PyYAML was installed without libyaml; reinstall it from a platform wheel that ships yaml.CSafeLoader"
    )


def test_the_catalogue_loader_refuses_pyyaml_without_libyaml(monkeypatch: pytest.MonkeyPatch) -> None:
    """DETECTOR: a build without libyaml fails loudly at import rather than degrading."""
    monkeypatch.setattr(yaml, "__with_libyaml__", False)
    spec = importlib.util.spec_from_file_location(
        f"{_lazy_catalogue.__package__}._lazy_catalogue_without_libyaml",
        Path(_lazy_catalogue.__file__),
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    with pytest.raises(ImportError, match="without libyaml"):
        spec.loader.exec_module(module)
