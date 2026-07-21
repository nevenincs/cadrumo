---
tags:
  - '#audit'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-02'
modified: '2026-07-17'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# `binding-vocabulary-cli-cohesion` audit: `Wave 1 D9 close-blocker audit`

## Scope

Wave 1 D9 close-blocker pass over the open remainder reported by
`vaultspec-core vault plan status` on 2026-07-02 after reconciling landed F8 work.
The pass used semantic search first, then targeted `rg`, plan-status JSON, scoped
`git diff -- <path>` WIP checks, and focused tests. This audit is not a closure
honesty review because the campaign is not structurally complete.

2026-07-02 refresh: `uv run --no-sync vaultspec-core vault plan status
2026-06-26-binding-vocabulary-cli-cohesion-plan --json` reports 18 of 27 steps
complete, `next_open_step` = `W03.P05.S15`, and `exec_missing_ids` = `[]`.

## Findings

### f8-implementation-reconciled | low | S25 and S26 were implemented but unchecked

The selector-union and `typed_enum` implementation was already present at HEAD in
commit `071438bd6`. Exec records were added for S25 and S26 and the plan steps were
checked through the plan CLI. The focused F8 run is not green yet: `test_selector_shape.py`
already carries non-authored WIP and fails because the live selector registry includes
`DONATIVO_DONOR` while the expected-set test has not been currentized. S27 remains
open and deferred until that peer-owned test WIP clears or its owner lands the
coverage update. Log: `_scratch-wave1-d9/f8-tests.log`.

### observation-prefix-tail-blocked | medium | S15-S18 still require relocation work on a dirty target surface

The Observation-prefix phase remains open. Several listed names are already prefixed,
but live code still exposes unprefixed carriers such as `RetencionObservation`,
`CounterpartObservation`, `CounterpartAggregationObservation`,
`DeclaracionObservation`, `BorradorObservation`, and `GroiObservation`. The first
phase target includes `src/aeat/domain/calculations/registry/_ledger_bindings.py`,
which already has non-authored WIP, so this pass did not start the relocation series.
S15-S18 are formally deferred to the named W03.P05 observation-prefix relocation
follow-up in this same approved plan, resuming at S15 after the dirty target files are
peer-clean.

### operator-verb-tail-blocked | medium | S21-S24 are blocked by active locale/operator-surface WIP

The CLI verb-reconciliation phase remains open: `bindings preview`, `calc pull --compute`,
and `work calculate` are still present in the live CLI. The step surface includes the
locale catalogues and operator help/write-policy/error-suggestion sweep; scoped WIP
checks found active non-authored edits in `src/aeat/locales/ca.yml`,
`src/aeat/locales/en.yml`, `src/aeat/locales/es.yml`, and `src/aeat/locales/hu.yml`.
Because these are operator-visible locale-bound changes, S21-S24 are deferred until
the locale/operator-surface WIP is clear and the locale CLI can own the full sweep.
The named follow-up is this plan's W04.P07 CLI source-pull verb reconciliation
sequence, resuming at S21.

## Fresh-Context Honesty Review

Reviewed the campaign as newly inherited, using the current plan status, ADR/reference
scope, exec-record inventory, focused F8 evidence, and scoped WIP checks as the
authority. Findings:

### close-observation-prefix | medium | S15-S18 are real relocation work blocked by dirty target files

The observation-prefix rows are not complete. The close-blocker pass found live
unprefixed carriers and a dirty first target (`_ledger_bindings.py`). Because each
relocation step is intended to be an atomic own-hunk rename with docs/API regeneration,
starting it on top of non-authored WIP would risk overwriting peer work. The formal
follow-up remains this plan's W03.P05 sequence, resuming at `S15` once the listed
carrier files are clean.

### close-operator-verb | medium | S21-S24 are operator-visible locale work blocked by locale WIP

The CLI verb rows are not complete. The locale catalogues currently carry
non-authored edits, and the rows require locale CLI ownership plus the write-policy,
error-suggestion, next-action, help, and command-identifier sweeps in one coherent
operator-visible change. The formal follow-up remains this plan's W04.P07 sequence,
resuming at `S21` once locale/operator-surface WIP is clear.

### close-f8-verification | low | S27 remains the F8 verification carry-forward

`S25` and `S26` have exec records and checked rows, but `S27` remains open because the
selector coverage test is not green against the live `DONATIVO_DONOR` source and the
test file carried non-authored WIP during this pass. The named follow-up is the same
W05.P08 F8 verification row, resuming when the selector coverage owner has cleared or
landed that test update.

## 2026-07-04 D9 Status Refresh

Current `vault plan status 2026-06-26-binding-vocabulary-cli-cohesion-plan --json`
reports 23 of 27 steps complete, `next_open_step` = `W04.P07.S21`, and
`exec_missing_ids` = `[]`. The open rows at HEAD are now only `W04.P07.S21`,
`W04.P07.S22`, `W04.P07.S23`, and `W04.P07.S24`; W03 and W05 are checked.

The prior W03 observation-prefix blocker is superseded by landed work. The plan now
shows `W03.P05.S15` through `W03.P05.S18` and `W03.P06.S19` through
`W03.P06.S20` checked with exec records.

G1 and G2 have also landed in code. Commit `c9d4cc09b0` renames `app modelo
bindings preview` to `app modelo bindings resolve`; current CLI help shows the
bindings subgroup exposing `list` and `resolve`. Commit `03ddcff732` splits
`config google sync calc pull --compute` into transport-only `pull` plus the read-only
sibling `compute`; current CLI help shows `export`, `verify`, `pull`, and `compute`.
This pass added missing S21 and S22 exec records from those landed commits and today's
focused evidence.

Verification refreshed for the reconciled G1/G2 surface:

- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py -k "bindings"` passed (`2 passed`).
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/tests/test_google_payloads.py` passed (`7 passed`).
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` passed (`140 passed`).
- `vaultspec-core vault check features --feature binding-vocabulary-cli-cohesion` is clean after rebuilding the feature index.

`test_documented_command_conformance.py` is not clean, but the failure is unrelated to
this feature: `docs/HARNESS-USERDOCS-KICKOFF-BRIEF.md` cites `aeat app agent --layout
plugin`, where `plugin` is parsed as a nonexistent subcommand, plus an ellipsis command
path. No failure names `modelo bindings resolve`, `config google sync calc pull`, or
`config google sync calc compute`.

The S21/S22 checkboxes remain unchecked in this pass only because the plan file carries
non-authored WIP that removes the template link-rule comment block. Mutating the plan
checkboxes would violate the abort-on-WIP rule. Once that plan-file WIP is cleared, S21
and S22 can be checked against the exec records added here.

`W04.P07.S23` is still open on intent. The live command remains `app modelo work
calculate`, and no landed G3 commit analogous to G1/G2 was found. The ADR acceptance
note says phase 2.4/W04 is delivered, but current code does not show a work-calculate
verb rename; this needs coordinator adjudication before any checkbox is claimed. If
`work calculate` is intentionally retained as the canonical aggregation-engine verb,
S23 should be closed with a no-rename/no-shift exec record that cites that decision. If
not, S23 still needs the operator-visible rename sweep.

`W04.P07.S24` remains open until S23 is adjudicated and the documented-command
conformance failure is either fixed by its owning campaign or formally inventoried as an
unrelated gate failure for W04 verification.

## Closure Decision

For Wave 1 D9 purposes, this campaign's remaining tail is now narrowed rather than fully
drained: S21/S22 have matching exec evidence and await safe checkbox mutation; S23/S24
remain open with the blocker above. The vault plan remains open by design; no missing
exec alert remains.

## Recommendations

When the plan-file WIP clears, run `vaultspec-core vault plan step check` for
`W04.P07.S21` and `W04.P07.S22` if no newer code drift invalidates the evidence. Do
not check `W04.P07.S23` until the G3/work-calculate intent is adjudicated against the
accepted ADR note and current command tree. Run `W04.P07.S24` only after S23 is
resolved and the documented-command conformance failure is either green or explicitly
inventoried as unrelated. Do not lift the bindings freeze from this campaign:
`vault plan status` still reports open steps.
