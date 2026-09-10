---
tags:
  - '#adr'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:21dae8e7c8525e3c1d72748fd9bd36bfd29b882dce6ed5a80f9420e495facc02'
related:
  - '[[2026-09-10-registry-temporal-coverage-corpus-tier-enforcement-research]]'
  - '[[2026-09-10-corpus-evidence-integrity-hand-shaped-corpus-text-research]]'
---
# `registry-temporal-coverage` adr: `corpus tier enforcement` | (**status:** accepted)

## Problem Statement

Normative-corpus citations need an authority check that distinguishes BOE-derived text from hand-shaped text. The initial proposal to require `corpus_tier` for every normative citation would classify a file's scope, but it would not catch the M037-style hand-shaped provision. This amendment corrects the mechanism while retaining the accepted concern.

## Considerations

- `corpus_tier` and provenance answer different questions: excerpt completeness and text origin, respectively.
- Provenance belongs to a corpus file, which can serve many citations; per-citation declaration would duplicate and self-certify the same fact.
- Filing-grade evidence must fail closed on unattributed text, while advisory use must remain visibly non-filing rather than silently erased.

## Considered options

- Mandate `corpus_tier` on all normative citations. Rejected: it correctly accepts a hand-shaped file presented as a provision excerpt, so it does not protect the defect at issue.
- Add provenance as a citation field. Rejected: it duplicates a file-level fact and trusts an author assertion about authorable text.
- Derive provenance from each normative corpus file during validation and bind evidence tier to it. Accepted: it evaluates the bytes once, has no author opt-out, and preserves the authority distinction through the resolved registry.

## Constraints

- Classification must use bundled corpus evidence and standard-library processing only; registry validation remains local and deterministic.
- The classification must distinguish attested, presumptive, and authored text without presenting the presumptive signal as proof.
- Before refusal is enabled, cited authored files claiming filing-grade authority must be re-grounded against official BOE material or explicitly downgraded.
- `corpus_tier` remains a separate, two-valued verified contract; no third tier is introduced.

## Implementation

Derive a three-state provenance classification for every file under `corpus/normatives/` during the canonical registry-validation path. Accept `legal_authority` only from BOE-attested text; permit a narrowly reviewed, per-file exception for BOE-presumptive text; refuse authored text as filing authority while retaining an explicit advisory path. Re-ground the identified cited authored files, separate the editorial gloss from source text, add defect fixtures that prove the detector refuses, and correct the stale `corpus_tier` coverage docstring.

## Rationale

This amendment selects the only measured option that changes the M037-shaped failure state. It derives the property that matters from the source bytes instead of recasting a completeness field as provenance, while keeping the existing tier contract meaningful and independently checked. The grounding is recorded in `2026-09-10-corpus-evidence-integrity-hand-shaped-corpus-text-research` and the amended `2026-09-10-registry-temporal-coverage-corpus-tier-enforcement-research`.

## Consequences

Filing-grade citations gain a real provenance boundary, and the registry makes advisory use of authored text explicit rather than silently filing-grade. The cost is a bounded re-grounding effort, a reviewable exception list for the presumptive band, and a validation-time corpus pass. The prior broad mandatory-tier migration is not pursued because it would add declarations without detecting the motivating hazard.
