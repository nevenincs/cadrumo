---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/plan/ location)
# Feature tag (replace linkage-design-audit with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#plan'
  - '#linkage-design-audit'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-15'
# Complexity tier (mandatory for new plans).
# Allowed: L1 (Steps only), L2 (Phases above Steps),
# L3 (Waves above Phases above Steps), L4 (Epic above Waves
# above Phases above Steps; PM association required).
# Pre-existing plans without this field default to L2.
tier: L2
# Related documents as quoted wiki-links.
# Carries the AUTHORISING documents (ADR, research, reference,
# prior plan) for every Step in this plan; Steps inherit this
# chain; per-row reference footers do not exist.
related:
  - "[[2026-05-15-linkage-design-audit-research]]"
  - "[[2026-05-15-linkage-design-audit-reference]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - The related: field carries the AUTHORISING documents (ADR, research,
       reference, prior plan) for every Step in this plan. Steps inherit this
       chain; per-row reference footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artefact: <Step Record>.
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

<!-- VAULT PLAN CLI:
     The `vault plan` CLI (vaultspec-core) is the canonical surface
     for structural manipulation of this plan document. Writers and
     executors MUST use `vault plan step add/insert/move/remove/
     check/uncheck/toggle/edit`, `vault plan phase add/move/remove/
     edit`, `vault plan wave add/move/remove/edit`, `vault plan epic
     intent`, and `vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `linkage-design-audit` `Wave 1: type-system uniformity (Phase 1 of linkage epic)` plan

Wave 1 of the linkage-design epic. Enrols the existing AEAT codebase
into its own type system by eradicating every type-checker suppression
and replacing every `Any`-typed annotation with a coherent typed value
or shim. Establishes the type-uniformity prerequisite for Wave 2 (model
consolidation), Wave 3 (referential integrity), and downstream Waves.

Authorising context: the linkage-design-audit research record and
reference taxonomy carry the full surface map and convergent findings.
Wave 1 specifically targets defect class T-11 (type-system escapes,
0 / 268 coverage) plus parts of T-04 and T-05 by uniformising types
across the boundary surface.

## Proposed Changes

Inventory results (Phase P01, complete): 377 suppression sites across
118 files. Composition: 160 `: Any` annotations, 106 `dict[str, Any]`
declarations, 92 `cast()` calls, 19 `# ty:ignore` or `# noqa`
suppressions. The 19 explicit suppressions are concentrated in test
files where they exercise pydantic validation error paths; these will
be rewritten with `pytest.raises` and similar helpers rather than
inline suppression.

Acquisition strategy for the 96 external-API sites: install the
community-maintained `google-api-python-client-stubs` package to cover
~47 Google Sheets / Drive sites. Playwright already ships `py.typed`;
investigate whether the over-conservative `allowed-unresolved-imports`
entry can be removed. Anthropic ships native types. Local stubs
already exist for `playwright_stealth` and `pypdfium2` under `stubs/`.

The remaining 281 sites in `domain/`, `application/`, `adapters/` non-
boundary, `core/`, and `entrypoints/` receive direct typed replacements
using existing pydantic models or fresh `TypedDict` / pydantic types
defined per package.

After Wave 1: dual-checker strictness gate adopted (`ty` already at
`all = "error"`; `pyright` added alongside for cross-verification on
`src/aeat/domain/` and `src/aeat/application/`). CI gates and
`semgrep` regression rules prevent reintroduction.

## Steps

Structural manipulation should use the `vault plan` CLI for any
identifier-affecting change. This initial body is hand-authored;
subsequent changes should go through `vault plan step add` and friends.

### Phase `P01` - inventory and tooling

Complete. Catalogues at `scratch/out/suppressions.{json,csv}`, summary
at `scratch/out/summary.json`. Detailed counts per category and per
file recorded; top 20 worst offenders identified.

- [x] `P01.S01` - build suppression inventory tool; `scratch/suppression_inventory.py`.
- [x] `P01.S02` - run inventory and produce master catalogue; `scratch/out/`.
- [x] `P01.S03` - categorise sites by package and external-API surface; `scratch/out/summary.json`.
- [ ] `P01.S04` - build pydantic-model audit tool for Wave 2 prep; `scratch/pydantic_audit.py`.

### Phase `P02` - external-API type acquisition

Install community type stubs and remove over-conservative
`allowed-unresolved-imports` entries from `pyproject.toml`. Verify
ty and pyright resolve the typed surface after each change.

- [ ] `P02.S01` - add `google-api-python-client-stubs` as dev dependency; `pyproject.toml`.
- [ ] `P02.S02` - remove over-conservative unresolved-import entries where types now resolve; `pyproject.toml`.
- [ ] `P02.S03` - extend local stub coverage for `playwright_stealth` if surface gaps remain; `stubs/playwright_stealth/__init__.pyi`.
- [ ] `P02.S04` - investigate the single `tomllib` `dict-any` site; `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`.
- [ ] `P02.S05` - re-run inventory to confirm external-API site count drops; `scratch/out/summary.json`.

### Phase `P03` - test-file deliberate-suppression rewrite

The 19 `# ty: ignore[...]` and `# noqa: B010/E731` suppressions in
test files exist to construct invalid pydantic input or bypass lint
on test helpers. Rewrite using `pytest.raises`, named functions in
place of lambdas, or proper pydantic error-construction patterns.

- [ ] `P03.S01` - rewrite `unknown-argument` suppressions in pydantic constructors; `src/aeat/adapters/persistence/storage/master_key/test_kdf_params.py`.
- [ ] `P03.S02` - rewrite `unknown-argument` and `missing-argument` suppressions; `src/aeat/adapters/persistence/storage/bucket/test_manifest.py`.
- [ ] `P03.S03` - rewrite `unknown-argument` and `missing-argument` suppressions; `src/aeat/adapters/persistence/storage/bucket/test_export_header.py`.
- [ ] `P03.S04` - rewrite `unknown-argument` and `invalid-argument-type` suppressions; `src/aeat/adapters/persistence/storage/master_key/test_recovery_record.py`.
- [ ] `P03.S05` - rewrite `unknown-argument` suppression in pydantic test; `src/aeat/application/workflow/test_bucket_pointer.py`.
- [ ] `P03.S06` - rewrite `unknown-argument` suppression in aggregation test; `src/aeat/application/aggregation/test_oss_ioss.py`.
- [ ] `P03.S07` - rewrite `invalid-assignment` suppression; `src/aeat/domain/vat/test_oss.py`.
- [ ] `P03.S08` - rewrite `invalid-assignment` suppression; `src/aeat/adapters/inbound/pdf/test_label_regex.py`.
- [ ] `P03.S09` - rewrite `invalid-argument-type` suppression in browser evasion test; `src/aeat/adapters/outbound/aeat/browser/test_evasion.py`.
- [ ] `P03.S10` - replace lambda lint suppressions with named functions; `src/aeat/application/aggregation/test_grouping.py`.
- [ ] `P03.S11` - replace `setattr` lint suppressions with proper test pattern; `src/aeat/application/transactions/test_import.py`.
- [ ] `P03.S12` - replace `setattr` lint suppressions; `src/aeat/application/auth/test_sessions_storage_state_paths.py`.
- [ ] `P03.S13` - replace `setattr` lint suppressions; `src/aeat/domain/modelos/test_external_evidence.py`.
- [ ] `P03.S14` - replace `setattr` lint suppression; `src/aeat/adapters/inbound/sanitizer/test_records.py`.

### Phase `P04` - domain/ suppression eradication

81 sites across 26 files. Cleanest expected wins; canonical pydantic
shapes already live here. Highest-leverage files: `_models.py` in
`invoices` (16) and `transactions` (16); `_loader.py` in registry (6);
`attachments/_models.py` (6).

- [ ] `P04.S01` - replace `Any`/`cast` sites in invoice models; `src/aeat/domain/invoices/_models.py`.
- [ ] `P04.S02` - replace `Any`/`cast` sites in transaction models; `src/aeat/domain/transactions/_models.py`.
- [ ] `P04.S03` - replace `cast` sites in registry loader; `src/aeat/domain/calculations/registry/_loader.py`.
- [ ] `P04.S04` - replace `Any` sites in attachment models; `src/aeat/domain/attachments/_models.py`.
- [ ] `P04.S05` - sweep remaining `domain/` files (long tail; 22 files, ~37 sites); `src/aeat/domain/`.

### Phase `P05` - application/ suppression eradication

70 sites across 28 files. Highest-leverage files: `auth/_sessions.py`
(11), `auth/__init__.py` (6), `workflow/_models.py` (5).

- [ ] `P05.S01` - replace `Any`/`cast` sites in auth sessions; `src/aeat/application/auth/_sessions.py`.
- [ ] `P05.S02` - replace `Any` sites in auth package init; `src/aeat/application/auth/__init__.py`.
- [ ] `P05.S03` - replace `Any` sites in workflow models; `src/aeat/application/workflow/_models.py`.
- [ ] `P05.S04` - sweep remaining `application/` files (25 files, ~48 sites); `src/aeat/application/`.

### Phase `P06` - adapter-internal suppression eradication

86 sites across 31 files. Adapter code not at an external boundary.
Per the disciplined adapter-boundary policy these are direct fixes,
not shims. Highest-leverage file: `persistence/storage/crypto/_encrypted_columns.py` (8).

- [ ] `P06.S01` - replace `Any`/`cast` sites in encrypted-columns adapter; `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`.
- [ ] `P06.S02` - sweep remaining `adapter-internal` files (30 files, ~78 sites); `src/aeat/adapters/`.

### Phase `P07` - core/ suppression eradication

20 sites across 9 files. `core/json_contract.py` (6) ties to T-08 and
will be revisited when `SchemaEnvelope` is adopted in Wave 3.

- [ ] `P07.S01` - replace `Any`/`cast` sites in JSON-contract module; `src/aeat/core/json_contract.py`.
- [ ] `P07.S02` - sweep remaining `core/` files (8 files, ~14 sites); `src/aeat/core/`.

### Phase `P08` - entrypoints/ suppression eradication

7 sites across 6 files. Smallest leak surface.

- [ ] `P08.S01` - sweep `entrypoints/` files (6 files, 7 sites); `src/aeat/entrypoints/`.

### Phase `P09` - dunder-override investigation

5 sites on 5 files. `__iter__` / `__getitem__` / similar overrides on
pydantic-extending types. Most likely must remain as pydantic v2
compatibility shims. Investigation determines whether each is
necessary or can be replaced with a typed pattern.

- [ ] `P09.S01` - investigate each dunder-override site; `scratch/out/dunder_overrides.md`.
- [ ] `P09.S02` - replace removable dunder shims with typed patterns; per-file.
- [ ] `P09.S03` - document irreducible shims in code comments; per-file.

### Phase `P10` - 'other' bucket investigation

12 sites on 3 files. Sites that did not classify into any leak
category. Investigation determines correct categorisation and Phase
assignment.

- [ ] `P10.S01` - categorise 'other' bucket sites; `scratch/out/other_sites.md`.
- [ ] `P10.S02` - dispatch to correct Phase or address inline.

### Phase `P11` - dual-checker strictness gate

Adopt `pyright` alongside the existing `ty` (`all = "error"`) for
cross-checker verification on `src/aeat/domain/` and
`src/aeat/application/`. Different inference algorithms catch
different issues.

- [ ] `P11.S01` - add `pyright` as dev dependency and config; `pyproject.toml`, `pyrightconfig.json`.
- [ ] `P11.S02` - run pyright strict on `domain/`; capture initial error report.
- [ ] `P11.S03` - run pyright strict on `application/`; capture initial error report.
- [ ] `P11.S04` - resolve pyright-only findings batch by batch.
- [ ] `P11.S05` - wire pyright into CI alongside ty.

### Phase `P12` - regression gates

Mechanical prevention of suppression reintroduction. CI step plus
semgrep rules. Aligns with the prior-art research recommendation for
`semgrep` as the per-pattern enforcement layer.

- [ ] `P12.S01` - add semgrep rule rejecting new `: Any` annotations in domain and application; `.semgrep/rules/`.
- [ ] `P12.S02` - add semgrep rule rejecting new `dict[str, Any]` declarations in domain and application; `.semgrep/rules/`.
- [ ] `P12.S03` - add semgrep rule rejecting new `cast()` calls in domain and application; `.semgrep/rules/`.
- [ ] `P12.S04` - add semgrep rule requiring inline justification comment on any new `# ty: ignore`; `.semgrep/rules/`.
- [ ] `P12.S05` - wire semgrep into CI as gating check.
- [ ] `P12.S06` - close out Wave 1 by re-running suppression inventory; expected baseline near zero.

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
     Wave depends on it, and which authorising documents back it.

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

State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelised when they share no hard
interdependency.

## Verification

State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in every Wave is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter.
