---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:b87e9594c0fcf56ef61e3923d83bee6a2586725ca2635e80d50acc965845d1c4'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
---
# `casilla-schema` audit: `W05.P11.S37 export exemption docstring review`

## Scope

Formal read-only review of the S37 documentation-only change in `src/cadrumo/domain/calculations/registry/_validate_export_exemption.py` and its execution record, grounded in the accepted canonical-derivations ADR, the raw M720 registry declarations, the binding-owned fixed-width selectors, and the production derivation path.

## Findings

### s37-exec-pass-count | low | The broader module result overstated its passing tests by one

The original execution record said the broader export-exemption module produced nine passes and one existing failure. A bounded rerun of that exact module produced **8 passed, 1 failed**. The named failure was accurately described: `test_declared_feeds_addressed_casilla_reasons_really_do_reach_a_box` fails because the bundled corpus currently has zero `FEEDS_ADDRESSED_CASILLA` declarations, and the plan assigns that dormant-member adjudication to S38. This finding is resolved: the execution record now says eight passes and one existing failure.

### s37-exec-markdown-hygiene | low | The corrected execution record had one extra blank line

The count correction was made through the VaultSpec CLI and its body hash and modified stamp attested cleanly, but the first receipt check reported one S37-owned markdown-hygiene warning. This finding is resolved: VaultSpec markdown repair removed the extra blank line, and the final scoped check reports markdown clean.

## Recommendations

No S37 follow-up remains. The reviewed production statement needs no code change. Direct TOML parsing proved two raw M720 records and zero inline fields. The bundled revision plus `derive_export_layouts_from_bindings` proved typed `BINDING` fields for `ejercicio` at offset 5, length 4 and `declaracion-complementaria-o-sustitutiva` at offset 121, length 2, and proved derivation idempotence. The focused real M720 pilot passed. Ruff check, Ruff format check, BasedPyright, and scoped diff check all passed; BasedPyright reported zero errors, warnings, and notes.

## Resolution

Both low-severity execution-record findings are **resolved**. The final S37 execution record states the exact observed result, preserves the accurate `FEEDS_ADDRESSED_CASILLA` explanation and S38 ownership boundary, has a current body hash and modified stamp, and passes VaultSpec markdown validation. Its content remains confined to the reviewed documentation correction and verification record.

Final verdict: **PASS**. The production docstring is factually precise, introduces no executable or legacy behavior change, and the S37 execution and audit records are cleanly attested. Unrelated vault warnings remain outside S37 ownership.
