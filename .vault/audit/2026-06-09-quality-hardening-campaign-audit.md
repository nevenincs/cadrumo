---
tags:
  - '#audit'
  - '#quality-hardening-campaign'
date: '2026-06-09'
related:
  - "[[2026-06-08-repo-health-diagnostics-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace quality-hardening-campaign with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `quality-hardening-campaign` audit: `justfile audit baseline: 2026-06-09 quality hardening kickoff`

## Scope

Full read-only sweep of every quality lane exposed by the repository `justfile`,
run on 2026-06-09 against the shared `chore/eliminate-shims` worktree, to
establish the consolidated baseline for the quality-hardening campaign. Lanes
covered: the static `check-*` gates (`check-style`, `check-format`,
`check-imports`, `check-relative-imports`, `check-dependencies`,
`check-security`, `check-types`) and the advisory `audit-*` lanes
(`audit-complexity`, `audit-dead-code`, `audit-duplication`). This audit is the
campaign root; each red lane becomes a tracked workstream burned down
incrementally. It continues the rolling repo-health trail without restating its
closed steps.

## Findings

### QHC-000 | GREEN | Five lanes already pass on the current baseline

`check-format`, `check-imports` (hexagonal layering contracts), `check-relative-imports`,
`check-dependencies` (deptry), and `audit-dead-code` (vulture) all exit 0 on
HEAD. The earlier repo-health pass recorded broken import-linter contracts and
relative-import violations; both are now green, so the structural-boundary
workstream is no longer red. No action required beyond keeping them green as a
regression guard during the campaign.

### QHC-001 | CLOSED | check-style: one E501 over-long docstring line

`just check-style` reported a single E501 (155 > 120) at
`src/aeat/application/calculations/_cross_period_clean_state.py:5` — a docstring
line cross-linking `RegistrySnapshot` and `ValidatedRegistryAuthority`.
Resolution: wrapped the sentence across lines, preserving both core-struct
cross-references. `just check-style` now exits 0. Landed on the campaign branch.

### QHC-002 | CLOSED | check-security: two semgrep pickle findings in the registry cache

`just check-security` reported 2 blocking semgrep findings
(`python.lang.security.deserialization.pickle.avoid-pickle`) at
`src/aeat/domain/calculations/registry/_loader.py:1064` (load) and `:1074`
(dump), in the `_load_registry_tree_cached` performance cache introduced by the
recent registry-perf commit. The cache deserialises only first-party data the
same process wrote, keyed by a sha256 of the registry-tree fingerprints; no
untrusted input crosses the boundary and a foreign/corrupt file is suppressed
and recomputed. Resolution: documented the trust rationale inline and added
`nosemgrep` markers at the two audited lines (fix-or-justify-at-line, not a
blanket production exclusion, per the `.semgrepignore` policy). `just check-security`
now exits 0.

### QHC-003 | OPEN | audit-complexity: 28 production functions above cognitive threshold 20

`just audit-complexity` exits 1: 260 cyclomatic grade-C+ blocks, 8 files below
maintainability grade A, and 28 production functions above the cognitive
threshold of 20. The dominant hotspots, in descending cognitive cost:

- 108: `src/aeat/domain/calculations/registry/_loader.py::_apply_locales` — by
  far the worst; a locale-merge routine.
- 48: `src/aeat/application/calculations/_cross_period_clean_state.py::_evaluate_requirement`.
- 44: `src/aeat/domain/calculations/registry/_bindings_previous_filing.py::resolve_previous_filing_binding_values`.
- 37: `src/aeat/domain/calculations/registry/_record_design_coverage.py::calculation_closure_identities`.
- 37: `src/aeat/entrypoints/cli/_config/_google.py::_push_secure_object_mirror_rows`.
- 34: `src/aeat/domain/calculations/registry/_cross_revision_divergence.py::_iter_cross_revision_casilla_divergences`.
- 32: `src/aeat/application/live/_errors.py::classify_live_iva_acquisition_failure`.
- 30: `src/aeat/domain/calculations/registry/_invoice_bindings.py::_validate_invoice_fact_and_aggregation`.
- 29: `_record_design_coverage.py::calculation_closure_numbers`, `_config/_repair_profile.py::register_repair_profile_command`.
- 27: `calc_sheets/_workbook_export.py::_apply_styling`, `_remote_state_guard.py::_validate_policy`, `_validate_semantic_role_typos.py::_semantic_role_looks_like_typo`.
- 25–26: a cluster across sede `_declarations`, secure-object migration, declaracion `_parser`, auth `_authenticator`, modelo `_m210_rate`/`_profile_binding`, cross-period `_evaluate_filing_history`.

Lowest-maintainability files: `_record_design.py` (0.0), sede
`_iva_compensation_wallet.py` (1.3), `_loader.py` (7.3),
`_workbook_parity.py` (9.4), `_schema.py` (14.8), `_formula_runtime.py` (16.2),
ledger `_models.py` (17.0), `_cross_period_clean_state.py` (18.7). Burn down via
behaviour-preserving helper extraction, worst-first, each paired with focused
tests and a re-run of the production complexity lane.

### QHC-004 | OPEN | audit-duplication: 51 clone groups (0.5% duplicated lines)

`just audit-duplication` reports 51 clone groups. The actionable clone families:

- Sede `_groi_check.py` / `_nif_iva_check.py` checker shapes (two clones, the
  largest 17 lines / 184 tokens).
- Registry `_counterpart_bindings.py` / `_invoice_bindings.py` binding builders
  (33-line / 452-token clone plus a 19-line clone).
- Registry `_bindings_previous_filing.py` / `_relations.py` relation-validation
  helpers.
- Registry `_aeat_nif_iva_oracle.py` / `_groi_oracle.py` oracle logic (26 lines).
- `core/errors/registry/_domain_part2.py` / `_domain_part3.py` error-hierarchy
  blocks (62-line / 379-token clone, plus intra-file repeats).
- Modelo work CLI `_modelo_work_verification_cli.py` / `_modelo_work_runs_cli.py`
  / `_modelo_work_revision_cli.py` rendering/addressing blocks (41-line clone).
- `_config/_google_sync_calc.py` intra-file repeats.

Consolidate one cohesive subsystem at a time. Apply the substitutability
pre-filter before promoting any "X where Y exists" — only merge when the
constraint shapes match.

### QHC-005 | OPEN | check-types: 3282 diagnostics (2383 ty + 899 pyright)

`just check-types` exits 1. ty over full `src` reports 2383 diagnostics;
pyright over the strict domain+application lane reports 899. The ty profile is
dominated by `unknown-argument` (1134) and `missing-argument` (116), which
cluster almost entirely in Typer-decorated CLI command modules
(`entrypoints/cli/_app_live.py` 154, `_config/__init__.py` 146, `_config/_google.py`
127, `_modelo_discovery_cli.py` 85) — i.e. checker mismodelling of the Typer
callback signature, not production bugs; these need a triage decision (per-module
suppression vs. a typed-callback pattern) rather than blind edits. The
mechanically-real, high-value subset:

- `missing-override-decorator` (174, ty) — add `@override`; purely mechanical.
- `reportMissingParameterType` (320, pyright) — annotate parameters.
- `reportArgumentType` (334) / `invalid-argument-type` (575, ty) — real boundary
  type drift (constructor normalisation, optional narrowing).
- `reportUnsupportedDunderAll` (36) — `__all__` entries that do not resolve.

Worst pyright file is `application/user_profile/_commands.py` (105). This lane is
the largest and is ratchet-shaped: burn down by diagnostic class, typed-boundary
fixes preferred over blanket ignores, and separate the Typer-callback noise from
genuine drift before quoting a target number.

## Recommendations

1. Quick-win gates (QHC-001, QHC-002) are closed; keep them green as regression
   guards.
2. Drive `audit-complexity` (QHC-003) worst-first, starting with
   `_loader.py::_apply_locales` (108) and `_evaluate_requirement` (48). Behaviour
   preserving extraction only; pair every reduction with focused tests and a
   complexity-lane re-run.
3. Consolidate `audit-duplication` (QHC-004) families one subsystem at a time;
   the sede checkers, the registry binding builders, and the modelo work CLI
   blocks are the cleanest first slices.
4. Triage the `check-types` (QHC-005) Typer-callback noise before quoting a
   target; land the mechanical `@override` and parameter-annotation classes
   first, then the real argument-type drift by package.
5. Treat suite runs as rolling checkpoints; never declare the campaign "done".
   Re-run the relevant lane after each landed slice and update this audit.

## Codification candidates

None yet. The campaign's mechanics (fix-or-justify-at-line for semgrep,
behaviour-preserving extraction for complexity, substitutability pre-filter for
duplication, typed-boundary-over-ignore for types) are already captured by
existing rules. A codification candidate will be reconsidered only if a burn-down
slice surfaces a durable, cross-session, project-bound constraint not already
covered.
