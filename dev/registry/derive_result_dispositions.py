"""Derive each revision's result disposition from its own diseño de registro.

The AEAT fichero-BOE "Tipo de declaración" field encodes what a filing's final
figure means. Which letter a NEGATIVE result maps to is fixed per modelo by that
modelo's own diseño, and the diseño states the admissible letters verbatim:
Modelo 303 lists ``C (solicitud de compensación)``, Modelo 130 lists
``B (resultado a deducir)`` and no C, Modelo 111 lists neither.

So the mapping is read out of the corpus rather than transcribed. The rule is
the letters' own precedence -- a modelo that admits C disposes a negative result
as C, one that admits B disposes it as B, one that admits D disposes it as D,
and one that admits none of the three has only N to fall back to.

**A modelo whose diseño never mentions the field has no result disposition at
all.** Fifteen do: the informative declarations (190, 193, 347, 349, 720, 184,
180 and their siblings) report holdings or third-party operations and settle no
cuota, so there is no result to dispose of. Their absence is measured across
their real corpus files rather than inferred from a failed match, and it is what
makes ``not applicable`` an honest declaration for them rather than a shrug.

The derivation is proved against the nine mappings the hand-authored table in
``core`` already carries: it must reproduce all nine independently, or it is not
reading what that table read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..quality.unread_inputs import report_unread

REPO_ROOT = Path(__file__).resolve().parents[2]
DISENOS_ROOT = REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus" / "aeat_official" / "disenos_registro"

#: Anchor without the accented character: the bundled corpus carries several
#: encodings, and matching on the ASCII tail finds the note in all of them.
_FIELD_ANCHOR = "ipo de declaraci"

#: Letters admissible as a NEGATIVE result's disposition, most specific first.
#: A modelo admitting C disposes a negative result as a solicitud de
#: compensacion; failing that B (resultado a deducir), failing that D (solicitud
#: de devolucion). N is the floor: every modelo carrying the field admits it.
_NEGATIVE_PRECEDENCE: tuple[str, ...] = ("C", "B", "D")

_ZERO_DISPOSITION = "N"
_CODE_IN_NOTE = re.compile(r"\b([A-Z])\s*\(")
_TEXT_SUFFIXES = frozenset({".txt", ".md", ".json", ".html"})


@dataclass(frozen=True, slots=True)
class DisenoDispositionEvidence:
    """What one modelo's diseno says about its Tipo de declaracion field."""

    modelo: str
    codes: frozenset[str]
    note: str
    corpus_files_scanned: int

    @property
    def declares_the_field(self) -> bool:
        """Whether the diseno carries a Tipo de declaracion field at all."""
        return bool(self.codes)

    @property
    def negative_disposition(self) -> str | None:
        """Return the letter a negative result maps to, or ``None`` when absent."""
        if not self.declares_the_field:
            return None
        for letter in _NEGATIVE_PRECEDENCE:
            if letter in self.codes:
                return letter
        return _ZERO_DISPOSITION

    @property
    def zero_disposition(self) -> str | None:
        """Return the letter a zero result maps to, or ``None`` when absent."""
        return _ZERO_DISPOSITION if self.declares_the_field else None


def read_diseno_evidence(modelo_id: str, root: Path | None = None) -> DisenoDispositionEvidence:
    """Read one modelo's Tipo de declaracion note out of the bundled corpus.

    Args:
        modelo_id: The modelo whose diseno directory to scan.
        root: Corpus root override, used by the proofs.

    Returns:
        The evidence, carrying an empty code set when the diseno never mentions
        the field. The scanned-file count travels with it so a zero can be told
        apart from a directory that was not there.
    """
    base = (root if root is not None else DISENOS_ROOT) / f"modelo_{modelo_id}"
    if not base.is_dir():
        return DisenoDispositionEvidence(modelo=modelo_id, codes=frozenset(), note="", corpus_files_scanned=0)
    scanned = 0
    unread: list[str] = []
    best = ""
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in _TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            # ``corpus_files_scanned`` exists so a zero can be told apart from a
            # directory that was not there, and counting a file before reading it
            # inflated exactly that denominator with files never examined. The
            # lenient decode was the other half: a replaced byte can break the
            # field anchor or the code pattern, losing evidence with no sign.
            unread.append(f"{path}: {type(error).__name__}: {error}")
            continue
        scanned += 1
        cursor = 0
        while True:
            cursor = text.find(_FIELD_ANCHOR, cursor)
            if cursor < 0:
                break
            candidate = " ".join(text[cursor : cursor + 320].split())
            cursor += len(_FIELD_ANCHOR)
            if _CODE_IN_NOTE.search(candidate) and len(candidate) > len(best):
                best = candidate
    report_unread(
        "diseno disposition evidence",
        "evidence in one of them is absent and the scanned count would have over-stated the corpus",
        unread,
    )
    return DisenoDispositionEvidence(
        modelo=modelo_id,
        codes=frozenset(_CODE_IN_NOTE.findall(best)),
        note=best,
        corpus_files_scanned=scanned,
    )


def core_table_expectations() -> dict[str, str]:
    """Return the hand-authored negative dispositions this derivation must reproduce."""
    import cadrumo.core.result_disposition as table

    return {str(modelo): spec.negative.value.upper() for modelo, spec in table._DISPOSITION_SPEC.items()}


def derivation_disagreements(root: Path | None = None) -> tuple[str, ...]:
    """Return one line per modelo where the derivation and the core table differ.

    Empty means the corpus independently reproduces every mapping the table
    asserts, which is the only evidence that this module reads what that table
    read rather than something that merely looks similar.
    """
    lines: list[str] = []
    for modelo, expected in sorted(core_table_expectations().items()):
        evidence = read_diseno_evidence(modelo, root)
        derived = evidence.negative_disposition
        if derived != expected:
            lines.append(
                f"modelo {modelo}: diseno admits {sorted(evidence.codes)} so a negative result derives "
                f"as {derived!r}, but the core table asserts {expected!r}",
            )
    return tuple(lines)


__all__ = [
    "DISENOS_ROOT",
    "DisenoDispositionEvidence",
    "core_table_expectations",
    "derivation_disagreements",
    "read_diseno_evidence",
]
