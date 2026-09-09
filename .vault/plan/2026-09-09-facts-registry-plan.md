---
tags:
  - '#plan'
  - '#facts-registry'
date: '2026-09-09'
tier: L3
related:
  - '[[2026-09-09-facts-registry-governed-fact-catalogue-adr]]'
  - '[[2026-09-09-facts-registry-discovery-blast-radius-research]]'
  - '[[2026-09-09-facts-registry-schema-persistence-research]]'
  - '[[2026-09-09-facts-registry-authority-plumbing-research]]'
  - '[[2026-09-09-facts-registry-dev-tooling-research]]'
modified: '2026-09-09'
body_schema: body-v2
body_hash: 'sha256:3a0b9188777a1c822abf29f4dac1d1e2f92b3947ba1696bfa15d2b35438ab35a'
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
     Replace facts-registry with a kebab-case feature tag, e.g. #foo-bar.
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

# `facts-registry` plan

Build one governed-fact authority, migrate every classified consumer, and
delete the superseded value, loader, cache, and data paths.

## Description

This L3 campaign implements the accepted sibling-catalogue decision. Wave 1
builds the new architecture without changing legacy providers or consumers,
while a parallel lane completes the exact migration and deletion ledger. Wave
2 enrolls providers. Wave 3 migrates consumers by independent domain. Wave 4
normalises facts and removes the obsolete architecture. Wave 5 performs the
final engineering handoff. Verification is concentrated at Wave boundaries;
individual coding Steps do not each carry a redundant test or review Step.

## Steps

## Wave `W01` - Build the authority core and close the target ledger

Build the new facts architecture without modifying legacy consumers while a parallel lane produces the exact migration and deletion ledger. Wave W02 depends on both outputs.

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

### Phase `W01.P01` - Implement greenfield facts contracts

Create the registry-owned envelope, closed payload families, typed queries, and resolved result contracts without touching existing domain loaders or consumers.

- [x] `W01.P01.S01` - Define governed fact envelope identities and payload families; `src/cadrumo/domain/calculations/registry/facts/schema.py`.
- [ ] `W01.P01.S02` - Define typed queries and provenance-bearing resolved results; `src/cadrumo/domain/calculations/registry/facts/resolution.py`.
- [ ] `W01.P01.S03` - Implement strict one-fact-per-file TOML parsing; `src/cadrumo/domain/calculations/registry/facts/loader.py`.

### Phase `W01.P02` - Implement greenfield provider authority

Add provider enrollment, catalogue compilation, authority identity, validation, fingerprint, memoisation, reset, and directory-ownership plumbing without migrating legacy providers.

- [ ] `W01.P02.S04` - Implement provider registration and directory ownership; `src/cadrumo/domain/calculations/registry/facts/providers.py`.
- [ ] `W01.P02.S05` - Attach the fact catalogue to authority construction; `src/cadrumo/domain/calculations/registry/authority.py`.
- [ ] `W01.P02.S06` - Enroll facts in fingerprints authority identity memoisation validation and resets; `src/cadrumo/domain/calculations/registry`.

### Phase `W01.P03` - Complete migration and retirement ledger

Classify every discovered candidate and record exact source symbols, consumers, destination fact families, migration dependencies, and files or symbols to delete, retain, or rewire.

- [x] `W01.P03.S07` - Classify every statutory declaration and production consumer; `src/cadrumo/core/external_constants.py`.
- [ ] `W01.P03.S08` - Record exact IVA recargo grounding and repository retirement conditions; `src/cadrumo/domain/iva`.
- [ ] `W01.P03.S09` - Record exact global legal-parameter adapter callers and closure conditions; `src/cadrumo/domain/calculations/registry/loader.py`.
- [ ] `W01.P03.S42` - Record retained domain facades and excluded technical configuration readers; `src/cadrumo/domain and src/cadrumo/core/external_constants.py`.

### Phase `W01.P04` - Build facts quality tooling

Create catalogue-denominated structural gates and a broad report-only discovery sentinel while preserving modelo-specific tooling.

- [ ] `W01.P04.S10` - Implement provider ownership identity temporal precedence and provenance gates; `dev/registry/analysis`.
- [x] `W01.P04.S11` - Implement the report-only governed-literal discovery sentinel; `dev/registry/analysis`.
- [ ] `W01.P04.S12` - Enroll facts checks without changing modelo denominators; `dev/quality/suite.py`.

### Phase `W01.P23` - Verify foundation boundary

At the Wave 1 handoff, run strict production typing and the two complementary dead-code signals after the greenfield architecture and retirement census converge.

- [ ] `W01.P23.S43` - Run canonical strict production type checking at the Wave 1 handoff; `justfile check-types and dev/quality/types.py`.
- [ ] `W01.P23.S44` - Run the reviewed-whitelist Vulture audit at the Wave 1 handoff; `justfile audit-dead-code and dev/audit/dead_code.py`.
- [ ] `W01.P23.S45` - Run shipped-entrypoint reachability at the Wave 1 handoff; `justfile audit-unreachable-code and dev/audit/unreachable_code.py`.

## Wave `W02` - Enroll governed data providers

Register existing data-backed domains behind the new authority in parallel, preserving their public behavior until their consumers migrate. Wave W03 depends on provider parity at this boundary.

### Phase `W02.P05` - Enroll IVA and recargo providers

Adapt IVA schedules, recargo schedules, typed lookup behavior, evidence, and precedence into authority-managed providers.

- [ ] `W02.P05.S13` - Register IVA rate schedules as typed dated provider adapters; `src/cadrumo/domain/iva/rates.py`.
- [ ] `W02.P05.S14` - Register recargo by applied rate and operation date; `src/cadrumo/domain/iva/recargo_equivalencia.py`.
- [ ] `W02.P05.S15` - Move IVA evidence enforcement into provider validation; `src/cadrumo/domain/iva/_grounding.py`.

### Phase `W02.P06` - Enroll categories and calendar providers

Adapt category profiles and legally governed calendar or deadline data into authority-managed providers.

- [ ] `W02.P06.S16` - Register statutory category profiles and dated caps; `src/cadrumo/domain/categories/registry.py`.
- [ ] `W02.P06.S17` - Register classified legal calendar and deadline facts; `src/cadrumo/domain/deadlines`.

### Phase `W02.P07` - Enroll treaty and authorisation providers

Adapt convenio overrides and apoderamientos catalogues into authority-managed providers.

- [ ] `W02.P07.S18` - Register convenio overrides as a typed provider adapter; `src/cadrumo/domain/calculations/registry/convenio.py`.
- [ ] `W02.P07.S19` - Register confirmed apoderamientos legal-taxonomy facts; `src/cadrumo/domain/auth/apoderamientos/catalogue.py`.

### Phase `W02.P08` - Enroll scalar and revision-backed facts

Enroll external-constant candidates and already revision-backed duplicate values through typed scalar, bracket, set, and date-window providers.

- [ ] `W02.P08.S20` - Register statutory scalars schedules and classifications; `src/cadrumo/core/external_constants.py`.
- [ ] `W02.P08.S21` - Adapt global legal parameters without duplicating authority; `src/cadrumo/_data/registry/aeat/legal`.
- [ ] `W02.P08.S22` - Project modelo-owned facts without moving parameter files; `src/cadrumo/_data/registry/aeat/modelos`.

### Phase `W02.P09` - Verify provider boundary

Exercise provider compilation, identity, cache invalidation, exact resolution, and provenance once all provider phases converge.

- [ ] `W02.P09.S23` - Verify provider compilation exact resolution and provenance at the Wave 2 handoff; `src/cadrumo/domain/calculations/registry/tests`.
- [ ] `W02.P09.S46` - Run canonical strict production type checking at the Wave 2 handoff; `justfile check-types and dev/quality/types.py`.
- [ ] `W02.P09.S47` - Run both dead-code audits at the Wave 2 handoff; `dev/audit/dead_code.py and dev/audit/unreachable_code.py`.

## Wave `W03` - Migrate consumers by legal domain

Move every classified consumer to typed provenance-bearing fact resolution in parallel domain phases. Wave W04 depends on closure of each domain migration ledger.

### Phase `W03.P10` - Migrate declaration and aggregation consumers

Rewire M347, M202, declaration thresholds, modelo group classifications, and aggregation consumers.

- [ ] `W03.P10.S48` - Rewire every M347 comparator validator and diagnostic to one fact; `src/cadrumo/domain/calculations/registry/_m347_threshold.py and dependent production callers`.
- [ ] `W03.P10.S49` - Rewire Modelo 202 and modelo classification consumers; `src/cadrumo/domain/calculations/registry/applicability_modelo202.py and src/cadrumo/application/aggregation/_service.py`.

### Phase `W03.P11` - Migrate renta and family consumers

Rewire maritime, maternity, descendant, Madrid, Art 20, Art 52, DT12, and SAL consumers.

- [ ] `W03.P11.S24` - Rewire maritime Art 7p and REBECA inputs; `src/cadrumo/domain/renta/maritime_exemption.py`.
- [ ] `W03.P11.S25` - Rewire descendant maternity custody and Madrid windows; `src/cadrumo/domain/contribuyente`.
- [ ] `W03.P11.S50` - Rewire Art 20 Art 52 DT12 and SAL calculations; `src/cadrumo/application/modelo and src/cadrumo/domain/modelos`.

### Phase `W03.P12` - Migrate IVA and invoice consumers

Rewire invoice rate interpretation, IVA calculations, recargo lookup, inventory defaults, and extraction authority consumers.

- [ ] `W03.P12.S26` - Rewire IVA lookups while preserving domain facades; `src/cadrumo/domain/iva`.
- [ ] `W03.P12.S27` - Rewire invoice slot percentage interpretation; `src/cadrumo/domain/invoices/enums.py`.
- [ ] `W03.P12.S51` - Rewire extraction recargo aggregation and inventory defaults; `src/cadrumo/application/ledger and src/cadrumo/application/aggregation and src/cadrumo/domain/contribuyente/inventory`.

### Phase `W03.P13` - Migrate treaty authorization and deadline consumers

Rewire convenio, apoderamientos, notification deadlines, amendment regimes, foreign-asset rules, and related mappings.

- [ ] `W03.P13.S52` - Rewire treaty and authorization consumers; `src/cadrumo/domain/calculations/registry/_formula_runtime_irnr.py and src/cadrumo/entrypoints/cli/config_payloads.py`.
- [ ] `W03.P13.S53` - Rewire deadline notification amendment and foreign-asset facts; `src/cadrumo/domain/deadlines and src/cadrumo/core`.

### Phase `W03.P14` - Verify consumer boundary

Exercise cross-domain resolution and provenance after all consumer migrations converge.

- [ ] `W03.P14.S28` - Verify cross-domain parity temporal selection and provenance at the Wave 3 handoff; `src/cadrumo`.
- [ ] `W03.P14.S54` - Run canonical strict production type checking at the Wave 3 handoff; `justfile check-types and dev/quality/types.py`.
- [ ] `W03.P14.S55` - Run both dead-code audits and add exact findings to the retirement ledger; `dev/audit/dead_code.py and dev/audit/unreachable_code.py`.

## Wave `W04` - Normalize facts and delete legacy authority paths

Move authored facts into the normalized facts corpus where approved, remove duplicate constants, loaders, caches, files, and imports, and make forbidden paths fail the quality gates. Wave W05 depends on a zero-open-item retirement ledger.

### Phase `W04.P15` - Normalize authored fact corpus

Move approved adapted data families and Python-held facts into one-fact-per-file normalized TOML while retaining source evidence.

- [ ] `W04.P15.S29` - Author normalized scalar schedule mapping and set fact fragments; `src/cadrumo/_data/registry/aeat/facts`.
- [ ] `W04.P15.S30` - Normalize adapted families assigned to facts ownership; `src/cadrumo/_data/registry/aeat/facts`.

### Phase `W04.P16` - Delete Python legal constants and duplicate mappings

Remove migrated legal declarations and local interpretations while preserving unrelated technical configuration and serialization tokens.

- [ ] `W04.P16.S31` - Delete migrated statutory declarations but retain technical configuration; `src/cadrumo/core/external_constants.py`.
- [ ] `W04.P16.S32` - Delete numeric IVA interpretation but retain persisted enum tokens; `src/cadrumo/domain/invoices/enums.py`.
- [ ] `W04.P16.S33` - Delete superseded regulatory mappings and fallback policies; `src/cadrumo`.

### Phase `W04.P17` - Delete bespoke loaders caches and data paths

Remove retired parsers, caches, wrappers, direct readers, duplicate TOML paths, and adapter closure entries.

- [ ] `W04.P17.S34` - Delete superseded legal-only adapters and provider-local caches; `src/cadrumo/domain/calculations/registry/loader.py`.
- [ ] `W04.P17.S56` - Delete retired IVA and recargo parsers caches and raw TOML; `src/cadrumo/domain/iva and src/cadrumo/_data/registry/aeat/iva`.
- [ ] `W04.P17.S57` - Delete retired IVA-local grounding and obsolete repository wrapper; `src/cadrumo/domain/iva/_grounding.py and src/cadrumo/core/resources/_repos/iva_rate_tables.py`.

### Phase `W04.P18` - Enforce negative architecture

Turn retirement-ledger closure, forbidden imports, unowned directories, direct reads, and provenance-free results into blocking gates.

- [ ] `W04.P18.S35` - Block imports of retired declarations and loader symbols; `dev/quality`.
- [ ] `W04.P18.S36` - Block direct governed-directory reads and unregistered loaders; `dev/quality`.
- [ ] `W04.P18.S37` - Block provenance-free results and unresolved migration entries; `dev/registry/analysis`.

### Phase `W04.P19` - Verify retirement boundary

Prove the normalized catalogue is the sole operative authority and that all planned deletion targets are absent.

- [ ] `W04.P19.S58` - Verify sole authority and retirement-ledger closure at the Wave 4 handoff; `src/cadrumo and dev/registry`.
- [ ] `W04.P19.S59` - Run canonical strict production type checking after deletion; `justfile check-types and dev/quality/types.py`.
- [ ] `W04.P19.S60` - Run both dead-code audits and remove exact orphaned code and tests; `dev/audit/dead_code.py and dev/audit/unreachable_code.py`.

## Wave `W05` - Integrate and verify campaign closure

Run the campaign-level integration, packaging, quality, and architectural verification once the construction and retirement waves have landed.

### Phase `W05.P20` - Run integrated engineering verification

Run focused facts, authority, affected-domain, packaging, and quality suites once at the campaign handoff.

- [ ] `W05.P20.S38` - Run strict type import architecture registry packaging and quality gates; `justfile`.
- [ ] `W05.P20.S61` - Run focused facts authority and affected-domain suites at final handoff; `src/cadrumo and dev/registry`.
- [ ] `W05.P20.S62` - Run both dead-code audits and require no campaign-introduced findings; `dev/audit/dead_code.py and dev/audit/unreachable_code.py`.

### Phase `W05.P21` - Review authority and deletion closure

Review the final authority boundary, provenance behavior, migration completeness, and removal diff against the accepted decision.

- [ ] `W05.P21.S39` - Review typed authority provenance enrollment and fail-closed behavior; `src/cadrumo/domain/calculations/registry`.
- [ ] `W05.P21.S40` - Review the deletion diff against the retirement ledger and exclusions; `src/cadrumo`.

### Phase `W05.P22` - Publish campaign closure

Update durable architecture documentation and close the plan only after all facts resolve through the authority and the retirement ledger is empty.

- [ ] `W05.P22.S41` - Close the campaign when every step and retirement entry is closed; `.vault/plan/2026-09-09-facts-registry-plan.md`.
- [ ] `W05.P22.S63` - Publish governed-fact schema provider and migration contracts; `docs and .codex/rules`.

## Parallelization

Waves are ordered handoffs. Within Wave 1, contracts, retirement discovery,
and quality-tooling design can proceed in parallel; provider-authority wiring
depends on the contract surface but need not wait for the completed retirement
ledger. Within Wave 2, IVA/recargo, categories/calendars,
treaties/authorisations, and scalar/revision-backed providers are parallel once
the Wave 1 authority contract lands. Within Wave 3, declaration/aggregation,
renta/family, IVA/invoices, and treaty/authorisation/deadline migrations are
parallel and converge only for the boundary verification. Within Wave 4,
normalised authoring can proceed beside deletion preparation, but physical
deletion and blocking negative gates require the relevant migration closure
entries. Wave 5 begins only after Wave 4 reports an empty retirement ledger.

## Verification

- At each Wave handoff, the canonical `check-types` composition of `ty`,
  `pyrefly`, and `basedpyright` passes over its declared production boundaries.
- At each Wave handoff, `audit-dead-code` reports the Vulture result after its
  reviewed whitelist, and `audit-unreachable-code` reports shipped-entrypoint,
  exact-symbol, and orphaned-test reachability. Exact campaign-created findings
  are resolved rather than suppressed.
- Provider-boundary checks prove compilation, fingerprints, memoisation,
  invalidation, exact temporal selection, precedence, and complete provenance.
- Consumer-boundary checks prove value parity and fail-closed resolution across
  every migrated domain.
- Retirement-boundary checks prove the authority is the sole operative source,
  every declared deletion target is absent, retained facades contain no direct
  TOML knowledge, and the migration ledger is empty.
- The final handoff runs focused facts, authority, and affected-domain tests,
  followed by the existing import, architecture, registry, packaging, and
  quality gates. The plan closes only when every Step is checked.
