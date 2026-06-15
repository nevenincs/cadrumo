---
tags:
  - '#plan'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
tier: L3
related:
  - '[[2026-06-15-service-capabilities-research]]'
  - '[[2026-06-15-service-capabilities-adr]]'
  - '[[2026-06-15-dependency-provisioning-adr]]'
---








# `service-capabilities` plan

## Wave `W01` - Capability backend

Core ServiceCapability enum, the profile capabilities schema section, the resolution layer, and gate rewiring.


### Phase `W01.P01` - Core enum + schema section

Add ServiceCapability StrEnum in core and the capabilities section in the profile schema TOML.

- [x] `W01.P01.S01` - Add ServiceCapability StrEnum (cloud_evidence_upload, llm_vision, google_export) in core with per-member docstrings; `src/aeat/core`.
- [x] `W01.P01.S02` - Add a capabilities `[[sections]]` with boolean fields to the user_profile schema TOML; add a roundtrip test; `add a roundtrip test; `src/aeat/_data/registry/aeat/user_profile/schema.toml`.

### Phase `W01.P02` - Resolution layer + gates

Add resolve_capability and rewire cloud-evidence/vision/google gates through it.

- [x] `W01.P02.S03` - Add resolve_capability + CapabilityDecision overlaying profile facts onto the global Settings default (gestor-mode absolute bar first); `src/aeat/application/user_profile`.
- [x] `W01.P02.S04` - Rewire cloud_evidence_read_permitted, the vision path, and google export through resolve_capability with typed refusals; `src/aeat/application/ledger/_evidence_input.py`.

### Phase `W01.P03` - CLI + wizard

config profile capabilities show/set and a wizard capabilities section.

- [x] `W01.P03.S05` - Add config profile capabilities show/set verbs routed through EditProfileSectionCommand; `add a wizard capabilities section; `src/aeat/entrypoints/cli/_config`.
- [x] `W01.P03.S11` - Add a capabilities section to the wizard create/edit flow so opt-in/out is offered at profile creation; `src/aeat/application/wizard`.

## Wave `W02` - Dependency probes + graceful degradation

Typed dependency probes, close the Ollama headline gap, Playwright remediation, CLI error containment.

### Phase `W02.P04` - Dependency probes

Typed DependencyStatus + per-service probes (ollama/model, playwright, google, provider CLIs).

- [x] `W02.P04.S06` - Add DependencyStatus + per-service probes (ollama reachability/model, playwright, google creds, provider CLIs) that never raise on absence; `src/aeat/application`.

### Phase `W02.P05` - Close ungraceful paths

Ollama probe-before-inference refusal, CLI catches LLMProviderError/connection errors, providers vision row, Playwright hint.

- [x] `W02.P05.S07` - Probe Ollama before vision inference + refuse instructively; `widen classify CLI to catch LLMProviderError/connection errors; add ollama providers row; Playwright hint; `src/aeat/application/ledger, src/aeat/entrypoints/cli`.
- [x] `W02.P05.S12` - Add an Ollama/vision row to ledger providers and a playwright-install remediation hint to BrowserError; `src/aeat/entrypoints/cli/_ledger_read_cli.py, src/aeat/adapters/outbound/aeat/browser/session.py`.

## Wave `W03` - Doctor + provisioning

aeat config doctor, pyproject extras + torch relocation, just doctor and provisioning recipes.

### Phase `W03.P06` - config doctor

aeat config doctor reporting availability + capability posture + remediation per service.

- [x] `W03.P06.S08` - Add aeat config doctor: per-service availability + active-profile capability posture + remediation; `typed envelope + non-zero exit on opted-in-but-missing; `src/aeat/entrypoints/cli/_config`.

### Phase `W03.P07` - pyproject + justfile

Capability extras, torch relocation, just doctor/provision recipes, fix env-playwright, README reconcile.

- [x] `W03.P07.S09` - Capability extras + relocate torch; `just doctor/provision recipes; fix env-playwright; reconcile README/justfile; `pyproject.toml, justfile, README.md`.
- [x] `W03.P07.S10` - Tests + locales + how-to onboarding doc across capabilities, probes, doctor, provisioning; `src/aeat tests, src/aeat/locales, docs/how-to`.
- [x] `W03.P07.S13` - Investigate the torch placement (vaultspec-rag managed-torch-direct-dependency) and restructure pyproject: capability-mapped extras + relocate torch correctly; `pyproject.toml`.
- [x] `W03.P07.S14` - Write the onboarding how-to doc covering bootstrap, capabilities, and the doctor; `docs/how-to`.
- [x] `W03.P07.S15` - Verify: full focused suite + conformance + honesty review; `close the plan; `.vault/audit`.
- [x] `W03.P07.S16` - Gate every Google-write verb (verify, push, probe --no-read-only) on google_export with a no-allowlist conformance test (honesty review H1); `src/aeat/entrypoints/cli/_config/_google.py, src/aeat/entrypoints/cli/_config/_google_sync_calc.py`.
- [x] `W03.P07.S17` - DEFERRED follow-up: add an llm_vision=off two-mode (scan PDF + image) evidence-refusal regression (honesty review M1); `src/aeat/application/ledger/tests`.

## Description


## Steps







## Parallelization


## Verification

