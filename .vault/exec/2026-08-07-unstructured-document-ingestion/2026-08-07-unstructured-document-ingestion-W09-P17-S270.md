---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:7f85c9e82f4488455b488de44c423694ecc73d5e5070250f9c1fc40353a87baa'
step_id: 'S270'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Redact a bank account in its printed grouped form, since _IBAN_PATTERN carries no separator class so ES9121000418450200051332 redacts while ES91 2100 0418 4502 0005 1332 and the hyphenated rendering both pass raw - and an IBAN is essentially always printed in groups of four, which is how it arrives off a bank statement or an invoice footer, so the covered spelling is the one that does not occur - the arm exists by operator directive because a bank account number is sensitive financial data

## Scope

- `src/cadrumo/core/redaction/__init__.py`

## Description

- Promote `normalise_iban` into `core/_iban.py` beside the shape pattern and the mod-97 primitive, and export it through the core facade.
- Sweep the registry casilla validator and the refund-account model, each of which open-coded the same uppercase-and-strip-separators canonicalisation, onto that one function.
- Widen the IBAN scan with a separator class covering the space and the hyphen, and fold the matched span onto canonical form before the shape gate and the checksum decide.
- Build the corpus from what a producer prints: real checksum-valid accounts in groups of four, in prose, and an uppercase negative corpus of statement and invoice lines that a spaced-BBAN shape cannot be told from without the checksum.

## Outcome

`ES91 2100 0418 4502 0005 1332` and the hyphenated rendering now hash on both funnels, as do the German, British and French printed groupings. A near-miss differing only in its final check character still reaches the operator, so the checksum and not the shape is still what admits a match.

The canonicalisation now has one home. Two validators had the same three calls written out and the confidentiality funnel had none at all, which is precisely why the printed spelling was readable in operator output while both validators accepted it.

## Verification

Reproduction before the change, both funnels:

    'ES9121000418450200051332'      -> 'sha256:b179add4'
    'ES91 2100 0418 4502 0005 1332' -> 'ES91 2100 0418 4502 0005 1332'
    'ES91-2100-0418-4502-0005-1332' -> 'ES91-2100-0418-4502-0005-1332'

After, with the neighbouring-word cases and the near-miss included:

    'ES91 2100 0418 4502 0005 1332'                 -> 'sha256:701b5a94'
    'IBAN ES91 2100 0418 4502 0005 1332 EN FACTURA' -> 'IBAN sha256:701b5a94 EN FACTURA'
    'ES91 2100 0418 4502 0005 1333'                 -> unchanged
    'BOE-A-2026-12345'                              -> unchanged

Suite:

    uv run --no-sync pytest src/cadrumo/core/tests/test_redaction_printed_iban.py src/cadrumo/core/tests/test_redaction_neighbouring_word.py src/cadrumo/core/tests/test_redaction.py src/cadrumo/core/tests/test_redaction_nif_iva.py src/cadrumo/core/tests/test_redaction_separator_bearing_identity.py -m unit -q -p no:randomly
    228 passed in 23.91s

Over-redaction control, same frozen locale snapshot, shipped module against this one:

    compared: 69657   differing vs HEAD: 0

Mutation C restores the compact-only pattern from outside the repository:

    MUTATION C APPLIED. leak reopened: 'ES91 2100 0418 4502 0005 1332'; compact still redacts: 'sha256:b179add4'

Mutation D removes the canonicalisation from the gate:

    MUTATION D APPLIED. leak reopened: 'ES91 2100 0418 4502 0005 1332'; compact still redacts: 'sha256:b179add4'

Both windows were asserted open before the run, both carry a positive control (the compact spelling still hashes) and mutation C additionally carries a negative control (an uppercase modelo line still survives). Both flipped the suite:

    mutate_c: 20 failed
    mutate_d: 20 failed

The swept validators:

    uv run --no-sync pytest src/cadrumo/domain/deadlines -m unit -q -p no:randomly
    196 passed in 104.11s

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_iban_data_type.py src/cadrumo/core/tests -m unit -q -p no:randomly
    2 failed, 1138 passed in 243.80s

## Notes

The two failures in the combined registry and core run are the same tree-wide peer gates recorded against the sibling Step, both outside the redaction and IBAN surfaces.

An automated sweep commit landed the two validator files partway through this Step, taking the consumers of `normalise_iban` while leaving the core export they import it from uncommitted. HEAD was briefly unable to import the deadlines package. The export was landed immediately afterwards through the apply-cached drive, because the core facade was carrying an unrelated peer addition at the time; that peer's line was left unstaged and intact.

The separator class admits the space and the hyphen but not the dot, matching exactly what the canonical normaliser strips, so the scan and the gate cannot disagree about what a separator is. That is the same failure the sibling Step closed on the CIF arm.
