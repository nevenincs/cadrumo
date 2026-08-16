---
generated: true
tags:
  - '#index'
  - '#service-capabilities'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:d164c59248ac26ad59fc6c1954188af88367640451b663bba760790a073cc685'
related:
  - '[[2026-06-15-service-capabilities-W01-P01-S01]]'
  - '[[2026-06-15-service-capabilities-W01-P01-S02]]'
  - '[[2026-06-15-service-capabilities-W01-P02-S03]]'
  - '[[2026-06-15-service-capabilities-W01-P02-S04]]'
  - '[[2026-06-15-service-capabilities-W01-P03-S05]]'
  - '[[2026-06-15-service-capabilities-W01-P03-S11]]'
  - '[[2026-06-15-service-capabilities-W02-P04-S06]]'
  - '[[2026-06-15-service-capabilities-W02-P05-S07]]'
  - '[[2026-06-15-service-capabilities-W02-P05-S12]]'
  - '[[2026-06-15-service-capabilities-W03-P06-S08]]'
  - '[[2026-06-15-service-capabilities-W03-P07-S09]]'
  - '[[2026-06-15-service-capabilities-W03-P07-S10]]'
  - '[[2026-06-15-service-capabilities-W03-P07-S13]]'
  - '[[2026-06-15-service-capabilities-W03-P07-S14]]'
  - '[[2026-06-15-service-capabilities-W03-P07-S15]]'
  - '[[2026-06-15-service-capabilities-W03-P07-S16]]'
  - '[[2026-06-15-service-capabilities-W03-P07-S17]]'
  - '[[2026-06-15-service-capabilities-adr]]'
  - '[[2026-06-15-service-capabilities-audit]]'
  - '[[2026-06-15-service-capabilities-plan]]'
  - '[[2026-06-15-service-capabilities-research]]'
---

# `service-capabilities` feature index

Auto-generated index of all documents tagged with `#service-capabilities`.

## Documents

### adr

- `2026-06-15-service-capabilities-adr` - `service-capabilities` adr: `Profile-linked service capabilities: opt-in/opt-out for Google export, LLM vision, and cloud evidence upload` | (**status:** `accepted`)

### audit

- `2026-06-15-service-capabilities-audit` - `service-capabilities` audit: `service-capabilities campaign close honesty review`

### exec

- `2026-06-15-service-capabilities-W01-P01-S01` - Add ServiceCapability StrEnum (cloud_evidence_upload, llm_vision, google_export) in core with per-member docstrings
- `2026-06-15-service-capabilities-W01-P01-S02` - Add a capabilities `[[sections]]` with boolean fields to the user_profile schema TOML
- `2026-06-15-service-capabilities-W01-P02-S03` - Add resolve_capability + CapabilityDecision overlaying profile facts onto the global Settings default (gestor-mode absolute bar first)
- `2026-06-15-service-capabilities-W01-P02-S04` - Rewire cloud_evidence_read_permitted, the vision path, and google export through resolve_capability with typed refusals
- `2026-06-15-service-capabilities-W01-P03-S05` - Add config profile capabilities show/set verbs routed through EditProfileSectionCommand
- `2026-06-15-service-capabilities-W01-P03-S11` - Add a capabilities section to the wizard create/edit flow so opt-in/out is offered at profile creation
- `2026-06-15-service-capabilities-W02-P04-S06` - Add DependencyStatus + per-service probes (ollama reachability/model, playwright, google creds, provider CLIs) that never raise on absence
- `2026-06-15-service-capabilities-W02-P05-S07` - Probe Ollama before vision inference + refuse instructively
- `2026-06-15-service-capabilities-W02-P05-S12` - Add an Ollama/vision row to ledger providers and a playwright-install remediation hint to BrowserError
- `2026-06-15-service-capabilities-W03-P06-S08` - Add aeat config doctor: per-service availability + active-profile capability posture + remediation
- `2026-06-15-service-capabilities-W03-P07-S09` - Capability extras + relocate torch
- `2026-06-15-service-capabilities-W03-P07-S10` - Tests + locales + how-to onboarding doc across capabilities, probes, doctor, provisioning
- `2026-06-15-service-capabilities-W03-P07-S13` - Investigate the torch placement (vaultspec-rag managed-torch-direct-dependency) and restructure pyproject: capability-mapped extras + relocate torch correctly
- `2026-06-15-service-capabilities-W03-P07-S14` - Write the onboarding how-to doc covering bootstrap, capabilities, and the doctor
- `2026-06-15-service-capabilities-W03-P07-S15` - Verify: full focused suite + conformance + honesty review
- `2026-06-15-service-capabilities-W03-P07-S16` - Gate every Google-write verb (verify, push, probe --no-read-only) on google_export with a no-allowlist conformance test (honesty review H1)
- `2026-06-15-service-capabilities-W03-P07-S17` - DEFERRED follow-up: add an llm_vision=off two-mode (scan PDF + image) evidence-refusal regression (honesty review M1)

### plan

- `2026-06-15-service-capabilities-plan` - `service-capabilities` plan

### research

- `2026-06-15-service-capabilities-research` - `service-capabilities` research: `Profile-linked service capabilities, dependency management, and graceful degradation: current-state map`
