"""One AEAT concept, one ``header_key`` spelling — and it is the Spanish one.

The standing naming rule assigns Spanish stems to domain concepts that map to
AEAT surfaces (``nif``, ``iva``, ``modelo``, ``casilla``). Export header keys
are such concepts: each names a fact AEAT prints in a fixed-width envelope
header. When one fact acquires two spellings, every consumer that reads the
corpus must know both, and the second spelling is invisible to anything
searching for the first.

**The case this gate was built from, and the evidence.** ``presenter_nif`` and
``presenter_tax_id`` name the same fact, established by two measurements rather
than by similarity:

* every occurrence of both, at HEAD, declares ``offset = 101`` and
  ``length = 9`` with ``kind = "header"``, ``data_type = "text"``,
  ``required = false``, ``padding = "right_space"`` and
  ``justification = "left"`` -- byte-identical field geometry, differing only
  in the token and its id slug;
* **no layout declares both.** That is the observation that could have
  falsified the conclusion: a single layout carrying both would prove they mark
  different facts by construction, whatever their geometry. The two are
  disjoint by modelo -- ``presenter_nif`` in 111/130/200/202/232/303/390,
  ``presenter_tax_id`` in 115/123 -- so this is one concept spelled two ways
  across modelo families, not a distinction the registry is drawing.

**Why this reads the committed fragments and not the enum.** The corpus is the
thing the loader consumes and the thing an author edits; an enum is a
downstream projection that can be relocated, renamed or deleted while the
fragments stay exactly as they are. A gate pinned to a symbol goes quiet the
moment that symbol moves, and reports its silence as a pass -- which is
precisely what a migration does to a symbol. Reading the fragments keeps the
gate meaningful across a rename of everything above them.

**Why the property, and not a token list.** An enumerated list of offending
tokens encodes the corpus on the day it was written and detects nothing
afterwards; the next English-stemmed key lands green. The property asserted
here is: *no ``header_key`` may carry an English stem for a concept whose
Spanish-stemmed spelling is also present in the corpus.* The stem pairs come
from the naming rule, not from tonight's findings, so a new offender in an
already-known concept is caught without touching this file.

**Why it is scoped to ``header_key`` and must stay that way.**
``presenter_tax_id`` also appears once as ``key = "presenter_tax_id"`` in
``registry/cadrumo/user_profile/schema.toml`` -- a **profile field name, in a
different namespace, on a surface this rule does not govern**. Widening the
scan to every ``key =`` in the registry would rule on that profile schema and
demand a rename the naming rule never asked for. If you are here to broaden
this gate, that is the thing to check first.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Final

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Spanish stem -> the English stem that must not stand in for it.
#:
#: Derived from the naming rule's Spanish-stem mandate, NOT from the corpus, so
#: the gate keeps working as the corpus changes. A pair belongs here when the
#: Spanish stem is the canonical AEAT vocabulary for the concept.
STEM_PAIRS: Final[tuple[tuple[str, str], ...]] = (
    ("nif", "tax_id"),
    ("nif", "taxid"),
)

#: The field names that carry an export header concept.
#:
#: BOTH spellings, deliberately. The corpus is mid-migration from ``header_key``
#: to ``producer_key``, and a gate that scans only the outgoing name returns an
#: empty set the moment that migration lands -- firing the population guard
#: below as "broken scan" at exactly the point the tree became healthy.
#:
#: That is the same defect this file's docstring warns about one level up: it
#: pins a check to a name that is itself moving. I made it while writing the
#: warning. Scanning both names means the gate follows the corpus through the
#: rename instead of going blind at it, and the third spelling -- if there ever
#: is one -- is added here rather than by rewriting the scan.
_HEADER_FIELD_NAMES: Final = ("header_key", "producer_key")

_HEADER_KEY = re.compile(
    r"^\s*(?:" + "|".join(_HEADER_FIELD_NAMES) + r')\s*=\s*"([^"]+)"',
    re.MULTILINE,
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[6]


def header_keys_at_revision(revision: str) -> frozenset[str]:
    """Return every ``header_key`` token in the registry at *revision*.

    Reads the git object store rather than the working tree, so the verdict is
    about a named commit and not about whatever a dozen agents have left on
    disk. Naming the tree a reading belongs to is the discipline this file is
    downstream of: the same measurement run against the worktree and reported
    as a fact about HEAD produced a confidently wrong finding earlier in this
    corpus's history.
    """
    tokens: set[str] = set()
    for field_name in _HEADER_FIELD_NAMES:
        listing = subprocess.run(  # noqa: S603 - fixed executable and arguments
            ["git", "grep", "-h", field_name, revision, "--", "src/cadrumo/_data/registry"],  # noqa: S607
            capture_output=True,
            # The registry is UTF-8 by contract, and `git grep -h` prints whole
            # matching LINES -- so a line carrying an accented AEAT name comes
            # back as UTF-8 bytes. `text=True` alone decodes with the platform's
            # locale codec, which on Windows is cp1252, where the second byte of
            # "Á" is undefined: the decode raised, `.stdout` came back None, and
            # this gate ERRORED instead of gating. Modelo 322's "Álava" line is
            # the one that does it, and it has been committed for some time.
            encoding="utf-8",
            check=False,
            cwd=_repository_root(),
        ).stdout
        tokens.update(_HEADER_KEY.findall(listing))
    return frozenset(tokens)


def english_stem_offenders(tokens: frozenset[str]) -> tuple[tuple[str, str], ...]:
    """Return ``(offending token, canonical token)`` for every dual spelling.

    A token offends only when substituting the Spanish stem yields a token the
    corpus ALSO carries. An English-stemmed key with no Spanish sibling is left
    alone deliberately: it may be the only spelling of a concept nobody has
    given a Spanish name yet, and refusing it here would be a naming ruling
    this gate has no evidence for.
    """
    offenders: list[tuple[str, str]] = []
    for token in sorted(tokens):
        for spanish, english in STEM_PAIRS:
            if not token.endswith(f"_{english}"):
                continue
            canonical = f"{token[: -len(english)]}{spanish}"
            if canonical in tokens:
                offenders.append((token, canonical))
    return tuple(offenders)


@pytest.fixture(scope="module")
def head_tokens() -> frozenset[str]:
    """Every ``header_key`` token committed at HEAD."""
    return header_keys_at_revision("HEAD")


def test_the_scan_reaches_a_real_population(head_tokens: frozenset[str]) -> None:
    """Fail on an empty scan before any verdict below is allowed to stand.

    A scan that returns nothing because the path moved, the pattern broke or
    the subprocess failed is indistinguishable from a corpus with no header
    keys at all -- and it would make every assertion here pass.

    Gated on the PROPERTY, never on a tally. An earlier version required more
    than twenty tokens, which encoded the corpus of the day: the count fell to
    eighteen when nineteen modelos' export layouts were retracted, and the gate
    then reported a healthy scan as a broken one. What actually distinguishes a
    real read from a broken one is that what came back is the live producer
    vocabulary -- a broken parse yields nothing, and a mis-parse yields tokens
    the closed enum does not carry.
    """
    from .....core.filing_producer_key import FilingProducerKey

    assert head_tokens, "the header_key scan found nothing at HEAD; that is a broken scan, not a corpus"
    unknown = head_tokens - {member.value for member in FilingProducerKey}
    assert not unknown, f"the header_key scan returned tokens outside the closed producer vocabulary: {sorted(unknown)}"


def test_the_gate_detects_a_known_dual_spelling() -> None:
    """Validate against a case whose answer is already known.

    A watchdog checked only against unknown states cannot be told apart from a
    broken one, so this pins the verdict on a hand-built corpus: the pair is a
    dual spelling, the lone English key is not, and the Spanish key is not.
    """
    corpus = frozenset({"presenter_nif", "presenter_tax_id", "orphan_tax_id", "declarante_nif"})
    assert english_stem_offenders(corpus) == (("presenter_tax_id", "presenter_nif"),)

    control = frozenset({"presenter_nif", "declarante_nif", "orphan_tax_id"})
    assert english_stem_offenders(control) == (), "the control corpus must PASS or the mutation proves nothing"


def test_no_header_key_spells_a_spanish_concept_in_english(head_tokens: frozenset[str]) -> None:
    """The canonical producer vocabulary keeps only the Spanish AEAT spelling.

    The committed corpus must carry NO dual spelling. An earlier version of
    this assertion pinned the `presenter_tax_id`/`presenter_nif` pair as the
    expected result, which made a live defect the contract: once the pair left
    HEAD the gate failed for having been FIXED, and while it stood it could
    never have caught a second offender appearing beside the first. The
    detector's own proof lives in
    :func:`test_the_gate_detects_a_known_dual_spelling`, against a hand-built
    corpus, so nothing is lost by asserting the real contract here.
    """
    from .....core.filing_producer_key import FilingProducerKey

    assert english_stem_offenders(head_tokens) == ()
    producer_keys = {member.value for member in FilingProducerKey}
    assert "presenter.tax_id" in producer_keys
    assert "presenter_tax_id" not in producer_keys
    assert "presenter_nif" not in producer_keys
