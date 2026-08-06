---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:4c2a64642ae16c8094256db529a7b77b08b036b8a30d8766b304e218fd191789'
step_id: 'S07'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
  - "[[2026-07-25-test-harness-honesty-adr]]"
---

# VERIFIED-SOUND RECORD, the majority of the audited gate surface carries genuine positive controls, recorded so a later audit does not re-derive the same negative result

## Scope

- `.vault/audit/2026-07-25-test-harness-honesty-false-green-gates-audit.md`

## Description

- Carry the audit's negative result forward as a record so a later pass does not re-derive it.
- Re-confirm the two gate families this session touched directly rather than accepting the whole surface on the audit's word.
- Name the surface that remains unexamined so the record cannot be read as broader coverage than it is.

## Outcome

Verified sound, and carried forward as a record so a later audit does not spend a pass re-deriving the same negative result.

The audited surface holds genuine positive controls. The zero-tolerance detectors for mocks, monkeypatching, skip and xfail markers, and tautological assertions each carry parametrized positive and negative controls plus a discovery guard asserting the walk actually found modules. The enrollment and rationale inventories share a real recursive-glob substrate whose emptiness would fail loudly in a separate membership gate asserting concrete known paths. The import-hygiene gate uses set equality rather than a bare count ceiling, so a count cannot mask an unnamed new violation. The ledger corpus fidelity gate asserts a minimum built-row count and validates every row through the real model. The deselection-banner and acceptance-wall gates are proven by real pytest subprocesses, and the acceptance-wall gate carries a genuine anti-tautology proof that mutates a real assertion and asserts the subprocess fails.

Two families were re-confirmed directly this session rather than accepted on the audit's word, both green at the recorded commit. The duplication authority's own gates pass, and its single-runner gate now walks the whole git-tracked tree rather than the development subtree, so a scanner reintroduced in the build recipe or a shell script is caught. The storage namespace adoption gate carries non-empty authority assertions and four controls covering an injected redeclaration, one reached through a module constant, one passed positionally, and a definition-sourced fragment that must stay clean.

An honest negative also belongs here. An exhaustive sweep of documented run commands found no documented invocation that collects zero tests and exits green; every one either carries an explicit marker expression or targets modules whose markers match the default. That negative is only meaningful because each command's collected count was measured rather than inferred.

What this record does NOT claim: it is a statement about the surface the audit examined, not about every gate in the tree. The breadth question is the separate sweep tracked as S08, and the coverage verdict belongs there.

## Notes

Semantic code search was degraded throughout this session and reported itself healthy: the code index held 188 sections against roughly 4546 files, with an available status and an empty degraded-reasons list. That is a regression from the roughly 1027 sections recorded when S01 landed. Two deliberately unrelated probes returned the same file at noise-level similarity, which is the behavioural field test the audit prescribes for a truncated index.

The vault index was healthy at 16121 documents and was used for grounding. It earned its place twice here, surfacing two closed successor plans whose steps duplicate open steps in the tracking plan; without it both would have been re-implemented as new work.

Discovery for this step was otherwise by direct reads and targeted search. Tracked as S02 and S03 of this plan, both external to this repository.
