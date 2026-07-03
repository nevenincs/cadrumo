---
name: registry-revision-content-inline-or-fragmented
trigger: always_on
---

# Registry revision content is fragmented — revision.toml is scalar-only; assess via the loaded snapshot, never `ls`/`find` alone

## Rule

A registry modelo revision declares its sections — `bindings`, `formulas`,
`casillas`, `verification_expectations`, `verification_predicates`,
`constructs`, `completeness_manifest`, and every other array-of-tables field —
ONLY in fragmented subdirectories (`bindings/`, `formulas/`,
`verification_expectations/`, …). The fragment directory's `revision.toml`
manifest carries ONLY scalar revision metadata (label, `valid_from`/`valid_to`,
`period_selector`, `legal_refs`, `source_refs`, `orden_aplicabilidad`,
`continuidad_validation`). The loader ENFORCES this: an inline
`[[revisions."…".<section>]]` table (or the `completeness_manifest` table) in
`revision.toml` is a loud `RegistryLoadError` naming the fragmented layout. To
assess whether a revision is calc-grade, whether a casilla is ledger-bound, or
whether a binding/formula is present, load the revision through the authority
and inspect the compiled schema — never infer a revision's coverage from
`ls bindings/` / `find -path '*formulas*'` on the subdirectory listing alone.

## Why

The dual-format era is over. Historically a revision MAY have declared its
sections EITHER inline in `revision.toml` OR in fragmented subdirectories, and a
subdirectory-blind check (`ls bindings/ | wc -l`) was therefore blind to inline
declarations: during #15 (IVA-3, M303 `2009-y-siguientes`) a subdirectory-count
check wrongly concluded the revision was "parse-only" and missed a real
"cuota-without-base" under-declaration, because that revision declared its cuota
bindings/formulas INLINE; the same blind spot mis-classified M369 (fully inline)
in the settlement-guard sweep. The `arch-remediation-registry-format` campaign
(register D6, ADR `2026-07-02-arch-remediation-registry-format-adr`) converged
every remaining inline revision to the fragmented layout — proven byte-identical
at the compiled-`ModeloRevision` level per revision — and added the loader
refusal above, so the inline-vs-fragmented blind spot can no longer recur: there
is one on-disk format, and the loaded snapshot is format-agnostic ground truth.
The read-the-loaded-snapshot guidance survives the convergence; the
dual-format caveat is now history. This is the discovery-method companion to
`aeat-rag-discovery` (RAG-first grounding) and `aeat-registry-authority-flow`
(the loader compiles fragments into one strict schema).

## How

- **Good:** to decide whether a casilla aggregates from the ledger on a given
  revision, load the revision through the authority
  (`resources().modelos.authority.snapshot(...)`) and inspect
  `revision.bindings` / `revision.casillas` — the compiled schema is the
  format-agnostic ground truth. Sections always live in subdirectories now, so
  `grep` the `bindings/` / `casillas/` fragments for the exact ids after
  RAG-grounding the concept.
- **Good:** to find binding-coverage asymmetries, compare a casilla's `binding =`
  + `input_kind` across sibling revisions from the LOADED snapshot, not by
  diffing subdirectory file counts (the #15 / #40 pattern).
- **Good:** before grounding any binding-source classification, read the
  binding's `source` field (`ledger_iva_aggregation` vs `profile` vs
  `relation_prefill`) — a `source = "profile"` binding (autoconsumo, state
  attribution) is not a ledger silent-zero even when absent (#43).
- **Bad:** re-introducing a section table inline in a fragment directory's
  `revision.toml`. The loader refuses it, naming the `<section>/` fragment
  subdirectory it belongs in.
- **Bad:** `ls bindings/ | wc -l` as the SOLE signal of "is this revision
  calc-grade / does this casilla bind" — count the LOADED snapshot's sections,
  not on-disk file counts, and never conclude "parse-only / staged build-out"
  from subdirectory absence without loading the revision.

## Status

Active. Converged by the `arch-remediation-registry-format` campaign (register
D6): every inline revision was migrated to the fragmented layout and the loader
now refuses inline sections in `revision.toml`, so the dual-format assessment
hazard is structurally eliminated rather than mitigated. The rule survives to
carry the load-the-snapshot discipline (never `ls`/`find`-count) and to record
that a section inline in `revision.toml` is now a hard load error.

## Source

The #15 IVA-3 correction (M303 `2009-y-siguientes` domestic-base, fixed in
`6c259afc3`; the recargo/59-60 tail in `4e669c113`) that first exposed the
inline-vs-fragmented blind spot; the `arch-remediation-registry-format` campaign
(ADR `2026-07-02-arch-remediation-registry-format-adr`, plan
`2026-07-02-arch-remediation-registry-format-plan`) that converged the tree to
fragmented-only and added the loader refusal. Companion rules:
`aeat-rag-discovery`, `aeat-registry-authority-flow`,
`registry-calculation-legal-grounding`.
