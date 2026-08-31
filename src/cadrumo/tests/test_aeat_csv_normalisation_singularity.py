"""AEAT CSV normalisation singularity: one function owns the comparison form.

``normalise_aeat_csv`` (:mod:`cadrumo.core.aeat_csv`) is the single production
answer to "what is the canonical form of this Código Seguro de Verificación?".
No other production module may restate the transform.

The reason this needs a gate rather than a docstring is recorded in the history
it comes from. The concept was consolidated once, onto the correct uppercase
form, and then re-fragmented: nine further sites carried their own copy while
the canonical module's own prose described them in the past tense as already
corrected. Two of those copies were ``str.casefold``, which is not a stylistic
variant -- it produces lowercase, which fails ``AEAT_CSV_PATTERN`` outright, and
it transliterates, which is fatal for a value that must round-trip to AEAT's
cotejo endpoint byte-for-byte to re-serve a filed document. The remaining seven
agreed with the canonical transform character-for-character, which is exactly
what makes them dangerous: nothing would have noticed them diverging.

Detection is a call-site check over the real ``ast`` module, recomputed every
run against the production tree with NO stored baseline and NO per-violation
allowlist: a case transform applied to a CSV-bearing expression outside the
canonical module is a second comparison form.

Two known limits, stated rather than papered over.

The receiver must NAME a csv for the walk to see it. The live evidence
comparison reads ``filing.external_evidence.reference_id`` against a receipt
CSV -- one side of a CSV comparison that carries no ``csv`` token, so an inline
copy written only on that side is invisible here. Nothing makes a third copy
impossible; this raises its cost.

``csv`` is two words in this tree. The AEAT identifier is one; the
comma-separated-values file format is the other, and it appears in the tabular
reader's settings and adapters. The match is anchored to the head or the tail of
each IDENTIFIER inside the receiver, which excludes the format sense as it is
written today (``financial_default_csv_encoding``) without needing an allowlist
to carve it out. A future format-sense site that does land head-or-tail should
be renamed to say which csv it means rather than added to an exemption list --
the ambiguity, not the gate, is the defect there.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Case transforms that mint a comparison form. ``strip`` is deliberately absent:
#: a bare trim is not a second normal form, and the emptiness guards that use one
#: are legitimate.
_CASE_TRANSFORMS = frozenset({"upper", "lower", "casefold"})

#: An identifier naming an AEAT CSV: ``csv`` (singular or plural) standing alone,
#: or at the head or tail of a snake_case name. Anchoring to the ends of the
#: IDENTIFIER rather than to the ends of the whole expression is what lets the
#: match survive a trailing ``.strip()``, which every removed comparison had;
#: anchoring at all is what keeps the comma-separated-values sense
#: (``financial_default_csv_encoding``) out without an exemption list.
_CSV_IDENTIFIER = re.compile(r"^csvs?(_|$)|(^|_)csvs?$", re.IGNORECASE)

#: The canonical home. It is the one module allowed to write the transform.
_CANONICAL = Path("src/cadrumo/core/_aeat_csv.py")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRODUCTION_ROOT = _REPO_ROOT / "src" / "cadrumo"


def _names_a_csv(receiver: ast.expr) -> bool:
    """Return whether any identifier inside ``receiver`` names an AEAT CSV."""
    return any(
        _CSV_IDENTIFIER.search(name)
        for node in ast.walk(receiver)
        for name in (
            [node.id] if isinstance(node, ast.Name) else [node.attr] if isinstance(node, ast.Attribute) else []
        )
    )


def _inline_csv_normalisations(tree: ast.AST) -> list[str]:
    """Return the enclosing function names of every inline CSV case transform."""
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr in _CASE_TRANSFORMS
                and _names_a_csv(child.func.value)
            ):
                offenders.append(node.name)
                break
    return offenders


def _production_modules() -> list[Path]:
    """Return every production module, test packages and the canonical home excluded."""
    canonical = _REPO_ROOT / _CANONICAL
    return [
        path
        for path in scan_directory(_PRODUCTION_ROOT, pattern="*.py", recursive=True)
        if "tests" not in path.parts and "__pycache__" not in path.parts and path != canonical
    ]


def test_the_canonical_home_is_where_the_gate_says_it_is() -> None:
    """Anchor check: a moved or renamed authority must retarget the gate, not pass it.

    Without this the exclusion above could point at nothing after a relocation
    and the scan would keep reporting a clean tree while the real home sat
    unexcluded and unenforced.
    """
    canonical = _REPO_ROOT / _CANONICAL
    assert canonical.is_file(), "the canonical CSV module moved; retarget _CANONICAL"

    source = canonical.read_text(encoding="utf-8")
    assert "def normalise_aeat_csv(" in source, (
        "the canonical comparison form is no longer defined where this gate excludes; "
        "retarget _CANONICAL rather than widening the scan"
    )


def test_the_detector_fires_on_the_forms_that_were_actually_removed() -> None:
    """Prove discrimination on the real removed shapes, not on the live tree.

    The scan below passes for a detector that matches nothing at all. These are
    the exact expressions this consolidation deleted, so a detector that stops
    recognising them has stopped protecting the thing it was built for.
    """
    a_casefold_comparison = """
def _blockers(metadata_csv, justificante):
    return metadata_csv.casefold() != justificante.csv.casefold()
"""
    an_upper_comparison = """
def _matches(evidence, csv):
    return evidence.reference_id == csv.strip().upper()
"""
    # The dotted-then-trimmed form. It is called out separately because it is the
    # shape the first cut of this detector MISSED: anchoring the match to the ends
    # of the whole receiver expression let a trailing ``.strip()`` hide the csv
    # token, so the gate reported a clean tree over a planted second copy.
    a_dotted_upper_comparison = """
def _guard(justificante, snapshot):
    return justificante.csv.strip().upper() != snapshot.csv.strip().upper()
"""
    a_set_membership = """
def _in_set(justificante, metadata_csvs):
    return justificante.csv.casefold() in {csv.casefold() for csv in metadata_csvs}
"""
    an_extractor = """
def _extract(csv_match):
    return csv_match.group(1).upper()
"""
    assert _inline_csv_normalisations(ast.parse(a_casefold_comparison)) == ["_blockers"]
    assert _inline_csv_normalisations(ast.parse(an_upper_comparison)) == ["_matches"]
    assert _inline_csv_normalisations(ast.parse(a_dotted_upper_comparison)) == ["_guard"]
    assert _inline_csv_normalisations(ast.parse(a_set_membership)) == ["_in_set"]
    assert _inline_csv_normalisations(ast.parse(an_extractor)) == ["_extract"]


def test_the_detector_leaves_the_canonical_call_and_the_other_csv_alone() -> None:
    """The negative half: routing through the authority, and the file format, stay quiet.

    A detector that fired on the fixed code or on the comma-separated-values
    sense would be uninhabitable, and the first red run would be resolved by
    weakening it rather than by fixing a real second form.
    """
    the_fixed_shape = """
def _blockers(metadata_csv, justificante):
    return normalise_aeat_csv(metadata_csv) != normalise_aeat_csv(justificante.csv)
"""
    an_emptiness_guard = """
def _index(justificante):
    return justificante.csv.strip()
"""
    the_file_format = """
def _reader(settings):
    return settings.financial_default_csv_encoding.strip().upper()
"""
    assert _inline_csv_normalisations(ast.parse(the_fixed_shape)) == []
    assert _inline_csv_normalisations(ast.parse(an_emptiness_guard)) == []
    assert _inline_csv_normalisations(ast.parse(the_file_format)) == []


def test_no_production_module_restates_the_csv_comparison_form() -> None:
    """Every production CSV normalisation calls the canonical authority."""
    offenders = {
        path.relative_to(_REPO_ROOT).as_posix(): callers
        for path in _production_modules()
        if (callers := _inline_csv_normalisations(ast.parse(path.read_text(encoding="utf-8"))))
    }

    assert not offenders, (
        "these production sites restate the AEAT CSV comparison form instead of "
        f"calling normalise_aeat_csv: {offenders}. A lowercase or casefolded form "
        "fails the uppercase alphanumeric contract it normalises toward and "
        "transliterates a value that must round-trip to AEAT's cotejo endpoint "
        "byte-for-byte; an inline copy that happens to agree today is a second "
        "key for one identifier waiting to drift. Import normalise_aeat_csv from "
        "cadrumo.core and delete the inline transform rather than leaving both."
    )
