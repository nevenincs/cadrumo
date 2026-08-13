---
tags:
  - '#plan'
  - '#iva-art-69-dos-services'
date: '2026-08-12'
modified: '2026-08-12'
body_hash: 'sha256:13d7f755a29cf2f1291f8e574e09ba15902c62813a892387acb0e798c7fd504c'
tier: L1
related:
  - '[[2026-08-12-iva-art-69-dos-services-adr]]'
---

# `iva-art-69-dos-services` plan

## Description

## Steps

- [x] `S01` - Declare the twelve lettered items of LIVA art 69.Dos as a closed StrEnum, mirroring the art 20 sub-article discriminator the tree already carries. Document each member from the bundled consolidated text it is read out of, never from memory, and carry the two exclusions the statute writes into its own letters - the art 70.Uno.1 carve-out inside letter d, and the transport-and-container carve-out inside letter j; `src/cadrumo/domain/iva/_schema.py`.
- [x] `S02` - Split the outbound B2C branch on the declared item: a declared item with a third-country recipient is not-subject under art 69.Dos, and everything else stays taxed at the rate tier. The recipient test is third-country ONLY, because art 69.Dos states its own limit in the same sentence and excludes Canarias, Ceuta and Melilla though they sit outside the Comunidad. An undeclared item is not evidence of absence and must stay on the taxed branch; `src/cadrumo/domain/iva/_classification.py`.
- [x] `S03` - Follow the split through the rate-tier demand so the excepted branch is not asked for a tier it never uses, and add the registry grounding row for the new rule in the SAME change - the decision table and the place-of-supply table are held in parity in both directions, so a rule without its row cannot be committed separately; `src/cadrumo/domain/iva/_classification.py, src/cadrumo/_data/registry/aeat/iva/place_of_supply/2025.toml`.
- [x] `S04` - Gate the split with mutation proofs in both directions: every declared item reaching not-subject for a third-country recipient, the same items staying taxed for a recipient in Canarias or Ceuta y Melilla, an undeclared item staying taxed, and the B2B limb unmoved by any declared item. Assert per item across the whole enum rather than on a sample, so a member added later is covered without editing the file; `src/cadrumo/domain/iva/tests/`.
- [x] `S05` - Retract the electronically-supplied-services concern on the prior feature's records rather than leaving it standing. Art 70.Uno.4 locates e-services at the recipient only when the recipient is established in the TAI, art 70.Dos only ever pulls services INTO the TAI, and art 69.Dos names no e-services item - so the subject outcome for an outbound B2C e-service is correct. Correct the exec note and the ADR consequence that called it probably over-taxed; `.vault/`.

## Parallelization

## Verification
