---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:1e7ba6409713680e25054ca860f458b67c3da819b1b5eaf00c580a6154b113a5'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---
# `object-name-declustering` audit: `s11 rehearsal review`

## Scope

Reviewed the S11 rehearsal implementation against the accepted declustering ADR,
research, reference, plan, and current manifest, graph, transform, hashing, path-safety,
and local execution contracts. The review exercised exact current-tree copying,
retained system-temporary isolation, installed-environment gates, inventory and byte
binding, source immutability, changed-path containment, finding deltas, and receipt
identity. No review agent edited the implementation.

## Findings

### installed-environment-binding | high | Rehearsal gates initially resolved an empty temporary environment

The first draft excluded `.venv` from the snapshot but ran `uv run --no-sync` without
binding the installed source environment. In a system-temporary copy this could create
or select an empty environment and make repository-native gates fail independently of
the proposed rename.

### copied-inventory-authority | high | The receipt initially trusted a caller inventory without rescanning the copy

The copied bytes were hash-verified, but the canonical object-name inventory was not
recomputed before transformation. Concurrent unrelated source drift could therefore
produce a receipt that claimed an older manifest inventory digest.

### volatile-gate-identity | high | Raw command output made equivalent replay identities unstable

The first receipt identifier included stdout and stderr hashes. Normal gates can emit
run duration or temporary paths, so equal source, manifest, argv, and exit results could
produce different replay identities.

### failed-command-evidence | medium | Failed gates initially discarded captured outcome evidence

The first fail-fast error named only argv, omitting return code and captured stream
digests and sizes.

### retained-root-normalization | medium | Some post-allocation failures did not disclose the retained target

Allocation-safety, directory creation, and final source-verification exceptions could
escape the normalized rehearsal error boundary without the temporary path needed for
inspection.

### tracked-deletion-membership | medium | Tree identity omitted absent tracked paths

The initial snapshot dropped tracked working-tree deletions rather than retaining an
explicit absent marker, weakening the baseline path-set identity.

## Recommendations

Bind commands to the verified installed runtime while resolving project imports from
the copy. Recompute the copied inventory before mutation. Separate stable replay
identity from volatile raw-output evidence while binding both. Preserve failed-command
outcomes, fail fast, include explicit tracked-deletion markers, disclose every retained
target, and bind Git and uv versions alongside Python and LibCST.

## Re-review status

Resolved: commands run sequentially without a shell, with fixed timeouts, the current
verified runtime environment, and temporary-tree import roots. Failed outcomes include
argv, exit code, and stdout/stderr SHA-256 plus sizes.

Resolved: the verified copy is scanned before mutation and must match both the supplied
inventory and manifest digest. Finding deltas use that copied baseline. Snapshot tree
identity includes explicit absent markers for tracked deletions.

Resolved: stable `receipt_id` binds source, manifest, inventory, paths, argv, exit,
finding, and tool data without volatile streams; `evidence_digest` separately binds the
raw output evidence. A two-run random-output probe produced one stable receipt identity
and two distinct evidence digests.

Resolved: every post-allocation error and final immutability failure discloses the
retained rehearsal root. The target is never automatically deleted. Tool evidence
includes Git, uv, Python, LibCST, the installed runtime environment, and rehearsal
schema. Final independent review found no high or critical issue.
