---
tags:
  - '#plan'
  - '#m200-export-nif-misbinding'
date: '2026-08-07'
modified: '2026-08-07'
body_hash: 'sha256:e794f3f5dfe7c64a595e49c065d39b320e8238b3039b1fe5317af930c6b577df'
tier: L2
related:
  - '[[2026-08-07-m200-export-nif-misbinding-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace m200-export-nif-misbinding with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `m200-export-nif-misbinding` plan

Close the M200 grupo mercantil NIF export field misbinding, a live filing-
correctness defect writing the filer's own NIF into AEAT's foreign-parent-TIN
slot on every Modelo 200 fichero-BOE export.

## Description

Executes `m200-export-nif-misbinding-adr` in full. `P01` lands the urgent
correctness fix (re-declare the misbound field as filler) with its own
byte-level regression and mutation proof. `P02` adds the mechanical
registry-build gate the ADR names as the closable subset of the defect class
(typed-source-width check), with its own fixture-anchor proof. `P03` records,
rather than silently drops, the two follow-ups the ADR explicitly scoped out:
the still-unwired grupo mercantil block and the broader unswept semantic-
mismatch sweep across other draft attributes, casilla fields, bindings, and
modelos.

## Steps

### Phase `P01` - stop the false-NIF write in the M200 fichero-BOE export

Close the live filing-correctness defect by re-declaring the misbound field as filler and locking the fix with a byte-level regression and mutation proof.

- [ ] `P01.S01` - Re-declare field modelo-200-page-001b-draft-profile_tax_id-pos-141 as kind filler, dropping draft_attribute; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0003-modelo-200-page-001b.toml`.
- [ ] `P01.S02` - Add a byte-range regression asserting the rendered page-001b offset 141 to 155 is blank for a populated profile_tax_id draft; `src/cadrumo/application/filing/tests/test_export_completeness_sets.py`.
- [ ] `P01.S03` - Prove the new regression is load bearing by reverting the field to draft profile_tax_id, confirming the test reds, then restoring the fix; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0003-modelo-200-page-001b.toml`.

### Phase `P02` - gate draft-attribute width against its typed source

Add a registry-build validator that mechanically catches a draft_attribute bound to a slot whose width diverges from its typed source's canonical width, the same defect class as P01, proven with a fixture-anchor test.

- [ ] `P02.S04` - Add a registry-build validator asserting a draft field whose draft_attribute resolves to a typed fixed-width source declares a matching length, starting with profile_tax_id against SubjectTaxId at 9 characters; `src/cadrumo/domain/calculations/registry/_export.py`.
- [ ] `P02.S05` - Add a fixture-anchor test mutating a scratch export field's profile_tax_id length away from 9 and asserting RegistryValidationError, then restore; `src/cadrumo/domain/calculations/registry/tests/test_export.py`.
- [ ] `P02.S06` - Name the new width check as the slot-width sibling of the overlap check in the module docstring; `src/cadrumo/domain/calculations/registry/_export.py`.

### Phase `P03` - record the explicit follow-ups this fix does not close

Scaffold a research document capturing the still-unwired grupo mercantil block and the broader unswept semantic-mismatch sweep as open questions for a future ADR, so the scope this ADR narrowed is not lost.

- [ ] `P03.S07` - Scaffold a research document recording the unwired grupo mercantil block and the unswept broader draft-attribute, casilla, and binding semantic-mismatch sweep as open questions for a future ADR; `.vault/research/2026-08-07-m200-grupo-mercantil-wiring-research.md`.

## Parallelization

`P01` and `P03` carry no interdependency and may run in parallel; `P01` is
the urgent path and should not wait on `P03`. `P02`'s validator
(`P02.S04`-`P02.S06`) is independent of the specific field fixed in `P01`, so
`P01` and `P02` may also run in parallel, but `P02.S05`'s fixture-anchor test
should be re-run once `P01.S01` lands so the new validator is exercised
against the post-fix registry state, not only a scratch fixture. Within each
Phase, Steps are sequential: the fix precedes its regression, the regression
precedes its mutation proof.

## Verification

The plan is complete when every Step above is closed and the following all
pass:

- The new byte-range regression (`P01.S02`) passes against the fixed
  registry TOML, and the mutation proof (`P01.S03`) demonstrably reds when
  the field is reverted to `draft`/`profile_tax_id`, then is restored green
  - a gate unproven until it bites.
- The existing fichero-BOE parity and completeness gates
  (`test_export_completeness_gate.py`, `test_export_completeness_sets.py`,
  `test_fichero_boe_completeness_parity.py`, named by
  `modelo-export-mirrors-official-structure` and
  `2026-07-01-fichero-boe-parity-gate-adr`) stay green for Modelo 200 after
  `P01.S01` - the filler re-declaration must not remove a casilla the
  completeness manifest requires.
- The new registry-build width validator's fixture-anchor test (`P02.S05`)
  demonstrably fires `RegistryValidationError` on a mutated scratch
  declaration, then is restored, and the full registry build
  (`uv run --no-sync pytest --collect-only -q` plus the registry-loading
  suite) stays green with the validator active.
- `vaultspec-core vault check placeholders` and `vaultspec-core vault plan
  check` report clean on this plan and its related documents.
- `P03.S07`'s research document exists and is linked, so the two follow-ups
  this ADR scoped out are tracked artifacts rather than an unrecorded
  narrowing.
