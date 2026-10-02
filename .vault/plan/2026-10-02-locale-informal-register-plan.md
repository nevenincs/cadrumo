---
tags:
  - '#plan'
  - '#locale-informal-register'
date: '2026-10-02'
tier: L1
related:
  - '[[2026-07-12-multilang-externalization-adr]]'
  - '[[2026-08-04-modelo-localization-cascade-adr]]'
  - '[[2026-08-16-locale-catalogue-sharding-adr]]'
modified: '2026-10-02'
body_schema: body-v2
body_hash: 'sha256:70ef6d3d6f85343c605f888cc80374378bf56e6bf1d5dc09311a6e9251117512'
---

# Normalize runtime translations to informal singular address

## Description

Approved 2026-10-02. The operator requested all remaining translation fixes with a fleet after accepting the measured pilot. Normalize application-authored Spanish, Catalan and Hungarian runtime copy to informal singular address. Preserve official Spanish, corpus excerpts, quoted text, placeholders, commands, meaning and concurrent edits. The existing externalization ADR governs canonical catalogues, the Modelo localization ADR governs official source preservation, and the sharding ADR governs scoped writes across S01-S05. This correction introduces no costly architecture decision.

The operator subsequently authorized committing this completed runtime correction and continuing the PO findings on 2026-10-02. Shared catalogue commits include only reviewed owned coordinates; concurrent TUI additions remain with their caller changes.

## Steps

- [x] `S01` - Normalize Catalan and Spanish runtime address; `src/cadrumo/locales/ca and src/cadrumo/locales/es non-schema shards`.
- [x] `S02` - Normalize Hungarian CLI, error and wizard address; `src/cadrumo/locales/hu/cli.yml, src/cadrumo/locales/hu/errors.yml, src/cadrumo/locales/hu/wizard.yml`.
- [x] `S03` - Normalize remaining Hungarian runtime address; `src/cadrumo/locales/hu non-schema shards except cli.yml, errors.yml and wizard.yml`.
- [x] `S04` - Resolve residual signals and independently review rewritten meaning; `scratch_locale_tone controller, exact-span adjudications and assigned locale values`.
- [x] `S05` - Verify catalogue integrity and close the integrated review; `locale verification, plan ledger and rolling audit`.

## Parallelization

S01, S02 and S03 ran concurrently with disjoint locale/shard ownership. S03's hu/common.yml ownership was explicitly handed off to a separate writer. Workers wrote assigned values through the canonical locale writer and their own scratch reports. The supervisor owned snapshots, adjudications, independent reviews, verification and vault metadata. After S04 and S05 passed, the operator authorized committing the completed runtime correction. Commit only owned changes; no push or publication is authorized.

## Verification

Require gate_value zero: unresolved candidate strings plus invalid or stale adjudications plus unreviewed rewrites plus unexplained protected-source drift plus invalid external provenance. Require independent meaning and register review of every rewritten value, exact-span evidence for exceptions, preserved placeholders, commands, quotations and authority text, and passing catalogue completeness, reserved-token, locale parity and live-rendering checks. Reconcile key coverage with the live owning source scanner, recording removal of proven unused leaves separately. Preserve original snapshots when concurrent source changes arrive; accept only exact independently reviewed provenance receipts and fail on later unexplained drift. Require integrated review PASS before closure.
