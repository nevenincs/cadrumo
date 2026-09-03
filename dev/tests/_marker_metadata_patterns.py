"""Scan-pattern tables for the campaign- and process-metadata marker gates.

:mod:`.test_marker_integrity` walks every test module's comments, docstrings,
and durable symbol/pytest-id names for this repo's own process history (a
numbered campaign-container id, a dated decision-record filename, a fixed
process-review phrase) — the leak `aeat-architecture-boundaries` and the vaultspec
"Code Stands Alone" mandate forbid. This module holds the declarative half of
that gate: the pattern/target/near-miss triples plus the small helpers that
apply and prove them. It is genuinely separable from the AST walk that uses
it, since none of it touches a module tree — it is scan data.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import NamedTuple


class MarkerScanScope(StrEnum):
    """How far across the tree one scan pattern is allowed to reach.

    The scan runs one mechanism over two module populations, and the two do
    not tolerate the same patterns. Test modules are scanned by every pattern.
    Production modules are scanned only by the patterns whose false-positive
    rate over real source is zero, because a pattern that fires on ordinary
    domain prose trains every reader to ignore the gate, and an ignored gate
    reports exactly what a clean tree reports.

    A measured example of the asymmetry, over the 1485 non-test modules under
    ``src/cadrumo``: the dated-document-stem pattern found only genuine
    document-identifier citations, while the ``phase`` pattern's hits were
    almost entirely legitimate — a Spanish tax-law ``RD-ley 4/2024 phase-out``,
    a two-phase custody protocol, a state machine's own target-phase
    vocabulary. Scope is therefore declared per pattern, beside the pattern,
    rather than chosen once for the whole table.
    """

    #: Scanned in test modules only.
    TEST_MODULES = "test_modules"
    #: Scanned in test modules and in ordinary production source.
    TEST_AND_PRODUCTION_MODULES = "test_and_production_modules"


class PatternCase(NamedTuple):
    """A scan pattern bound to the evidence that it still measures.

    A pattern that cannot match is indistinguishable from a clean tree: the
    scan reports nothing either way. Binding the probes to the pattern at its
    declaration is what stops a new pattern arriving without the controls
    proving it discriminates, and it is how a token scrambled while being
    split across a concatenation stops reading as a clean result.

    ``scope`` declares which module population the pattern is applied to; see
    :class:`MarkerScanScope`. It defaults to the narrower reach, so a new
    pattern arrives test-scoped and widening it is a deliberate edit backed by
    a measurement.
    """

    pattern: re.Pattern[str]
    must_match: tuple[str, ...]
    must_not_match: tuple[str, ...]
    scope: MarkerScanScope = MarkerScanScope.TEST_MODULES


CAMPAIGN_METADATA_CASES: tuple[PatternCase, ...] = (
    PatternCase(
        re.compile(r"\btest_w\d+_p\d+", re.IGNORECASE), ("def test_w01_p02_thing",), ("def test_workbook_parity",)
    ),
    # Production-scoped on a measurement rather than on judgement: across the
    # 1953 non-test modules under ``src/cadrumo`` this shape hit exactly one
    # site, a campaign address in a comment, and an exhaustive read of that hit
    # found nothing a tax module could legitimately want. The whole risk sits in
    # the near-miss below -- a bare ``W`` and digits is otherwise ordinary prose
    # -- and the control already discriminates it.
    PatternCase(
        re.compile(r"\bW\d{1,3}(?:\.P\d{1,3})?(?:\.S\d{1,4})?\b"),
        ("carried in W01.P02.S03",),
        ("the W3C standard",),
        scope=MarkerScanScope.TEST_AND_PRODUCTION_MODULES,
    ),
    # Production-scoped with its sibling above: the dotted phase-step pair is
    # unambiguous, and the same tree-wide read found no legitimate use of it.
    PatternCase(
        re.compile(r"\bP\d{1,3}\.S\d{1,4}\b"),
        ("see P02.S14",),
        ("only P02 here",),
        scope=MarkerScanScope.TEST_AND_PRODUCTION_MODULES,
    ),
    # Production-scoped last of the three step-notation cases, and deliberately
    # after its siblings rather than with them: this shape collides with ruff's
    # own rule codes, so it could only be widened once the suppression stripper
    # handled the file-level suppression form as well as the trailing one. With
    # that in place the pattern finds ZERO production hits across the tree,
    # measured through the stripper the gate itself runs -- the earlier figure of
    # 68 files was 55 file-level suppressions the stripper could not yet see,
    # plus the genuine sites since swept.
    PatternCase(
        re.compile(r"\bS\d{2,4}\b"),
        ("closed by S08",),
        ("the S1 bucket",),
        scope=MarkerScanScope.TEST_AND_PRODUCTION_MODULES,
    ),
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
    # ``wave`` is a process container here, but it is also an ordinary English
    # verb, and the bare word could not tell them apart: it fired on "a loosened
    # check would wave through" in a positive-control docstring, which names no
    # campaign container at all. The process sense is always a NOUN, so it is
    # either numbered ("wave 2") or referred back to by a determiner ("the
    # second wave"), exactly as the bare-``Step`` entry below is anchored. The
    # verb takes neither, and ``waveform`` and ``microwave`` are untouched.
    PatternCase(
        re.compile(r"\b[Ww]ave\s+\d+\b|\b(?:[Tt]his|[Tt]he)(?:\s+\w+(?:-\w+)*){0,2}\s+[Ww]ave\b"),
        ("the second wave landed", "carried in wave 2", "this wave closes the gap"),
        ("waveform analysis", "the one a loosened check would wave through", "microwave heating"),
    ),
    PatternCase(re.compile(r"\bAD" + r"R\b"), ("recorded in the ADR",), ("address parsing",)),
    PatternCase(re.compile(r"\bP" + r"R\b"), ("landed in PR",), ("PRINT mode",)),
    # Narrowed to a numbered or lettered phase. The letter class this entry
    # started with accepted any following word, so it fired on ``RD-ley 4/2024
    # phase-out`` -- a Spanish tax-law term this domain owns and must be able to
    # write. The same over-reach is why this family is test-scoped rather than
    # production-scoped (see :class:`MarkerScanScope`); the tax term reaches test
    # docstrings too, so the narrowing belongs on the pattern. A campaign phase
    # is identified, never merely described, so ``phase-2`` and ``Phase B`` stay
    # caught while ``phase-out``, ``phase-in`` and ``two-phase custody`` do not.
    PatternCase(
        re.compile(r"\b[Pp]hase[- ](?:\d|[A-Z]\b)"),
        ("phase-2 rollout", "Phase B carried it"),
        ("phases of the moon", "the RD-ley 4/2024 phase-out rates", "a phase-in period", "two-phase custody"),
    ),
    # Originally only ``.vault/adr`` -- a real audit citation under
    # ``.vault/reference/`` shipped in a test-module docstring and passed this
    # gate clean, because the pattern covered one of the vault's seven
    # subdirectories and missed the other six. Widened to the full set
    # (adr, audit, exec, index, plan, reference, research); "ad" + "r" stays
    # split for the same self-match reason as every other entry in this table.
    #
    # Production-scoped, on the same evidence as the dated-stem entry below: a
    # literal vault PATH is the most direct form of the citation the mandate
    # reverses, it carries no domain meaning a tax module could want, and the
    # exhaustive read over the non-test modules under ``src/cadrumo`` found no
    # legitimate use. The near-misses are what keep the reach honest -- prose
    # that merely mentions a vault, a reference implementation or an audit
    # trail names no document and stays clean.
    PatternCase(
        re.compile(r"\.vault/(?:ad" + r"r|audit|exec|index|plan|reference|research)\b", re.IGNORECASE),
        (
            "see .vault/adr/x",
            "cite .vault/audit/x",
            "cite .vault/exec/x",
            "cite .vault/index/x",
            "cite .vault/plan/x",
            "cite .vault/reference/2026-05-15-linkage-design-audit-reference.md",
            "cite .vault/research/x",
        ),
        ("the vault adr folder", "the reference implementation lives in the vault", "review the audit trail"),
        scope=MarkerScanScope.TEST_AND_PRODUCTION_MODULES,
    ),
    # Scanned in ordinary production source as well as in tests.
    # A dated document stem NAMES a specific record in this repo's own vault,
    # which is the citation direction "Code Stands Alone" reverses, and the
    # shape carries no domain meaning a tax module could want: the exhaustive
    # read of every hit across 1485 production modules found no legitimate use.
    #
    # Deliberately narrower than the bare-word entry above it, which bans the
    # token even where no document is named ("needs a superseding ADR"). That
    # entry is broader than the rule's text -- the rule permits stating the
    # constraint and forbids naming the document -- and the tension is
    # unresolved, so the bare word stays test-scoped rather than being widened
    # on an unruled reading.
    PatternCase(
        re.compile(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}[-_a-z0-9]*(?:ad" + r"r|audit|plan|reference|research)\b",
            re.IGNORECASE,
        ),
        (
            "2026-07-25-thing-adr",
            "2026-07-25-thing-audit",
            "2026-07-25-thing-plan",
            "2026-07-25-thing-reference",
            "2026-07-25-thing-research",
        ),
        ("2026-07-25 release notes",),
        scope=MarkerScanScope.TEST_AND_PRODUCTION_MODULES,
    ),
    # Every pattern above is blind to a bare NARRATIVE reference to this
    # repo's own campaign -- no digit, no dotted id, no document stem. Bare
    # "campaign" is not itself bannable: the release/packaging domain names a
    # real CI job "campaign" (``dev/packaging/campaign.py``, the workflow's
    # own ``campaign`` job id), so "the campaign's own CI already checks" and
    # "a foreign, failed ... campaign's cohort" are genuine engineering
    # vocabulary, not process narration. Only the first-person possessive
    # forms are unambiguous: nothing in this codebase's CI or packaging domain
    # calls its own job "this campaign" or "our campaign".
    PatternCase(
        re.compile(r"\b(?:this|our) campaign\b", re.IGNORECASE),
        ("this campaign's own research records show it", "our campaign has been finding these leaks"),
        ("the campaign's own CI already checks", "a marketing campaign was launched this spring"),
    ),
    # A bare, undigited "Step" survives every numbered pattern above.
    # Capitalisation is the only signal this repo's own prose gives: a
    # mid-sentence "Step" capitalised and anchored by a determiner ("this
    # Step", "the prior Step", "the first cloud-deletion Step") is this
    # repo's own plan-Step vocabulary -- ordinary English never capitalises
    # the noun mid-sentence. Lowercase "step" is untouched, and so is a
    # sentence-initial "Step" used as a modifier rather than referred back to
    # (a wizard's own "Step discovery reads the registry", with no determiner
    # in front of it). The hyphen guard keeps a genuine "Step-by-step"
    # adjective phrase out.
    PatternCase(
        re.compile(r"\b(?:[Tt]his|[Tt]he)(?:\s+\w+(?:-\w+)*){0,2}\s+Step(?!-)\b"),
        ("this Step exists to remove the gap", "before the first cloud-deletion Step closes"),
        ("Step discovery reads the registry", "the difficult Step-by-step tutorial walkthrough"),
    ),
)
CAMPAIGN_METADATA_PATTERNS = tuple(case.pattern for case in CAMPAIGN_METADATA_CASES)
#: The production-scoped subset, DERIVED from the one table rather than listed.
#:
#: A hand-maintained second list would drift from the scope each case declares,
#: and the drift direction that matters is silent: a case widened at its
#: declaration but absent here is simply never applied to production, which
#: reads as a clean production tree.
PRODUCTION_SCOPED_CAMPAIGN_METADATA_CASES: tuple[PatternCase, ...] = tuple(
    case for case in CAMPAIGN_METADATA_CASES if case.scope is MarkerScanScope.TEST_AND_PRODUCTION_MODULES
)
PRODUCTION_SCOPED_CAMPAIGN_METADATA_PATTERNS = tuple(case.pattern for case in PRODUCTION_SCOPED_CAMPAIGN_METADATA_CASES)
#: Ruff writes suppressions in two shapes and both carry rule codes that look
#: exactly like a campaign step id. The trailing form suppresses one line and
#: puts the directive straight after the hash; the file-level form sits at
#: module top and inserts the tool name between the hash and the directive,
#: as in hash-space-``ruff:``-space-directive. Anchoring on a hash immediately
#: followed by the directive sees only the first shape, so all 49 file-level
#: suppressions in this tree read as campaign metadata -- which is what kept
#: the bare-``S``-code pattern from being production-scoped, because those
#: false positives swamped the genuine hits.
_NOQA_LINT_CODE_PATTERN = re.compile(
    r"(#\s*(?:[a-z][a-z0-9_]*\s*:\s*)?noqa(?::\s*)?)([A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)",
)
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
#: Process uses of ``phase`` that must not name a durable test symbol or pytest id.
#:
#: Narrower than a bare-token ban, for the same reason :data:`PROCESS_PLAN_CASE`
#: is: the word is not free here. ``phase`` is production domain vocabulary —
#: ``_HandoverPhase`` names the login-handover state machine's states and
#: ``OperationPhaseEvent`` the operation executor's — so a bare ban flags the
#: state machines' own tests for using the word their subject uses. A plan
#: container is numbered or bound to its sibling containers, and that is what
#: separates it from a state a machine actually occupies.
PROCESS_PHASE_CASE = PatternCase(
    re.compile(
        r"(^|[_-])pha" + r"se[_-]?(?:\d+|step|wave)($|[_-])|(^|[_-])(?:wave|plan)[_-]pha" + r"se($|[_-])", re.IGNORECASE
    ),
    ("test_phase_1_rollout", "_phase2_migration", "test_wave_phase_ordering", "_phase_step_id"),
    ("test_phases_of_moon", "_crash_at_handover_phase_child", "test_handover_phase_receipt", "_read_journal_phase"),
)
PROCESS_SYMBOL_METADATA_CASES: tuple[PatternCase, ...] = (
    PatternCase(re.compile(r"(^|[_-])ad" + r"r($|[_-])", re.IGNORECASE), ("test_adr_probe",), ("test_address_parse",)),
    PROCESS_PHASE_CASE,
    PatternCase(
        re.compile(r"(^|[_-])wa" + r"ve($|[_-])", re.IGNORECASE),
        ("test_wave_rollup",),
        ("test_waveform_probe",),
    ),
    PROCESS_PLAN_CASE,
    PatternCase(re.compile(r"(^|[_-])p" + r"r($|[_-])", re.IGNORECASE), ("test_pr_review",), ("test_print_payload",)),
    # The bare step id in a durable symbol name, which none of the siblings
    # above reach: they name process NOUNS, and this form is an address. Two to
    # three digits, deliberately: it admits the whole live step range while
    # leaving a single digit to the domain, so an AWS bucket test keeps its
    # name. The comment beside the lint-code pattern explains why the bare form
    # was never production-scoped; nothing had scoped it for symbols either,
    # which is how fourteen files came to carry one.
    PatternCase(
        re.compile(r"(^|[_-])s\d{2,3}($|[_-])", re.IGNORECASE),
        ("test_s115_freezes_the_reviewed_helper_set",),
        ("test_s3_client_retries",),
    ),
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


def lint_codes_suppressed_in(module_text: str) -> frozenset[str]:
    """Return every lint code this module suppresses through a noqa directive.

    Scrubbing the directive is not enough on its own. A suppression is usually
    explained in prose beside it - "hence the S603" - and that sentence carries
    the code without carrying the directive, so a line-scoped scrub reports the
    explanation as campaign metadata. It also wraps, which is why the sentence
    cannot be recognised by looking at one line.

    A module that suppresses a code has established what that token means
    inside it, so prose naming the same code is explaining the suppression
    rather than addressing a plan step. The judgement is per module and needs
    the whole text, which is why this is separate from the token-level scrub.
    """
    return frozenset(
        code.strip()
        for match in _NOQA_LINT_CODE_PATTERN.finditer(module_text)
        for code in match.group(2).split(",")
    )


def campaign_metadata_findings(module_text: str, cases: tuple[PatternCase, ...]) -> tuple[str, ...]:
    """Return the campaign markers in one module's text, less its own lint vocabulary."""
    suppressed = lint_codes_suppressed_in(module_text)
    found: list[str] = []
    for line in module_text.splitlines():
        scrubbed = campaign_metadata_scan_text(line)
        for case in cases:
            match = case.pattern.search(scrubbed)
            if match is not None and match.group(0).strip() not in suppressed:
                found.append(match.group(0).strip())
                break
    return tuple(found)


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
