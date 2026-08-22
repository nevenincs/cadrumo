---
tags:
  - '#plan'
  - '#profile-registration-password-policy'
date: '2026-08-22'
tier: L3
related:
  - '[[2026-08-22-profile-registration-password-policy-canonical-credential-capability-adr]]'
  - '[[2026-08-22-profile-registration-password-policy-holistic-credential-capability-research]]'
  - '[[2026-08-22-profile-registration-password-policy-tui-custody-validation-mismatch-reference]]'
modified: '2026-08-22'
body_hash: 'sha256:25f276202f46d697e35f1fc674ec97d69eb6e1349834d79b2ee414148dc64559'
---

<!-- RETIRED: S01 -->

# `profile-registration-password-policy` plan

## Steps

## Wave `W01` - establish canonical credential authorities

Create the dependency-safe core authority, remove stale profile policy, separate recovery transport, and integrate custody before downstream application work.

### Phase `W01.P01` - define the core profile-password contract

Deliver one pure typed exact-sequence assessment and retire the obsolete eight-character profile policy.

- [ ] `W01.P01.S02` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then implement the canonical profile-password assessment, typed reasons, safe derived facts, exact-sequence behavior, and advisory strength while deleting obsolete generic profile-policy branches; `src/cadrumo/core/_credentials.py`.
- [ ] `W01.P01.S03` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then expose only canonical profile-password and retained non-profile credential capabilities while removing stale exports and lazy mappings without aliases; `src/cadrumo/core/__init__.py`.
- [ ] `W01.P01.S04` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then prove scalar and byte boundaries, surrogate refusal, safe reasons, advisory independence, and composed/decomposed exact preservation; `src/cadrumo/core/tests/test_credentials.py`.

### Phase `W01.P02` - consume the canonical contract in custody

Deliver defense-in-depth custody validation consuming core authority without owning operator prose or duplicate limits.

- [ ] `W01.P02.S05` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then make custody consume the canonical contract, remove duplicate constants and exports, and prove strict defense-in-depth boundaries plus obsolete-symbol absence; `src/cadrumo/adapters/persistence/storage/custody`.

### Phase `W01.P03` - separate recovery-secret encoding

Deliver a dedicated recovery codec shared by parent and supervised worker without changing mnemonic or envelope bytes.

- [ ] `W01.P03.S06` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then separate recovery-secret encoding across parent and worker and prove unchanged mnemonic, envelope, transport, and derivation roundtrips; `src/cadrumo/adapters/persistence/storage/custody`.

## Wave `W02` - make application capabilities typed and mutation-safe

Map prospective and proof operations through typed application outcomes before any inbound presentation changes.

### Phase `W02.P04` - repair registration and rotation

Deliver typed prospective-password refusals before KDF, locking, staging, journaling, re-heading, or publication.

- [ ] `W02.P04.S07` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then map canonical prospective refusals through registration and rotation before mutation, delete stale application policy paths, and prove exact no-mutation behavior; `src/cadrumo/application/user_profile`.

### Phase `W02.P05` - collapse authentication failures without hiding operational faults

Deliver one public proof refusal for malformed and incorrect passwords while preserving operational classifications.

- [ ] `W02.P05.S08` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then collapse malformed and incorrect existing-password proofs without hiding operational faults and prove login restore and recovery authorization behavior; `src/cadrumo/application/user_profile`.

## Wave `W03` - localize and harden every inbound credential surface

Align TUI, scripted CLI, locale ownership, and cross-surface regression behavior after application contracts stabilize.

### Phase `W03.P06` - align TUI assessment and submission

Deliver localized typed live feedback and submission without INTERNAL handling for expected credential refusals.

- [ ] `W03.P06.S09` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then align TUI assessment, registration attempts, and expected-error rendering with localized secret-safe application outcomes; `src/cadrumo/adapters/inbound/tui`.

### Phase `W03.P07` - align scripted CLI and locale ownership

Deliver scripted creation parity and complete real translations maintained only through the locale CLI.

- [ ] `W03.P07.S10` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then align scripted CLI and typed error registration, then manage complete real translations exclusively through dev.locales; `src/cadrumo/entrypoints/cli/_config`.

### Phase `W03.P08` - prove cross-surface and language parity

Deliver real headless TUI and scripted CLI regressions for the original crash and canonical boundaries.

- [ ] `W03.P08.S11` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then prove real TUI scripted CLI and all-language parity at scalar byte surrogate and exact-Unicode boundaries with no persistence on refusal; `profile credential inbound tests`.

## Wave `W04` - reconcile documentation and prove campaign closure

Remove residual bloat, update generated surfaces, run repository gates, formally review, and close with a fresh-context honesty audit.

### Phase `W04.P09` - remove residual bloat and reconcile documentation

Deliver no stale symbols, prose, generated references, or compatibility scaffolding.


### Phase `W04.P10` - run security and repository quality gates

Deliver focused and tree-wide evidence for behavior, architecture, localization, and documentation.


### Phase `W04.P11` - review and close honestly

Deliver independent formal review and fresh-context proof against the ADR and active goal.
