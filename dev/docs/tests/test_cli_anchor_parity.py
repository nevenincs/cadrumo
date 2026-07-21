"""CLI deep-link anchor parity for the search projection.

Every projected CLI search record (one per leaf command, one per option) deep
-links into the generated CLI reference by a ``<page>.html#<anchor>`` target. The
CLI reference is organised into per-family landing pages (``cli/app.html``,
``cli/config.html``) and per-verb-group pages (``cli/app/ledger.html``); a
grouped command's section renders on its group page, a leaf mounted directly on
a family renders on that family's landing page. A target that names the wrong
page lands the operator on a bare landing page with a fragment matching nothing
-- the exact defect that once stranded 300+ shipped records after the reference
was restructured into per-group pages while the target builder kept pointing at
``cli/<family>.html``.

This gate proves resolution against the actually-rendered pages, not a string
shape (a shape assertion was green while the links were dead):
:func:`test_every_cli_record_target_resolves` renders the CLI reference, builds
each page's real anchor set from its rendered headings via
``docutils.nodes.make_id`` (Sphinx's own slugger), and asserts every record's
target page exists AND its fragment is a real anchor on that page.
:func:`test_direct_child_config_leaves_resolve_on_family_page` locks the
family-page/group-page asymmetry so the direct-child ``config`` leaves keep
resolving on ``cli/config.html``.

No mocks: the CLI reference is really rendered (one subprocess) and the records
are really projected from the live command tree (four language subprocesses).
The anchor oracle (``make_id``) is independent of the emitter's slug code, so
the fragment half is non-tautological; the page half is proven by the section
genuinely rendering on the named page.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from docutils.nodes import make_id

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

#: An RST section underline is a line of one repeated adornment character. The
#: CLI reference uses the standard docutils set (``= - ^ ~ " '``).
_UNDERLINE_RE = re.compile(r"""^([=\-^~"'])\1*$""")


def _page_anchor_set(rst: str) -> set[str]:
    """Return the section-id set Sphinx will generate for a rendered CLI page.

    A section heading is a non-empty text line immediately followed by an
    adornment underline at least as long as the text. Sphinx slugs the heading
    node's plain text (RST inline markup such as the ``\\`\\``-literal backticks
    the command headings use is stripped to its text) via
    ``docutils.nodes.make_id``, so stripping the backtick characters from the
    raw heading line and slugging the remainder reproduces the live anchor.
    """
    anchors: set[str] = set()
    lines = rst.splitlines()
    for index in range(len(lines) - 1):
        text = lines[index]
        underline = lines[index + 1]
        if not text.strip():
            continue
        if _UNDERLINE_RE.match(text):
            continue  # the text line is itself an adornment (over-line, etc.)
        if _UNDERLINE_RE.match(underline) and len(underline) >= len(text.rstrip()):
            title = text.replace("``", "").strip()
            anchor = make_id(title)
            if anchor:
                anchors.add(anchor)
    return anchors


def _render_cli_reference(tmp_path: Path) -> dict[str, str]:
    """Render every CLI-reference RST page in one clean subprocess."""
    from dev.docs.cli_reference import generate_cli_reference_in_subprocess

    return generate_cli_reference_in_subprocess(tmp_path)


def _anchor_sets_by_page(rendered: dict[str, str]) -> dict[str, set[str]]:
    """Map each rendered ``cli/....rst`` page to its live section-id set."""
    return {rel_path: _page_anchor_set(rst) for rel_path, rst in rendered.items()}


def test_every_cli_record_target_resolves(tmp_path: Path) -> None:
    """Every CLI command and option record deep-links to a real page+anchor.

    Renders the CLI reference, derives each page's real anchor set from its
    rendered headings, projects the live CLI search records, and asserts for
    every record that (1) the target page was actually rendered and (2) the
    target fragment is a real section id on that page. A record whose page or
    fragment does not resolve is a dead deep link and fails loudly.
    """
    from dev.docs.terminology._cli_projection import project_cli_search_records

    rendered = _render_cli_reference(tmp_path)
    assert rendered, "CLI reference rendered no pages"
    anchors_by_page = _anchor_sets_by_page(rendered)

    commands, options, _stats = project_cli_search_records()
    assert commands, "projection produced no command records"
    assert options, "projection produced no option records"

    dead: list[str] = []
    resolved = 0
    for record in (*commands, *options):
        page_html, _, fragment = record.target.partition("#")
        rst_key = page_html.removesuffix(".html") + ".rst"
        if rst_key not in rendered:
            dead.append(f"{record.command_path}: page {page_html!r} was not rendered (target {record.target!r})")
            continue
        if fragment not in anchors_by_page[rst_key]:
            dead.append(f"{record.command_path}: fragment #{fragment} not on page {page_html!r}")
            continue
        resolved += 1

    assert not dead, "CLI records with dead deep links:\n  " + "\n  ".join(dead)
    # Guard against a silent empty pass: the projection carries hundreds of
    # records, so a near-zero resolved count means the oracle or projection
    # collapsed rather than everything genuinely resolving.
    assert resolved == len(commands) + len(options)
    assert resolved > 200, f"expected the full CLI surface (200+ records); only {resolved} resolved"


def test_direct_child_config_leaves_resolve_on_family_page(tmp_path: Path) -> None:
    """The direct-child ``config`` leaves resolve on ``cli/config.html``.

    ``aeat config`` mounts several leaf commands (``lock``, ``switch``,
    ``rekey``, ...) directly on the family with no intervening verb group, so
    they render on the family landing page rather than a group page. This locks
    that asymmetry: it is the case a naive "everything is on a group page" fix
    would break, and the case a naive "everything is on the family page" builder
    got right only for these leaves while breaking every grouped command.
    """
    from dev.docs.terminology._cli_projection import project_cli_search_records

    rendered = _render_cli_reference(tmp_path)
    config_family_rst = "cli/config.rst"
    assert config_family_rst in rendered, "config family landing page was not rendered"
    config_family_anchors = _page_anchor_set(rendered[config_family_rst])

    commands, _options, _stats = project_cli_search_records()
    direct_leaves = [
        record for record in commands if record.family == "config" and len(record.command_path.split(" ")) == 3
    ]
    assert direct_leaves, "expected direct-child config leaf commands in the projection"

    for record in direct_leaves:
        assert record.target.startswith("cli/config.html#"), (
            f"{record.command_path}: direct-child config leaf must target the family landing page, "
            f"got {record.target!r}"
        )
        fragment = record.target.partition("#")[2]
        assert fragment in config_family_anchors, f"{record.command_path}: fragment #{fragment} not on cli/config.html"
