"""The installed split-corpus proof reads every wheel member through the public seam."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from .. import lane_verification_core
from ..command_execution import CommandResult, run_command
from ..proof_ledger import recorded_proofs, reset_proof_ledger
from ..smoke_split_install import _INSTALLED_CORPUS_PROBE, _companion_corpus_hashes, _install_cohort_with_pip

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("failed_command", [None, "install", "check"])
def test_split_pip_proofs_require_successful_install_and_dependency_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_command: str | None
) -> None:
    """Keep command failure refusal and transaction proof recording coupled."""
    commands: list[tuple[str, ...]] = []

    def execute(argv: Sequence[str], *, cwd: Path, environment: Mapping[str, str] | None = None) -> CommandResult:
        assert cwd == tmp_path
        assert environment is None
        assert recorded_proofs() == ()
        commands.append(tuple(argv))
        now = datetime.now(UTC)
        return CommandResult(tuple(argv), str(cwd), now, now, 0.0, 19 if argv[3] == failed_command else 0, "", "")

    monkeypatch.setattr(lane_verification_core, "run_command", execute)
    wheel = tmp_path / "cadrumo.whl"
    companions = [tmp_path / f"cadrumo-data-{owner}.whl" for owner in ("manuals", "official", "normatives")]
    venv = tmp_path / "pip-venv"
    reset_proof_ledger()
    try:
        if failed_command is None:
            _install_cohort_with_pip(tmp_path, wheel, companions, venv)
            assert recorded_proofs() == ("exact local cohort install with pip", "pip dependency check")
        else:
            with pytest.raises(SystemExit) as failure:
                _install_cohort_with_pip(tmp_path, wheel, companions, venv)
            assert failure.value.code == 19
            assert recorded_proofs() == ()
        assert commands[0] == (
            str(lane_verification_core.venv_python_path(venv)),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            str(wheel.resolve()),
            *(str(path.resolve()) for path in companions),
        )
        if failed_command == "install":
            assert len(commands) == 1
        else:
            assert commands[1:] == [(commands[0][0], "-m", "pip", "check")]
    finally:
        reset_proof_ledger()


def _namespace_fixture(tmp_path: Path) -> tuple[list[Path], list[Path], dict[str, Path]]:
    """Create three disjoint namespace portions and matching real wheel members."""
    wheels: list[Path] = []
    portions: list[Path] = []
    binaries: dict[str, Path] = {}
    for owner, subtree in (("manuals", "manuals"), ("official", "aeat_official"), ("normatives", "normatives")):
        logical = f"corpus/{subtree}/split-probe-fixture-{tmp_path.name}/source.pdf"
        member = f"cadrumo_data/_data/{logical}"
        payload = f"independent {owner} corpus bytes".encode()
        wheel = tmp_path / f"cadrumo_data_{owner}-1.0.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(member, payload)
        wheels.append(wheel)
        portion = tmp_path / f"portion-{owner}"
        binary = portion / member
        binary.parent.mkdir(parents=True)
        binary.write_bytes(payload)
        portions.append(portion)
        binaries[owner] = binary
    return wheels, portions, binaries


@pytest.mark.parametrize("mutation", [None, "missing_normative", "changed_normative"])
def test_installed_probe_checks_normative_bytes_through_public_resources(tmp_path: Path, mutation: str | None) -> None:
    wheels, portions, binaries = _namespace_fixture(tmp_path)
    expected = _companion_corpus_hashes(wheels)
    assert len(expected) == 3
    assert hashlib.sha256(binaries["normatives"].read_bytes()).hexdigest() in expected.values()
    census = tmp_path / "wheel-corpus-sha256.json"
    census.write_text(json.dumps(expected), encoding="utf-8")
    if mutation == "missing_normative":
        binaries["normatives"].unlink()
    elif mutation == "changed_normative":
        binaries["normatives"].write_bytes(b"substituted installed normative evidence")
    result = run_command(
        [sys.executable, "-c", _INSTALLED_CORPUS_PROBE, str(census)],
        cwd=tmp_path,
        environment={**os.environ, "PYTHONPATH": os.pathsep.join(str(path) for path in (REPO_ROOT / "src", *portions))},
        errors="strict",
    )
    if mutation is None:
        assert result.returncode == 0, result.stderr
        assert "3 verified binary members" in result.stdout
    else:
        assert result.returncode != 0
        assert "corpus/normatives/" in result.stderr
        assert "missing" in result.stderr if mutation == "missing_normative" else "bytes drifted" in result.stderr


def test_wheel_census_refuses_an_absent_normative_companion(tmp_path: Path) -> None:
    wheels, _portions, _binaries = _namespace_fixture(tmp_path)
    with pytest.raises(SystemExit, match="every mandatory companion"):
        _companion_corpus_hashes(wheels[:2])


def test_wheel_census_refuses_overlapping_binary_ownership(tmp_path: Path) -> None:
    wheels, _portions, _binaries = _namespace_fixture(tmp_path)
    with zipfile.ZipFile(wheels[1]) as archive:
        member = archive.infolist()[0]
        content = archive.read(member)
    with zipfile.ZipFile(wheels[2], "a") as archive:
        archive.writestr(member.filename, content)
    with pytest.raises(SystemExit, match="duplicate ownership"):
        _companion_corpus_hashes(wheels)
