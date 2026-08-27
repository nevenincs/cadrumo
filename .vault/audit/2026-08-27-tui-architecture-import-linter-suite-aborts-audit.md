---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:52132755a5ff1868b545d0d1aacee502e211840d8e866411d67edae0ae896e37'
related: []
---

# `tui-architecture` audit: `the import-linter suite aborts, hiding five broken contracts`

## Scope

## Findings

## Recommendations

## Finding

`uv run --no-sync lint-imports` does not run. It aborts with:

    Modules have shared descendants.

This reproduces at CLEAN HEAD (`git archive HEAD` extraction), so it is not a
working-tree artefact. The architecture contracts are therefore enforcing
nothing, and have not been for as long as the abort has existed.

## Which contract aborts, and what is behind it

The run dies while checking the eighth contract,
`tui-feature-independence` ("TUI feature implementations share components
rather than each other"), whose `modules` are four sibling `**` expressions
over `tui.operations`, `tui.profile`, `tui.secret` and `tui.flows`. Removing
only that contract lets the suite complete, which is how it was identified.

With it removed the suite reports:

    Contracts: 4 kept, 5 broken.

Broken: `llm-not-persistence`, `tui-backend-prohibition`,
`tui-launcher-only-adapter-wiring`, `tui-components-independent`, and
`layered` -- the main hexagonal contract. 159 violation lines in total.
Examples: `cadrumo.application.ledger.llm_classification -> cadrumo.llm.suggestions`,
and `cadrumo.entrypoints.tui.operations` importing `cadrumo.adapters`.

None of this surfaces today, because the abort happens first.

## Why the ledger gates drift

`src/cadrumo/tests/test_importlinter_ledger.py` reads `.importlinter` and
reasons about its ignore edges. It is currently red on two counts: one
production module (`cadrumo.application.auth.apoderado_service`) pins an
adapters edge without being enrolled, and 31 reconciled entries no longer pin
any edge. Both are the expected consequence of a config nobody executes: the
file drifts because nothing fails when it does.

The 31 stale entries look like a sanctioned shrink -- the ledger says the set
"may only SHRINK" -- but that cannot be concluded while the linter is dark.
Several of those modules still import adapters
(`application.ledger.evidence`, `application.workflow.persistence`,
`application.user_profile.login_session` among them), so their pins going
missing is at least as likely to mean the contract stopped covering them.
Dropping them on the strength of the gate's own message would record a win
that has not been won.

## Not remediated here, deliberately

Making the suite run again turns five broken contracts and 159 violations into
a red gate on a shared tree with several peers mid-flight. That is an operator
call about sequencing, not a change to absorb inside an unrelated tick. The
first step is small -- repair or narrow `tui-feature-independence` so the
suite completes -- but the consequence is not.

## Evidence

Full report captured at `$CLAUDE_JOB_DIR/tmp/lint_report.txt` during this
investigation. `entrypoints/adapter_composition.py`, added earlier this
session, appears nowhere in it.

## Status

Open.
