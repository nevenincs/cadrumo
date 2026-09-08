---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:8b39f8be466bc7554a945efe1900b4df061b89596001804d108b6e3acd680441'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S199]]"
  - "[[2026-08-15-profile-password-custody-per-profile-recovery-mnemonic-adr]]"
---

# `reachability-burndown` audit: `S199 reverse mnemonic decoder withdrawal review`

## Scope

Independent bounded review of W05.P12.S199: the accepted recovery-mnemonic ADR amendment, recovery-key implementation and inverse-only test deletion, retained presentation authority, cadence entry, and Step Record evidence.

## Findings

No findings.

The amended accepted ADR now matches the live one-way custody model: production generates a wipeable `RecoveryKey`, canonically encodes its entropy as a 24-word BIP-39 mnemonic, presents and verifies exact possession, and later treats the phrase only as opaque KDF/proof input. The removed `decode_mnemonic` and reverse word-index table had no production consumer. Their inverse-only tests were replaced with the canonical BIP-39 zero-entropy vector, which independently fixes encoder output instead of allowing encoder and decoder to agree on the same defect.

`RecoveryKey`, `generate_recovery_key`, `encode_mnemonic`, the canonical wordlist, creation handoff, presentation controls, artifact recovery proof, wrong-mnemonic refusal, and post-handoff zeroisation remain live. The separate presentation ADR remains consistent: it requires exact phrase transport and verification, not entropy reconstruction or a general decoder.

The Step Record gives exact changed paths and exact Ruff, 38-test focused, residue, metastate, reachability, and vault-check commands. The vault-wide failure is correctly classified as unrelated: it reports pre-existing annotation, Markdown, schema, and historical-document findings and no diagnostic against the amended ADR.

## Recommendations

Approve W05.P12.S199. No code, ADR, or Step Record correction is required.
