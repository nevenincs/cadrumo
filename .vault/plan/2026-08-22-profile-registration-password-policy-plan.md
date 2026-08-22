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
body_hash: 'sha256:dcb7acf37140afd3cf336d21c537b5f12d22929027b7528492982b41deadb91f'
---

<!-- RETIRED: S01 -->

# `profile-registration-password-policy` plan

Canonicalize profile credential capabilities from core through every operator surface,
delete superseded policy code, and prove secure localized non-oracular behavior without
persistence mutation on refusal.

## Description

This plan executes the accepted canonical credential capability ADR as one ordered
campaign. W01 establishes the dependency-safe core authority, removes the stale profile
policy, separates recovery transport, and integrates custody. W02 maps prospective and
proof operations through typed application outcomes before mutation. W03 updates TUI,
scripted CLI, error registration, locales, and integrated regressions. W04 removes
residual bloat, reconciles generated and operator documentation, runs repository gates,
conducts formal review, and closes only after a fresh-context honesty audit.

Every Step begins with semantic discovery of current code and governing ADRs through
`vaultspec-rag`, followed by exact-symbol confirmation through `rg`, a current-HEAD
reread, and overlapping-diff inspection. Superseded constants, exports, validators,
branches, messages, and tests are deleted. No aliases, shims, fallbacks, compatibility
paths, or parallel policy implementations are permitted.

## Steps

## Wave `W01` - establish canonical credential authorities

Create the dependency-safe core authority, remove stale profile policy, separate recovery transport, and integrate custody before downstream application work.

### Phase `W01.P01` - define the core profile-password contract

Deliver one pure typed exact-sequence assessment and retire the obsolete eight-character profile policy.

- [x] `W01.P01.S02` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then implement the canonical profile-password assessment, typed reasons, safe derived facts, exact-sequence behavior, and advisory strength while deleting obsolete generic profile-policy branches; `src/cadrumo/core/_credentials.py`.
- [x] `W01.P01.S03` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then expose only canonical profile-password and retained non-profile credential capabilities while removing stale exports and lazy mappings without aliases; `src/cadrumo/core/__init__.py`.
- [x] `W01.P01.S04` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then prove scalar and byte boundaries, surrogate refusal, safe reasons, advisory independence, and composed/decomposed exact preservation; `src/cadrumo/core/tests/test_credentials.py`.

### Phase `W01.P02` - consume the canonical contract in custody

Deliver defense-in-depth custody validation consuming core authority without owning operator prose or duplicate limits.

- [x] `W01.P02.S05` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then make custody consume the canonical contract, remove duplicate constants and exports, and prove strict defense-in-depth boundaries plus obsolete-symbol absence; `src/cadrumo/adapters/persistence/storage/custody`.

### Phase `W01.P03` - separate recovery-secret encoding

Deliver a dedicated recovery codec shared by parent and supervised worker without changing mnemonic or envelope bytes.

- [x] `W01.P03.S06` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then separate recovery-secret encoding across parent and worker and prove unchanged mnemonic, envelope, transport, and derivation roundtrips; `src/cadrumo/adapters/persistence/storage/custody`.

## Wave `W02` - make application capabilities typed and mutation-safe

Map prospective and proof operations through typed application outcomes before any inbound presentation changes.

### Phase `W02.P04` - repair registration and rotation

Deliver typed prospective-password refusals before KDF, locking, staging, journaling, re-heading, or publication.

- [x] `W02.P04.S07` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then map canonical prospective refusals through registration and rotation before mutation, delete stale application policy paths, and prove exact no-mutation behavior; `src/cadrumo/application/user_profile`.

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

- [ ] `W04.P09.S12` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then delete repository-wide policy bloat and stale prose, reconcile docstrings, and regenerate only feature-owned API and operator documentation; `repository profile credential documentation surface`.

### Phase `W04.P10` - run security and repository quality gates

Deliver focused and tree-wide evidence for behavior, architecture, localization, and documentation.

- [ ] `W04.P10.S13` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then run focused anti-regression tests structural audits locale and documentation gates feature-surface checks full tests and vault checks; `repository quality gates`.

### Phase `W04.P11` - review and close honestly

Deliver independent formal review and fresh-context proof against the ADR and active goal.

- [ ] `W04.P11.S14` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then perform formal Vaultspec code review and action every architecture security secret localization recovery test bloat and documentation finding; `profile-registration-password-policy review`.
- [ ] `W04.P11.S15` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then run a fresh-context honesty audit proving every ADR and active-goal requirement from current code runtime storage tests artifacts and gates; `profile-registration-password-policy honesty audit`.
- [ ] `W04.P11.S16` - Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then reconcile Step Records Phase Summaries plan state vault links and final checks with no unsupported closure; `profile-registration-password-policy Vaultspec records`.

## Parallelization

Waves are ordered: W01 before W02, W02 before W03, and W03 before W04. Within W01,
P01 establishes the core API before P02 and P03 modify consumers. Custody integration
and recovery-codec work may proceed independently after P01 only when ownership of the
shared KDF modules is serialized. Within W02, prospective and proof mapping can be
researched in parallel, but their production edits share application facade ownership
and land coherently. Within W03, TUI and scripted CLI work can proceed independently
after W02; integrated language-parity tests follow both. Locale writes are serialized
through `dev.locales`. Formal review follows implementation and gates; the honesty audit
follows review remediation; Vaultspec reconciliation is last.

Every dispatch repeats the Step's semantic code and ADR grounding, exact-symbol
confirmation, plan status, `git log --grep`, HEAD reread, and overlap inspection.

## Verification

The plan is complete only when one core contract exclusively owns 15 through 256
Unicode scalars, at most 1,024 strict UTF-8 bytes, surrogate refusal, no rewriting,
typed safe reasons, and advisory strength; registration and rotation reject invalid
prospective passwords before KDF, locks, staging, journaling, re-heading, or publication;
and every refused operation leaves profile, session, envelope, recovery, inventory, and
record state unchanged.

Login, restore, current-password authorization, recovery export, and recovery removal
must expose malformed and incorrect passwords identically without candidate measurements,
while integrity, corruption, supervision, transaction, resource, and unavailable-storage
failures remain distinct. Recovery secrets must use a dedicated parent-and-worker codec,
retain exact mnemonic and envelope bytes, and never call profile-password validation.

Direct application, live TUI feedback, TUI submission, and scripted CLI must agree at
14, 15, 256, and 257 scalars and at 1,024 and 1,025 bytes. Composed and decomposed
accepted credentials remain byte-exact. Every supported locale renders one coherent
message; expected refusals contain no INTERNAL guidance, raw custody prose, traceback,
or submitted secret. Rotation preserves the DEK epoch, recovery enrollment, committed
records, generation lineage, and session revocation. Existing envelopes and recovery
roundtrips remain unchanged.

Repository searches must prove retired constants, duplicate validators, stale keys,
recovery/password coupling, aliases, shims, and compatibility branches absent. Locale
and API scaffolding checks, translation parity and honesty, documented-command
conformance, nitpicky Sphinx, focused tests, anti-regression bite proofs, ruff, structural
audits, feature-surface gates, prescribed full tests, plan checks, and vault checks must
pass. Formal review findings are resolved, the honesty audit proves every ADR and goal
criterion, and every closed Step has matching execution evidence.
