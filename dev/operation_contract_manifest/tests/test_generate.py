"""The operation contract manifest generator and its drift check against the real registry.

The fresh manifest is composed once from the eager production registry; every
case writes its own copy, so the shipped manifest is never touched here.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

import pytest

from cadrumo.application.operations.contract_manifest import OperationContractManifestV1
from dev.paths import REPO_ROOT

from ..generate import main, manifest_drifts, render_manifest, target_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_FINGERPRINT = re.compile(r'("schema_fingerprint":")([0-9a-f]{64})(")')

_GENERATE = """
import sys
from dev.operation_contract_manifest.generate import render_manifest
sys.stdout.buffer.write(render_manifest().encode("utf-8"))
"""

#: Only what the platform needs to start an interpreter passes through; the
#: child's home, storage and scratch locations are the test's own directory.
_PLATFORM_VARIABLES = frozenset({"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "COMSPEC"})


@pytest.fixture(scope="module")
def fresh() -> str:
    return render_manifest()


def _stale_fingerprint(document: str) -> str:
    """Change one schema fingerprint, as a model edit without regeneration leaves the manifest."""
    match = _FINGERPRINT.search(document)
    assert match is not None, "the manifest carries no schema fingerprint to plant a defect in"
    flipped = "".join("0" if character != "0" else "1" for character in match.group(2))
    return document[: match.start(2)] + flipped + document[match.end(2) :]


def test_generate_writes_a_manifest_that_reproduces_its_own_digest(tmp_path: Path, fresh: str) -> None:
    target = tmp_path / "contract_manifest.json"
    assert main(["--target", str(target)]) == 0
    written = target.read_text(encoding="utf-8")
    assert written == fresh
    manifest = OperationContractManifestV1.model_validate_json(written)
    assert manifest.render() == written


def test_check_accepts_a_fresh_manifest(tmp_path: Path, fresh: str) -> None:
    target = tmp_path / "contract_manifest.json"
    target.write_text(fresh, encoding="utf-8", newline="\n")
    assert main(["--check", "--target", str(target)]) == 0


def test_check_fails_on_a_manifest_with_a_stale_fingerprint(
    tmp_path: Path, fresh: str, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "contract_manifest.json"
    target.write_text(_stale_fingerprint(fresh), encoding="utf-8", newline="\n")
    assert manifest_drifts(target, fresh)
    assert main(["--check", "--target", str(target)]) == 1
    assert "DRIFT" in capsys.readouterr().err


def test_check_fails_when_an_operation_is_missing(tmp_path: Path, fresh: str) -> None:
    lines = fresh.splitlines(keepends=True)
    target = tmp_path / "contract_manifest.json"
    target.write_text("".join(lines[:1] + lines[2:]), encoding="utf-8", newline="\n")
    assert main(["--check", "--target", str(target)]) == 1


def test_check_fails_when_the_manifest_is_absent(tmp_path: Path) -> None:
    assert main(["--check", "--target", str(tmp_path / "absent.json")]) == 1


async def _generate_under(root: Path, seed: str) -> bytes:
    """Compose every production operation and render the manifest in a fresh interpreter.

    ``-I`` is deliberately absent: isolated mode ignores ``PYTHONHASHSEED``, so
    the seed would not be the one given.
    """
    environment = {key: value for key, value in os.environ.items() if key.upper() in _PLATFORM_VARIABLES}
    environment.update(
        {
            "CADRUMO_STORAGE_ROOT": str(root / "storage"),
            "PYDANTIC_DISABLE_PLUGINS": "__all__",
            "PYTHONHASHSEED": seed,
            "PYTHONPATH": os.pathsep.join((str(REPO_ROOT / "src"), str(REPO_ROOT))),
            "HOME": str(root),
            "USERPROFILE": str(root),
            "APPDATA": str(root),
            "LOCALAPPDATA": str(root),
            "TEMP": str(root),
            "TMP": str(root),
        }
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-P",
        "-s",
        "-B",
        "-c",
        _GENERATE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=root,
        env=environment,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=None)
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
    assert process.returncode == 0, stderr.decode()
    return stdout


@pytest.mark.asyncio
async def test_generation_does_not_depend_on_the_hash_seed(tmp_path: Path, fresh: str) -> None:
    first = await _generate_under(tmp_path, "0")
    second = await _generate_under(tmp_path, "1")
    assert first == second
    assert first.decode("utf-8") == fresh


def test_target_is_the_shipped_package_data_path() -> None:
    assert target_path().relative_to(target_path().parents[4]).as_posix() == (
        "src/cadrumo/_data/operations/contract_manifest.json"
    )
