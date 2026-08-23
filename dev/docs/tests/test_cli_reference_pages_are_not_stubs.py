"""The generated CLI reference must be readable pages, not link skeletons.

Every string the reference renders lives in the locale catalogue, and a catalogue
key survives ``scaffold`` only while something references it. That is correct: the
sanctioned way to keep a string is to use it. But it makes one regression silent and
cheap. A renderer stops calling a family of display copy; the copy becomes
unreferenced; the next ``scaffold`` prunes it; and every key-count gate goes GREEN
while the published pages quietly lose their titles, their orientation and their
headings. Nothing in a parity count can tell that apart from ordinary tidying.

BOTH HALVES OF THAT HAPPENED HERE. The per-command renderer emitted
``parameter.help_key.value`` -- the dotted key itself -- on every parameter of every
page, and classified each one with a hardcoded English ``(required)``. The family
landing page rendered as a bare bullet list under the raw family token, with no
title, no intro, no group heading and no way back to the index. In both cases the
authored wording existed in four locales and was simply never called, and in the
family case it had already been pruned by the time it was noticed.

SO THIS MODULE ASSERTS THE RENDERED OUTPUT, NOT THE KEYS. Key-level checks cannot
protect vocabulary that is gone, and cannot distinguish "deleted because dead" from
"deleted because unwired". A page that reads as a stub fails here whatever the
catalogue contains, and the failure names the page.

WHAT IS NOT PINNED. No wording, and no count of pages, groups or parameters: the
command graph moves constantly and any tally would be a constant to update rather
than a property to hold. What is pinned is that a page carries more than its own
skeleton.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.docs]

#: A dotted catalogue key rendered as page text. Any occurrence is a renderer that
#: emitted the NAME of a string instead of the string.
_LEAKED_KEY = re.compile(r"(?m)^\s+((?:cli|docs|flows|application|errors)\.[a-z0-9_.]+)\s*$")

#: Family landing pages: ``cli/app.rst``, ``cli/config.rst``. The generated index,
#: automation and schemas pages are a different shape and are checked separately.
_FAMILY_PAGE = re.compile(r"^cli/(?!index|automation|schemas)[a-z0-9_-]+\.rst$")


@pytest.fixture(scope="module")
def rendered_pages() -> dict[str, str]:
    """Every page the real generator produces, rendered once for this module."""
    from dev.docs.cli_reference import generate_cli_reference

    root = Path(tempfile.mkdtemp())
    (root / "index.rst").write_text("placeholder\n", encoding="utf-8")
    pages = generate_cli_reference(root)
    assert pages, "the CLI reference generator produced no pages at all"
    return pages


def test_no_page_prints_a_translation_key_instead_of_its_text(rendered_pages: dict[str, str]) -> None:
    """A dotted key on the page means the reader is shown an identifier.

    Scoped to lines that are ONLY a dotted token, so prose legitimately naming a key
    or a dotted module path inside a sentence does not trip it.
    """
    leaked: dict[str, list[str]] = {}
    for name, text in rendered_pages.items():
        found = sorted({match.group(1) for match in _LEAKED_KEY.finditer(text)})
        if found:
            leaked[name] = found[:4]

    assert not leaked, (
        "these generated pages print translation keys where the operator should read the text "
        f"they name: {leaked}"
    )


def test_family_pages_carry_more_than_their_link_skeleton(rendered_pages: dict[str, str]) -> None:
    """A family landing page is a reader's entry into a whole command family.

    Asserted structurally rather than by wording: the page must not be reducible to a
    heading plus links. The check is that it carries prose -- a line that is neither a
    heading, a bullet, nor blank -- which a stub page does not.
    """
    family_pages = sorted(name for name in rendered_pages if _FAMILY_PAGE.match(name))
    assert family_pages, f"no family landing page was generated; pages were {sorted(rendered_pages)}"

    stubs = []
    for name in family_pages:
        lines = rendered_pages[name].splitlines()
        prose = [
            line
            for line in lines
            if line.strip()
            and not line.lstrip().startswith("*")
            and not set(line.strip()) <= {"=", "-", "~", "^"}
        ]
        # The title line itself is prose by this measure, so a bare stub still yields
        # one entry; more than one means the page says something beyond its own name.
        if len(prose) < 2:
            stubs.append(f"{name} ({len(prose)} non-heading, non-bullet line(s))")

    assert not stubs, (
        "these family landing pages are link skeletons -- a heading and a list, with no "
        f"orientation for the reader: {stubs}"
    )


def test_every_family_page_offers_a_way_back_to_the_index(rendered_pages: dict[str, str]) -> None:
    """A landing page that cannot be left is a dead end in a navigable reference."""
    orphans = [
        name
        for name in sorted(rendered_pages)
        if _FAMILY_PAGE.match(name) and "/cli/index" not in rendered_pages[name]
    ]
    assert not orphans, f"these family pages never link back to the CLI reference index: {orphans}"
