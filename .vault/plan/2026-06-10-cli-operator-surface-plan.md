---
tags:
  - '#plan'
  - '#cli-operator-surface'
date: '2026-06-10'
modified: '2026-06-10'
tier: L3
related:
  - '[[2026-06-10-cli-operator-surface-adr]]'
  - '[[2026-06-10-cli-operator-surface-research]]'
  - '[[2026-06-10-cli-operator-surface-audit]]'
  - '[[2026-06-10-cli-operator-crud-matrix-audit]]'
---


# `cli-operator-surface` `operator surface hardening rollout` plan

## Wave `W01` - honesty quick wins

Land the independent, low-coupling honesty repairs that need no cross-file relocation: the D8 preflight active-revision default, the D6 --language help-text honesty contract, and the D5 self-referential-string conformance gate that lands before the W03 renames so it protects them, including fixing the known enum-choice offenders under the new gate. Backed by the operator-surface ADR D5/D6/D8, the surface audit F5/F6/F8, and the CRUD audit. No downstream Wave depends on W01 except that W03's renames are protected by the W01 D5 gate.

### Phase `W01.P01` - self-referential-string conformance gate (D5)

Add the conformance gate that pins command-naming hint strings and enum-choice-vs-handler sets against the live tree, then fix the known enum-choice offenders under it. The gate lands first so it protects the W03 renames.

- [x] `W01.P01.S01` - add a test-time conformance gate that pins next-action and failure-hint strings naming a command path to a live command, mirroring the documented-command gate mechanism; `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`.
- [x] `W01.P01.S02` - extend the conformance gate to assert every Typer option typed as an enum has its advertised choice set equal to the set the handler accepts, failing on any advertised member the handler refuses; `src/aeat/entrypoints/cli/tests`.
- [x] `W01.P01.S03` - narrow the doclink --source enum choice to the three members the handler accepts or widen the handler so the advertised set matches, satisfying the new gate; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `W01.P01.S04` - narrow the work verify --select choices to the states verify accepts so latest-verified and filed stop being advertised-but-impossible, satisfying the new gate; `src/aeat/application/modelo/_selectors.py`.
- [x] `W01.P01.S05` - correct the evidence-id help string that promises unambiguous prefix to state exact-equality matching, via the aeat.locales CLI; `src/aeat/locales/en.yml`.
- [x] `W01.P01.S06` - run the documented-command conformance gate and the new D5 gate to confirm zero drift across hint strings and enum-choice sets; `src/aeat/entrypoints/cli/tests`.

### Phase `W01.P02` - preflight active-revision default (D8)

Default preflight to the active revision for the natural key so the readiness question stops demanding an internal revision id, keeping --revision-id as an explicit override, and simplify the choose-modelo guide in the same commit.

- [x] `W01.P02.S07` - default preflight --revision-id to the active revision resolved from modelo, filing_year, and period through the modelo-addressing resolver, keeping --revision-id as an explicit override and refusing with a candidate list when the natural key is ambiguous; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W01.P02.S08` - add real-behavior tests proving preflight answers from the natural key alone, that the explicit --revision-id override still selects an exact revision, and that an ambiguous natural key refuses with candidates; `src/aeat/entrypoints/cli/tests`.
- [x] `W01.P02.S09` - simplify the choose-modelo guide to remove the run modelo describe, read out the revision id, paste it back detour in the same commit; `docs/how-to/choose-modelo.md`.
- [x] `W01.P02.S10` - update locale strings for the preflight help text via the aeat.locales CLI and regenerate the CLI reference for the changed signature; `src/aeat/locales/en.yml`.

### Phase `W01.P03` - honest --language help-text contract (D6)

Resolve the eager --language flag's silent help-text failure per the accepted ordering work-then-remove-then-warn, after a feasibility spike on deferred help rendering.

- [x] `W01.P03.S11` - run a feasibility spike on deferring help-text rendering until after eager-option resolution to determine whether --language can be made to actually localize help text without destabilising the import-time i18n model; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `W01.P03.S12` - implement the highest feasible D6 outcome in ordering work-then-remove-then-warn: make --language localize help text if the spike succeeds, else remove it from the help surface it cannot affect, else emit a one-line warning naming AEAT_OUTPUT_LANGUAGE; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `W01.P03.S13` - add real-behavior tests proving --language no longer silently fails for help text, asserting the chosen outcome and leaving the profile-owned precedence and AEAT_OUTPUT_LANGUAGE override unchanged; `src/aeat/entrypoints/cli/tests`.
- [x] `W01.P03.S14` - update locale strings via the aeat.locales CLI for any new warning text and regenerate the CLI reference if the flag surface changes; `src/aeat/locales/en.yml`.

## Wave `W02` - reversal and lineage

Close the single highest-leverage CRUD gap (D2 ledger restore to ACTIVE) and the ledger row identity-churn gap (D3 lineage-resolving history/view/track), each bundling domain transition, application action, CLI verb, audit event, real-behavior tests, locale updates, and same-commit docs edits. Backed by ADR D2/D3, surface audit F2/F3, and CRUD audit F-01 plus journeys (a) and (e). W02 lands before W03's grammar work only where the same ledger files collide.

### Phase `W02.P04` - ledger restore to ACTIVE (D2)

Build the restore-to-ACTIVE lifecycle transition, application action, CLI verb, and audit event with full operator-hardening guarantees and real-behavior tests including the bulk-stash recovery journey, updating the honest-permanence docs in the same commit.

- [x] `W02.P04.S15` - add a public restore-to-ACTIVE lifecycle transition over the state-generic primitive that moves STASHED to ACTIVE and ARCHIVED to ACTIVE, keeping SPLIT and MERGED lineage out of scope; `src/aeat/application/ledger/_actions_lifecycle.py`.
- [x] `W02.P04.S16` - add a restore_manual_transaction application action that honours the finalized-modelo guard and records --reason into its own audit event, mirroring the forward archive and stash actions; `src/aeat/application/ledger/_actions_lifecycle.py`.
- [x] `W02.P04.S17` - add a new ledger restore BucketEventType audit event distinct from the forward set-aside events; `src/aeat/application/ledger/_actions_lifecycle.py`.
- [x] `W02.P04.S18` - add the aeat app ledger restore --id ID CLI verb accepting the _resolve_id prefix form and carrying --yes and --reason, with the enum-choice and hint strings conforming to the W01 D5 gate; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `W02.P04.S19` - add real-behavior roundtrip and anti-tautology tests for the restore transition with every defaultable field populated non-default, asserting STASHED-to-ACTIVE and ARCHIVED-to-ACTIVE round-trip and the finalized-modelo guard refusal; `src/aeat/application/ledger/tests`.
- [x] `W02.P04.S20` - add a real-behavior test reproducing the bulk-stash recovery journey end to end, stashing several rows then restoring them to active without a whole-ledger reset; `src/aeat/entrypoints/cli/tests`.
- [x] `W02.P04.S21` - add restore help and event locale strings via the aeat.locales CLI; `src/aeat/locales/en.yml`.
- [x] `W02.P04.S22` - remove the Both are permanent honest-limitation sentence and document the restore verb in the correct-ledger-entries guide in the same commit; `docs/how-to/correct-ledger-entries.md`.
- [x] `W02.P04.S23` - remove the matching permanent-stash sentence from the import-bank-statements guide in the same commit; `docs/how-to/import-bank-statements.md`.
- [x] `W02.P04.S24` - run the documented-command conformance gate and regenerate the CLI reference for the new restore verb; `src/aeat/entrypoints/cli/tests`.

### Phase `W02.P05` - stable ledger lineage handle across edits (D3)

Make ledger history/view/track resolve any id in a row's edit-lineage chain to the current row so an old written-down id keeps answering after a correction, with real tests proving the old id still resolves.

- [x] `W02.P05.S25` - make ledger history resolve any id in a row's TransactionEditLineageEntry chain to the current row so an old written-down id keeps answering after an edit re-derives the transaction_id; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `W02.P05.S26` - make ledger view resolve any id in the edit-lineage chain to the current row so a pre-edit id still views the corrected row; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `W02.P05.S27` - make ledger track resolve any id in the edit-lineage chain to the current row so the lineage handle survives a correction; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `W02.P05.S28` - keep the content-addressed transaction_id authoritative for storage and audit while exposing the lineage resolution at the operator read boundary, not freezing the id across edits; `src/aeat/domain/transactions/_models.py`.
- [x] `W02.P05.S29` - add real-behavior tests recording an id, editing the row, and asserting the old id still resolves through history, view, and track to the current row; `src/aeat/entrypoints/cli/tests`.
- [x] `W02.P05.S30` - update locale strings for any changed lineage help text via the aeat.locales CLI and update the correct-ledger-entries guide id-churn note in the same commit; `docs/how-to/correct-ledger-entries.md`.
- [x] `W02.P05.S31` - run the documented-command conformance gate and the D5 gate to confirm the lineage surface introduces no hint drift; `src/aeat/entrypoints/cli/tests`.

## Wave `W03` - hard renames and one grammar

Execute the strict no-alias hard renames (D1 switch-replaces-unlock as one atomic relocation commit; the queued reset-state and bucket renames under the same discipline) and the D4 one-period-grammar conversion layer. Backed by ADR D1/D4, surface audit F1/F4. Depends on W01's D5 gate being in place to protect the rename, and coordinates with W02 where ledger period sites overlap the restore/lineage files. The D1 rename is exclusive: it touches many files and must coordinate with peers in this shared worktree.

### Phase `W03.P06` - switch-replaces-unlock hard rename (D1)

Replace unlock with the intent-named switch verb as one atomic relocation commit: rename, every caller, the retired-verb test, locale strings, docs sweep, and regenerated CLI reference in the same change, tagged relocation:switch. Exclusive file-heavy step; coordinate with peers.

- [x] `W03.P06.S32` - reconcile the already-landed unlock-to-switch hard rename at the config surface: canonical site, callers, locale strings via the aeat.locales CLI, docs sweep, generated CLI reference, and clean collection evidence all show switch as the live operator verb; `src/aeat/entrypoints/cli/_config/_custody.py`.
- [x] `W03.P06.S33` - reconcile the post-rename deletion of the retired-verb inventory subsystem: `_RETIRED_VERBS` no longer exists, the ADR records that deletion, and retired spellings are asserted by no-command behavior rather than a retained ledger; `src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`.
- [x] `W03.P06.S34` - verify every how-to guide that taught unlock was swept onto switch and the switch-by-unlocking gloss is absent from operator docs; `docs/how-to`.
- [x] `W03.P06.S35` - verify real-behavior tests proving switch performs the session-unlock mechanics underneath, that unlock resolves to no command, and that no alias or deprecation surface survives; `src/aeat/entrypoints/cli/tests`.

### Phase `W03.P07` - queued leaked-term hard renames

Apply the same hard-rename discipline to the other storage-leak terms the ADR queued: config repair reset-state and the operator-facing bucket noun, each as a separate atomic relocation commit with one intent-named spelling replacing the leaked term outright.

- [x] `W03.P07.S36` - close the already-landed config repair reset-state to reset-progress hard rename by de-jargoning the remaining reset-progress help, text-mode notices, locale strings via the aeat.locales CLI, docs sweep, retired-verb guard, and regenerated CLI reference with no reset-state alias; `src/aeat/entrypoints/cli/_config`.
- [x] `W03.P07.S37` - rename the operator-facing bucket noun to profile across CLI help and locale strings as a separate atomic relocation commit, keeping bucket only where it names the internal encrypted-storage concept, via the aeat.locales CLI with docs sweep and regenerated CLI reference; `src/aeat/locales/en.yml`.
- [x] `W03.P07.S38` - add real-behavior tests asserting the renamed verbs and nouns resolve, the leaked terms are retired with no alias, and the D5 gate and documented-command gate stay green; `src/aeat/entrypoints/cli/tests`.

### Phase `W03.P08` - one operator period grammar (D4)

Make the AEAT token grammar canonical everywhere per the 2026-06-10 ADR amendment: ledger --period sites accept AEAT tokens plus --year, reject calendar shapes and year-qualified hybrids, and teach one grammar in help and troubleshooting docs.

- [x] `W03.P08.S39` - make the ledger --period parser accept the canonical AEAT tokens (1T-4T, 0A, 01-12, plus registry-union members with ledger date spans) with --year, normalising to the internal representation and validating against the registry period union; `src/aeat/entrypoints/cli/_common.py`.
- [x] `W03.P08.S40` - lead the ledger --period --help with the canonical AEAT tokens and --year so operators are taught one grammar and no calendar-shape conversion promise remains; `src/aeat/entrypoints/cli/_common.py`.
- [x] `W03.P08.S41` - make ledger period refusal messages reject calendar shapes/year-qualified hybrids and name the AEAT-token grammar plus --year requirement, via the aeat.locales CLI; `src/aeat/locales/en.yml`.
- [x] `W03.P08.S42` - add real-behavior tests proving ledger --period accepts AEAT tokens with --year, refuses calendar shapes and year-qualified hybrids, normalises to one internal representation, and passes the registry validator for advertised date-span codes; `src/aeat/entrypoints/cli/tests`.
- [x] `W03.P08.S43` - update the troubleshooting period-trap section to teach the one canonical grammar and note that calendar shapes/year-qualified hybrids are refused; `docs/how-to/troubleshooting.md`.
- [x] `W03.P08.S44` - run the documented-command conformance gate and regenerate the CLI reference for the changed period help text; `src/aeat/entrypoints/cli/tests`.

## Wave `W04` - read-back baseline

Establish the D7 read-back baseline guarantee for record-creating verbs in audit priority order: M036 list/view first, then reconciliation history, then the IVA wallet correction path, closing the in-scope backlog surfaces and deferring the filing-record unfile decision per the ADR. Backed by ADR D7, surface audit F7, and CRUD audit F-03/F-05/F-07 plus journey (b). Lands last; depends on no other Wave but benefits from the W01 D5 gate guarding its new hint strings.

### Phase `W04.P09` - M036 read-back (D7)

Add m036 list and m036 view reading through the already-shipped declaration repository with no parallel read path, removing the modelo-036 honest-limitation sentences in the same commit.

- [x] `W04.P09.S45` - add a list_declarations read surface in the M036 lifecycle application module reading through the already-shipped declaration repository with no parallel read path; `src/aeat/application/modelo/_m036_lifecycle.py`.
- [x] `W04.P09.S46` - add the aeat app modelo m036 list and m036 view CLI verbs over the declaration read surface with hint strings conforming to the W01 D5 gate; `src/aeat/entrypoints/cli/_modelo_m036_cli.py`.
- [x] `W04.P09.S47` - add real-behavior tests recording an M036 declaration then listing and viewing it back, asserting the read path reads through the owning repository; `src/aeat/application/modelo/tests`.
- [x] `W04.P09.S48` - remove the no command yet lists recorded declarations honest-limitation sentence from the modelo-036 guide in the same commit; `docs/how-to/modelo-036.md`.
- [x] `W04.P09.S49` - add m036 list and view locale strings via the aeat.locales CLI and regenerate the CLI reference for the new verbs; `src/aeat/locales/en.yml`.

### Phase `W04.P10` - reconciliation history and IVA wallet correction (D7)

Add the reconciliation-history list surface and the IVA wallet correction/read path under the read-back baseline guarantee, closing the in-scope CRUD surfaces and deferring the filing-record unfile decision per the ADR.

- [x] `W04.P10.S50` - add a reconciliation-history list surface so past reconciliation verdicts are enumerable, reading through the owning repository with no parallel read path; `src/aeat/application/modelo`.
- [x] `W04.P10.S51` - add the aeat app modelo reconciliation-history CLI verb with hint strings conforming to the D5 gate; `src/aeat/entrypoints/cli`.
- [x] `W04.P10.S52` - add a guarded IVA wallet correction path so a wrong seed for a pre-history period can be corrected or re-read rather than being unrecoverable, gated on --confirm; `src/aeat/application/modelo`.
- [x] `W04.P10.S53` - add the aeat app modelo iva-wallet correction CLI verb with the read path and hint strings conforming to the D5 gate; `src/aeat/entrypoints/cli`.
- [x] `W04.P10.S54` - add real-behavior tests for the reconciliation-history list and the IVA wallet correction path asserting round-trip read-back; `src/aeat/application/modelo/tests`.
- [x] `W04.P10.S55` - update the affected how-to guides removing the no reconciliation-history and seed-once honest-limitation sentences and add locale strings via the aeat.locales CLI in the same commits, regenerating the CLI reference; `docs/how-to`.

## Description

Rollout plan for the accepted operator-surface ADR (2026-06-10-cli-operator-surface-adr, accepted with three operator caveats: strict no-alias hard renames, user-choice input overrides welcome, guessability as the verb acceptance test). The ADR's eight decisions D1 through D8 reconcile the operator-surface weaknesses catalogued by the surface audit (findings F1 to F8, with file and line evidence) and the CRUD matrix audit (capability matrix, journey verdicts (a) through (e), findings F-01 to F-08), both synthesised by the research document. The plan delivers four sequenced waves: W01 lands the independent honesty quick wins (D5 conformance gate first so it protects everything after it, D8 preflight natural-key default, D6 --language honesty contract in the accepted ordering work-then-remove-then-warn); W02 closes the highest-leverage recovery and identity gaps (D2 ledger restore to ACTIVE, D3 lineage-resolving read verbs); W03 executes the strict hard renames (D1 switch-replaces-unlock as one atomic relocation commit, the queued reset-state and bucket renames, D4 one-period-grammar conversion); W04 establishes the D7 read-back baseline (M036 list and view first, then reconciliation history and the IVA wallet correction path). The filing-record unfile decision and the gestor cross-profile bulk gap (CRUD F-04) are explicitly deferred per the ADR. Every operator-surface Step bundles real-behavior tests with no mocks or skips, locale updates through the `python -m aeat.locales` CLI only, same-commit docs updates, the documented-command conformance gate, and CLI-reference regeneration when the command tree changes; Steps that change `src/aeat` module structure also run `python -m dev.docs.apidocs scaffold`. The never-live-submission gate is untouched throughout.

## Steps







## Parallelization

Waves are sequenced by default: W01 lands before W02, W02 before W03, W03 before W04. The binding ordering constraints inside that default are: the W01.P01 D5 gate MUST land before any W03 rename so the gate protects the renamed hint strings and enum choices; W02 must land before W03.P08's grammar work only where the two touch the same ledger CLI files (`src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`, `src/aeat/entrypoints/cli/_common.py`); and within W01 the three Phases P01, P02, P03 are mutually independent and may run in parallel under three agents. Within W02, P04 (restore) and P05 (lineage) share `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py` and should be serialised or coordinated on that one file. W03.P06 (the D1 switch rename) is EXCLUSIVE: it is one atomic relocation commit touching the custody module, every caller, the retired-verb inventory test, locale catalogues, the docs sweep, and the regenerated CLI reference; in this shared multi-agent worktree the executing agent must announce the rename, check `git diff -- <file>` for peer WIP on every touched file before editing, and land the whole change in one explicit-path commit tagged relocation:switch. The two W03.P07 renames follow the same exclusive discipline, each as its own atomic commit. W04's two Phases are independent of each other and may parallelise. Suggested personas: vaultspec-high-executor for W02.P04, W03.P06, and W03.P08 (lifecycle and relocation core logic); vaultspec-standard-executor for W01, W02.P05, W03.P07, and W04; vaultspec-code-reviewer dispatched after each Wave closes per the swarm audit cadence.

## Verification

The plan is complete when every Step in every Wave is closed. Each Wave additionally closes against these concrete, runnable gates:

- Documented-command conformance gate stays green after every command-tree change: `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m integration`.
- The new D5 self-referential-string gate (W01.P01) passes from its landing onward, proving every command-naming hint resolves to a live command and every advertised Typer enum choice is acceptable to its handler; the doclink --source and work verify --select offenders enumerate as fixed under it.
- Locale gates stay green after every locale change: `python -m aeat.locales scaffold --check` exits clean and `python -m aeat.locales audit` reports no drift; the inter-locale parity and translation-honesty pytest gates pass.
- Docs drift gates: `python -m dev.docs.apidocs scaffold --check` exits clean after any `src/aeat` module-tree change, and the Sphinx nitpicky build gate `pytest dev/docs/tests/test_docs_build.py` passes after every docs sweep.
- CLI-reference regeneration is committed in the same change as every command-tree mutation (W02.P04 restore verb, W03.P06 and W03.P07 renames, W03.P08 period help, W04 read-back verbs).
- CRUD-audit journey re-runs as acceptance evidence: after W02 the bulk-stash recovery journey (CRUD audit journey (e), finding F-01) MUST PASS end to end without `ledger reset` - stash several rows, restore them, assert active; after W02 plus W03 the quarter-end loop (journey (a)) re-runs with its id-churn sharp edge resolved - an id written down before `ledger update` still answers through history, view, and track.
- W03 rename acceptance: `unlock` resolves to no command, `switch` performs the session-unlock mechanics, no `_RETIRED_VERBS` subsystem or deprecation ledger remains, no alias or deprecation surface exists, and the relocation commit passes `uv run --no-sync pytest --collect-only -q` clean immediately before landing.
- W04 read-back acceptance: an M036 declaration recorded by alta is listed by `m036 list` and shown by `m036 view`; the modelo-036 guide no longer carries the no-read-back honest-limitation sentence; reconciliation history and the IVA wallet correction path round-trip in real-behavior tests.
- All new tests are real-behavior per the quality-gates rule: no mocks, skips, xfail, stubs, or tautological assertions; lifecycle roundtrips populate every defaultable field non-default per the roundtrip discipline.
- Closure gate: per the campaign-close honesty review rule, a fresh-context honesty review runs against the closing summary before this plan is declared structurally complete, and `uv run --no-sync vaultspec-core vault check all` stays green throughout.
