---
tags:
  - '#adr'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-10-29'
body_hash: 'sha256:433ad31faaa2550682cc4f51bcf186709a35f63c77c15408cf772c24b9b13465'
related:
  - "[[2026-06-13-llm-evidence-classification-research]]"
  - "[[2026-06-10-llm-evidence-classification-adr]]"
---

# `llm-evidence-classification` adr: `The on-host vision model is the person's selection, never a shipped default` | (**status:** `accepted`)

## Problem Statement

The on-host vision evidence reader needs a vision-capable model, and the on-host
posture is the gestor-allowed, no-upload default. A model name shipped as a
settings default would be a hardcoded model definition in a tax product, with a
licence, a size and a quality ranking that Cadrumo does not own and cannot keep
current. A default that is wrong for the person's machine would also make the
read fail or run unusably slowly.

## Considerations

Reading invoices is structured-document OCR. The model only selects `category` /
`iva_category` from the registry allow-list; it never emits a regulated number
(those are registry-derived), so the choice of model carries no
calculation-grounding risk. Model weights are pulled into the person's own Ollama
runtime; the application ships none. cadrumo-agent already owns providers and
models, local ones included (`2026-10-25-agent-owned-models-adr`).

## Constraints

Cadrumo defines no AI model name, digest, size, licence, default, candidate list
or ranking. The vision model is the one the person selects from cadrumo-agent's
catalogue, and the catalogue must mark it vision-capable. With no selection, or
with a selection that cannot read images, the read refuses with a typed verdict;
no other model stands in. Every tax model call goes through the agent service.

## Implementation

No `aeat_llm_ollama_vision_model` setting and no default model name exist. The
application reads the person's selected model through the agent service at the
boundary and passes it as the request model. Scanned or image evidence is read
locally with no upload whenever the selected lane's catalogue entry sets
`reads_off_host` false.

## Rationale

The catalogue is the sole source of what models exist, what they cost on disk and
what licence they carry, so a selection read from it is always current and a
Cadrumo-side name can never go stale. The gestor-allowed, no-upload posture
stands: a lane whose catalogue entry sets `reads_off_host` false reads on this
host.

## Consequences

A gestor or autónomo reads scanned evidence on this host with the model they
picked, and no default carries a licence that bars commercial use. The model name
is a regulatory-neutral choice: it never produces a persisted tax number.

## Codification candidates
