"""Detector teeth for the secure-store write-path gate.

Every case builds an isolated source tree under ``tmp_path``. The gate must
report a store nothing fills, stay silent on the binding shapes the codebase
actually uses to write one, and fail on a declaration that has gone stale.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.quality.secure_store_write_path import (
    SecureStoreWritePathError,
    collect_store_usage,
    evaluate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPOSITORY = '''
class ExampleRepository(SecureBoundRepository[Payload]):
    """A secure store."""

    def save(self, payload: Payload) -> None:
        self._objects.save(payload)

    def load(self) -> Payload | None:
        return None
'''


def _tree(root: Path, modules: dict[str, str]) -> Path:
    """Write one synthetic source tree and return its root."""
    source = root / "src" / "cadrumo"
    for name, body in modules.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return source


def _declaration(root: Path, body: str) -> Path:
    path = root / "declaration.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_reports_a_store_that_is_read_and_never_written(tmp_path: Path) -> None:
    source = _tree(
        tmp_path,
        {
            "store.py": _REPOSITORY,
            "reader.py": "def show():\n    return ExampleRepository().load()\n",
        },
    )
    problems = evaluate(source, _declaration(tmp_path, ""))
    assert len(problems) == 1
    assert "ExampleRepository" in problems[0]
    assert "reader.py" in problems[0]


@pytest.mark.parametrize(
    "writer",
    [
        pytest.param("def go():\n    ExampleRepository().save(1)\n", id="direct-construction"),
        pytest.param(
            "def go():\n    repo = ExampleRepository()\n    repo.save(1)\n",
            id="assigned-name",
        ),
        pytest.param(
            "def go(repo: ExampleRepository) -> None:\n    repo.save(1)\n",
            id="annotated-parameter",
        ),
        pytest.param(
            "def go(repo: ExampleRepository | None = None) -> None:\n"
            "    resolved = repo if repo is not None else ExampleRepository()\n"
            "    resolved.save(1)\n",
            id="inject-or-default-conditional",
        ),
        pytest.param(
            "def go(repo=None):\n    resolved = repo or ExampleRepository()\n    resolved.save(1)\n",
            id="inject-or-default-boolop",
        ),
        pytest.param(
            "class Holder:\n"
            "    def __init__(self):\n"
            "        self._repo = ExampleRepository()\n"
            "    def go(self):\n"
            "        self._repo.save(1)\n",
            id="instance-attribute",
        ),
        pytest.param(
            "def _store() -> ExampleRepository:\n    return ExampleRepository()\ndef go():\n    _store().save(1)\n",
            id="module-accessor",
        ),
        pytest.param(
            "class Holder:\n"
            "    def _drafts(self) -> ExampleRepository:\n"
            "        return ExampleRepository()\n"
            "    def go(self):\n"
            "        self._drafts().save(1)\n",
            id="lazy-method-accessor",
        ),
    ],
)
def test_stays_silent_when_some_production_path_writes(tmp_path: Path, writer: str) -> None:
    source = _tree(
        tmp_path,
        {
            "store.py": _REPOSITORY,
            "reader.py": "def show():\n    return ExampleRepository().load()\n",
            "writer.py": writer,
        },
    )
    assert evaluate(source, _declaration(tmp_path, "")) == ()


@pytest.mark.parametrize(
    "method",
    ["save_period", "save_observation", "persist_row", "to_secure_object_write"],
)
def test_mutation_is_recognised_by_token_not_by_prefix(tmp_path: Path, method: str) -> None:
    source = _tree(
        tmp_path,
        {
            "store.py": _REPOSITORY,
            "reader.py": "def show():\n    return ExampleRepository().load()\n",
            "writer.py": f"def go():\n    ExampleRepository().{method}(1)\n",
        },
    )
    assert evaluate(source, _declaration(tmp_path, "")) == ()


def test_a_store_only_its_own_module_reads_is_not_reported(tmp_path: Path) -> None:
    source = _tree(tmp_path, {"store.py": _REPOSITORY + "\n\ndef peek():\n    return ExampleRepository().load()\n"})
    assert evaluate(source, _declaration(tmp_path, "")) == ()


def test_a_declaration_the_tree_now_writes_fails_as_spent(tmp_path: Path) -> None:
    source = _tree(
        tmp_path,
        {
            "store.py": _REPOSITORY,
            "reader.py": "def show():\n    return ExampleRepository().load()\n",
            "writer.py": "def go():\n    ExampleRepository().save(1)\n",
        },
    )
    declaration = _declaration(
        tmp_path,
        '[[read_only]]\nname = "ExampleRepository"\nkind = "awaiting_writer"\nrationale = "stale"\n',
    )
    problems = evaluate(source, declaration)
    assert len(problems) == 1
    assert problems[0].startswith("- ExampleRepository")


def test_a_declared_store_passes(tmp_path: Path) -> None:
    source = _tree(
        tmp_path,
        {
            "store.py": _REPOSITORY,
            "reader.py": "def show():\n    return ExampleRepository().load()\n",
        },
    )
    declaration = _declaration(
        tmp_path,
        '[[read_only]]\nname = "ExampleRepository"\nkind = "awaiting_writer"\nrationale = "known gap"\n',
    )
    assert evaluate(source, declaration) == ()


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param('name = "X"\nkind = "invented"\nrationale = "r"', id="unknown-kind"),
        pytest.param('name = "X"\nkind = "awaiting_writer"\nrationale = ""', id="blank-rationale"),
        pytest.param('name = ""\nkind = "awaiting_writer"\nrationale = "r"', id="blank-name"),
    ],
)
def test_an_unusable_declaration_is_refused(tmp_path: Path, entry: str) -> None:
    source = _tree(tmp_path, {"store.py": _REPOSITORY})
    declaration = _declaration(tmp_path, f"[[read_only]]\n{entry}\n")
    with pytest.raises(SecureStoreWritePathError):
        evaluate(source, declaration)


def test_the_shipped_tree_reports_its_stores() -> None:
    """The live scan finds repositories at all, so a silent pass cannot be vacuous."""
    usage = collect_store_usage()
    assert len(usage) >= 20
    assert any(store.written_by for store in usage)
    assert any(store.read_by for store in usage)


def test_the_shipped_tree_agrees_with_its_declaration() -> None:
    """The live gate, run where CI can see it.

    Without this the module is a command nobody invokes: the synthetic cases
    above prove the detector works on trees that do not ship, and a store wired
    for reading with no writer would still reach a release unremarked.
    """
    assert evaluate() == ()
