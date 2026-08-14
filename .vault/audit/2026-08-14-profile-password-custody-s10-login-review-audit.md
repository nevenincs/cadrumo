---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:a3ffab090695c10d69f1765df06c23d5eb0605116a3b930ea16c262371eb5a65'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `profile-password-custody` audit: `S10 candidate login handover review`

## Scope

Independent review of `W02.P04.S10` against the accepted custody roll-up and
the completed lifecycle/discovery phase. The review covered target resolution,
throttle ordering, current envelope and sentinel authentication, unbound B
candidate ownership, pointer compare-and-swap, live and record-session binding,
optional persisted acceleration, A retirement, rollback, crash behavior, real
six-case tests, negative legacy searches, and scoped static analysis. S11 and
production remediation were excluded.

## Findings

The candidate boundary is otherwise coherent. Target resolution and throttle
evaluation precede password resolution and Argon2. Current password material
loads the exact committed envelope and sentinel without recovery, manifest,
provider, or shared-master fallback. Cached B can resume only when the captured
pointer already selects B and the live binding does not disagree. Wrong or
malformed B closes only candidate material and leaves A's exact pointer, live
session, record session, and persisted B absence unchanged. Pointer publication
is captured-byte compare-and-swap; bind or acceleration failure restores A,
removes B acceleration, closes B, and compare-and-restores the pointer.
Unavailable keyring acceleration is explicitly process-scoped rather than an
authentication failure.

The original activation-order HIGH is closed. `_record_activation` now executes
inside the rollback-protected promotion transaction, before A retirement, and
uses the journal's stable UTC instant. The content-addressed bucket event makes
replay idempotent. A real corrupt-B event-store test proves exact A pointer,
live-session, record-session and persisted-session preservation while B's
candidate and acceleration are removed. The five real subprocess cases kill
the process at pointer-published, B-bound, accelerated, activated and A-retired
receipts and recover deterministically to authenticated B without test doubles.

### s10-handover-journal-is-not-bounded-canonical-nofollow | high | Recovery authority is loaded through an unbounded raceable path read

`_load_handover_journal` describes the journal as bounded, but calls
`Path.read_bytes()` with no maximum size and only performs a separate
`is_link_like()` check before opening the path. A sibling process can replace
the leaf between that check and the open; the read can therefore follow a link
or consume an unbounded file. The loader also accepts any JSON byte
representation Pydantic accepts rather than requiring the writer's one
canonical serialization. This file decides whether an interrupted switch is
replayed, cleared as terminal, or refused, so it is recovery authority rather
than advisory telemetry. The current implementation does not meet the requested
bounded durable-journal or the repository's established no-follow local-record
boundary.

The expanded tests are real and non-tautological, but none preplants an
oversized journal, a link/reparse leaf, or noncanonical/duplicate-key JSON, nor
does any race the journal leaf replacement. The focused corrupt-event-store
case passed independently in 41.70 seconds. The executor reports the complete
12-case integration selector passing in 502 seconds, all five crash cases, and
clean Ruff, Ty, and BasedPyright; those results close the former HIGH but cannot
establish an untested filesystem boundary. The stated MCP registration and
Modelo 303 failures remain external. Verdict is **FAIL** with one HIGH finding;
S10 remains unchecked.

## Recommendations

Give the handover journal a small explicit byte ceiling and load it through the
canonical anchored no-follow custody/local-record primitive on both POSIX and
Windows, validating regular-file type and stable identity from the opened
handle. Require exact canonical bytes after strict parsing, including rejection
of duplicate-key or alternate JSON spellings. Apply the same anchored boundary
to clear/replacement so a leaf swap cannot redirect deletion or publication.
Add real oversized, link/reparse, noncanonical and concurrent-replacement tests
without mocks, patches, skips, or mirrored parser logic.
