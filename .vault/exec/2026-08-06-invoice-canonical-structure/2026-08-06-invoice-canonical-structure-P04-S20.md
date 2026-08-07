---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f647a41e3fe35b58b157a86174219af9222c9c7158578ce9be22058267f39555'
step_id: 'S20'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Retire InvoiceKindOption and type the CLI kind option directly on InvoiceKind, in one atomic explicit-path commit across all thirteen sites

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py`

## Description

- Verified the two enums declare identical members and values BEFORE sweeping, since a mismatch would have silently changed the CLI's accepted tokens.
- Retired the option class and typed every site directly on the domain enum.
- Removed the conversions that had become identities.
- Resolved the duplicate import the retirement exposed.
- Observed clean collection immediately before committing, and landed it as one atomic explicit-path commit.

## Outcome

**The CLI no longer carries a second declaration of a closed axis the domain already owns.**

The option class mirrored the domain enum exactly — same members, same lowercase values — so it added nothing except a place for the two to drift. It is now gone, with all thirteen sites typed directly on the domain enum.

**Token preservation was verified rather than assumed, and that check was the load-bearing one.** Both enums declare `ISSUED = "issued"` and `RECEIVED = "received"`, so click renders the same accepted set and every existing invocation parses identically. Had they differed, retiring the option would have silently changed what the CLI accepts — a breaking operator-facing change disguised as a cleanup. The conversions between the two became identities and were removed with it.

**The retirement exposed a duplication the option class was hiding, which is the more interesting result.** The evidence CLI imported the canonical enum from the domain AND the CLI-local option class from its sibling module — two names for one axis, live in the same file, and only visible once the two names collided. Removing the option leaves one import of one enum.

That is the outcome the Step exists for rather than a side effect of it: a duplicate declaration does not merely sit there, it lets consumers bind to whichever copy they reach first, and nothing reds while both agree.

## Verification

The relocation rule's mandated gate, observed immediately before the commit:

    uv run --no-sync pytest --collect-only -q src/cadrumo
    20512/24465 tests collected (3953 deselected) in 51.15s

Clean collection, no errors.

    uv run --no-sync pytest .../test_documented_command_conformance.py .../test_catalogue_invoice_lifecycle.py .../test_ledger_evidence_confirm_cli.py .../test_ledger_evidence_self_counterparty.py -m integration -q --no-header
    378 passed in 15.59s

    uv run --no-sync ruff check .../_ledger_business_invoice_cli.py .../_ledger_evidence_cli.py
    All checks passed!

The documented-command conformance gate is the one that would catch a changed accepted-token set, and it passes unchanged — which is the executable form of the token-preservation claim.

Landed as ONE atomic explicit-path commit carrying the definition removal and every consumer, subject-tagged for the retired symbol. No apidocs regeneration: this Step adds and removes no module, so the stub tree is untouched by it.

## Notes

The apidocs drift gate remains red, unchanged, for peer modules only. It was checked rather than assumed, and deliberately not regenerated: this Step changes no module boundary, so running the generator would have swept peer stubs into a relocation commit that must stay atomic and scoped.

A note on why this duplication survived so long: both declarations were *correct*. Neither was a bug, neither reddened a test, and each read as reasonable in its own file — the CLI one even carried a docstring explaining that it mirrors the domain enum so click can render the choices. A duplicate that documents itself as a duplicate is the hardest kind to notice, because the documentation makes it look considered rather than redundant.
