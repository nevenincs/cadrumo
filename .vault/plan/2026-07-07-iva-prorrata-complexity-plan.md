---
tags:
  - '#plan'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-07'
tier: L3
related:
  - '[[2026-07-07-prorrata-especial-adr]]'
  - '[[2026-07-07-prorrata-sectores-diferenciados-adr]]'
  - '[[2026-07-07-prorrata-art104-tres-exclusions-adr]]'
  - '[[2026-07-07-prorrata-art105-cinco-interrupted-adr]]'
  - '[[2026-07-05-cross-period-prorrata-adr]]'
  - '[[2026-07-01-iva-complexity-hardening-scope-adr]]'
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
     Replace iva-prorrata-complexity with a kebab-case feature tag, e.g. #foo-bar.
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

# `iva-prorrata-complexity` plan

## Wave `W01` - Independent axes (art-104.Tres exclusions parallel-with art-105.Cinco interrupted)

The two least-entangled ADRs. art-104.Tres (denominator exclusions) and art-105.Cinco (interrupted-activity seeding) share no ledger-transaction field, no _iva_ledger apportionment routing, and no CLI verb; they overlap only on distinct functions in _prorrata_regularizacion.py and distinct additive iva.toml blocks. P01 and P02 therefore run in parallel, coordinated by per-file explicit-pathspec commits.

<!-- One-line headline summary plan. -->

### Phase `W01.P01` - art-104.Tres denominator exclusions

Ground the 6 real art-104.Tres exclusions and make the ledger volume-rollup a reconciliation pre-fill proposal (never a silent filed-volume authority), via a hybrid auto/operator exclusion classification.

- [ ] `W01.P01.S01` - Author the ley-37-1992 art-104 (art-104.Tres) legal entries with corpus_ref and required_text for the 6 real exclusions, correcting the stale subvenciones-no-vinculadas prose removed by Ley 3/2006; `src/aeat/_data/registry/aeat/legal/iva.toml`.
- [ ] `W01.P01.S02` - Add the Art104TresExclusion core enum and the operator-declared exclusion tag on the ledger transaction, with save/load roundtrip + anti-tautology proof; `src/aeat/core/, src/aeat/domain/transactions/_models.py`.
- [ ] `W01.P01.S03` - Filter the art-104.Tres exclusions from the annual volume rollup and keep it a reconciliation pre-fill proposal, never a silent filed-volume authority; `src/aeat/application/aggregation/_iva_ledger.py, src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [ ] `W01.P01.S04` - Surface the operator exclusion declaration at the CLI and the M303 exclusion metadata in the registry; `src/aeat/entrypoints/cli/, src/aeat/_data/registry/aeat/modelos/303/`.
- [ ] `W01.P01.S05` - Verify the exclusion classification against an AEAT worked example with no hand-computed expected values; `src/aeat/application/calculations/tests/`.

### Phase `W01.P02` - art-105.Cinco interrupted-activity seeding

Represent an interrupted ejercicio in the register and seed the resumed year with the lawful art-105.Cinco last-three-active-years global percentage (summed volumes, skipping the gap), advising honestly on insufficient history.

- [ ] `W01.P02.S06` - Extend the ley-37-1992 art-105 required_text with the art-105.Cinco clause, corpus-grounded; `src/aeat/_data/registry/aeat/legal/iva.toml`.
- [ ] `W01.P02.S07` - Add the interrupted-ejercicio marker/provenance to the register enums and the active/inactive history on ProrrataRegisterEntry; `src/aeat/core/_prorrata_register.py, src/aeat/domain/prorrata_register/__init__.py`.
- [ ] `W01.P02.S08` - Implement the last-three-active-years global seed walk (summed volumes via compute_prorrata_definitiva_anual, skipping the gap) and the insufficient-history advisory; `src/aeat/domain/prorrata_register/__init__.py, src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [ ] `W01.P02.S09` - Verify the interruption seed against a worked example with a genuine gap and no averaged percentages; `src/aeat/domain/prorrata_register/tests/`.

## Wave `W02` - Prorrata especial: regime-aware apportionment foundation

The foundational ledger-trio change. Especial makes the one shared ledger IVA aggregation regime-aware (per-input 100/0/general routing per LIVA art-106) and adds the typed input_classification axis to the transaction. Hard-collides with W01 and W03 on _models.py and _iva_ledger.py, so it runs after W01. It is the substrate that sectores (W03) extends.

### Phase `W02.P03` - especial per-input classification, apportionment and +10% advisory

Wire a typed per-input use-classification from the ledger into a regime-aware apportionment (100/0/general), and fire the settlement art-103.Dos.2 +10% mandatory-especial advisory. Consumes the existing classify_input_deduction substrate; general path stays byte-identical.

- [ ] `W02.P03.S10` - Author the ley-37-1992 art-103 and art-106 legal entries with corpus_ref + required_text, grounded in the bundled consolidated LIVA; `src/aeat/_data/registry/aeat/legal/iva.toml`.
- [ ] `W02.P03.S11` - Add the typed input_classification axis (core InputClassification) to the ledger transaction, operator-declared for especial buckets, with roundtrip + anti-tautology proof; `src/aeat/domain/transactions/_models.py`.
- [ ] `W02.P03.S12` - Make the shared ledger IVA apportionment regime-aware so especial routes each deducible cuota via _deductible_percentage_for (100/0/general), the general path stays byte-identical, and provenance carries the applied classification and percentage; `src/aeat/application/aggregation/_iva_ledger.py`.
- [ ] `W02.P03.S13` - Emit the settlement art-103.Dos.2 +10% mandatory-especial advisory Notice via is_especial_mandatory, non-blocking, both totals on Notice.context; `src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [ ] `W02.P03.S14` - Surface the per-input classification declaration at the CLI and the M303 especial classification metadata; `src/aeat/entrypoints/cli/, src/aeat/_data/registry/aeat/modelos/303/`.
- [ ] `W02.P03.S15` - Verify all three art-106 reglas (100/0/common) and the +10% comparison against an AEAT Manual practico worked example with no substrate-derived expected values; `src/aeat/application/aggregation/tests/`.

## Wave `W03` - Sectores diferenciados: per-sector extension

Extends especial's regime-aware aggregation to per-sector routing over the (ejercicio,sector)-keyed register (LIVA arts 101/9.1.c). Depends on W02 (regime-aware aggregation must exist) and collides with it on _models.py and _iva_ledger.py, so it runs last. Art-101.Dos common-deduction regime is deferred.

### Phase `W03.P04` - sector classification, per-sector orchestration and lifecycle

Operator-declared sector identification (CNAE/IAE) driving per-(ejercicio,sector) register orchestration and per-sector routing in the regime-aware aggregation, with a per-sector provisional/definitive lifecycle.

- [ ] `W03.P04.S16` - Author the ley-37-1992 art-101 legal entry corpus-grounded, noting the art-101.Dos common-deduction regime is deferred; `src/aeat/_data/registry/aeat/legal/iva.toml`.
- [ ] `W03.P04.S17` - Add operator-declared sector identification (CNAE/IAE) on the contribuyente profile and the sector reference on the ledger transaction; `src/aeat/domain/contribuyente/, src/aeat/domain/transactions/_models.py`.
- [ ] `W03.P04.S18` - Orchestrate per-(ejercicio,sector) register entries and per-sector routing in the regime-aware aggregation; `src/aeat/domain/prorrata_register/__init__.py, src/aeat/application/aggregation/_iva_ledger.py`.
- [ ] `W03.P04.S19` - Run the per-sector provisional/definitive lifecycle (seed and settlement per sector); `src/aeat/application/prorrata_register/, src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [ ] `W03.P04.S20` - Verify per-sector prorrata against a worked example with a greater-than-50-percentage-point sector spread; `src/aeat/domain/prorrata_register/tests/`.

## Description

Binds the four deferred IVA-prorrata "W06" axis ADRs (`prorrata-especial`,
`prorrata-sectores-diferenciados`, `prorrata-art104-tres-exclusions`,
`prorrata-art105-cinco-interrupted`) into one collision-free execution roadmap.
Each ADR concretises a slice the accepted `cross-period-prorrata` ADR explicitly
deferred, over the register / regime / sector schema that already exists from
birth (no migration). The four are clustered per-ADR (one Phase each) and grouped
into Waves by their code-surface footprint, so that any two axes sharing a
write-file never run concurrently. This plan authors no code; it only sequences
the future implementation, grounded verbatim in the bundled consolidated LIVA
(`ley-37-1992.html`, arts 101 / 103 / 104.Tres / 105.Cinco / 106).

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

Wave separation is derived from the ADR-vs-ADR write-file footprint matrix, not
assumed. The three ledger-touching axes - especial (E, W02), sectores (S, W03)
and art-104.Tres exclusions (X, W01.P01) - all WRITE the same two hot surfaces
(`domain/transactions/_models.py` and `application/aggregation/_iva_ledger.py`)
plus the M303 registry and the CLI ledger surface, so no two of them may run
concurrently. art-105.Cinco (I, W01.P02) is deliberately register / seeding
internal: it touches no transaction field, no apportionment routing and no CLI
verb, overlapping X only on a distinct function in `_prorrata_regularizacion.py`
and a distinct additive `iva.toml` block. Sectores additionally carries a logical
dependency on especial - it extends the regime-aware aggregation especial
establishes - so E must land before S regardless of the collision.

Resulting collision-free ordering:

- `W01` runs its two Phases IN PARALLEL: `W01.P01` (X) alongside `W01.P02` (I).
  This is the only parallel-safe pair. Their sole shared files are distinct
  functions in `_prorrata_regularizacion.py` (X extends the volume-divergence
  advisory; I adds the interrupted-seed branch) and distinct additive
  `[legal."ley-37-1992:art-104"]` vs `art-105` blocks in `iva.toml`; each Phase
  commits only its own files via explicit pathspec, so there is no line-level
  conflict.
- `W02` (E) is serial after W01: it rewrites the shared `_models.py` /
  `_iva_ledger.py` apportionment that X touched, and establishes the regime-aware
  aggregation W03 needs.
- `W03` (S) is serial last: it depends on E and collides with both E and X on the
  shared ledger surfaces.

Every Step declares its `path/to/file` scope; two Steps in different concurrent
Phases never share a write-scope. The four `iva.toml` legal-entry Steps (S01, S06,
S10, S16) each append a distinct, non-overlapping `[legal."..."]` block and are
safe under explicit-pathspec even when their Phases share Wave W01.

## Verification

The plan is complete when all 20 Steps are closed. Every Wave lands only against
these verifiable criteria:

- Legal grounding: each regulated rule/figure is grounded verbatim in the bundled
  `ley-37-1992` corpus (arts 101 / 103 / 104.Tres / 105.Cinco / 106) with a
  `required_text` cross-check; zero fabricated values.
- Roundtrip: each new persisted field (the art-104.Tres exclusion tag,
  `input_classification`, the sector reference, the interrupted-ejercicio marker)
  passes a strict save / load / equality roundtrip plus an anti-tautology proof.
- Oracle grounding: each apportionment / seed behaviour is proven against an AEAT
  Manual practico worked example, never against numbers hand-computed from the
  compute substrate.
- Byte-identity: the general (non-especial, single-sector, no-exclusion) path
  stays byte-identical to the landed cross-period-prorrata behaviour.
- Non-silence: every unclassified input, insufficient interruption history,
  mandatory-especial breach, or ledger-vs-declared divergence surfaces an advisory
  Notice, never a silent assumed value or a blocking refusal of a legitimate
  in-progress filing.
- Gate: each Wave closes with `vault plan check` clean and the focused prorrata
  test slice green under `-n0` on a settled tree, with owner-distinction against
  concurrent worktree churn.
