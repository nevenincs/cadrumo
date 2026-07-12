---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S19'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S19 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Rename the product database filename without fallback and ## Scope

- `src/cadrumo core configuration/state routing`
- `persistence SQL and master-key consumers`
- `cohesive database tests/examples` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
