---
tags:
  - '#plan'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
modified: '2026-05-22'
tier: L2
related:
  - '[[2026-05-22-secure-object-backlog-drain-plan]]'
  - '[[2026-05-22-secure-object-backlog-drain-P03-summary]]'
  - '[[2026-05-22-secure-object-backlog-drain-p03-s07-review-audit]]'
  - '[[2026-06-04-secure-object-backlog-drain-adr]]'
  - '[[2026-06-04-secure-object-backlog-drain-research]]'
---


# `secure-object-backlog-drain` R2 plan: repository hygiene slice

### Phase `P01` - R2 slice inventory

Confirm the selected repository-test slice and the required injection
pattern before editing code.

- [x] `P01.S01` - inventory the R2 hygiene candidates and select exact repaired files; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`.

### Phase `P02` - repository test repair

Convert selected repository tests to settings-backed isolation and
explicit repository injection.

- [x] `P02.S02` - repair submission repository domain tests with explicit secure-object repository injection; `src/aeat/domain/submission/test_repository.py`.
- [x] `P02.S03` - repair invoice and transaction catalogue roundtrip tests with explicit secure-object repository injection; `src/aeat/domain/invoices/test_repository.py`.
- [x] `P02.S04` - remove repaired files from the explicit hygiene classification map; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`.

### Phase `P03` - verification and review

Run focused gates and persist the review trail for R2.

- [x] `P03.S05` - run scoped ruff, hygiene guard, and repaired repository tests; `src/aeat`.
- [x] `P03.S06` - run mandatory code review and persist the R2 audit; `.vault/audit`.
- [x] `P03.S07` - write the R2 closeout summary and next-scope notes; `.vault/exec`.
