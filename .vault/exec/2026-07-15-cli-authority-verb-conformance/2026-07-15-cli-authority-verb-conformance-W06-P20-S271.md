---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S271'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Assert structurally that an execution record carries a populated Outcome before its Step may be checked, since the vault check passes empty scaffolds

## Scope

- `.vault/exec/`

## Description

- Add a repository-hygiene gate under the established `.vault`-aware quality-gate
  home that classifies a checked plan Step as an offender when its resolved
  execution record carries an empty Outcome section.
- Consume the owning tool's authoritative Step-to-record resolution in-process,
  once over the whole vault, rather than re-deriving any plan-to-directory path
  convention or shelling the status verb 332 times.
- Extract the Outcome section between its heading and the next heading, and
  classify it populated only when prose survives stripping HTML comment hints
  and whitespace.
- Capture the current offender set as a grandfathered, shrink-only checked-in
  baseline that the gate treats as a ceiling, failing on any offender not named
  in it.
- Give the gate three anti-vacuity subject floors, a hostile classifier probe,
  and a Notes-does-not-launder-Outcome probe, so a resolution collapse reds the
  gate rather than greening it over an empty corpus.

## Outcome

SATISFIED.

The honesty property this campaign rests on — a checked Step is backed by real
evidence — is now structurally enforced rather than left to author discipline.
The gate lives at `dev/quality/tests/test_exec_outcome_populated.py` with its
committed baseline `dev/quality/exec_outcome_baseline.json`. It lands in the CI
unit lane: `ci.yml` and `ci-full.yml` run `pytest ... -m "unit or (integration
and not serial)" ... dev/quality/tests` under a 900 s timeout, and the module
is marked `unit`/`hex_core` (the marker-integrity contract requires exactly one
`hex_*` marker; `hex_core` is the established convention for dev-tooling gates).

Resolution authority. The Step-to-record mapping is the owning package's own,
consumed in-process via `ExecRecordIndex.build`, the same resolution the status
verb reports. Re-deriving the plan-stem-to-exec-directory convention was
rejected as a second drifting authority, and shelling the status verb per plan
was rejected on cost: one status subprocess measured ~25 s of interpreter
startup, so 332 plans is over two hours, against ~15 s for the single in-process
pass.

Scope, stated so a green result is not over-read. The gate fires on exactly one
shape: a checked Step whose record resolves through the owning tool and whose
Outcome section is empty. A checked Step with no resolvable record is a distinct
violation owned by the exec-record-existence axis (`exec_missing`) and is
deliberately not counted here. The honest limitation matches the status verb's
own: a legacy record with no `step_id` frontmatter, or a record under a plan
that fails to parse, is unresolvable to its Step and therefore invisible to this
gate exactly as it is to status. The subject floors guard against that invisible
set swallowing the corpus.

Measured baseline (method: the gate's own scan function run once over the vault,
offenders deduplicated by unique record file):

- 306 plans parsed of 332; 26 failed to parse and were skipped (surfaced by the
  `plans_scanned` floor).
- 9416 checked Steps examined; 6827 distinct records resolved.
- 1916 distinct offending records (checked Step, record exists, Outcome empty)
  seeded into the baseline as debt-not-permission.

The 306-versus-1916 shape confirms the audit's `w06-evidence-not-produced`
finding at tree scale: roughly 28 percent of records the tool can resolve carry
no Outcome prose despite their Step being checked.

Mutation results (every assertion broken in a throwaway probe, no file edited,
no transient red visible to a peer; each confirmed to red):

- Baseline non-empty: emptied offender list — RED. Note lacking "debt" — RED.
  Missing baseline file — RED.
- Subject floors: `plans_scanned`, `checked_steps`, `resolved_records` each
  forced to zero — RED for each.
- No-new-offender: a planted stem absent from the baseline injected into the
  current set — RED.
- Count ceiling: baseline shrunk below the current count — RED.
- Classifier flags empty: `_outcome_is_populated` forced to always-True — the
  empty/comment-only and the empty-with-populated-Notes assertions both RED.
- Classifier bleed: `_outcome_body` forced to return Notes prose — the
  no-launder assertion RED.
- Classifier passes prose: `_outcome_is_populated` forced to always-False — the
  real-prose assertion RED.

All thirteen mutation cases red as expected; the positive direction is proven by
the unmutated suite passing.

Gate run at HEAD `47fbc9ab9461fefec4b57adb7e1bd334e2e9879b`:

- Command: `uv run --no-sync pytest dev/quality/tests/test_exec_outcome_populated.py -p no:cacheprovider -n0`
- Collected: 7 items (non-zero; not the "no tests ran" false green).
- Exit line: `7 passed in 14.40s` (exit 0).
- Also run under the exact CI lane invocation `pytest -q -n 8 --timeout=900 -m
  "unit or (integration and not serial)" dev/quality/tests/test_exec_outcome_populated.py`:
  `7 passed`, exit 0, confirming it participates in the lane rather than being
  silently deselected.

Lint: `ruff check` and `ruff format --check` both clean on the gate file.

## Notes

The offender identity is the unique record file, not the checked Step. The
owning tool's index is feature-keyed, so several same-feature plans resolve
their like-numbered Steps to one shared record; counting per Step inflated the
raw offender list roughly eightfold on multi-Step legacy records. The subject of
the Step is "the record carries a populated Outcome", and a file is populated or
not once, so deduplicating by record stem is the faithful count.

One correction to the brief. The brief estimated roughly 4140 records with a
populated Outcome and 1545 empty; the measured figures are 6827 resolved records
and 1916 empty (deduplicated). The brief's numbers came from an unreliable first
pass through a re-derived path mapping; the tool-resolved figures supersede
them. The brief's estimate of ~9438 checked Steps is confirmed at 9416.

The baseline is a ceiling that only shrinks; it is deliberately not required to
stay in lock-step with the live offender set, because filling a baselined
record's Outcome is exactly the intended pay-down and must not red the gate. A
peer commit advanced HEAD during the work and the gate stayed green at the new
HEAD, which is the correct ceiling behaviour: only a genuinely new empty-Outcome
closure reds it.

Not addressed here, and left to their own Steps: the 2074-ish checked Steps with
no resolvable record (the exec-record-existence concern, `exec_missing`), and the
26 unparseable plans. Both are surfaced through the subject floors rather than
silently swallowed, but neither is this gate's to fix.
