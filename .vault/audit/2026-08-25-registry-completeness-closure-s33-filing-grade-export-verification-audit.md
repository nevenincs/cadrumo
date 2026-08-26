---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:2fd6406b19448e77b483fd5d43a4b7eef1c3ea37db5da31de244772428778b9f'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` audit: `S33 corpus-wide filing-grade export verification`

## Scope

Current-tree revalidation of `W03.P05.S33` through the one validated registry authority, law-selected filing snapshots, filing-export closure composer, canonical live proof authority, producer-owner map, and the existing corpus-wide emitted-byte acceptance gate. This audit does not author layouts, drafts, producer snapshots, semantic maps, render profiles, output bytes, or official offset claims.

## Findings

### s33-zero-canonical-live-proof | high | Every filing-grade revision lacks the only admissible generation-and-emission proof

The dynamic authority inventory derives 66 filing-grade revisions, with no maintained modelo list or representative year. For every member, every declared law-selection coordinate selected that exact revision; every selected revision carried a nonempty layout set; and each layout-authority source reverified at its recorded bytes.

Fifty-eight revisions cite 662 producer keys. Every cited key belongs to the canonical shared snapshot owner; the remaining eight revisions cite no producer key. This proves current layout selection and owner-map completeness only. It does not supply a source-owned `ModeloDraft`, `FilingProducerSnapshot`, acceptance payload digest/extent, or official-offset probe.

`CANONICAL_LIVE_FILING_EXPORT_PROOF_ENTRIES` is empty. The one canonical proof authority consequently supplies no production draft or probe for any of the 66 revisions, and the closure composer returns 66 `missing_evidence` refusals owned by `aeat-export-fragment-generator-authority:production-emission-proof`. No filing revision has an emitted-byte proof and no subset is genuinely authorable from the current authoritative material. Test fixtures and declared layouts are not substitutes for that source-owned proof.

### s33-stale-m353-specific-assertion | medium | The existing narrow M353 gap witness no longer describes the current authority

The existing corpus-wide integration module was run against current HEAD. Its dynamic full-denominator and empty-live-proof cases passed, but the M353-specific historical-gap witness failed with `StopIteration`: it expected a `filing-layout` refusal that the current law-selected M353 revisions no longer produce. The current dynamic inventory instead reaches the verified-layout stage for every filing revision before the zero-entry production-emission refusal.

This is an honest verifier-maintenance item, not evidence that Modelo 353 or another model is emitted. It must be recast dynamically by its test owner before this step can claim a green full gate.

### s33-m353-dynamic-witness-followup | resolved | Both M353 eras reach the current production-emission refusal

The integration witness now derives each M353 revision's non-overlapping law-selection coordinates and requires both limbs to retain the canonical `production-emission-proof` refusal. A current sequential rerun passes all three integration cases. This resolves only the stale verifier finding; the zero-live-proof high finding remains open and no emitted-byte success is inferred.

## Recommendations

- Keep `S33` open. Do not infer payload bytes, probes, or a success claim from the 66 layout/owner-ready rows.
- A Sol-level export-authority implementation must enroll each admissible revision only after exact official semantics, a source-owned production draft and producer snapshot, generator provenance, a successful `export_draft` payload, and non-overlapping official-offset acceptance are independently available.
- Correct the stale modelo-specific integration witness separately, retaining a denominator-derived selection assertion rather than replacing it with a representative-year or count assertion.

## Verification receipt

- Read-only dynamic authority inventory: 66 filing revisions; 66 exact selections; 66 nonempty verified layout sets; 58 revisions / 662 declared shared-snapshot producer keys; 8 revisions with no producer key; 0 canonical live proof entries; 66 `production-emission-proof` refusals.
- Historical run: 2 passed, 1 failed in 159.82 seconds on the stale M353 expectation.
- Current run: 3 passed in 111.91 seconds after the dynamic M353 correction; all 66 production-emission refusals remain.
