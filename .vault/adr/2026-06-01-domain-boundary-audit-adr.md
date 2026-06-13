---
tags:
  - '#adr'
  - '#domain-boundary-audit'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - '[[2026-04-30-aeat-restructure-research]]'
  - '[[2026-06-01-domain-boundary-audit-audit]]'
  - '[[2026-06-04-domain-boundary-audit-research]]'
---



# `domain-boundary-audit` adr: `AEAT hexagonal ownership and layering contract` | (**status:** `accepted`)

## Problem Statement

The 40-finding domain-boundary audit (DB-01..DB-40) surfaced systematic ownership
drift across the 1700-file codebase: regulatory calculation logic implemented in the
CLI and application layers, an entire tax concept (Modelo-303 IVA compensation) with no
domain package, a registry whose declared public surface is bypassed by 33 modules,
domain repositories importing adapter concretions, the innermost `core` layer reaching
up into `domain`/`application`, a catch-all `profile` package bundling three unrelated
concerns, and twin DTOs / shims / duplicate enums across layer seams. The individual
findings each have a remediation, but they are symptoms of a missing, explicitly-stated
ownership contract. This ADR codifies that contract so the remediation plan has a
single authority to execute against, and so future agents inherit the boundary rules
rather than re-deriving them per finding.

This is an audit-driven decision: it ratifies and sharpens constraints the standing
rules already imply (hexagonal direction, calculation grounding, registry authority
flow, no shims, closed value sets in core) and resolves the open questions those rules
left ambiguous (where domain repository *implementations* live; whether `core/resources`
is a legitimate facade; how application/CLI result DTOs relate).

## Considerations

- The standing rules already assert most of the direction: "keep domain logic
  independent from adapters", "carry regulatory grounding through every domain
  boundary", "ValidatedRegistryAuthority is the production boundary", "no shims",
  "closed value sets MUST be StrEnum in core", "type every constant-like axis". The
  audit shows these are unevenly enforced, not contested.
- The single genuinely open architectural question is the persistence boundary: domain
  declares repository ports (`_protocols.py` exists in seven domain packages) yet the
  concrete `_repository.py` implementations are co-located in `domain/` and depend on
  `adapters.persistence.storage` concretions — overwhelmingly via deferred
  (TYPE_CHECKING / function-local) imports that hide the inversion from the import
  graph. 100 deferred edges, 6 module-level runtime edges.
- Blast radius is uneven: some clusters (registry export promotion, IVA-compensation
  home, regulatory-formula relocation) are clean atomic relocations; the profile rename
  touches 23+ importers; the persistence-port migration touches 16 repository files.
- The substitutability pre-filter is mandatory: several "X duplicates Y" findings are
  constraint-shape divergences (e.g. `RegistryManualId` ⊊ `ManualId`) that must NOT be
  collapsed naively.

## Constraints

- Every relocation MUST follow the atomic-relocation rule: canonical move + all
  consumer updates + `__all__` updates in ONE commit, `relocation:<symbol>` subject
  tag, `pytest --collect-only -q` clean immediately before commit. No re-export bridges.
- `domain` MUST NOT import `application`/`entrypoints`. `core` MUST NOT import
  `domain`/`application`/`adapters`/`entrypoints`. These are hard, non-deferrable.
- Regulatory numeric logic moved into domain MUST carry an oracle citation
  (`# oracle: BOE-… / AEAT-MANUAL-…`) per the no-tautological-calculation-tests rule;
  do not relocate a formula without grounding its test.
- Cycle-forced deferred imports remain permitted ONLY where a module-load cycle is
  proven; they MUST target the public surface, not private submodules.

## Implementation

This ADR records SEVEN decisions. The companion plan executes them as Waves.

**D1 — Layer dependency contract.** The legal dependency direction is
`core -> domain -> application -> {adapters, entrypoints}`. A lower layer never imports
a higher one. Domain declares repository ports; adapters implement them. Persistence
concretions (`SecureObjectRepository`, `Envelope`, `SensitivityClass`,
`SecureBoundRepository`) sit at or below their consumer. `adapters -> entrypoints` is
forbidden (currently clean). `entrypoints` and `adapters` may depend on `application`,
`domain`, `core`.

**D2 — Regulatory logic and values live in `domain`/registry, never above it.** Tax
formulas, statutory validations, regulatory thresholds, and closed regulatory decision
trees belong in a grounded domain home (or the registry). The CLI, application, and
adapter layers orchestrate and render; they do not compute or validate tax law. This
mandates: a new `domain/iva_compensation/` package (the marquee gap); relocating the
DT-12ª / SAL formulas and the M184/M347 validations out of the CLI; relocating the
M347/M720 thresholds out of `core/external_constants`; and moving registry-derived
verification classification beside its registry data.

**D3 — The registry public surface is the only import boundary.**
`domain/calculations/registry/__init__.__all__` is the contract. Every consumer imports
from it; no module imports a registry private submodule (`._ids`, `._schema`,
`._bindings`, `._authority`, `._loader`, …). Missing public symbols (the `_ids` id
aliases, `DecimalValue`, `CounterpartSourceKind`, and the oracle/filed-state types
consumed externally) are promoted into `__all__` first, then the 33 importers are swept
to the public path. The same applies to the `IvaInvoiceClassification` iva/invoices
export asymmetry.

**D4 — Persistence boundary (RATIFIED 2026-06-03).** Runtime
(module-level) `domain -> adapters` imports are eliminated immediately by deferring them
(cheap, removes the live inversion). The deeper question — relocating domain repository
*implementations* into `adapters/persistence/<domain>/` behind the existing ports vs
formally accepting domain-co-located encrypted repositories as a documented deviation —
is RULED as follows: **new** repositories MUST be implemented
in `adapters/persistence` behind a domain port; **existing** domain-co-located
repositories are accepted as managed debt and migrated opportunistically, never via a
re-export bridge, with the deferred imports tracked but not churned en masse. This
keeps `domain` runtime-clean of adapters without a 16-file big-bang.

*Operator ratification (2026-06-03):* D4 is accepted as written, with one refinement —
repositories MUST import secure-storage primitives from the storage package's **public
top-level surface**, never from underscore-private submodules (`storage.envelope._envelope`
and the like); reaching into `_`-prefixed modules "looks wrong" as a legitimate import
source. The original `S53` (defer the 6 `filing`/`justificante`/`submission` repository
imports of `SecureBoundRepository`/`SensitivityClass` into `TYPE_CHECKING`) is **infeasible**
and therefore superseded: `SecureBoundRepository` is a runtime generic base class
(`class SubmissionRepository(SecureBoundRepository[ModeloPresentado])`) and
`SensitivityClass.AUDIT` is a runtime `ClassVar` value — neither can be type-only. Those
edges are exactly the managed debt D4 accepts. The import-surface cleanup is tracked
mechanically in plan Wave `W11` (Secure-storage public-surface import purity); the sibling
adapter→application active-bucket-resolution inversion (`S60`/DB-31 B-4) is amplified into
Wave `W10` (Active-bucket context resolution consolidated in core), which relocates
`require_active_bucket_id` + `NoActiveProfileError` to a public `aeat.core` surface so every
layer depends inward.

**D5 — `core` is the generic shared kernel only.** `core` holds cross-cutting
primitives (decimal/money/hashing/json-contract/i18n/redaction/paths/logging) and closed
value-set enums. It holds no domain records, no setup/wizard state, no `core -> domain`
or `core -> application` edges. `core/profile.py` (actually setup-answers) and
`core/profile_catalogue.py` are renamed and their `Any`-typed lazy domain accessors are
retyped once the cycle is broken; `core/resources/_repos` is ruled a legitimate
shared-kernel registry facade ONLY if it depends on protocols defined in core or domain,
not on `application` — the `application.topics` types relocate out of the core import
path. Closed regulatory enums currently in `application/aggregation` move to `core`.

**D6 — One symbol, one home: no shims, no cross-layer twin DTOs.** Application result
models are canonical; CLI `OutputSchema` payloads derive from them (or the application
model becomes the `OutputSchema`); they do not share a class name. Re-export shims
(`pdf/_errors.py`, the dead `identity/` package, the `M347_THRESHOLD_EUR` re-export
chain, the `_domain_manual_id` coercion) are deleted and callers repointed. Duplicate
implementations (the Spanish-decimal parser, `LedgerReviewIssue`) collapse to one home.
Same-name-different-purpose collisions (`PortalRow`) are disambiguated. The
substitutability pre-filter gates every collapse.

**D7 — The `profile` package is renamed to its true subject.** `domain/profile` is a
three-concern catch-all (tax-residence — legitimate; renta/Modelo-100 family facts;
inventory/asset/amortization errors). The chosen resolution is rename-in-place plus
inventory-error relocation (lower blast radius than a full split): the
inventory/asset/amortization errors move to their `inventory`/`assets` subpackages; the
package is renamed so it no longer claims a bare "tax-residence profile" identity it
does not hold; the sole `domain/profile -> application.wizard` inverted edge (DB-17) is
removed by relying on the existing push-registration path.

## Rationale

The contract is grounded in the existing standing rules (which it ratifies and sharpens)
and in the 40-finding audit, which provides the file:line evidence for every decision.
The persistence-boundary middle ruling (D4) is chosen over both extremes because a
big-bang port migration of 16 repository files is high-risk on a shared branch with many
concurrent campaigns, while doing nothing leaves `domain` structurally coupled to
adapters; deferring the runtime edges captures most of the benefit (a runtime-clean
import graph) at near-zero risk, and the "new code behind ports" rule stops the debt
growing. D7's rename-in-place is chosen over a full renta/residence split because the
split would fracture `CCAA` (10+ importers) from the family-fact codes for little
ownership gain, while the rename removes the misleading claim with one atomic move.

## Consequences

Gains: a single stated ownership contract future agents inherit; a runtime-clean import
graph; regulatory logic testable in isolation with oracle grounding; a registry whose
refactors no longer silently break 33 consumers; `core` reusable as a true kernel.

Costs and pitfalls: the relocations are numerous (the plan enumerates a Step per named
occurrence) and each is an atomic multi-consumer commit that must land clean on a shared
branch — sequencing and collision-checking matter. The profile rename and the
persistence-port migration are the highest-blast-radius items and are staged late. D4 is
a provisional ruling; if the user prefers a full port migration or a full accepted
deviation, the plan's Wave-B reshapes accordingly. The IVA-compensation extraction (D2)
is large enough to be its own sub-campaign and must preserve `CasillaObservation`
provenance through the move.

## Codification candidates


- **Rule slug:** `import-from-public-surface-not-private-submodule`.
  **Rule:** A package's declared `__all__` is its import contract; consumers MUST import
  from the package root, never from a sibling/foreign package's underscore-private
  submodule. (Codifies D3; generalises beyond the registry.)
- **Rule slug:** `no-cross-layer-twin-dtos`.
  **Rule:** An application result model is canonical; a CLI `OutputSchema` payload MUST
  derive from it or BE it, and MUST NOT redeclare the same fields under the same class
  name in the entrypoint layer. (Codifies D6.)
- **Rule slug:** `regulatory-logic-lives-in-domain`.
  **Rule:** Tax formulas, statutory validations, and regulatory thresholds MUST live in
  a grounded `domain`/registry home with an oracle citation; the CLI, application, and
  adapter layers orchestrate and render but never compute or validate tax law.
  (Codifies D2; sharpens the calculation-grounding rule to cover placement, not just
  provenance.)

Defer promotion until the corresponding plan Wave lands and the constraint is proven in
practice; codify from the Verify pass, not from the ADR alone.
