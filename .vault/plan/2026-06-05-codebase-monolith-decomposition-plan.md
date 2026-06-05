---
tags:
  - '#plan'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
tier: L3
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
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
     Replace codebase-monolith-decomposition with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'. The related field
     carries the AUTHORISING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add frontmatter fields
     outside the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artifact: <Step Record>.
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
     in plan body. Authorising documents go in the plan's `related:`
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
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `codebase-monolith-decomposition` `codebase-wide monolith and cognitive complexity decomposition` plan

## Wave `W01` - global inventory and guard baseline

Establish authoritative current-state evidence for every production and test module over 1250 lines and every high-scoring function before selecting decomposition slices.

<!-- One-line headline summary plan. -->

### Phase `W01.P01` - inventory baseline

Persist the current over-1250-line module inventory and callable-size/cognitive-complexity inventory with exact and semantic discovery evidence.

- [x] `W01.P01.S01` - inventory every Python module over 1250 lines and classify production versus test scope; `src/aeat`.
- [x] `W01.P01.S02` - inventory high-length and high-branching callables as a cognitive-complexity proxy; `src/aeat`.

## Wave `W02` - CLI monolith decomposition

Reduce remaining CLI roots below the 1250-line objective through focused command registrars while preserving CLI-as-transport and backend-owned business logic.

### Phase `W02.P02` - ledger root continuation

Continue extracting coherent ledger command groups until _ledger.py moves materially toward the 1250-line objective without CLI-owned accounting policy.

- [x] `W02.P02.S03` - select the next coherent ledger command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W02.P02.S04` - extract the selected ledger command group into a focused registrar module; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_*.py`.
- [x] `W02.P02.S05` - verify selected ledger behavior and ratchet ledger root size after extraction; `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P02.S09` - select the next residual ledger command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P02.S10` - extract the selected residual ledger command group into a focused registrar module; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_*.py`.
- [x] `W02.P02.S11` - verify residual ledger behavior and ratchet ledger root size after extraction; `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

### Phase `W02.P03` - live and modelo root continuation

Continue reducing _app_live.py, _modelo.py, and config CLI roots after ledger slices, preserving command registrations and tests.

- [x] `W02.P03.S06` - select the next live CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P03.S12` - extract the selected live CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_*.py`.
- [x] `W02.P03.S13` - verify selected live CLI behavior and ratchet live root size after extraction; `src/aeat/entrypoints/cli/tests/test_live* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P03.S14` - select the next modelo CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P03.S15` - extract the selected modelo CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_*.py`.
- [x] `W02.P03.S16` - verify selected modelo CLI behavior and ratchet modelo root size after extraction; `src/aeat/entrypoints/cli/tests/test_modelo* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P03.S17` - select the next config CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/tests`.
- [x] `W02.P03.S18` - extract the selected config CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/*.py`.
- [x] `W02.P03.S19` - verify selected config CLI behavior and ratchet config root size after extraction; `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [ ] `W02.P03.S20` - select the next residual config or google CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests`.
- [ ] `W02.P03.S21` - extract the selected residual config or google CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/*.py`.
- [ ] `W02.P03.S22` - verify residual config or google CLI behavior and ratchet affected root size budgets; `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [ ] `W02.P03.S23` - select the next residual ledger CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/tests`.
- [ ] `W02.P03.S24` - extract the selected residual ledger CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_*.py`.
- [ ] `W02.P03.S25` - verify residual ledger CLI behavior and ratchet ledger root size budget; `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [ ] `W02.P03.S26` - select the next residual live CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/tests`.
- [ ] `W02.P03.S27` - extract the selected residual live CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_*.py`.
- [ ] `W02.P03.S28` - verify residual live CLI behavior and ratchet live root size budget; `src/aeat/entrypoints/cli/tests/test_live* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [ ] `W02.P03.S29` - select the next residual modelo CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/tests`.
- [ ] `W02.P03.S30` - extract the selected residual modelo CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_*.py`.
- [ ] `W02.P03.S31` - verify residual modelo CLI behavior and ratchet modelo root size budget; `src/aeat/entrypoints/cli/tests/test_modelo* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Wave `W03` - application and domain monolith decomposition

Decompose application/domain/backend monoliths only after ADR-backed boundary decisions identify safe seams and public facade preservation rules.

### Phase `W03.P04` - ADR bounded backend decomposition

Queue and execute ADR-backed decomposition for application, domain, adapter, persistence, and core modules over 1250 lines where safe boundaries require design decisions.

- [ ] `W03.P04.S07` - queue ADRs for application/domain/adapter/core monoliths whose decomposition requires boundary decisions; `.vault/adr src/aeat/application src/aeat/domain src/aeat/adapters src/aeat/core`.
- [ ] `W03.P04.S08` - add or extend static guards proving no Python module exceeds 1250 lines and no tracked callable exceeds the complexity budget; `src/aeat/tests src/aeat/entrypoints/cli/tests`.

## Description

Deliver the codebase-wide monolith decomposition objective: no Python module over 1250 lines and no cognitively high-scoring function left unbroken or unbounded by an explicit guard. This plan starts from current-state inventory rather than prior assumptions, then decomposes the remaining CLI roots through focused registrars and queues ADR-backed backend decomposition for application/domain/adapter/core modules where boundaries require design decisions.

The immediate execution path is conservative: keep CLI modules as transports, preserve top-level application facades for consumers, and ratchet static guards after every slice. Backend monoliths are not split by string-moving; each decomposition must preserve domain ownership, storage contracts, and public re-export surfaces.

## Parallelization

Inventory and semantic discovery may run in parallel with exact `fd`/`rg` discovery. File edits, plan mutations, and budget ratchets must stay serialized. CLI command group extractions can run independently by subgroup once their command surfaces and tests are identified. Backend application/domain decomposition must be ADR-bounded before implementation because public facade and ownership decisions are part of the change.

## Verification

The plan is complete only when current-state evidence proves no Python module in `src/aeat` exceeds 1250 lines, no tracked callable exceeds the accepted complexity/length budget, all broad static guards pass, focused behavior tests pass for every extracted surface, `vaultspec-core vault plan check` passes, and exact plus semantic discovery show command transports consume backend/application services rather than owning business policy.
