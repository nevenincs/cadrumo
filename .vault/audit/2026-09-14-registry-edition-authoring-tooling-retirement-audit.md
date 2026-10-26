---
tags:
  - '#audit'
  - '#registry-edition-authoring'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:79dc81c135e48b5618b0c2b3b85ca4532ae5bd468e7fbe1f523360bfce45d078'
related:
  - "[[2026-09-09-registry-edition-authoring-adr]]"
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# `registry-edition-authoring` audit: `Registry tooling retirement`

## Scope

Retire isolated edition-authoring campaign tooling, rejected-shape converters and their private worklists without changing the registry corpus or maintained correctness guards. Thirty removed paths are recorded with exact hashes and recoverable originals in `.logs/audit-runs/2026-09-14/registry-tooling-retirement-backup.json`; fourteen Just commands retire without aliases.

## Findings

### maintained-boundary-reference | medium | The durable tooling-boundary reference is still an empty scaffold

`2026-09-14-registry-edition-authoring-maintained-tooling-boundary-reference` contains only template comments and an empty Summary. The code removal distinguishes campaign measurements and one-time converters from maintained compiler validators, publication tools, corpus gates and reusable derivation helpers, but that ownership/rationale exists only in the transient implementation brief and deleted modules' history. Populate the reference with the retained invariant-to-owner mapping and the retirement classification for each deleted tool family before closeout; otherwise a future maintainer cannot audit whether a missing report was deliberately retired or accidentally lost without reconstructing this campaign.

### dependency-and-recovery-closure | low | Deleted paths remain recoverable and no live dependency points at them

No open code finding in the bounded closure check. All 28 manifest paths are absent from the live tree; every recorded backup exists and matches its declared SHA-256, and each backup is byte-identical to the tracked `HEAD` blob, so recovery does not depend on the temporary directory. Static searches found no surviving import or recipe reference to the retired modules. `edition_token_in_identifier` is preserved unchanged in `identifier_edition.py`, `bindings.py` imports that maintained home, and `test_identifier_edition.py` retains focused token/range cases. The binding registration corpus gate now obtains the bundled modelos root from the production resource boundary rather than a retired converter constant. The retained compiler contiguity/evolution validators, binding registration gate, record-design provenance checks, seeder/ledger, publication and reusable derivation/migration tools remain present.

### maintained-boundary-reference-resolution | low | The retained and retired tooling boundary is now documented

Resolved after a fresh Vaultspec read. `2026-09-14-registry-edition-authoring-maintained-tooling-boundary-reference` now distinguishes maintained compiler, conformance, health, publication and generated-target checks from campaign reports; records the unchanged identifier helper move and preserved provenance/registration gates; explains retirement of provider-shape, row-set, rename and result-fragment writers; and names the authoring/proof/seeder/ledger tools that remain. It also points to the exact backup manifest and preserves historical vault records as history.

### retirement-extension-closure | low | The relations absorption converter has no remaining schema target or caller

No open finding for the two-file extension. The updated manifest contains 30 paths; every live path is absent, every backup exists and matches its recorded SHA-256, and every backup remains byte-identical to `HEAD`. `absorb_relations_into_bindings.py` and its sole dedicated test have no caller or Just recipe. `ModeloRevision` no longer exposes the authored `relations` field the converter rewrote; maintained cross-model relation behavior and its independent tests remain in their current binding/runtime owners. The added deletion therefore retires a completed schema-transition writer rather than removing the relation runtime contract.

## Recommendations

The reviewed retirement closure has no open findings. The moved identifier helper has identical executable AST; official-design provenance tests and all current binding-registration checks remain. Generated import-load metadata was rebuilt and obsolete next-step command hints now name `check-registry`.

Verification: the initial focused suite passed 76 tests and exposed one pre-existing CLI-census omission. The census now includes the three actual existing package entry points, and the subsequent focused suite passed all 25 tests. Ruff and focused type checking passed. The final fingerprint check proves all 58 modelo trees unchanged. Broad collection failed with 15 obsolete IVA/spending-category/rental API errors, none caused by retired-module imports; those business-correctness tests were not deleted.

The maintained `check-facts` path still mixes a separate fact-relocation campaign's lane and historical accounting with useful discovery, placement, consumer and publication checks. Split its durable constraints/dispositions and consumer requirements into a maintained home before retiring historical bookkeeping. Replacing it with facts-only mode would drop real checks and is not authorized by this retirement proof.
