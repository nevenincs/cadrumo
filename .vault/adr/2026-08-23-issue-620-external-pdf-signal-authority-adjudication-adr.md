---
tags:
  - "#adr"
  - "#issue-620-external-pdf-signal"
date: '2026-08-23'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-authority-adjudication-research]]"
  - "[[2026-08-23-issue-620-external-pdf-signal-adr]]"
supersedes:
  - '2026-08-23-issue-620-external-pdf-signal-adr'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:23a4e0c23fd4bc99cd86bfd272b2eefdbc03ac437ec3f93dcaddc7901aa45a14'
---
# `issue-620-external-pdf-signal` adr: `authority adjudication` | (**status:** `accepted`)

## Problem Statement

The original issue decision admitted externally downloaded PDFs only as
unverified layout candidates. The completed authority investigation now proves
official-form lineage without authenticating the candidate bytes themselves.
A replacement decision is needed so the corpus preserves that signal and does
not imply current-registry agreement where the form is historical.

## Considerations

- The evidence for all ten files and their differing revision applicability is grounded in `2026-08-23-issue-620-external-pdf-signal-authority-adjudication-research`.
- Candidate-byte integrity, official-form derivation, and registry applicability answer different questions and can have different verdicts.
- The accepted registry authority flow remains stable and must constrain revision claims rather than being bypassed by PDF appearance.
- Tests must be deterministic and cannot depend on live AEAT or BOE availability.
- Checkout-only fixture placement and the ban on runtime authority remain stable constraints from the original issue decision.

## Considered options

**Retain one unverified flag.** Rejected because it discards the demonstrated
official-form lineage and gives no truthful way to distinguish current and
historical candidates.

**Promote each candidate to an official specimen.** Rejected because none of
the ten files is an exact official publication byte and every file identifies
itself as a non-valid FiscalBot example.

**Remove the candidates.** Rejected because their independent, digest-pinned
bytes remain useful adversarial parser inputs.

**Adjudicate three independent axes.** Accepted: identify the candidate as a
third-party sample, record verified derivation from a pinned official base, and
record its applicability to authored registry revisions separately.

## Constraints

- `third_party_sample` is an artifact-authenticity verdict and never means AEAT or BOE publication.
- `verified_official_base_derivative` requires a named official URL, digest, page mapping, and reproducible comparison summary.
- Derivative status never proves an exact direct-parent byte, populated values, filing validity, or redistribution rights.
- Registry applicability is one of current revision, historical authored revision, or historical layout without an applicable authored revision.
- A candidate may exercise production parsing code outside its applicable revision only when the test labels the run as adversarial parser behavior rather than form verification.
- Official comparison artifacts remain external authority anchors unless already stored for another accepted purpose; sidecars retain their URLs, digests, page mappings, and derived measurements so the focused suite remains offline.

## Implementation

Replace the single sidecar authority flag with typed artifact-authenticity,
official-base-derivation, and registry-applicability records. Each candidate
pins the official source digest and comparison method; paired overlays also pin
their render relationship. Contract tests validate the full vocabulary,
official-source evidence, and declared revision identifiers against the
committed registry. The cross-model outcome matrix selects the applicable
revision for M130, M131, and M303, and explicitly refuses current alignment for
the historical M036 and M349 layouts. Existing parser safety tests remain
checkout-only and make no runtime authority claim.

## Rationale

The three-axis contract is the only option that preserves every independently
proved fact without promoting a derivative to an official artifact. It also
makes the registry a tested participant in the verdict, addressing the central
failure of the original single-axis classification. The grounding in
`2026-08-23-issue-620-external-pdf-signal-authority-adjudication-research`
supports a positive derivation verdict for all ten files and different
applicability verdicts by modelo.

## Consequences

The corpus will provide a proper positive signal: ten verified official-base
derivatives, ten positively identified third-party artifacts, and explicit
current or historical applicability. Reviewers can distinguish what is known
from what remains impossible to claim. The schema and focused tests become more
verbose, and future candidates must supply official comparison evidence rather
than inheriting trust from a host or logo. M036 and M349 continue to test parser
robustness but cannot count as current-form verification; M303 cannot count for
2026.
