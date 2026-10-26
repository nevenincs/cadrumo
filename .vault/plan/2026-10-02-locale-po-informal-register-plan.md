---
tags:
  - '#plan'
  - '#locale-po-informal-register'
date: '2026-10-02'
tier: L1
related:
  - '[[2026-07-18-user-docs-localization-adr]]'
  - '[[2026-07-12-multilang-externalization-adr]]'
modified: '2026-10-02'
body_schema: body-v2
body_hash: 'sha256:0397bafa11563be8ae4c800f281734cb035ed21ec6739627bb0bedd61ee6f5f2'
---

# Documentation PO informal register and runtime commit

## Description

Approved 2026-10-02. The operator requested committing the completed runtime localization correction and continuing the documentation PO findings. The accepted gettext and externalization ADRs cover S02-S05; this correction makes no costly architecture decision. Preserve English message identities, official excerpts, code, links, placeholders, catalogue metadata, third-party subjects and concurrent edits. S01 commits only owned runtime changes. No push is authorized.

## Steps

- [x] `S01` - Review fresh runtime drift and commit only the completed owned corrections; `owned runtime catalogue coordinates, tests, locale rule and prior vault records`.
- [x] `S02` - Discover and normalize Catalan documentation address; `docs/locales/ca/LC_MESSAGES/**/*.po`.
- [x] `S03` - Discover and normalize Spanish documentation address; `docs/locales/es/LC_MESSAGES/**/*.po`.
- [x] `S04` - Discover and normalize Hungarian documentation address; `docs/locales/hu/LC_MESSAGES/**/*.po`.
- [x] `S05` - Review residual signals, repair the scoped pre-existing source delta, verify documentation integrity and commit the PO corrections; `scratch PO detector, owning docs verification, how-to/review-calculation-values PO synchronization, PO catalogues and plan/audit/ledger`.

## Parallelization

After root freezes a live PO inventory and exact packets, Catalan, Spanish and Hungarian PO translations may be handled concurrently by exclusive catalogue writers. Hungarian catalogues are partitioned into three disjoint file groups. Root owns tooling, baselines, numerical convergence, independent reviews, tests, vault records and commits. Reuse the authorized Luna Max fleet with fresh bounded assignments.

## Verification

Require unresolved documentation address signals, stale decisions, unreviewed rewrites and structural or source drift to converge to zero. Validate real PO parsing, non-fuzzy completeness, preserved identities and metadata, literal controls, fresh source drift and localized rendering through the owning docs gates. Independently review every rewritten value and each exact-span exception. Commit only verified owned changes and preserve unrelated worktree and index contents.
