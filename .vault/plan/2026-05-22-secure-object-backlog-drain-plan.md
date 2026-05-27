---
tags:
  - '#plan'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
tier: L2
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
  - '[[2026-05-22-secure-object-integrity-P02-S06-review]]'
  - '[[2026-05-22-secure-object-integrity-P05-S16-review]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `secure-object-backlog-drain` plan: audit-derived catalogue and hygiene cleanup

### Phase `P01` - locale catalogue placeholder drain

Remove known registry-source scaffold self-references from the locale
catalogues without broad translation churn.

- [x] `P01.S01` - audit the locale catalogues for registry-source scaffold self-references; `src/aeat/locales`.
- [x] `P01.S02` - replace registry-source CLI help placeholders through the locale workflow; `src/aeat/locales`.
- [x] `P01.S03` - run locale audit, scaffold, parity, and honesty gates; `src/aeat/locales`.

### Phase `P02` - secure-SQL hygiene exception drain

Reduce the explicit P02.S06 hygiene exception list by repairing a small
set of real-behavior tests.

- [x] `P02.S04` - inventory classified hygiene exceptions and select a first repair slice; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`.
- [x] `P02.S05` - repair the selected storage-hygiene slice with explicit isolation or repository injection; `src/aeat`.
- [x] `P02.S06` - run focused hygiene and repaired-module tests; `src/aeat`.

### Phase `P03` - review and closeout

Persist the review trail and keep any remaining debt classified.

- [x] `P03.S07` - run mandatory code review and persist backlog-drain audit findings; `.vault/audit`.
- [x] `P03.S08` - write the backlog-drain phase summary and next-scope notes; `.vault/exec`.
