"""Regression coverage for the generated legal-reference RST projection."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from docutils import nodes
from docutils.core import publish_doctree

from ..legal_reference import LegalProvisionRecord, render_legal_reference

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _system_messages(rst: str) -> tuple[str, ...]:
    """Parse generated RST and return docutils diagnostics from its tree."""
    warning_stream = StringIO()
    doctree = publish_doctree(
        rst,
        settings_overrides={"report_level": 1, "warning_stream": warning_stream},
    )
    return tuple(node.astext() for node in doctree.findall(nodes.system_message))


def test_required_text_trailing_whitespace_is_removed_only_from_rst_projection() -> None:
    """Inline literals stay valid without mutating authored required text."""
    record = LegalProvisionRecord(
        legal_id="ley-37-1992:art-99",
        kind="ley",
        document_id="BOE-A-1992-28740",
        corpus_ref="src/cadrumo/_data/corpus/normatives/html/ley-37-1992-art-99.html#a99",
        permalink="https://www.boe.es/eli/es/l/1992/12/28/37",
        required_text=("first authoritative phrase ", "second authoritative phrase"),
    )

    page = render_legal_reference(_REPO_ROOT, records=(record,)).pages[0]

    assert record.required_text == ("first authoritative phrase ", "second authoritative phrase")
    assert ":Required text: ``first authoritative phrase``; ``second authoritative phrase``" in page.rst
    assert _system_messages(page.rst) == ()


def test_authoritative_legal_pages_are_docutils_clean() -> None:
    """The registry-backed legal pages contain no docutils warnings."""
    result = render_legal_reference(_REPO_ROOT)
    failures = [
        f"{page.output_relpath}: {messages}"
        for page in result.pages
        if (messages := _system_messages(page.rst))
    ]

    assert not failures, "generated legal-reference RST has docutils diagnostics:\n" + "\n".join(failures)
