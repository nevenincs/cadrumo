---
tags:
  - '#plan'
  - '#iva-compensation-override-cli'
date: '2026-06-19'
modified: '2026-06-19'
tier: L2
related:
  - '[[2026-06-19-iva-compensation-override-cli-adr]]'
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
     Replace iva-compensation-override-cli with a kebab-case feature tag, e.g. #foo-bar.
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

# `iva-compensation-override-cli` plan

### Phase `P01` - Application recorder + persistence

Record an explicit taxpayer override as a persisted taxpayer_override IVA-wallet decision so the calculate path applies the cross-period carry, with mandatory provenance and an audit event.


<!-- One-line headline summary plan. -->

- [ ] `P01.S01` - Add record_iva_compensation_override_for_bucket: resolve NIF, build IvaCompensationOverride(amount, reason, evidence_locator, recorded_at), drive reconcile_modelo_303_iva_compensation with override and persist the taxpayer_override decision; `src/aeat/application/modelo/_iva_wallet_seed.py`.
- [ ] `P01.S02` - Emit a MODELO_IVA_WALLET override audit event carrying reason and evidence_locator provenance through the single BucketEventHistoryRepository; `src/aeat/application/modelo/_iva_wallet_seed.py`.
- [ ] `P01.S03` - Add a behaviour test: record override then assert the persisted taxpayer_override decision unblocks calculate and applies the amount to casilla 110 (persona 2T resolves to 525); `src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py`.

### Phase `P02` - Operator CLI surface + locales + conformance

Expose the recorder as the iva-wallet override verb with localized help/errors and conformance coverage, mirroring the seed/correct verbs.

- [ ] `P02.S04` - Register the iva-wallet override Typer verb with --filing-year --period --amount --reason --evidence-locator and mandatory default-off --confirm, refusing to overrule a fresh AEAT wallet decision; `src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py`.
- [ ] `P02.S05` - Add the IvaWalletOverrideResult output schema and register it for JSON-schema conformance; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [ ] `P02.S06` - Author override help/confirm/error locale leaves for en es ca hu via python -m aeat.locales set, then scaffold --check clean; `src/aeat/locales`.
- [ ] `P02.S07` - Add a CLI conformance test exercising the override verb end to end and run the documented-command conformance gate; `src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py`.

## Description

Implement the operator-facing IVA-wallet override verb decided in the
`iva-compensation-override-cli` ADR. The Modelo 303 cross-period compensación
carry is fully wired and safety-gated, but a local-only filer cannot complete it:
the reconciliation correctly blocks auto-applying a seeded or local prior balance
without live AEAT wallet evidence, and no CLI verb records the explicit taxpayer
override the block demands. The override machinery already exists end to end
(`IvaCompensationOverride` -> `_override_reconciliation_decision` -> persisted
`taxpayer_override` decision -> `apply_iva_compensation_decision_binding` writes
casilla 110); this plan adds the thin recording surface over it. The work mirrors
the existing `seed` and `correct` verbs (application wrapper in
`_iva_wallet_seed.py`, Typer verb in `_modelo_iva_wallet_cli.py`, locale leaves
via the `aeat.locales` CLI, conformance tests). It carries the safety invariants
from the ADR: mandatory provenance (reason + evidence locator), default-off
`--confirm`, single decision write path, no AEAT write, and no override of a
fresh AEAT wallet decision. The sticky-persisted-decision refresh and the
dependent-period verify gate (which still requires official external evidence)
are explicitly out of scope here.

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorizing documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

Phase `P01` (the application recorder and its behaviour test) must land before
Phase `P02` (the CLI surface), because the verb wraps the recorder. Within `P01`,
`S01` precedes `S02` and `S03`. Within `P02`, `S04` and `S05` may proceed
together; `S06` (locales) gates `S07` (the conformance test renders localized
help). The whole feature must not be sequenced ahead of, or merged into, the
active peer cross-period-filing-deadlock work that touches the same subsystem;
coordinate so the two land independently.

## Verification

- `P01`: a real save -> load behaviour test shows recording an override persists
  exactly one `taxpayer_override` decision for the period, and a subsequent
  `work calculate` applies the amount to casilla 110 (the persona 2T resolves to
  525, not 945). The override decision supersedes a stale `first_period_zero`
  decision for that period.
- `P01`: the override write emits one audit event carrying the reason and
  evidence locator; an override with empty reason or evidence locator is refused
  at the model boundary.
- `P02`: `python -m aeat.locales scaffold --check` and `audit` exit clean after
  the new leaves land; inter-locale and honesty parity gates stay green.
- `P02`: the documented-command conformance gate and the JSON-schema conformance
  gate pass for the new verb; the CLI conformance test drives the verb end to end
  and asserts the envelope reports the recorded override and the decided
  authority.
- The verb contacts AEAT zero times and refuses to overrule a fresh AEAT wallet
  decision; the dependent-period verify gate is unchanged (local override
  unblocks the calculation/carry, never the official-filing safety gate).
- The plan is complete when every Step is closed and a fresh-context review
  confirms the safety invariants from the ADR hold.
