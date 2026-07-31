---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:2acb3c5952e38bb3b96b9981ecce869efc09885650ad4edc98ef792874af2647'
step_id: 'S20'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Expose the dormant link-consistency detector on the existing ledger check verb as a typed period-independent result channel with a warning notice and a false readiness verdict, gated on a CLI test reproducing a one-sided link and asserting the row, the notice contract, and ready false

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`
- `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py`

## Description

- Wire the link-consistency detector into the existing ledger check verb rather than adding a new one: check is already the operator-facing local integrity probe for the ledger, so a second verb would have been a parallel authority for the same operator question.
- Resolve link integrity once per invocation and report it from all three branches of the verb, since it is a whole-bucket property of the two catalogues rather than a per-period readiness fact.
- Add a typed payload for one one-sided link and a list field on the check result, documenting which catalogue cites the other without being cited back.
- Fold the channel into the readiness verdict, so a disagreeing link makes the bucket not ready for the same reason a missing fact does.
- Emit a warning notice on the typed notice channel naming the repairing verb, with the count as structured context, and add the four locale catalogue leaves through the locales CLI.
- Extend the verb help in all four catalogues so the operator can discover the new coverage.

## Outcome

An operator can now discover a drifted invoice link. Before this step the detector and its result model existed and were unit-tested but no entrypoint called them, so a divergence was undiscoverable in practice.

Gated by two CLI tests: a consistent bucket reports an empty channel, ready true, and no notices; a reproduced one-sided link reports exactly one row with its direction, ready false, and a warning notice whose code, severity, suggestion, and context are asserted structurally. No localized prose is asserted.

## Notes

The one-sided state is no longer reachable through the CLI now that the writer is atomic, so the CLI test reproduces it at the repository boundary. That is deliberate: the detector must still work for a divergence arriving from an interrupted pre-atomic write or an out-of-band edit.

The diagnostic rides the typed notice channel and the rows are primary result data, so no bespoke advisory or suggestion field was added to the payload.

Setting one locale leaf failed once with a Windows permission error while a peer campaign held the same catalogue open; the retry succeeded and the drift check is clean across all four.
