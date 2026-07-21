---
tags:
  - '#adr'
  - '#prorrata-art104-tres-exclusions'
date: '2026-07-07'
modified: '2026-07-07'
related:
  - "[[2026-07-05-cross-period-prorrata-adr]]"
  - "[[2026-07-01-iva-complexity-hardening-scope-adr]]"
  - "[[2026-07-01-iva-bienes-inversion-regularizacion-adr]]"
---

# `prorrata-art104-tres-exclusions` adr: `Prorrata art 104.Tres denominator exclusions: ledger auto-classification boundary and reconciliation-vs-authority for the annual volume rollup` | (**status:** `proposed`)

## Problem Statement

The prorrata general percentage is a fraction of operation volumes (art. 104.Dos), and
LIVA art. 104.Tres (bundled `ley-37-1992.html`, `#a104`) lists the operations **excluded
from both terms** of that fraction. Verbatim, the exclusions are:

1. Operations carried out from **permanent establishments outside** the territory of
   application of the tax (`1.º ... establecimientos permanentes situados fuera del
   territorio de aplicación del Impuesto`);
2. The **IVA cuotas that directly taxed** those operations (`2.º Las cuotas del Impuesto
   sobre el Valor Añadido que hayan gravado directamente las operaciones`);
3. The amount of **entregas y exportaciones of bienes de inversión** the taxpayer used
   in its activity (`3.º ... entregas y exportaciones de los bienes de inversión`);
4. The amount of **inmobiliario or financiero operations that are not the taxpayer's
   habitual** business activity (`4.º ... operaciones inmobiliarias o financieras que no
   constituyan actividad empresarial o profesional habitual`), with arrendamiento always
   deemed habitual and "operaciones financieras" per art. 20.Uno.18;
5. Operations **not subject** to the tax under **art. 7** (`5.º Las operaciones no
   sujetas al impuesto según ... el artículo 7`);
6. The operations referred to in **art. 9, número 1.º, letra d)** (self-supplies of that
   letter) (`6.º Las operaciones a que se refiere el artículo 9, número 1.º, letra d)`).

The parent `cross-period-prorrata` ADR ships the annual ledger volume rollup as a
**divergence ADVISORY only** (`application/calculations/_prorrata_regularizacion.py`:
`ProrrataDeclaredVolumeLedgerRollup`, `build_prorrata_declared_volume_divergence_advisory`)
"precisely because it cannot auto-classify the art. 104.Tres exclusions." Ledger
transactions (`domain/transactions/_models.py`) carry **no exclusion flags** — only
`prorrata_reference`. The parent ADR deferred "the art. 104.Tres financial/inmobiliario
denominator special-computation rules beyond the exclusion set" and "automatic
art. 104.Tres exclusion classification in the ledger rollup (the rollup stays a
reconciliation check until then)."

**Grounding correction.** The scope ADR's prose and this campaign's brief list
"subvenciones no vinculadas al precio" as an art. 104.Tres exclusion. The **current**
consolidated art. 104.Tres does **not** — subvenciones were removed from the prorrata
denominator entirely by Ley 3/2006 (they are simply not computed, not an exclusion of
otherwise-computed volume). This ADR grounds on the **six** exclusions the bundled corpus
actually states and does not carry a subvenciones exclusion.

## Considerations

- The six exclusions differ sharply in whether the ledger can classify them:
  - **(2) direct IVA cuotas** — structural; the cuota is never a volume term. No signal
    needed (the rollup sums bases/contraprestaciones, not cuotas).
  - **(5) art. 7 no-sujetas** and **(6) art. 9.1.d autoconsumos** — derivable from the
    existing `IvaCategory` taxonomy (which already carries `OPERACION_NO_SUJETA` and the
    autoconsumo categories); no new flag, classify from the category already on the row.
  - **(3) bienes de inversión disposals** — owned by the bienes-inversión register
    (`adapters/persistence/profile/bienes_inversion.py`); the rollup reads that register,
    not a transaction flag.
  - **(1) foreign permanent establishment** and **(4) non-habitual inmobiliario/financiero
    operations** — **judgment facts** (PE location, habituality, the art. 20.Uno.18
    financial-operation scope with arrendamiento always habitual) the ledger cannot
    reliably infer. These need an explicit operator-declared exclusion tag.
- The rollup being advisory-only is the parent ADR's deliberate posture: the
  operator-declared annual volume casillas are the filed authority (parent O7), the rollup
  surfaces contradiction. Promoting the rollup to authority is legitimate only once every
  exclusion is classifiable AND the result is oracle-proven — otherwise it silently ships
  a wrong denominator.
- The judgment exclusions are a *closed set of two* leaves plus the category- and
  register-derived ones; a small typed `Art104TresExclusion` core enum captures the
  operator-declared cases without an open-ended flag bag.

## Considered options

**D1 — Per-exclusion classification: auto vs operator-declared.**

- **Hybrid, grounded per exclusion (CHOSEN).** Auto-classify the structurally- or
  category-derivable exclusions — (2) direct cuotas structurally, (5) art. 7 via
  `IvaCategory.OPERACION_NO_SUJETA`, (6) art. 9.1.d autoconsumo via its category, (3)
  bienes de inversión via a read of the bienes-inversión register — and require an
  explicit operator-declared `Art104TresExclusion` tag on the ledger row only for the two
  judgment exclusions ((1) foreign PE, (4) non-habitual inmobiliario/financiero). The tag
  is a new `core` StrEnum with the six leaves so the closed set has one typed home.
- (a) Everything operator-declared (REJECTED) — burdens the operator with exclusions the
  category/register already encode, and drifts from the existing `IvaCategory` taxonomy.
- (b) Everything auto (REJECTED) — the PE and habituality exclusions are genuine judgment
  facts; auto-classifying them ships a wrong denominator silently.

**D2 — Does the annual rollup ever become an authoritative filed-volume source?**

- **Stays a reconciliation advisory until every exclusion is classifiable AND oracle-proven;
  then promoted to a pre-fill PROPOSAL, never a silent replacement (CHOSEN).** The
  operator-declared annual volume casillas remain the filed authority (parent O7). Once
  the auto + operator-declared exclusion classification is complete and proven against an
  AEAT worked example, the rollup is promoted from "divergence advisory" to "pre-fill
  proposal + divergence advisory": it may *propose* the con-derecho/sin-derecho volumes,
  but a divergence from operator-entered volumes still surfaces, and the operator's
  declared volumes still file. The rollup never silently substitutes the denominator
  (`no-silent-under-declaration`).
- Promote the rollup to authority now (REJECTED) — with the judgment exclusions
  unclassified it would file a wrong regulated percentage; this is the exact defect the
  parent ADR made it advisory to avoid.

## Constraints

- Parent stability: the rollup, the divergence advisory, and the declared-volume authority
  (`cross-period-prorrata`, accepted, landed) are consumed and refined, not re-opened; this
  ADR adds exclusion classification and the promotion gate the parent deferred.
- No fabricated exclusion: the judgment exclusions exist only when operator-tagged; the
  category/register-derived ones are read from existing typed data, never inferred from
  amounts (`no-silent-under-declaration`).
- Legal grounding: art. 104.Tres is present verbatim in the bundled LIVA (art. 104 is
  already a `legal/iva.toml` entry, `#a104`); art. 7 is a dedicated corpus file
  (`ley-37-1992-art-7.html`) and art. 9 a `legal/iva-flow.toml` entry. The implementation
  cross-checks the exclusion taxonomy against these, adds the art. 7 / art. 9.1.d
  `legal_refs` where the exclusion is asserted, and does NOT introduce a subvenciones
  exclusion (`legal-grounding-verifies-bundled-authoritative-corpus`,
  `registry-calculation-legal-grounding`).
- Bienes-inversión boundary: the (3) bienes-de-inversión exclusion reads the
  bienes-inversión register (an active peer campaign surface); this ADR only *reads* it,
  it does not re-model disposals (`composition-service-no-parallel-write-path`).
- Verification: the exclusion-applied rollup is proven against an AEAT worked example that
  includes at least one excluded operation, never hand-computed
  (`no-tautological-calculation-tests`).

## Implementation

A new `core` `Art104TresExclusion` StrEnum (six leaves) types the exclusion axis. The
ledger row gains an operator-declared exclusion tag used only for the two judgment
exclusions (foreign PE, non-habitual inmobiliario/financiero); the other four are derived
— direct cuotas structurally, art. 7 and art. 9.1.d from `IvaCategory`, bienes de inversión
from a read of the bienes-inversión register. The annual volume rollup in
`_prorrata_regularizacion.py` applies the exclusions when summing con-derecho/sin-derecho
volumes and continues to raise the divergence advisory against the operator-declared
casillas. Once the classification is complete and oracle-proven, the rollup is promoted
from advisory to a pre-fill proposal (still non-authoritative: the declared volumes file,
divergence still surfaces). The art. 7 / art. 9.1.d `legal_refs` are added where the
exclusion is asserted; no subvenciones exclusion is introduced.

## Rationale

The rollup is advisory today for one reason — it cannot classify the exclusions — so the
whole feature is that classification, done honestly per exclusion. The hybrid (D1) is
forced by the exclusions genuinely splitting into structural/category/register-derived and
judgment cases; typing the closed set in `core` keeps it auditable. Keeping the declared
volumes as the filed authority and promoting the rollup only to a *proposal* (D2) preserves
the parent ADR's O7 lesson: a projection that could not represent the full regulated
computation must reconcile, not replace, and it earns pre-fill only once it can classify
every exclusion and is proven. Grounding on the six real exclusions (not subvenciones)
avoids baking a stale exclusion into a regulated denominator.

## Consequences

- Gain: the annual volume rollup applies the art. 104.Tres exclusions, so its divergence
  advisory becomes a meaningful reconciliation and, once proven, a pre-fill proposal — a
  step toward a ledger-derived definitive percentage without ever silently replacing the
  filed volumes.
- Gain: corrects the subvenciones mis-statement carried in prior prose; the denominator
  exclusions are exactly the six the law states.
- Cost accepted: the two judgment exclusions require operator tagging; the rollup stays
  non-authoritative (advisory, then proposal) — casilla-44 volumes remain operator-filed.
- Difficulty: the bienes-inversión register read crosses an active peer surface (read-only);
  the AEAT worked-example oracle must include an excluded operation.
- Pitfall: a future agent may re-add a subvenciones exclusion from a secondary source, or
  promote the rollup to silent authority before the judgment exclusions are classified —
  both ship a wrong regulated denominator. A third pitfall: excluding the *cuotas* term
  when the rollup already sums bases, double-counting exclusion (2).
- Pathway: complete + proven exclusion classification is the precondition the parent ADR
  set for the ledger rollup to earn volume-authority; this ADR builds it.

## Implementation footprint

Files the implementation will touch (for wave-clustering; see the ADR-vs-ADR overlap
report):

- `src/aeat/core/` (a new `_prorrata_exclusions.py` or the IVA core module) — the new
  `Art104TresExclusion` StrEnum (six leaves). Unique to this ADR.
- `src/aeat/domain/transactions/_models.py` — the operator-declared exclusion tag on the
  ledger row. **SHARED with `prorrata-especial` (input_classification) and
  `prorrata-sectores-diferenciados` (sector reference).**
- `src/aeat/application/calculations/_prorrata_regularizacion.py` — the rollup applies the
  exclusions; the divergence/pre-fill advisory. **SHARED with `prorrata-especial` (the
  +10% mandatory-especial advisory lives here).**
- `src/aeat/application/aggregation/_iva_ledger.py` — exclusion filtering at the annual
  volume rollup. **SHARED with `prorrata-especial` (regime routing) and
  `prorrata-sectores-diferenciados` (sector routing) — hottest shared surface.**
- `src/aeat/domain/iva/_prorrata.py` — the exclusion set is registry-grounded; substrate
  consumes it in the definitive-percentage computation. **SHARED (additive) with the
  sibling ADRs.**
- `src/aeat/adapters/persistence/profile/bienes_inversion.py` (or its facade) — read-only
  cross-read for the (3) bienes-de-inversión exclusion. Crosses the bienes-inversión peer
  surface (read-only).
- `src/aeat/_data/registry/aeat/legal/iva.toml` / `legal/iva-flow.toml` — art. 7 /
  art. 9.1.d `legal_refs` on the exclusion assertions (art. 104 entry already exists).
  **SHARED (additive, distinct blocks) with the sibling ADRs.**
- `src/aeat/_data/registry/aeat/modelos/303/**` — exclusion metadata on the volume
  casillas. **SHARED with `prorrata-especial` and `prorrata-sectores-diferenciados`.**
- CLI ledger surface / a `prorrata` verb group — operator exclusion tagging. **SHARED with
  `prorrata-especial` and `prorrata-sectores-diferenciados`.**
