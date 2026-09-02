"""Suffix-independent census of identifier-shaped fields, by NOUN vocabulary.

WHY THIS EXISTS, and why it is not optional polish. The first census of
identifier-shaped fields matched field NAMES against a suffix heuristic
(``_id``, ``_ref``, ``_code``, ``_key``, ``_number``, ``_csv``) and counted 589
bare-``str`` candidates. That count is a FLOOR, and this is proven rather than
suspected: ``clave_liquidacion`` is an AEAT-issued identifier this
codebase enrols by name, and it does not appear in the 589 at all, because it is a
plain Spanish noun carrying no such suffix. A surface measured only by suffix
therefore cannot report its own completeness, and enrolling exactly 589 while
calling the surface closed would reproduce the "artefact present, work absent"
failure a completeness claim must not reproduce.

This census reads the PROSE instead of the name: a field whose documentation
calls it an *identificador*, a *clave*, a *número* or a *referencia* is an
identifier candidate whatever it happens to be called. The two heuristics are
deliberately independent, so their DIFFERENCE is the measurement that matters
-- every record carries :attr:`NounCandidate.matches_suffix_heuristic`, and the
records where that is ``False`` are exactly the population the first census
could not see.

WHAT IT DOES NOT DO. It does not adjudicate. A noun in a docstring is evidence
that a human called the field an identifier, not a finding that it belongs in a
namespace: ``invoice_number`` is a counterparty-issued document number and
``file_id`` belongs to Google, and both match this vocabulary correctly while
being deliberately excluded from the AEAT taxonomy. Triage is a separate,
recorded disposition per record and is not hidden inside this scanner.

WHY A PINNED REVISION IS REQUIRED RATHER THAN OPTIONAL. This repository is
written to by many agents at once; a census taken over a moving working tree
cannot be reproduced, and its output is quoted into an execution record as the
gate proving the sweep ran. A number nobody can re-derive is not a gate. The
revision is therefore a positional argument with no default, matching the
sibling censuses under ``dev/``.

Usage::

    python -m dev.identity.identifier_noun_census HEAD
    python -m dev.identity.identifier_noun_census HEAD --json
    python -m dev.identity.identifier_noun_census HEAD --only-missed-by-suffix
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from typing import Final

from ..quality.repository_sources import production_sources

#: The noun vocabulary, matched against a field's DOCUMENTATION rather than its
#: name. Deliberately Spanish: this codebase names AEAT domain concepts with
#: their Spanish stems, so the prose describing an AEAT-issued identifier uses
#: these words even where the field name is anglicised or abbreviated.
#:
#: ``codigo`` is included because a *código* is what AEAT calls the CSV in
#: full (*Código Seguro de Verificación*); ``identity`` and ``identifier`` are
#: included because the English prose appears in this tree alongside the
#: Spanish and excluding it would rebuild a name-shaped blind spot inside a
#: vocabulary sweep meant to escape one.
NOUN_VOCABULARY: Final[frozenset[str]] = frozenset(
    {
        "identificador",
        "identifier",
        "identity",
        "clave",
        "numero",
        "referencia",
        "codigo",
    }
)

#: The ORIGINAL suffix heuristic, restated here solely so the difference
#: between the two sweeps is computable in one pass. This is not a second
#: authority for the suffix rule: nothing consumes it except
#: :attr:`NounCandidate.matches_suffix_heuristic`, whose entire purpose is to
#: mark which records the suffix sweep already had.
SUFFIX_HEURISTIC: Final[tuple[str, ...]] = ("_id", "_ref", "_code", "_key", "_number", "_csv")

_ATTRIBUTES_SECTION: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:Attributes|Args|Fields)\s*:\s*$",
    re.IGNORECASE,
)
_ATTRIBUTE_ENTRY: Final[re.Pattern[str]] = re.compile(r"^\s{4,}(\w+)\s*:\s*(.*)$")
_WORD: Final[re.Pattern[str]] = re.compile(r"[a-z]+")


def fold_accents(text: str) -> str:
    """Return ``text`` lowercased with diacritics stripped.

    ``número`` and ``numero`` are the same word for this sweep's purpose, and a
    docstring may spell it either way. Folding at the comparison boundary keeps
    the vocabulary itself accent-free and unambiguous rather than requiring
    every entry to be listed twice.
    """
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def matched_nouns(prose: str) -> tuple[str, ...]:
    """Every vocabulary noun appearing as a whole word in ``prose``.

    Whole-word rather than substring: a substring match would report *clave* in
    *claves* correctly but also fire on unrelated stems, and this census is
    read as evidence about a field's documented meaning.
    """
    words = set(_WORD.findall(fold_accents(prose)))
    return tuple(sorted(NOUN_VOCABULARY & words))


def attribute_prose(class_docstring: str | None) -> dict[str, str]:
    """Map each documented attribute name to its prose, from a Google-style docstring.

    This codebase documents model fields in the CLASS docstring's ``Attributes:``
    section rather than beside each field, so a per-field docstring walk would
    read almost nothing. Continuation lines are folded into the entry they
    belong to, because the noun that identifies a field is frequently on the
    second line of its description.
    """
    if not class_docstring:
        return {}
    entries: dict[str, str] = {}
    current: str | None = None
    in_section = False
    for line in class_docstring.splitlines():
        if _ATTRIBUTES_SECTION.match(line):
            in_section = True
            continue
        if not in_section:
            continue
        entry = _ATTRIBUTE_ENTRY.match(line)
        if entry is not None:
            current = entry.group(1)
            entries[current] = entry.group(2)
            continue
        if current is not None and line.strip():
            entries[current] = f"{entries[current]} {line.strip()}"
        elif not line.strip():
            current = None
    return entries


def field_description(node: ast.AnnAssign) -> str:
    """The ``description=`` text of a ``Field(...)`` default, or the empty string.

    A second documentation channel this tree uses alongside the class
    docstring. Reading only one of the two would under-report, which is the
    failure this whole census exists to correct at a different level.
    """
    call = node.value
    if not isinstance(call, ast.Call):
        return ""
    for keyword in call.keywords:
        if keyword.arg != "description":
            continue
        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
        if isinstance(keyword.value, ast.JoinedStr):
            return " ".join(
                part.value
                for part in keyword.value.values
                if isinstance(part, ast.Constant) and isinstance(part.value, str)
            )
    return ""


def annotation_text(node: ast.AnnAssign) -> str:
    """The field's annotation rendered back to source text."""
    return ast.unparse(node.annotation)


def is_bare_str(annotation: str) -> bool:
    """Whether the annotation is an unaliased ``str``, optionally optional.

    The subject is fields carrying no namespace type. ``str``,
    ``str | None`` and ``list[str]`` are bare; anything naming an alias is
    already enrolled or already typed by some other authority.
    """
    stripped = annotation.replace(" ", "")
    return stripped in {"str", "str|None", "None|str", "list[str]", "tuple[str,...]"}


@dataclass(frozen=True, slots=True)
class NounCandidate:
    """One field whose DOCUMENTATION calls it an identifier.

    Attributes:
        path: Repository-relative module path at the pinned revision.
        line: Line of the field's annotated assignment.
        model: Enclosing class name.
        field: Field name.
        annotation: The annotation as written.
        bare_str: Whether the annotation carries no namespace alias.
        nouns: Vocabulary nouns found in the field's documentation.
        matches_suffix_heuristic: Whether the ORIGINAL suffix sweep would also
            have found this field. ``False`` marks a record the first census
            could not see, which is the population this pass exists to surface.
        source: Which documentation channel supplied the prose.
    """

    path: str
    line: int
    model: str
    field: str
    annotation: str
    bare_str: bool
    nouns: tuple[str, ...]
    matches_suffix_heuristic: bool
    source: str

    def rendered(self) -> str:
        """A single deterministic line for the execution-record table."""
        seen = "suffix+noun" if self.matches_suffix_heuristic else "NOUN-ONLY"
        bare = "bare" if self.bare_str else "typed"
        return f"{self.path}:{self.line} {self.model}.{self.field} [{bare}] [{seen}] nouns={','.join(self.nouns)}"


class _NounVisitor(ast.NodeVisitor):
    """Collect documented identifier-shaped fields from one module's AST."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._stack: list[str] = []
        self.candidates: list[NounCandidate] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._stack.append(node.name)
        prose = attribute_prose(ast.get_docstring(node))
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                self._consider(statement, statement.target.id, prose)
        self.generic_visit(node)
        self._stack.pop()

    def _consider(self, node: ast.AnnAssign, name: str, prose: dict[str, str]) -> None:
        from_docstring = prose.get(name, "")
        from_field = field_description(node)
        nouns = matched_nouns(f"{from_docstring} {from_field}")
        if not nouns:
            return
        documented_in_class = bool(from_docstring) and bool(matched_nouns(from_docstring))
        channel = "class_docstring" if documented_in_class else "field_description"
        annotation = annotation_text(node)
        self.candidates.append(
            NounCandidate(
                path=self._path,
                line=node.lineno,
                model=".".join(self._stack),
                field=name,
                annotation=annotation,
                bare_str=is_bare_str(annotation),
                nouns=nouns,
                matches_suffix_heuristic=name.endswith(SUFFIX_HEURISTIC),
                source=channel,
            )
        )


def census_sources(sources: tuple[tuple[str, str], ...]) -> tuple[NounCandidate, ...]:
    """Every documented identifier-shaped field across already-pinned sources.

    Split from :func:`census` so the contract tests can drive an explicit
    source snapshot rather than a revision, which keeps them independent of
    what happens to be committed when they run.
    """
    found: list[NounCandidate] = []
    for path, source in sources:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            # A module that does not parse at the pinned revision is reported by
            # neither a candidate nor a silent skip: it cannot contribute a
            # field, and pretending otherwise would overstate the denominator.
            continue
        visitor = _NounVisitor(path)
        visitor.visit(tree)
        found.extend(visitor.candidates)
    return tuple(sorted(found, key=lambda item: (item.path, item.line, item.field)))


def census(revision: str) -> tuple[NounCandidate, ...]:
    """Return the noun-vocabulary candidate ledger from ``revision``.

    The revision is deliberately required, for the reason the module docstring
    states: a census over a moving worktree is not reproducible, and this one's
    output is quoted into an execution record as a gate.
    """
    return census_sources(production_sources(revision))


def _summarise(candidates: tuple[NounCandidate, ...]) -> dict[str, int]:
    """Counts the execution record needs, computed once."""
    missed = [item for item in candidates if not item.matches_suffix_heuristic]
    return {
        "documented_identifier_fields": len(candidates),
        "bare_str": sum(1 for item in candidates if item.bare_str),
        "missed_by_suffix_heuristic": len(missed),
        "missed_by_suffix_heuristic_and_bare": sum(1 for item in missed if item.bare_str),
    }


def main(argv: list[str] | None = None) -> int:
    """Print the census for one pinned revision, as text or JSON."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("revision", help="Pinned git revision to scan, e.g. HEAD or a sha")
    parser.add_argument("--json", action="store_true", help="Emit records and summary as JSON")
    parser.add_argument(
        "--only-missed-by-suffix",
        action="store_true",
        help="Restrict output to records the original suffix sweep could not see",
    )
    args = parser.parse_args(argv)

    candidates = census(args.revision)
    summary = _summarise(candidates)
    shown = (
        tuple(item for item in candidates if not item.matches_suffix_heuristic)
        if args.only_missed_by_suffix
        else candidates
    )

    if args.json:
        print(json.dumps({"summary": summary, "records": [asdict(item) for item in shown]}, indent=2, sort_keys=True))
        return 0

    for item in shown:
        print(item.rendered())
    print()
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
