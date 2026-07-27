---
generated: true
tags:
  - '#index'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - '[[2026-07-27-conformance-cli-P01-S01]]'
  - '[[2026-07-27-conformance-cli-P01-S02]]'
  - '[[2026-07-27-conformance-cli-P01-S03]]'
  - '[[2026-07-27-conformance-cli-P01-S04]]'
  - '[[2026-07-27-conformance-cli-P01-S33]]'
  - '[[2026-07-27-conformance-cli-P01-S34]]'
  - '[[2026-07-27-conformance-cli-P01-S35]]'
  - '[[2026-07-27-conformance-cli-P02-S05]]'
  - '[[2026-07-27-conformance-cli-P02-S06]]'
  - '[[2026-07-27-conformance-cli-P02-S07]]'
  - '[[2026-07-27-conformance-cli-P02-S08]]'
  - '[[2026-07-27-conformance-cli-P02-S09]]'
  - '[[2026-07-27-conformance-cli-P02-S10]]'
  - '[[2026-07-27-conformance-cli-P02-S11]]'
  - '[[2026-07-27-conformance-cli-P02-S12]]'
  - '[[2026-07-27-conformance-cli-P02-S26]]'
  - '[[2026-07-27-conformance-cli-P02-S28]]'
  - '[[2026-07-27-conformance-cli-P02-S30]]'
  - '[[2026-07-27-conformance-cli-P02-S31]]'
  - '[[2026-07-27-conformance-cli-P02-S36]]'
  - '[[2026-07-27-conformance-cli-P03-S13]]'
  - '[[2026-07-27-conformance-cli-P04-S18]]'
  - '[[2026-07-27-conformance-cli-P04-S27]]'
  - '[[2026-07-27-conformance-cli-P05-S32]]'
  - '[[2026-07-27-conformance-cli-adr]]'
  - '[[2026-07-27-conformance-cli-fact-lifts-and-boundary-gate-audit]]'
  - '[[2026-07-27-conformance-cli-governance-stamp-and-classification-audit]]'
  - '[[2026-07-27-conformance-cli-plan]]'
  - '[[2026-07-27-conformance-cli-research]]'
---

# `conformance-cli` feature index

Auto-generated index of all documents tagged with `#conformance-cli`.

## Documents

### adr

- `2026-07-27-conformance-cli-adr` - `conformance-cli` adr: `derived conformance facts in src, governance CLI in dev, one-way boundary` | (**status:** `accepted`)

### audit

- `2026-07-27-conformance-cli-fact-lifts-and-boundary-gate-audit` - `conformance-cli` audit: `fact lifts and boundary gate`
- `2026-07-27-conformance-cli-governance-stamp-and-classification-audit` - `conformance-cli` audit: `governance stamp and classification coherence`

### exec

- `2026-07-27-conformance-cli-P01-S01` - add the RevisionReviewStatus StrEnum (pending_review, agent_reviewed, operator_reviewed) to the core closed-value-set surface and export it through the core facade
- `2026-07-27-conformance-cli-P01-S02` - add optional governance scalars engineered_by, review_status, reviewed_by, reviewed_at to ModeloRevision with a model validator refusing reviewed_by or reviewed_at unless review_status is beyond pending_review, absence defaulting to pending_review
- `2026-07-27-conformance-cli-P01-S03` - hydrate the governance scalars from revision.toml in the TOML compiler, rejecting unknown or misplaced governance keys loudly
- `2026-07-27-conformance-cli-P01-S04` - add governance-stamp loader tests covering roundtrip, fail-closed default on absence, refusal of incoherent stamp combinations, and an anti-tautology mutation proof
- `2026-07-27-conformance-cli-P01-S33` - refuse a blank or whitespace-only reviewed_by and engineered_by so a stamp cannot claim signoff while naming nobody, bound reviewed_at against a future date, and tighten the bundled-tree invariant from not-null to non-blank
- `2026-07-27-conformance-cli-P01-S34` - derive the governance field set from a marker on the field declarations so a fifth governance scalar enrols itself into the placement refusal instead of silently escaping it
- `2026-07-27-conformance-cli-P01-S35` - derive the embedded core-type set for the compiled cache key from the compiled models annotations rather than a remembered hand list, or assert the derived set is a subset of the list, covering the ten unenrolled types including the core Modelo enum
- `2026-07-27-conformance-cli-P02-S05` - lift the registry-wide external-oracle grounding fold (per-modelo oracle inventory, revision selection, both-direction honesty facts) into a new importable module exported through the registry facade
- `2026-07-27-conformance-cli-P02-S06` - re-point the external-oracle grounding gate at the lifted library in the same commit, keeping both honesty directions asserted
- `2026-07-27-conformance-cli-P02-S07` - extract the fichero-BOE required-applicable casilla derivation into one shared public function consumed by the export gate
- `2026-07-27-conformance-cli-P02-S08` - re-point the export completeness and fichero-BOE parity tests at the shared required-set derivation, removing the mirrored duplicate
- `2026-07-27-conformance-cli-P02-S09` - add the classification-coherence checker (calculation_class vs tax_domain vs core modelo constants, plus the declared-but-dead axis census) as an importable typed fact-builder
- `2026-07-27-conformance-cli-P02-S10` - add the per-revision conformance profile composer with strict typed row models, composing model-law coverage, support matrix, registry-scope diagnostics, authorization state, external grounding, and governance stamps
- `2026-07-27-conformance-cli-P02-S11` - add structure-and-wiring tests for the classification-coherence checker grounded in the live registry tree
- `2026-07-27-conformance-cli-P02-S12` - add structure-and-wiring tests for the conformance profile composer, asserting provenance fields and degraded-mode labelling, never author-invented numeric expectations
- `2026-07-27-conformance-cli-P02-S26` - restore an independent registry-grounded oracle for the fichero-BOE required-applicable set so a relaxation of the predicate in either direction flips an assertion, remediating the review finding required-set-oracle-collapse
- `2026-07-27-conformance-cli-P02-S28` - parse each bundled oracle payload through a strict typed model so the declared source_kind token actually hydrates and an unknown token refuses at the boundary, removing the last untyped mapping read in the grounding fold
- `2026-07-27-conformance-cli-P02-S30` - split the scenario input figures out of the M303 prorrata oracle expected-by-casilla map and rename the payload to carry its filing year so its genuine expected figure enters the honesty relation
- `2026-07-27-conformance-cli-P02-S31` - model M303 casilla 44 regularizacion prorrata as a computed casilla grounded in LIVA art 105-106 with the AEAT manual figure as its external oracle expectation, closing a computable value left to operator entry
- `2026-07-27-conformance-cli-P02-S36` - bind the classification finding detail bound to the field it mirrors and add the missing case whose single blocker exceeds it so the truncation branch is proven rather than reasoned
- `2026-07-27-conformance-cli-P03-S13` - build the pure manager composing the src fact facades plus ModeloLocaleManager coverage rows, with typed payload models and a self-labelling no-validate degraded mode
- `2026-07-27-conformance-cli-P04-S18` - add the dev-path isolation gate asserting no shipped module imports dev.* or embeds a dev/ path literal, with an injectable-root anti-tautology proof
- `2026-07-27-conformance-cli-P04-S27` - widen the dev-path literal detection to the realistic PROJECT_ROOT join, os.path.join, f-string and backslash forms, invert the test that pins the hole open, and mirror the missing shipped conftest case, remediating the review finding dev-path-literal-hole
- `2026-07-27-conformance-cli-P05-S32` - amend the ADR boundary wording to name every wheel-shipped module under src/cadrumo and rule the two open questions on single-versus-dual boundary-detector authority and on whether the filing-year grounding resolver belongs on the public registry facade

### plan

- `2026-07-27-conformance-cli-plan` - `conformance-cli` plan

### research

- `2026-07-27-conformance-cli-research` - `conformance-cli` research: `modelo schema conformance governance mini-CLI`
