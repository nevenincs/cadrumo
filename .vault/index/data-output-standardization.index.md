---
generated: true
tags:
  - '#index'
  - '#data-output-standardization'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:5c80a8a3a0e3a01a74dc6c4cd5d35601e9b38f386ae9d5cc60e851a062ea2fd8'
related:
  - '[[2026-07-13-data-output-standardization-W06-P10-summary]]'
  - '[[2026-07-13-data-output-standardization-adr]]'
  - '[[2026-07-13-data-output-standardization-audit]]'
  - '[[2026-07-13-data-output-standardization-env-var-ownership-audit]]'
  - '[[2026-07-13-data-output-standardization-plan]]'
  - '[[2026-07-13-data-output-standardization-research]]'
  - '[[2026-07-14-data-output-standardization-audit]]'
---

# `data-output-standardization` feature index

Auto-generated index of all documents tagged with `#data-output-standardization`.

## Documents

### adr

- `2026-07-13-data-output-standardization-adr` - `data-output-standardization` adr: `Data output location and naming standardization` | (**status:** `accepted`)

### audit

- `2026-07-13-data-output-standardization-audit` - `data-output-standardization` audit: `financial catalogue dir liveness`
- `2026-07-13-data-output-standardization-env-var-ownership-audit` - `data-output-standardization` audit: `AEAT env-var ownership adjudication`
- `2026-07-14-data-output-standardization-audit` - `data-output-standardization` audit: `campaign close honesty review`

### exec

- `2026-07-13-data-output-standardization-W01-P01-S01` - Extend the state-root derivation so every output-dir Settings field default derives from cadrumo_local_storage_root under the category taxonomy, eliminating PROJECT_ROOT/var defaults
- `2026-07-13-data-output-standardization-W01-P01-S02` - Derive the integration-fields output dirs (financial, parity store, registry cache) from the state root and delete fields verified vestigial
- `2026-07-13-data-output-standardization-W01-P01-S03` - Delete the dormant consumer-less browser-trace dir field pair and sweep references
- `2026-07-13-data-output-standardization-W01-P01-S04` - Verify per-dir live-vs-vestigial write status of the var/financial catalogue dirs and record the verdicts
- `2026-07-13-data-output-standardization-W01-P02-S05` - Add a settings-derived corpus-text cache location, rename the cache file to the cadrumo stem, and remove the hard-coded gettempdir path
- `2026-07-13-data-output-standardization-W01-P02-S06` - Move the registry disk-cache production default under the cache root, rename the pickle stem to cadrumo, preserve xdist fingerprint sharing
- `2026-07-13-data-output-standardization-W01-P02-S07` - Add fingerprint-count eviction for accumulated registry cache pickles
- `2026-07-13-data-output-standardization-W01-P02-S08` - Update the white-box registry-cache and authority tests for the relocated cache locations
- `2026-07-13-data-output-standardization-W02-P03-S09` - Replace the plain FileHandler with a size-capped rotating handler for cadrumo.log
- `2026-07-13-data-output-standardization-W02-P03-S10` - Add retention-days pruning to the LLM response cache and usage JSONL following the run-telemetry precedent
- `2026-07-13-data-output-standardization-W02-P03-S11` - Add retention pruning for per-run trace directories
- `2026-07-13-data-output-standardization-W02-P03-S12` - Add retention pruning for wallet diagnostic dump files
- `2026-07-13-data-output-standardization-W02-P04-S13` - Author the structural lifecycle gate asserting every settings dir field declares exactly one lifecycle class
- `2026-07-13-data-output-standardization-W02-P04-S32` - Wire the dormant LLM and run-trace retention prunes into production paths, narrow the usage read-path uuid refusal, and add the retention-wiring gate (W02 review remediation)
- `2026-07-13-data-output-standardization-W03-P05-S14` - Rename the aeat-prefixed temp work-area and secret prefixes to cadrumo across the five sites
- `2026-07-13-data-output-standardization-W03-P05-S15` - Rename the CWD-anchored dot-aeat ledger provenance literals to cadrumo marker forms
- `2026-07-13-data-output-standardization-W03-P05-S16` - Fix the export filename schema in the test corpus to modelo-id-year-period with canonical period tokens
- `2026-07-13-data-output-standardization-W03-P06-S17` - Author the per-field ownership adjudication table for AEAT-prefixed app-owned settings
- `2026-07-13-data-output-standardization-W03-P06-S18` - Execute the settings-field renames the table authorizes, hard-cut, updating the dotenv exclusion set where product-state-selecting
- `2026-07-13-data-output-standardization-W03-P06-S19` - Sweep docs, locales, error-registry suggestions, and the agent harness for every renamed variable
- `2026-07-13-data-output-standardization-W04-P07-S20` - Repair gitignore: fix dead src/aeat corpus-manual rules, add runtime-s pattern, broaden root-level scratch patterns
- `2026-07-13-data-output-standardization-W04-P07-S21` - Remove the tracked repo-root run artifacts from version control
- `2026-07-13-data-output-standardization-W04-P07-S22` - Clean stale scratch and runtime-s directories after confirming no active-agent ownership, and document the scratch naming schema
- `2026-07-13-data-output-standardization-W05-P08-S23` - Author the shared two-tier atomic-write helper with the hardened master-key pattern as the strong tier
- `2026-07-13-data-output-standardization-W05-P08-S24` - Migrate the weak no-fsync atomic-write variants onto the helper
- `2026-07-13-data-output-standardization-W05-P08-S25` - Migrate the remaining stem-sibling atomic-write sites onto the helper
- `2026-07-13-data-output-standardization-W05-P08-S31` - Migrate the outbound local store sidecar write onto the atomic-write helper closing the torn object-plus-sidecar crash window
- `2026-07-13-data-output-standardization-W05-P09-S26` - Promote one canonical public isolation fixture covering every settings dir field, with a structural coverage gate
- `2026-07-13-data-output-standardization-W05-P09-S27` - Sweep the copy-pasted isolated-cli-backend fixture copies onto the canonical fixture
- `2026-07-13-data-output-standardization-W05-P09-S28` - Sweep the isolated-storage fixture family and unify the two collection-time pytest storage roots into one cleanup-registered helper
- `2026-07-13-data-output-standardization-W06-P10-S29` - Run collect-only, targeted suites, and lint gates with owner-triage of any shared-worktree failures
- `2026-07-13-data-output-standardization-W06-P10-S30` - Run the fresh-context honesty review against the campaign closure summary and persist the audit record
- `2026-07-13-data-output-standardization-W06-P10-summary` - `data-output-standardization` `W06.P10` summary

### plan

- `2026-07-13-data-output-standardization-plan` - `data-output-standardization` plan

### research

- `2026-07-13-data-output-standardization-research` - `data-output-standardization` research: `Data output location and naming standardization discovery`
