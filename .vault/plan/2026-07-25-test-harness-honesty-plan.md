---
tags:
  - '#plan'
  - '#test-harness-honesty'
date: '2026-07-25'
modified: '2026-07-27'
tier: L1
related:
  - '[[2026-07-25-test-harness-honesty-false-green-gates-audit]]'
  - '[[2026-07-25-test-harness-honesty-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `test-harness-honesty` plan

- [x] `S01` - CLOSED at commit ad2d2e3eda, the bare-.xls scan pattern carried a doubled backslash so it could never match a real literal and passed over four live sites, now corrected with three routed through the canonical constants, one documented Literal-alias escape guarded by a justification test, a positive control asserting every survivor pattern matches its target and rejects near-misses, and a non-empty-corpus assertion, verified by reintroducing a bare literal and observing the gate name the exact file and line; `src/cadrumo/tests/test_enum_constant_extraction_inventory.py`.
- [ ] `S02` - Signal a degraded state on the semantic discovery service so a truncated index either refuses to answer or marks its answers untrustworthy, because the governing rule makes an agent refuse coding work when the service is DOWN while a service that ANSWERS from a partial index never trips that refusal and returns a confident empty result for a concept that does have a canonical owner, measured at 1027 code sections against roughly 4546 files with an empty degraded-reasons list; `external, vaultspec-rag repository not this tree`.
- [ ] `S03` - Assess whether the code index can converge at all while a committing fleet re-triggers its rebuild through the file watcher, since the degraded window is not self-limiting and chunk counts were observed climbing while the job identifier changed; `external, vaultspec-rag repository not this tree`.
- [x] `S04` - Make the packaging preflight recipe state its marker selection explicitly, because it inherits the default marker expression over a mixed-marker directory and silently drops 106 of 330 tests while exiting zero, and the dropped modules are those named for the packaging smoke, Scoop, Homebrew, and Docker workflows the recipe gates; `justfile, dev/packaging/tests/`.
- [x] `S05` - Refresh the module size-budget pins that are documented as having no headroom while sitting far above actual, since a stale ceiling permits silent regrowth up to the gap and the gate reports green throughout; `src/cadrumo/tests/test_data_size_budget.py`.
- [x] `S06` - VERIFIED-SOUND RECORD, the held-serial escalation mechanism is unwired by design rather than dead code, recorded so a later reader does not fix a mechanism that is deliberately inert; `src/cadrumo/tests/_marker_hook.py`.
- [x] `S07` - VERIFIED-SOUND RECORD, the majority of the audited gate surface carries genuine positive controls, recorded so a later audit does not re-derive the same negative result; `.vault/audit/2026-07-25-test-harness-honesty-false-green-gates-audit.md`.
- [x] `S08` - Sweep the remaining survivor and conformance gates for the vacuous-pattern shape this audit found twice in one day, in the bare-literal scan and in the documentation claims gate, asserting each pattern against a known-match and a known-reject rather than trusting that a green gate is measuring anything; `src/cadrumo/tests/, dev/`.
- [x] `S09` - Triage the 33 empty-assert functions the S08 screen still flags at commit 003a2f987d, down from 38, separating genuine vacuity from legitimate absence assertions and from corpora guarded by a membership assertion in a sibling module, starting with the stub-drift gate that asserts its drift lists are empty without ever proving the manager saw a module; `dev/audit/vacuity_screen.py, src/cadrumo/tests/, dev/`.
- [ ] `S10` - Extend the vacuity screen beyond the single shape it detects, since it sees only an empty assertion with no non-emptiness proof and is blind to a gate asserting a total where the property is a decomposition, and no systematic search has run for escapes that outlived their reasons beyond the one ratchet where all seven enrolled entries proved stale; `dev/audit/vacuity_screen.py`.
- [x] `S11` - Reconcile the duplication disposition record against a fresh live scan, since the coverage gate is red at commit 003a2f987d on clone groups in the TUI form-screen module that carry no recorded disposition, a condition that predates this campaign and belongs to peer-owned code so it needs its owner rather than a silent classification by a sweep; `dev/audit/duplication_dispositions.toml`.
- [x] `S12` - Audit the gate surface for checks reachable only through a marker-scoped or narrowed selection, because a gate whose slowest half is never run is a gate whose result nobody has seen, which is how the duplication disposition gate stayed red unnoticed through a verification that ran its unit half and reported 22 passed; `src/cadrumo/tests/, dev/, justfile`.
- [x] `S13` - Close the stale-fixture family by requiring a test to bind a persisted record's version constant rather than restate its value, since two bucket-manifest fixtures kept writing schema_version=1 after the durability floor moved to 2 and neither failed loudly because both read paths treat the resulting raise as an ordinary degraded state, and the gate found five further stale sites on its first run; `src/cadrumo/tests/test_persisted_version_literal_inventory.py`.
## Description

## Steps

## Parallelization

## Verification

## Context

Tracks the six findings of the false-green gate audit. One (the vacuous bare-.xls scan pattern) is closed at commit ad2d2e3eda; the remainder are open. Two findings are informational records of verified-sound surfaces and are carried so a later reader does not re-derive them.

Re-measured on 2026-07-25 at commit 1307d1ced7, while working S04 through S08. The semantic code index had NOT recovered; it had regressed. It held 188 sections against roughly 4546 tracked files, down from the roughly 1027 recorded when S01 landed, while still reporting an available status and an empty degraded-reasons list, and while its own job state read succeeded.

The behavioural field test the audit prescribes was applied rather than the numeric one. Two deliberately unrelated probes, one for the clone-scanner runner and one for the secure-object namespace registry, returned the SAME file at similarity scores around 0.001, and neither target module appeared at all. That is the truncated-index signature, and it confirms the audit's central point: the count alone never distinguished healthy from degraded, but the behaviour does.

This strengthens rather than changes the disposition of S02 and S03. Both remain correctly scoped as external, since the search service is a separate product in a separate worktree, confirmed by the service reporting that worktree as its own distinct project root. What changes is the severity: the degraded window is not merely persisting, it is deepening, and a job that has already declared success will not retry. Any conclusion of the form "semantic search found no existing owner" reached in this window remains void.

Code discovery for S04 through S08 was therefore carried by targeted search over concept synonyms and direct module reads. The VAULT index was healthy at 16121 documents and was used heavily, where it earned its place: it surfaced two closed successor plans whose steps duplicate open steps in the sibling tracking plan, work that would otherwise have been re-implemented from scratch.
