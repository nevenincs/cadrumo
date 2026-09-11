---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:dac018106d00bf524f03a3eee212cf4ad77464f2bf0dabe1a76acded2caa3a55'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: S58 published-authority handoff review

## Scope

Review of W04.P19.S58: the published-authority artifact handoff, immutable consumer boundary, removal of retired IVA grounding-test coverage, and canonical validation gates. The immutable-mapping assertions correctly adapt the artifact tests to the current `FrozenMapping` contract. The generic fact-validation suite now exercises source-window refusal across every closed fact family, so deleting the retired IVA-specific compiler test does not remove that detector tooth. The known three invalid Modelo 222 authoring findings belong to the cross-domain gate and do not change this S58 assessment.

## Findings

### unresolved-iva-authority-lanes | high | Open typed-fact migrations leave operative raw legal authority paths

The live retirement ledger still records direct readers for IVA catalogue, place-of-supply, territorial scope, territorial carve-outs, and the IVA-local evidence verifier. The corresponding production modules still read raw IVA TOML and invoke IVA-local grounding. `migration_retirement_findings` accepts those paths only as named temporary holds while S81--S85 remain open; that is evidence of an intentionally incomplete ledger, not retirement-ledger closure. S58 therefore cannot establish its required sole-authority or zero-deletion-target condition.

## Recommendations

Complete the lossless typed fact migrations and remove the listed direct readers and IVA-local verifier in their owning steps. Then rerun the retirement gate without temporary holds and the packaged `bundled_authority()` proof before checking S58.
