---
generated: true
tags:
  - '#index'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - '[[2026-07-17-auth-cert-recovery-custody-P05-S32]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P05-S33]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P05-S34]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P06-S35]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P07-S42]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P07-S43]]'
  - '[[2026-07-17-auth-cert-recovery-custody-adr]]'
  - '[[2026-07-17-auth-cert-recovery-custody-audit]]'
  - '[[2026-07-17-auth-cert-recovery-custody-plan]]'
---

# `auth-cert-recovery-custody` feature index

Auto-generated index of all documents tagged with `#auth-cert-recovery-custody`.

## Documents

### adr

- `2026-07-17-auth-cert-recovery-custody-adr` - `auth-cert-recovery-custody` adr: `auth-cert-recovery-custody rescope grounding` | (**status:** `accepted`)

### audit

- `2026-07-17-auth-cert-recovery-custody-audit` - `auth-cert-recovery-custody` audit: `certificate secret door safety review`

### exec

- `2026-07-17-auth-cert-recovery-custody-P05-S32` - Remove certificate backend selection and key set, remove certificate secrets only by name through secure storage, and expose no compatibility alias or migration surface
- `2026-07-17-auth-cert-recovery-custody-P05-S33` - Prove certificate secret set and remove against real secure storage, including command failure after the secret mutation but before event commit followed by an idempotent retry with one correctly classified event, and reject backend selection, keyring spellings, migration, fallback, and duplicate mutation paths
- `2026-07-17-auth-cert-recovery-custody-P05-S34` - Require yes for auth reset while keeping auth status and auth test non-destructive
- `2026-07-17-auth-cert-recovery-custody-P06-S35` - Remove certificate backend selectors from every payload and schema projection while preserving independent master-key keyring custody contracts
- `2026-07-17-auth-cert-recovery-custody-P07-S42` - Add an AST recurrence gate, patterned on test_wizard_prompter_singularity.py, that bans module-global _override_* factory state and public override_* setters in production, exempting only the sanctioned core.config.override_settings
- `2026-07-17-auth-cert-recovery-custody-P07-S43` - Sweep the storage facade and generated API docs for the removed override_secret_store export and update the import-hygiene baseline after the seam removal

### plan

- `2026-07-17-auth-cert-recovery-custody-plan` - `auth-cert-recovery-custody` plan
