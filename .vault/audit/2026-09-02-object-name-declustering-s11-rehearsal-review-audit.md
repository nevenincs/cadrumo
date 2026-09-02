---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:578170ca9126ffc05fb3e938f7192d8d12ecd42c351330eeb635215a58a7af0c'
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

### component-authority-unbound | high | A caller can rehearse a forged partial component

`rehearse_object_name_component` resolves only the supplied component's operation IDs
against executable manifest rows. It does not derive the current operation graph or
verify the supplied component ID, affected paths, hard edges, risk evidence, or complete
operation membership. A caller can therefore construct an `OperationComponent` containing
only one operation from an indivisible connected component and obtain a receipt bearing an
arbitrary component ID. Full-manifest validation does not establish graph membership, so
the receipt does not prove the ADR's exactly-one-complete-reviewed-component boundary.

### generator-phase-unreachable | high | Declared owning generators cannot execute

The manifest contract requires every non-empty `generator_commands` declaration to include
the `generated-artifact` reference class. The rehearsal calls
`plan_object_name_transformation` before running generators, while that transformer refuses
every operation declaring `generated-artifact`. Consequently every operation with an owning
generator fails at the transformation boundary and the generator loop is unreachable for
non-empty generator input. Rehearsal cannot satisfy the accepted generated-owner workflow or
emit generator outcome evidence for a valid manifest.

## Recommendations

Bind commands to the verified installed runtime while resolving project imports from
the copy. Recompute the copied inventory before mutation. Separate stable replay
identity from volatile raw-output evidence while binding both. Preserve failed-command
outcomes, fail fast, include explicit tracked-deletion markers, disclose every retained
target, and bind Git and uv versions alongside Python and LibCST. Recompute the canonical
operation graph at the rehearsal boundary and require exact equality with the selected
component before issuing a receipt. Split generated-owner execution from the LibCST-only
transform phase so a reviewed generator can run in the disposable copy while its exact
generated paths remain inside the selected component allowlist.

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
schema.

Open: final contract review found two high-severity issues. The selected
`OperationComponent` is not bound back to the canonical graph, permitting partial or
forged component rehearsal, and generator-backed operations are refused by the
transformer before their owning commands can run. Focused Ruff, Ruff-format, ty,
byte-compilation, and import checks passed; those static checks do not exercise either
cross-module authority boundary. No critical, medium, or low issue remains open.
