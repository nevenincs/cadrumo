---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:b0542048b798873d3168c31fe9aa12f1d7c19ce1634a3150f84fa255d4b04fb8'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-research]]"
---

# `tui-architecture` audit: `S21 persistence integration review`

## Scope

Independent review of `W02.P04.S21` against the complete live plan, accepted
ADR and research, S17-S21 execution records, S17-S20 implementation and review
evidence, fresh code and vault RAG discovery, exact-symbol source confirmation,
and the current shared worktree. The review covered public-facade use,
real-filesystem and fresh-process behavior, atomic snapshot-plus-history
commits, monotonic and idempotent restart replay, lease conflict, renewal,
takeover, release and current-owner enforcement, credential-free durable bytes,
path and link containment, permissions, staging residue, one-winner lease and
journal races, test honesty, and the `W07.P16.S96` scope boundary. Production
code, tests, plan state, commits, and peer-owned work were not modified.

## Findings

### credential-free-raw-byte-proof | medium | The credential assertion does not inspect the complete durable record bytes

`test_public_persistence_facades_commit_replay_and_reload_credential_free_history`
parses the journal and checks only that five field names are absent from the
top-level `snapshot` mapping. It never checks the complete bytes for the exact
owner ID and lease token supplied to `commit`, nor does it inspect the record
root or retained `history`. A coherent regression that adds the current lease
or token beside `snapshot` and `history` would therefore persist the supplied
token while this asserted credential-free proof remains green. The production
record is currently limited to snapshot and history and no leak was found, but
S21's explicit raw-byte security invariant is not mutation-sensitive.

### public-real-behavior-coverage | low | Public facades and real operating-system boundaries cover the lifecycle matrix

The integration module imports both concrete repositories only from the public
persistence facade and operation contracts only from the public application
facade. It uses actual temporary filesystem roots, spawn-context child
processes, the production repository lock and atomic writer, and no fake, stub,
mock, patch, monkeypatch, skip, xfail, or mirrored business implementation.
Two transitions reload through a fresh repository and replay exclusive pages
`1`, `2`, then caught-up; a repeated page is equal; stale writes preserve the
winning bytes. Conflict, exact renewal, expiry observation, exact-predecessor
takeover, stale-owner refusal, current-owner commit, exact release, and
post-release refusal all execute through production facades.

### concurrency-and-filesystem-boundary | low | Lease and journal races each leave one complete durable winner

Two fresh processes race the same expired predecessor and yield exactly one
`TAKEN_OVER` result and one `OWNER_LOST` result, after which the persisted owner
is one of the two candidates and stale release preserves its bytes. Two further
processes race the same journal revision and yield one commit and one refusal;
fresh load returns the complete successor and a repeated stale commit preserves
the file. The tests verify canonical root containment, absence of a journal
file link, POSIX owner-only modes where that contract is enforceable, no staged
temporary residue after successful and refused paths, and refusal of a linked
journal root before redirected JSON can be created.

### scope-and-current-tree | low | S21 does not consume restart-reconciliation scope and the transient registry incident is clear

Repository re-instantiation and cursor replay exercise persistence restart
only; the test does not crash or reconcile a supervisor, classify uncertain
effects, resume an executor, or report an orphan, so `W07.P16.S96` remains
untouched. The previously reported registry collection failure is not current:
`_collect_registry_tree_fingerprints` is defined in the live loader, the exact
four-test integration route passes, and the sequential full persistence package
collects and passes all 21 tests.

### verification-gates | low | Current focused behavior, static analysis, and vault structure gates pass

The exact integration run passed 4 tests and the sequential unit-or-integration
package run passed 21 tests. Ruff check passed, Ruff format reports the S21 file
already formatted, and basedpyright reports zero errors, warnings, or notes.
VaultSpec structure, frontmatter, references, and integrity checks pass; its
remaining warnings are shared-corpus advisories, including the scaffold hints
that this authored audit removes.

## Recommendations

- Strengthen `credential-free-raw-byte-proof` by reading the complete journal
  bytes and asserting that the exact supplied owner ID and lease token are
  absent everywhere, while retaining the safe request digest. Include a
  credential-shaped sentinel that reaches the public runtime-to-persisted
  boundary if that boundary is available without entering S22 or S96 scope.
- Retain the public-facade imports, real spawn processes, complete-winner reload,
  byte-preserving refusals, linked-root refusal, permission checks, and residue
  assertions.

Final verdict: FAIL. One MEDIUM finding remains open; no CRITICAL or HIGH
finding is open.

## Credential-free raw-byte final re-review

### credential-free-raw-byte-proof-closure | low | The complete journal document now excludes the exact lease authority while retaining one safe digest

The remediated integration test reads the complete UTF-8 journal serialization,
parses its document root, and requires that root to contain exactly `snapshot`
and `history`. It then proves the safe request reference equals the supplied
content digest and that the digest occurs exactly once across the complete
serialized record. The exact owner ID and exact lease token supplied to both
lease acquisition and journal commit are absent everywhere in those bytes;
the credential and secret field-name sentinels are absent as well. This closes
the MEDIUM mutation gap: adding lease authority beside either the snapshot or
the retained history now fails the proof, while removing or duplicating the
safe digest also fails it. The S21 journal commit surface accepts only the
strict persisted snapshot plus its lease; a runtime credential operand cannot
reach this boundary without the later supervisor/secure-reference composition.
The exact caller-supplied owner and token are therefore the available
confidential sentinels at this scope.

### complete-record-and-history | low | Atomic snapshot and full-history persistence remain directly proved

Two committed revisions produce one document whose root is pinned to the
current snapshot and complete history. A fresh repository reloads the exact
successor and replays exclusive pages with sequences `1` and `2`; a repeated
first page is equal and the caught-up cursor remains stable. The existing race,
byte-preserving refusal, canonical containment, link refusal, permission, and
staging-residue assertions remain unchanged and current.

### s22-scope-boundary | low | The remediation does not enter supervisor lifecycle or reconciliation

The change is confined to raw journal inspection in the persistence integration
test. It does not import or invoke an operation supervisor, submit or execute an
operation, reconcile restart state, classify uncertain effects, resume work, or
report an orphan. `W02.P05.S22` and the later restart-reconciliation row remain
unconsumed.

### final-focused-gates | low | Current focused behavior and static gates pass after shared registry churn settled

The first fresh integration invocation stopped during collection while live
peer registry edits briefly imported an unavailable TOML helper; rereading the
current files showed that transient import had already been removed. The exact
integration route then passed 4 tests, and the sequential unit-or-integration
persistence package passed all 21 tests. Ruff check and format verification pass
for the integration test, and basedpyright reports zero errors, warnings, or
notes. Fresh VaultSpec RAG discovery converged on the same S17 journal safety
contract, D10 credential-free persistence decision, S21 plan row, implementation,
and review record confirmed by exact-symbol `rg` inspection.

Final verdict: PASS. The prior MEDIUM finding is closed; no CRITICAL, HIGH, or
MEDIUM finding remains.
