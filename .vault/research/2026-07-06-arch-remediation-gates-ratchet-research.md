---
tags:
  - '#research'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:d35bf56d4eb1b3bc9c3c9e3814f64652720b4d2bdd761e7c49828c1c0d655bdb'
related:
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-02-arch-remediation-gates-ratchet-plan]]"
  - "[[2026-07-06-arch-remediation-program-audit]]"
---

# `arch-remediation-gates-ratchet` research: `same-feature authority warning closeout grounding`

This research grounds the remaining vault lifecycle warning for
`arch-remediation-gates-ratchet`: the feature has a complete plan and exec
ledger, but no same-feature ADR. The technical authority already lives in the
accepted architecture-remediation program ADR; the question here is whether a
narrow same-feature curation ADR would improve vault graph health without
changing the ratchet architecture.

## Findings

### Current warning

`vaultspec-core vault check features -f arch-remediation-gates-ratchet --json`
reports one warning: the feature has a plan but no ADR. The diagnostic is
non-fixable and suggests adding an ADR for the feature.

The warning is metadata/governance only. It is not a failing code gate. The
current Wave 4 ratchet bundle passed 38 tests, as recorded in
`2026-07-06-arch-remediation-program-audit`.

### Existing authority

The accepted program ADR is the current decision authority. Its Wave 0
implementation section names the gates-ratchet track explicitly: repair the
`.importlinter` ledger, purge dead entries, flip unmatched alerting to error,
replace the application-to-adapters wildcard with pinned edges, and land
count-ratchet gates. It also states the program-wide ratchet policy: each wave
lands enforcement in the same change as remediation, and a ratchet may only be
loosened by an accepted ADR.

The gates-ratchet plan implements that Wave 0 instruction. Its description ties
the plan to deferral-register items D1 and D8 from the architecture review
audit, identifies `.importlinter` as the measurement instrument, and defines
the three phases: ledger hygiene, wildcard-to-pinned-edges, and ratchet gates.
Current `vaultspec-core vault plan status` reports that plan as 12 of 12 steps
complete.

### Precedent

Semantic vault search found existing curation ADRs with the title pattern
`warning closeout authority alignment`. Those records do not introduce runtime
behavior; they provide a same-feature decision node when a feature already has
plans or exec records but lacks local ADR authority. Their paired research
records use the corresponding `warning closeout research grounding` pattern and
state that the artifact exists to prevent future semantic search and developer
briefings from treating execution evidence as orphaned context.

The gates-ratchet case is similar but not identical. Unlike some older warning
closeouts, this feature already has a strong parent ADR. A same-feature ADR
would therefore need to be explicitly curation-only: it should anchor the
completed Wave 0 plan for vault health and discovery, not supersede the program
ADR or alter ratchet ceilings.

### Options

Option A: leave the warning documented only in the program audit. This avoids a
new decision artifact but keeps `vault check features` warning for the
gates-ratchet feature and leaves future agents to rediscover that the program
ADR is the parent authority.

Option B: add a second feature tag to the program ADR. Rejected. The vault
frontmatter checks already rejected duplicate feature-tag shape in this area,
and hand-tagging the parent ADR to satisfy a same-feature warning would blur
feature ownership.

Option C: create a narrow same-feature curation ADR after approval. Preferred.
The ADR should say that the accepted program ADR remains the architectural
authority, that the existing gates-ratchet plan is the approved execution ledger
for Wave 0 instruments, and that no code, tests, registry data, or ratchet
ceilings change. Its purpose would be vault graph health and semantic search
alignment only.

### Recommendation

Proceed to a same-feature curation ADR only after explicit user approval under
the ADR workflow. The recommended decision is: accept a narrow
`arch-remediation-gates-ratchet` authority-alignment ADR that preserves the
program ADR as the governing parent and records no new implementation mandate.

Do not use this research to justify code changes, ratchet rebaselining, or new
binding/source/resolver conventions. The current code gate is already green;
the remaining issue is lifecycle metadata.
