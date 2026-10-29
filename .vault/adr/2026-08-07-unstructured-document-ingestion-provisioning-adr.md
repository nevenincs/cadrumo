---
tags:
  - '#adr'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-10-29'
body_schema: 'body-v1'
body_hash: 'sha256:ceca6485e7a7b2f7176081ca3a7a11580d9c9fabfa33b25ae33798f95ce8ded1'
related:
  - '[[2026-08-06-llm-package-split-measurement-basis-reference]]'
  - '[[2026-08-06-llm-package-split-ingest-cascade-reference]]'
  - '[[2026-08-07-unstructured-document-ingestion-adr]]'
  - '[[2026-08-06-llm-package-split-adr]]'
  - '[[2026-06-15-dependency-provisioning-adr]]'
  - '[[2026-06-28-product-packaging-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
---
# `unstructured-document-ingestion` adr: `Model choice, transient-failure retry, and the cadrumo[llm] distribution boundary` | (**status:** `proposed`)

## Problem Statement

The ingestion pipeline the sibling ADR decides runs on local models, and the
operator's concern about packaging is repeatedly raised: "we're shipping the
llm and classification lanes as a bundled feature into the cadrumo core
package... think of cadrumo as cadrumo[core]... perhaps bundling the
programmatic canonical schema-driven OCR, xml, csv and pdf parsing is core but
the llm vision wrangling, provisioning is a cadrumo[llm] extra."

Ground state at HEAD, verified by reading the epicentre whole rather than
assumed: `ANTHROPIC_EXTRA` and `LLM_EXTRA` are registered in
`core/optional_extras.py` (`OPTIONAL_EXTRAS`), and `require_optional_extra`
raises an instructive `MissingOptionalExtraError`. The product measures no
hardware, probes no model runtime and reports no readiness of any
third-party dependency: `src/cadrumo` is a tax calculation engine, and the
desktop owns dependency setup and readiness. What does NOT exist, and is this
record's subject: any retry or backoff semantics on the inference transport,
and any packaging-lane proof of the absent-extra behaviour on the inference
surfaces.

The licence finding makes model choice more than an ergonomics feature: a
shipped default vision model that carries a research licence barring
commercial use is a shipping defect in a tax-filing product. The product
therefore ships no default model at all.

## Considerations

- **The packaging cohort is accepted and binding.**
  `2026-06-28-product-packaging-adr`: one exact-version three-distribution
  cohort; models, browser binaries and credentials are operator-provisioned
  capabilities, never package data; optional integrations are capability
  extras whose absence yields a typed refusal naming the extra, never
  `ModuleNotFoundError`.
- **The subpackage boundary is decided; the distribution question sits on top
  of it.** `2026-08-06-llm-package-split-adr` chose `src/cadrumo/llm/` behind
  an `llm` extra (its Option B) and explicitly deferred a separate
  distribution (its D2) behind re-scoping the persistence gates. The
  operator's `cadrumo[llm]` ask is satisfiable by the extra without touching
  that deferral.
- **`ANTHROPIC_EXTRA` is already separate from `LLM_EXTRA`.** The cloud SDK
  and the local-inference closure are independently installable, which the
  boundary below preserves: a local-only install never pulls a cloud SDK,
  and a consented-cloud install never needs Pillow.
- **The sibling ADR's D8/D8a govern the cloud interaction.** Degradation
  design here must not become a route around the reinstated consent gate.
- **Model choice and load admission belong to cadrumo-agent.** Its provider
  catalogue is the sole source of models, and it admits each model load
  (`2026-10-25-agent-owned-models-adr`).

## Considered options

- **A — leave the transport without a retry policy and the boundary
  implicit.** Rejected: a transient connection reset during a model load then
  surfaces as a hard failure, and the absent-extra behaviour stays unproven at
  the artifact level.
- **B — a typed retry policy on the transport, with the extra as the
  distribution boundary (chosen).** Builds on the registered extra; every
  piece is deterministic and CI-testable.
- **C — own the model runtime: ship or supervise the Ollama daemon,
  auto-start it, auto-pull models on demand.** Rejected: the packaging ADR
  places runtimes and models on the operator side of the line; a multi-GB
  download or a daemon spawn as a side effect of `calculate` is exactly the
  implicit behaviour the point-of-use refusal replaced; and process
  supervision drags in a platform-service problem this product does not need.
- **D — a separate `cadrumo-llm` distribution now.** Rejected here without
  prejudice: package-split D2 already defers it behind gate re-scoping, and
  the operator's stated need — core does not carry the inference closure —
  is met by the extra.

## Constraints

- The consent gate of the sibling ADR's D8a binds every degradation path;
  nothing here may route an unconsented request off-host.
- The packaging cohort is immutable: no model bytes, no runtime binaries in
  any wheel; `cadrumo.core.resources` remains the only resource access path.
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

### D5 — deinstallation: the extra is a package operation, records survive

The runtime daemon stays operator-owned per the packaging ADR: an unreachable runtime is an instructive refusal, never a spawn.

Removing the `[llm]` extra is a package operation (`pip uninstall` of the extra's closure) after which every guarded surface returns to the typed missing-extra refusal — that is the already-tested absent state, so deinstallation cannot strand a half-working surface. What removal never touches: persisted records. Transcriptions, drafts, provenance stamps and classifications derived from model reads remain valid history — a stamp naming a removed model is honest provenance, not a dangling reference.

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

### D8 — the `cadrumo[llm]` boundary: the operator's cut, tested and adopted

Core (a default `cadrumo` install, no extras): every deterministic reading
surface — the e-invoice XML parsers (Facturae, EN16931 CII and UBL,
VeriFactu/SII), PDF text-layer extraction, tabular dialect normalization and
deterministic row projection, the S3 grounding stage, the shape probe, and
the draft and transcription contracts. The `[llm]` extra: everything
model-bearing — vision wrangling and rasterisation handoff, semantic
extraction, classification, the tabular mapping *call*, and prompt and
model-response machinery. The cut lands awkwardly in two places, named
rather than smoothed: S3 grounding is core even though it exists chiefly to
check model output (correct — it equally grounds structured parses and
operator input); and the tabular lane splits mid-pipeline (a known
fixed-layout file imports fully with no extra; an unknown vocabulary reaches
the point of needing the mapping call and refuses with the missing-extra refusal).

Absent-extra behaviour is the shipped prior art, uniformly applied: every
`cadrumo.llm` entry point sits behind `require_optional_extra(LLM_EXTRA)`,
surfaces stay visible and discoverable, and invocation without the extra is
one instructive `MissingOptionalExtraError` naming the extra — never a
`ModuleNotFoundError`, never a silently absent verb. What never crosses the
boundary: core and domain never import `cadrumo.llm` outside the guarded
lazy seam (the import-linter enrolment the package-split ADR's D12
mandates); the extra holds no storage handle (its D3); `ANTHROPIC_EXTRA`
stays a separate extra so the local closure and the cloud SDK remain
independently installable. The separate `cadrumo-llm` *distribution* remains
deferred exactly as package-split D2 left it, behind the persistence-gate
re-scoping precondition; this record satisfies the operator's
core-versus-extra requirement without reopening it.

### D9 — packaging and deployment wiring

The `[llm]` extra's dependency list is completed (Pillow per the
package-split ADR's finding, and any future model-runtime SDK), and the
packaging smoke lanes gain an absent-llm lane: install the core wheel cohort
without the extra, drive every inference-adjacent surface, and assert each
refusal is the typed missing-extra refusal — proving at the artifact level what
`require_optional_extra` promises at the source level. No wheel gains model
bytes; the cohort contract is untouched.

## Rationale

Option B wins because both halves of the operator's ask are extensions of
surfaces the corpus already accepted: the extras machinery already carries the
exact absent-extra behaviour the packaging ADR requires — the work is to make
it real on the inference path and prove it at the artifact level, not to
invent a frame. Option C fails on an accepted ADR's line (operator-provisioned
runtimes) and on the implicit-side-effect principle the point-of-use refusal
replaced. Leaving load admission and model choice to cadrumo-agent keeps the
tax engine free of any model definition or hardware measurement.

## Consequences

**Gains.** A default install carries no inference closure, satisfying the
operator's `cadrumo[core]` framing, while every deterministic reading lane
keeps working. The absent-extra behaviour is wired into the packaging smoke
lanes. The commercial-licence defect in a shipped default is closed
structurally by shipping no default.

**Costs and risks.** Retry semantics add a bounded latency tail to
genuinely-down runtimes.

**Coupling.** The sibling pipeline ADR's D8/D8a own the cloud gate this
record's degradation must respect; its D9 harness lane owns every model
quality figure. The package-split ADR's D2 deferral and D12 enrolment are
consumed unchanged. The product-packaging ADR is extended, not contradicted.

**Deliberately out of scope.** Daemon supervision and service management, and
the separate `cadrumo-llm` distribution, which stays behind package-split
D2's precondition.

## Codification candidates

None. The packaging ADR's extras rule, `no-silent-under-declaration` and
`aeat-architecture-boundaries` govern everything here.
