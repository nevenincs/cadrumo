---
tags:
  - '#adr'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-10-29'
body_schema: 'body-v1'
body_hash: 'sha256:d17b6456b8ea68cdd2f7b140ca176ba94733435317b314779833d0d1fdaa6a8a'
related:
  - '[[2026-08-06-llm-package-split-measurement-basis-reference]]'
  - '[[2026-08-06-llm-package-split-ingest-cascade-reference]]'
  - '[[2026-08-07-unstructured-document-ingestion-adr]]'
  - '[[2026-06-15-dependency-provisioning-adr]]'
  - '[[2026-06-28-product-packaging-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
---
# `unstructured-document-ingestion` adr: `Model choice, transient-failure retry, and degradation without a consent bypass` | (**status:** `proposed`)

## Problem Statement

The ingestion pipeline the sibling ADR decides runs on local models. The tax
engine ships no model runtime and installs no model, and the operator's concern
is that the reading lanes stay a bounded, honest capability of that engine.

Ground state: the product measures no hardware, probes no model runtime and
reports no readiness of any third-party dependency: `src/cadrumo` is a tax
calculation engine, and the desktop owns dependency setup and readiness. What
does NOT exist, and is this record's subject: any retry or backoff semantics on
the inference transport, and a model-choice rule that keeps default models out
of the product.

The licence finding makes model choice more than an ergonomics feature: a
shipped default vision model that carries a research licence barring
commercial use is a shipping defect in a tax-filing product. The product
therefore ships no default model at all.

## Considerations

- **The packaging cohort is accepted and binding.**
  `2026-06-28-product-packaging-adr`: one exact-version three-distribution
  cohort; models, browser binaries and credentials are operator-provisioned
  capabilities, never package data.
- **The sibling ADR's D8/D8a govern the cloud interaction.** Degradation
  design here must not become a route around the consent gate.
- **Model choice and load admission belong to cadrumo-agent.** Its provider
  catalogue is the sole source of models, and it admits each model load
  (`2026-10-25-agent-owned-models-adr`).

## Considered options

- **A — leave the transport without a retry policy.** Rejected: a transient
  connection reset during a model load then surfaces as a hard failure.
- **B — a typed retry policy on the transport (chosen).** Every piece is
  deterministic and CI-testable.
- **C — own the model runtime: ship or supervise the Ollama daemon,
  auto-start it, auto-pull models on demand.** Rejected: the packaging ADR
  places runtimes and models on the operator side of the line; a multi-GB
  download or a daemon spawn as a side effect of `calculate` is exactly the
  implicit behaviour the point-of-use refusal replaced; and process
  supervision drags in a platform-service problem this product does not need.

## Constraints

- The consent gate of the sibling ADR's D8a binds every degradation path;
  nothing here may route an unconsented request off-host.
- The packaging cohort is immutable: no model bytes, no runtime binaries in
  any wheel; `cadrumo.core.resources` remains the only resource access path.
  The tax engine has no local-inference install option: model work routes
  through cadrumo-agent.
- Python provisions nothing and reports no dependency readiness. The CLI root
  surface stays `config` + `app`.
- Regulated values are unaffected: model choice never alters a tax figure.

## Implementation

### D1 — no provisioning surface in Python

`src/cadrumo` carries no provisioning authority: no model runtime probe, no
dependency status row, no doctor report and no pull or start of a local
runtime. A model or runtime that is not there is a typed refusal at the point
of use, naming the cause and no command, application or setup step.

### D2 — no hardware profile

The product measures no system memory, accelerator or VRAM, and declares no
hardware floor.

### D3 — load admission is cadrumo-agent's

The product performs no contention or hardware admission. cadrumo-agent
admits each model load and refuses one that does not fit with
`model_does_not_fit`, at run start or mid-turn. The product reads either as
the typed `MODEL_DOES_NOT_FIT` refusal and does not retry it.

### D4 — model choice is the person's, through cadrumo-agent

No model name, default, ranking, licence gate or hardware tier exists in the
product. The person picks the reading model in the agent's model picker, and
the licence is shown at selection (`2026-10-25-agent-owned-models-adr`).

**Per-model parameter support is a first-class capability axis, beside
vision support.** It is the catalogue's typed run options (temperature,
maximum output tokens, `num_ctx` and response format). The dispatch omits any
parameter the catalogue entry does not support rather than sending an assumed
default, so an unsupported field is a typed refusal, never a vendor 400.

### D5 — the runtime is operator-owned, records survive

The runtime daemon stays operator-owned per the packaging ADR: an unreachable runtime is an instructive refusal, never a spawn.

Removing a model or the runtime never touches persisted records. Transcriptions, drafts, provenance stamps and classifications derived from model reads remain valid history — a stamp naming a removed model is honest provenance, not a dangling reference.

### D6 — retry and backoff, scoped to the transient

The `LLMClient` transport gains a typed retry policy: exponential backoff
with jitter and a bounded total budget, applied only to transient transport
failures (connection refused or reset during model load, HTTP 5xx from the
runtime, read timeout on a model that is still loading). Never
retried: schema-validation refusals (retrying a semantic failure launders
it), `MODEL_DOES_NOT_FIT` refusals (the condition does not decay on a timer;
it decays when load changes), consent refusals, and capability refusals. The
policy is data on the client, visible in the request record, and CI-tested
against a real local HTTP server exhibiting each failure shape.

### D7 — degradation that cannot launder the consent gate

Local runtime unavailable, model unpullable, or a model that does not fit:
each yields its typed refusal. Where the deployment has the cloud route
configured and the surface is consent-eligible, the refusal MAY name the
gated cloud alternative in its remediation prose — but degradation never
*selects* it: there is no automatic fallback from a local failure to an
off-host read, because an outage must not convert into an unconsented
upload. The consent gate of the sibling ADR's D8a is upstream of any cloud
dispatch regardless of why the dispatch was attempted.

## Rationale

Option B wins because retry on genuinely transient transport failures is
deterministic and testable, while Option C fails on an accepted ADR's line
(operator-provisioned runtimes) and on the implicit-side-effect principle the
point-of-use refusal replaced. Leaving load admission and model choice to
cadrumo-agent keeps the tax engine free of any model definition or hardware
measurement.

## Consequences

**Gains.** The tax engine carries no inference closure and no model
definition, while every deterministic reading lane keeps working. The
commercial-licence defect in a shipped default is closed structurally by
shipping no default.

**Costs and risks.** Retry semantics add a bounded latency tail to
genuinely-down runtimes.

**Coupling.** The sibling pipeline ADR's D8/D8a own the cloud gate this
record's degradation must respect; its D9 harness lane owns every model
quality figure. The product-packaging ADR is extended, not contradicted.

**Deliberately out of scope.** Daemon supervision and service management.

## Codification candidates

None. The packaging ADR, `no-silent-under-declaration` and
`aeat-architecture-boundaries` govern everything here.
