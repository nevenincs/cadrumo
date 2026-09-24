"""The gate verdict is reused only for exactly the inputs it was proven on."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.tests.env_scope import scoped_env_var
from dev.cache_root import DEV_CACHE_ROOT_ENV

from ..verdict_cache import FORCE_ENV, record_clean_verdict, reused_verdict, verdict_key

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


def _key(repo: Path, docs: Path, generation: str = "gen-1") -> str:
    return verdict_key(docs_root=docs, goldens_root=None, authority_generation=generation, repo_root=repo)


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


def test_a_new_authority_generation_changes_the_key(tmp_path: Path) -> None:
    repo, docs = _tree(tmp_path)
    assert _key(repo, docs, "gen-1") != _key(repo, docs, "gen-2")


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
