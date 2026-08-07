---
name: registry-revision-content-inline-or-fragmented
trigger: always_on
---

# Registry revision content is fragmented; assess via the loaded snapshot

## Rule

A registry modelo revision declares its sections — `bindings`, `formulas`,
`casillas`, `verification_expectations`, `verification_predicates`,
`constructs`, `completeness_manifest`, and every other array-of-tables field —
ONLY in fragmented subdirectories (`bindings/`, `formulas/`,
`verification_expectations/`, …). The fragment directory's `revision.toml`
manifest carries ONLY scalar revision metadata: label, `valid_from` /
`valid_to`, `period_selector`, `legal_refs`, `source_refs`,
`orden_aplicabilidad`, `continuidad_validation`.

The loader ENFORCES this: an inline `[[revisions."…".<section>]]` table, or the
`completeness_manifest` table, in `revision.toml` is a loud `RegistryLoadError`
naming the fragmented layout.

To assess whether a revision is calc-grade, whether a casilla is ledger-bound,
or whether a binding or formula is present, **load the revision through the
authority and inspect the compiled schema** — never infer a revision's coverage
from a directory listing alone.

## Why

Inline and fragmented declarations were historically both legal, so a
subdirectory-blind check missed inline declarations and wrongly concluded a
revision was parse-only, masking a real under-declaration. The registry-format
campaign converged every revision to the fragmented layout — byte-identical at
the compiled `ModeloRevision` level — and added the loader refusal, so the
loaded snapshot is now format-agnostic ground truth.

The same trap survives in any file-shape assumption: a glob matching one file
shape silently excludes directory-mode fragments, which can hold most of the
corpus. Assume fragmentation until you have checked; both shapes ship.

## How

- **Good:** to decide whether a casilla aggregates from the ledger, load the
  revision through the authority and inspect `revision.bindings` /
  `revision.casillas` — the compiled schema is ground truth. Grep the fragments
  only to pin exact ids.
- **Good:** before grounding any binding-source classification, read the
  binding's `source` field. A `source = "profile"` binding is not a ledger
  silent-zero even when absent from a ledger sweep.
- **Bad:** re-introducing a section table inline in a fragment directory's
  `revision.toml`; the loader refuses it.
- **Bad:** `ls bindings/ | wc -l` as the sole signal of whether a revision is
  calc-grade, or concluding "staged build-out" from subdirectory absence without
  loading the revision.

## Source

ADR `2026-07-02-arch-remediation-registry-format-adr` and plan of the same stem.
Companions: `aeat-registry-authority-flow`,
`registry-calculation-legal-grounding`.
