---
tags:
  - '#audit'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
  - "[[2026-07-13-docs-lifecycle-tutorials-adr]]"
---

# `docs-lifecycle-tutorials` audit: `campaign-close honesty review`

## Scope

Fresh-context honesty review at campaign close, per the mandated
campaign-close-honesty-review rule (mechanism 1: independent code-reviewer
dispatch). The reviewer received the campaign ADR, plan, research disposition
table, exec records, and the commit range, and audited: disposition-table
fidelity, link integrity, the "This page covers the ..." convention,
tutorial output-transcript honesty with live CLI spot checks, declarative-
vs-action gaps, and plan-closure integrity. Reviewer verdict: REVISION
REQUIRED - no critical findings; three items to action before structural
completeness.

## Findings

### gates-unrun-at-review-time | high | P05.S16 gates had not run when the review snapshot was taken

The plan's gate step was open with both gates unverified across a campaign
that authored six new pages and rewired every toctree. RESOLVED in the same
session: the documented-command conformance gate passed (62 passed), the
Sphinx nitpicky gate failed once on an inverted grid colon-nesting in the
new tutorials index, the nesting was fixed, and the re-run passed (12
passed). Closed as P05.S16 with its exec record.

### tutorial-figures-not-live-replayed | medium | Q2-Q4 and IVA carry figures narrated from the binding model, not a real multi-quarter run

The one literal output transcript in the IRPF tutorial was verified honest
(carried verbatim from the previously verified walkthrough), and no other
transcript was fabricated - but the cumulative-carry and credit-carry
behaviour beyond the first quarter is stated in prose from the live-verified
binding model rather than reproduced from an end-to-end sandbox run.
FORMALLY DEFERRED: tracked as open step P05.S19 (replay both lifecycle
tutorials against a sandbox profile and reconcile the narrated figures);
the campaign closes with this step named as the follow-up.

### stray-process-files-in-docs-root | medium | three project-management files shipped in the docs tree

`docs/ADRS.md` and the two `*KICKOFF-BRIEF.md` files violated the
docs-architecture ADR clause 3a (no project-management metadata in the docs
tree); the research flagged them twice without converting the flag into a
step. RESOLVED in the same session: provenance and reference checks run
(committed, unreferenced, not generator-owned), all three retired via
`git rm`. Closed as P05.S18 with its exec record.

### everything-else-verified-clean | low | all other audited categories passed

Disposition-table fidelity (all merges, the retirement, the new pages, the
trims, and the toctrees match the ratified table exactly); link integrity
(zero references to the six deleted pages; every spot-checked anchor
resolves); the "This page covers the ..." opening present on all 17 checked
pages; CLI-claim spot checks against the live surface all correct
(iva-wallet verb set and flags, the `0A` annual token, the `requires` verb,
the Modelo 130 binding names); the shared-persona/one-year tutorial claim
holds; every closed step S01-S15 has a matching exec record and no step was
falsely closed.

## Recommendations

- Execute P05.S19 (full-year sandbox replay of both tutorials) as the one
  open follow-up; until it runs, the tutorials' post-Q1 numeric narration
  rests on the live-verified binding model rather than a reproduced run.
- If a public ADR index is wanted after the `ADRS.md` retirement, generate
  it from `.vault/adr/` rather than hand-maintaining a docs-tree file.
- Pattern note for future docs campaigns: research findings that name
  concrete defects (the stray files) should be converted into plan steps at
  plan-authoring time, not left as flags - both stray-file flags survived
  two documents without becoming actionable until the honesty review.
