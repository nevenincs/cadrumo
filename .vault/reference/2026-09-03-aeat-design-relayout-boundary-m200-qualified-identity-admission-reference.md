---
tags:
  - '#reference'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:bbcee203a0b1cc72bd2fc91774eefc889d9a2ae20c7b6f8a7b3e0ffa20e80be1'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

# `aeat-design-relayout-boundary` reference: `m200 qualified identity admission`

## Summary

The modelo 200 / revision 2024 semantic map is authored with the printed token
`588`, while the closed reviewed-promotion receipt admits the distinct,
qualified canonical declaration `DP200018:00588`.  The compiler may make that
one substitution only after it has rebuilt and verified the receipt-backed
unique adjudication set, confirmed the selected revision contains the exact
canonical declaration, and matched the numeric token to the qualified suffix.

This is not a general numeric-padding rule.  The public semantic-map resolver
continues to reject a bare token that is not an exact identifier or ordinary
left-padded numeric identifier.  The receipt-aware admission is private to the
M200/2024 compiler route, and the compiled map remains attested alongside the
authored map before rendering.

The export-ref writer consumes compiler output, not authored map text.  It
recognises valid TOML basic and literal ID strings in a casilla table's own
body, and refuses nested-table `id` decoys; this preserves the exact
declaration boundary when the compiler-published cohort uses literal quotes.

## Evidence

- `dev/registry/pipeline/_semantic_map_validation.py` reconstructs the
  reviewed-promotion receipt and derives the private qualified admission.
- `dev/registry/pipeline/_semantic_map_join.py` retains authored and compiled
  maps as a paired, constrained representation.
- `dev/registry/pipeline/_export_tree.py` accepts only either member of that
  pair while still requiring joined fields and records to attest the compiled
  map exactly.
- `dev/registry/pipeline/_casilla_export_refs.py` writes the derived reverse
  relation without loosening declaration discovery.
- `dev/registry/tests/test_semantic_map_validation.py` and
  `dev/registry/tests/test_export_tree.py` pin positive and mutation cases.
