---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-05-27'
step_id: S386
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-source-jurisdiction-axis-adr]]"
---

# `cross-domain-continuity` `W12.P65.S386`

Author the consolidating ADR for the source_jurisdiction axis. Final leaf of the six-leaf decomposition; closes the design record for the axis end-to-end.

Commit: `2a9385f4d`

- Created: `.vault/adr/2026-05-27-source-jurisdiction-axis-adr.md`

## Description

ADR scaffolded via `vaultspec-core vault add adr --feature source-jurisdiction-axis`. Body authored under the six canonical sections of the ADR template:

- **Problem Statement** — anchors LIRPF Art. 8 universal-base, TRLIRNR Art. 2/10/25 non-resident scope, LIRPF Art. 93.5 Beckham segregation. Documents the four-persona discovery surface (Pedro intracom / Olivia UK landlord / Felipe Argentina pensioner / Khadija Morocco worker) and explains why the persona-driven discovery posture substitutes for a formal research artefact under the cross-domain-continuity campaign.
- **Considerations** — ISO 3166-1 alpha-2 vs free-form country string; CLI-create vs aggregation-boundary gating; provenance-only vs filtering at the read surface; backward compatibility with pre-axis encrypted catalogues.
- **Constraints** — envelope schema stays at v1 (additive JSON-compatible field); refusal text via `tr()` per G3; model-level validator is stateless and intrinsic (no profile coupling); G6 anti-tautology test discipline derives expectations from regulatory anchors.
- **Implementation** — six-leaf chain laid out with commit SHAs for each Step (S381 → S386). Truth table for the profile-conditional resolver written in prose. Aggregation propagation rule (no filtering at resident-IRPF surface) recorded.
- **Rationale** — three-reason argument for CLI-create-boundary gating: (a) error surfaces before encrypted-catalogue persistence; (b) operator-facing refusal rather than deferred per-modelo issue; (c) single-point-of-enforcement vs N-fold per-modelo duplication. Truth-table regulatory anchoring (Art. 8 / 93.5 / 2 / 10). Anti-tautology mutant-test rationale.
- **Consequences** — deferred S385b per-row gating at IRNR M210 and Beckham M151 engines (blocked by those engines being authored); non-resident test-fixture discipline learnings from the S384 three-bug smoke sequence (projection wire → descriptor key → IRNR axis tuple → UE-country schema workaround); separate follow-up filed for the `representante_fiscal_nombre` schema-catalogue mismatch.

## Verification

- `vault check all` ran cleanly on the new ADR (the only flag is the expected "no research document" warning, addressed in-body via the persona-substrate note).
- The H1 status line explicitly reads `status: accepted` (body text, not frontmatter), aligning with the campaign convention.
- Body-only edits; YAML frontmatter (tags, date, related) untouched per the cli rule.

## Gate evidence

- G1 no naked env reads: unchanged; ADR-only commit.
- G2 typed pydantic at boundary: documented at the model level in the ADR Constraints section.
- G3 user messages via tr(): documented in the Constraints section as a project-wide standing rule.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: ADR documents the no-shims posture for the axis (single-source validator, profile-aware logic isolated to the resolver helper).
- G6 no tautological tests: documented as a project-wide standing rule; the ADR Rationale section enumerates the kill-the-mutant tests landed across S381-S385.

## References

- ADR: source-jurisdiction-axis-adr (this document is the meta-commit that ships it)
- Sibling Steps: S381 (model), S382 (encrypted roundtrip), S383 (CLI), S384 (resolver), S385 (aggregation provenance).
- Deferred follow-ups recorded in the ADR Consequences: S385b per-row gating (task #62), `representante_fiscal_nombre` schema gap (task #261 in coder2 view / closed as #58 in PM view).
- Surface: `.vault/adr/2026-05-27-source-jurisdiction-axis-adr.md`.
