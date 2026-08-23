---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:0f7a199fdbe875b12088e10ba8aa24328bef479bcd4949288f5db8d8727c03c5'
step_id: 'S39'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S39 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The implement inventory repository resolution, diagnostics, source identity, and fingerprint provenance and ## Scope

- `src/cadrumo/application/aggregation/_inventory.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# implement inventory repository resolution, diagnostics, source identity, and fingerprint provenance

## Scope

- `src/cadrumo/application/aggregation/_inventory.py`

## Description

- Resolve strict 2025 inventory bindings from the encrypted schema-v3 ledger through the sole inventory projection.
- Preserve activity and year coordinates, stable source identity, and sealed projection-fingerprint provenance.
- Emit closed, value-free diagnostics for absent, unreadable, incomplete, tampered, conflicting, and unsupported state.
- Normalize encrypted document validation failures at the repository boundary without retaining decrypted exception context.
- Add fake and real encrypted repository coverage for success, absence, corruption, determinism, conflict, tamper, and confidentiality.

## Outcome

The application now has a canonical allocation-free inventory source resolver for the three approved 2025 operations. It reads the encrypted inventory document, selects the exact activity ledger, delegates all arithmetic and authority validation to the sealed domain projection, and returns source-owned values for casillas 0177, 0181, and 0182 with stable source identity and the projection fingerprint.

Missing and malformed selectors, absent ledgers, unsupported contexts, encrypted read failures, incomplete or tampered projections, and retained closing conflicts have distinct machine-readable dispositions. Diagnostic messages, logs, and exception surfaces carry no financial values, evidence references, content digests, actor, or command data. The persistence adapter translates strict rehydration failures into the canonical inventory error outside the caught exception handler, leaving neither a cause nor a context containing decrypted input.

Both independent reviews finished clear with zero findings. Thirteen focused tests passed against fake and real encrypted repositories; Ruff, the type checker, scoped diff hygiene, and the feature vault check were clean.

## Notes

The canonical bare-modelo vocabulary gate no longer reports the S39 resolver. Its repository-wide run remains red only for four unrelated concurrent offenders in filing rendering and CLI specification files, which were not changed or committed here. Resolver enrollment and connected disposition remain owned by S40.
