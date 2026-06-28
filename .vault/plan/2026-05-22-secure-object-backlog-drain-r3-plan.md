---
tags:
  - '#plan'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
modified: '2026-05-22'
tier: L2
related:
  - '[[2026-05-22-secure-object-backlog-drain-r2-plan]]'
  - '[[2026-05-22-secure-object-backlog-drain-r2-P03-summary]]'
  - '[[2026-05-22-secure-object-backlog-drain-r2-p03-s06-review-audit]]'
  - '[[2026-06-04-secure-object-backlog-drain-adr]]'
  - '[[2026-06-04-secure-object-backlog-drain-research]]'
---


# `secure-object-backlog-drain` R3 plan: secure-storage roundtrip hygiene slice

### Phase `P01` - R3 slice inventory

Confirm the selected secure-storage roundtrip files and injection
pattern before edits.

- [x] `P01.S01` - inventory R3 secure-storage candidates and select exact repaired files; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`.

### Phase `P02` - secure-storage roundtrip repair

Repair the selected proof tests without weakening their boundary
assertions.

- [x] `P02.S02` - repair submission secure-storage roundtrip tests with explicit repository injection; `src/aeat/domain/submission/test_secure_storage_roundtrip.py`.
- [x] `P02.S03` - repair invoice secure-storage roundtrip tests with explicit repository injection; `src/aeat/domain/invoices/test_secure_storage_roundtrip.py`.
- [x] `P02.S04` - repair justificante secure-storage roundtrip tests with explicit repository injection; `src/aeat/domain/justificante/test_secure_storage_roundtrip.py`.
- [x] `P02.S05` - repair modelos work-unit secure-storage roundtrip tests with explicit repository injection; `src/aeat/domain/modelos/test_secure_storage_roundtrip.py`.
- [x] `P02.S06` - remove repaired files from the explicit hygiene classification map; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`.

### Phase `P03` - verification and review

Run focused gates and persist the R3 review trail.

- [x] `P03.S07` - run scoped ruff, hygiene guard, and repaired secure-storage roundtrip tests; `src/aeat`.
- [x] `P03.S08` - run mandatory code review and persist the R3 audit; `.vault/audit`.
- [x] `P03.S09` - write the R3 closeout summary and next-scope notes; `.vault/exec`.
