"""Gate: a checked plan Step's execution record must carry a populated Outcome.

The vault-health check validates an execution record's frontmatter, filename,
and links; it does not read whether the record's body *says anything*. A record
scaffolded through ``vaultspec-core vault add exec`` and then left unfilled is
therefore structurally valid and green — its ``## Outcome`` section is empty
between the heading and the following ``## Notes`` heading. Counted by file
existence alone, such a scaffold reads as a completed Step. The honesty property
the whole plan pipeline rests on — a checked Step is backed by real evidence —
is currently enforced by author discipline alone. This gate is the structural
enforcement: a checked Step whose resolved execution record carries an empty
Outcome is a new offender and fails.

Resolution authority. The Step-to-record mapping is NOT re-derived here. The
mapping from a plan's ``(feature, step_id)`` to its execution record is owned by
``vaultspec_core`` — the same package that scaffolds the records and that the
``vaultspec-core status`` verb consumes — and this gate calls that resolver
in-process (``ExecRecordIndex``) exactly once over the whole vault. Re-deriving
the plan-stem-to-exec-directory convention inside a test would be a second,
drifting authority; a plan carrying a narrative topic infix has its records
under a directory named for its feature tag, not its filename, and only the
owning tool knows that reliably. Shelling the CLI per plan was rejected on cost:
one ``status`` subprocess is ~25 s of interpreter startup, so 332 plans is over
two hours, whereas the single in-process ``ExecRecordIndex`` pass is ~30 s.

Scope, stated so a reader does not over-read a green result. This gate fires on
exactly one shape: a *checked* Step whose execution record *exists and resolves*
through the owning tool and whose ``## Outcome`` section is empty. A checked Step
with *no* resolvable record is a different violation, owned by the exec-record
existence check (the ``exec_missing`` axis of ``vaultspec-core status`` and the
``plan-closure-requires-exec-records`` discipline) and deliberately not counted
here. The honest limitation is the same one ``status`` carries: a legacy record
that declares no ``step_id:`` frontmatter, or a record under a plan that fails to
parse, cannot be resolved to its Step by the owning tool and is therefore
invisible to this gate as it is to ``status``. The subject floors below guard
against that invisible set silently swallowing the whole corpus.

Ratchet. The historical debt is large — measured near 1916 offending records at
seeding — and is not this gate's to erase in one pass; a gate that reds the
whole tree on day one is bad citizenship in a shared worktree and gets disabled.
The current offender set is captured as a checked-in baseline that the gate
treats as a ceiling: the offender set may only shrink, and any offender NOT named
in the baseline fails. The baseline is grandfathered debt, not permission — its
entries should be paid down by filling the named records' Outcomes, which shrinks
the set; the gate never requires a baselined record to *stay* empty.

Anti-vacuity. This gate exists because sibling gates in its campaign were
false-green over unproven sets, so it carries its own floors and a hostile probe:
the subject counts (plans scanned, checked Steps examined, records resolved) are
asserted non-zero against plausible floors so a resolution collapse cannot green
the gate by checking nothing, and the classifier is proven directly to flag an
empty/comment-only Outcome and to pass real prose, and to stop at the next
heading so a populated Notes section cannot launder an empty Outcome.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final

import pytest
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.plan.status import ExecRecordIndex
from vaultspec_core.vaultcore.query import list_documents

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# dev/quality/tests/<this file> -> repo root is three parents up.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_BASELINE_PATH: Final[Path] = _REPO_ROOT / "dev" / "quality" / "exec_outcome_baseline.json"

# Anti-vacuity subject floors. Set well below the measured live figures (near 306
# parsed plans, 9400 checked Steps, 6800 resolved records at seeding) so ordinary
# closure activity never trips them, but far enough above zero that a resolution
# collapse — the owning API returning nothing, or every plan failing to parse —
# reds the gate instead of greening it by checking an empty corpus.
_MIN_PLANS_SCANNED: Final[int] = 250
_MIN_CHECKED_STEPS: Final[int] = 5_000
_MIN_RESOLVED_RECORDS: Final[int] = 4_000

_HTML_COMMENT: Final[re.Pattern[str]] = re.compile(r"<!--.*?-->", re.DOTALL)
_ANY_HEADING: Final[re.Pattern[str]] = re.compile(r"^#{1,6}\s")
_OUTCOME_HEADING: Final[str] = "## Outcome"


def _outcome_body(record_text: str) -> str | None:
    """Return the text between the ``## Outcome`` heading and the next heading.

    Returns ``None`` when the record carries no ``## Outcome`` heading at all —
    a record with no Outcome section has no populated Outcome by construction.
    The body stops at the NEXT heading of any level (the template's ``## Notes``
    follows immediately), so a populated Notes section can never bleed into the
    Outcome body and launder an empty Outcome as populated.
    """
    lines = record_text.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if line.strip() == _OUTCOME_HEADING:
            start = index + 1
            break
    if start is None:
        return None
    body: list[str] = []
    for line in lines[start:]:
        if _ANY_HEADING.match(line):
            break
        body.append(line)
    return "\n".join(body)


def _outcome_is_populated(record_text: str) -> bool:
    """A record's Outcome is populated iff it carries prose beyond scaffolding.

    HTML comment hints and whitespace do not count: the scaffolded record ships
    an empty Outcome section (and comment hints in sibling sections), so a naive
    non-empty check would pass every unfilled scaffold — the exact worthless
    behaviour this gate replaces.
    """
    body = _outcome_body(record_text)
    if body is None:
        return False
    return bool(_HTML_COMMENT.sub("", body).strip())


@dataclass(frozen=True)
class _ScanResult:
    """One whole-vault scan of checked Steps against their execution records."""

    offending_record_stems: frozenset[str]
    plans_scanned: int
    plans_unparseable: int
    checked_steps: int
    resolved_records: int


@cache
def _scan_offenders() -> _ScanResult:
    """Resolve every checked Step to its record and classify the Outcome.

    Consumes ``vaultspec_core``'s own ``ExecRecordIndex`` as the authoritative
    ``(feature, step_id) -> record stem`` mapping — the resolution the
    ``vaultspec-core status`` verb reports — rather than re-deriving any
    plan-to-directory path convention. Cached so the ~30 s pass runs once for
    the whole module.
    """
    index = ExecRecordIndex.build(_REPO_ROOT)
    exec_paths = {doc.name: doc.path for doc in list_documents(_REPO_ROOT, doc_type="exec")}

    offending: set[str] = set()
    resolved: set[str] = set()
    plans_scanned = 0
    plans_unparseable = 0
    checked_steps = 0

    for plan_doc in list_documents(_REPO_ROOT, doc_type="plan"):
        try:
            plan = parse_plan(plan_doc.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            plans_unparseable += 1
            continue
        plans_scanned += 1
        feature = plan_doc.feature
        if not feature:
            continue
        for step in plan.steps:
            if not step.checked:
                continue
            checked_steps += 1
            stem = index.record_for(feature, step.canonical_id)
            if stem is None:
                # No resolvable record: the exec-record-existence gate's concern,
                # deliberately out of scope here (see module docstring).
                continue
            record_path = exec_paths.get(stem)
            if record_path is None:
                continue
            resolved.add(stem)
            try:
                record_text = record_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not _outcome_is_populated(record_text):
                offending.add(stem)

    return _ScanResult(
        offending_record_stems=frozenset(offending),
        plans_scanned=plans_scanned,
        plans_unparseable=plans_unparseable,
        checked_steps=checked_steps,
        resolved_records=len(resolved),
    )


def _load_baseline() -> dict[str, object]:
    return json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))


def _baseline_offender_stems() -> frozenset[str]:
    return frozenset(_load_baseline()["offending_record_stems"])


def test_baseline_file_is_well_formed_and_is_debt_not_permission() -> None:
    """The checked-in baseline must exist, be non-empty, and be labelled debt.

    An emptied baseline would still leave the ratchet correct (every current
    offender would fail as unnamed), but the debt would then read as if it had
    been paid rather than grandfathered. The non-empty assertion keeps the
    baseline an honest record of the seeding debt.
    """
    assert _BASELINE_PATH.is_file(), f"missing exec-outcome baseline: {_BASELINE_PATH}"
    baseline = _load_baseline()

    assert "offending_record_stems" in baseline
    assert isinstance(baseline["offending_record_stems"], list)
    assert baseline["offending_record_stems"], "baseline offender list is empty; seed it from the live scan"

    note = str(baseline.get("$schema_note", ""))
    assert "debt" in note.lower(), "the baseline note must state it is grandfathered debt, not permission"


def test_scan_meets_anti_vacuity_subject_floors() -> None:
    """A resolution collapse must red the gate, not green it by checking nothing.

    If the owning resolver returned nothing, or every plan failed to parse, the
    offender set would be empty and the ratchet below would pass vacuously. These
    floors make that collapse a loud failure instead.
    """
    scan = _scan_offenders()
    assert scan.plans_scanned >= _MIN_PLANS_SCANNED, (
        f"only {scan.plans_scanned} plans parsed (floor {_MIN_PLANS_SCANNED}); "
        f"{scan.plans_unparseable} failed to parse — the scan corpus collapsed, so a green "
        "ratchet would mean 'nothing was checked' rather than 'nothing is wrong'"
    )
    assert scan.checked_steps >= _MIN_CHECKED_STEPS, (
        f"only {scan.checked_steps} checked Steps examined (floor {_MIN_CHECKED_STEPS}); "
        "the Step-to-record resolution collapsed"
    )
    assert scan.resolved_records >= _MIN_RESOLVED_RECORDS, (
        f"only {scan.resolved_records} execution records resolved (floor {_MIN_RESOLVED_RECORDS}); "
        "the record index collapsed"
    )


def test_no_new_empty_outcome_offender() -> None:
    """No checked Step's record may carry an empty Outcome unless already baselined.

    This is the load-bearing assertion. A newly-checked Step whose record is a
    bare scaffold — Outcome empty — is a new offender absent from the baseline
    and fails here, which is precisely the honesty property the vault-health
    check cannot enforce.
    """
    current = _scan_offenders().offending_record_stems
    baseline = _baseline_offender_stems()

    new_offenders = sorted(current - baseline)
    assert new_offenders == [], (
        "checked Step(s) whose execution record carries an EMPTY Outcome section "
        "(only whitespace and/or HTML comment scaffolding), and which are not named in "
        f"{_BASELINE_PATH.name}. Fill the Outcome with the evidence for the Step — the "
        "command, its result, and the HEAD it ran against — before checking the Step, or "
        "un-check the Step:\n  " + "\n  ".join(new_offenders)
    )


def test_offender_count_does_not_exceed_baseline() -> None:
    """The offender set may only shrink; a count regression fails here.

    Kept alongside the set-difference gate so paying down one offender while
    introducing another (which keeps the count flat) is still caught by the
    set-difference check, and a bare count regression is caught here.
    """
    current = _scan_offenders().offending_record_stems
    baseline = _baseline_offender_stems()
    assert len(current) <= len(baseline), (
        f"empty-Outcome offender count regressed: {len(current)} current > {len(baseline)} baselined. "
        f"Every offender must be a named entry in {_BASELINE_PATH.name}, or (preferably) fixed by "
        "filling the record's Outcome, which shrinks the set."
    )


# ---------------------------------------------------------------------------
# Hostile probe: prove the classifier discriminates, on synthetic records.
# ---------------------------------------------------------------------------

_SCAFFOLD_EMPTY_OUTCOME: Final[str] = (
    "# Some Step heading\n"
    "\n"
    "## Scope\n"
    "\n"
    "- `src/module.py`\n"
    "\n"
    "## Description\n"
    "\n"
    "<!-- Succinct line-by-line list of steps executed. -->\n"
    "\n"
    "## Outcome\n"
    "\n"
    "## Notes\n"
    "\n"
    "<!-- Incidents. Data loss. -->\n"
)

_COMMENT_ONLY_OUTCOME: Final[str] = (
    "# Step\n\n## Outcome\n\n<!-- fill me in with the command, the collected count, and the HEAD SHA -->\n\n## Notes\n"
)

_POPULATED_OUTCOME: Final[str] = (
    "# Step\n\n## Outcome\n\nSATISFIED. Ran the gate at HEAD abc123; 6 collected, exit 0.\n\n## Notes\n"
)

_NO_OUTCOME_HEADING: Final[str] = "# Step\n\n## Description\n\nDid a thing.\n\n## Notes\n"

_EMPTY_OUTCOME_BUT_POPULATED_NOTES: Final[str] = (
    "# Step\n\n## Outcome\n\n## Notes\n\nA great deal of prose lives here, but the Outcome above is empty.\n"
)


def test_classifier_flags_empty_and_comment_only_outcomes() -> None:
    """A whitespace-only or comment-only Outcome is NOT populated.

    This is the assertion that proves the classifier does the work the vault
    health check does not: it refuses the exact bare-scaffold shape the CLI
    emits.
    """
    assert _outcome_is_populated(_SCAFFOLD_EMPTY_OUTCOME) is False
    assert _outcome_is_populated(_COMMENT_ONLY_OUTCOME) is False
    assert _outcome_is_populated(_NO_OUTCOME_HEADING) is False


def test_classifier_passes_a_real_prose_outcome() -> None:
    """A record whose Outcome carries real prose is populated."""
    assert _outcome_is_populated(_POPULATED_OUTCOME) is True


def test_classifier_does_not_launder_an_empty_outcome_with_populated_notes() -> None:
    """A populated Notes section cannot rescue an empty Outcome.

    The Outcome body stops at the next heading, so prose under ``## Notes`` is
    never read as Outcome content. Without this, every scaffold whose author
    filled only Notes would falsely pass.
    """
    assert _outcome_is_populated(_EMPTY_OUTCOME_BUT_POPULATED_NOTES) is False
    body = _outcome_body(_EMPTY_OUTCOME_BUT_POPULATED_NOTES)
    assert body is not None
    assert "prose lives here" not in body
