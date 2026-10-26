"""The one place this package names an HTML parser backend.

Every AEAT page read -- sede status readers, the representation gate, the
cotejo viewer probe, the Clave page flows -- builds its document through
:func:`parse_html`, so the backend is one decision rather than one per call
site. BeautifulSoup raises ``FeatureNotFound`` rather than falling back when a
named backend is absent, which makes the choice a live-failure axis the moment
the dependency picture shifts: scattered across call sites, that failure
arrives at whichever page a taxpayer happened to read first.

The backend is ``lxml``, and the reasons are measured rather than preferred.
``pyproject.toml`` declares ``beautifulsoup4[lxml]`` as a direct dependency
precisely because this package names the backend, so moving to the stdlib
parser would silently invalidate a declaration the packaging smoke test also
asserts. lxml is the more forgiving parser for the legacy markup AEAT actually
serves. And parsing all 75 bundled AEAT-origin pages under both backends and
comparing the structural signals these readers consume -- table, row, cell,
anchor, href, heading, input, form, select, option, span and div counts, plus
extracted text length -- diverged on none of them, so the standardisation
costs nothing observable to a reader.

Callers pass markup and nothing else. Refusal stays with the caller: each read
path raises its own typed error with its own operator-facing message, and a
constructor that guessed at one would flatten that back into a generic parse
failure.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

_PARSER_BACKEND = "lxml"


def parse_html(markup: str) -> BeautifulSoup:
    """Parse *markup* into a document tree using this package's parser backend.

    Args:
        markup: Raw HTML body of an AEAT page.

    Returns:
        The parsed :class:`~bs4.BeautifulSoup` document.

    Raises:
        bs4.FeatureNotFound: When the declared backend is not installed. That
            is a broken environment rather than a bad page, so it is left to
            propagate rather than folded into a per-caller parse error.
    """
    return BeautifulSoup(markup, _PARSER_BACKEND)


__all__ = ["parse_html"]
