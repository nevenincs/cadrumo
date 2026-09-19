---
tags:
  - '#research'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:b87af1e172ab7acc6f6902812516c3daabc1b97a6ac17e6b9ad4399f8476d68e'
related:
  - "[[2026-07-14-honest-all-green-adr]]"
  - "[[2026-07-17-duplication-evidence-repair-adr]]"
  - "[[2026-07-17-duplication-evidence-repair-plan]]"
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# `duplication-burndown` research: `honest clone closure`

The decision boundary is whether honest closure means no token clones, no
unexplained semantic duplication, or merely a disposition for each observed
token clone. These are not equivalent: the installed detector can prove the
first only within `src/cadrumo`, explicitly cannot prove the second, and the
third leaves the health dashboard amber. Evidence therefore favors a two-axis
closure contract—detector-observed zero plus a separately evidenced semantic
review—but the ADR must decide whether intentional token repetition can remain
and, if so, whether an entirely green dashboard is still a campaign goal.

## Findings

### Zero textual clones is the only existing route to a green D2 verdict

The single runner classifies a successful scan as `OBSERVED_ZERO`, `CLONES`,
or `UNAVAILABLE`; zero is valid only when at least one file was inspected
(`dev/audit/duplication.py:12`, `dev/audit/duplication.py:135`). The health
report maps only `OBSERVED_ZERO` to green and maps every positive clone count
to amber (`dev/audit/report.py:190`). A live `just audit-duplication` execution
on 2026-09-03 reported 52 clusters across 1,964 files, so disposition-only
closure cannot make the current dashboard green without changing that
contract. The active burndown plan independently scopes elimination of every
currently observed production clone from one stable evidence set
(`.vault/plan/2026-09-03-duplication-burndown-plan.md:22`).

This option gives an objective end condition and matches the existing
dashboard. Its limit is material: `jscpd@4.2.0` compares token sequences, scans
only `src/cadrumo`, and ignores test and data paths
(`dev/audit/duplication.py:35`, `dev/audit/duplication.py:45`,
`dev/audit/duplication.py:83`). It can therefore reach textual zero while a
concept remains implemented twice with different syntax.

### Zero unexplained semantic duplication is broader but needs a second proof

The runner documents a prior case where five Ledger projections repeated one
casilla fold using syntactically different loops and were not detected
(`dev/audit/duplication.py:45`). Semantic closure would inspect each textual
candidate for shared authority and also search for duplicate concepts outside
the detector's token-matching envelope. This aligns with the repository's
concern about duplicate authority, not merely similar text, but no current
result type or dashboard dimension records that proof: the runner owns only
jscpd execution and parsing (`dev/audit/duplication.py:2`) and D2 delegates to
that result unchanged (`dev/audit/report.py:190`).

This option is strongest against architectural overlap, but “zero semantic
duplication” is not independently reproducible unless the ADR specifies the
inventory, reviewer evidence, scope, and accepted non-substitutability test.
It cannot replace the token scan because semantic review alone would lose the
runner's reproducible regression signal.

### Disposition-only closure preserves judgment but does not satisfy all-green

The accepted evidence-repair decision deliberately keeps clone count advisory
and accepts measured amber as honest closure
(`.vault/adr/2026-07-17-duplication-evidence-repair-adr.md:25`). Its completed
plan requires one `cluster-owned`, `intentional`, or `advisory-residue`
disposition per observed group and explicitly says the goal is evidence rather
than zero clones (`.vault/plan/2026-07-17-duplication-evidence-repair-plan.md:27`,
`.vault/plan/2026-07-17-duplication-evidence-repair-plan.md:52`). The historical
registry existed immediately before commit
`23eadb38842c9b95a809b5df085cf47ef30fbc02`; that commit deleted it in a
241,725-line, 1,285-file change, while its parent recorded four groups—three
intentional PEP 562 module-local hooks and one inconsistent summary count
(`git show 23eadb38842c9b95a809b5df085cf47ef30fbc02^:dev/audit/duplication_dispositions.toml`).

Disposition-only closure is useful as lossless triage and prevents forced
abstractions where implementations are not substitutable. It is insufficient
as the campaign's sole closure rule because it neither changes the existing
amber D2 result nor examines semantic duplication invisible to jscpd. Treating
the registry as an allowlist that suppresses detected groups would also
conflict with the accepted prohibition on baseline and allowlist mutes
(`.vault/adr/2026-07-14-honest-all-green-adr.md:59`).

### The governing records require an explicit ADR reconciliation

The honest-all-green decision requires root-cause fixes and forbids weakening
gates (`.vault/adr/2026-07-14-honest-all-green-adr.md:27`,
`.vault/adr/2026-07-14-honest-all-green-adr.md:59`), while the evidence-repair
decision intentionally permits amber. The new plan asks for both clone
elimination and repository-wide honest health
(`.vault/plan/2026-09-03-duplication-burndown-plan.md:22`). The ADR must settle:

- whether D2 green remains literal token-clone zero;
- whether semantic-review evidence is an additional closure gate;
- whether a demonstrably non-substitutable textual clone is refactored,
  remains visible amber, or changes the campaign's dashboard objective; and
- whether disposition records are review evidence only, never suppression.

The evidence favors keeping the detector's literal green semantics and using
dispositions as an adjudication ledger, while requiring a separate bounded
semantic review. This research does not decide how intentional repetition
affects final campaign status.

### Investigation boundary

This research did not adjudicate any of the 52 live groups, design shared
helpers, alter detector thresholds, or evaluate duplication in `dev/`, tests,
generated data, or documentation. Those actions belong to execution after the
ADR fixes the closure contract.

## Sources

- `.vault/adr/2026-07-14-honest-all-green-adr.md:27`
- `.vault/adr/2026-07-14-honest-all-green-adr.md:59`
- `.vault/adr/2026-07-17-duplication-evidence-repair-adr.md:25`
- `.vault/plan/2026-07-17-duplication-evidence-repair-plan.md:27`
- `.vault/plan/2026-07-17-duplication-evidence-repair-plan.md:52`
- `.vault/plan/2026-09-03-duplication-burndown-plan.md:22`
- `dev/audit/duplication.py:2`
- `dev/audit/duplication.py:12`
- `dev/audit/duplication.py:35`
- `dev/audit/duplication.py:45`
- `dev/audit/duplication.py:83`
- `dev/audit/duplication.py:135`
- `dev/audit/report.py:190`
- commit `23eadb38842c9b95a809b5df085cf47ef30fbc02`
- `git show 23eadb38842c9b95a809b5df085cf47ef30fbc02^:dev/audit/duplication_dispositions.toml`
- `just audit-duplication`, executed 2026-09-03 in
  `Y:/code/cadrumo-worktrees/main` against the live shared worktree
