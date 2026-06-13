---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-26-cross-domain-continuity-plan]]'
---

# `cross-domain-continuity` audit: `Peer-WIP collision protocol audit (lint-zero session)`

## Summary

Closes W13.P66.S406. During the 2026-06-03 lint-zero session three
distinct peer-WIP collisions surfaced. The `aeat-git-worktree-safety`
abort-on-WIP rule held in every case — no peer work was overwritten,
no destructive operations were attempted. The collision-recovery
discipline worked. However the operator-facing diagnostic when the
collision blocked a test run was opaque, and this audit records the
finding so a future session can improve the refusal-pattern surface.

## Collisions observed

### Collision 1: dual NoActiveProfileError ErrorCode registry race

A peer mid-flight refactor of `aeat.core.errors` introduced a
`NoActiveProfileError` subclass without registering its `ErrorCode`
entry. A sibling class with the same name lived under
`aeat.application.workflow._errors`. Both inherited from `AeatError`
and both ran through the `bind_error_code` `__init_subclass__` hook,
which raised:

    ValueError: AeatError subclass aeat.core.errors.NoActiveProfileError is missing a declared ErrorCode registry entry

The collision blocked any test that imported the affected module
chain. The diagnostic is technically accurate but does not tell the
operator that this is a transient peer-WIP state rather than a defect
to fix. The collision resolved when the peer's commit landed.

### Collision 2: diagnostics.py mid-refactor while landing S2067

A peer refactor of `aeat.application.diagnostics` (deferring heavy
imports to TYPE_CHECKING) landed concurrently with the S2067 wiring
of `PROFILE_EXPORTED` / `PROFILE_IMPORTED` events. The two edits did
not conflict at the file level, but the peer commit's CRLF→LF
normalisation of the file triggered git's "CRLF will be replaced by
LF" warning chain on subsequent commits. No work was lost.

### Collision 3: secure-storage event-record file additions

Several `.vault/exec/2026-05-22-secure-storage-production-hardening/`
step-record files were peer-added between successive `git status`
checks and `git add` invocations. The explicit-pathspec
`git add -- <pathspec>` discipline ensured only the authoring agent's
own files landed; the peer's records went under their own commits.

## Findings

### Finding 1 — opaque AeatError ErrorCode failure during peer-WIP race

**Pathway**: `aeat.core.errors.__init_subclass__` → `bind_error_code`
→ `_registry.py:222` ValueError.

**File**: `src/aeat/core/errors/__init__.py:95`.

**What is lost**: An operator running the test suite mid-collision
sees a `ValueError: AeatError subclass ... is missing a declared
ErrorCode registry entry`. The message does not signal that the
state is transient (a peer mid-edit), so an operator may chase it
as a defect to fix in their own work tree.

**Remediation**: The `bind_error_code` refusal could include a hint
that the class declaration may be from a peer commit in flight; the
operator-facing message should suggest `git status` + a re-run after
peer state settles. Tracked as a future follow-up Step under #627.

### Finding 2 — CRLF warnings on every commit during peer activity

**Pathway**: `.gitattributes` declares `* text=auto eol=lf` (line 2),
which is the canonical policy. Peer Windows worktrees with local
`autocrlf=true` introduce CRLF on commit, which git correctly
normalises but with a `warning:` on every affected file.

**File**: `.gitattributes:2`.

**What is lost**: Commit logs are noise-cluttered (~50 lines per
commit during peer-heavy windows); signal-to-noise drops.

**Remediation**: Closed under W13.P66.S404 — verification that
`.gitattributes` already declares the rule. No further code change
needed; the warnings are git doing the right thing.

### Finding 3 — peer-WIP file-additions to .vault/ between status and add

**Pathway**: Peer agent commits exec records (e.g.
`secure-storage-production-hardening-W12-P26-S117.md`) between a
`git status --short` snapshot and a `git add -- <pathspec>` call.

**What is lost**: The driving agent's `git add` does not include the
peer records, which is the correct outcome — they belong to the
peer's commit, not the driver's. Confirms the explicit-pathspec
discipline is working as intended.

**Remediation**: None needed. The discipline holds.

## Conclusion

The `aeat-git-worktree-safety` abort-on-WIP discipline held perfectly
during this session. No peer work was overwritten; no destructive
operations were attempted; every git commit landed only the authoring
agent's own files. The single operator-facing improvement surfaced is
the `bind_error_code` refusal text (Finding 1), which deserves a
focused follow-up Step under #627 if the collision pattern repeats.
