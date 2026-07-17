---
tags:
  - '#adr'
  - '#tributacion-conjunta-individual'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - "[[2026-06-30-tributacion-conjunta-individual-research]]"
---

# `tributacion-conjunta-individual` adr: `tributacion conjunta vs individual comparison surface` | (**status:** `accepted`)

## Problem Statement

Issue #547 (P1, NEEDS-DESIGN) reports that no surface computes a Modelo 100 filing under both tributacion conjunta and individual and reports the favorable one. Grounding against HEAD (research `2026-06-30-tributacion-conjunta-individual-research`) shows the premise is partly outdated: a committed comparator already exists end-to-end (`compare_taxation_modes`, the `aeat app modelo work compare-taxation` verb, a registered `WorkCompareTaxationResult` payload, behavioural oracle tests, and four-locale strings), landed from audit `2026-05-27-marcos-cli-testimonial-audit` Recommendation 3. The comparator runs the shared registry engine twice over identical inputs, flipping `declaration_type` between 2 (conjunta) and 1 (individual), and reports the lower-cuota mode with a 1 EUR materiality threshold. The open question is therefore not "build a comparator" but "what is the correct scope and home for the comparator that exists, and what does it still get wrong". The load-bearing defect is that the individual branch reuses the conjunta unit's single set of inputs, so it faithfully models only a single-earner unidad familiar; it cannot represent genuine two-earner individual filing (two separate returns, each on that spouse own income) because no spouse-income axis exists in the profile.

## Considerations

- Modalidad axis exists: binding `renta-2025-profile-declaration-type` (profile_key `filing_export.n`, `TIPOTRIBUTACION`), values 1/2. No new core enum is required.
- Reduccion Art. 84 exists: formula `0179-renta-2025-reduccion-art-84-conjunta` targets casilla 0461, emitting 3.400 EUR (modalidad 1, Art. 82.1.1) or 2.150 EUR (modalidad 2 monoparental, Art. 82.1.2) when `declaration_type==2`, gated by `family-minor-children-in-unit`. Figures match the bundled AEAT Renta manuals 2022..2025; legal_refs cite ley-35-2006 art-82/83/84.
- Spouse identity axes exist (tax_id, name, birth_date, sex, disability, non-resident, EU/EEA) and marriage/family axes exist; spouse INCOME does not.
- The comparator reuses the shared engine core (`calculate_registry_snapshot`) so formula arithmetic is single-sourced, but the work-unit entry point assembles inputs on a locally-built path that mirrors the calculate path rather than sharing it.
- Constraints in force: `aeat-safety-legal-gates` (advisory/calc-only, no live submission), `aeat-architecture-boundaries` (two-root CLI, closed sets are core StrEnums), `cli-notices-are-the-only-diagnostic-channel` (cross-surface nudges ride the typed Notice channel), `one-aggregation-path-pull-equals-calculate` (one input-assembly path).

## Considered options

Decision 1 - modalidad axis and reduccion:
- (A, chosen) Reuse the existing `declaration-type` binding and Art. 84 formula; add no new axis. Pro: the axis and the 3.400/2.150 reduccion already exist and are corpus-grounded; zero new core surface. Con: none material.
- (B, rejected) Introduce a new core `TributacionModalidad` StrEnum. Rejected: duplicates the live `declaration_type` binding; violates no-legacy/no-duplication and adds a parallel axis for a value the registry already carries.

Decision 2 - where the comparison lives and how it runs:
- (A, chosen) Keep the dedicated read verb `aeat app modelo work compare-taxation` as the canonical home, and add a discoverability nudge from the overview surface as a typed Notice when the active profile is a married unidad familiar, pointing to the verb. Pro: dedicated verb already exists and is correct; the nudge closes the "operator never learns it exists" gap without a bespoke result field. Con: the overview must detect the married-profile signal.
- (B, rejected) Move the comparison into the overview surface as an inline advisory that runs the calc. Rejected: overview is a read/status surface; running a full dual calc there couples an expensive computation into every status render and buries a first-class result inside advisory prose.
- (C, rejected) Multiplex the comparison onto `calculate --what-if individual`. Rejected: a what-if flag on the mutating calculate verb blurs the ephemeral, no-persist comparison with the revision-persisting calc path and invites forking the calc path.

Decision 3 - household/spouse-income input axis:
- (A, chosen for scope boundary) Record that a spouse-income axis is a hard dependency of any two-return individual comparison and is ABSENT at HEAD; scope it as the explicit precondition for the second slice, not as an inline addition. Pro: honest dependency accounting; keeps the first slice shippable. Con: the two-earner case stays unmodelled until the axis lands.
- (B, rejected now) Add the spouse-income profile axis and two-return aggregation in this same decision. Rejected: it is a substantial profile-schema and aggregation change (per-spouse income attribution, two-return summation) that deserves its own bounded slice and grounding; folding it in here over-scopes.

Decision 4 - bounded first slice vs full unidad-familiar matrix:
- (A, chosen) Ratify the shipped single-return comparator as the bounded first slice, correct the individual-branch faithfulness claim honestly (label it single-earner-faithful), consolidate the input-assembly onto the shared calculate path, and add the overview nudge. Defer the full two-earner income-split matrix to a second slice gated on the spouse-income axis (Decision 3B). Pro: ships value now, states the limit honestly, respects one-aggregation-path. Con: two-earner couples get a directional-but-incomplete answer until slice two.
- (B, rejected) Hold the whole feature until the full matrix is built. Rejected: discards a working single-earner comparator and the discoverability fix for the ~200k newly-married couples the origin audit cited.

## Constraints

- Spouse-income axis dependency: the two-earner individual comparison (Decision 3B / slice two) cannot begin until the profile carries per-spouse attributable income and the comparator can run a second individual return. This is a blocking precondition for the full matrix; the first slice does not depend on it.
- Input-assembly parallelism: `compare_taxation_for_work_unit` builds resolved inputs on a path that mirrors, rather than shares, the live calculate path. Consolidating both onto one input-assembly helper is required by `one-aggregation-path-pull-equals-calculate` before the comparator is trusted as authoritative; until then a calculate-path change can silently drift the comparator.
- Legal-figure finishing step: the 3.400/2.150 figures are grounded in the bundled AEAT manuals and the formula source_citations but carry agent-prepared reviewed_by; an operator cross-check against consolidated BOE Art. 84 (per legal-grounding-verifies-bundled-authoritative-corpus) is the finishing step before the reduccion is treated as filing-grade authority.
- Multi-year: the axis and formula exist for 2024 and 2025 revisions; earlier revisions are out of scope for the first slice.

## Implementation

We will ratify the existing single-return comparator as the accepted first slice and make four changes, none of which forks the calculation path.

We will keep `aeat app modelo work compare-taxation` as the canonical comparison home and reuse the existing `declaration-type` binding and Art. 84 reduccion formula unchanged; no new core enum axis is added.

We will consolidate `compare_taxation_for_work_unit` onto the same input-assembly helper the live calculate path uses, so the comparison and the calculate path cannot drift, satisfying one-aggregation-path.

We will correct the comparator honesty surface: the individual branch is faithful only for a single-earner unidad familiar, so the result and its recommendation reason will state that the individual figure is a single-return computation and (until slice two) does not model two separate spouse returns. The recommendation remains primary result data on the payload.

We will add an overview discoverability nudge as a typed `Notice` (info severity, `suggestion` = the compare-taxation command) emitted when the active profile is a married unidad familiar, never as a bespoke result field.

We will record the spouse-income profile axis and two-return aggregation as the explicit, separately-grounded second slice, gated on adding per-spouse income attribution to the profile schema.

## Rationale

The comparator already exists and is corpus-grounded, so the decision is scoping and honesty, not construction (research `2026-06-30-tributacion-conjunta-individual-research`). Reusing the live `declaration-type` binding and Art. 84 formula avoids a duplicate modalidad axis that would violate the no-duplication and single-taxonomy disciplines. The dedicated verb is the correct home because the comparison produces a first-class result, not a diagnostic; the overview nudge belongs on the Notice channel precisely because it is an incidental cross-surface hint, which is what `cli-notices-are-the-only-diagnostic-channel` reserves that channel for. Bounding the first slice to the single-return case is justified by a knockout constraint: genuine two-earner comparison requires a spouse-income axis that does not exist at HEAD, so the full matrix is not implementable today without a separate profile-schema change. Consolidating the input-assembly path is mandated, not optional, by one-aggregation-path: a comparator that assembles inputs differently from the calculate path is a latent drift surface even though the formula core is shared.

## Consequences

Positive: single-earner unidad familiar couples get a correct, corpus-grounded conjunta-vs-individual recommendation now; married taxpayers discover the verb via the overview nudge; the comparator stops drifting from the calculate path once input-assembly is shared; the honesty correction removes a silently-wrong claim (that the individual branch models two-earner filing).

Negative / accepted cost: two-earner couples receive only a directional single-return answer until slice two lands, and the result must explicitly disclaim that limit rather than silently present a partial figure as complete. The overview must gain a married-profile detection signal. The reduccion figures remain agent-reviewed pending an operator BOE cross-check.

Neutral: opens a clearly-scoped second slice (spouse-income axis plus two-return aggregation) with its own grounding, and leaves the 2024/2025 revision coverage as the supported range with earlier years explicitly out of scope.
