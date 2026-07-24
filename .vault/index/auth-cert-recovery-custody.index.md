---
generated: true
tags:
  - '#index'
  - '#auth-cert-recovery-custody'
date: '2026-07-24'
modified: '2026-07-24'
related:
  - '[[2026-07-17-auth-cert-recovery-custody-P04-S22]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P04-S23]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P04-S24]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P04-S25]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P04-S26]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P04-S27]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P04-S28]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P04-S29]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P04-S30]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P04-S31]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P05-S32]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P05-S33]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P05-S34]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P06-S35]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P06-S36]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P06-S37]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P06-S38]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P06-S39]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P06-S40]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P07-S41]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P07-S42]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P07-S43]]'
  - '[[2026-07-17-auth-cert-recovery-custody-P08-S44]]'
  - '[[2026-07-17-auth-cert-recovery-custody-adr]]'
  - '[[2026-07-17-auth-cert-recovery-custody-audit]]'
  - '[[2026-07-17-auth-cert-recovery-custody-plan]]'
  - '[[2026-07-24-auth-cert-recovery-custody-close-honesty-review-audit]]'
---

# `auth-cert-recovery-custody` feature index

Auto-generated index of all documents tagged with `#auth-cert-recovery-custody`.

## Documents

### adr

- `2026-07-17-auth-cert-recovery-custody-adr` - `auth-cert-recovery-custody` adr: `auth-cert-recovery-custody rescope grounding` | (**status:** `accepted`)

### audit

- `2026-07-17-auth-cert-recovery-custody-audit` - `auth-cert-recovery-custody` audit: `certificate secret door safety review`
- `2026-07-24-auth-cert-recovery-custody-close-honesty-review-audit` - `auth-cert-recovery-custody` audit: `close honesty review`

### exec

- `2026-07-17-auth-cert-recovery-custody-P05-S32` - Remove certificate backend selection and key set, remove certificate secrets only by name through secure storage, and expose no compatibility alias or migration surface
- `2026-07-17-auth-cert-recovery-custody-P05-S33` - Prove certificate secret set and remove against real secure storage, including command failure after the secret mutation but before event commit followed by an idempotent retry with one correctly classified event, and reject backend selection, keyring spellings, migration, fallback, and duplicate mutation paths
- `2026-07-17-auth-cert-recovery-custody-P05-S34` - Require yes for auth reset while keeping auth status and auth test non-destructive
- `2026-07-17-auth-cert-recovery-custody-P06-S35` - Remove certificate backend selectors from every payload and schema projection while preserving independent master-key keyring custody contracts
- `2026-07-17-auth-cert-recovery-custody-P07-S41` - Thread constructor secret_store: SecretStore|None=None dependency-injection through the secret-store factory, certificate-secret backend, certificate-sources check, and materialisation helpers
- `2026-07-17-auth-cert-recovery-custody-P07-S42` - Add an AST recurrence gate, patterned on test_wizard_prompter_singularity.py, that bans module-global _override_* factory state and public override_* setters in production, exempting only the sanctioned core.config.override_settings
- `2026-07-17-auth-cert-recovery-custody-P07-S43` - Sweep the storage facade and generated API docs for the removed override_secret_store export and update the import-hygiene baseline after the seam removal
- `2026-07-17-auth-cert-recovery-custody-P04-S22` - Replace config rekey with only config passphrase change and secure input handling
- `2026-07-17-auth-cert-recovery-custody-P04-S23` - Replace recovery display and rotation spellings with recovery status, create, and rotate
- `2026-07-17-auth-cert-recovery-custody-P04-S24` - Register only recovery verify and flat recover with secrets-stdin and no mnemonic argv
- `2026-07-17-auth-cert-recovery-custody-P04-S25` - Write create and rotate candidates directly to the controlling terminal and require full no-echo retype before commit
- `2026-07-17-auth-cert-recovery-custody-P04-S26` - Replace obsolete bootstrap exemptions with the exact accepted passphrase and recovery paths
- `2026-07-17-auth-cert-recovery-custody-P04-S27` - Prove passphrase change through a real encrypted vault
- `2026-07-17-auth-cert-recovery-custody-P04-S28` - Prove recovery status, create, rotate, verify, and recover without serialized mnemonic material
- `2026-07-17-auth-cert-recovery-custody-P04-S29` - Prove passphrases, mnemonics, and secret-input values are absent from help and examples
- `2026-07-17-auth-cert-recovery-custody-P04-S30` - Prove secure TTY failures and strict bounded secrets-stdin JSON through localized CLI execution
- `2026-07-17-auth-cert-recovery-custody-P04-S31` - Align bootstrap and repair-policy inventories with the recovery family and flat recover exception
- `2026-07-17-auth-cert-recovery-custody-P06-S36` - Migrate the auth, certificate, and recovery help and risk metadata to the accepted grammar
- `2026-07-17-auth-cert-recovery-custody-P06-S37` - Migrate the four locale catalogues for the auth, certificate, and recovery families through the locales CLI
- `2026-07-17-auth-cert-recovery-custody-P06-S38` - Re-arm the MCP mirror for the accepted auth, certificate, and recovery verbs
- `2026-07-17-auth-cert-recovery-custody-P06-S39` - Regenerate the CLI reference and operator how-to pages for the auth, certificate, and recovery families from the frozen live surface
- `2026-07-17-auth-cert-recovery-custody-P06-S40` - Prove the removed auth, certificate, and recovery spellings are absent from every source and generated surface
- `2026-07-17-auth-cert-recovery-custody-P08-S44` - DEFERRED until the operator P04 passphrase door commits: make certificate secret set reject the passphrase as an argv value and read it only via the hidden prompt or bounded stdin, reusing the P04 door _secure_input.py bounded-stdin no-echo infrastructure rather than building a parallel secret-input authority, gated on a test proving the passphrase cannot be supplied as an argv value and is read only through hidden prompt or bounded stdin

### plan

- `2026-07-17-auth-cert-recovery-custody-plan` - `auth-cert-recovery-custody` plan
