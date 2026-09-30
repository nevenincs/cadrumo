"""The gate verdict is reused only for exactly the inputs it was proven on."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.tests.env_scope import scoped_env_var
from dev.cache_root import DEV_CACHE_ROOT_ENV

from ..verdict_cache import (
    FORCE_ENV,
    check_reusing_verdict,
    engine_import_closure,
    record_clean_verdict,
    reused_verdict,
    verdict_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _tree(root: Path) -> tuple[Path, Path]:
    files = {
        "src/cadrumo/cli.py": "print('cli')\n",
        "dev/docs/sequences/runner.py": "# engine\n",
        "dev/docs/build.py": "# build\n",
        "uv.lock": "lock\n",
        "docs/_sequences/how-to/page/seq.json": '{"frames": []}\n',
        "docs/_sequences/contracts/how-to/page/seq.seq": "@result aeat --version\n",
        "docs/how-to/page.md": "# Page\n\nProse.\n\n```{cli-sequence} seq\n:verify: Check it.\n```\n",
    }
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root, root / "docs"


def _key(repo: Path, docs: Path, authority_database: str = "db-1") -> str:
    return verdict_key(
        docs_root=docs,
        goldens_root=None,
        authority_database_sha256=authority_database,
        repo_root=repo,
    )


@pytest.mark.parametrize(
    ("relative", "text"),
    [
        ("src/cadrumo/cli.py", "print('changed')\n"),
        ("dev/docs/sequences/runner.py", "# engine changed\n"),
        ("uv.lock", "lock changed\n"),
        ("docs/_sequences/how-to/page/seq.json", '{"frames": [1]}\n'),
        ("docs/_sequences/contracts/how-to/page/seq.seq", "@result aeat --help\n"),
        ("docs/how-to/page.md", "# Page\n\nProse.\n\n```{cli-sequence} seq\n:verify: Check more.\n```\n"),
    ],
)
def test_any_input_the_verdict_depends_on_changes_the_key(tmp_path: Path, relative: str, text: str) -> None:
    repo, docs = _tree(tmp_path)
    before = _key(repo, docs)
    (repo / relative).write_text(text, encoding="utf-8")
    assert _key(repo, docs) != before


def _engine_importing_helpers(root: Path) -> tuple[Path, Path]:
    """Extend the fixture tree with an engine module that reaches dev helpers four ways."""
    repo, docs = _tree(root)
    files = {
        "dev/__init__.py": "",
        "dev/docs/__init__.py": "",
        "dev/docs/sequences/__init__.py": "",
        "dev/docs/sequences/checks.py": (
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "from dev.packaging.command_execution import run_command\n"
            "from .runner import frames\n"
            "if TYPE_CHECKING:\n"
            "    from dev.typing_only import Shape\n"
            "def currency() -> None:\n"
            "    from dev.registry.pipeline.publication import generation\n"
            "def spawn() -> None:\n"
            "    from dev.lazy_helper import launch\n"
        ),
        "dev/packaging/__init__.py": "",
        "dev/packaging/command_execution.py": "from dev._paths import REPO_ROOT\n",
        "dev/_paths.py": "REPO_ROOT = None\n",
        "dev/lazy_helper.py": "def launch() -> None: ...\n",
        "dev/typing_only.py": "class Shape: ...\n",
        "dev/registry/__init__.py": "",
        "dev/registry/pipeline/__init__.py": "",
        "dev/registry/pipeline/publication.py": "generation = 1\n",
    }
    for relative, text in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return repo, docs


def test_the_closure_follows_runtime_dev_imports_and_skips_typing_and_registry_tooling(tmp_path: Path) -> None:
    repo, _docs = _engine_importing_helpers(tmp_path)

    closure = engine_import_closure(repo)

    assert "dev/packaging/command_execution.py" in closure
    assert "dev/_paths.py" in closure
    assert "dev/lazy_helper.py" in closure
    assert "dev/packaging/__init__.py" in closure
    assert "dev/typing_only.py" not in closure
    assert not any(path.startswith("dev/registry/") for path in closure)


@pytest.mark.parametrize(
    ("relative", "changes_key"),
    [
        ("dev/packaging/command_execution.py", True),
        ("dev/_paths.py", True),
        ("dev/lazy_helper.py", True),
        ("dev/typing_only.py", False),
        ("dev/registry/pipeline/publication.py", False),
    ],
)
def test_a_dev_module_the_engine_imports_is_a_verdict_input(tmp_path: Path, relative: str, changes_key: bool) -> None:
    repo, docs = _engine_importing_helpers(tmp_path)
    before = _key(repo, docs)
    path = repo / relative
    path.write_text(path.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
    assert (_key(repo, docs) != before) is changes_key


def test_a_new_authority_database_changes_the_key(tmp_path: Path) -> None:
    repo, docs = _tree(tmp_path)
    assert _key(repo, docs, "db-1") != _key(repo, docs, "db-2")


def test_page_prose_outside_the_directives_does_not_change_the_key(tmp_path: Path) -> None:
    repo, docs = _tree(tmp_path)
    before = _key(repo, docs)
    page = docs / "how-to" / "page.md"
    page.write_text(page.read_text(encoding="utf-8").replace("Prose.", "Reworded prose."), encoding="utf-8")
    assert _key(repo, docs) == before


def test_only_a_recorded_clean_verdict_is_reused_and_force_bypasses_it(tmp_path: Path) -> None:
    with scoped_env_var(DEV_CACHE_ROOT_ENV, str(tmp_path / "cache")):
        assert reused_verdict("a" * 64) is None
        record_clean_verdict("a" * 64)
        reused = reused_verdict("a" * 64)
        assert reused is not None
        assert "aaaaaaaaaaaa" in reused
        assert reused_verdict("b" * 64) is None
        with scoped_env_var(FORCE_ENV, "1"):
            assert reused_verdict("a" * 64) is None


def test_the_shared_flow_runs_once_reuses_after_a_pass_and_never_records_a_divergence(tmp_path: Path) -> None:
    calls: list[str] = []

    def passing() -> tuple[str, ...]:
        calls.append("pass")
        return ()

    def diverging() -> tuple[str, ...]:
        calls.append("diverge")
        return ("frame 3 diverged",)

    with scoped_env_var(DEV_CACHE_ROOT_ENV, str(tmp_path / "cache")):
        assert check_reusing_verdict("c" * 64, passing) == ((), None)
        problems, reused = check_reusing_verdict("c" * 64, passing)
        assert problems == ()
        assert reused is not None
        assert calls == ["pass"]

        assert check_reusing_verdict("d" * 64, diverging) == (("frame 3 diverged",), None)
        assert check_reusing_verdict("d" * 64, diverging) == (("frame 3 diverged",), None)
        assert calls == ["pass", "diverge", "diverge"]
