---
tags:
  - '#adr'
  - '#m303-synthetic-generator-primitive-spec'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-02-m303-parser-engine-totals-impedance-adr]]"
  - "[[2026-06-03-synthetic-fixture-primitive-encoding-discipline-adr]]"
  - "[[2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - '[[2026-06-04-m303-synthetic-generator-primitive-spec-research]]'
---

# `m303-synthetic-generator-primitive-spec` adr: M303 synthetic fixture primitive box additions to _generate.py | (**status:** `accepted`)

## Authoring note

Authored via Write tool. Concrete spec for the coder picking up #157
after coder2-2 shell-wedged. This ADR is implementation-faithful enough
that a fresh-context coder can land it without re-reading the prior
M303 ADR cluster.

## Problem statement

The parser/engine impedance ADR
(`2026-06-02-m303-parser-engine-totals-impedance-adr`) decided Route A:
the M303 declaracion_pdf extraction profile extracts **primitives**
(`iva.repercutido.general`, `iva.repercutido.reducido`,
`iva.repercutido.super-reducido`, `iva.autorepercutido.intracomunitaria`,
`iva.autoconsumo.promotor.cuota`, `iva.soportado.interiores`), and the
engine recomputes `iva.cuota-devengada-total` (c27) and
`iva.cuota-deducible-total` (c45) via the existing formulas.

To land Route A, the synthetic-PDF generator
(`src/aeat/tests/fixtures/justificantes/_generate.py`) must print those
primitive line items on the M303 fixture pages so the parser has
something to extract. Today's `_draw_modelo_303_corpus` prints only the
form-page totals (boxes 27/29/45 and the downstream chain 46/64/66/69/71).
Coder2-2 was supposed to implement this and shell-wedged before
shipping. The cross-modelo discipline ADR
(`2026-06-03-synthetic-fixture-primitive-encoding-discipline-adr`)
codifies this is the right shape; this ADR pins the M303-specific design
so the next coder can land it in one focused commit.

## Decision: single-rate filer pattern with all base on `iva.repercutido.general` @ 21%

The simplest primitive distribution that keeps the existing c27/c45
totals intact across all 15 M303 corpus fixtures is the **single-rate
filer** pattern: all base attributed to the 21% general bracket, with
the other primitive brackets set to zero. Concretely:

- `iva.repercutido.general.base` = c27 / Decimal("0.21"), rounded to money-2
- `iva.repercutido.general.cuota` = c27 (the existing leaf)
- `iva.repercutido.reducido.base` = Decimal("0.00")
- `iva.repercutido.reducido.cuota` = Decimal("0.00")
- `iva.repercutido.super-reducido.base` = Decimal("0.00")
- `iva.repercutido.super-reducido.cuota` = Decimal("0.00")
- `iva.autorepercutido.intracomunitaria.base` = Decimal("0.00")
- `iva.autorepercutido.intracomunitaria.cuota` = Decimal("0.00")
- `iva.autoconsumo.promotor.base` = Decimal("0.00")
- `iva.autoconsumo.promotor.cuota` = Decimal("0.00")
- `iva.soportado.interiores.base` = c29 / Decimal("0.21"), rounded to money-2
- `iva.soportado.interiores.cuota` = c29 (the existing leaf)

With these primitives:

- Engine recomputes `iva.cuota-devengada-total` = sum of all repercutido
  cuota + autorepercutido cuota + autoconsumo promotor cuota = c27 + 0 +
  0 + 0 + 0 = c27. ✓
- Engine recomputes `iva.cuota-deducible-total` = sum of all soportado +
  autorepercutido (deducible side) = c29 + 0 = c29.
- Since the existing fixtures set c45 = c29 (only interior deducible,
  no intracomunitaria), the engine's c45 recomputation also equals the
  fixture's c45. ✓
- Downstream chain (c46/c64/c66/c69/c71) is unchanged because c27 and
  c45 are unchanged.

The single-rate filer pattern preserves every existing fixture's c46-c71
closure chain bit-for-bit, so the existing per-fixture closure docstrings
and the `_compute_m303_closure` helper require zero changes.

## Why not mixed-rate distribution

A mixed-rate distribution (e.g. 60% general / 30% reducido / 10%
super-reducido) is more realistic-shaped for a typical AEAT M303 filer
but introduces three costs not justified by the verification-chain test
goal:

1. **Per-rate cuota math.** Each rate bracket needs base × tipo = cuota
   computed and the cuotas summed to match c27. The 21%/10%/4% tipos
   make the per-rate base values irrational (e.g. 60% of 12000 / 0.21 ≈
   34285.71); rounding errors at money-2 propagate to c27 mismatch by
   ±0.01 across fixtures. Solvable with careful rounding but adds
   authoring cost.

2. **Loses per-fixture stability.** Each of 15 fixtures needs a hand-
   chosen rate distribution; an audit pass needs per-fixture
   justification of the chosen split. The single-rate pattern is
   uniform across fixtures.

3. **Doesn't exercise additional engine code paths.** The
   `iva.cuota-devengada-total` formula sums whatever brackets are
   non-zero; whether one bracket is non-zero or three are non-zero, the
   formula's branch coverage is identical (it sums them all
   unconditionally).

A mixed-rate fixture pool is appropriate for **rate-distribution-
specific** verification tests (e.g. tests that assert "the engine
correctly distributes base across rate brackets when the operator
files mixed-rate"), and those should land as additional fixtures with
explicit mixed-rate intent declared in their docstring — not as a
remediation of the existing single-rate-equivalent corpus.

## Generator changes

The implementation is concentrated in three locations within
`src/aeat/tests/fixtures/justificantes/_generate.py`:

### 1. `_Modelo303CorpusFixture` dataclass — add primitive fields

After `c45: Decimal` (line ~1648), add:

```python
# Primitive leaf inputs that the engine sums into c27 (cuota-devengada-total)
# and c45 (cuota-deducible-total) per Route A of
# 2026-06-02-m303-parser-engine-totals-impedance-adr.
# Single-rate filer pattern: all base/cuota on the 21% general bracket;
# other repercutido/soportado brackets set to zero.
repercutido_general_base: Decimal      # iva.repercutido.general.base
repercutido_general_cuota: Decimal     # iva.repercutido.general.cuota (= c27)
repercutido_reducido_base: Decimal     # iva.repercutido.reducido.base (= 0)
repercutido_reducido_cuota: Decimal    # iva.repercutido.reducido.cuota (= 0)
repercutido_super_reducido_base: Decimal   # = 0
repercutido_super_reducido_cuota: Decimal  # = 0
autorepercutido_intra_base: Decimal    # iva.autorepercutido.intracomunitaria.base (= 0)
autorepercutido_intra_cuota: Decimal   # = 0
autoconsumo_promotor_base: Decimal     # iva.autoconsumo.promotor.base (= 0)
autoconsumo_promotor_cuota: Decimal    # = 0
soportado_interiores_base: Decimal     # iva.soportado.interiores.base
soportado_interiores_cuota: Decimal    # iva.soportado.interiores.cuota (= c29)
```

### 2. `_compute_m303_primitives` helper

Add a sibling to `_compute_m303_closure` that derives the primitive set
from the existing c27 and c29 leaf inputs:

```python
def _compute_m303_primitives(c27: Decimal, c29: Decimal) -> dict[str, Decimal]:
    """Compute single-rate M303 primitives that sum to c27 and c29.

    Pattern: all base on iva.repercutido.general @ 21%; all deducible on
    iva.soportado.interiores @ 21%. Other repercutido/soportado/
    autorepercutido/autoconsumo brackets set to zero.

    Returns a dict with the 12 primitive field values for the corpus fixture.
    Grounded in 2026-06-03-m303-synthetic-generator-primitive-spec-adr.
    """
    tipo_general = Decimal("0.21")
    zero = Decimal("0.00")
    return {
        "repercutido_general_base": (c27 / tipo_general).quantize(Decimal("0.01")),
        "repercutido_general_cuota": c27,
        "repercutido_reducido_base": zero,
        "repercutido_reducido_cuota": zero,
        "repercutido_super_reducido_base": zero,
        "repercutido_super_reducido_cuota": zero,
        "autorepercutido_intra_base": zero,
        "autorepercutido_intra_cuota": zero,
        "autoconsumo_promotor_base": zero,
        "autoconsumo_promotor_cuota": zero,
        "soportado_interiores_base": (c29 / tipo_general).quantize(Decimal("0.01")),
        "soportado_interiores_cuota": c29,
    }
```

### 3. Per-fixture instantiation — propagate primitive values

Each `_MODELO_303_CORPUS_FIXTURES` entry adds 12 primitive field assignments
via `**_compute_m303_primitives(c27, c29)`. Worked example for the first
fixture (lines ~1702-1716):

```python
_Modelo303CorpusFixture(
    filename="303/2021-2T.pdf",
    ejercicio="2021",
    periodo="2T",
    tax_id="Y0000001S",
    new_template=False,
    c27=Decimal("12000.00"),
    c29=Decimal("7800.00"),
    c45=Decimal("7800.00"),
    c46=_compute_m303_closure(Decimal("12000.00"), Decimal("7800.00"))[0],
    c64=_compute_m303_closure(Decimal("12000.00"), Decimal("7800.00"))[1],
    c66=_compute_m303_closure(Decimal("12000.00"), Decimal("7800.00"))[2],
    c69=_compute_m303_closure(Decimal("12000.00"), Decimal("7800.00"))[3],
    c71=_compute_m303_closure(Decimal("12000.00"), Decimal("7800.00"))[4],
    **_compute_m303_primitives(Decimal("12000.00"), Decimal("7800.00")),
),
```

This propagation is mechanical across all 15 fixtures.

### 4. `_draw_modelo_303_corpus` — print primitive line items

The drawing function gains primitive line items printed **before** the
existing total lines. The label text comes from the AEAT-published M303
form vocabulary. Suggested order (matches the AEAT-published printed
form's vertical layout — Régimen general → IVA devengado section first,
then IVA deducible):

```
"IVA devengado regimen general:"  (section header)
"Base imponible general (01) {base_general}"
"Cuota general (03) {cuota_general}"
"Base imponible reducido (04) {base_reducido}"     # 0 in single-rate
"Cuota reducida (06) {cuota_reducido}"             # 0
"Base imponible super-reducido (07) {base_super}"  # 0
"Cuota super-reducida (09) {cuota_super}"          # 0
"Adquisiciones intracomunitarias base (10) {base_intra}"   # 0
"Adquisiciones intracomunitarias cuota (12) {cuota_intra}" # 0
"Operaciones autoconsumo base (14) {base_autoconsumo}"     # 0
"Operaciones autoconsumo cuota (16) {cuota_autoconsumo}"   # 0
"Total cuota devengada (27) {c27}"   # existing line, kept for AEAT-form fidelity

"IVA deducible:"  (section header)
"Base operaciones interiores corrientes (28) {base_soportado}"
"Cuota operaciones interiores corrientes (29) {c29}"       # existing line
...other existing chain lines unchanged
```

The total lines (27/45) are kept on the fixture page because they appear
on the AEAT-published justificante, but the extraction profile (per the
2026-06-02 ADR) no longer targets them.

### 5. Extraction profile update (already specified in the parent ADR)

The `0001-modelo-303-declaracion-pdf.toml` extraction profile entries
for casillas 27 and 45 are removed and replaced with primitive-id
targets per the 2026-06-02 Route A specification. The patterns target
the new primitive line labels:

```
{casilla_id = "iva.repercutido.general.cuota", match_strategy = "named_label",
 value_kind = "amount", label_pattern = 'Cuota\s+general'},
{casilla_id = "iva.repercutido.reducido.cuota", ...},
... etc for each primitive ...
{casilla_id = "iva.soportado.interiores.cuota", ...},
```

## Per-fixture value distribution table

Every fixture's c27/c29 values are unchanged from the existing
`_MODELO_303_CORPUS_FIXTURES` table. The derived primitives follow
deterministically from `_compute_m303_primitives(c27, c29)`. Worked out
for the 8 new-template fixtures:

| fixture          | c27       | repercutido_general_base | c29       | soportado_interiores_base |
|------------------|-----------|--------------------------|-----------|---------------------------|
| 303/2023-1T.pdf  | 12600.00  | 60000.00                 | 8100.00   | 38571.43                  |
| 303/2023-2T.pdf  | 13800.00  | 65714.29                 | 8700.00   | 41428.57                  |
| 303/2023-3T.pdf  | 15000.00  | 71428.57                 | 9300.00   | 44285.71                  |
| 303/2023-4T.pdf  | 16800.00  | 80000.00                 | 10500.00  | 50000.00                  |
| 303/2024-1T.pdf  | 13200.00  | 62857.14                 | 8400.00   | 40000.00                  |
| 303/2024-2T.pdf  | 14400.00  | 68571.43                 | 9000.00   | 42857.14                  |
| 303/2024-3T.pdf  | 16200.00  | 77142.86                 | 10200.00  | 48571.43                  |
| 303/2024-4T.pdf  | 18000.00  | 85714.29                 | 11400.00  | 54285.71                  |

The 7 legacy-template fixtures (2021-2T through 2022-4T) get the same
primitive treatment, though their extraction profile (the 2009-y-siguientes
revision profile) MUST be updated in the same commit per the
co-landing rule in the parent ADR.

## Anti-tautology test

Per the cross-modelo discipline ADR
(`2026-06-03-synthetic-fixture-primitive-encoding-discipline-adr`), add a
single anti-tautology test that:

1. Loads one M303 fixture's primitives.
2. Mutates `repercutido_general_cuota` to a new value (e.g. add 100.00).
3. Re-renders the PDF.
4. Parses + runs the engine.
5. Asserts `iva.cuota-devengada-total` equals the mutated value (+ 100.00 vs original) — i.e. the engine's recomputation tracks the primitive.

Failure of this test means the engine isn't really summing primitives —
either the parser is still extracting the printed total and discarding
the primitives, or the engine formula is broken. Either way, the
verification-chain reds were not the real green.

## Commit shape

Single atomic commit per the engine-and-fixture co-landing rule:

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml` (profile patterns: remove 27/45, add primitive ids).
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml` (legacy profile patterns: same shape).
- `src/aeat/tests/fixtures/justificantes/_generate.py` (dataclass + helper + per-fixture instantiation + drawing).
- Regenerate the 15 M303 corpus PDFs by running `uv run python src/aeat/tests/fixtures/justificantes/_generate.py`.
- Update each fixture's sidecar JSON if the sidecar declares per-casilla expected values (verify whether the sidecars carry expected casilla values; if so, they need the new primitive entries).
- Add the anti-tautology test as `src/aeat/adapters/inbound/declaracion/test_m303_primitive_anti_tautology.py`.

Estimated change footprint: ~80-100 LOC across the generator + ~20 LOC
profile changes + ~50 LOC anti-tautology test + binary fixture
regeneration (15 PDFs).

## Out of scope

- Mixed-rate fixture pool (deferred until a rate-distribution-specific
  test surfaces).
- Real-corpus M303 fixtures (those carry operator-filed primitives;
  this ADR is for the synthetic pool).
- The fichero-BOE golden SHA contract (separate ADR
  `2026-06-03-fichero-boe-golden-sha-contract-shape-adr`).

## Status

Accepted. The coder picking up #157 implements per this spec in one
atomic commit; the cross-modelo discipline ADR remains the durable
pattern.

## Findings (2026-06-03, coder pickup) — spec defect: 12-field encoding does not match registry schema

Author: coder picking up team-lead delegation for task #157 on
`chore/eliminate-shims`. Reading the registry casillas before any
edit, three concrete spec-vs-registry mismatches block the proposed
12-field encoding. The decision (Route A primitives) remains correct;
the **per-fixture field shape** authored in this ADR does not match
the casillas the engine and the parser must speak to.

### Finding 1 — there are no `.base` casillas; per-rate primitives are cuota-only Decimals

The ADR proposes 12 primitive fields on `_Modelo303CorpusFixture`
split into base/cuota pairs:
`repercutido_general_base + repercutido_general_cuota`,
`repercutido_reducido_base + repercutido_reducido_cuota`,
`repercutido_super_reducido_base + repercutido_super_reducido_cuota`,
`autorepercutido_intra_base + autorepercutido_intra_cuota`,
`autoconsumo_promotor_base + autoconsumo_promotor_cuota`,
`soportado_interiores_base + soportado_interiores_cuota`.

The actual M303 registry casillas (verified in
`src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`
and the parallel 2009-y-siguientes file) are single-leaf cuota IDs:

- `iva.repercutido.general` — one Decimal, `input_kind = "bound"`
- `iva.repercutido.reducido` — one Decimal, `input_kind = "bound"`
- `iva.repercutido.super-reducido` — one Decimal, `input_kind = "bound"`
- `iva.soportado.interiores` — one Decimal, `input_kind = "bound"`
- `iva.autorepercutido.intracomunitaria` — one Decimal, `input_kind = "bound"`

There is no `iva.repercutido.general.cuota`, no
`iva.repercutido.general.base`, no `iva.soportado.interiores.base`,
etc. Adding 12 fields to the dataclass authors a shape the registry
does not honour; the extraction profile would have to target
`label_pattern = 'Cuota\s+general'` against `casilla_id = "iva.repercutido.general"`
(no `.cuota` suffix), and the `.base` fields have no engine consumer
at all — the engine sums cuota leaves directly, never per-rate bases.

The correct encoding is **6 cuota-only primitive fields** (5 in the
2009-y-siguientes legacy revision; see Finding 3):

```python
repercutido_general: Decimal           # iva.repercutido.general
repercutido_reducido: Decimal          # iva.repercutido.reducido
repercutido_super_reducido: Decimal    # iva.repercutido.super-reducido
autorepercutido_intra: Decimal         # iva.autorepercutido.intracomunitaria
autoconsumo_promotor_base: Decimal     # iva.autoconsumo.promotor.base (2023+ only)
soportado_interiores: Decimal          # iva.soportado.interiores
```

The base values per-rate were a useful authoring intuition (operator
fills in base + tipo → cuota), but the registry contract is
cuota-only at the engine boundary. If a future ADR wants per-rate
base casillas, the schema gain belongs there, not in fixture-shape.

### Finding 2 — `iva.autoconsumo.promotor.cuota` is computed, not a primitive

The ADR lists `autoconsumo_promotor_cuota` as one of the 12
primitives. The 2023-y-siguientes casilla declares
`input_kind = "computed"` with `formula = "modelo-303-autoconsumo-promotor-cuota"`,
whose expression is `iva.autoconsumo.promotor.base * 0.21`. It cannot
be supplied as an extracted primitive — the engine refuses computed
casillas in `inputs`. Only `iva.autoconsumo.promotor.base` is a leaf;
the engine derives the cuota.

So the per-rate primitive field set for the **2023-y-siguientes**
revision is the five cuota leaves above plus
`iva.autoconsumo.promotor.base` — six fields total, not twelve.

### Finding 3 — `iva.autoconsumo.promotor.*` casillas don't exist in 2009-y-siguientes

The 2009-y-siguientes casilla file declares only the five non-autoconsumo
leaves. Authoring `autoconsumo_promotor_base` on the legacy fixtures
(2021-2T … 2022-4T, 7 specimens) is harmless to the dataclass but
**must not** appear in the legacy extraction profile or the
synthetic-PDF page for those fixtures, and the legacy
`iva.cuota-devengada-total` formula does not sum it. The dataclass
either needs a default (`Decimal("0.00")` and only printed on new-template
pages) or the legacy fixtures simply do not populate it.

### Finding 4 — value-distribution table preservation invariant still holds, with corrections

Per ADR §"Decision: single-rate filer pattern", the engine recomputed
totals must equal the fixture's existing `c27` and `c29` for every
fixture. Under the corrected encoding:

- **devengada-total** = `repercutido.general + repercutido.reducido + repercutido.super-reducido + autorepercutido.intracomunitaria` (+ `autoconsumo.promotor.cuota` in 2023+). Setting `repercutido.general = c27` and the other repercutido + autorepercutido leaves to zero (and autoconsumo.promotor.base = 0, so its computed cuota = 0) yields engine c27 = fixture c27. ✓
- **deducible-total** = `soportado.interiores + autorepercutido.intracomunitaria`. Setting `soportado.interiores = c29` and `autorepercutido.intracomunitaria = 0` yields engine c45 derived as c29; existing fixtures already set fixture c45 = c29, so the chain holds. ✓

The original ADR's c46/c64/c66/c69/c71 closure preservation is
unchanged.

### Decision impact — pause for re-authoring

The ADR's intent (Route A primitives, single-rate filer pattern,
atomic commit) is sound. The concrete 12-field encoding is not
implementable against the actual registry. Rather than land a
half-fix that invents `.base`/`.cuota` casillas or routes through
a `computed` leaf, this coder is stopping and surfacing the
findings per the team-lead's escalation gate. The corrected encoding
is straightforward (6 cuota-only fields for 2023+, 5 for legacy), and
the extraction-profile patch becomes correspondingly smaller; a fresh
coder pickup with this Findings section + the corrected primitive
list can land in one atomic commit per the original commit-shape
discipline.

No code, fixture, profile, or test changes were made on this pass.
Branch state at end of this pass matches HEAD `f6ae3c35e` modulo
this ADR edit.
