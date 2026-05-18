---
tags:
  - '#audit'
  - '#profile-lifecycle-cli'
date: '2026-05-18'
related:
  - "[[2026-05-18-profile-lifecycle-cli-adr]]"
  - "[[2026-05-18-profile-lifecycle-cli-plan]]"
  - "[[2026-05-17-profile-lifecycle-cli-cascade-closure-research]]"
---

# `profile-lifecycle-cli` audit: P01 cascade scope expansion

## Scope

Honest re-sizing of Phase P01 (crypto cutover + NIST passphrase
floor) after execution surfaced that the test-fixture cascade plus
the production master-key-consumption surface are wider than the
2026-05-18 cascade-closure plan sized. This audit records the new
sub-sequence and the dispatch strategy.

## Findings

### F1 - 96 test-fixture sites use `override_master_key_provider`

A first-pass regex migrated only 26 well-formed try/finally blocks.
The remaining 70 sites use shape-variants (no paired clear,
intervening engine setup between set and try, set-once-at-module-
level patterns) that need structural awareness no available tool
(stdlib `ast`, regex) can deliver without losing comments. Hand
migration across one commit is intractable for one agent.
Dispatch as a parallel swarm with each agent owning a directory.

### F2 - Production master-key surface is wider than P01 sized

`blob_store/_blob_store.py`, `blob_store/_materialisation.py`,
`secret_store/_secret_store.py`, `envelope/_envelope.py`, and
`_rotation.py` all call `provider.get_master_key()` directly. The
ADR's mandate to retire the ClassVar caches creates an Argon2-per-
operation perf cliff unless these production paths also migrate to
read from `BucketSession.dek` via `get_active_master_key()`. That
migration is not in the original P01 step list.

### F3 - Column path cut is mechanically separable

The `_resolve_master_key()` body becomes a one-line delegation to
`get_active_master_key()`. The 6 in-module call sites do not
change. The hard part is having sessions activated before the
column path runs, which is what F1's swarm closes.

### F4 - P01.S01 and P01.S02 already landed safely

The new `_active_session.py` plus its registry binding shipped as
commit `49af100d`. Forward-only additive, no production
consumers yet, ready to be wired by the sub-phases below.

## Recommendations

Restructure P01 into four sub-phases that ship as separate atomic
commits:

- **P01a (done)**: `_active_session.py` + registry binding.
- **P01b**: 96-file test-fixture migration. Dispatched as a
  parallel sub-agent swarm; each agent owns one directory
  (`outbound/`, `persistence/storage/`, `application/`, `domain/`,
  `entrypoints/`, `diagnostics/`); each agent commits its
  scope-only diff after local validation; the override seam stays
  intact through this phase.
- **P01c**: migrate production blob/secret/envelope/rotation from
  `provider.get_master_key()` to `get_active_master_key()`. Delete
  ClassVar caches on `KeyringMasterKeyProvider` and
  `FileFallbackMasterKeyProvider`, the `_purge_caches_at_exit`
  atexit hook, and the `_reset_for_tests` classmethods in the same
  commit.
- **P01d**: delete the override seam (`override_master_key_provider`
  function, module globals, re-exports). Replace
  `_resolve_master_key()` body with delegation. Land NIST 8-char
  passphrase floor and the AST-guard test in the same commit.

The original P01.S01 - S17 Step IDs remain immutable per the
plan-hardening rule; only the parallelisation prose changes.
Phases P02 and P03 stay as planned; their dependency on P01 is
unchanged because P01a through P01d all close before P02 / P03
start.
