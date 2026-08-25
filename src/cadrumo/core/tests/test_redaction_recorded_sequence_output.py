"""No recorded operator output may change under the funnel unless it is an identity.

Every corpus that has ever cleared a change to this funnel was authored, and
every one of them was shaped so the live defect was unreachable. The shipped
locale catalogues contain no serialised instant, no decimal-bearing payload and
no prose with short neighbours. A hand-written negative list contains what its
author thought to doubt. Three defects have now shipped past a sound
measurement of an authored corpus, and the most recent one hashed this
application's own canonical work-unit name -- handing an operator
``modelo-sha256:44bc266f.boe`` where an export filename belongs.

The recorded sequence outputs are not authored for this purpose. They are
captured renderings of real commands, so they are the closest thing in the tree
to the population the funnel actually guards, and nobody curated them to avoid
embarrassing a redaction rule. That is exactly why they can catch what an
authored corpus cannot.

The property is one-directional and deliberately so: a recorded line may change
ONLY where the changed span is a real identity or account by the authorities'
own judgement. It says nothing about whether redaction is firing often enough --
the authored suites carry that half -- and everything about whether it is
firing on operator output it has no business touching.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from ..directory_scan import DirectoryEntryKind, scan_directory
from ..redaction import redact_for_cli_output, redact_for_log
from .test_redaction_population_coverage import (
    _DIGEST_RE,
    _admitting_authority,
    _recover_hashed_spans,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RECORDED_SEQUENCES = REPOSITORY_ROOT / "docs" / "_sequences"

_FUNNELS: tuple[tuple[str, Callable[[str], str]], ...] = (
    ("redact_for_cli_output", redact_for_cli_output),
    ("redact_for_log", redact_for_log),
)

#: A line cannot be touched by any shape-based arm without carrying one of
#: these. Applied only to keep the sweep cheap: it is a strict superset of what
#: the patterns can match, so it cannot hide a violation. A digit run of seven
#: or more covers both personal-identity arms; two letters followed by an
#: alphanumeric run covers the CIF, NIF-IVA and IBAN arms.
_CANDIDATE_LINE_RE = re.compile(r"(?:\d[ .\-]?){7}|[A-Za-z]{2}[ .\-]?[0-9A-Za-z]{4}")

#: Below this the corpus is not the corpus this gate was written against, and a
#: zero-violation result would mean the files moved rather than that the funnel
#: is clean.
_MINIMUM_EXPECTED_FILES = 100

#: The corpus is known to carry real identity-shaped specimens. If none of them
#: redact, the funnel is not running and every assertion below passes vacuously.
_MINIMUM_EXPECTED_REDACTIONS = 5


def _recorded_lines() -> Iterator[str]:
    """Yield each distinct line of recorded output, pre-filtered to candidates."""
    seen: set[str] = set()
    for path in scan_directory(RECORDED_SEQUENCES, recursive=True, select=DirectoryEntryKind.FILES):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line in text.splitlines():
            if line in seen or not _CANDIDATE_LINE_RE.search(line):
                continue
            seen.add(line)
            yield line


def test_the_recorded_corpus_is_present_and_large_enough_to_measure() -> None:
    """A gate over a corpus that moved is a gate over nothing.

    This assertion is the difference between "the funnel touched no recorded
    output" and "the recorded output is no longer where this gate looks", which
    are indistinguishable in the result.
    """
    assert RECORDED_SEQUENCES.is_dir(), f"recorded sequence corpus is missing at {RECORDED_SEQUENCES}"

    files = len(scan_directory(RECORDED_SEQUENCES, recursive=True, select=DirectoryEntryKind.FILES))

    assert files >= _MINIMUM_EXPECTED_FILES, f"only {files} recorded files found; the corpus moved or shrank"


def test_no_recorded_operator_line_is_rewritten_unless_it_carries_an_identity() -> None:
    """The standing gate. A widening shows up here as a concrete rewritten line.

    A violation is reported with the line and the span, because the useful
    output of this gate is not the count -- it is which operator-facing token
    the funnel started eating.

    **Mutate this at RULE level, never at the authority.** The check deliberately
    composes the same ``validate_identity`` the funnel consults, so a mutation
    that patches the authority moves the funnel and this gate's own admitting
    predicate together: the gate stays green and the proof proves nothing. Both
    controls have been discharged at rule level -- widening the pattern back to
    the shape-only form reds this case and the named-regression case below,
    while silencing the funnel entirely reds only the redaction floor. That
    difference is the point: "nothing was over-redacted" and "the funnel never
    ran" produce the same output here and are opposite facts.
    """
    violations: list[str] = []
    redacted_tokens: set[str] = set()

    for line in _recorded_lines():
        for funnel_name, funnel in _FUNNELS:
            emitted = funnel(line)
            if emitted == line:
                continue
            for digest in _DIGEST_RE.findall(emitted):
                spans = _recover_hashed_spans(line, digest)
                admitted = {span for span in spans if _admitting_authority(span)}
                if admitted:
                    redacted_tokens |= admitted
                    continue
                violations.append(f"{funnel_name}: {line!r} -> {emitted!r} (hashed {sorted(spans)!r})")

    assert not violations, "the funnel rewrote recorded operator output that carries no identity:\n" + "\n".join(
        violations[:20]
    )
    assert len(redacted_tokens) >= _MINIMUM_EXPECTED_REDACTIONS, (
        f"only {len(redacted_tokens)} identity-shaped tokens redacted across the whole recorded corpus; "
        "the funnel is not running and this gate is measuring nothing"
    )


def test_the_work_unit_naming_the_corpus_carries_reaches_the_operator_intact() -> None:
    """The specific regression, named, so a re-widening is legible not just red.

    ``<modelo>-<year>-<period>`` is this app's canonical work-unit name. It
    normalises to eight digits and a trailing letter -- the personal-identity
    shape exactly -- across every modelo family and both period shapes, so a
    shape-only rule hashes all of them. An operator handed a digest in place of
    an export filename has a path they cannot use.

    The registry rule id is the same collision reached by a different route: it
    is not a work-unit name at all, and it still presents a long digit run
    broken by hyphens. Two independent naming conventions landing on one shape
    is why the fix had to be the arm's admission rule rather than an exclusion
    for the names anyone had thought of.
    """
    names = [
        "modelo-130-2026-1T.boe",
        "303-2026-1T",
        "390-2026-0A",
        "100-2026-0A",
        "184-2026-0A",
        "349-2026-4T",
        "modelo-202-2025-y-siguientes-rel-cuota-base-1p",
    ]

    for name in names:
        for _funnel_name, funnel in _FUNNELS:
            assert funnel(name) == name, f"{name!r} was rewritten to {funnel(name)!r}"
