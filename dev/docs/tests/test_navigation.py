"""Each page's sidebar is the collapsed toctree, rendered by Sphinx itself.

Built with the real theme on a small fixture site whose tree has two sections,
each with a nested page. A page's sidebar must carry its ancestors, their
siblings, the top-level sections and its own children, and must not carry the
nested pages of a section it is not in. The same site built without the
collapsed navigation carries every page on every page, which is the cost this
exists to remove, and doubles as proof that the check can see a full tree.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_PAGES = {
    "index": "Home\n====\n\n.. toctree::\n   :caption: Guide\n\n   section-a/index\n   section-b/index\n",
    "section-a/index": "Section A\n=========\n\n.. toctree::\n\n   a1\n   a2\n",
    "section-a/a1": "Page A1\n=======\n\n.. toctree::\n\n   a1x\n",
    "section-a/a1x": "Page A1X\n========\n\nLeaf.\n",
    "section-a/a2": "Page A2\n=======\n\nLeaf.\n",
    "section-b/index": "Section B\n=========\n\n.. toctree::\n\n   b1\n",
    "section-b/b1": "Page B1\n=======\n\n.. toctree::\n\n   b1x\n",
    "section-b/b1x": "Page B1X\n========\n\nLeaf.\n",
}


def _build(tmp_path: Path, *, collapsed: bool) -> str:
    source = tmp_path / ("collapsed" if collapsed else "full") / "src"
    for name, text in _PAGES.items():
        page = source / f"{name}.rst"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(text, encoding="utf-8")
    register = "def setup(app):\n    from dev.docs.navigation import register\n    register(app)\n" if collapsed else ""
    (source / "conf.py").write_text(
        textwrap.dedent(
            f"""\
            import sys
            sys.path.insert(0, {str(REPO_ROOT)!r})
            project = "fixture"
            html_theme = "furo"
            """
        )
        + register,
        encoding="utf-8",
    )
    out = source.parent / "html"
    completed = subprocess.run(  # noqa: S603 - fixed argv: this interpreter running Sphinx on a fixture tree
        [sys.executable, "-m", "sphinx", "-b", "html", "-q", "-W", str(source), str(out)],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return (out / "section-a" / "a1.html").read_text(encoding="utf-8")


def _sidebar_titles(page: str) -> set[str]:
    tree = BeautifulSoup(page, "html.parser").select_one("div.sidebar-tree")
    assert tree is not None, "the theme rendered no sidebar tree"
    return {link.get_text(strip=True) for link in tree.select("a.reference.internal")}


def test_a_page_sidebar_is_its_collapsed_branch(tmp_path: Path) -> None:
    titles = _sidebar_titles(_build(tmp_path, collapsed=True))
    assert {"Section A", "Section B", "Page A1", "Page A2", "Page A1X"} <= titles
    assert not titles & {"Page B1", "Page B1X"}, f"a non-ancestor branch was expanded: {sorted(titles)}"


def test_the_theme_alone_embeds_every_page_on_every_page(tmp_path: Path) -> None:
    """Teeth: the same check sees the full tree when the collapse is not applied."""
    titles = _sidebar_titles(_build(tmp_path, collapsed=False))
    assert {"Page B1", "Page B1X"} <= titles
