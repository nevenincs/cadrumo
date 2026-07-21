---
tags:
  - '#adr'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-17'
related:
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-02-aeat-architecture-review-audit]]"
  - "[[2026-07-02-arch-remediation-crash-window-reference]]"
  - '[[2026-07-06-arch-remediation-crash-window-research]]'
---
# `arch-remediation-crash-window` adr: `multi-store crash-window guarantees` | (**status:** `accepted`)

## Problem Statement

A profile bucket's durable state spans four sibling stores plus a lock: the
plaintext manifest, the encrypted SQLite database and its write-ahead-log
sidecar, the content-addressed blob store, and the keystore wrapped DEK. Every
single write is atomic, but the composed verbs (create, rename, hard delete,
bundle export/import, attachment put, master-key rotation) sequence writes
across those stores, and their inter-store orderings were convention-guarded
only. The architecture review recorded this as finding
persistence-multi-store-crash-windows: the crash-window matrix was not itself a
tested artefact, so which torn intermediate states are recoverable, and by which
repair verb, was undocumented and unverified. This ADR discharges deferral
register item D11 of the arch-remediation program.

## Considerations

The composed verbs already carry the right instincts (atomic single writes,
probe-skip idempotent rotation, fail-closed integrity gates, trash-rename
removal), so the work is to confirm each ordering against HEAD and pin every
recoverable end-state with a crash-injection test, not to redesign the stores.
Tests must use real adapters (real encrypted SQLite, real blob store, real
keystore) and simulate the interruption point rather than patch the storage
primitives, per the roundtrip-discipline anti-tautology rule. The matrix in the
grounding reference is a worklist, not gospel: HEAD confirmation precedes every
test, and several matrix rows proved wrong on ordering.

## Considered options

- Document the matrix only, no tests. Rejected: an unverified matrix rots and
  proves nothing about the repair verbs it names.
- Add crash-injection tests without first confirming HEAD orderings. Rejected: a
  test written before the ordering is confirmed risks proving the wrong window
  (the matrix mislabels several orderings).
- Confirm each ordering against HEAD, then pin each confirmed window with one
  anti-tautology crash-injection test, and document non-goals explicitly.
  Chosen.

## Constraints

Confined to the persistence storage adapter test surface plus the reference
document body; no production code is modified. A window whose HEAD resolution is
a documented non-goal drops its test. A genuine production gap surfaced by a test
is reported rather than silently patched.

## Implementation

Phase one confirms each composed verb's actual write ordering at HEAD and
resolves every VERIFY cell in the grounding reference to a confirmed guarantee or
a documented non-goal. Phase two authors one crash-injection test per confirmed
window using the anti-tautology pattern against the existing repair / diagnostic
verbs, leading with the highest-value mixed-key master-key rotation window across
envelope files, blob manifests, and the keystore DEK. Phase three pins the
write-ahead-log sidecar accounting: every at-rest plaintext-scan surface and the
sealed-archive export must carry every committed row regardless of checkpoint
state. Detailed per-cell findings and coordinates live in the grounding
reference.

## Rationale

Turning the convention-guarded matrix into HEAD-confirmed, tested guarantees is
the minimum that makes the multi-store crash surface auditable. The
anti-tautology discipline (interrupt or corrupt, then prove detection or
recovery) is what distinguishes a real guarantee from a repair verb that passes
with the window un-simulated. Grounded in the program ADR and the architecture-
review audit finding.

## Consequences

The recoverable end-states of the composed bucket verbs are now enumerated and
tested, and the reference records where the matrix diverged from HEAD (create
ordering, attachment single-store model, bundle direct-write, rotation
orchestration). One production gap surfaced: the sealed-archive reader does not
reliably reject a truncated archive (a torn write), which is reported for a
follow-up hardening step rather than patched under this test-only campaign.
