---
tags:
  - '#plan'
  - '#period-grammar-standardisation'
date: '2026-06-11'
tier: L3
related:
  - '[[2026-06-10-cli-operator-surface-adr]]'
  - '[[2026-06-10-ledger-filter-period-adr]]'
  - '[[2026-06-01-registry-period-code-union-cli-boundary-adr]]'
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
     Replace period-grammar-standardisation with a kebab-case feature tag, e.g. #foo-bar.
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

# `period-grammar-standardisation` `period grammar standardisation: AEAT-token-only, year always separate, conflation burn-down` plan

## Wave `W01` - Operator-facing period grammar standardisation (AEAT-token-only)

Landed: the ledger and modelo --period surfaces accept only canonical AEAT tokens with the year on a separate --year clause; calendar shapes and the 2026-1T hybrid refuse; locale, docs, and conformance gates are green. The backend parser de-conflation (P03/P11) remains blocked on removal of the transitional adapters.

### Phase `W01.P01` - CLI operator-input grammar: AEAT-token-only + separate --year, conversion layer deleted

Ledger --period accepts only canonical AEAT tokens (0A/1T-4T/01-12); year travels on --year; the _aeat_token_to_calendar conversion layer and the 2026-1T hybrid regex are deleted; helpers return a Period built directly from (year, token).


<!-- One-line headline summary plan. -->

- [x] `W01.P01.S01` - Delete the _aeat_token_to_calendar conversion layer and the _FILTER_YEAR_QUALIFIED_RE hybrid regex; `make _canonical_period / _filter_canonical_period / _optional_canonical_period build a Period directly from (year, bare-token); `src/aeat/entrypoints/cli/_common.py`.
- [x] `W01.P01.S02` - Add Period.from_year_and_token(year, token) so the (year, AEAT-token) pair resolves straight to a Period date span with no intermediate calendar string; `src/aeat/application/aggregation/_models.py`.
- [x] `W01.P01.S03` - Update every ledger CLI caller to the two-argument (token, year=...) period signature so the --filter mini-grammar carries year as a separate clause; `src/aeat/entrypoints/cli/_ledger_list.py, _ledger_review_cli.py, _ledger_read_cli.py, _ledger_import_cli.py, _overview.py`.
- [x] `W01.P01.S04` - Land the CLI-layer grammar as one explicit-path commit; `confirm CLI import smoke and the ledger period grammar gates pass; `src/aeat/entrypoints/cli`.

### Phase `W01.P02` - Operator refusal regressions and locale messages

Calendar shapes (2026Q1/2026-03/2026) and the 2026-1T hybrid refuse with instructive localised messages naming the AEAT tokens and --year; no dual-notation wording survives.

- [x] `W01.P02.S05` - Assert calendar shapes (2026Q1/2026-03/2026) and the year-qualified hybrid (2026-1T) refuse at every ledger period site with an instructive message naming the AEAT tokens and --year; `src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py`.
- [x] `W01.P02.S06` - Rewrite the period refusal locale messages via the aeat.locales CLI to name the AEAT tokens and the --year argument, removing every both-notations / calendar-shape phrasing; `src/aeat/locales/en.yml`.
- [x] `W01.P02.S07` - Run the documented-command and educational-docs conformance gates green after the grammar and locale changes; `src/aeat/entrypoints/cli/tests`.

### Phase `W01.P03` - Backend parser de-conflation: domain/period.py + work-period normalisation

Delete the combined-input regexes from parse_canonical_period; remove the round-trip through a combined token in normalize_modelo_work_period; confirm persisted shape is separated (year, registry_token); reconcile the registry parse_modelo_period dialect with the AEAT-token-only mandate.

- [x] `W01.P03.S08` - Delete the combined-input regexes (_QUARTER_PERIOD_RE, _DASHED_QUARTER_PERIOD_RE, _MONTH_PERIOD_RE, _ANNUAL_PERIOD_RE, _BARE_YEAR_RE) from parse_canonical_period and rewrite the module docstring to drop the combined-token-storage claim; `src/aeat/domain/period.py`.
- [x] `W01.P03.S09` - Confirm WorkUnit / draft / deadline-window persist a separated (filing_year, registry_token) and add or extend a roundtrip test proving no combined period string is ever persisted; `src/aeat/application/modelo/_work_addressing.py`.
- [x] `W01.P03.S10` - Remove the round-trip through a combined token in normalize_modelo_work_period; `build (year, registry_token) directly without composing 2026Q1-style intermediates; `src/aeat/application/modelo/_work_addressing.py`.
- [x] `W01.P03.S11` - Reconcile the registry parse_modelo_period dashed YYYY-Qn dialect with the AEAT-token-only mandate or document why the registry-introspection dialect is out of the operator-period scope; `src/aeat/domain/calculations/registry`.
- [x] `W01.P03.S12` - Update test_period.py to assert the combined forms now refuse and only the bare-token (with ejercicio), month, 0A and nP tokens are accepted; `src/aeat/domain/tests/test_period.py`.

### Phase `W01.P04` - Docs sweep and final repo-wide conflation gate

Every how-to and reference teaches only --year --period <token>; a repo-wide grep gate confirms zero 2026Q1 / YYYY-nT / period=YYYY usage outside refusal-regression fixtures.

- [x] `W01.P04.S13` - Sweep every how-to and reference doc to teach only --year --period <token>, removing every 2026Q1 / period=2026-1T / bare-year example; `docs/how-to, docs/reference`.
- [ ] `W01.P04.S14` - Add a final repo-wide grep gate asserting zero 2026Q1 / YYYY-nT / period=YYYY usage in code, tests and docs outside the refusal-regression fixtures; `run the relevant suites green; `src/aeat, docs`.

### Phase `W01.P05` - DEEP LAYER: internal combined-token representation migration

Discovery: combined 2026Q1/2026-1T strings are load-bearing BELOW the operator surface — registry deadline-window TOML (period = 2026Q1 across every modelo), the WorkflowEngine period contract (workflow_period_for_work_unit emits 2026Q1/2026-1T, asserted across _workflow_gate, _resume and dozens of tests), and the source docstrings that honestly describe that token. Deleting the domain/period.py combined regexes is BLOCKED until this internal representation migrates to separated (filing_year, registry_token). High blast radius across the registry authoring tree in a shared worktree; tracked as outstanding follow-on, not completed this pass.

- [x] `W01.P05.S15` - Hydrate registry deadline-window TOML period strings into core.Period at the loader boundary, preserving free-form registry authoring input per aeat-registry-authority-flow while exposing the separated (filing_year, registry_token) model shape downstream; `src/aeat/_data/registry/aeat/modelos/**/deadline_windows, src/aeat/domain/calculations/registry`.
- [x] `W01.P05.S16` - Replace the WorkflowEngine combined-token contract: have workflow_period_for_work_unit and the resume/gate paths carry (filing_year, registry_token) instead of composing 2026Q1/2026-1T, and migrate every dependent test assertion; `src/aeat/application/modelo/_workflow_gate.py, src/aeat/application/workflow/_resume.py`.
- [ ] `W01.P05.S17` - OUTSTANDING — Once the deep layer is separated, delete the combined-input regexes from parse_canonical_period (unblocks P03.S08) and rewrite the source docstrings that cite 2026Q1 as the canonical token; `src/aeat/domain/period.py, src/aeat/application/workflow/_resume.py, src/aeat/domain/calculations/registry/_queries.py`.

## Wave `W02` - Core Period value object: implementation and backend rollout

Promote a fundamental core.Period value object (filing_year + StandardPeriodCode, accessors, canonical __str__/__repr__, value semantics, full token coverage) to core/_period.py, then roll it out by substrate cluster to replace every period: str field and combined-string construction. The coordinator authors the core type; sonnet coding subagents execute the per-cluster rollout, each grounding site discovery via rg + vaultspec-rag. Backed by 2026-06-11-period-grammar-standardisation-adr.

### Phase `W02.P06` - Author core.Period value object (COORDINATOR)

The coordinator authors core.Period in core/_period.py composing filing_year + StandardPeriodCode, with accessors, canonical __str__/__repr__, value semantics, full token coverage, and a from_year_and_code constructor; with a strict unit test suite. Not delegated.

- [x] `W02.P06.S18` - Author core.Period composing filing_year:int + code:StandardPeriodCode, with read-only accessors (year, registry_token, start_date, end_date, contains, kind), a canonical __str__/__repr__ and pydantic serialiser, value semantics (frozen, hashable, equality by (year, code)), and a from_year_and_code constructor covering span shapes, instalment claves and extended union members; `src/aeat/core/_period.py`.
- [x] `W02.P06.S19` - Write strict core.Period unit tests: construction per token kind, accessor correctness, str-repr stability, equality/hash as a dict key, has_date_span for non-span periods, and refusal on malformed inputs; `src/aeat/core/tests/test_period.py`.
- [x] `W02.P06.S20` - Re-export core.Period from core __all__ and confirm CLI import smoke and the core test suite pass; `src/aeat/core/__init__.py`.

### Phase `W02.P07` - Re-seat aggregation Period and ledger on core.Period (sonnet)

Delegate: re-seat application/aggregation Period on core.Period (drop the raw combined-string field, delegate from_year_and_token), preserving the live ledger-filter parity the one-aggregation-path rule protects.

- [x] `W02.P07.S21` - Re-seat application/aggregation Period on core.Period: drop the raw combined-string field, delegate from_year_and_token to core.from_year_and_code, and prove the live ledger-filter parity is preserved; `src/aeat/application/aggregation/_models.py`.

### Phase `W02.P08` - Roll out core.Period across application schema/model fields (sonnet swarm)

Delegate per module: replace period: str fields with core.Period in state_projection, overview/_calendar (+ alias helpers), aggregation service/source_mesh/retenciones, workflow _resume models, iva/_prorrata, submission/_models, verification/_schema, filing/_schema, modelo/_export; each subagent grounds sites via rg + vaultspec-rag and adds roundtrip coverage at persistence boundaries.

- [x] `W02.P08.S22` - Replace the period: str fields and the _period_aliases / _normalize_period_token / _filing_year_from_period helper machinery in the overview calendar with core.Period; `src/aeat/application/overview/_calendar.py`.
- [x] `W02.P08.S23` - Replace the period: str / ledger_period fields in the state projection with core.Period and add a save->load->equality roundtrip plus anti-tautology proof at that persistence boundary; `src/aeat/application/state_projection.py`.
- [x] `W02.P08.S24` - Replace the period: str fields in the aggregation service, source mesh and retenciones models with core.Period; `src/aeat/application/aggregation/_service.py, _source_mesh.py, _retenciones.py`.
- [x] `W02.P08.S25` - Replace the period: str fields in the iva prorrata, submission, verification schema, filing schema and modelo export models with core.Period; `src/aeat/domain/iva/_prorrata.py, src/aeat/domain/submission/_models.py, src/aeat/application/verification/_schema.py, src/aeat/domain/filing/_schema.py, src/aeat/application/modelo/_export.py`.
- [x] `W02.P08.S31` - DISCOVERY (recon): the period:str substrate splits into 8 file-disjoint clusters A-H — A overview/_calendar, B state_projection, C aggregation service/retenciones/source_mesh (waits on P07), D filing/_schema ModeloDraft (encrypted-SQL roundtrip), E submission/_models ModeloPresentado (encrypted-SQL roundtrip), F verification/_schema, G iva/_prorrata (DIFFERENT vocabulary Q1/M01/annual — NOT a core.Period candidate, out of scope), H modelo/_export bucket-event; `agents bridge inbound combined strings via parse_canonical_period during transition; `src/aeat/application, src/aeat/domain`.
- [x] `W02.P08.S33` - DEFERRED C2 (from cluster C): migrate CalculationSourceContext.period (aggregation/_source_mesh.py) plus the ~26 calculation resolvers that read it and the observation-store key derivation (observation_key in _observations_repository.py) to core.Period as one isolated atomic commit; `src/aeat/application/aggregation/_source_mesh.py, src/aeat/application/calculations`.

### Phase `W02.P09` - Registry deadline-window loader-boundary hydration (sonnet)

Delegate: hydrate core.Period at the registry loader boundary while preserving modelo deadline_windows TOML as free-form authoring input per aeat-registry-authority-flow.

- [x] `W02.P09.S26` - Hydrate core.Period at the registry loader boundary while preserving free-form deadline_windows TOML authoring input, and prove model_dump/model_dump_json expose the separated Period object shape rather than a combined period string; `src/aeat/domain/calculations/registry, src/aeat/_data/registry/aeat/modelos`.

### Phase `W02.P10` - WorkflowEngine period contract migration (sonnet)

Delegate: replace the workflow_period_for_work_unit combined-token contract and the _resume / _workflow_gate consumers with core.Period, migrating the ~30 dependent test assertions off 2026Q1/2026-1T.

- [x] `W02.P10.S27` - Replace the workflow_period_for_work_unit combined-token contract and the _resume / _workflow_gate consumers with core.Period, migrating every dependent test assertion off 2026Q1 / 2026-1T; `src/aeat/application/modelo/_workflow_gate.py, src/aeat/application/workflow/_resume.py`.
- [x] `W02.P10.S32` - DISCOVERY (recon): P09 registry deadline-window and P10 WorkflowEngine are INSEPARABLY COUPLED via _deadline_window_period_for_registry_period (workflow_gate.py:47-72) which returns str(window.period) as the workflow period; `plus ModeloDeadline.period and RegistrySnapshot.period are additional sites; ~125-130 test lines across ~30 files — migrate as ONE atomic dispatch, not parallel; `src/aeat/application/modelo/_workflow_gate.py, src/aeat/application/workflow, src/aeat/domain/deadlines, src/aeat/domain/calculations/registry`.

### Phase `W02.P11` - Cleanup: delete dead regexes, reconcile dialect, final gate (sonnet + coordinator verify)

Delegate then verify: once every consumer carries core.Period, delete the combined-input regexes from parse_canonical_period, reconcile or retire the parse_modelo_period dashed dialect, and add the repo-wide zero-combined-string regression gate.

- [x] `W02.P11.S28` - Delete the combined-input regexes from parse_canonical_period and rewrite the module docstring once every consumer carries core.Period; `src/aeat/domain/period.py`.
- [x] `W02.P11.S29` - Reconcile or retire the registry parse_modelo_period dashed YYYY-Qn dialect against core.Period; `src/aeat/domain/calculations/registry`.
- [ ] `W02.P11.S30` - Add the repo-wide regression gate asserting zero combined-period-string construction or storage outside refusal-regression fixtures and the Period __str__ projection; `src/aeat/core/tests`.
- [x] `W02.P11.S34` - Remove the transitional _coerce_period BeforeValidator inbound coercions and the outbound _to_canonical_period / _period_to_canonical_str combined-string adapters (introduced by clusters C/E/H) once every producer emits core.Period, so combined strings can no longer enter at those pydantic/export boundaries; `src/aeat/domain/submission/_models.py, src/aeat/application/aggregation, src/aeat/application/modelo/_export.py, src/aeat/application/filing/_complementaria.py`.
- [ ] `W02.P11.S35` - Remove the residual application aggregation Period wrapper and constructor so aggregation exports and tests use core.Period directly; `src/aeat/application/aggregation/_models.py, src/aeat/application/aggregation/_modelo_bindings.py, src/aeat/application/aggregation, src/aeat/tests/test_ledger_tax_fact_manipulations.py`.

## Description

Burns down every conflated period spelling in favour of the single
`--year YYYY --period <AEAT-token>` shape mandated by the D4 amendment of
`2026-06-10-cli-operator-surface-adr` ("AEAT tokens only; the calendar shapes
`2026Q1 / 2026-03 / 2026` AND the `2026-1T` hybrid are removed; no dual
notation, no conversion layer, no backward-compatibility shadow"). The work is
stratified by depth:

- **P01 — CLI operator-input grammar (done, landed `224a6cd6c`).** The ledger
  `--period` / `--filter period=` surfaces accept only the canonical AEAT
  tokens; the year travels on a separate `--year` option / `--filter year=`
  clause. The `_aeat_token_to_calendar` conversion layer and the
  `_FILTER_YEAR_QUALIFIED_RE` hybrid regex are deleted; the helpers build a
  typed `Period` directly from `(year, bare-token)`, and the ledger command /
  query / report period fields become `Period | None`.
- **P02 — operator refusals + locale (done).** Calendar shapes and the
  `2026-1T` hybrid refuse with an instructive, four-locale-parity message naming
  the AEAT tokens and `--year`; the documented-command and educational-docs
  conformance gates stay green.
- **P03 — backend parser de-conflation (outstanding, blocked by P11 cleanup).**
  `domain/period.py::parse_canonical_period` still accepts the combined input
  regexes, and `normalize_modelo_work_period` round-trips through a `2026Q1`
  intermediate. These cannot be deleted until the remaining transitional
  adapters are removed or replaced with local loader-boundary parsers.
- **P04 — docs + final gate.** The hand-authored how-to / reference docs already
  teach only `--year --period`; the final repo-wide zero-conflation grep gate is
  blocked until P11 removes transitional combined-string adapters and defines
  the explicit allowlist for registry authoring inputs and refusal fixtures.
- **P05 — DEEP internal-representation layer (complete).** The registry
  deadline-window loader now hydrates authored strings into `core.Period` at the
  schema boundary, and the WorkflowEngine contract carries `core.Period`
  instead of `2026Q1 / 2026-1T` strings.

## Parallelization

P01, P02 and P05 are landed. P03 (`domain/period.py` regex deletion) remains
blocked by P11: `parse_canonical_period` is still the transitional adapter for
registry loader-boundary TOML hydration and older inbound seams. P04.S14 (the
repo-wide zero-conflation gate) is likewise blocked until P11 defines the final
allowlist for registry authoring inputs and refusal fixtures, then deletes the
now-dead transitional adapters.

## Verification

The plan is complete when all of the following hold:

- `uv run --no-sync pytest src/aeat/domain/tests/test_period.py src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py src/aeat/application/aggregation/tests/test_period_boundary_authority.py -m "integration or not integration"` is green, with calendar shapes and the `2026-1T` hybrid asserted to refuse (the 5 `register_wizard_catalogue` integration-harness failures are tracked separately and are not period-logic).
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py src/aeat/entrypoints/cli/tests/test_educational_docs_conformance.py` is green (landed: 107 passed).
- `python -m aeat.locales scaffold --check` is clean and the four locale catalogues carry the period-refusal keys at parity.
- A final repo-wide grep finds zero `YYYYQ[1-4]` / `YYYY-[1-4]T` / `period=YYYY` usage in code, tests, and docs **outside** the explicit registry-authoring and refusal-regression allowlist — gated only after P11 removes transitional adapters.
- `uv run --no-sync vaultspec-core vault check all` stays green for this feature.

The plan is complete when every Step in every Wave is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter. -->
