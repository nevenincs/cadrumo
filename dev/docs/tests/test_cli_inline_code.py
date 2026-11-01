"""CLI reference preserves the code semantics of authored help."""

from pathlib import Path

import pytest
from docutils import nodes
from docutils.core import publish_doctree

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
from dev.locales.signal_document_prose import visible_document_prose

from ..cli_reference import _cli_help_as_rst, _render_graph_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.docs]


def test_only_complete_markdown_code_spans_become_rst_literals() -> None:
    source = "Use `fifo` or `pmp`; :ref:`guide`, `label <https://example.org>`_, ``existing``, x=`value`, and `open."
    assert _cli_help_as_rst(source) == (
        "Use ``fifo`` or ``pmp``; :ref:`guide`, `label <https://example.org>`_, ``existing``, x=`value`, and `open."
    )
    before = publish_doctree(source, settings_overrides={"report_level": 5, "halt_level": 6})
    after = publish_doctree(_cli_help_as_rst(source), settings_overrides={"report_level": 5, "halt_level": 6})
    assert before.astext() == after.astext()


def test_multilingual_compile_receives_rst_code_markup(tmp_path: Path) -> None:
    from .._locale_chrome import markup_page
    from ..compile_slots import activate, deactivate
    from ..message_marks import FRAGMENT_PREFIX, prepare

    page = tmp_path / "cli" / "app" / "ledger.rst"
    page.parent.mkdir(parents=True)
    page.write_text("Ledger\n======\n", encoding="utf-8")
    path = ("aeat", "app", "ledger", "inventory", "create")
    node = next(node for node in COMMAND_GRAPH.nodes() if node.path == path)
    slots = activate(("en", "es", "ca", "hu"))
    try:
        with markup_page("cli/app/ledger"):
            _render_graph_command(OutputLanguage.EN, path, node.spec)
        prepare(
            tmp_path,
            slots=slots,
            docnames=["cli/app/ledger"],
            doc2path=lambda _docname: page,
            source_language="en",
            compact=False,
        )
    finally:
        deactivate()
    fragment = page.parent / f"{FRAGMENT_PREFIX}ledger.rst"
    text = fragment.read_text(encoding="utf-8")
    assert "``fifo``" in text and "``pmp``" in text


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_real_generated_commands_keep_literal_nodes_and_visible_prose(language: OutputLanguage, tmp_path: Path) -> None:
    paths = (("aeat", "app", "ledger", "inventory", "create"), ("aeat", "app", "live", "verify", "tgvi"))
    graph_nodes = {node.path: node for node in COMMAND_GRAPH.nodes()}
    source = "\n".join(_render_graph_command(language, path, graph_nodes[path].spec) for path in paths)
    document = publish_doctree(source, settings_overrides={"report_level": 5, "halt_level": 6})
    literals = {node.astext() for node in document.findall(nodes.literal)}
    assert {"fifo", "pmp", "nif"} <= literals
    assert not any(node.astext() in {"fifo", "pmp"} for node in document.findall(nodes.title_reference))

    page = tmp_path / "docs" / "cli" / "app" / "sample.rst"
    page.parent.mkdir(parents=True)
    page.write_text(source + "\nNearby misspeling.\n", encoding="utf-8")
    prose = " ".join(text for _line, text in visible_document_prose(page))
    assert "misspeling" in prose
    assert "fifo" not in prose and "pmp" not in prose
