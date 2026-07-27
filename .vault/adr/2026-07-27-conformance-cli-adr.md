---
tags:
  - '#adr'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - '[[2026-07-27-conformance-cli-research]]'
  - '[[2026-07-01-verification-power-adr]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
  - '[[2026-04-21-casilla-schema-completeness-adr]]'
  - '[[2026-07-02-arch-remediation-registry-format-adr]]'
---

# `conformance-cli` adr: `derived conformance facts in src, governance CLI in dev, one-way boundary` | (**status:** `accepted`)

## Problem Statement

The modelo registry carries 73 modelos and 90 revisions whose conformance —
review provenance, grounding rigour, classification coherence, enforcement
posture — is deduced today by scattered folds and pytest gates, with no
frontend able to answer "what is the status of modelo X, what drifted, what
is unreviewed" (`2026-07-27-conformance-cli-research`). Prior per-modelo
coverage tables were one-shot vault artefacts that rotted on landing. A
governance mini-CLI is needed now because agent-driven campaigns are scaling
the registry faster than ad-hoc audits can police it, and because the
review/engineering provenance the operator needs to govern (reviewed-by,
engineered-by, filed vs informative vs non-filing) has no declared home on
the schema tree at all. The decision must also harden the dev-scaffolding /
shipped-application boundary: nothing under `src/cadrumo/` may ever
reference `dev/` code or metadata.

## Considerations

- The `aeat` root surface is contractually two families; every governance
  CLI in-tree is a `python -m` Typer trio; the terminology CLI documents
  itself as the precedent (`2026-07-27-conformance-cli-research`, placement
  finding).
- Most conformance facts are already importable library functions under
  `src/cadrumo`; four fact sets are test-trapped, headed by the
  external-oracle grounding inventory (research, importable-vs-trapped
  finding).
- Import hygiene already treats a shipped module importing `dev.*` as a
  violation family; the boundary must additionally cover runtime metadata
  reads, not only imports.
- Decided law binds the semantics: grounding fraction is coverage, never
  correctness (`2026-07-01-verification-power-adr`); enrollment is calibrated
  design, never a mechanical sweep; a derived status index is discovery
  evidence, not authority; the tool must read the loaded snapshot, never
  fragment-dir listings (`2026-07-02-arch-remediation-registry-format-adr`).
- Review provenance is underivable by construction; everything else the
  frontend needs is derivable and therefore never staler than the tree.
- Closed value sets must be `StrEnum`s in `core`; boundary payloads must be
  typed pydantic models (`aeat-architecture-boundaries`).

## Considered options

- **A — dev-only Typer trio, facts recomputed dev-side.** Cheapest; but
  duplicates fact logic outside `src/cadrumo`, unreachable by product code
  and product tests; rejected.
- **B — extend `aeat app registry` with governance verbs.** Typed envelope
  and operator-harness citability; but grows the operator-facing product
  surface with contributor-governance concerns and binds every verb to
  docs/locale/conformance gates; rejected for this feature (a later ADR may
  surface a read-only roll-up there).
- **C — hybrid (chosen).** Fact-builders live in `src/cadrumo` as importable
  typed libraries; `dev/registry/conformance` is a rendering/governance
  shell over them; a strict one-way boundary keeps `src` ignorant of `dev`.
- **Declared status scalar vs derived status.** A declared per-modelo
  maturity field was rejected: it is a second source of truth the tool would
  then police for drift, and the cautionary precedent treats derived indexes
  as discovery evidence only. Status stays derived; only provenance — which
  cannot be derived — is declared.

## Constraints

- Shared factory worktree: implementation lands as small explicit-pathspec
  commits; registry schema changes ride the loader fingerprint cache, which
  already keys on the full tree.
- `no-legacy-compatibility`: the new governance fields are optional-with-
  fail-closed-default from birth; no migration, no read-tolerance branches.
- Test-trapped fact lifts must land with their consuming pytest gates
  re-pointed at the library in the same commit, keeping the gates green and
  non-tautological.
- The validating authority can refuse to load mid-churn registry trees in
  this concurrent worktree; the CLI needs the non-validating loader as an
  explicit degraded mode that reports itself as such.
- RAG discovery precedes every implementation step (mandatory rule); the
  registry loader/schema surface is peer-contended.

## Implementation

**Placement.** A new package `dev/registry/conformance/` following the house
trio: `__main__.py` → thin Typer `cli.py` → pure `manager.py`. Verbs:
`report [--json]` (full per-modelo/per-revision conformance profile),
`coverage [--json]` (per-axis counts: verification expectations,
completeness manifests, extraction profiles, external grounding, locales,
authorization), `audit [--check]` (drift/coherence findings; `--check`
gates), `stamp` (writes the declared governance scalars with vocabulary
validation; direct TOML authoring remains legal — the loader validates
either way). Text output is greppable `key=value` rows; `--json` emits
strict pydantic payloads. No `aeat` surface is touched.

**Fact layer (all in `src/cadrumo`).** New and lifted fact-builders live
beside the existing coverage audit in the registry domain package and are
exported through package facades: a registry-wide external-grounding fold
(lifted from the test-trapped oracle-enrollment module, which then imports
it), a fichero-BOE required-set derivation shared with the export gate, a
classification-coherence checker (calculation_class vs tax_domain vs
core constants vs dead axes), and a per-revision conformance profile
composer that reuses the model-law coverage audit, the support matrix,
registry-scope validation, locale coverage records, and the authorization
manifest. All folds read loaded snapshots through the authority; a
`--no-validate` degraded mode uses the raw tree loader and stamps every
emitted row as unvalidated.

**Declared provenance.** A new optional per-revision governance stamp on
`revision.toml` scalars: `engineered_by` (non-empty free text),
`review_status` (new `StrEnum` in `cadrumo.core`: `pending_review`,
`agent_reviewed`, `operator_reviewed`), `reviewed_by` + `reviewed_at`
(required exactly when status is not `pending_review`; refused otherwise).
Absence of the block means `pending_review` — fail-closed honesty, so all 90
revisions start as a visible unreviewed backlog. The legal-catalogue prose
backlog (`pending operator re-stamp` markers) is only REPORTED by marker
mining, explicitly labelled heuristic; restructuring the legal-catalogue
schema is out of scope. Classification drift is reported, not canonicalized.

**One-way boundary (hardened).** `src/cadrumo/**` must never import `dev.*`
(existing import-hygiene family) and must never read `dev/**` paths at
runtime — no baseline, worklist, report, or config under `dev/` may be
consumed by shipped code; everything shipped code needs lives under
`src/cadrumo`. The dev CLI consumes `src/cadrumo` only through public
top-level facades. Ratchet baselines and rendered reports live under
`dev/registry/conformance/` and are consumed only by dev-side code and
dev-side pytest gates. A dedicated boundary test extends the hygiene gate to
assert no `src/cadrumo` module embeds a `dev/` path literal.

**Gate posture and ratchets.** Screen-first: `report`/`coverage` always exit
0; `audit --check` is the only gating exit, backed by shrink-only JSON
baselines (documented-command idiom) with anti-vacuity floors and an
empty-input `SystemExit` refusal. Facts are promoted from screen to gate
per-fact when their worklist empties, per the attribution-screen doctrine. A
dev-side pytest wrapper runs `audit --check` in CI.

## Rationale

The hybrid wins on a knockout: the boundary rule makes dev-side fact
computation unreachable by the product, while product-side facts remain
usable by both worlds — so facts go in `src`, rendering goes in `dev`, and
the direction of the arrow is the whole design. Deriving status (rather than
declaring it) is the only posture consistent with the decided law that
derived indexes are discovery evidence and with the observed rot of every
declared-but-dead governance axis the research catalogued. Declaring
provenance (rather than deriving it) is forced: authorship and signoff are
facts about humans and agents, not about the tree. The degenerate
`Literal["reviewed"]` cannot carry a pending state, which is exactly the
state the operator needs to govern; a real three-state enum with fail-closed
absence makes the backlog visible instead of laundering it into prose.

## Consequences

- All 90 revisions surface as `pending_review` on day one: an honest,
  large, visible backlog and a stamping campaign to run — deliberate, not a
  defect.
- The registry schema grows three optional scalars per revision; loader,
  strict schema, and validation gain small, well-bounded changes on a
  peer-contended surface.
- The four test-trapped fact sets become libraries, making their gates
  thinner and reusable by any future surface (including a later
  `aeat app registry` roll-up ADR, which this record deliberately defers).
- The dev/src boundary becomes enforceable doctrine with a path-literal
  gate, closing the metadata loophole the import scan alone cannot see.
- Risk: the conformance profile is only as honest as its inputs; the report
  must label heuristic findings (prose-mined backlog) and degraded modes
  (`--no-validate`) so a green row is never mistaken for operator authority.
- Risk: a stamp vocabulary too coarse for future needs (e.g. per-casilla
  review) — accepted; casilla-level stamping at ~15,774 entries is
  unmanageable and revision granularity matches the unit of legal validity.
