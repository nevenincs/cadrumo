---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S297'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S297 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Give every corpus-scanning emptiness gate a non-zero subject floor, or prove per gate that its corpus cannot silently empty, since 87 in-surface gates assert an offender list empty without proving they scanned anything and a path rename would green them while the forbidden condition survives and ## Scope

- `src/cadrumo/`
- `dev/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Give every corpus-scanning emptiness gate a non-zero subject floor, or prove per gate that its corpus cannot silently empty, since 87 in-surface gates assert an offender list empty without proving they scanned anything and a path rename would green them while the forbidden condition survives

## Scope

- `src/cadrumo/`
- `dev/`

## Description

- Run both the ad-hoc candidate scanner and the canonical vacuity screen; classify corpus-scanning emptiness gates as genuine (directory/module walks that silently empty on a rename) versus false positives (fixed-path reads that raise loudly, deliberate absence assertions, detector controls, and gates already floored by a same-corpus sibling).
- Add two floored corpus helpers to the CLI backend-boundary gate and floor the application-plus-entrypoints walk inline, covering six walk-gates that assert an offender list empty with no proof the walk reached the CLI surface.
- Floor the modelo-CLI-module corpus at its source helper, covering four decomposition guards that iterate it.
- Floor the runtime-text-file corpus of the retired-command-phrase gate, the two source-and-docs scan corpora of the retired-custody and retired-reset spelling gates, and the tracked-executable corpus of the single-jscpd-runner gate.
- Fix a live vacuity defect the new floor exposed: the retired-command-phrase gate computed its repository root one directory too shallow, so it had been scanning zero files and passing vacuously since inception; correct the root depth and resolve the one benign match it then surfaced (a module docstring documenting the retired command path) by rewording the prose.
- Mutation-check every floor by collapsing its corpus in a throwaway probe and confirming the gate fails on the floor rather than passing.
- Second pass, the source-tests tranche: floor the production-source live-test-opt-in walk in the marker-integrity gate, and floor the outside-source-tree project-test walk in the skip/xfail gate; both mutation-checked. Read and exclude the remaining tranche candidates as already-controlled (sibling discovery floors, self-flooring bidirectional pins, structurally-non-empty constant unions, documented pre-flip dormancy, and detector controls over injected or synthetic input).

## Outcome

PARTIAL — a coherent sub-family closed, Step left OPEN with a named residue boundary.

Command (the touched gates, run together):

`uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_backend_boundary.py src/cadrumo/entrypoints/cli/tests/test_architecture_boundaries.py src/cadrumo/entrypoints/cli/tests/test_retired_cli_literals.py src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py dev/audit/tests/test_duplication.py -m "integration or unit" -p no:cacheprovider -q`

Collected and passed: 61 (non-zero). Exit line: `61 passed in 32.95s`. HEAD at run: `c7a7c6eee70ede281f35d696c0ffe68b2201eb33`.

Floored (12 gate functions across 5 files), each mutation-verified to fail on a collapsed corpus:

- Backend-boundary gate: two floored corpus helpers plus one inline floor cover the deleted-profile-import walk (the calibration case), the duplicate-aggregation-CLI walk, the censo-foundation walk, the registry-corpus-ownership walk, the observability-wrapper walk, and the process-language test-file walk. Floors fire at 0 files (mutation confirmed on the helper and on a consumer).
- Architecture-boundaries gate: floor at the modelo-CLI-module corpus helper covers the legacy-root-import, raw-id-regex, legacy-selector, and centralized-addressing guards. Floor fires at 0 modules (mutation confirmed).
- Retired-command-phrase gate: floor at the runtime-text-file corpus. Floor fires at 0 files (mutation confirmed) — and it caught a genuine pre-existing defect (see Notes).
- Retired-custody and retired-reset spelling gates: floor after the shared source/locale/doc scan. Both floors fire at 0 files (mutation confirmed).
- Single-jscpd-runner gate: floor at the tracked-executable corpus. Floor fires at 0 files (mutation confirmed).

Excluded after reading (verified false positives of the heuristic):

- Backend-boundary fixed-path gates (`read_text` over hardcoded tuples) and the removed-module `.exists()` gates: a rename raises loudly or the tuple is a literal, so neither can silently empty.
- Architecture-boundaries single-file reads of the legacy root: a rename raises through the AST resolver.
- Educational-docs cited-verb and relative-link gates: a same-module sibling asserts the shared docs corpus is non-empty, so the corpus cannot silently empty.
- Doc-privacy tracked/untracked ban gates: the root is `git rev-parse --show-toplevel` (raises on a non-repo) and the module carries planted-leak anti-tautology controls, so the corpus cannot silently empty.
- Duplication coverage-read gate: a deliberate empty-tuple input to a property test, not a corpus scan.

Second pass — the `src/cadrumo/tests/` tranche plus the `dev/audit` remainder.

Command (the two floored gates in isolation):

`uv run --no-sync pytest src/cadrumo/tests/test_marker_integrity.py::test_live_test_opt_in_token_is_not_used_by_production_aeat_live_paths src/cadrumo/tests/test_no_skip_xfail.py::test_project_tests_outside_source_tree_do_not_skip -m "unit or integration" -p no:cacheprovider -q`

Collected and passed: 2 (non-zero). Exit line: `2 passed in 24.08s`. HEAD at run: `efefe0e8b594529bf0db784f8dc5b4134937147f`.

Floored (2 gate functions across 2 files), each mutation-verified to fail on a collapsed corpus:

- Marker-integrity gate: floor the production-source live-test-opt-in walk (`src/cadrumo/{adapters,application,core,entrypoints}`, 1015 modules, floor 200). Fires at 0 (mutation confirmed).
- Skip/xfail gate: floor the outside-source-tree project-test walk (158 modules, floor 20); the sibling discovery guardrail floors only the in-tree corpus, not this one. Fires at 0 (mutation confirmed).

Excluded after reading (already-controlled; ~41 candidates across this tranche):

- Dev-path-isolation (11): detector silence proofs over injected synthetic roots, and the module already carries a live-scan vacuity floor.
- Marker-integrity (9 of 10): floored via the sibling that asserts the shared module inventory reaches `src/cadrumo`, or self-flooring bidirectional pins that red on collapse via equality against a non-empty expected set, or fixture-based over that same floored inventory.
- Mock-inventory (4) and broad-exception-raises (3): consume a fixture over the shared control-module inventory, floored by a sibling discovery guardrail.
- Skip/xfail (2 of 4): fixture-based over the floored discovery corpus; one is a detector silence control over synthetic input.
- Persisted-format-enrollment (3): one structurally floored by a non-empty constant union, one whose registry a sibling subscripts (loud on collapse), one documented as intentional pre-flip dormancy under the compatibility-lifecycle regime.
- Import-hygiene (2): one pins the committed baseline value (not a scan); one is a detector silence control over planted modules.
- Console-script-imports (2): a subprocess return-code equals-zero (not an empty collection); a fixed-path absence assertion.
- Legal-attribution-screen (3): detector controls over synthetic catalogue entries.

Third pass — the CLI conformance gates plus `application/user_profile` and `bucket_maintenance`, completing the in-surface read.

Command (the five floored gates in isolation, with two shared functions):

`uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py::test_cli_has_no_bare_emit_definition_import_or_call src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py::test_no_bare_emit_json_success_call src/cadrumo/entrypoints/cli/tests/test_modelo_registry_bindings_surface.py::test_no_parallel_bindings_typer_outside_canonical_module src/cadrumo/entrypoints/cli/tests/test_registry_corpus.py::test_no_top_level_normatives_or_manual_root_verb_is_registered src/cadrumo/entrypoints/cli/tests/test_registry_corpus.py::test_no_aeat_normatives_or_manual_fetch_verb_under_app_registry -m "integration or unit" -p no:cacheprovider -q`

Collected and passed: 5 (non-zero). Exit line: `1 failed, 5 passed` on the first batch run — the one failure was the reverted audit-remediation gate (see residue); the five kept floors are the 5 passed, re-confirmed green in the full 194-passed module run at HEAD `6378048c29cca07ad013e3d0ce71d3af61008c86`.

Floored (5 gate functions across 3 files), each mutation-verified to fail on a collapsed corpus:

- JSON-schema conformance: floor the two bare-emit AST scans (`_emit` definition/import/call over `entrypoints/cli`, floor 50; `emit_json_success` over `entrypoints/cli` + `application`, floor 200). Both fire at 0 (mutation via a chdir to an empty root, since these use a relative scan path).
- Modelo-registry-bindings surface: floor the parallel-bindings-Typer walk over the CLI tree (floor 100). Fires at 0.
- Registry-corpus: a shared floored helper `_cli_source_modules` routes both root-verb boundary scans (floor 100). Both fire at 0.

Excluded after reading (already-controlled; the rest of the conformance and application candidates):

- JSON-schema `test_every_cli_leaf_has_a_registered_schema`: self-flooring — a collapsed command-tree walk leaves the whole non-empty `SCHEMA_REGISTRY` as orphans, so the symmetric-difference reds. Sibling custody-key gates self-floor via a fixed non-empty key set plus a registry subscript; the secret-material scan is a detector-controlled pass over that same floored registry; the notice-field and removed-key gates are parametrized-over-constant or fixed-list absence checks.
- Determinism `test_enrolled_commands_are_all_registered`: self-floors (`ENROLLED - SCHEMA_REGISTRY` reds on a collapsed registry).
- Documented-command `test_no_new_aeat_plain_fences` and `..._inline_aeat_command_spans`: same-corpus sibling asserts `len(_user_doc_pages()) >= 20`; the module also carries an invocation-count `_VACUITY_FLOOR`.
- In-process envelope parity: already floors `grounded >= 100`.
- Custody-completeness: self-floors (`len(TYPED_CATEGORY_NAMESPACES) == 5` pin, and the subtraction reds on a collapsed registry).
- Bundle-export-recovery (6), bundle-export (1), registration (2): behavioural assertions over a test-controlled `tmp_path`/`storage_root` (leftover-temp cleanup, refused-registration side-effects), not codebase scans.
- Registry-cli-live (3), fast-path-no-state (2), json-error-contract, app-agent-plugin, app-maintenance-reconcile, ledger-evidence confirm/extract, ledger-classify-fixture, profile-export-roundtrip, google-sync-push (7), root-fallback-write-guard: single-operation behavioural tests over ephemeral dirs.
- Config-custody-profile-lifecycle: fixed-path reads over a hardcoded three-file dict (loud `FileNotFoundError` on a rename).

## Notes

- The retired-command-phrase gate was a live instance of the exact defect this Step hunts, and the correction matters for the record: this defect class was classified LATENT in the formal review, but this instance was ACTIVE — already lying at HEAD. Its repository-root literal was one directory too shallow (the expression resolved to `<repo>/src`), so its two runtime surfaces resolved to the non-existent paths `<repo>/src/src/cadrumo` and `<repo>/src/env`, and it scanned zero files while passing green. The class therefore contained at least one gate that was already false-green, not merely one that could become so. The new floor surfaced it; correcting the root then surfaced one benign match — a module docstring stating the old command path is retired — resolved by rewording so the literal no longer appears while the meaning is preserved. This is a production-source edit inside the campaign surface, made only after confirming no peer WIP on the file.
- The floored consumers in the backend-boundary and architecture-boundaries gates inherit their floor from a called helper; the ad-hoc candidate scanner is function-scoped and cannot see an out-of-function floor, so it will still list those consumers. That is expected and is why the mutation-check, not the scanner, is the proof.
- The second-pass full-module run of `test_marker_integrity.py` and `test_no_skip_xfail.py` also reported three failures in functions this Step did not edit — `test_module_pytestmark_is_first_test_statement`, `test_source_test_comments_and_docstrings_do_not_reference_campaign_metadata`, and `test_no_skip_or_xfail_shortcuts` (the last firing on two `pytest.skip` calls in the MCP stdio-lifetime test). Those files are committed at HEAD and outside this campaign's surface, and both floored gates pass in isolation, so the three are pre-existing peer/HEAD debt distinguished from this Step's work, not a regression it introduced.
- Third pass surfaced a live peer regression, not a vacuity finding: `test_typer_help_sources_are_direct_translations` (in the CLI audit-remediation gate) is RED at HEAD because peer commit `a8dbc4f91a` ("refactor(locales): split the five locale-surface complexity hotspots", 2026-07-28) introduced four plain `help=` string literals in `src/cadrumo/locales/cli.py` (lines 136/140/144/148) instead of `tr(...)` calls. That gate ALSO carries a genuine latent vacuity — its corpus is the relative path `Path("src/cadrumo")`, which scans nothing if the working directory is ever not the repo root (the root-literal fragility this campaign hunts). A floor there is the right fix, but flooring a gate that is currently red on an unrelated peer regression would commit a red gate, and resolving the regression requires wrapping the four strings through the locales CLI (the peer-owned locale surface, out of this Step's scope). The floor plus a `PROJECT_ROOT`-anchoring of the scan path should land once the locale regression is fixed by its owner.
- RESIDUE (Step left OPEN for one precisely-named, peer-blocked item). The full in-surface candidate set has now been read and classified across three passes: the CLI/entrypoints walk-gates, the `src/cadrumo/tests/` tranche, the `dev/audit` gates, the CLI conformance gates, and the `application/user_profile` and `bucket_maintenance` candidates. Every genuine corpus-scanning emptiness gate has been floored and mutation-verified EXCEPT one — `test_typer_help_sources_are_direct_translations` — which cannot be resolved here because it is currently red on peer regression `a8dbc4f91a` in a peer-owned locale surface. Recommended handoff: the locales owner wraps the four `help=` literals in `src/cadrumo/locales/cli.py` through the locales CLI, after which the floor and `PROJECT_ROOT` anchoring for that gate land trivially. The `dev/docs`, `dev/packaging`, and `dev/deploy` candidates remain explicitly out of this campaign's scope.
