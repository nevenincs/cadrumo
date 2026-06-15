---
tags:
  - '#research'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-14'
related:
  - '[[2026-06-14-legal-grounding-centralization-adr]]'
---

# `legal-grounding-centralization` research: investigation backing the decision

This research captures the investigation that backed the `legal-grounding-centralization` ADR.

## Findings

A five-agent RAG centralization swarm inventoried inline / hardcoded / ungrounded
regulatory values and definitions that bypass the central authority across IRPF, IVA,
recargo, deductible-expense, and IVA-calculation surfaces, in violation of
`aeat-schema-central-config` and `registry-calculation-legal-grounding`.

The investigation identified three remediation mechanisms, in declining grounding
strength: (1) a registry parameter with `legal_refs`→`corpus_ref`, guarded by the
corpus-text gate (strongest, heaviest); (2) an `external_constants` leaf for a true
regulatory figure consumed by-name; and (3) a `Settings` field for a deployment value.
It also found two dormant subsystems requiring an explicit bind-versus-delete choice.
The findings drive a per-finding remediation mechanism plus sequencing — a remediation
campaign, not a novel architecture.
