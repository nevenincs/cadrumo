"""Structural contract gates over the enrolled ``cli-sequence`` corpus.

The tightened @result contract: a ``@result`` frame must assert the
result PAYLOAD — at least one ``@expect`` on a ``result.<path>`` / ``result[...]``
json-path — not merely ``exit_code`` or the ``status`` spine field, so a sequence
verifies the MEANING of its final output rather than only that the process ran.

The detection lives in the parser (``result_frame_asserts_result_payload``); this
module enforces it as a ratcheting per-page gate — the same discipline as the
mandatory-display fence gate — so the docs build, the check tier, and the engine's
own synthetic unit tests stay green while the converters sweep. A page may never
exceed its committed offender count; a page absent from the baseline may carry
none; a page below its baseline passes. An empty baseline means every enrolled
``@result`` frame asserts its payload.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from dev.docs.sequences import (
    default_docs_root,
    discover_sequences,
    read_golden,
    result_frame_asserts_result_payload,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_BASELINE_PATH = Path(__file__).resolve().parent / "result_assertion_baseline.json"
_EXECUTED_OPERATOR_JOURNEYS = frozenset(
    {
        "profile-setup-capabilities",
        "profile-setup-logout",
        "profile-setup-maintain",
        "protect-data-access-logout",
    },
)
_PUBLIC_DEVELOPMENT_METADATA_RE = re.compile(
    r"^\s*(?:@(?:setup|result|capture|expect|static|step)\b|:(?:seed|shells):)",
    re.MULTILINE,
)


def _current_offender_counts() -> dict[str, int]:
    """Return the per-page count of @result frames that assert no result payload."""
    discovered, problems = discover_sequences(docs_root=default_docs_root())
    assert not problems, "sequence discovery reported problems:\n  " + "\n  ".join(problems)
    counts: dict[str, int] = {}
    for item in discovered:
        if not result_frame_asserts_result_payload(item.sequence):
            counts[item.page] = counts.get(item.page, 0) + 1
    return counts


def test_result_frames_assert_the_result_payload() -> None:
    """No enrolled page carries more payload-less @result frames than its baseline.

    A ``@result`` frame asserting only ``exit_code`` (and/or ``status``) proves the
    command ran without proving it produced the right answer. This gate ratchets
    DOWN from a committed per-page baseline: converters add a ``result.<path>``
    assertion and tighten the entry, and an empty baseline means the contract is
    fully applied. A page below its baseline passes, so the sweep never reds the
    tree mid-flight.
    """
    baseline: dict[str, int] = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    current = _current_offender_counts()
    problems: list[str] = []
    for page in sorted(current):
        count = current[page]
        allowed = baseline.get(page, 0)
        if count > allowed:
            problems.append(
                f"{page}: {count} @result frame(s) assert no result payload, baseline allows {allowed}. "
                "A @result frame must carry at least one @expect on the result payload "
                "(e.g. '@expect result.status == \"verified_complete\"' or "
                "'@expect result.work_unit_id != null'), not only 'exit_code'/'status'; "
                f"then tighten the entry in {_BASELINE_PATH.name}"
            )
    assert not problems, (
        "cli-sequence @result frames must assert their result payload "
        "(ADR D4 result-assertion contract):\n  " + "\n  ".join(problems)
    )


def test_sequence_discovery_reads_a_non_empty_corpus() -> None:
    """Every gate in this module is vacuous over an empty discovery result.

    ``discover_sequences`` reports an absent or empty docs tree as zero
    sequences and zero PROBLEMS, so nothing downstream distinguishes "the
    corpus is clean" from "there was no corpus". The ratchet above then folds
    an empty result into an empty offender map and passes.
    """
    discovered, problems = discover_sequences(docs_root=default_docs_root())
    assert not problems, "sequence discovery reported problems:\n  " + "\n  ".join(problems)
    assert len(discovered) > 100, f"expected the enrolled sequence corpus, discovered only {len(discovered)}"


def test_an_empty_docs_root_yields_no_offenders_and_no_problems(tmp_path: Path) -> None:
    """The reproduction behind the guard above is real, not theoretical.

    Pointed at an empty root, discovery returns nothing AND reports nothing
    wrong, so the offender map is empty and the ratchet passes clean. This was
    observed for real: a probe that resolved its docs root to a path that did
    not exist got a confident zero back and no error. Asserting the behaviour
    here keeps the non-emptiness guard load-bearing rather than decorative.
    """
    discovered, problems = discover_sequences(docs_root=tmp_path, contracts_root=tmp_path)
    assert discovered == ()
    assert problems == (), "an empty root is reported as clean, which is exactly why the guard is needed"


def test_development_metadata_pattern_discriminates() -> None:
    """Positive control: the metadata pattern matches its grammar and rejects prose.

    The corpus scan finds nothing today, so it is green whether the pattern
    works or not. These cases pin it against lines it MUST flag and reader
    prose it MUST NOT, independently of what the documentation contains.
    """
    must_match = (
        "@setup aeat app ledger import --file fixtures/x.csv",
        "@result aeat app modelo work verify wu",
        "@capture work_unit_id result.work_unit_id",
        '@expect result.status == "verified_complete"',
        "@static aeat app live justificante pull",
        "@step Create the quarterly draft.",
        ":seed: demo-profile",
        ":shells: bash pwsh",
        "  @result an indented frame still leaks",
    )
    must_not_match = (
        "Write to us at support@setupdesk.example.",
        "An @ sign in ordinary prose.",
        "Mention of a step, a result, and an expectation in a sentence.",
        "text @result appearing mid-line is not a directive line",
    )
    for line in must_match:
        assert _PUBLIC_DEVELOPMENT_METADATA_RE.search(line), f"metadata pattern no longer flags {line!r}"
    for line in must_not_match:
        assert not _PUBLIC_DEVELOPMENT_METADATA_RE.search(line), f"metadata pattern over-matches prose {line!r}"


def test_result_assertion_baseline_is_well_formed() -> None:
    """The ratchet baseline is a well-formed page -> non-negative-count map.

    The baseline is deliberately NOT asserted equal to the live counts: a page
    below its baseline is legitimate mid-sweep progress. The one-directional
    guarantee (no page exceeds its baseline) lives in
    :func:`test_result_frames_assert_the_result_payload`.
    """
    baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    assert isinstance(baseline, dict), "result_assertion_baseline.json must map page -> count"
    for page, allowed in baseline.items():
        assert isinstance(page, str) and page, "baseline keys must be non-empty docname-style page paths"
        assert isinstance(allowed, int) and not isinstance(allowed, bool) and allowed >= 0, (
            f"baseline entry {page!r} must be a non-negative integer count, got {allowed!r}"
        )


def test_operator_profile_journeys_remain_executed_truth() -> None:
    """Profile custody journeys keep real execution and committed golden evidence."""
    discovered, problems = discover_sequences(docs_root=default_docs_root())
    assert not problems, "sequence discovery reported problems:\n  " + "\n  ".join(problems)
    by_id = {item.sequence_id: item for item in discovered}

    for sequence_id in sorted(_EXECUTED_OPERATOR_JOURNEYS):
        item = by_id[sequence_id]
        assert item.sequence.executed_frames, f"{sequence_id} must not be downgraded to an all-@static card"
        golden = read_golden(item.page, sequence_id)
        assert golden.frames, f"{sequence_id} must retain committed real-behavior evidence"


def test_user_markdown_contains_no_sequence_development_metadata() -> None:
    """Machine grammar stays in private keyed contracts, never reader Markdown."""
    docs_root = default_docs_root()
    scanned: list[Path] = [
        path
        for path in sorted(docs_root.rglob("*.md"))
        if not (path.relative_to(docs_root).parts and path.relative_to(docs_root).parts[0] in {"_build", "_sequences"})
    ]
    assert len(scanned) > 20, f"expected the reader-facing docs corpus, scanned only {len(scanned)} page(s)"
    offenders: list[str] = []
    for path in scanned:
        relative = path.relative_to(docs_root)
        text = path.read_text(encoding="utf-8")
        for match in _PUBLIC_DEVELOPMENT_METADATA_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{relative.as_posix()}:{line}: {match.group(0).strip()}")
    assert offenders == [], "development metadata leaked into user-facing Markdown:\n  " + "\n  ".join(offenders)


def test_every_sequence_has_exactly_one_keyed_private_contract() -> None:
    """The public directive inventory and private contract inventory agree."""
    docs_root = default_docs_root()
    discovered, problems = discover_sequences(docs_root=docs_root)
    assert not problems, "sequence discovery reported problems:\n  " + "\n  ".join(problems)
    expected = {Path(item.page) / f"{item.sequence_id}.seq" for item in discovered}
    contracts_root = docs_root / "_sequences" / "contracts"
    actual = {path.relative_to(contracts_root) for path in contracts_root.rglob("*.seq")}
    assert actual == expected, (
        f"private sequence contracts differ from public directives; "
        f"missing={sorted(str(path) for path in expected - actual)}, "
        f"orphaned={sorted(str(path) for path in actual - expected)}"
    )
