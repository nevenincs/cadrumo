"""The disposable root's own decisions: where it may live, what removal touches, the seed and the password's path."""

from __future__ import annotations

import csv
import secrets
import sys
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.inbound.financial.providers.csv import CsvProvider

from ...runtime_lifecycle.caller_owned_root import AcceptanceError
from ..disposable_root import (
    LEDGER_SEED,
    MINIMUM_SEEDED_ROWS,
    ROOT_PREFIX,
    contains_secret,
    create_root,
    enclosing_git_project,
    first_answer,
    log_files,
    removable_root,
    remove_root,
    remove_secret_bearing,
    restaged,
    seed_ledger,
    seeded_rows,
    temporary_parent,
)
from ..lane_errors import UnavailableError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _link(target: Path, link: Path) -> None:
    """Make ``link`` a directory junction (Windows) or symbolic link to ``target``."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def _root_name() -> str:
    return f"{ROOT_PREFIX}{secrets.token_hex(16)}"


def test_the_parent_is_the_accounts_own_temporary_folder() -> None:
    assert temporary_parent({"LOCALAPPDATA": "C:\\Users\\someone\\AppData\\Local"}) == Path(
        "C:\\Users\\someone\\AppData\\Local", "Temp"
    )
    with pytest.raises(UnavailableError, match="LOCALAPPDATA"):
        temporary_parent({})


@pytest.mark.parametrize("marker", ["directory", "file"])
def test_a_root_below_a_git_project_is_refused_and_nothing_is_created(tmp_path: Path, marker: str) -> None:
    project = tmp_path / "project"
    parent = project / "deep" / "Temp"
    parent.mkdir(parents=True)
    if marker == "directory":
        (project / ".git").mkdir()
    else:
        # A worktree's .git is a file naming its common directory.
        (project / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")

    assert enclosing_git_project(parent) == project
    assert enclosing_git_project(parent / "not-yet-created") == project
    with pytest.raises(AcceptanceError, match="inside the Git project"):
        create_root(parent)
    assert list(parent.iterdir()) == []


def test_a_junction_into_a_git_project_is_caught_where_it_lands(tmp_path: Path) -> None:
    project = tmp_path / "project"
    inside = project / "inside"
    inside.mkdir(parents=True)
    (project / ".git").mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    linked = elsewhere / "Temp"
    _link(inside, linked)

    assert enclosing_git_project(linked) == project
    with pytest.raises(AcceptanceError, match="inside the Git project"):
        create_root(linked)
    assert list(inside.iterdir()) == []


def test_only_a_named_directory_directly_below_the_parent_is_removable(tmp_path: Path) -> None:
    parent = tmp_path / "Temp"
    root = parent / _root_name()
    root.mkdir(parents=True)
    assert removable_root(root, parent) == root.resolve()

    for name in ("cadrumo-e2e-short", "cadrumo-e2e-" + "G" * 32, "other", ROOT_PREFIX.rstrip("-")):
        wrong = parent / name
        wrong.mkdir()
        with pytest.raises(AcceptanceError, match="not named like a disposable root"):
            removable_root(wrong, parent)

    deeper = parent / "nested" / _root_name()
    deeper.mkdir(parents=True)
    with pytest.raises(AcceptanceError, match="not directly below"):
        removable_root(deeper, parent)
    with pytest.raises(AcceptanceError, match="not directly below"):
        removable_root(root, tmp_path / "other-parent")

    missing = parent / _root_name()
    with pytest.raises(AcceptanceError, match="not a directory"):
        removable_root(missing, parent)


def test_a_root_that_is_a_link_is_refused_and_its_target_kept(tmp_path: Path) -> None:
    parent = tmp_path / "Temp"
    parent.mkdir()
    target = tmp_path / "precious"
    target.mkdir()
    (target / "keep.txt").write_text("keep\n", encoding="utf-8")
    linked = parent / _root_name()
    _link(target, linked)

    with pytest.raises(AcceptanceError, match="it is a link"):
        remove_root(linked, parent)
    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep\n"


def test_removal_deletes_the_link_inside_the_root_and_never_its_target(tmp_path: Path) -> None:
    parent = tmp_path / "Temp"
    root = parent / _root_name()
    (root / "logs").mkdir(parents=True)
    (root / "logs" / "cadrumo.log").write_text("line\n", encoding="utf-8")
    readonly = root / "readonly.txt"
    readonly.write_text("read only\n", encoding="utf-8")
    readonly.chmod(0o444)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep\n", encoding="utf-8")
    _link(outside, root / "models")

    assert remove_root(root, parent) == []
    assert not root.exists()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep\n"


def test_a_path_that_cannot_be_removed_is_named_not_hidden(tmp_path: Path) -> None:
    parent = tmp_path / "Temp"
    root = parent / _root_name()
    locked_directory = root / "logs"
    locked_directory.mkdir(parents=True)
    locked = locked_directory / "cadrumo-native.jsonl"
    locked.write_text("{}\n", encoding="utf-8")
    if sys.platform == "win32":
        # Python opens files without delete sharing, so Windows refuses the deletion while the handle lives.
        holder = locked.open("rb")
        release = holder.close
    else:
        locked_directory.chmod(0o500)

        def release() -> None:
            locked_directory.chmod(0o700)

    try:
        left = remove_root(root, parent)
    finally:
        release()
    assert len(left) == 1
    assert left[0].startswith(str(locked))
    assert locked.exists()
    assert remove_root(root, parent) == []


def test_the_seed_carries_the_password_on_standard_input_only(tmp_path: Path) -> None:
    password = secrets.token_urlsafe(32)
    calls: list[tuple[tuple[str, ...], dict[str, str] | None]] = []

    def run(*arguments: str, secret: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
        calls.append((arguments, secret))
        if "import" in arguments:
            return 0, {"status": "success", "result": {}}
        return 0, {"status": "success", "result": {"total": 5, "rows": [{}] * 5}}

    csv_path = tmp_path / "seed.csv"
    assert seed_ledger(run, csv_path, password) == 5
    assert [arguments[1:4] for arguments, _ in calls] == [("app", "ledger", "import"), ("app", "ledger", "list")]
    assert calls[0][0][-4:] == ("--file", str(csv_path), "--provider", "csv")
    for arguments, secret in calls:
        assert arguments[0] == "--profile-secrets-stdin"
        assert all(password not in argument for argument in arguments)
        assert secret == {"profile_passphrase": password}


def test_the_seed_refuses_a_ledger_with_too_few_rows_without_naming_the_password() -> None:
    password = secrets.token_urlsafe(32)

    def run(*arguments: str, secret: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
        if "import" in arguments:
            return 0, {"status": "warning", "result": {}}
        return 0, {"status": "success", "result": {"total": MINIMUM_SEEDED_ROWS - 1, "rows": [{}, {}]}}

    with pytest.raises(AcceptanceError, match=f"holds {MINIMUM_SEEDED_ROWS - 1} movements") as refused:
        seed_ledger(run, Path("seed.csv"), password)
    assert password not in str(refused.value)


def test_a_refused_import_names_its_code_and_not_the_password() -> None:
    password = secrets.token_urlsafe(32)

    def run(*arguments: str, secret: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
        return 4, {"status": "error", "error": {"code": "REFUSED_LOCAL_RUNTIME", "message": "no runtime"}}

    with pytest.raises(AcceptanceError, match="app ledger import: exit 4, code REFUSED_LOCAL_RUNTIME") as refused:
        seed_ledger(run, Path("seed.csv"), password)
    assert password not in str(refused.value)


def test_the_row_count_reads_the_total_before_the_shown_rows() -> None:
    assert seeded_rows({"result": {"total": 7, "rows": [{}]}}) == 7
    assert seeded_rows({"result": {"rows": [{}, {}, {}]}}) == 3
    assert seeded_rows({"result": {"total": True, "rows": [{}]}}) == 1
    assert seeded_rows({"result": None}) == 0
    assert seeded_rows({}) == 0


def test_the_seed_fixture_is_five_synthetic_movements_the_csv_provider_reads() -> None:
    provider = CsvProvider()
    validation = provider.validate_source(LEDGER_SEED)
    assert validation.is_valid, validation.warnings
    parsed = tuple(provider.ingest(LEDGER_SEED))
    assert len(parsed) == 5
    assert len({row.raw.amount for row in parsed}) == 5
    assert {row.raw.currency for row in parsed} == {"EUR"}

    with LEDGER_SEED.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    printed = [row["Importe"].lstrip("-") for row in rows]
    assert len(set(printed)) == len(printed) >= MINIMUM_SEEDED_ROWS
    assert all(len(amount) >= 6 for amount in printed)
    assert all(len(row["Concepto"]) >= 6 for row in rows)
    assert all(row["Referencia"].startswith("E2E-") for row in rows)


def test_the_logs_copied_are_the_desktop_runtime_and_agent_logs_and_no_link_is_followed(tmp_path: Path) -> None:
    root = tmp_path / "root"
    logs = root / "logs"
    logs.mkdir(parents=True)
    for name in ("cadrumo-native.jsonl", "cadrumo.log", "cadrumo.log.1", "cadrumo.log.lock", "cadrumo-native.lock"):
        (logs / name).write_text("x\n", encoding="utf-8")
    (logs / "profile-worker-stall-1.txt").write_text("x\n", encoding="utf-8")
    runtime = root / "agent" / "abc" / "home" / "runtime"
    runtime.mkdir(parents=True)
    for name in ("gateway.log", "worker.log", "conversation-worker-1.stderr.log", "state.json"):
        (runtime / name).write_text("x\n", encoding="utf-8")
    (root / "agent" / "abc" / "home" / "other.log").write_text("x\n", encoding="utf-8")
    outside = tmp_path / "outside"
    (outside / "home" / "runtime").mkdir(parents=True)
    (outside / "home" / "runtime" / "gateway.log").write_text("x\n", encoding="utf-8")
    _link(outside, root / "agent" / "linked")

    assert sorted(relative for _source, relative in log_files(root)) == [
        "agent/abc/conversation-worker-1.stderr.log",
        "agent/abc/gateway.log",
        "agent/abc/worker.log",
        "logs/cadrumo-native.jsonl",
        "logs/cadrumo.log",
        "logs/cadrumo.log.1",
    ]


def test_a_results_file_holding_the_password_is_removed_and_named(tmp_path: Path) -> None:
    password = secrets.token_urlsafe(32)
    results = tmp_path / "results"
    (results / "logs").mkdir(parents=True)
    clean = results / "logs" / "cadrumo.log"
    clean.write_text("nothing here\n", encoding="utf-8")
    narrow = results / "logs" / "cadrumo-native.jsonl"
    narrow.write_bytes(b'{"m": "' + password.encode("utf-8") + b'"}\n')
    wide = results / "runtime-setup.stderr.log"
    wide.write_bytes(("prefix " + password).encode("utf-16-le"))

    found = remove_secret_bearing(results, password)
    assert len(found) == 2
    assert all(password not in finding for finding in found)
    assert clean.exists() and not narrow.exists() and not wide.exists()
    assert contains_secret(("x" + password).encode("utf-8"), password)
    assert not contains_secret(b"unrelated", password)


def test_the_launch_clock_stops_at_the_first_answer() -> None:
    now = [0.0]
    answers = iter([False, False, True])

    def pause(seconds: float) -> None:
        now[0] += seconds

    assert first_answer(lambda: next(answers), lambda: now[0], 10.0, pause) == pytest.approx(0.2)
    with pytest.raises(UnavailableError, match="no DevTools endpoint"):
        first_answer(lambda: False, lambda: now[0], now[0] + 0.25, pause)


def test_staging_counts_what_it_wrote_and_removed() -> None:
    before = {"a": (1, 10), "b": (2, 20), "gone": (3, 30)}
    after = {"a": (1, 10), "b": (5, 21), "new": (7, 40)}
    assert restaged(before, after) == {"files_written": 2, "bytes_written": 12, "files_removed": 1}
