---
tags:
  - '#adr'
  - '#quality-gate-zero-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6a75fd9e73550f1f35fad7e79eac3c1d857981fb43b11cc4bce9411899bd235b'
related:
  - "[[2026-08-24-quality-gate-zero-closure-static-gate-matrix-research]]"
  - "[[2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference]]"
  - "[[2026-07-14-honest-all-green-adr]]"
  - "[[2026-06-09-quality-hardening-campaign-adr]]"
  - "[[2026-06-04-repo-health-triage-adr]]"
---
# `quality-gate-zero-closure` adr: `Exact zero closure protocol for static gates and Vault health` | (**status:** `proposed`)

## Problem Statement

The accepted `2026-07-14-honest-all-green-adr` establishes that a green repository must be earned by root-cause repair under the project's honesty rules. It does not yet define the joined authority, handoff protocol, or final evidence predicate for the current static-gate and Vault-health closure surface. The decision needed now is how to coordinate remediation across active feature plans while preserving the independent hard-gate contract and producing a verification result that is attributable to one revision.

The decision is grounded by `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research` and its executable ownership map in `2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference`. The measured counts in those records are discovery snapshots only; this ADR does not establish a debt baseline or a target threshold.

## Considerations

- The canonical style, format, type, import, relative-import, dependency, and ratchet commands are independent hard checks. The closure contract must preserve their existing scope and exact pass conditions; `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research`.
- A shared dirty worktree contains active plan-owned surfaces. Remediation must remain owner-attributable and must record collision and handoff evidence; `2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference`.
- Type diagnostics repeat around shared boundaries and checker/rule families, so the unit of work must be a root cause with fan-out evidence rather than a raw diagnostic count; `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research`.
- Vault hard errors invalidate the document graph, while warnings describe work that must remain visible and owned; hard errors and warnings therefore need separate closure predicates; `2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference`.
- The standing-gate and diagnostic-first policies remain parent constraints. This ADR adds the joined zero-closure protocol and does not relax either parent decision; `2026-06-09-quality-hardening-campaign-adr`, `2026-06-04-repo-health-triage-adr`, and `2026-07-14-honest-all-green-adr`.

## Considered options

- **O1 — One coordinator edits every failing path in a repository-wide sweep.** Rejected: it makes peer WIP indistinguishable from campaign work, creates modify/modify collisions, and weakens ownership and provenance.
- **O2 — Owner-coordinated remediation with a joined zero-closure predicate.** Chosen: the coordinator owns the evidence matrix, sequencing, and handoffs; active plans retain authority for their paths and repair each root cause with their own behavior proof.
- **O3 — Establish a threshold, diagnostic baseline, new exclusion, skip/xfail, suppression, or allowlist for the known-red set.** Rejected: it changes the signal instead of repairing the defect and contradicts the standing honesty and quality-gate decisions.
- **O4 — Leave every red row to its active plan without a coordinating closure protocol.** Rejected: it preserves local ownership but leaves no joined evidence standard or final predicate, so the repository can remain red indefinitely with incompatible measurements.
- **O5 — Order type work by checker totals or largest files alone.** Rejected: totals and file size are useful discovery signals but do not identify the shared production boundary that caused a family of diagnostics.

## Constraints

- The static closure predicate is exact zero from the canonical commands for style, format, types, architecture imports, relative imports, dependencies, and ratchets. Existing command scope and explicitly documented tool behavior remain unchanged; this ADR adds no baseline, threshold, exclusion, suppression, skip, xfail, or allowlist.
- A clean verification snapshot is mandatory for closure. The coordinator captures the starting revision and dirty-path set, obtains owner acceptance for every remediation path, records the overlap result, and reruns the full matrix only after the candidate revision has no unaccounted dirty overlap. If the revision or dirty-path ledger changes during verification, the result is invalid and the matrix is rerun.
- Active feature plans remain the source of implementation authority. The coordinator may sequence, join, or hand off a finding, but may not silently take over an owned path or modify it after an owner refuses the handoff. An unowned finding is recorded for explicit adjudication rather than fixed through an undocumented sweep.
- Root-cause type batches must identify the checker/rule family, shared boundary or protocol, affected owners, and behavior proof before editing. Each batch reruns all configured type checkers and its focused tests; a lower count alone never closes a batch.
- Vault hard errors block closure and must reach zero through the owning Vault CLI and the responsible feature's provenance path. Vault warnings are not converted into success or hidden: every warning is inventoried with an owner, disposition, and next action, and the final report states any warning that remains.
- This ADR governs the static-gate and Vault-health closure surface. Unit, integration, security, packaging, external-advisory, and credential-gated lanes retain their own authorities and must be reported separately; absence of their evidence cannot be presented as green.
- The parent `2026-07-14-honest-all-green-adr` remains stable and accepted for the overarching no-shortcut and whole-tree honesty mandate. This proposed record is a narrower operational decision for the `quality-gate-zero-closure` feature, not a supersession or amendment of that parent.

## Implementation

Adopt an owner-coordinated closure campaign with one joined evidence matrix. The coordinator records the gate command, owner, path scope, starting revision, dirty-path overlap, focused behavior proof, full-gate result, and final disposition for each batch. Active plans continue to author and execute their production and test changes; the coordinator supplies sequencing and refuses unowned or colliding edits.

The sequence is:

1. Capture the revision, dirty-path ledger, active-plan status, and complete gate outputs as a non-baseline snapshot.
2. Repair syntax blockers and owner-accepted style/format defects, then rerun the affected behavior tests and the full style and format checks.
3. Resolve dependency classification and direct-declaration defects, followed by the dependency preflight.
4. Work type diagnostics as root-cause batches ordered by fan-out and boundary leverage. After each batch, run its focused behavior proof and all three configured type checkers, then inspect for cross-checker regressions.
5. Route ratchet failures to their active test-harness, import, profile, registry, or other feature owner. Preserve mutation-biting policy tests and repair their topology or production behavior; do not make a red test disappear through a policy exception.
6. Repair Vault hard errors through the owning lifecycle verb, review the resulting provenance, and run targeted checks before the global Vault check. Maintain the warning inventory as a separate output.
7. Re-read the revision and dirty-path ledger, then run the complete joined matrix from the clean verification snapshot. The coordinator closes the campaign only when every static hard gate is exactly zero, Vault hard errors are zero, and the separate warning and out-of-scope lane reports are attached.

A root-cause type batch is complete only when the shared source contract is repaired, the owner-approved path remains attributable, focused behavior tests pass, all configured type checkers pass for the relevant surface, and the full static matrix shows no new failure. The batch record reports rule families and affected paths for diagnosis, never a numeric pass threshold.

## Rationale

O2 is the only option that combines the existing owner boundaries with a repository-level truth claim. It preserves the standing hard-gate contract and the no-shortcut mandate from `2026-07-14-honest-all-green-adr`, while making the active-plan handoff and clean-snapshot evidence explicit. The reference's gate map and sequencing protocol support one joined matrix without replacing the individual gate authorities; `2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference`.

Exact zero is the knockout criterion. A baseline, threshold, or exception would make the signal green while leaving the defect population unknown, and a count reduction would not prove that a shared type boundary or behavior contract is correct. Root-cause batches retain causal evidence and let every checker challenge the same repair; `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research`.

Separating Vault hard errors from warnings is equally deliberate. Hard errors prevent trustworthy lifecycle and provenance interpretation and therefore block closure. Warnings remain useful only when their owners, dispositions, and next actions stay visible, so warning inventory is part of the evidence even when it is not the hard-error predicate; `2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference`.

## Consequences

The project gains one attributable definition of static zero closure without weakening any gate. Owners can continue their active plans while the coordinator joins their evidence, and type work is directed at shared causes rather than cosmetic tallies.

The campaign incurs handoff and revalidation overhead. Measurements taken in a dirty or moving worktree remain useful for triage but cannot close the campaign, and a concurrent revision change can invalidate an otherwise passing run. Some warnings may remain after hard-error closure; they are visible, owned follow-up work rather than a hidden claim of Vault perfection.

The protocol does not grant authority over product architecture, calculation grounding, registry content, security policy, or external services. Any finding whose repair changes those decisions must return to the governing feature ADR and plan, while this record supplies only the closure and evidence discipline.
