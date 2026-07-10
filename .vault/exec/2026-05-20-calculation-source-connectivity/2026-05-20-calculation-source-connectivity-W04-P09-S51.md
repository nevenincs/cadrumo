---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S51'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-source-connectivity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S51 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Emit bucket events with source mesh diagnostics and fingerprints and ## Scope

- `src/aeat/application/modelo/_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit bucket events with source mesh diagnostics and fingerprints

## Scope

- `src/aeat/application/modelo/_actions.py`

## Description

- Emit `source_provenance_count` and an order-independent `source_provenance_trace_sha256` digest on the `MODELO_CALCULATION_CREATED` bucket-event payload.
- Fold each provenance row's stable source_kind / source_ref / fingerprint triple into the digest in sort-canonical order, mirroring the existing `borrador_bindings_trace_sha256` join-record pattern; an empty tuple yields the empty-string digest.
- Keep the additions purely additive so existing per-key payload readers are unaffected.

## Outcome

An audit reader can now detect a source-connectivity change from the bucket event's digest without decrypting the calculation revision, and can count the contributing source objects. The event stays a compact pointer back to the persisted revision, which carries the full typed trace.

## Notes

Folded into the same wave as S50 once the persisted `source_provenance` field existed. Confirmed no existing test asserts an exact `MODELO_CALCULATION_CREATED` payload key set (all readers use per-key access), so the additive keys are safe.
