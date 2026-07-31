---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:d9c351b9de3428c732d7af9415a3643e5f07716af5224d1d5c3df00d287e80af'
step_id: 'S21'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden onboarding.md

## Scope

- `docs/how-to/onboarding.md`

## Description

- Author the net-new `onboarding.md` (the page was MISSING; this is the one genuine net-new step of the plan, wireframe-approved before authoring).
- Design it as a NARRATIVE JOURNEY MAP, not a second command walkthrough: `quickstart.md` already owns the concrete shortest command path, so onboarding orients a newcomer through the whole lifecycle and ROUTES to the deep guide at each stage rather than inlining command sequences (per aeat-documentation-workflow story-driven + cross-linking, avoiding duplication).
- Lead with the never-submit safety boundary (aeat prepares/checks/exports LOCAL files; the human files at the AEAT portal) - the load-bearing local-first, human-gated framing per aeat-safety-legal-gates - then the six-stage journey-at-a-glance and a pointer to Quickstart.
- Walk the six stages with one or two orienting sentences plus the cross-link each: Stage 1 profile-setup, Stage 2 import-bank-statements, Stage 3 classify-transactions, Stage 4 choose-modelo, Stage 5 filing-readiness + verification-reports, Stage 6 file-at-aeat + reconcile. Add a passphrase (S-PASS) and Spanish-runtime (S-LANG) "Before you begin", and a "Where to go next" pointing at the explanation/boundary pages, calendar, troubleshooting, and glossary.
- Register the page in the how-to `index.md` router (a "Get Started" card ahead of Quickstart) so it is reachable.

## Outcome

- `onboarding.md` authored as the journey-map orientation, with imperative stage headers, taxpayer-general terms (NIF/CIF/DNI/NIE), relative markdown links, no self-praise, and no inlined command sequences (it routes; the linked guides execute).
- Registered in `docs/how-to/index.md` under "How do I start this?".
- Gates: CLI conformance `test_documented_command_conformance.py -m integration` = 59 passed (the new page is scanned and carries no command claims, so nothing to drift); the Sphinx `-n -W` build result is recorded in the Notes.

## Notes

- No `aeat ...` command invocation is inlined in onboarding.md by design - it is a router - so there is nothing for the command-conformance gate to falsify beyond link integrity.
- This closes the `aeat-user-docs-hardening` plan at 32/32: 31 verify-closes of existing pages against the 2026-06-18 persona audit's findings (all resolved at HEAD) plus this one net-new orientation page.
