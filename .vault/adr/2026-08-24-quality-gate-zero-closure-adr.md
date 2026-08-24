---
tags:
  - '#adr'
  - '#quality-gate-zero-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:09722d317f87bbd1af8687a5628b5e0e193989d6302f006115fe04857eaf636c'
related:
  - "[[2026-08-24-quality-gate-zero-closure-static-gate-matrix-research]]"
  - "[[2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference]]"
  - "[[2026-07-14-honest-all-green-adr]]"
  - "[[2026-06-09-quality-hardening-campaign-adr]]"
  - "[[2026-06-04-repo-health-triage-adr]]"
---
# `quality-gate-zero-closure` adr: `Perpetual rolling ratchet with revision-scoped exact-zero checkpoints` | (**status:** `accepted`)

## Problem Statement

The accepted record currently frames the joined static-gate and Vault-health work as a finite closure campaign over a measured failure inventory. That framing is incorrect for an actively developed codebase: the inventory changes whenever concurrent work lands, and a passing run can establish truth only for the revision that was actually inspected. Treating code sanity as a terminal plan deliverable therefore makes the plan drift with the worktree or encourages an obsolete checkpoint to be presented as permanent closure.

The decision needed now is how to preserve exact-zero gate semantics, owner attribution, joined verification, and meaning-based architecture discovery without claiming that code sanity can ever be permanently closed. The mechanism itself must operate continuously, while any plan that installs or activates it must remain finite and independently completable. The decision remains grounded by `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research` and `2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference`.

## Considerations

- The canonical style, format, type, import, relative-import, dependency, and ratchet commands are independent hard checks whose exact pass conditions must remain intact; `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research`.
- Dirty-worktree counts are re-fetchable observations rather than an exhaustive backlog or debt baseline, and concurrent changes can invalidate their use as current evidence; `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research`.
- Active feature plans own overlapping production, test, registry, and Vault paths, so intake and routing must follow current ownership rather than a frozen campaign allocation; `2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference`.
- Repeated diagnostics commonly fan out from shared boundaries, making root-cause attribution and behavior proof more durable than checker totals or file rankings; `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research`.
- Semantic ownership also moves as code is added and consumers are repointed. The RAG service and semantic index therefore require current-revision revalidation rather than a one-time declaration; `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research`.
- Vault hard errors and Vault warnings have different truth conditions: hard errors invalidate the joined hard predicate, while warnings must remain visible and owned without being silently converted into either success or permanent debt; `2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference`.
- The standing-gate, diagnostic-first, and honest-all-green decisions remain binding. This amendment changes the lifetime and evidence semantics of the operating model, not the strength of any gate; `2026-06-09-quality-hardening-campaign-adr`, `2026-06-04-repo-health-triage-adr`, and `2026-07-14-honest-all-green-adr`.

## Considered options

- **O1 — Execute one fixed repository-wide zero-closure campaign and declare code sanity complete.** Rejected: its failure inventory becomes stale as active development moves, and its terminal claim would outlive the only revision for which its evidence was true.
- **O2 — Operate a perpetual rolling ratchet with revision-scoped exact-zero checkpoints.** Chosen: current failures and semantic ownership are continuously re-observed and routed, while a green claim is emitted only for the immutable revision that passed the complete joined predicate.
- **O3 — Stabilize the moving target with a diagnostic baseline, threshold, new-error-only rule, exclusion, suppression, skip, xfail, or allowlist.** Rejected: it makes the measurement easier to preserve by weakening what green means.
- **O4 — Leave every gate failure entirely within independent feature plans without a joined operator loop.** Rejected: local ownership is preserved, but no repository-level checkpoint, stale-evidence invalidation rule, semantic redeclaration cadence, or common intake path remains.

## Constraints

- Exact zero remains the checkpoint predicate for the canonical style, format, type, architecture-import, relative-import, dependency, and ratchet hard gates. Vault hard errors must also be zero. This decision authorizes no threshold, diagnostic baseline, exclusion, suppression, skip, xfail, or allowlist.
- A green checkpoint is evidence about one immutable candidate revision, its gate configuration, commands, and verification environment. It must be produced from a clean verification snapshot. If the candidate revision or accounted path set changes during verification, the in-progress result is discarded and the loop observes the new candidate.
- A later revision inherits no green assertion from an earlier checkpoint. The earlier checkpoint remains valid historical evidence for its own revision, but it cannot be used to claim the current tree is green.
- Failure counts, rule rankings, and path clusters are diagnostic observations only. They may guide routing and ordering, but they never become the loop's pass condition, an exhaustive worklist, or a fixed debt allowance.
- Active feature plans remain the implementation authority for their owned paths. The ratchet operator may observe, attribute, sequence, join evidence, and request a handoff, but may not silently take over an owned surface or rewrite peer work through a repository-wide sweep.
- Repairs are handled as current root-cause batches. Each batch identifies the producing boundary or policy family, current owner, affected paths, and focused behavior proof, then reruns every overlapping hard gate needed to detect cross-gate regression.
- Every observation redeclares semantic canonical homes and live consumer ownership from the current RAG index, then verifies candidate hits against the live code. A confirmed duplicate, displaced canonical home, or unowned consumer is routed as current work; old RAG evidence never becomes an allowlist or standing declaration.
- Vault warnings remain attached to every checkpoint with their owner, disposition, and next action. They are not hidden, treated as hard-error zero, or promoted into a permanent warning baseline.
- Unit, integration, security, packaging, external-advisory, credential-gated, and other separately governed lanes retain their own authorities. A static/Vault-hard checkpoint must state which of those lanes were actually evidenced and may not imply broader green.
- `2026-07-14-honest-all-green-adr` remains accepted as the overarching whole-tree honesty mandate. Under this record, “all green” is necessarily a revision-scoped evidence claim, never permanent closure of code sanity.

## Implementation

Install a persistent operator loop around the existing gate and discovery authorities. Each observation records the candidate revision, verification environment, exact commands, dirty-path state, full gate results, current path owners, current semantic canonical homes and consumers, and any warning or out-of-scope lane disposition. The measured failure topology and RAG ownership declaration are regenerated from the live revision whenever the loop runs; no previous snapshot is assumed to describe the current tree.

When an observation is red, the loop groups failures by current root cause and routes each group to the feature or policy owner that controls the affected surface. Meaning-based RAG redeclaration runs in the same observation cycle: candidate redeclarations and canonical-home drift are verified against live definitions and consumers, then routed to the responsible owner when confirmed. Owners repair real behavior under their governing decisions and return focused proof plus the affected hard-gate results. New failures, changed ownership, newly overlapping paths, and semantic drift enter the same intake path instead of being appended to a supposedly exhaustive closure backlog.

When a candidate is ready for joined verification, the complete matrix and current-revision RAG redeclaration audit run against its clean, pinned snapshot. Any revision movement invalidates the run and returns the mechanism to observation. Exact zero across the static hard gates and Vault hard errors emits a revision-scoped checkpoint with the warning inventory, semantic audit disposition, and separately governed lane report attached. The next repository change begins unverified and must earn its own checkpoint.

The rolling ratchet is an operating mechanism, not a permanently open implementation plan. A finite plan may install and activate its triggers, evidence ledger, ownership-routing protocol, semantic redeclaration cadence, stale-run invalidation, reporting surface, and live biting proof. That plan completes when the mechanism is durable, active, and demonstrably able to observe, refuse false green, route current failures, redeclare semantic ownership, and produce attributable evidence. It may include bounded repairs required to activate the mechanism, but it does not need to exhaust the repository's present or future defect population.

A successful mechanism-installation record and a green checkpoint are separate claims. Installation may complete while the latest live observation remains red with visible owners and next actions; that result proves the ratchet is operating, not that the revision is green. Likewise, attaining a checkpoint does not close the mechanism or the standing quality obligation.

## Rationale

O2 preserves the only two honest properties that matter simultaneously: the gates retain their exact-zero meaning, and the resulting truth claim is limited to the revision actually tested. The existing research establishes that the observed inventory and ownership topology move during concurrent development, so a fixed campaign cannot remain an authoritative description of the work; `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research` and `2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference`.

The perpetual loop prevents snapshot drift from becoming plan drift. Current failures and semantic ownership are always derived from current evidence, while bounded owner repairs remain attributable to the plans and decisions that authorize their paths. A finite installation plan can therefore complete against durable mechanism outcomes without pretending to enumerate every defect that future development may create.

Revision scoping also preserves the honest-all-green mandate without weakening it. Exact zero remains the knockout criterion, but it is a checkpoint rather than a terminal repository state. Baselines and exceptions are unnecessary because movement is handled by re-observation, semantic redeclaration, and re-verification, not by teaching the gate to tolerate yesterday's failures.

## Consequences

The repository gains an enduring quality-control mechanism whose green claims are precise, reproducible, and attributable. Historical checkpoints remain useful evidence, while every changed revision must earn its own result.

There is no terminal “code sanity closed” state. The project accepts continuing observation, RAG redeclaration, routing, repair, and revalidation as an operating cost of active development. Concurrent changes may repeatedly invalidate candidate runs, but they no longer invalidate a finite plan or force that plan to absorb an ever-changing backlog.

Mechanism completion and repository state must be reported separately. The installation plan can finish successfully while routed failures remain, and a green checkpoint can become historical as soon as a new revision exists. Neither condition may be phrased as permanent closure.

The current failure matrix ceases to be an execution contract. It remains useful for immediate triage, but new findings and ownership changes flow through the ratchet and, where implementation authority is needed, into bounded owner work rather than a single perpetual plan.

Vault warnings and separately governed lanes remain visible beside every checkpoint. The resulting report is intentionally narrower than a claim of universal repository health, and any broader claim requires the evidence of those independent authorities.
