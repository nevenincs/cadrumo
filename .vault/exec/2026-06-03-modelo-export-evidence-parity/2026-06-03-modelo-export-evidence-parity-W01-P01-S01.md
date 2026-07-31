---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-07-17'
body_hash: 'sha256:39b17843aaf0849b98a2404a0d78c7e5118ab4a521accebb4894f03b9e732f4d'
step_id: 'S01'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W01.P01.S01` step record

Scope: `W01.P01.S01` - LedgerFilingEvidence domain record.

## Description

- Add strict frozen `LedgerEvidenceRow`, `ManualFactBasisEntry`, and `LedgerFilingEvidence` records.
- Include tax facts, legal/source references, attachment ids, document-link ids, and purchase-evidence references on the contributing-row projection.
- Add domain tests for strict JSON roundtrip and frozen validation behavior.

## Outcome

The domain layer now has a typed bundled-evidence record pegged to `snapshot_fingerprint`, with direct unit coverage for persistence-friendly JSON roundtrip and immutability.

## Notes

Application capture, revision pegging, encrypted revision roundtrip, and no-silent-omission enforcement remain open in later W01 steps.
