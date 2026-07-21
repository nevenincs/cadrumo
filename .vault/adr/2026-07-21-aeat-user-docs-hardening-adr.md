---
tags:
  - '#adr'
  - '#aeat-user-docs-hardening'
date: '2026-07-21'
modified: '2026-07-21'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
  - "[[2026-06-18-aeat-user-docs-hardening-audit]]"
---

# `aeat-user-docs-hardening` adr: `persona-verified imperative how-to hardening (retroactive record)` | (**status:** `accepted`)

## Problem Statement

**This is a retroactive record**, authored 2026-07-21 to close a vault lifecycle
gap: the `aeat-user-docs-hardening` campaign (plan dated 2026-06-16, thirty-two
execution records closed by 2026-07-04) ran to completion with a plan, a rolling
audit, and per-page execution evidence, but the decision it implemented was
never captured as an ADR. This record states that decision as it was actually
made and executed; it introduces no new choice.

The problem the campaign addressed: the how-to corpus under `docs/how-to/` made
claims about the application that no process verified against the running CLI.
Prose could overstate capability (the audit's finding that the authentication
page presented all five auth providers as usable when only some were available),
drift from live command syntax, or explain in developer vocabulary what a
taxpayer-facing reader needs as plain instruction. Editorial review alone cannot
catch documentation-versus-application divergence, because the reviewer trusts
the page.

## Considerations

- The conformance gates (documented-command conformance, Sphinx nitpicky build)
  verify that cited commands exist and links resolve — not that a page's claims
  about behaviour are true. Truthfulness needs execution.
- Parallel per-page verification requires state isolation: personas sharing an
  active profile, master key, or ledger would corrupt each other's runs.
- The project's user-docs style mandate (simplistic, singular, imperative
  instruction steps — codified as the `aeat-user-docs-hardening` project rule)
  was in force and is the editorial standard each hardened page converges on.
- The rolling audit (2026-06-18) is the campaign's findings ledger; the plan's
  thirty-two `Harden <page>` steps are the closure vehicle, one per how-to page.

## Considered options

1. Editorial rewrite pass without execution: rejected — cannot detect
   doc-versus-app divergence; the campaign's confirmed findings (overstated
   provider availability, stale command hints) are exactly the class it misses.
2. Rely on the automated conformance gates alone: rejected — they gate command
   existence and link integrity, not the truth of behavioural claims.
3. Persona-driven verify-close (accepted): dispatch one naive-user persona per
   documentation page; the persona reads only its page, executes the documented
   commands literally through the real CLI in an isolated state root, and
   reports divergence; the coordinator confirms every finding against HEAD
   before recording it in the rolling audit; a per-page plan step then hardens
   the page and verify-closes against the audit findings.

## Constraints

- Personas run in isolated state roots (per-persona local-storage root plus
  sibling `var/*` dirs) so parallel runs never collide on profile, master key,
  ledger, or drafts.
- The coordinator independently verifies backend calculation and factual
  correctness before a finding is recorded; persona testimony alone is
  inventory, not gospel.
- Hardened prose follows the imperative instruction-step style rule and the
  documented-command conformance gate; neither is weakened to make a page pass.

## Implementation

One naive-user persona per page under `docs/` (how-to, quickstart, tutorials,
explanation), each executing its page literally against the real CLI; confirmed
findings accumulate in the rolling audit as the durable index; the plan carries
one `Harden <page>` step per how-to page (S01–S32), each closed by rewriting
the page to resolve its confirmed findings and verifying resolution at HEAD.
Persona testimonials persist under `.agents/testimonials/`. Two objectives ride
the same pass: stress the docs (clarity, completeness, correctness, links) and
verify the application delivers what each page promises — product gaps found by
personas are logged as findings, not papered over with confident prose.

## Rationale

Literal execution by a reader-shaped agent is the only reviewer that fails the
way a real user fails: it cannot fill gaps from context it does not have, so
every divergence between page and application surfaces as a concrete,
reproducible finding. Confirming findings against HEAD before recording keeps
the audit honest in a fast-landing shared worktree, and binding each page to
one closure step makes campaign completion checkable rather than declared.

## Consequences

- Every how-to page carries execution-verified prose; the campaign closed all
  thirty-two pages with per-page execution records.
- The method is reusable: the rolling-audit-plus-verify-close shape reappears
  in later documentation campaigns.
- Costs are real: one persona dispatch plus coordinator confirmation per page,
  and isolated state roots to maintain.
- Retroactive honesty: because this record postdates the work, it cannot have
  steered it; its value is that the vault now names the decision the evidence
  trail already proves.
