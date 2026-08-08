---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:1ea4af3346c907755befa8de4f030c7d9d69ba87fa7c0a4d58d9d4d085a04424'
step_id: 'S199'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Build the operator answer channel for counterparty establishment

## Scope

- `src/cadrumo/entrypoints/cli`
- `src/cadrumo/application/ledger`

## Description

- Add the counterparty command group and its confirm verb, taking the subject as a positional argument and the territory as the closed enum so the accepted set is rendered on a parse failure.
- Add the withdraw verb, because the confirm verb's conflict refusal already instructed the operator to use it.
- Add the show verb, so what the ladder will answer can be read without triggering an error to discover it.
- Derive the idempotent-retry signal from the returned record rather than from a pre-read of the store, and surface it as an info notice beside a typed field.
- Register the three JSON payload schemas on the shared envelope spine.
- Add fourteen operator strings with real values in all four locale catalogues.
- Gate the loop end to end from a real CLI invocation.

## Outcome

The last rung of the establishment ladder could be read and not written. The recording function was complete, idempotency-guarded and covered by its own suite, and it had no production caller and no operator surface — so a domestic invoice printing a bare CIF exhausted the ladder, surfaced a review item naming the counterparty, and left the operator with no verb to answer it. The next document from the same counterparty exhausted identically. This closes that end.

The application layer needed no change: it already owned the idempotency rules, the conflict refusal and the canonical-identity key. What was missing was entirely the channel, which is why the work is a CLI surface rather than a redesign.

Two verbs beyond the minimum are carried, and neither is scope creep. Withdraw ships because the confirm verb's conflict refusal names it: landing confirm alone would have shipped an instruction pointing at a command that does not exist, which is the defect shape this campaign keeps finding. Show ships because the gate needed a way to ask what the ladder would answer, and the honest way to get it was through the contract rather than by constructing a repository inside the test — an answer that can only be discovered by provoking a conflict error is not a read path.

The retry signal is derived without a check-then-act window. The verb supplies its own timestamp and recognises its own write by comparing what comes back: the writer preserves the original stamp on a retry precisely so a repeat cannot look like a fresh confirmation, so a returned stamp that differs from the supplied one is proof the record already existed. A pre-read would have answered the same question through a window a retrying caller can lose.

## Verification

The unreached surface measured before any change, by grepping every caller of each function outside its defining module:

    record_counterparty_establishment   -> facade re-export and tests only, zero production callers
    forget_counterparty_establishment   -> facade re-export and tests only, zero production callers
    resolve_counterparty_establishment  -> wired, at the ladder's last rung

The loop, end to end, through the real CLI against the real encrypted profile store:

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_counterparty_cli.py -n0 -q -m integration
    9 passed in 12.88s

Locale coverage, checked against the four catalogues after scaffolding:

    en keys: 14 placeholders: []
    es keys: 14 placeholders: []
    ca keys: 14 placeholders: []
    hu keys: 14 placeholders: []

Contract and locale gates:

    uv run --no-sync pytest src/cadrumo/tests/test_parity.py src/cadrumo/tests/test_locale_translation_honesty.py src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -n0 -q -m "unit or integration"
    2 failed, 201 passed in 347.36s

The two failures are the translation-honesty ratchet and neither names a key from this row. Measured against HEAD rather than argued: the keys the gate reports as untranslated overflow are present in HEAD's own catalogues with identical values across locales and absent from HEAD's allowlist, so the gate was already red before this work began.

## Notes

The gate is deliberately written as a loop rather than as a persistence check, and that distinction is the row's whole point. A test that invokes the verb and then reads the store proves the verb writes — which is exactly the property the unreachable function already had, proven by its own suite, while nothing called it. So every assertion here runs the verb through the CLI and then asks what the consumer will answer.

Three attempts were needed to get that assertion honest. The first reached into the application layer directly and failed on an unlocked bucket session; the second still reached past the contract; the third goes through the show verb, which asks the same resolver the ladder asks. The gap the failure exposed was real rather than an inconvenience of testing, and adding the verb was the fix rather than working around it.

The show verb reports what the LADDER will answer, not what the repository holds, and the two are not the same question: the resolver declines to return a fact the document's evidence contradicts, so a row can be stored and still settle nothing. A payload read from the repository would have shown an operator a territory no later document would use. Provenance inspection — who asserted, when, and on what note — is therefore not on this surface and is a defensible follow-up.

The catalogue tooling failed twice mid-run with a permission error on the atomic replace, which is this host's known concurrent-I/O behaviour rather than a defect in the tool. Both runs were repeated and the resulting values verified key by key rather than trusted; one Catalan value was lost to the first failure and re-set.

An early reading suggested the locale scaffold had swept in placeholder keys belonging to other lanes. Re-measuring against the current HEAD showed zero new keys: those placeholders were a peer's, already committed, and the earlier reading was taken against a HEAD that had since moved. The finding was withdrawn before it was acted on.
