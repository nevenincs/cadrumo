"""Project authored legal provisions into casilla-card citations and links."""

from __future__ import annotations

import html
import posixpath
import re
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Final

from ._locale_chrome import docs_chrome
from .casilla_display import _LEGAL_INSTRUMENT_NAMES, _humanise_token
from .legal_catalogue import load_legal_provisions
from .legal_reference_routing import legal_reference_target
from .terminology.casilla_anchor import CASILLA_REFERENCE_DIR

if TYPE_CHECKING:
    from cadrumo.core.external_constants import OutputLanguage

    from .legal_reference_models import LegalProvisionRecord


@dataclass(frozen=True)
class _LegalLink:
    """One catalogue provision projected for display on a casilla card."""

    #: Human reading of the whole provision ("Ley 37/1992, art. 92").
    label: str
    #: The instrument alone ("Ley 37/1992"), so sibling provisions group under it.
    instrument: str
    #: The provision within that instrument ("art. 92"), or empty for a law-level row.
    provision: str
    #: Site-relative target of the generated legal-reference destination.
    target: str


#: Id tokens that merely restate the authored ``kind`` and are dropped from the
#: display so ``ley-37-1992`` reads "Ley 37/1992", not "Ley ley 37/1992".
_LEGAL_KIND_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "acuerdo",
        "convenio",
        "decreto",
        "dl",
        "instruccion",
        "ley",
        "orden",
        "rd",
        "rdl",
        "rdleg",
        "real",
        "refundido",
        "reglamento",
        "resolucion",
        "texto",
        "trlirnr",
        "trlirpf",
        "trlis",
    },
)


_YEAR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^(19|20)\d{2}$")


# ── Legal provision display ──────────────────────────────────────────────────


def _legal_numeral(tokens: list[str]) -> tuple[str | None, list[str]]:
    """Split a trailing ``<number>-<year>`` pair off a document-id token run."""
    if len(tokens) >= 2 and _YEAR_PATTERN.match(tokens[-1]) and tokens[-2].isdigit():
        return f"{tokens[-2]}/{tokens[-1]}", tokens[:-2]
    return None, tokens


def _legal_provision_display(
    legal_id: str,
    provision: LegalProvisionRecord,
    language: OutputLanguage,
) -> tuple[str, str]:
    """Split one catalogue provision into ``(instrument, provision)`` for display.

    Built only from authored fields (``kind``, ``article``, ``section``) and the
    document half of the catalogue id, which encodes the instrument's number and
    year. An id whose shape yields nothing falls back to the raw id, so the
    display never invents a citation it cannot derive.
    """
    name, provision_part = _legal_instrument_display(legal_id, provision, language)
    if not name:
        return legal_id, ""

    # The authored ``section`` prose is the most human reading of a provision;
    # ``article`` is next (numeric articles take the ``art.`` prefix, worded
    # ones already read as prose); the id's own provision half is the floor.
    if provision.section:
        return name, provision.section
    if provision.article:
        prefix = "art. " if provision.article[:1].isdigit() else ""
        return name, f"{prefix}{provision.article}"
    if provision_part:
        return name, provision_part.replace("-", " ")
    return name, ""


@lru_cache(maxsize=8)
def _legal_links(repo_root: Path, language: OutputLanguage) -> dict[str, _LegalLink]:
    """Map every catalogue provision id to its display name and generated destination.

    The destination is the generated legal-reference page the sibling generator
    writes, derived through that module's own target helper, so a casilla's
    grounding lands on the in-site provision entry rather than dumping a raw
    token or bouncing the reader straight out to BOE.
    """
    links: dict[str, _LegalLink] = {}
    for provision in load_legal_provisions(repo_root):
        target = legal_reference_target(
            provision.document_id,
            provision.legal_id,
            article=provision.article,
            section=provision.section,
            corpus_ref=provision.corpus_ref,
            permalink=provision.permalink,
        )
        instrument, within = _legal_provision_display(provision.legal_id, provision, language)
        links[provision.legal_id] = _LegalLink(
            label=f"{instrument}, {within}" if within else instrument,
            instrument=instrument,
            provision=within,
            target=_relative_to_casilla_page(target),
        )
    return links


def _relative_to_casilla_page(site_target: str) -> str:
    """Rewrite a site-relative target as a link relative to a casilla page."""
    page, _, fragment = site_target.partition("#")
    relative = posixpath.relpath(page, CASILLA_REFERENCE_DIR)
    return f"{relative}#{fragment}" if fragment else relative


def _legal_list(refs: tuple[str, ...], links: dict[str, _LegalLink], label: str) -> tuple[list[str], int]:
    """Render the legal basis grouped by instrument, returning lines and link count.

    Four refs into one norm used to print that norm's name four times, which is
    what made the grounding compete with the answer above it. Grouping states
    the instrument once and lists its provisions after it, so the block reads as
    one citation rather than as a row of equally-weighted tags.
    """
    grouped: OrderedDict[str, list[str]] = OrderedDict()
    resolved = 0
    for ref in refs:
        link = links.get(ref)
        if link is None:
            grouped.setdefault("", []).append(
                f'<span class="casilla-legal-ref casilla-legal-ref--raw">{html.escape(ref)}</span>',
            )
            continue
        resolved += 1
        anchor = (
            f'<a class="casilla-legal-ref" href="{html.escape(link.target, quote=True)}"'
            f' title="{html.escape(ref, quote=True)}">{html.escape(link.provision or link.instrument)}</a>'
        )
        grouped.setdefault(link.instrument, []).append(anchor)

    items: list[str] = []
    for instrument, anchors in grouped.items():
        name = f'<span class="casilla-legal-name">{html.escape(instrument)}</span> ' if instrument else ""
        items.append(f"<li>{name}{', '.join(anchors)}</li>")
    lines = [
        '<div class="casilla-card__legal">',
        f'<span class="casilla-card__legal-label">{html.escape(label)}</span>',
        '<ul class="casilla-card__legal-list">',
        *items,
        "</ul>",
        "</div>",
    ]
    return lines, resolved


def _legal_id_parts(legal_id: str) -> tuple[str | None, str, str, str]:
    document_part, _, provision_part = legal_id.partition(":")
    tokens = [token for token in document_part.split("-") if token]
    numeral, remainder = _legal_numeral(tokens)
    remainder = [token for token in remainder if token.lower() not in _LEGAL_KIND_TOKENS]
    separator = "/" if numeral else "-"
    qualifier = separator.join(token.upper() if len(token) <= 4 else _humanise_token(token) for token in remainder)

    return numeral, qualifier, separator, provision_part


def _legal_instrument_display(
    legal_id: str, provision: LegalProvisionRecord, language: OutputLanguage
) -> tuple[str, str]:
    numeral, qualifier, separator, provision_part = _legal_id_parts(legal_id)
    instrument = _LEGAL_INSTRUMENT_NAMES.get(provision.kind)
    kind_display = (
        instrument if instrument is not None else docs_chrome(f"docs.casilla.legal_kind.{provision.kind}", language)
    )
    name = " ".join(part for part in (kind_display, qualifier) if part)
    if numeral:
        name = f"{name}{separator if qualifier else ' '}{numeral}"
    name = name.strip()
    return name, provision_part
