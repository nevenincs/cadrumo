"""The live toolchain configuration agrees on its supported Python minor."""

from __future__ import annotations

import re
import tomllib

import pytest

from ..._paths import REPO_ROOT, UTF_8
from ...ci.python_runtime_matrix import load_runtime_inventory
from .._base_image import linux_base_image

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MINOR = re.compile(r"3\.\d+")


def _minor(value: str) -> str:
    match = _MINOR.search(value)
    assert match is not None, f"cannot read a Python minor from {value!r}"
    return match.group(0)


def test_live_toolchain_declarations_agree_on_the_supported_python_minor() -> None:
    expected = load_runtime_inventory().minimum_minor
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding=UTF_8))
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding=UTF_8))

    declared = {
        ".python-version": _minor((REPO_ROOT / ".python-version").read_text(encoding=UTF_8)),
        "pyproject.toml": _minor(project["project"]["requires-python"]),
        "uv.lock": _minor(lock["requires-python"]),
        "Dockerfile": _minor(linux_base_image()),
    }

    assert set(declared.values()) == {expected}, declared
