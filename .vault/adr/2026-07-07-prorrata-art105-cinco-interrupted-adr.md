---
tags:
  - '#adr'
  - '#prorrata-art105-cinco-interrupted'
date: '2026-07-07'
modified: '2026-07-17'
related:
  - "[[2026-07-05-cross-period-prorrata-adr]]"
  - "[[2026-07-01-iva-complexity-hardening-scope-adr]]"
  - '[[2026-07-10-prorrata-art105-cinco-interrupted-research]]'
---

# `prorrata-art105-cinco-interrupted` adr: `Prorrata art 105.Cinco interrupted activity: register representation and the last-three-active-years provisional rule` | (**status:** `accepted`)

## Problem Statement

LIVA art. 105.Cinco (bundled `ley-37-1992.html`, `#a105`) governs the prorrata percentage
during years of **interrupted activity**. Verbatim: "En los supuestos de interrupción
durante uno o más años naturales de la actividad empresarial o profesional o, en su caso,
de un sector diferenciado de la misma, el porcentaje de deducción definitivamente aplicable
durante cada uno de los mencionados años será el que globalmente corresponda al conjunto de
los tres últimos años naturales en que se hubiesen realizado operaciones." — for each
interrupted año natural, the definitive applicable percentage is the one that **globally
corresponds to the aggregate of the last three años naturales in which operations were
actually performed**.

The landed cross-period register seeds each ejercicio's provisional from the immediately
prior year's definitive (`ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA`, seeded
from the year−1 settlement observation). That carry **breaks** when year−1 had no activity:
there is no prior definitive to carry, and the register
(`domain/prorrata_register/__init__.py`, `ProrrataRegisterEntry`) has no representation of
an interrupted ejercicio. The parent `cross-period-prorrata` ADR deferred exactly this:
"art. 105.Cinco interrupted activity three-year rule."

Crucially, art. 105.Cinco is a **global** percentage over the *aggregate volumes* of the
last three active years — not the average of their three definitive percentages. The
register already persists, per ejercicio, the definitive volume inputs
(`definitive_volume_con_derecho` / `definitive_volume_sin_derecho`), so the global
percentage is `compute_prorrata_definitiva_anual` over the **summed** three-year volumes.
The substrate and the stored volumes already support this exactly; only the
interrupted-ejercicio representation and the seed walk are missing.

## Considerations

- The register is the only place that knows which past ejercicios had operations, so the
  "last three active years" set must be computed by walking the register, skipping
  interrupted ejercicios. This makes interrupted-year representation a prerequisite for the
  rule.
- Because the rule is a global percentage over aggregate volumes (not an average of
  percentages), the register must retain each active year's *volume inputs* — which it
  already does — and the seed recomputes via the substrate over the summed volumes; a
  percentage-average shortcut would ship a wrong regulated number.
- The register regime enum (`ProrrataRegisterRegime`) already carries a `ninguna` recorded
  no-prorrata state; an interrupted ejercicio is a distinct concept ("had no operations at
  all"), not "was under no prorrata" — conflating them loses the active/inactive signal the
  three-year walk needs.
- Art. 105.Cinco applies per differentiated sector too ("o, en su caso, de un sector
  diferenciado"); the register's `sector_id` axis already scopes the walk, so the rule
  composes with `prorrata-sectores-diferenciados` per sector without extra schema.
- This slice is almost entirely register/seeding-internal: it needs no ledger transaction
  field, no per-input classification, and no CLI verb — the interruption is recorded on the
  register and the seed logic reads it. That makes it the least entangled of the four
  prorrata slices with the ledger/CLI surfaces.

## Considered options

**D1 — How the register represents an interrupted ejercicio.**

- **An explicit "sin operaciones" (interrupted) marker on the ejercicio entry, distinct
  from the `ninguna` regime (CHOSEN).** The register records an interrupted ejercicio as an
  entry with no definitive percentage and an explicit interrupted state (a boolean or a
  dedicated state member), so the three-year walk can skip it. History is preserved: the
  register knows exactly which past years had operations.
- (a) Reuse `ProrrataRegisterRegime.ninguna` for interruption (REJECTED) — `ninguna` means
  "under no prorrata" (e.g. fully deductible, no sin-derecho ops), which is an *active* year
  with a 100% definitive; interruption means *no operations*. Conflating them makes the
  walk skip legitimately-active `ninguna` years or count truly-interrupted years.
- (b) Represent interruption only by the ABSENCE of an entry (REJECTED) — absence is
  ambiguous (a not-yet-created year vs a deliberately-interrupted year), and the walk cannot
  distinguish "no data" from "no operations".

**D2 — How the provisional prorrata behaves under the three-year rule.**

- **Seed the resuming ejercicio from the global percentage over the aggregate of the last
  three active years' volumes (CHOSEN).** When seeding an ejercicio whose immediately prior
  year is interrupted, the seed does not read year−1; it walks the register back, skipping
  interrupted years, collects the last three años naturales with operations, sums their
  stored con-derecho/sin-derecho volumes, and computes the global definitive percentage via
  `compute_prorrata_definitiva_anual`. A dedicated provenance
  (`interrumpida_tres_ultimos`, or the carried provenance annotated with the three-year
  basis) records that the seed came from the art. 105.Cinco rule, never a fabricated default
  and never silently the single pre-interruption year.
- (a) Carry the single most-recent pre-interruption definitive percentage (REJECTED) —
  contradicts art. 105.Cinco, which mandates the global figure over the last three active
  years, not the last one.
- (b) Average the last three definitives (REJECTED) — the law is a global percentage over
  aggregate *volumes*, not an average of percentages; the two differ whenever the three
  years' volumes are unequal.

## Constraints

- Parent stability: the cross-period register, seeding, and settlement mechanism
  (`cross-period-prorrata`, accepted, landed) are consumed and extended, not re-opened; the
  register already stores the per-year volume inputs the rule needs, and the `sector_id`
  axis already scopes it (`no-legacy-compatibility` — the volume fields exist).
- No fabricated regulated value: the resumption provisional comes only from the substrate
  over the stored three-active-year volumes; when fewer than the needed active years exist
  in the register, the seed surfaces an advisory naming the missing history rather than
  assuming a percentage (`no-silent-under-declaration`).
- Legal grounding: art. 105 is already a `legal/iva.toml` entry, currently grounding
  arts. 105.Uno/.Cuatro; the implementation extends its `required_text` to cover the
  art. 105.Cinco clause verbatim from the bundled corpus
  (`registry-calculation-legal-grounding`,
  `legal-grounding-verifies-bundled-authoritative-corpus`).
- Secure storage + roundtrip: the interrupted marker participates in the register's
  save/load/equality roundtrip and anti-tautology proof (`aeat-roundtrip-discipline`).
- Carry discipline: the three-year walk resolves each contributing year's revision via
  `select_revision` and re-confirms its `stamped_revision_id`; a divergent stamp blocks that
  contribution (`carried-observations-stamp-their-revision`,
  `revision-resolution-is-law-determined`).
- Verification: the global three-year percentage is proven against an AEAT worked example
  (or a hand-constructed multi-year register whose expected figure is the substrate's global
  computation over independently-stated volumes), never a percentage-average shortcut
  (`no-tautological-calculation-tests`).

## Implementation

The register entry gains an explicit interrupted ("sin operaciones") marker distinct from
the `ninguna` regime, recorded per `(ejercicio, sector_id)` and participating in the
roundtrip. The seed logic, when the immediately prior year is interrupted, walks the
register back skipping interrupted years, collects the last three active años naturales,
sums their stored con-derecho/sin-derecho volumes, and computes the global definitive
percentage through the existing `compute_prorrata_definitiva_anual`, recording an
art. 105.Cinco provenance. When insufficient active-year history exists, the seed surfaces
an advisory rather than assuming a percentage. The rule composes per sector via the existing
`sector_id` scoping. The art. 105 legal entry's `required_text` is extended with the
art. 105.Cinco clause from the bundled corpus. No ledger transaction field, per-input
classification, or CLI verb is required.

## Rationale

Art. 105.Cinco is a seeding rule, and the register was built to carry per-year definitive
volumes precisely so a multi-year global recomputation is possible without new storage — the
work is representing interruption and walking the history. A distinct interrupted marker
(D1) is required because `ninguna` is an *active* 100%-definitive year, not an inactive one;
conflating them corrupts the three-year walk. Seeding from the global percentage over the
aggregate volumes (D2) is the literal reading of "el que globalmente corresponda al conjunto
de los tres últimos años" and reuses the substrate, avoiding the percentage-average error a
casual implementation would make. Keeping the slice register/seeding-internal makes it the
cleanest of the four to run in parallel with the ledger-touching siblings.

## Consequences

- Gain: a taxpayer resuming after one or more interrupted years is seeded with the lawful
  art. 105.Cinco global percentage instead of a broken year−1 carry or a fabricated default.
- Gain: the register gains a truthful active/inactive history, which also sharpens the
  seeding cross-check for normal years.
- Cost accepted: the rule needs at least some active-year history in the register; with
  insufficient history it advises rather than computes (honest, not silent).
- Difficulty: the global-over-aggregate-volumes semantics must be implemented exactly
  (summed volumes, not averaged percentages); the AEAT/worked-example oracle must exercise a
  genuine interruption gap.
- Pitfall: a future agent may reuse `ninguna` for interruption (corrupting the walk) or
  average the three definitives (a wrong regulated number). A second pitfall: walking
  calendar years instead of *active* years — the three must be the last three *with
  operations*, skipping the gap.
- Pathway: the interrupted marker and the active-year walk generalise to the per-sector
  interruption art. 105.Cinco explicitly allows, composing with
  `prorrata-sectores-diferenciados`.

## Implementation footprint

Files the implementation will touch (for wave-clustering; see the ADR-vs-ADR overlap
report). This slice is deliberately register/seeding-internal — it touches NO ledger
transaction field, NO per-input classification, and NO CLI verb, making it the least
entangled of the four with the ledger/CLI surfaces:

- `src/cadrumo/core/_prorrata_register.py` — an interrupted-state member/marker (or a new
  provenance `interrumpida_tres_ultimos`) in the register enums. **SHARED (additive) with
  `prorrata-especial` and `prorrata-sectores-diferenciados` (register enums).**
- `src/cadrumo/domain/prorrata_register/__init__.py` — the interrupted-ejercicio representation
  on `ProrrataRegisterEntry` and the last-three-active-years seed walk. **SHARED with
  `prorrata-sectores-diferenciados` (per-sector orchestration) and `prorrata-especial`
  (especial-complete signal).**
- `src/cadrumo/domain/iva/_prorrata.py` — reuse `compute_prorrata_definitiva_anual` over the
  summed three-year volumes (read-mostly; maybe a global-aggregate helper). **SHARED
  (additive) with the sibling ADRs.**
- the register seeding path (`application/calculations/_prorrata_regularizacion.py` or the
  seeding helper that reads the register) — the art. 105.Cinco seed branch and the
  insufficient-history advisory. **SHARED with `prorrata-especial` (advisory builders) and
  `prorrata-art104-tres-exclusions` (rollup/advisory).**
- `src/cadrumo/_data/registry/aeat/legal/iva.toml` — extend the existing
  `[legal."ley-37-1992:art-105"]` `required_text` with the art. 105.Cinco clause. **SHARED
  (additive, same entry) with the sibling ADRs' distinct legal blocks.**
- NO change to `domain/transactions/_models.py`, NO change to
  `application/aggregation/_iva_ledger.py` per-input routing, NO CLI ledger change —
  distinguishing this ADR from the three ledger-touching siblings.
