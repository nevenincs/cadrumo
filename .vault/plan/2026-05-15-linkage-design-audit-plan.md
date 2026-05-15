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
- [x] `P01.S02` - run inventory and produce master catalogue; `scratch/out/suppressions.json`.
- [x] `P01.S03` - categorise sites by package and external API; `scratch/out/summary.json`.
- [ ] `P01.S04` - build pydantic-model audit tool for Wave 2 prep; `scratch/pydantic_audit.py`.

### Phase `P02` - external-API type acquisition

Install community type stubs and remove over-conservative
`allowed-unresolved-imports` entries from `pyproject.toml`. Verify
ty and pyright resolve the typed surface after each change.

- [ ] `P02.S05` - add `google-api-python-client-stubs` as dev dependency; `pyproject.toml`.
- [ ] `P02.S06` - remove over-conservative unresolved-import entries; `pyproject.toml`.
- [ ] `P02.S07` - extend `playwright_stealth` stub if surface gaps remain; `stubs/playwright_stealth/__init__.pyi`.
- [ ] `P02.S08` - investigate single tomllib dict-any site; `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`.
- [ ] `P02.S09` - re-run inventory to confirm external-API site count drops; `scratch/out/summary.json`.

### Phase `P03` - test-file deliberate-suppression rewrite

The 19 `# ty: ignore[...]` and `# noqa: B010/E731` suppressions in
test files exist to construct invalid pydantic input or bypass lint
on test helpers. Rewrite using `pytest.raises`, named functions in
place of lambdas, or proper pydantic error-construction patterns.

- [ ] `P03.S10` - rewrite ty-ignore in master-key kdf-params test; `src/aeat/adapters/persistence/storage/master_key/test_kdf_params.py`.
- [ ] `P03.S11` - rewrite ty-ignore in bucket-manifest test; `src/aeat/adapters/persistence/storage/bucket/test_manifest.py`.
- [ ] `P03.S12` - rewrite ty-ignore in bucket-export-header test; `src/aeat/adapters/persistence/storage/bucket/test_export_header.py`.
- [ ] `P03.S13` - rewrite ty-ignore in master-key recovery-record test; `src/aeat/adapters/persistence/storage/master_key/test_recovery_record.py`.
- [ ] `P03.S14` - rewrite ty-ignore in workflow bucket-pointer test; `src/aeat/application/workflow/test_bucket_pointer.py`.
- [ ] `P03.S15` - rewrite ty-ignore in aggregation oss-ioss test; `src/aeat/application/aggregation/test_oss_ioss.py`.
- [ ] `P03.S16` - rewrite ty-ignore in vat oss test; `src/aeat/domain/vat/test_oss.py`.
- [ ] `P03.S17` - rewrite ty-ignore in pdf label-regex test; `src/aeat/adapters/inbound/pdf/test_label_regex.py`.
- [ ] `P03.S18` - rewrite ty-ignore in browser evasion test; `src/aeat/adapters/outbound/aeat/browser/test_evasion.py`.
- [ ] `P03.S19` - replace lambda noqa in aggregation grouping test; `src/aeat/application/aggregation/test_grouping.py`.
- [ ] `P03.S20` - replace setattr noqa in transactions import test; `src/aeat/application/transactions/test_import.py`.
- [ ] `P03.S21` - replace setattr noqa in auth sessions-storage test; `src/aeat/application/auth/test_sessions_storage_state_paths.py`.
- [ ] `P03.S22` - replace setattr noqa in modelos external-evidence test; `src/aeat/domain/modelos/test_external_evidence.py`.
- [ ] `P03.S23` - replace setattr noqa in sanitizer records test; `src/aeat/adapters/inbound/sanitizer/test_records.py`.

### Phase `P04` - domain/ suppression eradication

81 sites across 26 files. Cleanest expected wins; canonical pydantic
shapes already live here. Highest-leverage files: `_models.py` in
`invoices` (16) and `transactions` (16); `_loader.py` in registry (6);
`attachments/_models.py` (6).

- [ ] `P04.S24` - replace Any/cast in invoice models; `src/aeat/domain/invoices/_models.py`.
- [ ] `P04.S25` - replace Any/cast in transaction models; `src/aeat/domain/transactions/_models.py`.
- [ ] `P04.S26` - replace cast in registry loader; `src/aeat/domain/calculations/registry/_loader.py`.
- [ ] `P04.S27` - replace Any in attachment models; `src/aeat/domain/attachments/_models.py`.
- [ ] `P04.S28` - sweep remaining 22 domain files for suppression eradication; `src/aeat/domain/`.

### Phase `P05` - application/ suppression eradication

70 sites across 28 files. Highest-leverage files: `auth/_sessions.py`
(11), `auth/__init__.py` (6), `workflow/_models.py` (5).

- [ ] `P05.S29` - replace Any/cast in auth sessions; `src/aeat/application/auth/_sessions.py`.
- [ ] `P05.S30` - replace Any in auth package init; `src/aeat/application/auth/__init__.py`.
- [ ] `P05.S31` - replace Any in workflow models; `src/aeat/application/workflow/_models.py`.
- [ ] `P05.S32` - sweep remaining 25 application files for suppression eradication; `src/aeat/application/`.

### Phase `P06` - adapter-internal suppression eradication

86 sites across 31 files. Adapter code not at an external boundary.
Per the disciplined adapter-boundary policy these are direct fixes,
not shims. Highest-leverage file: encrypted-columns adapter (8).

- [ ] `P06.S33` - replace Any/cast in encrypted-columns adapter; `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`.
- [ ] `P06.S34` - sweep remaining 30 adapter-internal files for suppression eradication; `src/aeat/adapters/`.

### Phase `P07` - core/ suppression eradication

20 sites across 9 files. `core/json_contract.py` (6) ties to T-08 and
will be revisited when `SchemaEnvelope` is adopted in Wave 3.

- [ ] `P07.S35` - replace Any/cast in JSON-contract module; `src/aeat/core/json_contract.py`.
- [ ] `P07.S36` - sweep remaining 8 core files for suppression eradication; `src/aeat/core/`.

### Phase `P08` - entrypoints/ suppression eradication

7 sites across 6 files. Smallest leak surface.

- [ ] `P08.S37` - sweep 6 entrypoint files for suppression eradication; `src/aeat/entrypoints/`.

### Phase `P09` - dunder-override investigation

5 sites on 5 files. `__iter__` / `__getitem__` / similar overrides on
pydantic-extending types. Most likely must remain as pydantic v2
compatibility shims. Investigation determines whether each is
necessary or can be replaced with a typed pattern.

- [ ] `P09.S38` - investigate each dunder-override site and write report; `scratch/out/dunder_overrides.md`.
- [ ] `P09.S39` - replace removable dunder shims with typed patterns; `src/aeat/`.
- [ ] `P09.S40` - document irreducible shims with rationale comments; `src/aeat/`.

### Phase `P10` - 'other' bucket investigation

12 sites on 3 files. Sites that did not classify into any leak
category. Investigation determines correct categorisation and Phase
assignment.

- [ ] `P10.S41` - categorise the 12 unclassified sites; `scratch/out/other_sites.md`.
- [ ] `P10.S42` - dispatch each site to the correct Phase or address inline; `src/aeat/`.

### Phase `P11` - dual-checker strictness gate

Adopt `pyright` alongside the existing `ty` (`all = "error"`) for
cross-checker verification on `src/aeat/domain/` and
`src/aeat/application/`. Different inference algorithms catch
different issues.

- [ ] `P11.S43` - add pyright dev dependency; `pyproject.toml`.
- [ ] `P11.S44` - add pyright strict configuration; `pyrightconfig.json`.
- [ ] `P11.S45` - run pyright strict on domain and capture findings; `src/aeat/domain/`.
- [ ] `P11.S46` - run pyright strict on application and capture findings; `src/aeat/application/`.
- [ ] `P11.S47` - resolve pyright-only findings across domain and application; `src/aeat/`.
- [ ] `P11.S48` - wire pyright into CI alongside ty; `.github/workflows/`.

### Phase `P12` - regression gates

Mechanical prevention of suppression reintroduction. CI step plus
semgrep rules. Aligns with the prior-art research recommendation for
`semgrep` as the per-pattern enforcement layer.

- [ ] `P12.S49` - add semgrep rule rejecting new Any annotations; `.semgrep/rules/no-any-annotation.yml`.
- [ ] `P12.S50` - add semgrep rule rejecting new dict-str-Any declarations; `.semgrep/rules/no-dict-str-any.yml`.
- [ ] `P12.S51` - add semgrep rule rejecting new cast calls in domain and application; `.semgrep/rules/no-cast-in-domain.yml`.
- [ ] `P12.S52` - add semgrep rule requiring inline justification for new ty-ignore; `.semgrep/rules/justify-ty-ignore.yml`.
- [ ] `P12.S53` - wire semgrep into CI as gating check; `.github/workflows/`.
- [ ] `P12.S54` - close out Wave 1 by re-running suppression inventory; `scratch/out/suppressions.json`.

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

Sequencing has two hard ordering constraints:

- P01 must complete before any other Phase (the inventory drives all
  batching decisions). P01 is complete except for P01.S04 (pydantic
  audit tool) which is Wave 2 prep and can run alongside Wave 1.
- P02 (external-API stub acquisition) must complete before P06
  (adapter-internal sweep) and any Phase touching `adapters/outbound/`.
  Otherwise the adapter agents would lack the typed shims they need to
  reference.
- P11 (strictness gate) and P12 (regression gates) sequence last; they
  measure and lock in the result of all earlier Phases.

Parallel-eligible phases once P01 + P02 land:

- P03 (test-file rewrites) runs in parallel with P04 / P05 / P06 /
  P07 / P08; tests do not share files with production sweeps.
- P04 / P05 / P07 / P08 run in parallel; their file scopes are
  disjoint.
- P06 must wait for P02; once P02 lands, P06 runs in parallel with the
  others.
- P09 and P10 are small investigation Phases; run alongside the
  larger sweeps without blocking.

Recommended dispatch: Phase P02 first (small, unblocks everything else),
then P03 + P04 + P05 + P06 + P07 + P08 + P09 + P10 in parallel, then
P11 and P12 sequentially as the gate.

## Verification

Mission-success criteria, each mechanically checkable:

- The suppression inventory tool reports zero `cast()` calls and zero
  `Any` annotations under `src/aeat/domain/` and `src/aeat/application/`.
- The inventory reports zero `dict[str, Any]` / `Mapping[str, Any]`
  annotations under `src/aeat/domain/`, `src/aeat/application/`,
  `src/aeat/core/`, `src/aeat/entrypoints/`, and adapter-internal
  files (i.e., adapters not at an external API boundary).
- Remaining `cast` / `Any` / `dict[str, Any]` sites all sit inside
  files inside `src/aeat/adapters/outbound/` that are direct external
  API touchpoints (Playwright, Google Drive, Google Sheets, LLM,
  tomllib).
- `uv run --no-sync ty check` passes with the same `all = "error"`
  configuration.
- `uv run --no-sync pyright --strict src/aeat/domain src/aeat/application`
  passes.
- The 19 deliberate test suppressions are replaced with `pytest.raises`
  or named-function patterns; no `# ty: ignore` or `# noqa` survives
  in test files.
- CI gates green; semgrep rules in `.semgrep/rules/` reject any new
  suppression-equivalent annotation.

The plan is complete when every Step is closed (`- [x]`) and the
verification checks pass on the merged branch.
