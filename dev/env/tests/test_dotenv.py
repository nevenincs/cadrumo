"""`env/.env` provisioning ports the main worktree's values and never prints one.

Every file here is synthetic. Each value carries a marker, and every case
asserts that no marker reaches the command's output, because the real file
holds the operator's secrets.
"""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

import pytest

from cadrumo.core import config_google
from cadrumo.core.config import Settings
from cadrumo.core.storage_environment import STORAGE_ROOT, ChildEnvironmentProfile, child_environment
from dev.packaging.command_execution import run_command
from dev.packaging.google_oauth import GOOGLE_OAUTH_ENV, GOOGLE_OAUTH_RESOURCE

from .._dotenv import main_worktree, provision

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MARKER = "synthetic-secret"


def _worktree(root: Path, *, template: str, dotenv: str | None = None) -> Path:
    (root / "env").mkdir(parents=True)
    (root / "env" / ".env.example").write_text(template, encoding="utf-8", newline="")
    if dotenv is not None:
        (root / "env" / ".env").write_text(dotenv, encoding="utf-8", newline="")
    return root


def _dotenv(root: Path) -> str:
    return (root / "env" / ".env").read_text(encoding="utf-8", newline="")


def _output(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


_TEMPLATE = "# settings\nURL=https://default.example\nTOKEN=\nTIMEOUT=30\n"


def test_a_new_worktree_receives_every_value_set_in_main(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main = _worktree(
        tmp_path / "main",
        template=_TEMPLATE + "RETIRED=old\n",
        dotenv=(
            "# settings\n"
            "URL=https://default.example\n"
            f"TOKEN={_MARKER}-token\n"
            f"TIMEOUT=90 # {_MARKER}-comment\n"
            "RETIRED=old\n"
            "UNSET=\n"
            f"export EXTRA='{_MARKER}-extra'\n"
        ),
    )
    feature = _worktree(tmp_path / "feature", template=_TEMPLATE)

    assert provision(feature, main) == 0

    assert _dotenv(feature) == (
        "# settings\n"
        "URL=https://default.example\n"
        f"TOKEN={_MARKER}-token\n"
        f"TIMEOUT=90 # {_MARKER}-comment\n"
        f"EXTRA='{_MARKER}-extra'\n"
    )
    output = _output(capsys)
    assert "Ported 3 value(s)" in output
    assert "TOKEN, TIMEOUT, EXTRA" in output
    assert _MARKER not in output


def test_a_value_this_worktree_set_itself_is_never_overwritten(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    main = _worktree(tmp_path / "main", template=_TEMPLATE, dotenv=f"TOKEN={_MARKER}-main\nTIMEOUT=90\n")
    mine = f"URL=https://default.example\nTOKEN={_MARKER}-mine\nTIMEOUT=30\n"
    feature = _worktree(tmp_path / "feature", template=_TEMPLATE, dotenv=mine)

    assert provision(feature, main) == 0

    assert _dotenv(feature) == mine.replace("TIMEOUT=30", "TIMEOUT=90")
    output = _output(capsys)
    assert "Kept 1 value(s) this worktree sets itself: TOKEN" in output
    assert _MARKER not in output


def test_a_second_run_changes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main = _worktree(tmp_path / "main", template=_TEMPLATE, dotenv=f"TOKEN={_MARKER}\nNEW=1\n")
    feature = _worktree(tmp_path / "feature", template=_TEMPLATE)
    assert provision(feature, main) == 0
    first = _dotenv(feature)
    capsys.readouterr()

    assert provision(feature, main) == 0

    assert _dotenv(feature) == first
    assert "No new values to port" in _output(capsys)


def test_a_multi_line_value_is_reported_and_left_alone(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main = _worktree(tmp_path / "main", template=_TEMPLATE, dotenv=f'TOKEN="{_MARKER}\nsecond line"\nTIMEOUT=90\n')
    feature = _worktree(tmp_path / "feature", template=_TEMPLATE)

    assert provision(feature, main) == 0

    assert _dotenv(feature) == _TEMPLATE.replace("TIMEOUT=30", "TIMEOUT=90")
    output = _output(capsys)
    assert "Skipped 1 multi-line value(s); copy by hand: TOKEN" in output
    assert _MARKER not in output


def test_windows_line_endings_survive_porting(tmp_path: Path) -> None:
    template = _TEMPLATE.replace("\n", "\r\n")
    main = _worktree(tmp_path / "main", template=template, dotenv=f"TOKEN={_MARKER}\r\n")
    feature = _worktree(tmp_path / "feature", template=template)

    assert provision(feature, main) == 0

    content = _dotenv(feature)
    assert f"TOKEN={_MARKER}\r\n" in content
    assert "\r\r\n" not in content
    assert content.count("\n") == content.count("\r\n")


def test_an_unreadable_main_dotenv_fails_without_quoting_it(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    main = _worktree(tmp_path / "main", template=_TEMPLATE)
    (main / "env" / ".env").write_bytes(f"TOKEN={_MARKER}\xff\n".encode("latin-1"))
    feature = _worktree(tmp_path / "feature", template=_TEMPLATE)

    assert provision(feature, main) == 1

    assert _dotenv(feature) == _TEMPLATE
    assert _MARKER not in _output(capsys)


def test_without_a_main_worktree_the_template_is_copied(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    feature = _worktree(tmp_path / "feature", template=_TEMPLATE)

    assert provision(feature, None) == 0

    assert _dotenv(feature) == _TEMPLATE
    assert "nothing to port" in _output(capsys)


def _git(repository: Path, *arguments: str) -> None:
    executable = shutil.which("git")
    assert executable is not None, "git must be on PATH to prove worktree discovery"
    identity = ("-c", "user.email=gate@example.invalid", "-c", "user.name=gate")
    completed = run_command(
        [executable, "--no-optional-locks", *identity, *arguments],
        cwd=repository,
        timeout_seconds=120,
    )
    assert completed.returncode == 0, completed.stderr


def test_the_main_worktree_is_found_from_a_sibling_and_not_from_itself(tmp_path: Path) -> None:
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "--initial-branch=main")
    _git(main, "commit", "--allow-empty", "-m", "root")
    feature = tmp_path / "feature"
    _git(main, "worktree", "add", "-b", "feature", str(feature))

    found = main_worktree(feature)

    assert found is not None
    assert found.resolve() == main.resolve()
    assert main_worktree(main) is None


def test_no_main_worktree_is_found_when_main_is_not_checked_out(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--initial-branch=trunk")
    _git(repository, "commit", "--allow-empty", "-m", "root")

    assert main_worktree(repository) is None


def test_setup_materializes_client_for_a_worker_that_scrubs_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    synthetic = os.environ[GOOGLE_OAUTH_ENV]
    root = _worktree(
        tmp_path / "checkout",
        template=GOOGLE_OAUTH_ENV + "=\n",
        dotenv=GOOGLE_OAUTH_ENV + "='" + synthetic + "'\n",
    )
    monkeypatch.delenv(GOOGLE_OAUTH_ENV)
    assert provision(root, None) == 0
    resource = root / GOOGLE_OAUTH_RESOURCE
    assert resource.read_text(encoding="utf-8") == synthetic
    worker = child_environment(
        ChildEnvironmentProfile.OPERATOR,
        tmp_path / "worker-storage",
        received={GOOGLE_OAUTH_ENV: synthetic},
        base={GOOGLE_OAUTH_ENV: synthetic},
    )
    assert GOOGLE_OAUTH_ENV not in worker
    monkeypatch.setenv(STORAGE_ROOT.variable, worker[STORAGE_ROOT.variable])
    monkeypatch.setattr(config_google, "installation_client_source", lambda: resource)
    selected = Settings().cadrumo_google_oauth_client_json
    assert selected is not None
    assert selected.get_secret_value() == synthetic
    assert synthetic not in _output(capsys)


def test_setup_without_google_credentials_succeeds_without_a_resource(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(GOOGLE_OAUTH_ENV)
    root = _worktree(tmp_path / "checkout", template=GOOGLE_OAUTH_ENV + "=\n")
    assert provision(root, None) == 0
    resource = root / GOOGLE_OAUTH_RESOURCE
    assert not resource.exists()
    monkeypatch.setattr(config_google, "installation_client_source", lambda: resource)
    assert Settings().cadrumo_google_oauth_client_json is None


def test_setup_refuses_malformed_google_credentials_without_disclosure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(GOOGLE_OAUTH_ENV)
    root = _worktree(
        tmp_path / "checkout",
        template=GOOGLE_OAUTH_ENV + "=\n",
        dotenv=GOOGLE_OAUTH_ENV + "='{invalid-" + _MARKER + "}'\n",
    )
    assert provision(root, None) == 1
    assert not (root / GOOGLE_OAUTH_RESOURCE).exists()
    assert _MARKER not in _output(capsys)
