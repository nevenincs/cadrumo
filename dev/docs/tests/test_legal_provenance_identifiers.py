"""Reviewer prose keeps its words while declared source identifiers stay literal."""

from __future__ import annotations

import pytest
from docutils import nodes
from docutils.core import publish_doctree

from ..legal_page_rendering import rst_provenance_text
from ..legal_reference_models import LegalProvisionRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


@pytest.mark.parametrize("anchor", ["datrigesima", "dtquinta", "dadecimotercera-2"])
def test_reviewer_source_identifiers_preserve_text_and_leave_near_matches_as_prose(anchor: str) -> None:
    record = LegalProvisionRecord(
        legal_id="ley-35-2006:da-30",
        kind="ley",
        document_id="BOE-A-2006-20764",
        corpus_ref=f"corpus/normatives/html/ley-35-2006.html#{anchor}",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
    )
    source = (
        f"Reviewer prose with typppo, #{anchor}. The file ley-35-2006.html and {anchor} match; "
        f"#{anchor}typo, #{anchor}-extra, prefix{anchor}, and {anchor}.extension do not."
    )
    tree = publish_doctree(rst_provenance_text(source, record))
    assert tree.astext() == source
    assert tuple(node.astext() for node in tree.findall(nodes.literal)) == (
        "#" + anchor,
        "ley-35-2006.html",
        anchor,
    )
    ordinary = " ".join(str(node) for node in tree.findall(nodes.Text) if not isinstance(node.parent, nodes.literal))
    assert "typppo" in ordinary
    assert f"#{anchor}typo" in ordinary
    assert f"#{anchor}-extra" in ordinary
    assert f"{anchor}.extension" in ordinary


def test_reviewer_without_source_identifiers_remains_ordinary_prose() -> None:
    record = LegalProvisionRecord(
        legal_id="ley-35-2006:art-1",
        kind="ley",
        document_id="BOE-A-2006-20764",
        corpus_ref="corpus/normatives/html/ley-35-2006.html#a1",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
    )
    source = "Agent review is pending; this paragraph has typppo and an unregistered #otheranchor."
    tree = publish_doctree(rst_provenance_text(source, record))
    assert tree.astext() == source
    assert not tuple(tree.findall(nodes.literal))
