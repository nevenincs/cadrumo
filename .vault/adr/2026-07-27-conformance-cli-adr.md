---
tags:
  - '#adr'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-28'
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

**One-way boundary (hardened).** Every wheel-shipped module under
`src/cadrumo` must never import `dev.*` (existing import-hygiene family) and
must never read `dev/**` paths at runtime — no baseline, worklist, report, or
config under `dev/` may be consumed by shipped code; everything shipped code
needs lives under `src/cadrumo`. The rule scopes to SHIPPED modules: a
wheel-excluded test tree may reach into `dev/` (the pre-existing hygiene gate
legitimately reads a `dev/` test-debt baseline today), because such a reach
cannot follow the package to an installed user. The dev CLI consumes
`src/cadrumo` only through public top-level facades. Ratchet baselines and
rendered reports live under `dev/registry/conformance/` and are consumed only
by dev-side code and dev-side pytest gates.

Boundary-detector ownership is SINGLE-AUTHORITY. The detection logic — both
the `dev.*` import family and the `dev/` path-literal family — lives in the
existing hygiene scanner under `dev/`, which already owns the import family
and the baseline machinery; the `src/cadrumo` boundary test asserts against
that one authority rather than re-implementing it. Two independently-authored
detectors were considered and rejected: the duplication had already diverged
within a single campaign (the shipped-`conftest.py` case existed in one copy
only), and a silently-forked authority is worse than either alternative. The
src-side test importing `dev.*` is not a boundary violation, because a test
module is wheel-excluded and the scan's own imports have no bearing on the
shipped surface it measures.

Capability-fact ownership is likewise SINGLE-AUTHORITY, and the owner is the
shipped support matrix rather than either conformance surface. The
`dev.registry.matrix` manager recomputes ten fields — the latest-revision
selection, the revision count and valid-from, calc-grade, manifest presence, the
two export-format predicates, extractor presence and extraction-profile count —
every one of which the public `build_support_matrix` already returns on
`ModeloEntry`, derived from the same primitives by the same expressions; the dev
module's own See Also block names that builder. It is RETIRED rather than
rewired: its single `report` verb renders a table the operator support-matrix
verb already renders from the shipped authority, and the conformance `report`
verb already carries the same probe for EVERY revision as a strict superset, with
a registry-root flag and row-level degraded-mode labelling the matrix has
neither of.

Two alternatives were rejected. Delegating the dev manager to the conformance
composer's per-revision `_capability_facts` closes four of the ten fields and
leaves the latest-revision SELECTION — the axis the whole matrix is keyed on —
still forked dev-side, and that fold carries no extractor boolean, only a count.
Declaring the duplication deliberate behind a divergence gate is refused on the
same ground as the boundary detector above: these copies have already diverged
(the dev row lacks title, calculation class, supported revisions, renames,
deprecations and portal cross-references; the per-revision fold dropped the
extractor boolean for a count), so a gate would institutionalise a fork instead
of deleting it.

The residue after the retirement is a type gap, not a second authority. Two sites
still spell the export-format tokens as bare strings — the per-modelo
latest-revision roll-up and the per-revision conformance fold — but they answer
different questions and are not substitutable, so neither is promotable into the
other. What forces the re-spelling is that the export-format closed set is
declared as a bare `Literal` on the export-layout schema rather than a `StrEnum`
in `core`, against the closed-value-set rule this record already invokes. Lifting
that axis is the durable fix and is tracked separately from the retirement.
Retiring the module also corrects two prose references that point the wrong way
across the boundary this record hardens: the shipped support-matrix module and
its test both document themselves as mirroring the dev matrix. Neither is an
import nor a path read, so the gate does not fire, but a shipped module naming
dev scaffolding as its origin of truth is this ADR's arrow reversed.

**Degraded-mode labelling is row-level, not container-level.** A `--no-validate`
read stamps EVERY emitted row and finding as unvalidated, never only the
enclosing audit object. A container-level flag is lost the moment a renderer
serialises the rows or a composer merges them with rows from a validated
source, at which point a degraded row is indistinguishable from an
authoritative one — the precise misreading this ADR's risk section exists to
prevent.

**The filing-year grounding resolver stays off the public facade.** A
period-agnostic, non-raising revision resolver must not sit in the same public
namespace as the law-determined resolver, which resolves a filing-year and
period pair and raises when none or several match: the inviting name is one
autocomplete away from a calculation path silently dropping the period axis
and abstaining where the law requires a refusal. It stays private to the
grounding fold, or is exposed under a name that cannot be mistaken for the
law-determined path if a cross-package consumer genuinely needs it.

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
- `dev.registry.matrix` is retired as a forked capability authority: contributors
  read the same columns from the conformance `report` verb or the operator
  support-matrix verb, both strict supersets of it. Its dev test-lane entry, its
  own tests, and the two shipped docstrings citing it as their mirror move with
  it; the synthetic planted-import fixtures naming it need a live module name.
- The export-format closed set stays a bare `Literal` on the export-layout
  schema, so the two surviving legitimate predicate sites still re-spell its
  tokens until that axis is lifted to a core `StrEnum`. Accepted as a separate,
  narrower change rather than folded into the retirement.
- Risk: a stamp vocabulary too coarse for future needs (e.g. per-casilla
  review) — accepted; casilla-level stamping at ~15,774 entries is
  unmanageable and revision granularity matches the unit of legal validity.
