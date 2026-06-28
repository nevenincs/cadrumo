---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W31.P158'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W31.P158`

De-shim / de-stub phase. The ADR explicitly rejects operator-facing
manual-fetch behaviour because PDF + manifest writes are not
bucket-scoped or event-traceable. The boundary test
`test_no_aeat_normatives_or_manual_fetch_verb_under_app_registry`
enforces that no `citations fetch` or `manuals fetch` verb is
registered under the read-only `aeat app registry` surface.

## Description

The boundary test scans every `.py` file under
`src/aeat/entrypoints/cli/`, skips test files (which legitimately
quote the forbidden patterns as search strings in their own
boundary scans), and asserts none of the four forbidden command
registrations appears:

- `@citations_app.command("fetch"`
- `@citations_app.command('fetch'`
- `@manuals_app.command("fetch"`
- `@manuals_app.command('fetch'`

The wave introduces no stubs and no compat shims; the de-stub limb
is vacuously satisfied. The boundary test is the forward guard
that prevents a future agent from quietly adding a fetch verb
under the read-only surface.

Closed plan rows: `W31.P158.S0943`, `W31.P158.S0944`,
`W31.P158.S0945`, `W31.P158.S0946`, `W31.P158.S0947`,
`W31.P158.S0948`.

## Tests

Boundary test passes as part of the 11-test
`test_registry_corpus.py` suite.
