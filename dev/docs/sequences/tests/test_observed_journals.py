"""The docs check and its profile workers observe through the journal directory beside the sandbox storage.

The generic observer is tested in ``dev.dependency_observation``; these cases
cover the docs-owned worker script, journal directory and entry points. Expected
digests are computed here with ``hashlib``, independently of the observer.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from dev.dependency_observation.observation import (
    CHECKOUT_ROOT_FILE,
    CHILD_SCRIPT_NAME,
    Observation,
)
from dev.packaging.command_execution import run_command

from ..observed_journals import JOURNAL_DIRECTORY_NAME, WORKER_SCRIPT_NAME

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_WORKTREE = Path(__file__).resolve().parents[4]
_SEQUENCES = _WORKTREE / "dev" / "docs" / "sequences"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _names_digest(*names: str) -> str:
    return _sha("\n".join(sorted(names)).encode("utf-8"))


def _write(path: Path, data: bytes | str = b"") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


def _journal_lines(path: Path) -> list[list[str]]:
    return [line.split("\t") for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    directory = tmp_path / "checkout"
    directory.mkdir()
    return directory.resolve()


def _child(code: str, *arguments: str, cwd: Path) -> tuple[int, str, str]:
    result = run_command([sys.executable, "-I", "-B", "-c", code, *arguments], cwd=cwd, environment=None)
    return result.returncode, result.stdout, result.stderr


_OBSERVE_WORKER_CHILD = (
    "import sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from dev.docs.sequences.observed_journals import observe_worker\n"
    "observe_worker(Path(sys.argv[2]), Path(sys.argv[3]))\n"
    "Path(sys.argv[4]).read_bytes()\n"
)


def test_an_observed_worker_writes_a_begin_line_first_and_journals_what_it_then_reads(
    root: Path, tmp_path: Path
) -> None:
    journals = tmp_path / "journals"
    journals.mkdir()
    target = _write(root / "worker-data" / "input.bin", b"\x00worker input\xff")
    code, _out, err = _child(_OBSERVE_WORKER_CHILD, str(_WORKTREE), str(root), str(journals), str(target), cwd=tmp_path)
    assert code == 0, err
    (journal,) = journals.glob("*.journal")
    lines = _journal_lines(journal)
    assert lines[0][0] == "B"
    assert ["F", _sha(b"\x00worker input\xff"), str(target)] in lines
    assert ["D", _names_digest("input.bin"), str(target.parent)] in lines
    assert not any(line[0] == "X" for line in lines)

    parent = Observation(root, started_ns=0)
    parent.harvest(journals)
    assert parent.files[target] == _sha(b"\x00worker input\xff")
    assert parent.incomplete == []


def test_the_worker_script_refuses_to_run_when_the_checkout_pointer_is_missing(tmp_path: Path) -> None:
    journals = tmp_path / "journals"
    script = _write(journals / WORKER_SCRIPT_NAME, (_SEQUENCES / WORKER_SCRIPT_NAME).read_bytes())
    result = run_command([sys.executable, "-I", "-B", str(script)], cwd=tmp_path, environment=None)
    assert result.returncode != 0
    assert CHECKOUT_ROOT_FILE in result.stderr
    assert list(journals.glob("*.journal")) == [], "a refused worker must not leave an unobserved run behind"


_PREPARE_CHILD = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from dev.dependency_observation.observation import observe_process\n"
    "from dev.docs.sequences.observed_journals import prepare_worker_journals\n"
    "if sys.argv[3] == 'observed':\n"
    "    observe_process(Path(sys.argv[2]))\n"
    "storage = Path(sys.argv[4])\n"
    "prepared = prepare_worker_journals(storage)\n"
    "print(json.dumps(None if prepared is None else str(prepared)))\n"
)


def test_worker_journals_are_prepared_only_by_an_observed_process(root: Path, tmp_path: Path) -> None:
    storage = tmp_path / "sandbox" / "storage"
    storage.mkdir(parents=True)
    code, out, err = _child(_PREPARE_CHILD, str(_WORKTREE), str(root), "plain", str(storage), cwd=tmp_path)
    assert code == 0, err
    assert json.loads(out.strip().splitlines()[-1]) is None
    assert not (storage.parent / JOURNAL_DIRECTORY_NAME).exists()

    code, out, err = _child(_PREPARE_CHILD, str(_WORKTREE), str(root), "observed", str(storage), cwd=tmp_path)
    assert code == 0, err
    prepared = Path(json.loads(out.strip().splitlines()[-1]))
    assert prepared == storage.parent / JOURNAL_DIRECTORY_NAME
    assert (prepared / WORKER_SCRIPT_NAME).read_bytes() == (_SEQUENCES / WORKER_SCRIPT_NAME).read_bytes()
    assert (prepared / CHECKOUT_ROOT_FILE).read_text(encoding="utf-8") == str(root)
    assert (prepared / CHILD_SCRIPT_NAME).read_bytes() == (
        _WORKTREE / "dev" / "dependency_observation" / CHILD_SCRIPT_NAME
    ).read_bytes()
    assert {Path(path).name for path in _registered_after_prepare(root, tmp_path, storage)} == {
        WORKER_SCRIPT_NAME,
        CHILD_SCRIPT_NAME,
    }


_REGISTERED_CHILD = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from dev.dependency_observation.observation import observe_process\n"
    "from dev.docs.sequences.observed_journals import prepare_worker_journals\n"
    "observation = observe_process(Path(sys.argv[2]))\n"
    "prepare_worker_journals(Path(sys.argv[3]))\n"
    "print(json.dumps(sorted(observation.worker_scripts)))\n"
)


def _registered_after_prepare(root: Path, tmp_path: Path, storage: Path) -> list[str]:
    code, out, err = _child(_REGISTERED_CHILD, str(_WORKTREE), str(root), str(storage), cwd=tmp_path)
    assert code == 0, err
    registered = json.loads(out.strip().splitlines()[-1])
    assert isinstance(registered, list)
    return [str(path) for path in registered]
