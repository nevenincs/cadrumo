"""The indexed Python domain resolves every lookup exactly as Sphinx's own search does."""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest
from sphinx.application import Sphinx
from sphinx.domains.python import PythonDomain

from ..python_xref_index import IndexedPythonDomain

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_PAGES = {
    "alpha": """Alpha
=====

.. py:module:: pkg.alpha

.. py:class:: Widget

   .. py:method:: render()

   .. py:attribute:: size

.. py:function:: build()

.. py:data:: Widget_alias
""",
    "beta": """Beta
====

.. py:module:: pkg.beta

.. py:class:: Widget

   .. py:method:: build()

.. py:exception:: Failure

.. py:function:: render()
""",
    "gamma": """Gamma
=====

.. py:module:: other.gamma.deep

.. py:class:: Failure

.. py:attribute:: Failure.size
""",
}


def _build(tmp_path: Path) -> Sphinx:
    source = tmp_path / "source"
    source.mkdir()
    (source / "conf.py").write_text("extensions = ['dev.docs.python_xref_index']\n", encoding="utf-8", newline="\n")
    toctree = "\n".join(f"   {name}" for name in _PAGES)
    (source / "index.rst").write_text(f"Index\n=====\n\n.. toctree::\n\n{toctree}\n", encoding="utf-8", newline="\n")
    for name, text in _PAGES.items():
        (source / f"{name}.rst").write_text(text, encoding="utf-8", newline="\n")
    app = Sphinx(
        str(source),
        str(source),
        str(tmp_path / "out"),
        str(tmp_path / "doctrees"),
        "dummy",
        status=None,
        warning=None,
        freshenv=True,
    )
    app.build()
    return app


def _queries() -> list[tuple[str, str, str, str | None, int]]:
    names = ("Widget", "render", "render()", "build", "size", "Failure", "Widget.render", "gamma.deep.Failure", "x", "")
    modules = ("", "pkg.alpha", "pkg.beta", "nowhere")
    classes = ("", "Widget", "Failure")
    types = (None, "class", "meth", "func", "attr", "exc", "obj", "mod", "unknown-role")
    return [
        (module, cls, name, kind, mode)
        for module, cls, name, kind, mode in itertools.product(modules, classes, names, types, (0, 1))
    ]


def test_every_lookup_matches_the_unindexed_search(tmp_path: Path) -> None:
    app = _build(tmp_path)
    domain = app.env.domains["py"]
    assert isinstance(domain, IndexedPythonDomain)
    fuzzy_hits = 0
    for module, cls, name, kind, mode in _queries():
        expected = PythonDomain.find_obj(domain, app.env, module, cls, name, kind, mode)
        actual = domain.find_obj(app.env, module, cls, name, kind, mode)
        assert actual == expected, (module, cls, name, kind, mode)
        fuzzy_hits += mode == 1 and len(expected) > 1
    # The comparison must reach the branch the index replaces, with several candidates.
    assert fuzzy_hits > 0


def test_the_index_follows_inventory_changes(tmp_path: Path) -> None:
    app = _build(tmp_path)
    domain = app.env.domains["py"]
    assert isinstance(domain, IndexedPythonDomain)
    assert [name for name, _ in domain.find_obj(app.env, "", "", "Failure", None, 1)] == [
        "pkg.beta.Failure",
        "other.gamma.deep.Failure",
    ]

    domain.clear_doc("beta")
    assert [name for name, _ in domain.find_obj(app.env, "", "", "Failure", None, 1)] == ["other.gamma.deep.Failure"]

    app.env.temp_data["docname"] = "beta"
    domain.note_object("late.Failure", "class", "late-failure")
    assert [name for name, _ in domain.find_obj(app.env, "", "", "Failure", None, 1)] == [
        "other.gamma.deep.Failure",
        "late.Failure",
    ]
