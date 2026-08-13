---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:53efe3cd9d64b335b9ce1f317fb22975e305d13f5ffe4df18fd490721ed4831b'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-research]]"
  - "[[2026-08-11-tui-architecture-W02-P04-S19]]"
  - "[[2026-08-13-tui-architecture-s17-lease-contract-review-audit]]"
  - "[[2026-08-13-tui-architecture-s18-review-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `tui-architecture` audit: `S19 review`

## Scope

Independent review of `W02.P04.S19` against the complete live plan, accepted
ADR and research, S17-S19 execution records, S17/S18 review audits, recorded
code and vault RAG grounding, current scoped diff, and repository rules. The
review covered the durable filesystem lease repository, exact transition
evidence, shared journal lock integration, corruption and byte-preservation
behavior, real-process concurrency, focused tests, and S18 regression
preservation. Plan state, execution records, production code, tests, and
peer-owned changes were not modified.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### S19 review | {level} | {summary}

     followed by a paragraph carrying the detail. S19 review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### journal-pre-acquisition-authorization | high | A future lease can authorize a snapshot from before ownership began

`OperationLeaseStorage.require_live_exact_unlocked` verifies exact durable
equality and requires only that `expires_at` be later than the snapshot's
`updated_at`. It does not require `acquired_at` to be at or before that
timestamp. Consequently, a lease durably acquired at 09:01 authorizes a journal
snapshot whose persisted caller timestamp is 09:00, even though the S17 active
observation contract correctly rejects that same temporal relation. A direct
production-model reproduction acquired the future lease and then committed the
earlier snapshot successfully. The focused tests cover absent, expired, stale
owner, and stale token refusals, but omit this pre-acquisition case. S19
therefore does not yet prove that the exact durable lease was active at
`snapshot.updated_at`.

### durable-transition-shape | low | Lease persistence and transition refusals otherwise preserve the S17 contract

The strict schema-v1 record carries only operation identity, caller time, and
the S17 lease witness; unknown or malformed durable data fails closed. The
adapter calls no clock or identity generator. Absent acquisition, active
conflict, expired refusal, exact renewal, expired-owner takeover, exact release,
and `OWNER_LOST` all use production S17 results and validate before atomic
replacement. Conflict, expiry, and predecessor-mismatch paths do not mutate the
record.

### shared-journal-lock | low | Lease authorization and journal CAS use one canonical lock without nesting

Lease and journal storage resolve the same canonical `operation-journals` root
and `.repository` sidecar through public `JournalRepositoryBase` authority.
Journal commit holds that lock across the unlocked exact-lease read, snapshot
revision validation, and hardened atomic write. The implementation introduces
no second taxonomy, lock, or writer; process tests prove one acquisition winner
and prove a journal process waits on the lease repository lock.

### verification-gates | low | Focused behavior and static gates are green but do not cover the HIGH

The exact focused run passed 31 tests, including the S17 contract and S18
journal regressions. Ruff check and format passed, and basedpyright reported zero
errors, warnings, or notes. VaultSpec structural checks passed with 1,384
shared-corpus advisory warnings; this audit's body attestation is current. Those
gates omit the successful pre-acquisition authorization reproduction above.

### journal-pre-acquisition-remediation | low | The complete live interval and byte-preserving refusal now close the HIGH

The journal's unlocked durable-lease authorization now first requires exact
equality with the currently stored lease and then enforces the complete live
interval `acquired_at <= snapshot.updated_at < expires_at`. The check remains
inside the journal's existing `JournalRepositoryBase` sidecar-lock scope, before
snapshot compare-and-swap validation or atomic replacement.

The real-filesystem regression releases the original lease, durably acquires an
exact future lease through `OperationLeaseFilesystemRepository`, and attempts a
successor snapshot whose `updated_at` precedes that lease's `acquired_at`. The
production journal refuses it as not yet active and the test proves the existing
journal bytes are unchanged. The exact focused run passed 31 tests. Scoped Ruff
check and format passed, and basedpyright reported zero errors, warnings, or
notes. No new HIGH, CRITICAL, MEDIUM, or LOW finding remains in the re-review
scope.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

- Completed: the journal lease check enforces the complete active interval
  `acquired_at <= snapshot.updated_at < expires_at` while retaining exact
  current-lease equality under the same `JournalRepositoryBase` lock.
- Completed: the real-filesystem byte-preservation test acquires a lease after the
  proposed snapshot timestamp, proves the commit refuses, and confirms an
  existing journal remains byte-for-byte unchanged.
- Completed: the exact focused pytest, Ruff, format, and basedpyright gates were
  rerun after remediation. The prior HIGH is independently closed.

Initial verdict: FAIL. One HIGH finding was open; no CRITICAL or MEDIUM finding
was open.

Re-review verdict on 2026-08-14: PASS. The prior HIGH is closed and no finding
remains open in the authorized S19 re-review scope.

