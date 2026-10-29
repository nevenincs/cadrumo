---
tags:
  - '#adr'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-10-29'
body_schema: 'body-v1'
body_hash: 'sha256:7280cbc88fbc5d136c35423efb635e1720f045188a2c208f2503d90d700af7b1'
related:
  - '[[2026-08-06-llm-package-split-measurement-basis-reference]]'
  - '[[2026-08-06-llm-package-split-ingest-cascade-reference]]'
  - '[[2026-08-07-unstructured-document-ingestion-adr]]'
  - '[[2026-08-06-llm-package-split-adr]]'
  - '[[2026-06-15-dependency-provisioning-adr]]'
  - '[[2026-06-28-product-packaging-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
---
# `unstructured-document-ingestion` adr: `The cadrumo[llm] distribution boundary` | (**status:** `proposed`)

## Problem Statement

The ingestion pipeline the sibling ADR decides runs on models, and the operator's concern is packaging: "we're shipping the llm and classification lanes as a bundled feature into the cadrumo core package... think of cadrumo as cadrumo[core]... perhaps bundling the programmatic canonical schema-driven OCR, xml, csv and pdf parsing is core but the llm vision wrangling is a cadrumo[llm] extra."

Ground state, verified by reading the epicentre whole rather than assumed: `LLM_EXTRA` is registered in `core/_optional_extras.py` (`OPTIONAL_EXTRAS`), guarded by `require_optional_extra` with an instructive `MissingOptionalExtraError` install hint, and `aeat config check` renders the extras walk. What does not exist is a packaging-lane proof of the absent-extra behaviour on the inference surfaces.

## Considerations

- **The packaging cohort is accepted and binding.** `2026-06-28-product-packaging-adr`: one exact-version three-distribution cohort; models, browser binaries and credentials are never package data; optional integrations are capability extras whose absence yields declared install guidance, never `ModuleNotFoundError`.
- **The subpackage boundary is decided; the distribution question sits on top of it.** `2026-08-06-llm-package-split-adr` chose `src/cadrumo/llm/` behind an `llm` extra (its Option B) and explicitly deferred a separate distribution (its D2) behind re-scoping the persistence gates. The operator's `cadrumo[llm]` ask is satisfiable by the extra without touching that deferral.
- **`ANTHROPIC_EXTRA` is already separate from `LLM_EXTRA`.** The cloud SDK and the local-inference closure are independently installable, which the boundary below preserves: a local-only install never pulls a cloud SDK, and a consented-cloud install never needs Pillow.
- **The sibling ADR's D8/D8a govern the cloud interaction.** Degradation design here must not become a route around the reinstated consent gate.

## Considered options

- **A: the extra as the distribution boundary (chosen).** Builds on the registered extra and the accepted absent-extra behaviour; every piece is deterministic and CI-testable.
- **B: a separate `cadrumo-llm` distribution now.** Rejected here without prejudice: package-split D2 already defers it behind gate re-scoping, and the operator's stated need, that core does not carry the inference closure, is met by the extra.

## Constraints

- The consent gate of the sibling ADR's D8a binds every degradation path; nothing here may route an unconsented request off-host.
- The packaging cohort is immutable: no model bytes, no runtime binaries in any wheel; `cadrumo.core.resources` remains the only resource access path.
- Regulated values are unaffected: model choice never alters a tax figure.

## Implementation

### D1 — the `cadrumo[llm]` boundary: the operator's cut, tested and adopted

Core (a default `cadrumo` install, no extras): every deterministic reading surface — the e-invoice XML parsers (Facturae, EN16931 CII and UBL, VeriFactu/SII), PDF text-layer extraction, tabular dialect normalization and deterministic row projection, the S3 grounding stage, the shape probe, the draft and transcription contracts, and the dependency *probes* (the doctor must be able to report an absent extra). The `[llm]` extra: everything model-bearing — vision wrangling and rasterisation handoff, semantic extraction, classification, the tabular mapping *call*, and prompt and model-response machinery. The cut lands awkwardly in two places, named rather than smoothed: S3 grounding is core even though it exists chiefly to check model output (correct — it equally grounds structured parses and operator input); and the tabular lane splits mid-pipeline (a known fixed-layout file imports fully with no extra; an unknown vocabulary reaches the point of needing the mapping call and refuses with the install hint).

Absent-extra behaviour is the shipped prior art, uniformly applied: every `cadrumo.llm` entry point sits behind `require_optional_extra(LLM_EXTRA)`, surfaces stay visible and discoverable, and invocation without the extra is one instructive `MissingOptionalExtraError` naming `pip install cadrumo[llm]` — never a `ModuleNotFoundError`, never a silently absent verb. What never crosses the boundary: core and domain never import `cadrumo.llm` outside the guarded lazy seam (the import-linter enrolment the package-split ADR's D12 mandates); the extra holds no storage handle (its D3); `ANTHROPIC_EXTRA` stays a separate extra so the local closure and the cloud SDK remain independently installable. The separate `cadrumo-llm` *distribution* remains deferred exactly as package-split D2 left it, behind the persistence-gate re-scoping precondition; this record satisfies the operator's core-versus-extra requirement without reopening it.

### D2 — packaging and deployment wiring

The `[llm]` extra's dependency list is completed (Pillow per the package-split ADR's finding), and the packaging smoke lanes gain an absent-llm lane: install the core wheel cohort without the extra, drive every inference-adjacent surface, and assert each refusal is the declared install guidance — proving at the artifact level what `require_optional_extra` promises at the source level. No wheel gains model bytes; the cohort contract is untouched.

### D3 — degradation that cannot launder the consent gate

Local runtime unavailable, model not installed, hardware below floor: each yields its typed refusal. Where the deployment has the cloud route configured and the surface is consent-eligible, the refusal MAY name the gated cloud alternative in its remediation prose — but degradation never *selects* it: there is no automatic fallback from a local failure to an off-host read, because an outage must not convert into an unconsented upload. The consent gate of the sibling ADR's D8a is upstream of any cloud dispatch regardless of why the dispatch was attempted.

## Rationale

The extras machinery already carries the exact absent-extra behaviour the packaging ADR requires — the work is to make it real on the inference path and prove it at the artifact level, not to invent a frame. A default install carries no inference closure, satisfying the operator's `cadrumo[core]` framing, while every deterministic reading lane keeps working.

## Consequences

**Gains.** A default install carries no inference closure, while every deterministic reading lane keeps working. The absent-extra refusal is proven on the built artifact.

**Coupling.** The sibling pipeline ADR's D8/D8a own the cloud gate this record's degradation must respect. The package-split ADR's D2 deferral and D12 enrolment are consumed unchanged. The product-packaging ADR is extended, not contradicted.

**Deliberately out of scope.** The separate `cadrumo-llm` distribution, which stays behind package-split D2's precondition. Model definitions, selection and hosting belong to cadrumo-agent (`2026-10-25-agent-owned-models-adr`).

## Codification candidates

None. The packaging ADR's extras rule, `no-silent-under-declaration` and `aeat-architecture-boundaries` govern everything here.
