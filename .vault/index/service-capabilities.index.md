---
generated: true
tags:
  - '#index'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - '[[2026-06-15-service-capabilities-W01-P01-S01]]'
  - '[[2026-06-15-service-capabilities-W01-P01-S02]]'
  - '[[2026-06-15-service-capabilities-W01-P02-S03]]'
  - '[[2026-06-15-service-capabilities-W01-P02-S04]]'
  - '[[2026-06-15-service-capabilities-W01-P03-S05]]'
  - '[[2026-06-15-service-capabilities-W02-P04-S06]]'
  - '[[2026-06-15-service-capabilities-W02-P05-S07]]'
  - '[[2026-06-15-service-capabilities-W03-P06-S08]]'
  - '[[2026-06-15-service-capabilities-adr]]'
  - '[[2026-06-15-service-capabilities-plan]]'
  - '[[2026-06-15-service-capabilities-research]]'
---

# `service-capabilities` feature index

Auto-generated index of all documents tagged with `#service-capabilities`.

## Documents

### adr

- `2026-06-15-service-capabilities-adr` - `service-capabilities` adr: `Profile-linked service capabilities: opt-in/opt-out for Google export, LLM vision, and cloud evidence upload` | (**status:** `accepted`)

### exec

- `2026-06-15-service-capabilities-W01-P01-S01` - Add ServiceCapability StrEnum (cloud_evidence_upload, llm_vision, google_export) in core with per-member docstrings
- `2026-06-15-service-capabilities-W01-P01-S02` - Add a capabilities [[sections]] with boolean fields to the user_profile schema TOML
- `2026-06-15-service-capabilities-W01-P02-S03` - Add resolve_capability + CapabilityDecision overlaying profile facts onto the global Settings default (gestor-mode absolute bar first)
- `2026-06-15-service-capabilities-W01-P02-S04` - Rewire cloud_evidence_read_permitted, the vision path, and google export through resolve_capability with typed refusals
- `2026-06-15-service-capabilities-W01-P03-S05` - Add config profile capabilities show/set verbs routed through EditProfileSectionCommand
- `2026-06-15-service-capabilities-W02-P04-S06` - Add DependencyStatus + per-service probes (ollama reachability/model, playwright, google creds, provider CLIs) that never raise on absence
- `2026-06-15-service-capabilities-W02-P05-S07` - Probe Ollama before vision inference + refuse instructively
- `2026-06-15-service-capabilities-W03-P06-S08` - Add aeat config doctor: per-service availability + active-profile capability posture + remediation

### plan

- `2026-06-15-service-capabilities-plan` - `service-capabilities` plan

### research

- `2026-06-15-service-capabilities-research` - `service-capabilities` research: `Profile-linked service capabilities, dependency management, and graceful degradation: current-state map`
