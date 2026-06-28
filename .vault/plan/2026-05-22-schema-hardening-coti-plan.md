---
tags:
  - '#plan'
  - '#schema-hardening-coti'
date: '2026-05-22'
modified: '2026-05-22'
tier: L2
related:
  - '[[2026-05-22-schema-hardening-coti-adr]]'
  - '[[2026-05-22-schema-hardening-coti-research]]'
  - '[[2026-05-22-schema-hardening-adr]]'
  - '[[2026-05-22-schema-hardening-research]]'
  - '[[2026-05-21-schema-hardening-reference]]'
  - '[[2026-05-22-schema-hardening-plan]]'
---


# `schema-hardening-coti` `quoted-fund-coti-burn-down` plan

### Phase `P01` - Quoted-fund coti source confirmation

Confirm the exact committed-source and legal-publication boundary for the Modelo 100 quoted-fund coti family before code edits.

- [x] `P01.S01` - Confirm official and committed source context for quoted-fund coti roles; `.vault/audit`.
- [x] `P01.S02` - List the exact current coti warning-exposed committed registry rows; `src/aeat/_data/registry/aeat/modelos/100`.

### Phase `P02` - Coti optional-token implementation

Remove only coti from broad optional-token stripping and replace the hidden suppression with explicit reviewed singleton metadata.

- [x] `P02.S03` - Remove coti from broad optional semantic-role token stripping; `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`.
- [x] `P02.S04` - Mark the six reviewed quoted-fund coti singleton rows explicitly; `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas`.
- [x] `P02.S05` - Add coti boundary and committed singleton regression tests; `src/aeat/domain/calculations/registry/test_semantic_role.py`.

### Phase `P03` - Verification and review closure

Run focused gates and persist the vault audit review trail for the coti slice.

- [x] `P03.S06` - Run focused semantic-role and registry warning gates; `src/aeat/domain/calculations/registry`.
- [x] `P03.S07` - Update reference audit and review records for coti burn-down; `.vault`.
- [x] `P03.S08` - Create execution records and code review audit for coti slice; `.vault/exec`.
