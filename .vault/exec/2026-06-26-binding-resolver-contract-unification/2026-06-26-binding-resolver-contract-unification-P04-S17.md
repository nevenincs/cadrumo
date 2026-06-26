---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S17'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-resolver-contract-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-06-26-binding-resolver-contract-unification-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Extend the phase-2.1 mesh parity gate to assert the disposition registry covers every BindingSourceKind member and equals the union of enrolled resolver owned_sources, reading the LIVE mesh sets at run time with no hard-coded dispositions so r2's newly-enrolled withholding source is reflected automatically, making no-dormant-source-resolvers enforceable across the union and ## Scope

- `src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Extend the phase-2.1 mesh parity gate to assert the disposition registry covers every BindingSourceKind member and equals the union of enrolled resolver owned_sources, reading the LIVE mesh sets at run time with no hard-coded dispositions so r2's newly-enrolled withholding source is reflected automatically, making no-dormant-source-resolvers enforceable across the union

## Scope

- `src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py`

## Description

- Extend the phase-2.1 mesh parity gate with the disposition-registry assertions: the registry covers every `BindingSourceKind` member; the ENROLLED partition equals `_BUCKET_AGGREGATION_OWNED_SOURCES` exactly (the union the ADR mandates); the DEFERRED partition equals `DEFERRED_SOURCE_KINDS`; the RESERVED partition equals `RESERVED_SOURCE_KINDS`; and the three dispositions are a total disjoint cover.
- Re-point the existing reserved carve-out in the test at the canonical `RESERVED_SOURCE_KINDS` so the test no longer re-lists the members.

Modified files: `src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py`.

## Outcome

Landed in the P04 commit `9e59719a9`. The gate now reads the LIVE mesh sets at run time with no hard-coded dispositions, so r2's newly-enrolled withholding source (and the folded profile / borrador) are reflected automatically; a drift between the registry and the enrolled owned_sources fails the gate. This makes no-dormant-source-resolvers enforceable across the union. The extended gate plus the binding + E2E suites green; collect-only clean.

## Notes

The parity test is clean of peer WIP, so it was staged with a direct explicit-pathspec `git add`. The new disposition assertions are anti-tautological: the total-disjoint-cover assertion would fail if any member silently fell out of all three partitions.
