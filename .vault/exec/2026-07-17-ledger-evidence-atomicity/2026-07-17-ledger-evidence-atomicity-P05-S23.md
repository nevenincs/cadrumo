---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S23'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Close the code-review findings on the remediation itself by promoting the one-sided link direction to a core enum consumed by the domain record and the operator payload, carrying typed rows into the notice builder instead of serialised mappings, and cross-linking the concrete repository parameters in the linking docstring, gated on the docstring core-struct module returning green

## Scope

- `src/cadrumo/core/_invoice_link.py`
- `src/cadrumo/domain/invoices/_service.py`
- `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`
- `src/cadrumo/application/invoices/_linking.py`

## Description

- Declare the one-sided link direction as a closed enum in the innermost core ring, replacing the inline two-token literal the domain record carried, so one taxonomy serves the domain, the operator payload, and the tests.
- Consume the enum in the domain consistency record and at both construction sites, and re-point the four test modules that asserted the raw tokens at enum members.
- Type the operator payload's direction field as the same enum instead of a bare string, and project typed payload rows at the check verb rather than serialised mappings.
- Take the typed consistency rows into the notice builder instead of a mapping bag, so identifiers and the closed axis stay typed up to the envelope.
- Add an Args section to the linking writer's docstring cross-linking both concrete repository parameters, which the core-struct docstring gate requires once the parameters name anchor types.

## Outcome

The closed direction axis is now typed from the domain record through to the operator envelope, and the docstring core-struct module is green again.

Strict payload validation caught a real defect during this step rather than after it: projecting the rows through a JSON dump produced a bare string for the enum field, which the strict model refused, so the verb exited non-zero. The fix was to construct the typed payload rows directly. Had the payload field stayed a bare string, the same dump would have passed silently and the downgrade would have shipped.

## Notes

Three findings arrived from review after the earlier Steps had closed, all on the remediation rather than the campaign's original scope. They are tracked here as one Step instead of reopening closed records.

The docstring gate red was mine and self-inflicted: narrowing the two parameters from the domain protocols to the concrete adapters made them anchor types, which obliges the function docstring to cross-link them. A pre-existing method role naming the same class does not satisfy the gate, because the role regex captures only the final path segment.

The core facade and its generated API stub both carried a concurrent campaign's uncommitted additions. Rather than commit their work under this change, both files were staged as HEAD-anchored own-edits-only patches through the index, leaving their working-tree state untouched, and the staged set was verified to carry none of their markers before the commit.

That protected the peer's work but caused a fleet-wide outage, and the sequencing lesson is the durable one. The index was staged BEFORE the same lines were mirrored into the working tree, so the tree spent a window with the enum's consumer already switched over and the facade export absent. The core facade is reached transitively by every CLI surface, so every command died at the terminal boundary and every subprocess-spawning test in the repository went red for a reason unrelated to itself; three agents reported it and at least two re-attributed failures away from their own work before it was traced here. The formatter then re-sorted the new import in the working tree, desynchronising it from the staged version and forcing an incremental re-stage that widened the window further.

The correction is ordering, not technique: apply the edit to the working tree FIRST and stage the own-only patch SECOND. The technique is right and remains the way to avoid capturing a peer's uncommitted work, but it is most needed on exactly the contended, widely-imported files where an unimportable window is most expensive, so the order matters more there than anywhere else. A one-second import smoke check after any structural edit to a widely-reached module is the cheap guard, and a genuinely long unimportable window should be announced to the fleet in advance rather than discovered.
