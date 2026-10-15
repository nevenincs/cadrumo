"""Resolve imported external annotation names through their real inventory."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from sphinx.application import Sphinx

from dev._paths import REPO_ROOT

from ._sphinx_probe import run_sphinx_probe

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_imported_textual_event_names_link_to_inventory(tmp_path: Path) -> None:
    run_sphinx_probe(__name__, "_build_imported_textual_event_probe", tmp_path)


def _build_imported_textual_event_probe(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    inventory_path = REPO_ROOT / "docs" / "_inventories" / "textual.inv"
    (docs / "conf.py").write_text(
        f"""\
import importlib.util
import os
os.environ['CADRUMO_DOCS_PROJECT_ROOT'] = {str(REPO_ROOT)!r}
spec = importlib.util.spec_from_file_location('contextual_reference_conf', {str(REPO_ROOT / "docs" / "conf.py")!r})
docs_conf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs_conf)
project = 'Contextual references'
extensions = ['sphinx.ext.intersphinx']
intersphinx_mapping = {{'textual': ('https://textual.textualize.io/', {str(inventory_path)!r})}}
master_doc = 'index'
nitpicky = True
def setup(app):
    app.connect('missing-reference', docs_conf._resolve_short_reference, priority=700)
""",
        encoding="utf-8",
    )
    (docs / "index.rst").write_text(
        "Contextual references\n=====================\n\n"
        ".. py:currentmodule:: cadrumo.entrypoints.tui.profile.overview_interactions\n\n"
        ":class:`Message` :class:`DescendantFocus` :class:`DataTable.RowSelected` "
        ":class:`Input.Changed` :class:`Checkbox.Changed`\n\n"
        ":class:`Input.MissingEvent` :class:`MissingFirstParty`\n",
        encoding="utf-8",
    )
    warnings = io.StringIO()
    app = Sphinx(
        str(docs),
        str(docs),
        str(tmp_path / "html"),
        str(tmp_path / "doctrees"),
        "html",
        status=io.StringIO(),
        warning=warnings,
        freshenv=True,
    )
    app.build(force_all=True)
    warning_text = warnings.getvalue()
    assert warning_text.count("WARNING:") == 2, warning_text
    assert "reference target not found: Input.MissingEvent" in warning_text
    assert "reference target not found: MissingFirstParty" in warning_text
    html = (tmp_path / "html" / "index.html").read_text(encoding="utf-8")
    for anchor in (
        "textual.message.Message",
        "textual.events.DescendantFocus",
        "textual.widgets._data_table.DataTable.RowSelected",
        "textual.widgets._input.Input.Changed",
        "textual.widgets._checkbox.Checkbox.Changed",
    ):
        assert f"#{anchor}" in html
