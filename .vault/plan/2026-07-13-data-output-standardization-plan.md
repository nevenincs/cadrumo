---
tags:
  - '#plan'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
tier: L3
related:
  - '[[2026-07-13-data-output-standardization-adr]]'
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
     Replace data-output-standardization with a kebab-case feature tag, e.g. #foo-bar.
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

# `data-output-standardization` plan

## Wave `W01` - Location authority

Finish the state-root decision: derive every output-dir default from cadrumo_local_storage_root and relocate the two OS-tempdir durable caches under a settings-driven cache root (rulings R1, R2).

<!-- One-line headline summary plan. -->

### Phase `W01.P01` - Root derivation

Generalise the state-root derivation table so all output-dir defaults derive from the root; delete dormant fields; verify vestigial financial catalogue dirs.

- [ ] `W01.P01.S01` - Extend the state-root derivation so every output-dir Settings field default derives from cadrumo_local_storage_root under the category taxonomy, eliminating PROJECT_ROOT/var defaults; `src/cadrumo/core/config.py`.
- [ ] `W01.P01.S02` - Derive the integration-fields output dirs (financial, parity store, registry cache) from the state root and delete fields verified vestigial; `src/cadrumo/core/_config_integration_fields.py`.
- [ ] `W01.P01.S03` - Delete the dormant consumer-less browser-trace dir field pair and sweep references; `src/cadrumo/core/config.py`.
- [ ] `W01.P01.S04` - Verify per-dir live-vs-vestigial write status of the var/financial catalogue dirs and record the verdicts; `.vault/audit`.

### Phase `W01.P02` - Cache relocation

Move the corpus-text cache and the registry disk pickle off the OS temp dir into the settings-derived cache root with eviction, preserving xdist sharing.

- [ ] `W01.P02.S05` - Add a settings-derived corpus-text cache location, rename the cache file to the cadrumo stem, and remove the hard-coded gettempdir path; `src/cadrumo/domain/calculations/registry/_validate_evidence.py`.
- [ ] `W01.P02.S06` - Move the registry disk-cache production default under the cache root, rename the pickle stem to cadrumo, preserve xdist fingerprint sharing; `src/cadrumo/domain/calculations/registry/_loader_cache.py`.
- [ ] `W01.P02.S07` - Add fingerprint-count eviction for accumulated registry cache pickles; `src/cadrumo/domain/calculations/registry/_loader.py`.
- [ ] `W01.P02.S08` - Update the white-box registry-cache and authority tests for the relocated cache locations; `src/cadrumo/domain/calculations/registry/tests`.

## Wave `W02` - Lifecycle policy

Give every durable generated artifact family one declared lifecycle (rotation, TTL, retention, or documented unbounded) and gate the taxonomy structurally (ruling R3).

### Phase `W02.P03` - Rotation and retention

Rotating log handler and retention prunes for the unbounded artifact families, following the run-telemetry precedent.

- [ ] `W02.P03.S09` - Replace the plain FileHandler with a size-capped rotating handler for cadrumo.log; `src/cadrumo/core/logging.py`.
- [ ] `W02.P03.S10` - Add retention-days pruning to the LLM response cache and usage JSONL following the run-telemetry precedent; `src/cadrumo/adapters/outbound/llm`.
- [ ] `W02.P03.S11` - Add retention pruning for per-run trace directories; `src/cadrumo/core/observability/_store.py`.
- [ ] `W02.P03.S12` - Add retention pruning for wallet diagnostic dump files; `src/cadrumo/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`.

### Phase `W02.P04` - Lifecycle gate

Structural test asserting every settings dir field maps to a declared lifecycle class.

- [ ] `W02.P04.S13` - Author the structural lifecycle gate asserting every settings dir field declares exactly one lifecycle class; `src/cadrumo/core/tests`.

## Wave `W03` - Naming standardization

Hard-cut rename of app-owned aeat-star artifact names to cadrumo-star, fix the export filename schema, and adjudicate the AEAT-to-CADRUMO env-var prefix per field (rulings R4, R6).

### Phase `W03.P05` - Artifact renames

Hard-cut cadrumo naming for temp prefixes, cache filenames, CWD provenance literals, and the export filename schema.

- [ ] `W03.P05.S14` - Rename the aeat-prefixed temp work-area and secret prefixes to cadrumo across the five sites; `src/cadrumo temp prefixes`.
- [ ] `W03.P05.S15` - Rename the CWD-anchored dot-aeat ledger provenance literals to cadrumo marker forms; `src/cadrumo/application/ledger`.
- [ ] `W03.P05.S16` - Fix the export filename schema in the test corpus to modelo-id-year-period with canonical period tokens; `src/cadrumo modelo export tests`.

### Phase `W03.P06` - Env-var adjudication

Per-field ownership table for AEAT-prefixed app-owned settings, the renames it authorizes, and the full prose-surface sweep.

- [ ] `W03.P06.S17` - Author the per-field ownership adjudication table for AEAT-prefixed app-owned settings; `.vault/audit`.
- [ ] `W03.P06.S18` - Execute the settings-field renames the table authorizes, hard-cut, updating the dotenv exclusion set where product-state-selecting; `src/cadrumo/core/config.py`.
- [ ] `W03.P06.S19` - Sweep docs, locales, error-registry suggestions, and the agent harness for every renamed variable; `renamed env-var prose surfaces`.

## Wave `W04` - Scratch and repo hygiene

One mandated scratch convention, gitignore repair, removal of tracked run artifacts and the ad-hoc runtime-s directories (ruling R5).

### Phase `W04.P07` - Repo hygiene

Gitignore repair, tracked-artifact removal, scratch convention, runtime-s retirement.

- [x] `W04.P07.S20` - Repair gitignore: fix dead src/aeat corpus-manual rules, add runtime-s pattern, broaden root-level scratch patterns; `.gitignore`.
- [ ] `W04.P07.S21` - Remove the tracked repo-root run artifacts from version control; `repo-root run artifacts`.
- [ ] `W04.P07.S22` - Clean stale scratch and runtime-s directories after confirming no active-agent ownership, and document the scratch naming schema; `scratch`.

## Wave `W05` - Writer consolidation

Converge the four atomic-write dialects onto one shared helper and the divergent test-isolation fixtures onto one canonical public surface (rulings R7, R8).

### Phase `W05.P08` - Atomic write helper

One shared two-tier atomic-write helper; migrate all four dialects onto it.

- [ ] `W05.P08.S23` - Author the shared two-tier atomic-write helper with the hardened master-key pattern as the strong tier; `src/cadrumo/core`.
- [ ] `W05.P08.S24` - Migrate the weak no-fsync atomic-write variants onto the helper; `bucket pointer, outbound local store, bucket manifest, corpus bundle`.
- [ ] `W05.P08.S25` - Migrate the remaining stem-sibling atomic-write sites onto the helper; `envelope, blob store, secret store, rotation, env_io, corpus manifest, locales`.

### Phase `W05.P09` - Test isolation

One canonical public isolation fixture with coverage gate; sweep the copy-pasted fixture families and unify collection-time roots.

- [ ] `W05.P09.S26` - Promote one canonical public isolation fixture covering every settings dir field, with a structural coverage gate; `src/cadrumo/tests/secure_sql.py`.
- [ ] `W05.P09.S27` - Sweep the copy-pasted isolated-cli-backend fixture copies onto the canonical fixture; `cli test isolation fixtures`.
- [ ] `W05.P09.S28` - Sweep the isolated-storage fixture family and unify the two collection-time pytest storage roots into one cleanup-registered helper; `conftest storage roots`.

## Wave `W06` - Verification and close

Run the full gates with owner triage and the mandated fresh-context honesty review before declaring the campaign structurally complete.

### Phase `W06.P10` - Gates and honesty review

Full-tree gates with owner triage plus the mandated fresh-context honesty review and audit record.

- [ ] `W06.P10.S29` - Run collect-only, targeted suites, and lint gates with owner-triage of any shared-worktree failures; `full-tree gates`.
- [ ] `W06.P10.S30` - Run the fresh-context honesty review against the campaign closure summary and persist the audit record; `.vault/audit`.

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
