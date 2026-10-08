---
tags:
  - '#adr'
  - '#censal-surface-parser'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:affdf8e9016f41bceeb4d5f4b43b025bacc5ff744dec73a49a3c635d8afdf0b3'
related:
  - "[[2026-10-03-censal-surface-parser-research]]"
  - "[[2026-07-25-censal-profile-autofill-adr]]"
---

# `censal-surface-parser` adr: complete semantic census observations | (**status:** `accepted`)

## Problem Statement

The current observation loses three reachable census consultations. The live evidence in `2026-10-03-censal-surface-parser-research` invalidates the historical unavailability conclusion.

## Considerations

The operator explicitly requested all four consultations, own-name Cl@ve Movil, and resilient parsing before implementation on 2026-10-03. This authorization covers the additive observation contract and consultation navigation below; it does not authorize guessed tax interpretation or remote mutations.

## Considered options

Fixed layout offsets are rejected because reordering can silently misassign tax facts. A closed field whitelist alone is rejected because new fields disappear. Semantic records with retained labels, casilla identifiers and unresolved values are chosen, with explicit refusal when meaningful association cannot be established.

## Constraints

Retain the existing encrypted observation and reviewed adoption boundaries. All navigation remains consultation-only and own-name. Never drive modification controls. Never infer a negative fact from a missing cell or missing section. Taxpayer data must not enter fixtures, logs or records. Previously stored identity-only observations remain identifiable by absent consultation evidence, not retroactively treated as complete.

The historical record `2026-07-25-censal-profile-autofill-adr` remains authoritative for custody, identity alignment and reviewed adoption. Its D3 no-form-driving restriction is refined for the three observed read-only consultation controls: their existing form handoffs and popup targets may be driven under exact route/action guards. Its historical assertion that the subsidiary routes are unavailable is reopened by this session's rendered evidence; no historical text is erased. This does not change the certificate-specific deferred regime interpretation in `2026-08-08-censo-regimen-adoption-adr`.

## Implementation

We will extend the application-owned observation with immutable self-describing consultation sections and rows, including original field labels, casilla identifiers, rendered values and source routes. Header and label relationships drive parsing; unknown content is retained or explicitly refused. The existing identity/address projection stays the adoption input, while complete subsidiary evidence travels with the same encrypted reviewed observation. Tax interpretation and profile-field mappings require explicit grounding, independently of extraction.

## Rationale

Semantic observations preserve AEAT's statement through layout changes without inventing meanings for unfamiliar fields. The live map supports exact consultation handoffs; accepting broad form submission is unnecessary.

## Consequences

Complete census evidence becomes available to existing pull custody. Changes that destroy semantic relationships fail visibly. New regime-to-profile adoption rules are not implied by capture. Acceptance records the user's current requested scope, not completion.
