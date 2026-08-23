---
tags:
  - "#adr"
  - "#issue-620-external-pdf-signal"
date: '2026-08-23'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-research]]"
  - "[[2026-07-26-declaracion-real-render-verification-adr]]"
  - "[[2026-08-03-declaracion-real-render-verification-specimen-corpus-distribution-research]]"
  - "[[2026-06-01-verification-fixture-roles-adr]]"
  - "[[2026-08-23-issue-620-external-pdf-signal-authority-adjudication-research]]"
superseded_by: '2026-08-23-issue-620-external-pdf-signal-authority-adjudication-adr'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:468b3c753923ba253fcfe8071d88e88ddd307b59b4eafba3b89832ec38f2a095'
---
# `issue-620-external-pdf-signal` adr: `third-party-hosted PDFs as adversarial external layout evidence` | (**status:** `superseded`)

## Problem Statement

The accepted real-render decision requires external document evidence while refusing unproved verification claims. The new candidate PDFs need a classification that permits parser testing without promoting third-party hosting or metadata into AEAT authority. The grounding is `2026-08-23-issue-620-external-pdf-signal-research`.

## Considerations

- External bytes can exercise parser token and geometry behavior independently of repository generators.
- Authorship, official publication and populated numeric values are separate claims and remain unproved.
- The accepted parent ADR is stable and already requires evidence gaps to remain visible.
- Checkout-only placement follows the related specimen-corpus distribution research.

## Considered options

**Classify the candidates as real AEAT specimens.** Rejected because the source chain and metadata do not authenticate authorship.

**Reject the candidates entirely.** Rejected because it discards independent blank-layout behavior that can falsify parser assumptions.

**Classify them as unverified external layout candidates.** Accepted. Assert only reproducible physical properties and parser outcomes; retain authority and populated-value gaps explicitly.

## Constraints

- Metadata, logos, titles, filenames and hosting-page descriptions never satisfy authority provenance by themselves.
- A blank candidate cannot ground populated-value placement or calculation correctness.
- An unavailable download remains an explicit matrix result rather than being silently omitted.
- Candidate bytes are checkout-time test inputs, never runtime authority or registry source data.
- Redistribution rights are not decided here and must not be inferred from availability.

## Implementation

Each candidate is stored with a strict typed sidecar recording its retrieval locator, digest and measured PDF properties. A physical-byte gate checks the sidecar against the bytes and rejects authority claims. Parser tests use blank candidates to assert printed-box discovery and absence of fabricated amounts. A cross-model matrix records supported, unsupported and unavailable outcomes. Registry evidence fields change only where the measured result proves the existing claim is overstated.

## Rationale

The accepted option is the only one that preserves both useful independent parser signal and evidence honesty. It follows D3 of the parent real-render ADR without pretending that externality equals authority.

## Consequences

The parser gains adversarial blank-layout coverage across several modelos, and future source candidates have a falsifiable admission contract. Reports become more explicit because unsupported and unavailable outcomes cannot vanish. The cost is a deliberately qualified evidence vocabulary: these candidates cannot enrol a modelo under the parent ADR's real-or-facsimile requirement and cannot close populated-value verification. A later authenticated specimen may supersede an individual candidate's evidence role without changing this classification boundary.
