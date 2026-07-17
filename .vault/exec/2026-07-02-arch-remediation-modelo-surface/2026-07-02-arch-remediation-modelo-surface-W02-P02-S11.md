---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Consume the single iva-wallet ownership declaration from the registry relation-source validator, removing the inline _IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS carve-out

## Scope

- `src/aeat/domain/calculations/registry/_validate_relation_sources.py`

## Description

- Replace the inline literal `_IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS` frozenset in the relation-source validator with the public canonical set.

## Outcome

The registry relation-source collision gate consumes the single declaration; the duplicated literal is gone. Commit `e353111d8`.

## Notes
