---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S36'
related:
  - '[[2026-06-30-cli-persona-testimonials-plan]]'
---

# W06.P13.S36 Replay-Risk Review

Scope: final-message replay risk across current transcript and canonical
testimonial evidence.

## Description

Review existing real transcripts and canonical harnessed testimonial documents
for current under-declaration, data-loss, cross-profile, legal-evidence, or
live-read risks that need a W06 code-fixer dispatch.

RAG grounding:

- `uvx vaultspec-rag search "persona testimonial replay final messages calculation risk under declaration evidence" --type code`
- Targeted M100, M303, M200, and cross-profile code searches for the domains named
  by the reviewed testimonials.

## Outcome

No current campaign-owned product defect was found. S37 does not need a fixer
dispatch from this replay pass.

Classified:

- Critical historical under-declaration signals are already covered by W05 or
  current gates: M100 0171 aggregation, M100 relation diagnostics, M200 silent-zero
  guards and 00599 propagation, M303 wallet override/first-period handling, and
  cross-profile refusal tests.
- Legal-evidence and cross-period blocks remain expected refusal or safety-design
  behavior where local-only observations must not become official AEAT evidence.
- Artifact-only gaps remain under S34/S35, including Ana's no-export timebox and
  Taller Norte's historical compensation block that current first-period and
  established-activity tests cover.

Reviewed sources included `tmp/personas/_cpdefix-closeout-ledger.md`, the Ana,
Lucia, Nordic, and Taller transcripts, and canonical testimonial documents for
autonomo M130/M303, late filer, gestor multiclient, IVA cross-period, mixed income,
r2 autonomo, Renta full-year, and Sociedad 200.

S36 is complete without S37 dispatch.

## Notes

The researcher ran read-only file discovery and text searches plus code RAG. One
non-mutating `wc -l` attempt failed because `wc` is unavailable in this PowerShell
environment.
