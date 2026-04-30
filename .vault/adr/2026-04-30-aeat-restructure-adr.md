---
tags:
  - '#adr'
  - '#aeat-restructure'
date: '2026-04-30'
related:
  - '[[2026-04-30-aeat-restructure-research]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `aeat-restructure` adr: domain-aligned restructure of `src/aeat/` | (**status:** `wip — do not execute`)

> **WIP — DO NOT EXECUTE.** This ADR persists the destination layout that
> the ongoing per-module audit is measured against. The source of truth
> for module classification, monolithic markers, and conflation flags is
> the parallel research document. This ADR matures as the audit progresses
> and is only marked `accepted` once the audit closes and the research
> doc is signed off.

## Problem Statement

`src/aeat/` is a flat ~40-subpackage tree that does not visibly reflect
the project's three conceptual domains:

- **incoming financial data** — outside data ingested into the system.
- **local state** — internal persistence and the system's own memory.
- **AEAT remote** — external interaction with the AEAT portal.

Connector and orchestration code sits alongside pure-domain modules;
cross-cutting plumbing (`config.py`, `logging.py`, `errors/`) lives at the
package root with no visible home; user-facing surfaces lack a sibling
home for the MCP launcher. The flat structure has produced concrete
boundary violations — `auth/` conflates Google authentication with AEAT
authentication, `submission/` was a recurring live-write liability that
required excision, and `storage/` at roughly 12k lines bundles ORM, blob
store, crypto, classification, recovery, redaction, rotation, and the
secret store under one subpackage.

A per-module audit is in progress in the parallel research document.
This ADR captures the destination layout the audit measures against.

## Considerations

The proposal is informed by industry research synthesised in the research
document. The dominant Python references converge on the following
canonical layer names:

- **Cosmic Python** (Percival/Gregory): `domain/`, `adapters/`,
  `entrypoints/`, `service_layer/`; for larger projects `domain_model/`,
  `infrastructure/`, `services/`, `api/`.
- **AWS Prescriptive Guidance for Python hexagonal**: `domain/`,
  `adapters/`, `entrypoints/`, plus `infra/` for cross-cutting code.
- **Hexagonal in/out variant**: adapters split into `inbound/` and
  `outbound/` to telegraph dependency direction.

Project-specific constraints:

- The existing test-marker taxonomy (`domain_financial_input`,
  `domain_local_state`, `domain_aeat_remote`, `domain_mediation`,
  `domain_infra`) must remain mappable to the new layout.
- AEAT-canonical Spanish vocabulary (`modelos`, `casillas`, `borrador`,
  `declaracion`, `justificante`, `sede`) is part of the ubiquitous
  language and must be preserved at module-name level — DDD's "scream
  business" principle.
- Live AEAT writes are forbidden (legal liability); any rename of the
  `submission/` surface must telegraph this in code, not only in docs.
- Track A (AEAT bidirectional sync) and Track B (financial input
  unidirectional pipeline) must remain visible as connector clusters in
  the new layout.

## Constraints

- The restructure cannot reintroduce a default-enabled live-write path;
  the four-factor live-submit gate must remain defense-in-depth.
- The `submission` → `export` rename must preserve the read-only
  preflight and dry-run surfaces — they are primary pre-export gates per
  project mandate.
- Internal splits of monolithic modules (`storage`, `auth`, `cli`,
  `filing`, `workflow`, etc.) are **in-scope** for this restructure: per-
  module split designs are produced during the audit and folded into
  this ADR as audit findings land. Splits and the move to the new
  layout are planned together so that destinations reflect the post-
  split shape, not the pre-split monolith.
- Execution may be phased — the ADR captures the destination shape,
  but rollout can land in waves (e.g. layout move first, then per-
  monolith internal fracture). Phasing is a delivery decision; the
  destination shape is not.
- The test-marker taxonomy is realigned in lockstep with the layout
  rename. New markers ship in the same milestone as the package moves.
- Existing `.vault/` corpus that references old module names, old test
  markers, or pre-restructure path references is slated for
  supersession in lockstep with rollout. The supersession workstream
  produces an audit-driven changelist before any execution begins.

## Implementation

Adopt a hexagonal-with-inbound/outbound layout, using canonical Python
DDD vocabulary plus a `core/` bucket for foundational cross-cutting
modules.

```
src/aeat/
├── domain/                     # business model + computation
│   ├── modelos/                # renamed from `models` (Spanish-canonical, avoids Pydantic clash)
│   ├── casillas/
│   ├── manuals/
│   ├── normatives/
│   ├── portals/
│   ├── formulas/
│   ├── deadlines/
│   ├── schema/
│   └── profile/
├── adapters/
│   ├── inbound/                # incoming financial data
│   │   ├── pdf/                # renamed from `_pdf_import` (drop underscore)
│   │   ├── borrador/
│   │   ├── declaracion/
│   │   ├── justificante/
│   │   ├── identity/
│   │   ├── sanitizer/
│   │   └── financial/          # candidate: rename to `transactions/` (Track-B clarity)
│   ├── outbound/               # AEAT remote
│   │   ├── browser/
│   │   ├── sede/
│   │   └── export/             # renamed from `submission/` (legal-liability framing)
│   └── persistence/            # local state on disk
│       ├── storage/            # internal split planned during audit (in-scope)
│       ├── observability/
│       └── llm/
├── application/                # use cases / orchestration (the connectors)
│   ├── filing/
│   ├── workflow/
│   ├── sync/
│   ├── setup/
│   ├── review/
│   ├── verification/
│   └── auth/                   # internal split into auth/aeat + auth/google planned during audit (in-scope)
├── entrypoints/                # primary adapters (user-facing)
│   ├── cli/
│   └── mcp/
└── core/                       # foundational cross-cutting modules
    ├── config.py
    ├── logging.py
    ├── errors/
    ├── i18n/
    ├── env_io.py
    ├── paths.py                # renamed from `_paths.py` (drop underscore)
    ├── json_contract.py        # renamed from `_json_contract.py` (drop underscore)
    └── click_context.py        # renamed from `_click_context.py` (drop underscore)
```

### Rename rationale (high-impact)

- **`submission/` → `adapters/outbound/export/`**: the word "submission"
  carries the connotation of submitting to AEAT. The rename matches the
  project charter (`produce → verify → export`) and makes any future
  re-introduction of a write path visually conspicuous.
- **`infrastructure/` (industry canonical) → `core/`**: project-owner
  preference; reads as foundational modules rather than as infrastructure-
  as-code (the AWS-flavoured connotation). Distinguishes from
  `adapters/persistence/` (which is also "infrastructure" in DDD terms).
- **`mediation` (earlier proposal) → `application/`**: industry-canonical
  word; reads on first contact for any Python developer familiar with
  DDD or hexagonal.
- **`models/` → `domain/modelos/`**: AEAT-canonical Spanish term; avoids
  the foot-gun of new contributors expecting Pydantic models. The
  Pydantic-naming collision is the dominant reason for the rename.
- **`_pdf_import` → `adapters/inbound/pdf/`**: drops the underscore
  prefix; surfaces the shared-primitive role explicitly.
- **`financial/` → `adapters/inbound/financial/`** (candidate
  `transactions/`): Track-B semantics are clearer with `transactions/`.
  Final choice deferred until the financial subpackage audit completes.

### Monolithic split planning

Monolithic modules (≥ 950 LOC, flagged `[MONO]` in the research doc) are
split-planned during the per-module audit. The split design is folded
into this ADR per module as the audit lands. Splits and the layout move
are coordinated so destinations reflect the post-split shape:

- The audit produces a per-module split design — proposed sub-modules,
  their public surface, and the fracture lines.
- The destination column in the research doc heat map is updated to
  reference the post-split sub-paths where applicable.
- Sub-modules inherit the parent's bucket assignment unless the audit
  surfaces `[CORE-LEAK]` candidates that bubble up into `core/`.

The currently-known `[MONO]` modules (20 of 38 non-empty) are listed in
the research doc heat map with their flags. Highest-priority splits:
`storage` (~12k LOC, `[CONFLATE]`), `cli` (~7.6k LOC, `[CONFLATE]`),
`auth` (~4.8k LOC, `[CONFLATE]`), `filing` (~4.5k LOC, `[CONFLATE]`),
`errors` (~3k LOC, `[CONFLATE?]`).

### Test-marker realignment

The existing axis-B test markers carry the project's domain taxonomy.
They realign in lockstep with the layout rename so package and marker
vocabulary stay in sync.

Proposed marker set:

| Old marker | New marker | New home (package) | Notes |
| --- | --- | --- | --- |
| `domain_financial_input` | `domain_inbound` | `adapters.inbound.*` | direct rename |
| `domain_local_state` | (split) | (see below) | bifurcates |
| → | `domain_model` | `domain.*` | NEW — covers catalogues + computation engines + profile |
| → | `domain_persistence` | `adapters.persistence.*` | NEW — covers storage + observability + llm |
| `domain_aeat_remote` | `domain_outbound` | `adapters.outbound.*` | covers browser + sede + export |
| `domain_submission` | (folded) | `adapters.outbound.export.*` | absorbed under `domain_outbound`; tests that need finer grain mark with file-level naming or a sub-marker `domain_export` (decision deferred to marker-rollout phase) |
| `domain_mediation` | `domain_application` | `application.*` | direct rename |
| `domain_infra` | `domain_core` | `core.*` | direct rename |

**Migration mechanic**: the marker rename PR ships in the same change
window as the package move. Tests do not transit a state where their
marker is wrong relative to their location.

**Naming rationale**:

- `domain_model` is the DDD canonical term for the business model
  layer; reads better than `domain_domain` and conveys the layer's
  purpose without inventing new vocabulary.
- `domain_persistence` is the canonical hexagonal/DDD word for the
  storage-side adapters; clearer than the previous `domain_local_state`
  which collapsed two layers.
- `domain_inbound`/`domain_outbound`/`domain_application`/`domain_core`
  match the new top-level package names 1:1 — the marker name is the
  package name with a `domain_` prefix.

### Vault-corpus supersession

Existing `.vault/` documents that reference old module names, old test
markers, or pre-restructure path conventions are slated for supersession
in lockstep with rollout. A scan of the corpus produces a per-document
contradiction list (captured in the research doc's "Vault-corpus
contradictions" section).

Each contradicted document is classified:

- **Mark superseded**: document is superseded by this ADR or by a
  downstream artefact; add a `superseded_by:` link in frontmatter and
  do not edit the body.
- **Inline-update**: document is still authoritative on its topic but
  contains stale path/marker references; update those references in
  place when the rollout PR lands.
- **Archive**: document is historical (`.vault/exec/` records of
  completed work). Leave as-is; the path references are forensic.

The contradiction list and per-document classification ship as a
research-doc artefact, not as separate vault entries — they are the
input plan for the rollout, not standalone decisions.

## Rationale

The proposal is selected over alternatives because:

- **Industry-canonical vocabulary** — every top-level name appears in
  the Cosmic Python and AWS hexagonal references and is recognisable on
  day one to a Python developer with DDD familiarity.
- **Honest split between domain and persistence** — fixes the "state"
  collapse that bundled catalogues, compute, and storage. Catalogues are
  domain knowledge; storage is the infrastructure that persists them.
- **Inbound/outbound under `adapters/`** — a recognised hexagonal
  variant that matches the project's three-domain mental model exactly
  while keeping a single `adapters/` parent.
- **Legal-liability rename of `submission/` → `export/`** — telegraphs
  the prohibition in code as well as docs.
- **Spanish AEAT vocabulary preserved** — `modelos`, `casillas`,
  `borrador`, `declaracion`, `justificante`, `sede` keep their AEAT-
  canonical names. DDD's "ubiquitous language" principle is honoured.
- **`core/` for cross-cutting** — owner preference; reads as foundational
  modules.
- **Test-marker mapping is preserved** — the existing taxonomy maps onto
  the new layout with a single bifurcation flagged for follow-up.

## Consequences

**Positive:**

- New contributors orient immediately: top-level layout matches Python
  DDD references.
- Boundary violations become visually obvious — a module under
  `adapters/inbound/` importing from `adapters/outbound/` is a code-
  review red flag without further explanation.
- The `submission` → `export` rename closes a recurring ambiguity that
  has produced legal-liability incidents in the past.
- The four empty placeholder subpackages (`corpus`, `history`, `inbox`,
  `status`) get an unambiguous fate: delete or move to a clear home.

**Negative / risks:**

- Large refactor — all imports inside `src/aeat/` change; tests break
  en masse. Execution must be mechanical and verifiable, not hand-
  rolled. Phasing is the lever (layout move first, internal fractures
  next), not the contents of the change.
- 20 of 38 non-empty modules require internal split designs before they
  can be moved cleanly. Audit throughput is the critical-path
  constraint, not execution.
- Test-marker realignment must ship in lockstep with the package move
  (no in-flight state where marker name and package name disagree).
  Coordination cost across PRs.
- The AEAT-canonical Spanish term `modelos/` collides with the Python
  convention of `models/` for Pydantic. Acceptable trade-off (DDD
  ubiquitous-language wins) but requires onboarding documentation.
- Risk of surprise import shadowing during the move — must be vetted
  before execution.
- Vault-corpus supersession introduces a parallel doc-rewrite workload.
  Doing this before execution adds calendar time but prevents
  contradictory authoritative docs at rollout.

**Out of scope (this ADR does not relax these):**

- Reintroduction of live AEAT writes. The `submission` → `export`
  rename is a labelling change; the live-write CLI surface excised on
  2026-04-18 stays excised. The four-factor live-submit gate stays in
  effect as defense-in-depth.
- Per-document vault rewrites. The supersession workstream produces a
  classified contradiction list (research doc); the actual edits to
  superseded documents land as part of rollout PRs, not as standalone
  decisions captured here.

## References

Internal:

- Research (parallel, source-of-truth for module classification):
  `2026-04-30-aeat-restructure-research`.
- Live-submit CLI excision: `2026-04-18-live-submit-cli-excision-adr`.
- Auth provider abstraction: `2026-04-18-auth-provider-abstraction-adr`.
- Export-first product mode: `2026-04-17-export-first-adr`.

Industry:

- Cosmic Python — Appendix B: A Template Project Structure.
- AWS Prescriptive Guidance — Structure a Python project in hexagonal
  architecture using AWS Lambda.
- "Clean DDD lessons: project structure and naming conventions" — UNIL
  engineering / Medium.
- PEP 8 — Style Guide for Python Code.
