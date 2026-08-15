---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:bd83629fed270c46daadfda1b0aeaf81c0b128f6fafc3a358c0ad12953c6556d'
step_id: 'S86'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule on the two test modules that cannot be collected in ANY lane because they raise a registry validation error at import, several modelos declaring neither an export layout nor an authority grade, so those tests have not run for as long as that has been true while a collection error reads as infrastructure noise and gets scrolled past, and establish whether this is expected transient state of the registry buildout or a defect that needs its own owner

## Scope

- `src/cadrumo/application/calculations/tests/ and src/cadrumo/application/modelo/tests/`

## Description

- Reproduced collection of both named packages plain, under `-m integration`, and under `-m "not integration"`.
- Reproduced collection of `dev/registry/tests`, the package the campaign-sequencing audit measured the same defect class against.
- Traced the failing mechanism the row describes to the registry authority-grade and export-layout validators, and located the repair commits in `git log`.
- Located the dedicated gate that proves full-corpus collectability, read its docstring and CI wiring, and confirmed it is deliberately excluded from every routine local and CI lane.

## Outcome

The row's premise no longer holds. Both named packages collect cleanly at HEAD: `src/cadrumo/application/calculations/tests/` and `src/cadrumo/application/modelo/tests/` together report `2500/2616 tests collected (116 deselected)` with zero `ERROR` lines under the default marker split, and `116/2616` plus `2500/2616` (the two marker-complement halves, `-m integration` and `-m "not integration"`) sum to the same 2616 with zero errors either way. `dev/registry/tests`, the package a same-week audit measured at 29 collection errors, now also collects cleanly (`455/479 tests collected (24 deselected)`, zero errors).

This is a repair, not a fix that predates the row: `.vault/audit/2026-08-14-registry-campaign-sequencing-audit.md`, dated the day before this Step ran, measured `dev/registry/tests` at 29 collection errors and 2 further failures, all raising from one mechanism -- `filing-grade authority requires operator_reviewed` -- against modelo 200 (`2024-y-siguientes`, `2025`) and modelo 390 (`2025`) revisions still carrying `pending_review`, plus five DANA legal references at `agent_reviewed`. Its own root-cause correction records that most of those were not an attestation backlog at all: a shared test fixture built a filing-grade snapshot and forwarded it into a function typed for a plain revision inspection, which reads neither of the two attributes that function needs, so those fixtures could not have passed against any corpus however attested; two sibling suites had already migrated to the inspection-grade fixture and finishing that migration closed the errors. `git log` shows the landing commits: `286ea37802 fix(registry): admit any reviewed status for filing-grade authority`, `66619ae6ee fix(registry): admit any reviewed revision for a filing-grade snapshot`, and `8e7c1fe93d application: read non-filing revision inspection instead of filing-grade snapshot`, all ancestors of the current HEAD, alongside the ongoing `registry: continue authority-grade sweep (round N)` commits (rounds 34-42 are all under HEAD) that are separately closing the "several modelos declaring neither an export layout nor an authority grade" gap this row names by declaring `authority_grade` and export layouts revision by revision. Per the orchestration rule requiring HEAD re-derivation before acting on a finding, this ruling is grounded in a fresh collection run against current HEAD, not against the row's or the audit's original measurement.

Ruling on the row's actual question, why a collection error can read as infrastructure noise and get scrolled past: something in this repo WOULD have caught it, but its placement explains the scroll-past exactly. `src/cadrumo/tests/test_full_corpus_collectability_harness.py::test_every_test_module_in_the_tree_is_collectable` is a dedicated real-subprocess proof that recursively collects the entire first-party corpus and asserts both a plausible collected count and an empty error list -- precisely the assertion that would have failed throughout the window these two packages could not import. Its own docstring states why it is not part of the routine unit lane: "recursively collecting the complete corpus is valuable end-to-end evidence, but routine unit execution must not pay for a second full collection." The `justfile` enrols it, together with `test_worker_count_hook_harness.py`, as the sole members of a dedicated `test-harness` recipe (`justfile:472-481`) that every other corpus-walking lane explicitly `--ignore`s, and `.github/workflows/ci.yml` runs that recipe as its own named CI job, `cadrumo-test-harness`, separate from the unit and integration jobs. The `default` `just` recipe only lists recipes; nothing composes `test-harness` into a developer's ordinary local loop, and no pre-commit hook references it. So the mechanism exists, is real (not tautological -- its own test plants a genuinely uncollectable module and asserts the detector reports it), and ran in CI the whole time as an independently-named, independently-triaged job -- but a developer running `just test-unit`, the ordinary integration lane, or even a tree-wide `pytest --collect-only` scoped to a subset of packages sees a fully green result regardless, because the corpus-wide proof is structurally elsewhere. A collection error inside two packages therefore surfaces only as one red check among many named CI jobs, with no cross-reference from the green unit/integration jobs pointing at it, which is the concrete shape of "reads as infrastructure noise and gets scrolled past": nothing in the routine, frequently-watched lanes will ever show it.

No modelo ids need handover: the export-layout/authority-grade gap the row names is the peer's already-declared, already-in-progress registry authority-grade sweep (rounds 34-42 landed under HEAD, per `.vault/audit/2026-08-14-registry-campaign-sequencing-audit.md` Tier 1/Tier 3 sequencing), not a newly-discovered defect needing a new owner.

## Notes

No production or registry code was touched; this Step is investigation-and-ruling only, per its scope and per the explicit instruction not to edit `src/cadrumo/_data/registry/`. The plan checkbox for `W04.P07.S86` was left unchecked by this Step's author per the dispatch contract; the row can be marked complete once reviewed, since the ruling and its grounding are both recorded here.
