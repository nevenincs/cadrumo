---
tags:
  - '#plan'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-06'
body_hash: 'sha256:17b2b8f4a4f394ea0b1da093e3d079bbc00cdd73dfd06ae0b3c79967cb34750d'
tier: L2
related:
  - '[[2026-07-21-ci-discipline-adr]]'
  - '[[2026-07-20-ci-speed-redesign-adr]]'
  - '[[2026-06-01-registry-period-code-union-cli-boundary-adr]]'
---

# `ci-lane-deconflation` plan

## Description

Close the open work left by the CI lane deconflation campaign and the defects
it surfaced. Three authorizing records feed this plan. The ci-discipline ADR
governs P01 and P02: its D6 amendment added the two new tier rows (T1-docs and
T1-frontend) and corrected the false claim that the carve-out was shared. The
ci-speed-redesign ADR governs the budget constraints those lanes sit inside.
The registry-period-code-union ADR governs P03, whose D6 amendment authorised
the filing-period type split that this campaign surfaced as a live regression.

The campaign itself is landed. What remains is verification that could not be
performed locally, backlog that enrolment made visible for the first time, and
findings correctly left unfixed because they need grounding this campaign did
not have.

## Steps

### Phase `P01` - Lane correctness and first-run verification

The two new lanes both failed their first real execution and their fixes are unverified. Nothing in this phase can be called done from a local run: the claim being tested is that these lanes behave correctly on a runner, which is a different claim from the code being right.

- [ ] `P01.S01` - Verify the docs lane passes on a runner now that it builds before it reads, its first run failed 13 times on an absent docs/_build/html; `.github/workflows/docs.yml`.
- [ ] `P01.S02` - Verify the frontend lane passes on a runner under Node 22, its first run refused npm ci because jest-dom 7.0.0 requires node 22 and the manifest under-declares at 20.19; `.github/workflows/frontend.yml`.
- [ ] `P01.S03` - Dispatch ci-full for its first ever execution and record the result, its run count is zero so every claim about its steps is structural rather than observed; `.github/workflows/ci-full.yml`.
- [x] `P01.S04` - Move the ci-full docs build above the tooling-gates step so the terminology gates that resolve to built HTML get their artefact, blocked until the legal-entry defect stops masking the dependency; `.github/workflows/ci-full.yml`.
- [x] `P01.S05` - Decide what to do about the already-pushed branch, a peer snapshot pushed it so the original decision is moot and the live question is whether the published history needs remediation; `origin/main`.

### Phase `P02` - Enrolled-lane backlog closure

Enrolling the integration suite and the dev tooling gates exposed accumulated rot that had never been visible. These rows close it and lift the two non-blocking guards. A guard left non-blocking indefinitely becomes decorative, so each carries the condition for flipping it.

- [x] `P02.S06` - Close the entrypoints CLI integration failures, measured at 18 across 8 modules with 138 passing, and regenerate the set from two intersected runs rather than one; `src/cadrumo/entrypoints/cli/tests`.
- [x] `P02.S07` - Reshape overview.calendar profiles to a per-profile summary with detail behind a per-profile call, the resource_link this row first prescribed is refused because resolution re-runs a read verb over persisted state while this verb is computed from a clock; `src/cadrumo/entrypoints/mcp`.
- [x] `P02.S08` - Measure the dev tooling gates at a clean HEAD, the local count of 55 is contaminated because 32 belong to an uncommitted peer legal entry and the true figure is nearer 23; `dev/audit, dev/deploy, dev/env, dev/registry, dev/docs`.
- [x] `P02.S09` - Flip continue-on-error off the integration parallel step once its backlog closes, the step is deterministic so it can go blocking independently of the serial pass; `.github/workflows/ci-full.yml`.
- [ ] `P02.S10` - Flip continue-on-error off the integration serial step once one runner execution is observed, its build branch producing three wheels and three sdists has never been watched; `.github/workflows/ci-full.yml`.
- [x] `P02.S22` - Author the ADR reshaping the overview.calendar payload, the resource_link remedy the gate names cannot apply to a computed verb with no persisted record and the irreducible floor leaves only 622 characters of headroom; `src/cadrumo/entrypoints/mcp`.
- [x] `P02.S23` - Fix thin_output_schema growing the schemas it thins, its oneOf inline-or-linked shape duplicates the property body so thinning a shared-defs verb enlarges it; `src/cadrumo/entrypoints/mcp`.

### Phase `P03` - Registry and core follow-through

Findings the campaign surfaced in the registry and core surfaces that are real but were correctly not fixed inline, either because they need domain grounding or because acting on them would have collided with in-flight work.

- [x] `P03.S11` - Build the registry selector parity gate binding declared period_selector tokens to the accepted set, delegating to the production validator rather than restating it so the gate cannot become a second authority; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `P03.S12` - Route the declaracion parser administrative-token set through the core authority, it hardcodes four tokens and is missing COMUNICACION and VARIACION from the core set it shadows; `src/cadrumo/adapters/inbound/declaracion/_parser.py`.
- [x] `P03.S13` - Decide the strength class for casillas 0529 and 0531, promoting them to the coverage-gated class raises the denominator and could flip verdicts on legitimate filings so it needs domain grounding; `src/cadrumo/_data/registry/aeat/modelos/100`.
- [x] `P03.S14` - Fix the embedded newline in the rd-439-2007 art-76 legal entry notes field, the validator rejects any Unicode C category and a narrower scan for control characters reads as clean; `src/cadrumo/_data/registry/aeat/legal`.
- [x] `P03.S18` - Pin which snapshot coordinates the filing-period cross-check covers, the consistency validator returns early on a null filing period so administrative-token snapshots quietly lost a check the validator's name still implies; `src/cadrumo/domain/calculations/registry/tests/test_snapshot_filing_period_coverage.py`.
- [x] `P03.S19` - State in the filing-period consistency validator's own docstring which coordinates it no longer covers and why, a test enforces the fact but the explanation belongs at the validator; `src/cadrumo/domain/calculations/registry`.

### Phase `P04` - Tracked but owned elsewhere

Work this campaign found and cannot close, recorded so it is not silently dropped. Each row names why it is not ours and what the owning party must do.

- [x] `P04.S15` - Repair the four core tests broken by the root-only Modelo localization migration, it stripped title and official_name and label from the M036 manifest without updating hand-derived expectations; `src/cadrumo/core/tests/test_toml_registry_parity.py`.
- [x] `P04.S16` - Re-pin the model-facing description digest once the description sources settle, the gate forbids re-pinning from a dirty tree and the locale and CLI help surfaces are actively churning; `dev/packaging/tests/test_verify_distribution_identity.py`.
- [x] `P04.S17` - Record a finding about the 204 semantic-dedup exec records rather than remediating them, all 204 carry empty Description Outcome and Notes and were bulk-scaffolded in one commit so 0 resolve to an implementing commit, and unchecking would assert work the tree shows was done; `.vault/exec/2026-06-13-semantic-dedup-epic`.
- [x] `P04.S20` - Resolve the import-hygiene test-debt failures from the maternidad private reaches, raising a baseline designed to only decrease would invert the ratchet so establish whether the debt is legitimate before admitting it; `src/cadrumo/tests/test_import_hygiene_gate.py`.
- [x] `P04.S21` - Replace the two bare 303 literals in the relation-source validator with the core enum, they entered in today's operator snapshot rather than becoming newly visible and they red a tree-wide gate for every agent; `src/cadrumo/domain/calculations/registry/_validate_relation_sources.py`.
- [x] `P04.S24` - Confirm with the localization cascade owner that the result-summary application row is meant to follow the active output language, the repair is stronger than what it replaced but it crosses another campaign's surface; `src/cadrumo/entrypoints/cli/tests/test_modelo_result_summary_labels.py`.
- [x] `P04.S25` - Sweep for tests relying on the English CLI env override for help text, it is inert against the cached Click tree so any such test asserts against whatever language the tree was built in; `src/cadrumo/entrypoints/cli/tests`.
- [x] `P04.S26` - Require an exec record whose evidence is a passing test to state the selection that produced it, three agents in one day nearly accepted a marker expression that selected nothing and exited zero; `.vaultspec/templates`.
- [x] `P04.S27` - Rule on whether the schema-size gate should measure emitted content, its docstring calls itself a proxy for structured content while it directly measures the definition bytes a client actually loads; `src/cadrumo/entrypoints/mcp/tests`.

## Parallelization

P03 and P04 are fully parallel with everything else and with each other. They
need no CI run and no push, so they are the rows to work while P01 is blocked.

P01 carries the only hard ordering in the plan, and it is external. S05 (the
push decision) gates S01, S02 and S03, because none of those lanes can be
observed until the commits reach the remote. S04 is gated instead by S14: the
ordering hypothesis it acts on is currently masked by the legal-entry defect,
so acting before S14 would be acting on something that cannot be demonstrated.

P02 is partly gated by P01. S09 depends on S06 closing the backlog it measures.
S10 depends on S03, because the serial pass has never been observed on a runner
and flipping it on local evidence alone is the failure this plan exists to
avoid. S07 and S08 are independent and can be worked immediately.

## Verification

Every row closes against evidence from a real execution, not a local run. That
distinction is the plan's central criterion, because the campaign's costliest
errors all came from claims that were structurally sound and never observed.

- S01, S02 and S03 close on a named run id whose conclusion is success. A
  passing local invocation is not evidence for any of them, and the docs lane
  is the worked example: it was structurally correct, its conformance gates
  were green, and it failed 13 times on its first real execution.
- S04 closes when the terminology gate that resolves to built HTML is
  demonstrated to depend on the build, not assumed to. If S14 lands and the
  dependency does not materialise, close S04 as not-needed with that finding
  recorded rather than reordering on a hypothesis.
- S06 closes on two intersected runs, never one. The lane measured 19 failures,
  then 28, and 12 of the difference was a peer's transiently broken module.
- S07 closes with the payload moved. Raising the budget is a failed close.
- S09 and S10 close only after the step they guard has been seen green on a
  runner. Flipping either on local evidence is the specific failure these rows
  exist to prevent.
- S11 closes only when the gate is shown to FAIL against a planted violation.
  A parity gate whose discovery silently finds nothing is indistinguishable
  from one that passes because the tree is clean.
- S13 and S16 are decisions, not implementations. They close when the decision
  is recorded with its grounding, including a decision to leave things as they
  are.

Commit verification for every row: resolve the sha with `git log --format=%H
--grep=<subject> -1` and read `git show <sha> --numstat`. Never verify with
`git show HEAD`, which returned a peer's commit during this campaign.

## Context

Durable tracking for the CI lane deconflation campaign of 2026-08-05 and every item it surfaced. Authored because the working task list is session state: an outage loses it, and several rows here are the only written record of a measured finding.

The campaign began as signal scoping - a documentation edit was firing the full Python static+unit suite while producing no documentation verdict, and a frontend dependency bump was firing both Python lanes plus a three-OS packaging probe. Fixing the carve-out required giving both surfaces lanes of their own, which in turn exposed that two whole test lanes were declared in the justfile and invoked by no workflow: the src/ integration suite (~370 modules) and nine dev/ subsystems. Enrolling those produced the backlog most of these rows track.

Three measurement hazards govern how rows here must be closed, each learned the expensive way during the campaign:

Do not triage a lane from a single run. The integration lane measured 19 failures, then 28; intersecting the two showed 12 were a peer's transiently broken module killing every cold-subprocess test at CLI import. Roughly 19 peer commits land per 12-minute run.

Verify a commit by SHA, never by HEAD. HEAD moves under you in this worktree - `git show HEAD` immediately after a commit returned a peer's. Resolve with `git log --format=%H --grep=<subject> -1`, then `git show <sha> --numstat`, and read the per-file line counts rather than only the file list.

A green gate proves nothing until you have seen it fail. Two gates in this campaign were near-misses: a duplication report rendering 0 clones while 65 existed, and a probe whose broken fixtures reported valid filing periods as refused - caught only by its positive control.

Every row states what was measured and where the evidence sits, so a reader who inherits this without the conversation can act on it.
