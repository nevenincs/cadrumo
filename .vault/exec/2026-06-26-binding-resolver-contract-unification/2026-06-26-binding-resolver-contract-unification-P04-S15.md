---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S15'
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
     The S15 and 2026-06-26-binding-resolver-contract-unification-plan placeholders are machine-filled by
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
     The Author one declared disposition mapping keyed by BindingSourceKind member to its resolution state replacing the _pre_mesh_handled and _BUCKET_AGGREGATION_OWNED_SOURCES structures and the service provider enum, re-reading the LIVE mesh sets at execution time so every member carries its HEAD-at-execution disposition including r2's newly-enrolled withholding source as enrolled (not deferred), applying the apply-cached-on-collision drive against the concurrent r2 #28 withholding-enrollment and codex typing WIP and ## Scope

- `src/aeat/application/modelo/_calculation_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author one declared disposition mapping keyed by BindingSourceKind member to its resolution state replacing the _pre_mesh_handled and _BUCKET_AGGREGATION_OWNED_SOURCES structures and the service provider enum, re-reading the LIVE mesh sets at execution time so every member carries its HEAD-at-execution disposition including r2's newly-enrolled withholding source as enrolled (not deferred), applying the apply-cached-on-collision drive against the concurrent r2 #28 withholding-enrollment and codex typing WIP

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Author the one disposition registry in the source-mesh module: a `BindingSourceDisposition` StrEnum (`enrolled` / `deferred` / `reserved`) and `build_binding_source_dispositions(enrolled_sources)` that classifies every `BindingSourceKind` member from the LIVE enrolled set passed in, the `DEFERRED_SOURCE_KINDS` set, and the new `RESERVED_SOURCE_KINDS` carve-out.
- Move the reserved-undeclared carve-out (`PURCHASE_INVOICE_EVIDENCE`, `LEDGER_TRANSACTION`) from the parity test into the canonical `RESERVED_SOURCE_KINDS` frozenset so it has one declaration.
- Make the builder raise (typed `AggregationValidationError`) on a member that matches zero or two dispositions, so the registry is provably a total disjoint cover with no hard-coded per-member dispositions.
- Add the `aggregation.source_mesh.errors.ambiguous_source_disposition` error key through the locale CLI across all four catalogues.

Modified files: `src/aeat/application/aggregation/_source_mesh.py`, `src/aeat/application/aggregation/__init__.py`, `src/aeat/locales/{en,es,ca,hu}.yml`.

## Outcome

Landed in the P04 commit `9e59719a9`. One mapping now answers "where does source X resolve" for all 21 members, reading the live enrolled set at execution so a newly-enrolled source (withholding, profile, borrador) is reflected automatically. No casilla shift; the parity + binding + E2E suites green; locale scaffold --check + audit green.

## Notes

The locale CLI run also pruned five keys that this feature's own P01/P02 deletions had orphaned (the borrador/profile result-wrap validator messages and two PerModeloRegistryBindingResolution provider errors left behind by P01.S02); the prune is correct in-scope hygiene, verified value-preserving on every retained key.
