"""Agent updates retain only the wheel's declared production surface."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from dev.packaging.native.update_agent import wheel_files

from ..hashing import digest
from ..update_agent import _require_runtime_receipt

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("change", ["none", "source", "staged", "missing", "unenrolled"])
def test_wheel_update_requires_the_same_inventoried_runtime(tmp_path: Path, change: str) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    receipt = runtime / "runtime-receipt.json"
    receipt.write_text('{"lock":"one"}')
    root = tmp_path / "package"
    staged = root / "lib/cadrumo/agent-runtime.json"
    staged.parent.mkdir(parents=True)
    staged.write_bytes(receipt.read_bytes())
    files = {"lib/cadrumo/agent-runtime.json": digest(receipt)}
    if change == "source":
        receipt.write_text('{"lock":"two"}')
    elif change == "staged":
        staged.write_text('{"lock":"modified"}')
    elif change == "missing":
        staged.unlink()
    elif change == "unenrolled":
        files.clear()
    if change == "none":
        _require_runtime_receipt(root, runtime, "lib/cadrumo/site-packages", files)
    else:
        with pytest.raises(ValueError, match="build app-payload"):
            _require_runtime_receipt(root, runtime, "lib/cadrumo/site-packages", files)


def test_wheel_files_omits_every_canonical_test_source(tmp_path: Path) -> None:
    wheel = tmp_path / "cadrumo_agent-0.1.0-py3-none-any.whl"
    with ZipFile(wheel, "w") as archive:
        for name in (
            "cadrumo_agent/__init__.py",
            "cadrumo_agent/cli.py",
            "cadrumo_agent/tests/fixture.py",
            "cadrumo_agent/test_support.py",
            "cadrumo_agent/_test_vectors.py",
            "cadrumo_agent/conftest.py",
            "cadrumo_agent/__pycache__/cached.py",
            "cadrumo_agent-0.1.0.dist-info/METADATA",
        ):
            archive.writestr(name, "fixture = True\n")

    files = wheel_files(wheel, version="0.1.0", prefix="Lib/site-packages")
    names = set(files)

    assert "Lib/site-packages/cadrumo_agent/__init__.py" in names
    assert "Lib/site-packages/cadrumo_agent/cli.py" in names
    assert "Lib/site-packages/cadrumo_agent-0.1.0.dist-info/METADATA" in names
    assert {name for name in names if name.endswith(".py")} == {
        "Lib/site-packages/cadrumo_agent/__init__.py",
        "Lib/site-packages/cadrumo_agent/cli.py",
    }
    assert not any(name.endswith("/cached.py") for name in names)
    assert any(
        name.startswith("Lib/site-packages/cadrumo_agent/__pycache__/cli.") and name.endswith(".pyc") for name in names
    )
