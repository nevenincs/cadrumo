"""The casilla reference deep-link scheme, shared by generator and search.

The casilla reference generator (``dev/docs/casilla_reference.py``) renders one
page per modelo under ``docs/_generated/casillas/<modelo>.rst`` and gives every
casilla an explicit HTML anchor. A search record that deep-links a casilla to
its entry must target that exact page and anchor, or the palette card lands on
the page top (or, as before this scheme, on a search-for-itself query string).

This module is the single derivation authority both sides consume: the
generator emits the anchor id from :func:`casilla_page_anchor`, and
``_from_casilla`` (the search-record funnel) builds its target from
:func:`casilla_reference_target`. Because both read the same slug function, the
card and the landing page can never disagree on where a casilla lives - the
docs-side instance of the one-aggregation-path discipline (the CLI-target break
was exactly a destination hardcoded away from its renderer).

Casilla ids carry characters an HTML id cannot (``DP200014:00562``,
``decl.ejercicio``, ``contraparte.clave-operacion``), so the slug folds every
run of non-``[a-z0-9]`` characters to a single hyphen and lowercases. The
generator emits the id verbatim through a raw-HTML anchor span (never a Sphinx
label - casilla ids are unique per modelo but repeat ACROSS modelos, so a
global ``.. _name:`` target would collide), so this slug is the rendered id with
no docutils re-normalisation. A post-slug collision WITHIN one modelo page is a
generator build failure, never a silent merge.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Final

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.modelo import Modelo

__all__ = [
    "CASILLA_REFERENCE_DIR",
    "casilla_page_anchor",
    "casilla_page_relpath",
    "casilla_reference_page",
    "casilla_reference_target",
]

#: The generated casilla reference directory, relative to the docs root. Each
#: modelo renders one ``<modelo>.rst`` page here plus an ``index.rst`` toctree.
#: Uncommitted and regenerated every build, like ``docs/_generated/glossary.rst``.
CASILLA_REFERENCE_DIR: Final[str] = "_generated/casillas"

_ANCHOR_PREFIX: Final[str] = "casilla-"


def _slug(casilla_id: str) -> str:
    """Fold a casilla id to a lowercase ``[a-z0-9-]`` HTML-id-safe slug."""
    decomposed = unicodedata.normalize("NFKD", casilla_id)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    segments: list[str] = []
    current: list[str] = []
    for ch in ascii_text:
        if ch.isascii() and ch.isalnum():
            current.append(ch.lower())
        elif current:
            segments.append("".join(current))
            current = []
    if current:
        segments.append("".join(current))
    return "-".join(segments)


def casilla_page_anchor(modelo: Modelo | str, casilla_id: CasillaId | str) -> str:
    """Return the HTML anchor id for one casilla on its modelo reference page.

    Args:
        modelo: The owning modelo (only its identity scopes uniqueness; the id
            is page-local, so the anchor carries no modelo segment).
        casilla_id: The canonical registry ``casilla.id``.

    Returns:
        The ``casilla-...`` fragment id the generator stamps on the entry and
        a deep link targets after the ``#``.

    Raises:
        ValueError: If the casilla id folds to an empty slug (no id character
            survives) - an anchor-less entry the generator must never emit.
    """
    slug = _slug(str(casilla_id))
    if not slug:
        raise ValueError(f"casilla id {casilla_id!r} folds to an empty anchor slug")
    return _ANCHOR_PREFIX + slug


def casilla_page_relpath(modelo: Modelo | str) -> Path:
    """Return the generated RST page path for a modelo, relative to the docs root."""
    value = modelo.value if isinstance(modelo, Modelo) else str(modelo)
    return Path(CASILLA_REFERENCE_DIR) / f"{value}.rst"


def casilla_reference_page(modelo: Modelo | str) -> str:
    """Return the built page URL for a modelo (``_generated/casillas/<modelo>.html``)."""
    value = modelo.value if isinstance(modelo, Modelo) else str(modelo)
    return f"{CASILLA_REFERENCE_DIR}/{value}.html"


def casilla_reference_target(modelo: Modelo | str, casilla_id: CasillaId | str) -> str:
    """Return the full page+anchor deep-link target for one casilla.

    The single form consumed by ``_from_casilla`` and the committed relevance
    rewrite: ``_generated/casillas/<modelo>.html#casilla-<slug>``.
    """
    return f"{casilla_reference_page(modelo)}#{casilla_page_anchor(modelo, casilla_id)}"
