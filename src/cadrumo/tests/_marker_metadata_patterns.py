"""Scan-pattern tables for the campaign- and process-metadata marker gates.

:mod:`.test_marker_integrity` walks every test module's comments, docstrings,
and durable symbol/pytest-id names for this repo's own process history (a
numbered campaign-container id, a dated decision-record filename, a fixed
process-review phrase) — the leak `aeat-source-hygiene` and the vaultspec
"Code Stands Alone" mandate forbid. This module holds the declarative half of
that gate: the pattern/target/near-miss triples plus the small helpers that
apply and prove them. It is genuinely separable from the AST walk that uses
it, since none of it touches a module tree — it is scan data.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class PatternCase(NamedTuple):
    """A scan pattern bound to the evidence that it still measures.

    A pattern that cannot match is indistinguishable from a clean tree: the
    scan reports nothing either way. Binding the probes to the pattern at its
    declaration is what stops a new pattern arriving without the controls
    proving it discriminates, and it is how a token scrambled while being
    split across a concatenation stops reading as a clean result.
    """

    pattern: re.Pattern[str]
    must_match: tuple[str, ...]
    must_not_match: tuple[str, ...]


CAMPAIGN_METADATA_CASES: tuple[PatternCase, ...] = (
    PatternCase(re.compile(r"\btest_w\d+_p\d+", re.IGNORECASE), ("def test_w01_p02_thing",), ("def test_workbook_parity",)),
    PatternCase(
        re.compile(r"\bW\d{1,3}(?:\.P\d{1,3})?(?:\.S\d{1,4})?\b"),
        ("carried in W01.P02.S03",),
        ("the W3C standard",),
    ),
    PatternCase(re.compile(r"\bP\d{1,3}\.S\d{1,4}\b"), ("see P02.S14",), ("only P02 here",)),
    PatternCase(re.compile(r"\bS\d{2,4}\b"), ("closed by S08",), ("the S1 bucket",)),
    PatternCase(re.compile(r"\blegacy-(?:plan|step)"), ("a legacy-plan carry",), ("a legacy-format reader",)),
    PatternCase(
        re.compile(r"\baccepted contract\b", re.IGNORECASE),
        ("the accepted contract",),
        ("accepted contracts elsewhere",),
    ),
    PatternCase(re.compile(r"\bhistory-step\b", re.IGNORECASE), ("a history-step note",), ("revision history",)),
    PatternCase(
        re.compile(r"\bfollow-up step\b", re.IGNORECASE),
        ("a follow-up step remains",),
        ("follow-up guidance",),
    ),
    PatternCase(re.compile(r"\bplan Step\b"), ("per plan Step here",), ("the export plan cells",)),
    PatternCase(re.compile(r"\bSte" + r"p\s+\d+\b"), ("Step 4 of the campaign",), ("Steps 1 and 2",)),
    PatternCase(re.compile(r"\bstep by step\b", re.IGNORECASE), ("walk step by step",), ("one step at a time",)),
    # ``Plan de empleo`` is a real LIRPF pension concept, so the uppercase-letter
    # tail is what separates the process noun from the domain one.
    PatternCase(re.compile(r"\bPla" + r"n\s+[A-Z]\b"), ("fall back to Plan B",), ("Plan de empleo reduccion",)),
    PatternCase(re.compile(r"\bwave\b", re.IGNORECASE), ("the second wave landed",), ("waveform analysis",)),
    PatternCase(re.compile(r"\bAD" + r"R\b"), ("recorded in the ADR",), ("address parsing",)),
    PatternCase(re.compile(r"\bP" + r"R\b"), ("landed in PR",), ("PRINT mode",)),
    PatternCase(re.compile(r"\b[Pp]hase[- ][A-Za-z0-9]"), ("phase-2 rollout",), ("phases of the moon",)),
    PatternCase(re.compile(r"\.vault/ad" + r"r", re.IGNORECASE), ("see .vault/adr/x",), ("the vault adr folder",)),
    PatternCase(
        re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[-_a-z0-9]*ad" + r"r", re.IGNORECASE),
        ("2026-07-25-thing-adr",),
        ("2026-07-25 release notes",),
    ),
)
CAMPAIGN_METADATA_PATTERNS = tuple(case.pattern for case in CAMPAIGN_METADATA_CASES)
_NOQA_LINT_CODE_PATTERN = re.compile(r"(#\s*noqa(?::\s*)?)([A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)")
#: Process nouns that must not name a durable test symbol or pytest id.
#:
#: The plan entry is narrower than its four siblings on purpose. Those four name
#: nothing in this domain, so banning the bare token costs nothing. ``plan`` is
#: not free: the workbook exporter's ``SheetExportPlan`` and the LIRPF ``plan de
#: empleo`` reduccion both own the word legitimately, and banning it bare flags
#: 26 such symbols. Only the process compounds are matched, so the domain keeps
#: the word it already uses.
PROCESS_PLAN_CASE = PatternCase(
    re.compile(r"(^|[_-])pl" + r"an[_-](?:step|phase|wave|item|id)($|[_-])", re.IGNORECASE),
    ("test_plan_step_ordering", "_plan_item_rollup"),
    ("test_plan_de_empleo_capped", "_m130_plan", "test_export_plan_mirrors_manifest"),
)
PROCESS_SYMBOL_METADATA_CASES: tuple[PatternCase, ...] = (
    PatternCase(re.compile(r"(^|[_-])ad" + r"r($|[_-])", re.IGNORECASE), ("test_adr_probe",), ("test_address_parse",)),
    PatternCase(
        re.compile(r"(^|[_-])pha" + r"se($|[_-])", re.IGNORECASE),
        ("test_phase_rollout",),
        ("test_phases_of_moon",),
    ),
    PatternCase(
        re.compile(r"(^|[_-])wa" + r"ve($|[_-])", re.IGNORECASE),
        ("test_wave_rollup",),
        ("test_waveform_probe",),
    ),
    PROCESS_PLAN_CASE,
    PatternCase(re.compile(r"(^|[_-])p" + r"r($|[_-])", re.IGNORECASE), ("test_pr_review",), ("test_print_payload",)),
)
PROCESS_SYMBOL_METADATA_PATTERNS = tuple(case.pattern for case in PROCESS_SYMBOL_METADATA_CASES)

#: The pattern the plan entry replaced. Concatenating ``"pa" + "ln"`` to keep the
#: token out of the file's own scan transposed it, so the compiled pattern was
#: ``paln`` — a string this tree does not contain. It matched nothing from the day
#: it was written, and a scan that matches nothing reports exactly what a clean
#: tree reports. Retained as the negative control for the replacement.
RETIRED_SCRAMBLED_PLAN_PATTERN = re.compile("pa" + "ln", re.IGNORECASE)


def campaign_metadata_scan_text(token_string: str) -> str:
    """Return token text with ordinary lint suppression codes removed."""
    return _NOQA_LINT_CODE_PATTERN.sub(lambda match: match.group(1), token_string)


def assert_cases_discriminate(cases: tuple[PatternCase, ...]) -> None:
    """Assert each case's pattern matches every target and rejects every near-miss."""
    assert cases, "pattern case table is empty, so the control asserts nothing"
    failures: list[str] = []
    for case in cases:
        assert case.must_match, f"{case.pattern.pattern!r} declares no target it must match"
        assert case.must_not_match, f"{case.pattern.pattern!r} declares no near-miss it must reject"
        failures.extend(
            f"{case.pattern.pattern!r} failed to match its target {probe!r}"
            for probe in case.must_match
            if not case.pattern.search(probe)
        )
        failures.extend(
            f"{case.pattern.pattern!r} wrongly matched near-miss {probe!r}"
            for probe in case.must_not_match
            if case.pattern.search(probe)
        )
    assert not failures, "scan patterns no longer discriminate:\n" + "\n".join(failures)
