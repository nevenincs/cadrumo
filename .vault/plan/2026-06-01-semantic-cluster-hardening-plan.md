---
tags:
  - '#plan'
  - '#semantic-cluster-hardening'
date: '2026-06-01'
tier: L3
related:
  - '[[2026-06-01-semantic-cluster-hardening-adr]]'
  - '[[2026-06-01-semantic-cluster-hardening-research]]'
  - '[[2026-05-31-core-authority-adr]]'
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

# `semantic-cluster-hardening` `campaign` plan

A RAG-driven re-audit-and-remediate campaign that cross-references the
`src/aeat` tree against the accepted canonical-authority decisions and
removes duplication, dead code, and domain functionality redefinition. It
adds a standing 7th swarm-audit axis (semantic functionality-cluster
overlap), treats all prior research as unverified leads, and prioritises the
408-added / 1305-modified module delta since the 2026-05-19 baseline. Work
proceeds as a delta-audit gate (W01) feeding four sequenced remediation
Waves; every remediation Step is one cohesive change landing as one atomic
explicit-path commit with a real behaviour test.

## Wave `W01` - delta-audit gate and Axis-7 establishment

Establishes the standing 7th cadence axis and produces the verified functionality-cluster inventory over the 408-added/1305-modified delta since the 2026-05-19 baseline. Feeds every downstream Wave; prior research is treated as unverified leads, re-confirmed here with RAG plus rg.

### Phase `W01.P01` - Axis-7 cadence establishment

Add the standing 7th axis to the swarm-audit cadence and sync it into provider surfaces.

- [x] `W01.P01.S01` - Add the standing 7th axis (semantic functionality-cluster overlap and canonical-definition enrollment) to the cadence rule; `.vaultspec/rules/rules/aeat-swarm-audit-cadence.md`.
- [x] `W01.P01.S02` - Sync the amended cadence rule into provider surfaces via vaultspec-core; `.vaultspec`.

### Phase `W01.P02` - delta enumeration and RAG sweep

Enumerate the changed-module delta since baseline, run the Axis-7 RAG-plus-rg sweep, and persist a verified-cluster audit document.

- [x] `W01.P02.S03` - Enumerate Python modules added and modified since the 2026-05-19 baseline; `src/aeat`.
- [x] `W01.P02.S04` - Run the Axis-7 RAG functional-concept sweep over the delta and verify candidate clusters with rg; `src/aeat`.
- [x] `W01.P02.S05` - Persist the verified functionality-cluster delta-audit document; `.vault/audit`.

## Wave `W02` - duplication-cluster consolidation

Consolidates verified substitutable duplication clusters to canonical homes with behaviour and roundtrip tests. Seeded by the decimal-to-cents triplication; extended by clusters the delta sweep surfaces. Depends on W01.

### Phase `W02.P03` - numeric primitive consolidation

Create the canonical core money/Decimal primitive and migrate the three confirmed cents-rounding sites onto it.

- [x] `W02.P03.S06` - Create the canonical core money Decimal primitive with half-up cents rounding; `src/aeat/core/money/__init__.py`.
- [x] `W02.P03.S07` - Add a behaviour and roundtrip test for the core money primitive; `src/aeat/core/money/test_money.py`.
- [x] `W02.P03.S08` - Migrate the fincas rounding helper onto the core money primitive; `src/aeat/domain/fincas/_rounding.py`.
- [x] `W02.P03.S09` - Migrate the inventory quantize helper onto the core money primitive; `src/aeat/domain/profile/inventory/__init__.py`.
- [x] `W02.P03.S10` - Migrate the assets quantize helper onto the core money primitive; `src/aeat/domain/profile/assets/__init__.py`.

### Phase `W02.P04` - delta-surfaced cluster triage

Triage the verified clusters from the delta audit and insert one consolidation Step per confirmed cluster.

- [x] `W02.P04.S11` - Triage verified delta-audit clusters and insert one consolidation Step per confirmed cluster; `.vault/audit`.

## Wave `W03` - base-definition and pydantic enrollment re-verification

Re-proves, never trusts, the claimed canonical enrollment completeness (STRICT_FROZEN_CONFIG, typed aliases, enums) against the current tree, with the added modules as prime suspects. Depends on W01.

### Phase `W03.P05` - STRICT_FROZEN re-verification

Re-scan the current tree for local strict/frozen ConfigDict copies and close any stragglers against the canonical constant.

- [x] `W03.P05.S12` - Re-scan the current tree for local strict-frozen ConfigDict copies versus the canonical constant; `src/aeat`.
- [x] `W03.P05.S13` - Triage the local-config stragglers and insert one migration Step per confirmed site; `src/aeat`.

### Phase `W03.P06` - typed-alias and enum enrollment re-verification

Re-run the diagnostics enforcement suite, record gaps in the delta, and insert one migration Step per confirmed gap.

- [x] `W03.P06.S14` - Re-run the diagnostics enrollment enforcement suite and record gaps; `src/aeat/diagnostics/test_identity_primitive_placement.py`.
- [x] `W03.P06.S15` - Triage typed-alias and enum enrollment gaps in the delta and insert one migration Step per confirmed gap; `src/aeat`.

## Wave `W04` - exception consolidation

Authors the blank exception-restructure ADR, deletes the unused DomainError under a safeguarded commit, normalises error-module naming, and re-verifies every domain error base roots at AeatError. Depends on W01.

### Phase `W04.P07` - exception ADR and DomainError deletion

Author the exception-restructure ADR and delete the unused DomainError under a safeguarded commit sequence.

- [x] `W04.P07.S16` - Author the exception-restructure ADR content; `.vault/adr/2026-05-09-exception-restructure-adr.md`.
- [x] `W04.P07.S17` - Commit surrounding exception work as the safeguard checkpoint before deletion; `src/aeat/domain`.
- [x] `W04.P07.S18` - Delete the unused DomainError in its own clearly-messaged commit; `src/aeat/domain/_errors.py`.

### Phase `W04.P08` - error-module naming normalisation

Rename the four errors.py modules to the dominant _errors.py convention, each with consumer updates.

- [x] `W04.P08.S19` - Rename the renta error module to the _errors convention with consumer updates; `src/aeat/domain/renta/errors.py`.
- [x] `W04.P08.S20` - Rename the iva error module to the _errors convention with consumer updates; `src/aeat/domain/iva/errors.py`.
- [x] `W04.P08.S21` - Rename the normatives error module to the _errors convention with consumer updates; `src/aeat/domain/normatives/errors.py`.
- [x] `W04.P08.S22` - Rename the manuals error module to the _errors convention with consumer updates; `src/aeat/domain/manuals/errors.py`.

### Phase `W04.P09` - error-root re-verification

Re-verify every domain package error base still roots at AeatError.

- [x] `W04.P09.S23` - Re-verify every domain package error base roots at AeatError; `src/aeat/domain`.

## Wave `W05` - domain redefinition and taxonomy

Re-confirms prior duplication-sweep conceptual leads against current state, promotes tax_domain to a closed core StrEnum with loader hydration, and renames the mis-named portals Subdomain. Depends on W01; runs on the cleaned field after W02-W04.

### Phase `W05.P10` - tax_domain typed-constant promotion

Add a closed core tax_domain StrEnum, hydrate it at the loader boundary, and re-type the schema field with a roundtrip test.

- [x] `W05.P10.S24` - Add the closed tax_domain StrEnum typed-constant to core; `src/aeat/core/_tax_domain.py`.
- [x] `W05.P10.S25` - Hydrate tax_domain to the typed enum at the registry loader boundary; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `W05.P10.S26` - Re-type the ModeloDefinition tax_domain field to the enum; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W05.P10.S27` - Add a roundtrip test for tax_domain loader hydration; `src/aeat/domain/calculations/registry/test_tax_domain.py`.

### Phase `W05.P11` - Subdomain rename

Rename the mis-named portals Subdomain StrEnum to a portal-host concept with consumer updates.

- [x] `W05.P11.S28` - Rename the portals Subdomain StrEnum to a portal-host concept with consumer updates; `src/aeat/domain/portals/_categories.py`.

### Phase `W05.P12` - prior-lead re-confirmation

Re-confirm prior duplication-sweep conceptual leads against current state and insert one Step per confirmed redefinition.

- [x] `W05.P12.S29` - Re-confirm prior duplication-sweep conceptual leads and insert one Step per confirmed redefinition; `.vault/audit`.

## Parallelization

W01 (the delta-audit gate) must land first; it produces the verified-cluster
inventory that W02 and the W03/W06 triage Steps consume. W02 through W05 are
sequenced by default, but W03 (enrollment re-verification) carries no hard
dependency on W02 and may run in parallel with it once W01 closes. W05 runs
last so the taxonomy work lands on a field already cleaned by W02 to W04.
Within a Wave, the triage Steps (`W02.P04.S11`, `W03.P05.S13`,
`W03.P06.S15`, `W05.P12.S29`) are expansion points: they insert one new Step
per confirmed item via `vault plan step insert`, and those inserted Steps are
independent and parallelisable. The four error-module renames
(`W04.P08.S19` to `S22`) are mutually independent and may run in parallel,
each its own atomic commit.

## Verification

Mission success criteria, each a verifiable check:

- The cadence rule carries the standing 7th axis and `vaultspec-core` sync
  regenerates provider surfaces with no drift (`spec doctor` clean).
- The delta-audit document exists with verified clusters, each tagged real or
  constraint-shape-divergent under the substitutability pre-filter.
- A single canonical core money primitive exists; `fincas`, inventory, and
  assets import it; its behaviour test passes and no `quantize` cents-rounding
  literal remains in the three former sites (`rg` confirms).
- The diagnostics enrollment enforcement suite passes with zero new
  violations introduced by the delta.
- The exception-restructure ADR is authored and accepted; `DomainError` is
  deleted in its own commit; the four error modules are named `_errors.py`;
  all 23 domain error bases root at `AeatError`.
- `tax_domain` is a closed core `StrEnum` hydrated at the loader boundary
  with a passing roundtrip test; `Subdomain` is renamed with no stale
  references (`rg` confirms).
- Every remediation commit was preceded by a clean
  `uv run --no-sync pytest --collect-only -q`; canonical-site moves are tagged
  `relocation:<symbol>`.
- Each Wave passes a fresh-context campaign-close honesty review before it is
  declared structurally complete.

The plan is complete when every Step in every Wave is closed (`- [x]`) and
every triage Step has either inserted its follow-on Steps or recorded that
none were warranted.
