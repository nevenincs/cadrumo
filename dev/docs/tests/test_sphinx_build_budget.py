"""Strict build gates consume the machine slot already assigned by xdist."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dev.packaging.command_execution import CommandResult

from ..compile_comparison import compare
from ..compile_once import WITNESS_LANGUAGE
from ..i18n import SITE_ROOT_LANGUAGES
from . import built_site
from ._sphinx_build_harness import gate_build_jobs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


@pytest.mark.parametrize("worker", (None, "gw0"))
@pytest.mark.parametrize("requested", (None, "3", "auto"))
def test_sphinx_reader_width_respects_the_outer_slot(
    monkeypatch: pytest.MonkeyPatch, worker: str | None, requested: str | None
) -> None:
    """Standalone settings remain available without multiplying an xdist budget."""
    for name, value in (("PYTEST_XDIST_WORKER", worker), ("CADRUMO_DOCS_JOBS", requested)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    assert gate_build_jobs() == ("1" if worker is not None else requested or "4")


@pytest.mark.parametrize("worker", (None, "gw0"))
@pytest.mark.parametrize("requested", ("0", "-1", "invalid"))
def test_invalid_explicit_width_still_refuses_inside_an_outer_worker(
    monkeypatch: pytest.MonkeyPatch, worker: str | None, requested: str
) -> None:
    """Clamping a nested build must not conceal an invalid operator setting."""
    if worker is not None:
        monkeypatch.setenv("PYTEST_XDIST_WORKER", worker)
    else:
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    monkeypatch.setenv("CADRUMO_DOCS_JOBS", requested)
    with pytest.raises(SystemExit, match="CADRUMO_DOCS_JOBS"):
        gate_build_jobs()


@pytest.mark.parametrize("worker,slots", ((None, 2), ("gw0", 1)))
@pytest.mark.parametrize("refused", (None, "dev.docs.build", "dev.docs.compile_once"))
def test_the_real_build_pair_keeps_both_commands_and_their_refusals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, worker: str | None, slots: int, refused: str | None
) -> None:
    """Exercise the shared build publisher and strict comparison without expensive builds."""
    if worker is not None:
        monkeypatch.setenv("PYTEST_XDIST_WORKER", worker)
    else:
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    monkeypatch.setenv("CADRUMO_DOCS_JOBS", "3")
    allocated: list[int] = []
    commands: list[str] = []

    def executor(*, max_workers: int) -> ThreadPoolExecutor:
        allocated.append(max_workers)
        return ThreadPoolExecutor(max_workers=max_workers)

    def command(argv: list[str], *, cwd: Path, environment: dict[str, str], errors: str) -> CommandResult:
        assert cwd.is_dir() and errors == "replace"
        assert "--strict" in argv
        role = argv[2]
        commands.append(role)
        if role == "dev.docs.build":
            assert environment["CADRUMO_DOCS_JOBS"] == ("1" if worker is not None else "3")
            destination = Path(argv[argv.index("--out-dir") + 1])
        else:
            assert role == "dev.docs.compile_once"
            assert argv[argv.index("--jobs") + 1] == ("1" if worker is not None else "3")
            destination = Path(argv[argv.index("--html-root") + 1]) / WITNESS_LANGUAGE
        destinations = (
            (destination,)
            if role == "dev.docs.build"
            else tuple(destination.parent / language for language in SITE_ROOT_LANGUAGES)
        )
        for root in destinations:
            root.mkdir(parents=True, exist_ok=True)
            (root / "index.html").write_text("<html><body>same witness</body></html>", encoding="utf-8")
        now = datetime.now(UTC)
        return CommandResult(
            argv=tuple(argv),
            cwd=str(cwd),
            started_at=now,
            completed_at=now,
            duration_seconds=0,
            returncode=int(role == refused),
            stdout="build output",
            stderr="build refusal" if role == refused else "",
        )

    monkeypatch.setattr(built_site, "ThreadPoolExecutor", executor)
    monkeypatch.setattr(built_site, "run_command", command)
    built_site._publish(tmp_path, "test-digest")
    built = built_site._read(tmp_path, "test-digest")
    assert built is not None
    for role, outcome in (("dev.docs.build", built.witness_build), ("dev.docs.compile_once", built.compile)):
        assert outcome.returncode == int(role == refused)
        assert (outcome.failure() is not None) == (role == refused)
    comparison = compare(built.html_root / WITNESS_LANGUAGE, built.witness, WITNESS_LANGUAGE)
    assert comparison.pages == 1 and comparison.equal == 1
    assert comparison.differences == 0 and comparison.absent == 0
    assert allocated == [slots]
    assert sorted(commands) == ["dev.docs.build", "dev.docs.compile_once"]
