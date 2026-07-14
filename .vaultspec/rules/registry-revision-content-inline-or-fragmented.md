---
name: registry-revision-content-inline-or-fragmented
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

Historically a revision could declare sections EITHER inline in `revision.toml` OR
in fragmented subdirectories, so a subdirectory-blind check (`ls bindings/ | wc -l`)
missed inline declarations — in #15 (M303 `2009-y-siguientes`) it wrongly concluded
"parse-only" and missed a real cuota-without-base under-declaration, and it
mis-classified fully-inline M369. The `arch-remediation-registry-format` campaign
(ADR `2026-07-02-arch-remediation-registry-format-adr`) converged every revision to
the fragmented layout (byte-identical at the compiled-`ModeloRevision` level) and
added the loader refusal, so the loaded snapshot is now format-agnostic ground truth.
Companion to `aeat-registry-authority-flow`.

## How

- **Good:** to decide whether a casilla aggregates from the ledger, load the
  revision through the authority (`resources().modelos.authority.snapshot(...)`) and
  inspect `revision.bindings` / `revision.casillas` — the compiled schema is ground
  truth; `grep` the `bindings/` / `casillas/` fragments only to pin exact ids.
- **Good:** before grounding any binding-source classification, read the binding's
  `source` field (`ledger_iva_aggregation` vs `profile` vs `relation_prefill`) — a
  `source = "profile"` binding (autoconsumo, state attribution) is not a ledger
  silent-zero even when absent (#43).
- **Bad:** re-introducing a section table inline in a fragment directory's
  `revision.toml` — the loader refuses it, naming the `<section>/` subdirectory.
- **Bad:** `ls bindings/ | wc -l` as the SOLE signal of "is this revision
  calc-grade / does this casilla bind" — count the LOADED snapshot's sections, and
  never conclude "parse-only / staged build-out" from subdirectory absence without
  loading the revision.

## Status / Source

Active; converged by `arch-remediation-registry-format` (ADR
`2026-07-02-arch-remediation-registry-format-adr`, plan
`2026-07-02-arch-remediation-registry-format-plan`) — inline sections in
`revision.toml` are now a hard load error. First exposed by the #15 IVA-3 correction
(`6c259afc3`, recargo tail `4e669c113`). Companion: `aeat-registry-authority-flow`,
`registry-calculation-legal-grounding`.
