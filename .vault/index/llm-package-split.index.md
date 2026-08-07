---
generated: true
tags:
  - '#index'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:8b5325d413f707370d84ddfbabd3f435573f1e3cbe4fdb62cb2aff6bf3897288'
related:
  - '[[2026-08-06-llm-package-split-W01-P01-S01]]'
  - '[[2026-08-06-llm-package-split-W01-P01-S02]]'
  - '[[2026-08-06-llm-package-split-W01-P01-S03]]'
  - '[[2026-08-06-llm-package-split-W01-P01-S04]]'
  - '[[2026-08-06-llm-package-split-W01-P01-S65]]'
  - '[[2026-08-06-llm-package-split-W01-P02-S06]]'
  - '[[2026-08-06-llm-package-split-W01-P02-S07]]'
  - '[[2026-08-06-llm-package-split-W01-P02-S08]]'
  - '[[2026-08-06-llm-package-split-adr]]'
  - '[[2026-08-06-llm-package-split-enforcement-and-disposition-audit]]'
  - '[[2026-08-06-llm-package-split-ingest-cascade-reference]]'
  - '[[2026-08-06-llm-package-split-measurement-basis-reference]]'
  - '[[2026-08-06-llm-package-split-plan]]'
  - '[[2026-08-06-llm-package-split-research]]'
  - '[[2026-08-07-llm-package-split-plan-tracker-reconciliation-audit]]'
---

# `llm-package-split` feature index

Auto-generated index of all documents tagged with `#llm-package-split`.

## Documents

### adr

- `2026-08-06-llm-package-split-adr` - `llm-package-split` adr: `Local-inference document reading as a gated subpackage: exempt from encryption, bound by the persistence gates` | (**status:** `proposed`)

### audit

- `2026-08-06-llm-package-split-enforcement-and-disposition-audit` - `llm-package-split` audit: `Enforcement gaps, the vacuous-green defect class, and the disposition register`
- `2026-08-07-llm-package-split-plan-tracker-reconciliation-audit` - `llm-package-split` audit: `Plan-to-code reconciliation: 50 steps landed against a tracker reading zero`

### exec

- `2026-08-06-llm-package-split-W01-P01-S01` - Register an llm OptionalExtra in the declared set rather than hand-rolling it like the agent extra, red if the extra resolves outside OPTIONAL_EXTRAS
- `2026-08-06-llm-package-split-W01-P01-S02` - Declare the llm extra's runtime packages explicitly, gated red if a clean non-extra install still resolves an inference-only package
- `2026-08-06-llm-package-split-W01-P01-S03` - Guard the rasterisation path with require_optional_extra immediately before its lazy import, red if the import raises ModuleNotFoundError instead of the typed refusal when the extra is absent
- `2026-08-06-llm-package-split-W01-P01-S04` - Replace the misdiagnosed Ollama remediation raised on a missing-Pillow failure with the extra's install hint, red if the rasteriser still reports a missing PIL as a broken PDF
- `2026-08-06-llm-package-split-W01-P01-S65` - Declare Pillow as a direct project dependency carrying the lxml comment's incidental-transitive rationale, since the extra alone leaves the direct reliance undeclared in the base closure
- `2026-08-06-llm-package-split-W01-P02-S06` - Add a hardware-floor probe for the model runtime reporting through the existing DependencyStatus shape, named for the floor it measures rather than the overloaded word capability which already denotes four unrelated concepts in this tree, red if an under-specified machine reports capable
- `2026-08-06-llm-package-split-W01-P02-S07` - Surface the hardware probe as a typed refusal naming the shortfall in the config doctor, red if the refusal omits the accepted floor
- `2026-08-06-llm-package-split-W01-P02-S08` - Add a non-vacuity assertion to the sensitive-surface list so every entry must resolve to at least one non-test module or the gate fails naming the entry, closing the fail-open hole for all eighteen surfaces

### plan

- `2026-08-06-llm-package-split-plan` - `llm-package-split` plan

### reference

- `2026-08-06-llm-package-split-ingest-cascade-reference` - `llm-package-split` reference: `Ingest cascade blueprint, format coverage, and injection posture`
- `2026-08-06-llm-package-split-measurement-basis-reference` - `llm-package-split` reference: `Measurement basis: every quantitative claim with its key, sample size and provenance`

### research

- `2026-08-06-llm-package-split-research` - `llm-package-split` research: `Extracting the document-ingestion and inference path into an optional local-inference package`
