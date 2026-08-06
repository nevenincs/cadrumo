---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:f1959178dbfe8360cee357905ebe70aa2bf53652c9e6b0fe6fe3a4864ea2fbd2'
step_id: 'S19'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename the product database filename without fallback

## Scope

- `src/cadrumo core configuration/state routing`
- `persistence SQL and master-key consumers`
- `cohesive database tests/examples`

## Description

- Ground the database filename boundary in the accepted state matrix, live configuration route, SQL engine, master-key consumer, and real persistence tests.
- Expand the Step scope through the plan CLI to cover core route derivation, SQL/master-key consumers, and cohesive tests and examples.
- Replace the product-owned database filename with `cadrumo.db` across every active source and test consumer.
- Refuse canonical root, bucket, and explicit SQLite targets using the retired filename before opening or creating a database.
- Preserve former-file bytes and prohibit fallback, migration, copy, move, alias, or schema alteration.

## Outcome

The authoritative default routes now derive `cadrumo.db` for both root fallback and active-profile buckets, route classification recognizes only that filename, and production consumers inspect the Cadrumo database. The controlled update changed 47 existing source/test files with 91 filename substitutions, plus the state/SQL refusal implementation and its real-filesystem tests.

Canonical former databases are detected with filesystem metadata only and raise `FormerProductStateError` before a URL is returned. An explicitly configured SQLite target named `aeat.db` raises `StorageError` before its parent directory or engine is created. The real tests preserve sentinel bytes and prove that no Cadrumo database appears during refusal.

The clean checkout-shaped verification mirror passed all 52 focused core route, SQL engine, storage runtime, and secure-SQL tests. Exact residue classification leaves the retired filename only in the single refusal constant and four refusal-test constructions.

## Notes

The first focused invocation in the shared checkout refused during collection because its local state tree already contains a former database. That file was not opened, read, modified, moved, copied, deleted, or committed. The same test set passed in a clean checkout-shaped mirror. User-authorized overlap preservation was honored; unrelated dirty product-identity and operator-surface paths are excluded from this commit.
