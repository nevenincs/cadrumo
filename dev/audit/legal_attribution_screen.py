"""Screen legal citations for a provision that approves a DIFFERENT modelo.

The registry's evidence gate confirms a ``required_text`` phrase is PRESENT in
the cited corpus file. It has no notion of whether the provision BELONGS to the
modelo citing it, and that gap was not theoretical: four filing-grade citations
sat inside it when this screen was written. Modelos 187, 188 and 194 each cited
an article whose own text reads "Se aprueba el modelo 193", and 296 cited one
concerning "modelo 123". The evidence gate passed all four, correctly by its
own contract, because the phrase it checks genuinely is in the file.

Those four were corrected at MODELO level, and for a time this screen read zero
because modelo-level citations were all it looked at. Three of them survived at
REVISION level -- 187, 188 and 194 each citing the article approving 193 -- and
became visible only once the input was widened to both surfaces. Those three have
since been re-pointed at their own approving ordenes, so the worklist now reads
zero across both surfaces. The screen prints its current counts and freezes no
figure in this prose, so a reader is told what the catalogue says today rather
than what it said at authoring.

This is the same tautology the grounding rule warns about, one level up. There
the ``required_text`` was self-authored, so it validated internal consistency
rather than faithfulness to the BOE. Here the text is faithful and the
ATTRIBUTION is wrong, which no phrase check can catch.

The rule this applies: when an entry's ``required_text`` carries an approval
phrase AND names a modelo, that entry approves that modelo, and any other modelo
citing it is claiming a provision that is not about it.

Read the ``required_text`` entries JOINTLY, never phrase-by-phrase. Modelo 848's
approval phrase and its form number live in separate entries, so a per-phrase
rule demotes it wrongly -- a mistake made and corrected during the grounding
pass that produced this screen.

A SCREEN, not a gate. It was written as one because citations were known-wrong
and a gate would have landed red on every peer for a defect they did not
create; correcting them is legal-authority work, needing the right approving
orden located in the bundled corpus. That condition has since been met: the
worklist reads zero at both surfaces, and the ratchet now lives in
``tests/test_legal_attribution_gate.py``, which calls the functions below rather
than restating their rule. This module keeps its exit-0 reporting contract for
interactive use -- enforcement is the gate's job, reporting is this one's.

MEASURED LIMIT, and the widening that was rejected. This screen catches the
APPROVAL shape only, and there is a real mis-attribution it does not see: modelo
296 cites ``orden-hac-56-2024:art-1``, whose text reads "El anexo II, modelo 123
/ se sustituye por el anexo I de esta orden". That provision AMENDS modelo 123's
annex; it approves nothing, so no approval phrase is present and this screen
correctly skips it under its own rule.

The obvious widening -- flag any entry naming exactly ONE modelo when a different
modelo cites it -- was implemented and measured before being rejected. It returns
11 hits, and several are legitimate: 353 citing an article that names 322 is the
IVA grupos pair, 220 citing one that names 200 is the IS pair, and a
``disposición final única`` routinely amends several forms while ``required_text``
quotes the clause of only one. A provision can bind form A while quoting form B,
so "names one modelo" is not evidence of ownership.

An approving article, by contrast, is definitively about the form it approves,
which is why the narrow rule holds and the wide one does not. Catching the
amending shape needs a signal that distinguishes "this provision governs form X"
from "this provision mentions form X", and this screen does not have one. Left as
a stated gap rather than paid for with a worklist that is half noise -- a
worklist nobody trusts gets read by nobody.

Run as ``python -m dev.audit.legal_attribution_screen``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final, NamedTuple

from .._paths import REPO_ROOT
from .legal_catalogue import load_legal_entries, required_text_by_entry

#: Registry authoring tree, relative to the repository root, matching the
#: convention the catalogue loader beside this module already uses.
REGISTRY_DIR: Final = Path("src/cadrumo/_data/registry/aeat")

#: Phrases a Spanish approving provision uses. Matched accent-insensitively
#: against a folded copy, because the corpus and the catalogue disagree on
#: accents often enough that an accent-exact match silently misses entries.
_APPROVAL_PHRASES: Final = ("aprueba el modelo", "aprobacion del modelo", "se aprueban los modelos")

#: Matches the form number AND any further numbers listed after it, because a
#: single article routinely approves a family: "se aprueban los modelos 123 y
#: 124". Capturing only the first number made the second look mis-attributed --
#: caught by this screen's own multi-form test before it ever ran on real data.
_MODELO_NUMBER_LIST: Final = re.compile(r"\bmodelos?\s+(\d{3}(?:\s*(?:,|y)\s*\d{3})*)", re.IGNORECASE)
_THREE_DIGITS: Final = re.compile(r"\d{3}")
_FOLD: Final = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")


def fold(text: str) -> str:
    """Return ``text`` accent-folded and lowercased for tolerant matching."""
    return text.translate(_FOLD).lower()


def approved_modelo_numbers(required_text: tuple[str, ...]) -> frozenset[str]:
    """Return the modelo numbers an entry's ``required_text`` says it approves.

    Empty when the entry carries no approval phrase at all, which is the common
    case: most cited provisions are framework articles that establish an
    obligation without approving a form, and those make no attribution claim to
    check.

    The whole list is read as one body of text. An approval phrase in one entry
    and the form number in another still pair, because that is how modelo 848 is
    recorded and a per-phrase reading demotes it wrongly.

    Args:
        required_text: The entry's declared phrases, in file order.

    Returns:
        Every three-digit modelo number the approving text names.
    """
    joined = fold(" ".join(required_text))
    if not any(phrase in joined for phrase in _APPROVAL_PHRASES):
        return frozenset()
    return frozenset(
        number for listed in _MODELO_NUMBER_LIST.findall(joined) for number in _THREE_DIGITS.findall(listed)
    )


class Mismatch(NamedTuple):
    """One modelo citing a provision that approves a different form."""

    modelo: str
    entry_id: str
    approves: tuple[str, ...]

    def render(self) -> str:
        """Return the finding as one operator-readable line."""
        approved = ", ".join(self.approves)
        return f"modelo {self.modelo} cites {self.entry_id}, whose approving text names modelo {approved}"


def find_mismatches(
    modelo_refs: dict[str, tuple[str, ...]],
    entries: dict[str, tuple[str, ...]],
) -> list[Mismatch]:
    """Return every citation whose approving provision names another modelo.

    Args:
        modelo_refs: Modelo code mapped to the legal entry ids it cites.
        entries: Legal entry id mapped to its ``required_text`` phrases.

    Returns:
        One entry per mis-attributed citation, sorted for stable output.
    """
    found: list[Mismatch] = []
    for modelo, refs in sorted(modelo_refs.items()):
        for entry_id in refs:
            approves = approved_modelo_numbers(entries.get(entry_id, ()))
            if approves and modelo not in approves:
                found.append(Mismatch(modelo, entry_id, tuple(sorted(approves))))
    return found


def _modelo_refs_from_registry() -> dict[str, tuple[str, ...]]:
    """Return every citation each registry modelo makes, at both levels.

    Reads BOTH the modelo definition's own ``legal_refs`` and those of each of
    its revisions. A revision-level citation makes exactly the same attribution
    claim as a modelo-level one, and reading only the modelo level left three
    mis-attributions standing after the modelo-level ones were corrected:
    modelos 187, 188 and 194 each cite an article whose approving text names
    modelo 193, at revision level, where this screen had never looked. The
    worklist read zero and was telling the truth about the surface it read.

    Loads through the raw compiler rather than the validated authority. The
    authority applies registry-wide business-rule validation, so any unrelated
    refusal anywhere in the tree makes it raise -- and this screen then cannot
    run at all, precisely when authoring activity is heaviest and a
    mis-attribution is most likely to be introduced. A screen that reads
    citations does not need the tree to be valid; it needs the tree to be
    readable. The catalogue side of this screen already reads authored TOML
    directly for the same reason.

    The population is every modelo the registry actually defines, taken from the
    tree itself. No skip list is consulted, because a modelo absent from the
    registry is absent from the walk rather than something to except.
    """
    from cadrumo.domain.calculations.registry import load_registry_tree

    modelos, _catalogues = load_registry_tree(REPO_ROOT / REGISTRY_DIR)
    refs: dict[str, tuple[str, ...]] = {}
    for definition in modelos:
        cited: set[str] = {str(ref) for ref in (getattr(definition, "legal_refs", ()) or ())}
        for revision in definition.revisions.values():
            cited.update(str(ref) for ref in (getattr(revision, "legal_refs", ()) or ()))
        refs[definition.id] = tuple(sorted(cited))
    return refs


def main() -> int:
    """Print the worklist.

    Exits 0 whatever the worklist says: this reports and does not gate, because
    the mis-attributions are known-present and correcting them is legal
    authority work.

    It does REFUSE, non-zero, when its own inputs cannot support a result -- a
    missing catalogue or an empty read. Either would print an empty worklist,
    which is indistinguishable from a clean one. "Always exits 0" described the
    worklist and read as a promise about the process.
    """
    root = REPO_ROOT
    entries = required_text_by_entry(load_legal_entries(root))
    if not entries:
        raise SystemExit("read zero legal entries; the result would be meaningless")

    approving = {k: v for k, v in entries.items() if approved_modelo_numbers(v)}
    mismatches = find_mismatches(_modelo_refs_from_registry(), entries)

    print(f"legal entries read: {len(entries)}; of those, approving a named modelo: {len(approving)}")
    print(f"citations whose approving provision names a DIFFERENT modelo: {len(mismatches)}\n")
    for mismatch in mismatches:
        print(f"  {mismatch.render()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
