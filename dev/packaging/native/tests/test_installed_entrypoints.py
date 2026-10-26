"""Actual installed metadata must resolve every declared console script target."""

from __future__ import annotations

import importlib.metadata
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

EntryPointCheck = Callable[[importlib.metadata.Distribution, set[str]], tuple[importlib.metadata.EntryPoint, ...]]


def _distribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declarations: str, module_code: str
) -> importlib.metadata.Distribution:
    module_name = "_entrypoint_fixture_" + uuid4().hex
    (tmp_path / f"{module_name}.py").write_text(module_code, encoding="utf-8")
    metadata = tmp_path / "cadrumo-0.5.1.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Metadata-Version: 2.1\nName: cadrumo\nVersion: 0.5.1\n", encoding="utf-8")
    (metadata / "entry_points.txt").write_text(
        "[console_scripts]\n" + declarations.replace("MODULE", module_name), encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    return importlib.metadata.Distribution.at(metadata)


def _checker() -> EntryPointCheck:
    module = runpy.run_path(str(REPO_ROOT / "native/tests/entrypoint_smoke.py"))
    return cast(EntryPointCheck, module["declared_entrypoints"])


def test_installed_callable_entrypoint_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    distribution = _distribution(
        tmp_path, monkeypatch, "cadrumo-runtime = MODULE:main\n", "def main():\n    return None\n"
    )
    entries = _checker()(distribution, {"cadrumo-runtime"})
    assert len(entries) == 1 and callable(entries[0].load())


@pytest.mark.parametrize(
    ("declarations", "module_code", "failure"),
    [
        ("", "def main():\n    return None\n", "differ from"),
        (
            "cadrumo-runtime = MODULE:main\nextra = MODULE:main\n",
            "def main():\n    return None\n",
            "differ from",
        ),
        (
            "cadrumo-runtime = MODULE:main\ncadrumo-runtime = MODULE:main\n",
            "def main():\n    return None\n",
            "duplicate",
        ),
        ("cadrumo-runtime = MODULE:main\n", "main = 42\n", "not callable"),
        ("cadrumo-runtime = MODULE:main\n", "other = 42\n", "cannot resolve"),
        ("cadrumo-runtime = MODULE:main\n", "raise SystemExit(0)\n", "cannot resolve"),
    ],
)
def test_installed_entrypoint_metadata_refuses_invalid_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declarations: str, module_code: str, failure: str
) -> None:
    distribution = _distribution(tmp_path, monkeypatch, declarations, module_code)
    with pytest.raises(AssertionError, match=failure):
        _checker()(distribution, {"cadrumo-runtime"})
