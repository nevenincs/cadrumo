"""A section the design leaves unnamed has its own heading key on each page of a generated layout.

An unnamed section holds what a page places outside its named parts, so the
same id names a different part on every page. A heading key shared between
two pages would give both parts one translation, which is wrong on all but
one of them. Sections the design names share a key on purpose: the key is the
design's own words.
"""

from __future__ import annotations

from collections import defaultdict
from functools import cache

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import FormLayoutDefinition, FormLayoutSeedSource

from ...compiler.loader import load_registry_tree
from ..cli import REGISTRY_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _generated_layouts() -> tuple[tuple[str, str, FormLayoutDefinition], ...]:
    modelos, _catalogues = load_registry_tree(REGISTRY_ROOT)
    return tuple(
        (str(modelo.id), str(revision_id), layout)
        for modelo in modelos
        for revision_id, revision in modelo.revisions.items()
        for layout in revision.form_layouts
        if layout.seed_source is not FormLayoutSeedSource.AUTHORED
    )


def _unnamed_keys_on_several_pages(layout: FormLayoutDefinition) -> dict[str, list[str]]:
    pages: defaultdict[str, set[str]] = defaultdict(set)
    for page in layout.pages:
        for section in page.sections:
            if section.official_heading is None:
                pages[section.heading_key].add(page.id)
    return {key: sorted(ids) for key, ids in pages.items() if len(ids) > 1}


def test_no_unnamed_section_shares_its_heading_key_with_another_page() -> None:
    shared = {
        f"{modelo} {revision}": keys
        for modelo, revision, layout in _generated_layouts()
        if (keys := _unnamed_keys_on_several_pages(layout))
    }

    assert _generated_layouts()
    assert shared == {}


def test_a_form_with_unnamed_sections_on_several_pages_is_checked() -> None:
    pages_with_unnamed = [
        sum(1 for page in layout.pages if any(section.official_heading is None for section in page.sections))
        for _modelo, _revision, layout in _generated_layouts()
    ]

    assert max(pages_with_unnamed) > 1
