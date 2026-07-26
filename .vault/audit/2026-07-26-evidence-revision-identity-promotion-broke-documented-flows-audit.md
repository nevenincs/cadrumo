---
tags:
  - '#audit'
  - '#evidence-revision-identity'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - '[[2026-07-26-evidence-revision-identity-adr]]'
---

# `evidence-revision-identity` audit: `the deductible-evidence promotion breaks three documented walkthroughs`

## Scope

The deductible-IVA evidence finding was promoted from ADVISORY to BLOCKING at
verify. That decision is sound and this record does not reopen it: the escape
path was verified end to end, and refusing to grant over a deduction the
taxpayer cannot exercise is correct under LIVA art. 97.

What was not checked is the documented surface. `verify` now exits non-zero on
flows the how-to corpus executes and asserts, so the docs build is red and
three published walkthroughs no longer run.

Found by running the Sphinx docs gate, which nothing else had exercised in this
session. Semantic search was unusable throughout, so this rests on executing the
sequence runner and reading its output.

## Findings

### documented-verify-flow-now-exits-non-zero | high | the sequence cannot execute, so its golden cannot be refreshed

`dev.docs.sequences refresh --page how-to/verification-reports` fails:

> cli-sequence `verification-reports-modelo-303` failed to execute: line 8:
> frame exited 1, expected 0

on `aeat --format json app modelo work verify`, with the emitted notice being
the new `modelo.work.verify.finding.blocking_rule` carrying the art. 97 message.

This is not a stale golden. Re-running the refresh produced **byte-identical**
files, because the frame never completes — the recorded output cannot advance
past a command that now refuses. A golden refresh is therefore not the remedy,
and reaching for one first (as this record's author did) wastes a 15-minute run.

### three sequences reach the same gate | high | the blast radius is the whole how-to verify surface

Sequences invoking `modelo work verify` on a ledger-derived draft:
`verification-reports-modelo-303`, `verification-reports-export-check`, and
`review-values-review-saved`.

### docs gate is red in every locale scope | high | five failing tests, not one

`test_sphinx_nitpicky_build_is_clean`, `test_user_scope_build_is_nitpicky_clean_and_excludes_api`,
and the localized user-scope builds for `es`, `ca` and `hu`. The failure
multiplies across scopes because each rebuilds the same executed corpus.

### the walkthroughs teach a sequence the product no longer permits | medium | this is the substance, not the gate

The fixtures carry a deductible IVA row with no purchase invoice, which was
verifiable before the promotion and is refused after it. So the documents
instruct an operator through a flow that now stops — and the stop is correct.
The documentation is what is wrong, not the gate.

## Recommendations

Update the three sequences to teach the ordering the promotion makes mandatory:
register and attach purchase-invoice evidence before verify, which is precisely
what the refusal's own `next_action` instructs. That turns a broken walkthrough
into one that teaches the new requirement, and it exercises the attach path the
promotion depends on.

Do not weaken the sequences with a non-zero exit expectation. `@expect exit_code
== 1` would make the gate green while publishing a walkthrough that ends in a
refusal, which is worse than the current red.

Prefer fixing the fixtures over reverting the promotion. The promotion is
correct; only its documented surface lagged.

Whoever takes it should run the docs gate to confirm, and budget for it: the
full run is roughly 35 minutes, which is why it had gone unmeasured.
