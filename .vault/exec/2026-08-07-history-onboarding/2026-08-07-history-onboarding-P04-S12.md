---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b9d287028b997866610e5ea26a03bd1971028ccc9386fd62b85d93ef6a2fdac4'
step_id: 'S12'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# land real es, en, ca and hu values for every new help string, Notice message key and result-field label the P01 through P03 verbs introduce, verified by dev.locales scaffold --check, gated on the shared locale catalogues being free of unrelated in-flight writes before landing

## Scope

- `src/cadrumo/locales`

## Description

- Land real es, en, ca and hu values for all eleven new keys the P01 through P04 surfaces introduce.

## Outcome

Eleven keys across the CLI help, the operator help surface, the run advisories,
the denominator notes and the overview nudge, each with a real translation in all
four catalogues. No key echoes its own name and none was left to a scaffold
placeholder.

## Verification

src/cadrumo/locales/es.yml: +34 -0
    src/cadrumo/locales/en.yml: +29 -0
    src/cadrumo/locales/ca.yml: +33 -0
    src/cadrumo/locales/hu.yml: +30 -0
    COMMITTED 269b3be338

Verified at HEAD after landing: all four catalogues carry all eleven keys with
non-placeholder values.

## Notes

The catalogues are under continuous concurrent write, so every value was applied
through the locale tool's own batch API against a scratch copy of the HEAD blobs
and never against the working copy. That mattered: two earlier attempts would have
DELETED peer content — a `deudas` help block, two ledger-establishment refusal
messages — because the blob was derived from a HEAD snapshot minutes stale. The
landing now rebuilds from HEAD and refuses on any removed line, in the same
command as the commit.

The zero-removal check itself had to be fixed: built naively it rebuilt a
60,000-element set per line and hung for eleven minutes on a 3 MB catalogue.
