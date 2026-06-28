---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-28
modified: '2026-05-28'
step_id: S386b
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-source-jurisdiction-axis-adr]]"
---

# `cross-domain-continuity` `W12.P65.S386b` (ADR frontmatter hygiene)

Hygiene pass on the source-jurisdiction-axis ADR shipped at S386 (2a9385f4d): wire the `related:` frontmatter field with the three authorising-doc wiki-links that were intentionally left out of the original commit per the no-hand-edit-frontmatter rule.

Commit: `27770c166`

- Modified: `.vault/adr/2026-05-27-source-jurisdiction-axis-adr.md`

## Description

The S386 ADR was authored body-only with frontmatter left at the vault-CLI scaffold default (`related: []`). The vault check on the original commit flagged the empty related field as expected workflow output, with the agreement that the wiki-links would be wired in a separate hygiene pass via the appropriate CLI surface.

This commit lands that hygiene pass. The ADR's `related:` field now carries three wiki-links:

- `[[2026-05-26-cross-domain-continuity-plan]]` — the L4 epic plan that authorises the entire source_jurisdiction axis decomposition (S381 through S386).
- `[[2026-05-27-m210-irnr-full-engine-adr]]` — the IRNR Phase 1 / Phase 2 split ADR that the W02 deferred-work wave (S385b) builds on.
- `[[2026-05-27-dsl-conditional-predicate-adr]]` — the DSL conditional-predicate ADR that the S398 rollback memo cites as the operator-design authority. The cross-reference is relevant here because the source-jurisdiction-axis ADR's Consequences section names the predicate-vs-classifier decision as deferred work; the dsl-conditional-predicate ADR governs the operator semantics that would be used if a future predicate-based gating shape lands.

Body text untouched in this commit; only the frontmatter `related:` array changed.

## Verification

- ADR frontmatter renders cleanly under the vault graph inspector; all three wiki-links resolve to existing documents.
- `vault check all` no longer flags the empty related field on this ADR (the campaign-wide cross-document drift is unrelated).

## Gate evidence

- G1 no naked env reads: unchanged; frontmatter-only commit.
- G2 typed pydantic at boundary: N/A; vault metadata only.
- G3 user messages via tr(): N/A.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: pure hygiene, no compatibility scaffolding.
- G6 no tautological tests: N/A; no tests touched.

## References

- Parent: source-jurisdiction-axis-adr at S386 (2a9385f4d).
- Cross-domain-continuity plan: the epic the ADR is bound to.
- m210-irnr-full-engine-adr: the Phase 1 / Phase 2 split that the ADR's Consequences section defers per-row gating to.
- dsl-conditional-predicate-adr: the operator-semantics authority for the deferred predicate-vs-classifier decision (now answered by the 2026-05-28 research memo at `.vault/research/2026-05-28-source-jurisdiction-axis-research.md`).
