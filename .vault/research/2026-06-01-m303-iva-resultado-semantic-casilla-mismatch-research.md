---
tags:
  - '#research'
  - '#m303-iva-resultado-chain'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# M303 iva.resultado semantic-to-form-number casilla mismatch: research & options

## Problem Statement

After the #111 refactor (`resultado-regimen-general` now computed as semantic casilla `iva.resultado-regimen-general`), the downstream formula `iva.resultado` still chains through form-numbered casillas:

```
iva.resultado = [66] + [77] + [68] - iva.compensacion-aplicada-periodo
```

where:
- `[66]` = `[64]` × `[65]` / 100 (computed via form-number args)
- `[64]` = `iva.resultado-regimen-general` + `[58]` + `[76]` (mixed semantic + form-number args)

**The schema boundary mismatch:**
- Registry loader + pydantic validators populate **semantic casillas only** (e.g., `iva.resultado-regimen-general`, `iva.compensacion-aplicada-periodo`)
- Bucket aggregation source resolver (ledger_iva_aggregation bindings) projects **semantic values only**
- Formula evaluation engine still references **form-numbered casillas** (`64`, `65`, `66`, `77`, `68`)
- IVA wallet engine integration and bucket aggregation tests both fail to find values for form-number references

**Root cause:** Semantic refactoring was incomplete. The formula expression tree was updated in #111 to use `iva.resultado-regimen-general`, but the downstream result-chaining formula (`iva.resultado`) and its intermediate steps (`64`, `66`) still chain through form numbers that the bucket resolver never populates.

## Architectural Options

### Option A: Full Semantic Rewire (preferred)

Rewrite the entire `iva.resultado` chain to reference semantic casilla IDs:

1. Rename form-numbered references to semantic names:
   - `[64]` → `iva.resultado-total` or similar (aggregate of general + simplified + regularization)
   - `[65]` → introduce semantic binding/selector for "state-apportionment-ratio" (currently operator-input only)
   - `[66]` → `iva.resultado-atribuible-estado` (state-attributable result)
   - `[77]` → `iva.importacion-liquidada` (importation IVA)
   - `[68]` → `iva.tributacion-conjunta-regularizacion` (joint taxation adjustment)

2. Update all three formulas (64, 66, resultado) to use semantic names exclusively
3. Extend bindings to project semantic casillas for new atomic concepts if needed
4. Bucket resolver then picks up all values through semantic paths

**Pros:**
- Eliminates schema boundary mismatch permanently
- Aligns with registry authority flow (semantic schema → runtime projections)
- Future-proof: semantic names survive regulatory form layout changes
- Clean verification expectations (all computed_casillas are semantic)

**Cons:**
- Requires TOML rewrites (3 formula definitions)
- May need new bindings for previously operator-input-only values (e.g., apportionment ratio)
- Higher complexity if apportionment ratio binding is non-trivial

---

### Option B: Extend Source Resolver to Project Form Numbers (moderate)

Keep form-numbered references in formulas; extend the bucket aggregation source resolver to project semantic casilla values onto form-numbered "convenience" casillas:

1. After resolver populates semantic values, compute form-number projections:
   - `[64]` = `iva.resultado-regimen-general + [58] + [76]` (computed projection)
   - `[66]` = `[64] × [65] / 100` (computed projection)

2. Add a post-processing step in `calculate_modelo_revision_from_bucket_aggregation()` to insert form-number projections into the engine result

**Pros:**
- No TOML registry changes
- Minimal code changes (one post-processing loop)
- Existing tests pass without modification

**Cons:**
- Violates separation of concerns: resolver should not compute derived values
- Hides the schema mismatch; future formulae may make the same mistake
- Apportionment ratio (`[65]`) still missing from resolver (operator-input only)
- Verification expectations still mix semantic + form-number (confusing)

---

### Option C: Intermediate Computed Binding (hybrid)

Keep most form-numbered references in formulas; introduce a small set of semantic-to-form-number intermediate bindings:

1. Add three new synthetic bindings:
   - `binding[64]` → source `computed_from_semantic` with DSL: `iva.resultado-regimen-general + [58] + [76]`
   - `binding[66]` → source `computed_from_semantic` with DSL: `[64] × [65] / 100`
   - (Keep `[77]`, `[68]` as-is: manual-input or separate binding to semantic casillas)

2. Formulas reference the new bindings instead of raw form numbers
3. Resolver populates semantic casillas; bindings layer computes the intermediate form-number derivations

**Pros:**
- TOML-level solution (no code changes needed in bucket resolver)
- Explicit and traceable (bindings are first-class registry objects)
- Hybridity allows gradual migration

**Cons:**
- Adds synthetic bindings that exist only for compatibility
- Still mixes semantic + form-number in verification expectations
- Less clean than full semantic rewire
- Requires binding DSL extension to support "computed_from_semantic" source type (or inline formula)

---

## Recommendation

**Option A (Full Semantic Rewire)** is the strongest choice:

1. It completes the semantic refactoring that #111 started
2. It aligns with the registry authority flow and pydantic schema patterns
3. It unblocks bucket resolver + IVA wallet engine integration cleanly
4. It prevents future similar regressions

The effort is moderate (3 formula TOML rewrites + possibly 1 new binding for apportionment ratio). The payoff is high: clean schema boundary, future-proof, and consistent with design intent.

**Secondary option:** If apportionment-ratio binding introduces unexpected complexity, fall back to **Option C** as a pragmatic hybrid that is still cleaner than Option B.

## References

- Registry authority flow ADR (semantic schema, runtime projections, validation boundary)
- M303 2023 revision TOML formulas (64, 66, resultado definitions)
- Bucket aggregation test expectations (what values are needed at runtime)
