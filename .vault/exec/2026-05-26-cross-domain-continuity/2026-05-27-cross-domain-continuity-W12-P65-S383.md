---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-05-27'
step_id: S383
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-source-jurisdiction-axis-adr]]"
---

# `cross-domain-continuity` `W12.P65.S383`

Close the write-side of the source_jurisdiction axis: widen the manual-ledger command + patch, thread the field through `_transaction_from_command`, add the `--source-jurisdiction` CLI flag on `aeat app ledger add`, and populate the help-text locale across all four supported languages.

Commits:
- `d75202aab` — source-side wiring (3 files)
- `5cbd8e1c4` — locale companion (4 yml files, scaffolded via the locale CLI)

- Modified: `src/aeat/application/ledger/_models.py`
- Modified: `src/aeat/application/ledger/_actions.py`
- Modified: `src/aeat/entrypoints/cli/_ledger.py`
- Modified: `src/aeat/locales/{en,es,ca,hu}.yml`

## Description

The write-side boundary needed three coordinated changes:

1. `ManualLedgerTransactionCommand` gains `source_jurisdiction: str | None = None` plus the 2-char alpha-uppercase validator. The command is the strict input boundary for `create_manual_transaction`, so the validator must live here (the CLI cannot rely on the model defaulting alone).
2. `ManualLedgerTransactionPatch` gains the same field and a validator that delegates to the command-side classmethod via the existing pattern (mirrors `_normalise_optional_currency` and `_normalise_optional_identifier_tuple`).
3. `_transaction_from_command` in `_actions.py` threads `command.source_jurisdiction` into the `Transaction.model_validate(...)` payload at the eligible construction site, completing the path: CLI flag → command → action → Transaction → encrypted catalogue.

The CLI flag is added to `ledger_add` as a typer option:

```
source_jurisdiction: str | None = typer.Option(
    None,
    "--source-jurisdiction",
    help=tr("cli.ledger.add.source_jurisdiction_help"),
),
```

The operator value is passed verbatim into the `ManualLedgerTransactionCommand(...)` construction. No profile-conditional defaulting in this Step — that lands in S384.

The help-text locale key `cli.ledger.add.source_jurisdiction_help` is populated via `python -m aeat.locales scaffold` followed by four `python -m aeat.locales set <locale> <key> <value>` calls. The translations are regulatory-anchored (LIRPF Art. 93 Beckham, IRNR scope) so the operator sees the relevance directly in their language.

## Sibling commit — S383b (locale companion)

`5cbd8e1c4` lands the four locale yml deltas in a separate commit, per the standing convention that locale-CLI scaffold output is committed independently from the code change that introduces the key. This isolates the locale diff from the code diff at review time.

## Verification

- Existing `ledger add` test suite continues to pass; the new flag is optional with a None default so existing invocations are unaffected.
- The model-level validator from S381 re-applies on the command, so malformed `--source-jurisdiction FOO` input surfaces as a pydantic ValidationError, routed through the existing `_ledger_validation_bad` → operator-facing refusal pattern.
- The locale CLI ran cleanly across all four languages; help-text reach confirmed at the `tr()` resolution site.

## Gate evidence

- G1 no naked env reads: unchanged.
- G2 typed pydantic at boundary: command and patch both carry strict-validator field.
- G3 user messages via tr(): help text routed through `tr("cli.ledger.add.source_jurisdiction_help")`; validator-error messages wrap through the existing CLI refusal funnel.
- G4 no locale yml hand-edits: all four locales populated via the `python -m aeat.locales set` CLI; the sibling-commit pattern records the scaffold output explicitly.
- G5 no shims: patch-side validator delegates to command-side classmethod (one canonical rule, two binding sites — same shape as the surrounding validators).
- G6 no tautological tests: no new tests in this leaf (CLI flag exercised by existing tests once the locale key resolves; profile-conditional tests land at S384).

## References

- ADR: source-jurisdiction-axis-adr (Implementation §S383)
- Sibling Steps: S381 (model field), S382 (encrypted roundtrip), S384 (profile-conditional resolver).
- Sibling commits in this Step: `5cbd8e1c4` (locale yml deltas — S383b).
- Surface: `--source-jurisdiction` flag at `src/aeat/entrypoints/cli/_ledger.py:ledger_add`; payload threading at `_actions.py:_transaction_from_command`.
