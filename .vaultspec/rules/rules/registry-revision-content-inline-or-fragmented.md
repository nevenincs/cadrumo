---
name: registry-revision-content-inline-or-fragmented
---

# Registry revision content is inline OR fragmented — assess by both, never `ls`/`find` alone

## Rule

A registry modelo revision MAY declare its bindings, formulas,
`verification_expectations`, and `verification_predicates` EITHER inline in
`revision.toml` (the older monolithic format) OR in fragmented subdirectories
(`bindings/`, `formulas/`, `verification_expectations/`, …). When assessing
whether a revision is calc-grade, whether a casilla is ledger-bound, or whether a
binding/formula is present, read BOTH the inline `revision.toml` AND the
subdirectories — RAG-ground the concept first (`aeat-rag-discovery`), then `grep`
to confirm. NEVER infer a revision's calc-grade or binding coverage from
`ls bindings/` / `find -path '*formulas*'` on the subdirectories alone: the
subdirectory listing is blind to inline declarations and yields false
"parse-only / zero-bindings / staged build-out" conclusions.

## Why

During #15 (IVA-3, M303 `2009-y-siguientes`, filing years 2009-2022), a
structural check that only counted `bindings/` and `formulas/` subdirectory
files concluded the revision was "parse-only" with no calculation machinery and
filed a verdict of "not a live gap, by design". That was WRONG: the
`2009-y-siguientes` revision declares its cuota bindings, formulas, compensación
carry, and `verification_expectations` INLINE in `revision.toml`, while the
sibling `2023-y-siguientes` uses the fragmented-subdirectory format. The
subdirectory-blind check missed a real, plausibly-live "cuota-without-base"
under-declaration (the base-imponible casillas 01/04/07/28 were ledger-unbound on
2009-2022 while the cuota resolved). The operator's "the schema may be defective —
use RAG" challenge surfaced it; RAG-grounding the actual binding sets exposed the
defect, which was then fixed (#15 + the #41 recargo/59-60 tail). The same
inline-vs-fragmented blind spot also mis-classified M369 (OSS, fully inline) in
the settlement-guard sweep. Only M303 and M369 use inline today, but the format
is per-revision, not per-modelo, so the check must always consider both. This is
the discovery-method companion to `aeat-rag-discovery` (RAG-first grounding) and
`aeat-registry-authority-flow` (the loader merges inline and fragmented into one
strict schema regardless of on-disk form).

## How

- **Good:** to decide whether a casilla aggregates from the ledger on a given
  revision, `grep` BOTH `revision.toml` (inline `[[revisions."…".bindings]]` +
  the casilla's `binding =` / `input_kind`) AND the `bindings/` /
  `casillas/` subdirectories; RAG-search the concept first, then `grep` the exact
  ids. Better still, load the revision through the authority
  (`resources().modelos.authority.snapshot(...)`) and inspect
  `revision.bindings` / `revision.casillas` — the loaded schema is format-agnostic
  and is the ground truth.
- **Good:** to find binding-coverage asymmetries, compare a casilla's `binding =`
  + `input_kind` across sibling revisions from the LOADED snapshot (or by reading
  both inline and fragmented sources), not by diffing subdirectory file counts
  (the #15 / #40 pattern).
- **Good:** before grounding any binding-source classification, read the binding's
  `source` field (`ledger_iva_aggregation` vs `profile` vs `relation_prefill`),
  wherever it is declared — a `source = "profile"` binding (autoconsumo, state
  attribution) is not a ledger silent-zero even when absent (#43).
- **Bad:** `ls bindings/ | wc -l` or `find … -path '*formulas*' -name '*.toml' | wc -l`
  as the SOLE signal of "is this revision calc-grade / does this casilla bind" —
  blind to inline declarations; it produced the wrong #15 "parse-only" verdict.
- **Bad:** concluding "not a gap / staged build-out / parse-only by design" from
  subdirectory absence without reading `revision.toml` and RAG-grounding the
  actual binding/formula set.

## Source

The #15 IVA-3 correction (M303 `2009-y-siguientes` domestic-base, fixed in
`6c259afc3`; the recargo/59-60 tail in `4e669c113`), the binding-coverage
systemic sweep, and the binding-source grounding that scoped out the
profile-source autoconsumo/state-attribution casillas. Promoted per the
`vaultspec-codify` discipline after the inline-vs-fragmented blind spot caught two
real regulated under-declaration defects and prevented a false-positive in one
campaign. Companion rules: `aeat-rag-discovery`, `aeat-registry-authority-flow`,
`registry-calculation-legal-grounding`.
