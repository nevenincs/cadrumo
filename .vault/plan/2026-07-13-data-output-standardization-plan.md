---
tags:
  - '#plan'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
tier: L3
related:
  - '[[2026-07-13-data-output-standardization-adr]]'
  - '[[2026-07-13-data-output-standardization-research]]'
---

# `data-output-standardization` plan

## Wave `W01` - Location authority

Finish the state-root decision: derive every output-dir default from cadrumo_local_storage_root and relocate the two OS-tempdir durable caches under a settings-driven cache root (rulings R1, R2).

### Phase `W01.P01` - Root derivation

Generalise the state-root derivation table so all output-dir defaults derive from the root; delete dormant fields; verify vestigial financial catalogue dirs.

- [x] `W01.P01.S01` - Extend the state-root derivation so every output-dir Settings field default derives from cadrumo_local_storage_root under the category taxonomy, eliminating PROJECT_ROOT/var defaults; `src/cadrumo/core/config.py`.
- [x] `W01.P01.S02` - Derive the integration-fields output dirs (financial, parity store, registry cache) from the state root and delete fields verified vestigial; `src/cadrumo/core/_config_integration_fields.py`.
- [x] `W01.P01.S03` - Delete the dormant consumer-less browser-trace dir field pair and sweep references; `src/cadrumo/core/config.py`.
- [x] `W01.P01.S04` - Verify per-dir live-vs-vestigial write status of the var/financial catalogue dirs and record the verdicts; `.vault/audit`.

### Phase `W01.P02` - Cache relocation

Move the corpus-text cache and the registry disk pickle off the OS temp dir into the settings-derived cache root with eviction, preserving xdist sharing.

- [x] `W01.P02.S05` - Add a settings-derived corpus-text cache location, rename the cache file to the cadrumo stem, and remove the hard-coded gettempdir path; `src/cadrumo/domain/calculations/registry/_validate_evidence.py`.
- [x] `W01.P02.S06` - Move the registry disk-cache production default under the cache root, rename the pickle stem to cadrumo, preserve xdist fingerprint sharing; `src/cadrumo/domain/calculations/registry/_loader_cache.py`.
- [x] `W01.P02.S07` - Add fingerprint-count eviction for accumulated registry cache pickles; `src/cadrumo/domain/calculations/registry/_loader.py`.
- [x] `W01.P02.S08` - Update the white-box registry-cache and authority tests for the relocated cache locations; `src/cadrumo/domain/calculations/registry/tests`.

## Wave `W02` - Lifecycle policy

Give every durable generated artifact family one declared lifecycle (rotation, TTL, retention, or documented unbounded) and gate the taxonomy structurally (ruling R3).

### Phase `W02.P03` - Rotation and retention

Rotating log handler and retention prunes for the unbounded artifact families, following the run-telemetry precedent.

- [x] `W02.P03.S09` - Replace the plain FileHandler with a size-capped rotating handler for cadrumo.log; `src/cadrumo/core/logging.py`.
- [x] `W02.P03.S10` - Add retention-days pruning to the LLM response cache and usage JSONL following the run-telemetry precedent; `src/cadrumo/adapters/outbound/llm`.
- [x] `W02.P03.S11` - Add retention pruning for per-run trace directories; `src/cadrumo/core/observability/_store.py`.
- [x] `W02.P03.S12` - Add retention pruning for wallet diagnostic dump files; `src/cadrumo/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`.

### Phase `W02.P04` - Lifecycle gate

Structural test asserting every settings dir field maps to a declared lifecycle class.

- [x] `W02.P04.S13` - Author the structural lifecycle gate asserting every settings dir field declares exactly one lifecycle class; `src/cadrumo/core/tests`.
- [x] `W02.P04.S32` - Wire the dormant LLM and run-trace retention prunes into production paths, narrow the usage read-path uuid refusal, and add the retention-wiring gate (W02 review remediation); `src/cadrumo/adapters/outbound/llm/_client.py`.

## Wave `W03` - Naming standardization

Hard-cut rename of app-owned aeat-star artifact names to cadrumo-star, fix the export filename schema, and adjudicate the AEAT-to-CADRUMO env-var prefix per field (rulings R4, R6).

### Phase `W03.P05` - Artifact renames

Hard-cut cadrumo naming for temp prefixes, cache filenames, CWD provenance literals, and the export filename schema.

- [x] `W03.P05.S14` - Rename the aeat-prefixed temp work-area and secret prefixes to cadrumo across the five sites; `src/cadrumo temp prefixes`.
- [x] `W03.P05.S15` - Rename the CWD-anchored dot-aeat ledger provenance literals to cadrumo marker forms; `src/cadrumo/application/ledger`.
- [x] `W03.P05.S16` - Fix the export filename schema in the test corpus to modelo-id-year-period with canonical period tokens; `src/cadrumo modelo export tests`.

### Phase `W03.P06` - Env-var adjudication

Per-field ownership table for AEAT-prefixed app-owned settings, the renames it authorizes, and the full prose-surface sweep.

- [x] `W03.P06.S17` - Author the per-field ownership adjudication table for AEAT-prefixed app-owned settings; `.vault/audit`.
- [x] `W03.P06.S18` - Execute the settings-field renames the table authorizes, hard-cut, updating the dotenv exclusion set where product-state-selecting; `src/cadrumo/core/config.py`.
- [x] `W03.P06.S19` - Sweep docs, locales, error-registry suggestions, and the agent harness for every renamed variable; `renamed env-var prose surfaces`.

## Wave `W04` - Scratch and repo hygiene

One mandated scratch convention, gitignore repair, removal of tracked run artifacts and the ad-hoc runtime-s directories (ruling R5).

### Phase `W04.P07` - Repo hygiene

Gitignore repair, tracked-artifact removal, scratch convention, runtime-s retirement.

- [x] `W04.P07.S20` - Repair gitignore: fix dead src/aeat corpus-manual rules, add runtime-s pattern, broaden root-level scratch patterns; `.gitignore`.
- [x] `W04.P07.S21` - Remove the tracked repo-root run artifacts from version control; `repo-root run artifacts`.
- [x] `W04.P07.S22` - Clean stale scratch and runtime-s directories after confirming no active-agent ownership, and document the scratch naming schema; `scratch`.

## Wave `W05` - Writer consolidation

Converge the four atomic-write dialects onto one shared helper and the divergent test-isolation fixtures onto one canonical public surface (rulings R7, R8).

### Phase `W05.P08` - Atomic write helper

One shared two-tier atomic-write helper; migrate all four dialects onto it.

- [x] `W05.P08.S23` - Author the shared two-tier atomic-write helper with the hardened master-key pattern as the strong tier; `src/cadrumo/core`.
- [x] `W05.P08.S24` - Migrate the weak no-fsync atomic-write variants onto the helper; `bucket pointer, outbound local store, bucket manifest, corpus bundle`.
- [x] `W05.P08.S25` - Migrate the remaining stem-sibling atomic-write sites onto the helper; `envelope, blob store, secret store, rotation, env_io, corpus manifest, locales`.
- [x] `W05.P08.S31` - Migrate the outbound local store sidecar write onto the atomic-write helper closing the torn object-plus-sidecar crash window; `src/cadrumo/adapters/outbound/storage/_local.py`.

### Phase `W05.P09` - Test isolation

One canonical public isolation fixture with coverage gate; sweep the copy-pasted fixture families and unify collection-time roots.

- [x] `W05.P09.S26` - Promote one canonical public isolation fixture covering every settings dir field, with a structural coverage gate; `src/cadrumo/tests/secure_sql.py`.
- [x] `W05.P09.S27` - Sweep the copy-pasted isolated-cli-backend fixture copies onto the canonical fixture; `cli test isolation fixtures`.
- [x] `W05.P09.S28` - Sweep the isolated-storage fixture family and unify the two collection-time pytest storage roots into one cleanup-registered helper; `conftest storage roots`.

## Wave `W06` - Verification and close

Run the full gates with owner triage and the mandated fresh-context honesty review before declaring the campaign structurally complete.

### Phase `W06.P10` - Gates and honesty review

Full-tree gates with owner triage plus the mandated fresh-context honesty review and audit record.

- [x] `W06.P10.S29` - Run collect-only, targeted suites, and lint gates with owner-triage of any shared-worktree failures; `full-tree gates`.
- [x] `W06.P10.S30` - Run the fresh-context honesty review against the campaign closure summary and persist the audit record; `.vault/audit`.

## Description

Executes the accepted data-output-standardization ADR (rulings R1 to R8),
grounded in the six-axis discovery research of the same feature. The campaign
gives every generated artifact one settings-derived location under the
`cadrumo_local_storage_root` category taxonomy, evicts durable artifacts from
the OS temp dir, declares a growth lifecycle per artifact family behind a
structural gate, hard-cuts the remaining `aeat`-branded artifact names to
`cadrumo` per the product-authority doctrine, formalises the repo scratch
convention while repairing gitignore and removing tracked run artifacts, and
consolidates the four atomic-write dialects and the divergent test-isolation
fixture families onto single canonical surfaces. Pre-release zero-legacy
regime throughout: renames and relocations are hard cuts, never bridged.
Per the operator's no-codification directive, conventions are recorded in the
ADR and audit records, not as new vaultspec rules.

## Steps

## Parallelization

Waves are sequenced by default, with these relaxations: W04 (repo hygiene)
touches no Python surface and may run in parallel with any other wave; W03.P05
(artifact literal renames) is independent of W01/W02 and may run early; W05.P09
(test isolation) depends on W01.P01 landing (the fixture coverage gate
enumerates the final settings-field set) and must trail it. Within W01, P02
depends on P01 (the cache root derives from the taxonomy). W02.P04 (the
lifecycle gate) must trail W02.P03. W03.P06.S18/S19 must trail S17 (the
adjudication table authorizes them). W06 is strictly last. Every coder step
follows the shared-worktree disciplines: explicit-pathspec commits, abort on
non-authored WIP, no destructive git.

## Verification

- No settings dir field defaults to a PROJECT_ROOT-anchored output path; a
  structural test enumerates dir fields and asserts state-root derivation.
- `rg "gettempdir" src/cadrumo` (production, non-staging) shows no durable
  artifact writer; the two relocated caches read their location from Settings.
- The lifecycle gate passes: every settings dir field maps to exactly one
  declared lifecycle class; the rotating log handler and the three new
  retention prunes have real-behavior tests.
- `rg "aeat[-_](secret|workbook|xls-conversion|review-package|scale-bench|registry_|corpus_text)" src/cadrumo`
  returns zero production hits; renamed env vars are swept from docs,
  locales, error suggestions, and the agent harness (conformance gates
  green).
- `.gitignore` has no dead `src/aeat` rules, covers `.runtime-*/`, and the
  five tracked run artifacts are gone from `git ls-files`.
- The atomic-write helper is the sole `NamedTemporaryFile`+`os.replace`
  implementation site (grep-verified); prior call sites delegate.
- The canonical isolation fixture's coverage gate passes and the
  copy-pasted fixture families are gone.
- `uv run --no-sync pytest --collect-only -q` clean; targeted suites for
  every touched surface green; ruff clean on touched files; failures
  owner-triaged per the full-tree-gate discipline.
- The fresh-context honesty review has run and its audit record is
  persisted; surfaced items are closed or formally deferred before the
  campaign is declared complete.
