"""Structural contract gates over the enrolled ``cli-sequence`` corpus.

The tightened @result contract: a structured ``@result`` frame must assert its
success or refusal payload through ``result.*`` or ``error.*``, not merely
``exit_code`` or the ``status`` spine field. A terminal ``--help`` frame has no
JSON envelope and instead proves successful help rendering; the CLI help snapshot
gates own its exact text.

The contract is REFUSED at the ``parse_sequence`` boundary, so a payload-less
``@result`` frame cannot be authored: it must be named in the parser's
``_RESULT_PAYLOAD_EXEMPT`` map, with a reason, in the same change. This module
closes the opposite direction, asserting the exemption set still equals the live
payload-less set so a paid-down allowance cannot silently linger.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

from ..sequences.checks import default_docs_root, discover_sequences
from ..sequences.golden_store import read_golden
from ..sequences.parser import _RESULT_PAYLOAD_EXEMPT, result_frame_asserts_result_payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

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


def _offender_sequence_ids() -> frozenset[str]:
    """Return every enrolled sequence whose ``@result`` frame asserts no payload."""
    discovered, problems = discover_sequences(docs_root=default_docs_root())
    assert not problems, "sequence discovery reported problems:\n  " + "\n  ".join(problems)
    return frozenset(
        item.sequence.sequence_id for item in discovered if not result_frame_asserts_result_payload(item.sequence)
    )


def test_result_payload_exemptions_match_the_live_offenders() -> None:
    """The exemption set equals the live payload-less set, exactly.

    The contract itself is enforced at the ``parse_sequence`` boundary, so a NEW
    payload-less ``@result`` frame cannot be authored at all: it fails the docs
    build unless it is named in ``_RESULT_PAYLOAD_EXEMPT`` with a reason. This gate
    closes the other direction — an exemption whose debt has been paid, or one
    naming a sequence that no longer exists, reds until it is removed, so the
    allowance can never silently outlive what it was granted for.

    This replaces a committed per-page baseline file whose deletion left the whole
    contract unenforced and unannounced; the exemption now lives beside the code
    that honours it and cannot go missing independently of it.
    """
    offenders = _offender_sequence_ids()
    exempt = frozenset(_RESULT_PAYLOAD_EXEMPT)
    assert offenders == exempt, (
        "the payload-less @result frames and the boundary exemptions have diverged:\n"
        f"  exempt but no longer payload-less (remove the entry): {sorted(exempt - offenders)}\n"
        f"  payload-less but not exempt: {sorted(offenders - exempt)}"
    )
    for sequence_id, reason in _RESULT_PAYLOAD_EXEMPT.items():
        assert reason.strip(), f"exemption {sequence_id!r} must state why it is not yet convertible"


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
        for path in scan_directory(docs_root, pattern="*.md", recursive=True)
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
    actual = {
        path.relative_to(contracts_root) for path in scan_directory(contracts_root, pattern="*.seq", recursive=True)
    }
    assert actual == expected, (
        f"private sequence contracts differ from public directives; "
        f"missing={sorted(str(path) for path in expected - actual)}, "
        f"orphaned={sorted(str(path) for path in actual - expected)}"
    )
