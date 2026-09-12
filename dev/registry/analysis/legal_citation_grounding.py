"""Screen: does every required_text quote occur in the excerpt it cites?

``required_text`` exists so a reader can confirm the registry's legal claim
against the source it names. A quote that cannot be found in its own
``corpus_ref`` does not fail loudly -- nothing refuses, nothing warns -- so the
claim quietly rests on the author's word instead of the BOE's text.

Three defects produce that, and they are not equally dangerous:

``whitespace``  The quote spans a Unicode space the excerpt writes differently,
                usually U+00A0 between a word and a number ("modelo<nbsp>390").
                grep renders nbsp as a space, so a human checking by eye
                CONFIRMS the citation while a strict check finds nothing. This
                is the worst class precisely because it reads as verified.
                Whitespace is typography and carries no legal meaning, so the
                screen folds it on both sides and the authored quote stands.

``diacritic``  The quote drops accents the source carries ("articulos" for
                "artículos"). Orthography is not typography: the accented form
                is what the BOE published, so the QUOTE is wrong and gets
                re-quoted. This screen never folds accents -- doing so would
                accept a quote that does not exist.

``absent``     The text is nowhere in the cited excerpt under either folding.
                Either the citation names the wrong article, or the claim is
                not grounded by the document it points at. Needs a person.

The screen reads authored TOML directly and never imports the domain, so it
keeps reporting when the registry does not load. It exits 0 whatever it finds.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_DATA: Final = Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "_data"
_LEGAL: Final = _DATA / "registry" / "aeat" / "legal"

CITATION_CLASSES: Final[tuple[str, ...]] = ("whitespace", "diacritic", "absent")


@dataclass(frozen=True, slots=True)
class Finding:
    """One quote that does not occur verbatim in the excerpt it cites."""

    catalogue: str
    legal_id: str
    kind: str
    quote: str


def _fold_space(value: str) -> str:
    """Collapse every Unicode whitespace run to one space; NFC, nothing more."""
    return " ".join(unicodedata.normalize("NFC", value).split())


def _fold_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn")


def _excerpt_for(corpus_ref: str) -> Path | None:
    target = _DATA / corpus_ref.split("#", 1)[0]
    extracted = target.with_name(target.name + ".extracted.md")
    for candidate in (extracted, target):
        if candidate.is_file():
            return candidate
    return None


def scan() -> Iterator[Finding]:
    """Yield every citation whose quote is not verbatim in its cited excerpt."""
    cache: dict[Path, tuple[str, str, str]] = {}
    for catalogue in sorted(_LEGAL.glob("*.toml")):
        document = tomllib.loads(catalogue.read_text(encoding="utf-8"))
        for legal_id, entry in document.get("legal", {}).items():
            corpus_ref, quotes = entry.get("corpus_ref"), entry.get("required_text")
            if not corpus_ref or not quotes:
                continue
            excerpt = _excerpt_for(corpus_ref)
            if excerpt is None:
                continue
            if excerpt not in cache:
                text = excerpt.read_text(encoding="utf-8")
                spaced = _fold_space(text)
                cache[excerpt] = (text, spaced, _fold_accents(spaced))
            text, spaced, folded = cache[excerpt]
            for quote in quotes:
                if quote in text:
                    continue
                if _fold_space(quote) in spaced:
                    yield Finding(catalogue.name, legal_id, "whitespace", quote)
                elif _fold_accents(_fold_space(quote)) in folded:
                    yield Finding(catalogue.name, legal_id, "diacritic", quote)
                else:
                    yield Finding(catalogue.name, legal_id, "absent", quote)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--findings", action="store_true")
    args = parser.parse_args(argv)

    findings = tuple(scan())
    counts = {kind: sum(1 for f in findings if f.kind == kind) for kind in CITATION_CLASSES}

    if args.json:
        print(json.dumps({"counts": counts, "findings": [f.__dict__ for f in findings]}, indent=2))
        return 0

    print("# legal_citation_grounding schema=1")
    print(f"citations ungrounded={len(findings)} " + " ".join(f"{k}={v}" for k, v in counts.items()))
    if args.findings:
        for finding in sorted(findings, key=lambda f: (f.kind, f.catalogue, f.legal_id)):
            print(f"  {finding.kind} {finding.catalogue} {finding.legal_id}: {finding.quote[:70]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
