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
modified: '2026-09-11'
body_schema: body-v2
body_hash: 'sha256:d772ffbce85b2d6cb2941d06261bb98f3ccb26fc984bc6814b047f87a58d0e34'
---

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

### Phase `W01.P01` - Implement greenfield facts contracts

Create the registry-owned envelope, closed payload families, typed queries, and resolved result contracts without touching existing domain loaders or consumers.

- [x] `W01.P01.S01` - Define governed fact envelope identities and payload families; `src/cadrumo/domain/calculations/registry/facts/schema.py`.
- [x] `W01.P01.S02` - Define typed queries and provenance-bearing resolved results; `src/cadrumo/domain/calculations/registry/facts/resolution.py`.
- [x] `W01.P01.S03` - Implement strict one-fact-per-file TOML parsing; `src/cadrumo/domain/calculations/registry/facts/loader.py`.

### Phase `W01.P02` - Implement greenfield provider authority

Add provider enrollment, catalogue compilation, authority identity, validation, fingerprint, memoisation, reset, and directory-ownership plumbing without migrating legacy providers.

- [x] `W01.P02.S04` - Implement provider registration and directory ownership; `src/cadrumo/domain/calculations/registry/facts/providers.py`.
- [x] `W01.P02.S05` - Attach the fact catalogue to authority construction; `src/cadrumo/domain/calculations/registry/authority.py`.
- [x] `W01.P02.S06` - Enroll facts in fingerprints authority identity memoisation validation and resets; `src/cadrumo/domain/calculations/registry`.

### Phase `W01.P03` - Complete migration and retirement ledger

Classify every discovered candidate and record exact source symbols, consumers, destination fact families, migration dependencies, and files or symbols to delete, retain, or rewire.

- [x] `W01.P03.S07` - Classify every statutory declaration and production consumer; `src/cadrumo/core/external_constants.py`.
- [x] `W01.P03.S08` - Record exact IVA recargo grounding and repository retirement conditions; `src/cadrumo/domain/iva`.
- [x] `W01.P03.S09` - Record exact global legal-parameter adapter callers and closure conditions; `src/cadrumo/domain/calculations/registry/loader.py`.
- [x] `W01.P03.S42` - Record retained domain facades and excluded technical configuration readers; `src/cadrumo/domain and src/cadrumo/core/external_constants.py`.

### Phase `W01.P04` - Build facts quality tooling

Create catalogue-denominated structural gates and a broad report-only discovery sentinel while preserving modelo-specific tooling.

- [x] `W01.P04.S10` - Implement provider ownership identity temporal precedence and provenance gates; `dev/registry/analysis`.
- [x] `W01.P04.S11` - Implement the report-only governed-literal discovery sentinel; `dev/registry/analysis`.
- [x] `W01.P04.S12` - Enroll facts checks without changing modelo denominators; `dev/quality/suite.py`.

### Phase `W01.P23` - Verify foundation boundary

At the Wave 1 handoff, run strict production typing and the two complementary dead-code signals after the greenfield architecture and retirement census converge.

- [x] `W01.P23.S43` - Run canonical strict production type checking at the Wave 1 handoff; `justfile check-types and dev/quality/types.py`.
- [x] `W01.P23.S44` - Run the reviewed-whitelist Vulture audit at the Wave 1 handoff; `justfile audit-dead-code and dev/audit/dead_code.py`.
- [x] `W01.P23.S45` - Run shipped-entrypoint reachability at the Wave 1 handoff; `justfile audit-unreachable-code and dev/audit/unreachable_code.py`.

## Wave `W02` - Enroll governed data providers

Register existing data-backed domains behind the new authority in parallel, preserving their public behavior until their consumers migrate. Wave W03 depends on provider parity at this boundary.

### Phase `W02.P05` - Enroll IVA and recargo providers

Adapt IVA schedules, recargo schedules, typed lookup behavior, evidence, and precedence into authority-managed providers.

- [x] `W02.P05.S13` - Register IVA rate schedules as typed dated provider adapters; `src/cadrumo/domain/iva/rates.py`.
- [x] `W02.P05.S14` - Register recargo by applied rate and operation date; `src/cadrumo/domain/iva/recargo_equivalencia.py`.
- [x] `W02.P05.S15` - Move IVA evidence enforcement into provider validation; `src/cadrumo/domain/iva/_grounding.py`.

### Phase `W02.P06` - Enroll categories and calendar providers

Adapt category profiles and legally governed calendar or deadline data into authority-managed providers.

- [x] `W02.P06.S16` - Register statutory category profiles and dated caps; `src/cadrumo/domain/categories/registry.py`.
- [x] `W02.P06.S17` - Register classified legal calendar and deadline facts; `src/cadrumo/domain/deadlines`.

### Phase `W02.P07` - Enroll treaty providers and classify authorisation vocabulary

Adapt convenio overrides through the authority and retain bootstrap apoderamientos vocabulary outside governed facts until authoritative temporal evidence exists.

- [x] `W02.P07.S18` - Register convenio overrides as a typed provider adapter; `src/cadrumo/domain/calculations/registry/convenio.py`.
- [x] `W02.P07.S19` - Classify apoderamientos as bootstrap product vocabulary outside governed facts pending authoritative temporal evidence; `src/cadrumo/domain/auth/apoderamientos/catalogue.py`.

### Phase `W02.P08` - Enroll scalar and revision-backed facts

Enroll external-constant candidates and already revision-backed duplicate values through typed scalar, bracket, set, and date-window providers.

- [x] `W02.P08.S20` - Register statutory scalars schedules and classifications; `src/cadrumo/core/external_constants.py`.
- [x] `W02.P08.S21` - Enroll canonical legal facts without duplicate authority; `src/cadrumo/_data/registry/aeat/legal`.
- [x] `W02.P08.S22` - Project modelo-owned facts without moving parameter files; `src/cadrumo/_data/registry/aeat/modelos`.

### Phase `W02.P09` - Verify provider boundary

Exercise provider compilation, identity, cache invalidation, exact resolution, and provenance once all provider phases converge.

- [x] `W02.P09.S23` - Verify provider compilation exact resolution and provenance at the Wave 2 handoff; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `W02.P09.S46` - Run canonical strict production type checking at the Wave 2 handoff; `justfile check-types and dev/quality/types.py`.
- [x] `W02.P09.S47` - Run both dead-code audits at the Wave 2 handoff; `dev/audit/dead_code.py and dev/audit/unreachable_code.py`.

## Wave `W03` - Migrate consumers by legal domain

Move every classified consumer to typed provenance-bearing fact resolution in parallel domain phases. Wave W04 depends on closure of each domain migration ledger.

### Phase `W03.P10` - Migrate declaration and aggregation consumers

Rewire M347, M202, declaration thresholds, modelo group classifications, and aggregation consumers.

- [x] `W03.P10.S48` - Rewire every M347 comparator validator and diagnostic to one fact; `src/cadrumo/domain/calculations/registry/_m347_threshold.py and dependent production callers`.
- [x] `W03.P10.S49` - Rewire Modelo 202 and modelo classification consumers; `src/cadrumo/domain/calculations/registry/applicability_modelo202.py and src/cadrumo/application/aggregation/_service.py`.

### Phase `W03.P11` - Migrate renta and family consumers

Rewire maritime, maternity, descendant, Madrid, Art 20, Art 52, DT12, and SAL consumers.

- [x] `W03.P11.S24` - Rewire maritime Art 7p and REBECA inputs; `src/cadrumo/domain/renta/maritime_exemption.py`.
- [x] `W03.P11.S25` - Rewire descendant maternity custody and Madrid windows; `src/cadrumo/domain/contribuyente`.
- [x] `W03.P11.S50` - Rewire Art 20 Art 52 DT12 and SAL calculations; `src/cadrumo/application/modelo and src/cadrumo/domain/modelos`.

### Phase `W03.P12` - Migrate IVA and invoice consumers

Rewire invoice rate interpretation, IVA calculations, recargo lookup, inventory defaults, and extraction authority consumers.

- [x] `W03.P12.S26` - Rewire IVA lookups while preserving domain facades; `src/cadrumo/domain/iva`.
- [x] `W03.P12.S27` - Rewire invoice slot percentage interpretation; `src/cadrumo/domain/invoices/enums.py`.
- [x] `W03.P12.S51` - Rewire extraction recargo aggregation and inventory defaults; `src/cadrumo/application/ledger and src/cadrumo/application/aggregation and src/cadrumo/domain/contribuyente/inventory`.

### Phase `W03.P13` - Migrate treaty and deadline consumers; classify unresolved legal lanes

Rewire treaty and deadline consumers, retain apoderamientos as non-governed vocabulary, replace unbounded legal-parameter projections with source-grounded temporal variants, and only then migrate residual direct legal-parameter paths before the consumer boundary.

- [x] `W03.P13.S52` - Rewire treaty consumers while retaining apoderamientos as classified non-governed product vocabulary; `src/cadrumo/domain/calculations/registry/_formula_runtime_irnr.py and src/cadrumo/entrypoints/cli/config_payloads.py`.
- [x] `W03.P13.S53` - Rewire deadline and notification consumers while retaining unclassified amendment and foreign-asset projections pending evidence; `src/cadrumo/domain/deadlines and src/cadrumo/core`.
- [x] `W03.P13.S70` - Capture and author the bounded administrator-retention fact slice from BOE redactions; `dev/corpus and src/cadrumo/_data/corpus/normatives/html and src/cadrumo/_data/registry/aeat/facts`.
- [x] `W03.P13.S68` - Capture hash-pinned BOE article 95 redactions and author source-cited temporal withholding-rate facts under the governed authority; `dev/corpus and src/cadrumo/_data/corpus/normatives/html and src/cadrumo/_data/registry/aeat/facts and src/cadrumo/_data/registry/aeat/legal and src/cadrumo/domain/transactions`.
- [x] `W03.P13.S74` - Capture the official M036 activity-code mapping, author source-cited article-95 activity-selector facts, and remove their legacy adapter definitions; `dev/corpus and src/cadrumo/_data/corpus and src/cadrumo/_data/registry/aeat/facts and src/cadrumo/_data/registry/aeat/legal and src/cadrumo/domain/transactions`.
- [x] `W03.P13.S71` - Capture hash-pinned BOE articles 109 and 110 redactions, author source-cited temporal selectors by legal applicability, and rewire Modelo 131 to its form-specific authority; `dev/corpus and src/cadrumo/_data/corpus/normatives/html and src/cadrumo/_data/registry/aeat/facts and src/cadrumo/_data/registry/aeat/legal and src/cadrumo/application/aggregation`.
- [x] `W03.P13.S72` - Capture hash-pinned BOE article 161 redactions and author source-cited temporal equivalence-surcharge facts under the governed authority; `dev/corpus and src/cadrumo/_data/corpus/normatives/html and src/cadrumo/_data/registry/aeat/facts and src/cadrumo/_data/registry/aeat/legal and src/cadrumo/domain/iva`.
- [x] `W03.P13.S73` - Capture hash-pinned BOE article 31 and transitional-provision redactions and author source-cited temporal objective-estimation exclusion facts under the governed authority; `dev/corpus and src/cadrumo/_data/corpus/normatives/html and src/cadrumo/_data/registry/aeat/facts and src/cadrumo/_data/registry/aeat/legal and src/cadrumo/application/modelo`.
- [x] `W03.P13.S66` - Replace generic fact selectors with provider-owned validated applicability coordinates before consumer-boundary verification; `src/cadrumo/domain/calculations/registry/facts and src/cadrumo/domain/calculations/registry and src/cadrumo/domain/transactions and src/cadrumo/application/aggregation`.
- [ ] `W03.P13.S64` - Verify the migrated objective-estimation fact consumer through the signed published authority artifact before the consumer-boundary handoff; `src/cadrumo/application/modelo/_objective_estimation_advisory.py and src/cadrumo/application/modelo/tests/test_objective_estimation_exclusion_advisory.py and src/cadrumo/_data/registry/authority/authority.json`.
- [x] `W03.P13.S75` - Delete retired legal-parameter provider implementations after governed facts replace every live resolver and consumer path; `dev/registry/compiler/legal_parameters.py and dev/registry/tests/test_legal_parameter_provider.py and src/cadrumo/domain and src/cadrumo/application`.
- [x] `W03.P13.S69` - Enforce and prove canonical tax-fact temporal coverage, date-axis selection, provenance, and refusal outside source-grounded windows; `dev/registry/compiler/fact_validation.py and dev/registry/compiler/validator.py and dev/registry/tests/test_retired_fact_provider_gate.py`.
- [x] `W03.P13.S76` - Repair Article 101 excerpt filenames and source references so provision-tier evidence is verifiable before the cross-domain authority proof; `src/cadrumo/_data/corpus/normatives/html and src/cadrumo/_data/registry/aeat/legal and src/cadrumo/_data/registry/aeat/facts`.

### Phase `W03.P14` - Verify consumer boundary

Exercise the real authority path for M347/modelo thresholds, renta and family
windows, IVA and recargo temporal/exclusion cases, treaty overrides, and
deadline facts. The handoff also proves that governed-value consumers no
longer import the retained operational configuration as a legal-value store,
and reruns the previously deferred treaty-focused test.

- [ ] `W03.P14.S28` - Verify authority-level exact resolution, temporal selection, provenance, consumer parity, and absence of governed-value legacy imports; `src/cadrumo and dev/registry`.
- [ ] `W03.P14.S54` - Run canonical strict production type checking at the Wave 3 handoff; `justfile check-types and dev/quality/types.py`.
- [ ] `W03.P14.S55` - Run both dead-code audits and add exact findings to the retirement ledger; `dev/audit/dead_code.py and dev/audit/unreachable_code.py`.
- [ ] `W03.P14.S67` - Add an authority-level cross-domain fact gate that verifies corpus grounding, resolution, parity, and unsupported applicability refusal; `src/cadrumo/domain/calculations/registry/tests and dev/registry/analysis`.

## Wave `W04` - Normalize facts and delete legacy authority paths

Move authored facts into the normalized facts corpus where approved, remove duplicate constants, loaders, caches, files, and imports, and make forbidden paths fail the quality gates. Wave W05 depends on a zero-open-item retirement ledger.

### Phase `W04.P15` - Normalize authored fact corpus

Move approved adapted data families and Python-held facts into one-fact-per-file normalized TOML while retaining source evidence.

- [x] `W04.P15.S29` - Replace the statutory Python fact adapter with normalized scalar and decimal-mapping fragments carrying exact typed payloads, effective applicability, and official source evidence; `src/cadrumo/_data/registry/aeat/facts and dev/registry/compiler/fact_providers.py and dev/registry/compiler/statutory_constants.py and dev/registry/tests and dev/registry/analysis/facts_external_constants_retirement.toml`.
- [ ] `W04.P15.S30` - Normalize adapted families assigned to facts ownership; `src/cadrumo/_data/registry/aeat/facts`.

### Phase `W04.P16` - Delete Python legal constants and duplicate mappings

Remove migrated legal declarations and local interpretations while preserving unrelated technical configuration and serialization tokens.

- [ ] `W04.P16.S31` - Delete migrated statutory declarations but retain technical configuration; `src/cadrumo/core/external_constants.py`.
- [ ] `W04.P16.S32` - Delete numeric IVA interpretation but retain persisted enum tokens; `src/cadrumo/domain/invoices/enums.py`.
- [ ] `W04.P16.S33` - Delete superseded regulatory mappings and fallback policies; `src/cadrumo`.
- [ ] `W04.P16.S65` - Delete the statutory Python-fact adapter and duplicate declarations after normalized fact fragments replace both lanes; `dev/registry/compiler/statutory_constants.py and dev/registry/compiler/fact_providers.py and dev/registry/tests/test_statutory_constants_provider.py and src/cadrumo/core/external_constants.py`.

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
treaties/authorisation classification, and scalar/revision-backed providers are parallel once
the Wave 1 authority contract lands. Within Wave 3, declaration/aggregation,
renta/family, IVA/invoices, and treaty/deadline migrations are
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
