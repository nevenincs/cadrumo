---
tags:
  - '#plan'
  - '#quality-gate-zero-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_hash: 'sha256:f71d6de431472a8ef449467b9e20eb250bd85335b6d26e083cdb777a116ba19a'
tier: L3
related:
  - '[[2026-08-24-quality-gate-zero-closure-adr]]'
  - '[[2026-08-24-quality-gate-zero-closure-static-gate-matrix-research]]'
  - '[[2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference]]'
  - '[[2026-07-14-honest-all-green-adr]]'
  - '[[2026-06-09-quality-hardening-campaign-adr]]'
  - '[[2026-06-04-repo-health-triage-adr]]'
---

# `quality-gate-zero-closure` plan

## Description

This L3 roll-up executes the accepted `2026-08-24-quality-gate-zero-closure-adr`, grounded by `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research` and `2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference`. W01 owns the fresh non-baseline snapshot, joined evidence matrix, RAG discovery, and explicit owner handoffs. W02 repairs syntax, style, format, dependency, architecture-import, and relative-import surfaces. W03 repairs type root causes at shared boundaries. W04 routes every ratchet family and repairs Vault hard errors while keeping warnings visible. W05 drives security, complexity, duplication, checkout drift, corpus-text, semantic, and composed advisory surfaces toward measured green. W06 is the only closure authority and requires a clean verification snapshot, independent review, RAG redeclaration audit, and separate out-of-scope lane evidence.

Active feature plans retain implementation authority for their paths. The coordinator records the command, owner, path scope, starting revision, dirty-path overlap, focused behavior proof, full-gate result, and disposition for every batch. No Step permits a baseline, threshold, new exclusion, suppression, skip, xfail, mock, monkeypatch, tautological assertion, or hidden allowlist to make a red signal disappear.

## Steps

## Wave `W01` - snapshot and ownership control

Capture a fresh non-baseline repository snapshot, revalidate the live gate and RAG surfaces, and bind every finding to an accepted owner before any remediation. Downstream Waves depend on this ledger and the authorizing zero-closure ADR, static-gate research, and failure-topology reference.

### Phase `W01.P01` - fresh snapshot and gate inventory

Record HEAD, dirty paths, active-plan status, and the complete current check and audit outputs as a re-fetchable discovery snapshot with no baseline semantics.

- [ ] `W01.P01.S01` - Capture the current HEAD, dirty-path ledger, active-plan status, and ownership snapshot as dated non-baseline evidence (Luna max); `.vault/audit/`.
- [ ] `W01.P01.S02` - Run the canonical hard static matrix and retain complete outputs with exit statuses and diagnostic families (Luna max); `justfile`.
- [ ] `W01.P01.S03` - Run the Vault, requested advisory, corpus-text, and health-report commands and retain full outputs without treating counts as a baseline (Luna max); `dev/audit/`.
- [ ] `W01.P01.S04` - Record unit, integration, packaging, credential-gated, external, RAG, semantic, and pre-commit lane state separately from the hard predicate (Luna max); `.vault/audit/`.

### Phase `W01.P02` - ownership and RAG topology

Revalidate semantic discovery, feature ownership, collision boundaries, and handoff acceptance so every red surface is attributable before editing.

- [ ] `W01.P02.S05` - Revalidate the live RAG code and Vault indexes and repeat meaning-based discovery for gate runners, ownership, and shared boundaries (Luna max); `.vault/audit/`.
- [ ] `W01.P02.S06` - Map each static, type, ratchet, Vault, and advisory finding to its active feature plan and exact owner Step (Luna max); `.vault/audit/`.
- [ ] `W01.P02.S07` - Obtain explicit owner acceptance and record dirty-path overlap, starting HEAD, collision result, and handoff target for every remediation batch (Luna max); `.vault/audit/`.
- [ ] `W01.P02.S08` - Adjudicate every unowned or colliding finding before edits and preserve a refusal or follow-up record instead of taking silent ownership (Luna max); `.vault/audit/`.

## Wave `W02` - repair hard static gates

Repair owner-accepted syntax, style, format, dependency, architecture-import, and relative-import defects while preserving canonical command scope and exact-zero acceptance. This Wave starts only after W01 ownership and snapshot evidence.

### Phase `W02.P03` - syntax style and format

Clear syntax blockers, owner-accepted Ruff findings, and formatting drift in file-disjoint batches before downstream semantic checks.

- [ ] `W02.P03.S09` - Repair the syntax blockers in the CLI invocation-scope test and prove its focused behavior before formatter work (Terra xhigh); `src/cadrumo/entrypoints/cli/tests/test_action_reconciliation_invocation_scope.py`.
- [ ] `W02.P03.S10` - Repair the export-producer Ruff line-length, import-order, and unused-symbol findings with behavior proof (Luna max); `src/cadrumo/application/filing/_export_producer.py`.
- [ ] `W02.P03.S11` - Apply owner-accepted Ruff style repairs in application and profile paths and run their focused tests (Luna max); `src/cadrumo/application/`.
- [ ] `W02.P03.S12` - Apply owner-accepted Ruff style repairs in CLI paths and run their focused tests (Luna max); `src/cadrumo/entrypoints/cli/`.
- [ ] `W02.P03.S13` - Apply owner-accepted Ruff style repairs in test paths and run their focused tests (Luna max); `src/cadrumo/tests/`.
- [ ] `W02.P03.S14` - Run owner-scoped Ruff format checks, inspect formatter rewrites for peer overlap, and then run full style and format checks (Luna max); `dev/quality/`.

### Phase `W02.P04` - dependency and architecture boundaries

Resolve direct dependency declarations and import-linter boundary failures without changing command scope or adding architecture carve-outs.

- [ ] `W02.P04.S15` - Correct the deptry first-party classification for local development imports without declaring a misleading package (Terra xhigh); `justfile`.
- [ ] `W02.P04.S16` - Resolve the direct grimp dependency finding by declaring the real tooling dependency or removing the owning import path (Terra xhigh); `pyproject.toml`.
- [ ] `W02.P04.S17` - Resolve the direct tomlkit dependency finding by declaring the real tooling dependency or removing the owning import path (Terra xhigh); `pyproject.toml`.
- [ ] `W02.P04.S18` - Repair the import-linter delegate-wrapper boundary and route any architecture decision to the import-centralization owner (Sol only); `src/cadrumo/application/user_profile/_custody_ports.py`.
- [ ] `W02.P04.S19` - Run dependency preflight, deptry, import-linter, and architecture tests with no new ignore, carve-out, or contract pin (Luna max); `dev/quality/suite.py`.

### Phase `W02.P05` - relative imports and gate parity

Repair absolute intra-package imports and verify the local static recipes remain scope-equivalent to the CI static lane.

- [ ] `W02.P05.S20` - Replace absolute intra-package imports in the source test consumers with owner-approved relative imports (Luna max); `src/cadrumo/tests/`.
- [ ] `W02.P05.S21` - Replace absolute self-imports in development tooling with owner-approved relative imports (Luna max); `dev/`.
- [ ] `W02.P05.S22` - Re-run the relative-import checker and verify local recipe and CI static scope parity (Luna max); `dev/quality/relative_imports.py`.

## Wave `W03` - close type root causes

Reduce type diagnostics through shared boundary and protocol repairs with focused behavior proof and all three configured checkers after each root-cause batch. This Wave depends on W02 syntax and import stability.

### Phase `W03.P06` - type diagnostic triage matrix

Capture normalized checker, rule-family, file, owner, and boundary evidence and select root-cause batches by fan-out rather than raw counts.

- [ ] `W03.P06.S23` - Run full type audit mode and normalize checker, rule-family, file, fan-out, and owner evidence before selecting a batch (Luna max); `dev/quality/types.py`.
- [ ] `W03.P06.S24` - Preserve the empty external-gap allowance and prove every diagnostic remains a hard finding without a baseline or blanket cast (Luna max); `dev/quality/types.py`.
- [ ] `W03.P06.S25` - Assign each type root-cause batch to an accepted feature owner and record its focused behavior proof and cross-checker expectation (Luna max); `.vault/audit/`.

### Phase `W03.P07` - calculation and row-observation boundaries

Repair shared calculation and row-observation protocols that fan out into pyrefly and ty diagnostics, retaining real behavior proofs and source-casilla ownership.

- [ ] `W03.P07.S26` - Repair the typed row-set assembly boundary that fans out into calculation checker diagnostics under source-casilla ownership (Terra xhigh); `src/cadrumo/application/calculations/_row_set_assembly.py`.
- [ ] `W03.P07.S27` - Repair dependent calculation consumers while preserving row identity, source provenance, and real calculation behavior (Terra xhigh); `src/cadrumo/application/calculations/`.
- [ ] `W03.P07.S28` - Run the real worksheet export-pull-calculate encrypted roundtrip and focused calculation behavior proof for the repaired boundary (Luna max); `src/cadrumo/application/storage/calc_sheets/tests/test_row_set_calculation_roundtrip.py`.

### Phase `W03.P08` - auth registry and shared protocols

Repair auth, registry, and other shared typed protocol boundaries driving BasedPyright and cross-checker diagnostics under their active feature owners.

- [ ] `W03.P08.S29` - Repair auth operators shared typed protocols behind unknown-member and unknown-argument families under the auth owner (Terra xhigh); `src/cadrumo/adapters/outbound/aeat/auth/`.
- [ ] `W03.P08.S30` - Repair registry connectivity shared protocols behind repeated checker diagnostics under the registry owner (Terra xhigh); `src/cadrumo/application/registry/`.
- [ ] `W03.P08.S31` - Run focused auth, registry, provenance, and refusal behavior suites for each repaired protocol boundary (Luna max); `src/cadrumo/adapters/outbound/aeat/auth/tests/`.

### Phase `W03.P09` - cross-checker regression and type zero

Rerun all configured checkers and focused behavior suites after every type batch, then close only when the full type gate is exactly zero with no new cross-checker failure.

- [ ] `W03.P09.S32` - Run ty, pyrefly, and BasedPyright after every root-cause batch and compare normalized rule and fan-out evidence (Luna max); `dev/quality/types.py`.
- [ ] `W03.P09.S33` - Run changed-owner focused behavior suites and inspect cross-checker regressions before accepting a batch (Luna max); `src/cadrumo/`.
- [ ] `W03.P09.S34` - Close the type gate only at exact zero and record that no ignore, diagnostic baseline, or unresolved-import allowance was added (Luna max); `.vault/audit/`.

## Wave `W04` - close ratchets and Vault health

Route every ratchet family to its active owner, repair Vault hard errors through owning CLI verbs, and maintain an explicit warning inventory. This Wave depends on the code surfaces being type-stable.

### Phase `W04.P10` - ratchet family remediation

Route inventory, marker, relative-import, shortcut, double, monkeypatch, broad-raise, bare-except, and tautology failures to their active owners and preserve mutation-biting behavior.

- [ ] `W04.P10.S35` - Repair stale inventory and relocation assertions against the declared project test roots under test-harness ownership (Terra xhigh); `dev/tests/test_test_inventory.py`.
- [ ] `W04.P10.S36` - Repair marker and live-import policy topology through the test-harness owner and preserve real subprocess proofs (Terra xhigh); `src/cadrumo/tests/test_marker_integrity.py`.
- [ ] `W04.P10.S37` - Remove forbidden monkeypatch controls through real reachable behavior under the test-harness owner (Terra xhigh); `src/cadrumo/tests/test_monkeypatch_inventory.py`.
- [ ] `W04.P10.S38` - Repair skip and xfail policy violations without adding exemptions or changing the ratchet predicate (Terra xhigh); `dev/tests/test_no_skip_xfail.py`.
- [ ] `W04.P10.S39` - Repair mock and test-double inventory violations with real behavior and owner-approved fixtures (Terra xhigh); `dev/tests/test_mock_inventory.py`.
- [ ] `W04.P10.S40` - Replace broad exception raises with narrow behavior-preserving errors and focused tests (Terra xhigh); `dev/tests/test_no_broad_exception_raises.py`.
- [ ] `W04.P10.S41` - Replace bare except paths with explicit exception handling and focused tests (Terra xhigh); `dev/tests/test_no_bare_except.py`.
- [ ] `W04.P10.S42` - Repair tautological assertions while preserving mutation-biting controls and external behavior proof (Terra xhigh); `dev/tests/test_no_tautology.py`.
- [ ] `W04.P10.S43` - Run the full ratchet recipe after each owner handoff and require exact zero across every policy family without an allowlist (Luna max); `justfile`.

### Phase `W04.P11` - Vault hard-error repair

Repair every current Vault frontmatter, schema, encoding, and provenance blocker through the owning lifecycle CLI and revalidate targeted and global checks.

- [ ] `W04.P11.S44` - Repair the issue-113 audit frontmatter and provenance through the owning Vault lifecycle CLI (Luna max); `.vault/audit/2026-08-23-issue-113-operator-gate-audit.md`.
- [ ] `W04.P11.S45` - Repair the 2026-08-23 registry-unblock reference frontmatter and provenance through the owning Vault lifecycle CLI (Luna max); `.vault/reference/2026-08-23-registry-unblock-loop-reference.md`.
- [ ] `W04.P11.S46` - Repair the 2026-08-24 registry-unblock reference frontmatter and provenance through the owning Vault lifecycle CLI (Luna max); `.vault/reference/2026-08-24-registry-unblock-loop-reference.md`.
- [ ] `W04.P11.S47` - Repair the invalid encoding and frontmatter in the Modelo 036 filing-authority reference through the owning Vault CLI (Luna max); `.vault/reference/2026-08-24-registry-completeness-closure-modelo-036-2025-filing-authority-reference.md`.
- [ ] `W04.P11.S48` - Add grounding references to the registry-loader period-code ADR through its owning decision flow (Luna max); `.vault/adr/2026-06-01-registry-loader-period-code-hydration-adr.md`.
- [ ] `W04.P11.S49` - Add ADR grounding to the registry-hardening next-work plan through its owning plan flow (Luna max); `.vault/plan/2026-06-02-registry-hardening-next-work-plan.md`.
- [ ] `W04.P11.S50` - Add grounding references to the CLI testimonial ADR through its owning decision flow (Luna max); `.vault/adr/2026-06-04-cli-testimonial-adr.md`.
- [ ] `W04.P11.S51` - Add grounding references to the renta-region deductibility ADR through its owning decision flow (Luna max); `.vault/adr/2026-07-04-renta-region-deductibility-adr.md`.
- [ ] `W04.P11.S52` - Add ADR grounding to the 2026-07-12 calculation-truth registry plan through its owning plan flow (Luna max); `.vault/plan/2026-07-12-calculation-truth-registry-plan.md`.
- [ ] `W04.P11.S53` - Add ADR grounding to the 2026-07-14 calculation-truth registry plan through its owning plan flow (Luna max); `.vault/plan/2026-07-14-calculation-truth-registry-plan.md`.
- [ ] `W04.P11.S54` - Run targeted Vault checks and global Vault check all after each CLI repair and review body hash, modified stamp, links, schema, and provenance (Luna max); `.vault/`.

### Phase `W04.P12` - warning inventory and feature provenance

Inventory warnings separately from hard errors, assign owners and dispositions, and regenerate only the quality-gate feature index through its owning CLI.

- [ ] `W04.P12.S55` - Inventory Vault warnings separately from hard errors with owner, disposition, next action, and remaining-risk status (Luna max); `.vault/audit/`.
- [ ] `W04.P12.S56` - Regenerate the quality-gate feature index through the owning feature-index CLI and verify every related link (Luna max); `.vault/index/quality-gate-zero-closure.index.md`.
- [ ] `W04.P12.S57` - Recheck annotations, orphan, feature-index, body-hygiene, schema-warning, modified-stamp, and encoding warning families without hiding unresolved debt (Luna max); `.vault/`.
- [ ] `W04.P12.S58` - Reconcile every Vault document changed by an owner CLI and preserve its machine body hash, modified stamp, and provenance evidence (Luna max); `.vault/`.

## Wave `W05` - clear advisory and corpus surfaces

Drive security, complexity, duplication, checkout-drift, corpus-text, semantic, and composed advisory reports toward green without adding suppressions or baselines. This Wave depends on hard-gate repairs so findings are measured on the intended tree.

### Phase `W05.P13` - security zero

Run the canonical semgrep security runner, remediate actionable findings at their owning paths, and prove scanned-file evidence and zero findings without hidden exclusions.

- [ ] `W05.P13.S59` - Run the canonical semgrep security runner and persist complete structured findings with scanned-file evidence (Luna max); `dev/audit/security.py`.
- [ ] `W05.P13.S60` - Remediate ERROR-severity security findings at their owner-accepted production paths and prove focused behavior remains correct (Terra xhigh); `src/cadrumo/`.
- [ ] `W05.P13.S61` - Resolve WARNING and INFO security findings or record an explicit owner disposition without adding rule suppressions or hidden exclusions (Luna max); `.vault/audit/`.
- [ ] `W05.P13.S62` - Rerun check-security and require a demonstrably scanned tree with zero findings for the green security result (Luna max); `dev/audit/tests/test_security.py`.

### Phase `W05.P14` - complexity and duplication zero

Refactor new or regressed complexity and copy-paste clusters, retire resolved ratchet records, and keep all findings attributable without adding baselines or dispositions.

- [ ] `W05.P14.S63` - Refactor new or regressed cyclomatic, maintainability, and cognitive complexity hotspots with focused behavior proof (Terra xhigh); `src/cadrumo/`.
- [ ] `W05.P14.S64` - Retire only resolved complexity baseline and allowlist entries and prove no new baseline or suppression was added (Luna max); `dev/audit/complexity_baseline.json`.
- [ ] `W05.P14.S65` - Rerun complexity and health-report dimensions and require no red or unmeasured result (Luna max); `dev/audit/complexity.py`.
- [ ] `W05.P14.S66` - Consolidate confirmed copy-paste clusters through their owning feature plans while preserving divergent constraint shapes and behavior (Terra xhigh); `src/cadrumo/`.
- [ ] `W05.P14.S67` - Retire only resolved duplication dispositions and prove no new disposition or hidden clone exclusion was added (Luna max); `dev/audit/duplication_dispositions.toml`.
- [ ] `W05.P14.S68` - Rerun duplication and composed advisory reports and require observed zero rather than unavailable or capped output (Luna max); `dev/audit/duplication.py`.

### Phase `W05.P15` - checkout drift and corpus text

Repair byte-level checkout drift and refresh or validate every committed manual-corpus sidecar so the drift and corpus-text checks prove current bytes.

- [ ] `W05.P15.S69` - Measure tracked byte drift and repair owner-accepted line-ending or terminator drift without broad checkout rewrites (Luna max); `dev/audit/checkout_drift.py`.
- [ ] `W05.P15.S70` - Run the shrink-only checkout-drift check and prove the tracked-byte drift count is zero without growing its ceiling (Luna max); `dev/audit/checkout_drift_baseline.json`.
- [ ] `W05.P15.S71` - Run corpus-text freshness against every manual PDF and inventory stale or missing sidecars (Luna max); `dev/corpus/extract_manual_corpus_text.py`.
- [ ] `W05.P15.S72` - Regenerate sidecars only for changed corpus PDFs and verify runtime evidence parity and provenance (Luna max); `src/cadrumo/_data/manual_corpus_text/`.
- [ ] `W05.P15.S73` - Rerun check-corpus-text and focused corpus evidence tests and require every committed sidecar to be current (Luna max); `src/cadrumo/domain/calculations/registry/`.

### Phase `W05.P16` - RAG semantics and advisory dashboard

Revalidate the RAG service, run semantic redeclaration and leakage searches, and drive the composed advisory and health reports to an evidence-backed green result.

- [ ] `W05.P16.S74` - Revalidate RAG daemon health and run check-rag and check-semantic against the current indexed source (Luna max); `dev/audit/semantic.py`.
- [ ] `W05.P16.S75` - Run meaning-based RAG redeclaration and canonical-home searches, verify every hit against live consumers, and persist the audit (Luna max); `.vault/audit/`.
- [ ] `W05.P16.S76` - Repair confirmed semantic redeclarations or hand them to the owning feature plan with evidence and no silent coordinator takeover (Terra xhigh); `src/cadrumo/`.
- [ ] `W05.P16.S77` - Run audit-all and audit-health-report in text and JSON modes and require green, measured dimensions with no advisory suppression (Luna max); `dev/audit/advisory.py`.

## Wave `W06` - prove clean closure

Re-read revision and dirty paths, run the complete joined matrix from a clean snapshot, perform independent RAG and code reviews, and publish hard-gate, warning, and out-of-scope evidence. This Wave is the only closure authority and depends on every prior Wave.

### Phase `W06.P17` - clean-snapshot joined matrix

Capture a new revision and dirty-path ledger and run every required just check and audit command only when the candidate snapshot is clean and owner overlap is accounted for.

- [ ] `W06.P17.S78` - Capture a new candidate HEAD and dirty-path ledger and refuse closure until every owner overlap is accounted for (Luna max); `.vault/audit/`.
- [ ] `W06.P17.S79` - Run style, format, type, architecture-import, relative-import, dependency, ratchet, and static dashboard commands and require exact zero for every hard gate (Luna max); `justfile`.
- [ ] `W06.P17.S80` - Run security, complexity, duplication, checkout-drift, corpus-text, composed advisory, and health-report commands and attach complete measured outcomes (Luna max); `dev/audit/`.
- [ ] `W06.P17.S81` - Run global Vault check all and require zero hard errors while retaining the separately inventoried warning set (Luna max); `.vault/`.
- [ ] `W06.P17.S82` - Run pre-commit, RAG, semantic, dependency-preflight, and relevant documentation or packaging checks and report any unavailable lane separately (Luna max); `justfile`.
- [ ] `W06.P17.S83` - Re-read HEAD and dirty paths after the matrix and invalidate and repeat the run if revision or ledger state changed (Luna max); `.vault/audit/`.

### Phase `W06.P18` - independent code review and honesty audit

Review the landed repairs for safety, intent, architecture, and quality, audit for suppression and redeclaration shortcuts, and action every surviving finding.

- [ ] `W06.P18.S84` - Conduct a formal safety, intent, architecture, and quality code review of every landed repair and owner handoff (Luna max); `.vault/audit/`.
- [ ] `W06.P18.S85` - Perform a fresh-context honesty review and open or route every surviving finding before declaring structural completeness (Luna max); `.vault/audit/`.
- [ ] `W06.P18.S86` - Audit the campaign diff and evidence for new suppressions, baselines, skips, xfails, mocks, monkeypatches, tautologies, or hidden allowlists (Luna max); `.vault/audit/`.
- [ ] `W06.P18.S87` - Re-run the RAG redeclaration audit and prove every canonical consumer import and semantic duplicate disposition against current code (Luna max); `.vault/audit/`.
- [ ] `W06.P18.S88` - Review the collision and handoff ledger for unowned edits, refusal violations, and peer-path provenance before close (Luna max); `.vault/audit/`.

### Phase `W06.P19` - final evidence and lane report

Publish the joined matrix with exact-zero hard gates, zero Vault hard errors, visible warnings, advisory outcomes, clean-snapshot identity, and separately reported external lanes.

- [ ] `W06.P19.S89` - Publish the joined evidence matrix with exact commands, environment, HEAD identity, dirty state, exit statuses, counts, focused tests, owners, and path scopes (Luna max); `.vault/audit/`.
- [ ] `W06.P19.S90` - Publish the separate warning inventory and out-of-scope unit, integration, packaging, external-advisory, and credential-gated lane report without implying missing evidence is green (Luna max); `.vault/audit/`.
- [ ] `W06.P19.S91` - Reconcile every closed Step with its execution record and review artifact before marking the plan complete (Luna max); `.vault/exec/2026-08-24-quality-gate-zero-closure/`.
- [ ] `W06.P19.S92` - Validate the feature index, plan convention, Vault health, and final clean-snapshot predicate before closure (Luna max); `.vault/index/quality-gate-zero-closure.index.md`.

## Parallelization

Waves are hard-sequenced: W01 snapshot and ownership must precede W02 hard static repair; W02 must precede W03 type closure; W03 must precede W04 ratchet and Vault closure; W04 must precede W05 advisory and corpus convergence; and W05 must precede W06 clean verification and review. Any revision or dirty-path change during a closure run invalidates the run and returns to W01 or W06 as appropriate.

Within W01, P01 precedes P02. Within W02, P03 clears syntax before P04 and P05; P04 and P05 may then proceed in parallel only on disjoint, owner-accepted paths. Within W03, P06 establishes the diagnostic matrix before P07 and P08; those two boundary phases may run in parallel when their path ledgers do not overlap, and P09 is a barrier. Within W04, P10 and P11 may run in parallel after W03, while P12 waits for the Vault repair results and warning inventory. Within W05, P13 through P16 may run in parallel after W04 only when their scanner and production path scopes are disjoint; P16's dashboard consumes the completed scanner evidence. W06 is sequential: P17 runs the clean joined matrix, P18 independently reviews it, and P19 publishes the final evidence.

Model routing is explicit in each Step: Luna max owns audits, normalized diagnostic triage, type-check reruns, mechanical sanity, Vault checks, and evidence review; Terra xhigh owns production coding, behavior-preserving refactors, and real-test repairs; Sol only handles an architecture refactor or boundary decision in W02.P04.S18 after the owning architecture plan accepts the handoff. No agent may silently edit a peer-owned path.

## Verification

The plan is complete only when all 92 Steps are checked through their canonical execution records and the independent review artifacts agree with the current tree. Closure requires the following evidence from one unchanged clean verification snapshot:

- The canonical hard checks are exact zero: style, format, all configured type checkers, architecture imports, relative imports, dependency declarations, and every ratchet family. The local dashboard and CI-scope commands must agree, and no count reduction, threshold, baseline, exclusion, suppression, skip, xfail, or allowlist may substitute for zero.
- `vaultspec-core vault check all --json` reports zero hard errors. The warning inventory remains separate and lists every warning with owner, disposition, next action, and residual risk, including annotations, orphans, feature-index drift, body hygiene, schema warnings, modified stamps, and encoding signals.
- Security, complexity, duplication, checkout drift, and corpus-text reports are measured on the intended tree and green under their existing authorities. `check-security` proves that files were scanned and has no findings; complexity and duplication have no unresolved hotspots or clone clusters; checkout drift is zero without ceiling growth; and every manual-corpus sidecar is current.
- RAG health and semantic checks are measured rather than skipped. The redeclaration audit verifies canonical homes and live consumers by meaning, records every true duplicate or justified divergence, and leaves no unowned finding or silent coordinator takeover.
- The joined report records each exact command and environment, start and end HEAD, clean status, dirty-path overlap, exit status, full diagnostic count, focused behavior proof, active owner, path scope, and final disposition. Any revision or dirty-ledger change invalidates the matrix and requires a rerun.
- The formal code review and fresh-context honesty review find no unactioned safety, intent, architecture, quality, provenance, or handoff issue. The review explicitly proves that no new suppression, baseline, skip, xfail, mock, monkeypatch, tautology, or hidden allowlist was introduced.
- Unit, integration, packaging, external-advisory, and credential-gated lanes are reported separately with their actual evidence and are never presented as green by absence. A missing or unavailable lane is an explicit out-of-scope or blocked result, not a hard-gate pass.
