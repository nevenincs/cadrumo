---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:efc415921b3e2d257ef425b0634665896ed2da9f4f03e8c156e434ae3cfb1a20'
step_id: 'S292'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Extract the shared journal-repository file substrate, noting the two classes are constraint-shape divergent so this is extraction rather than replacement

## Scope

- `src/cadrumo/application/config_reset.py`
- `src/cadrumo/application/user_profile/_bundle_export_operation.py`

## Description

- Confirmed `ConfigResetJournalRepository` (in `_config_reset_repository.py`) and `ProfileBundleExportJournalRepository` (in `user_profile/_bundle_export_operation.py`) are constraint-shape divergent — different operation models, error taxonomies, and lifecycle surfaces (reset owns creation-exclusivity, incompleteness gating, and deletion-ownership verification; export owns deletion, isolating scan, and prepared-state selection) — but share an identical atomic per-file JSON substrate: init, `root`, `path_for`, `save`, `load`, `list`, `_ensure_root`, `_validate_existing_root`, `_write`, `_journal_paths`, operation-id validation, and link-like refusal, differing only in journal dirname, model parser, error classes, and message subject.
- Extracted (not replaced) that common substrate into a generic `JournalRepositoryBase[T: JournalOperation]` with a structural `JournalOperation` Protocol, parameterized by journal dirname, resolved storage root, operation parser, error types, and message subjects.
- Made both concrete repositories subclass the base, each resolving its settings to a storage root and passing the bindings up, while keeping every divergent method verbatim.
- Homed the base in the application layer (`application/_journal_repository.py`) rather than core: both consumers are application persistence code, and `application/user_profile` is a descendant of the base's owning package `application`, so the descendant import is legitimate under the import-hygiene ownership rule (Family-1 cross-package test stays green).
- Updated the fresh-process recovery crash-injection harness, which keyed the `save` trace on the definition filename, to also match `_journal_repository.py` now that `save` lives in the base.

## Outcome

The atomic journal file substrate has one owner, `JournalRepositoryBase`, extracted from the two divergent repositories rather than collapsing them. Each repository keeps its distinct model, error taxonomy, and lifecycle surface and inherits the shared read/write mechanics.

Home-selection rationale: an earlier attempt to home the base in `core` (both consumers already import `core` heavily) tripped a pre-existing fragile import chain — `core.locks` imports `core.config`, whose settings validator lazily imports the `pointer_path`/`read_pointer` facade names; importing the base eagerly from `core/__init__` pulled that chain in before the facade names were bound, and `import cadrumo.core` failed with a partially-initialized-module error. The application layer imports core only after core is fully initialized, so it has no such cycle, and the import-hygiene gate confirms the two descendant importers are legitimate.

Discovery basis: the mandated `vaultspec-rag` code index was measured untrustworthy (mid-rebuild, control probes missed), so a structural AST duplicate scan supplied the cluster and every claim was re-established by exact `rg` search and by reading both classes in full.

Verification (HEAD `a4ccd70c3e16898587cc74f33f40b2cdcf7dce45`):

- `uv run --no-sync ruff check` / `ruff format --check` clean on all touched source files (PEP 695 native type parameters per the project's UP046 rule; one import-sort auto-fix).
- `uv run --no-sync python -m dev.docs.apidocs scaffold --check` — `Stub tree is conformant.` (the new module's stub and its parent toctree are staged; no peer stubs swept).
- `uv run --no-sync pytest src/cadrumo/application/tests/test_config_reset_recovery.py -m "unit or integration" -n0 -q` — 11 collected, `11 passed in 84.07s` (fresh-process roll-forward across every durable boundary).
- `uv run --no-sync pytest src/cadrumo/application/tests/test_config_reset_concurrency.py src/cadrumo/application/bucket_maintenance/tests/test_service_delete.py src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py -m "unit or integration" -n0 -q` — 27 collected, `27 passed in 115.03s`.
- `uv run --no-sync pytest src/cadrumo/application/tests/test_config_reset_repository.py src/cadrumo/application/user_profile/tests/test_bundle_export.py -m "unit or integration" -n0 -q` — 22 collected, `22 passed in 18.98s`.
- Mutation proof: replacing the shared base `_write` payload with a fixed stub JSON reddened both repositories' suites simultaneously — `6 failed, 16 passed` across `test_config_reset_repository.py` (reset) and `test_bundle_export.py` (export) — proving both genuinely consume the single substrate; restored to `22 passed`.
- Clean-room HEAD-import proof (the untracked-sibling hazard for a new extracted module): the new `_journal_repository.py` was staged into the same commit as its two importers (`git cat-file -e HEAD:...` confirms it is tracked). Proven from outside the worktree: `git archive HEAD src/cadrumo` extracted into a fresh temp directory carrying no untracked files, then `PYTHONPATH=<tmp>/src python -c "import cadrumo.application._config_reset_repository / ...user_profile._bundle_export_operation"` loaded `cadrumo` and both importers from the archive path (asserted the worktree src was shadowed, not leaked). A clean checkout imports; the committed-module-imports-untracked-sibling defect is absent.

## Notes

The initial `core` home broke `import cadrumo.core` via a pre-existing `core.locks`->`core.config`->facade cycle; resolved by relocating the base to the application layer (see Outcome). The recovery crash-injection harness coupled to the `save` definition file and needed the one-line relocation-follow-up above — behaviour was preserved, only the definition file moved.

Unrelated pre-existing failure observed and confirmed NOT mine: `test_import_hygiene_gate.py::test_family2_shim_modules_are_exactly_the_documented_bridges` reds on `src/cadrumo/entrypoints/cli/_wizard_payloads.py`, a peer's committed wizard shim (commit `73f06fa1f2`) tracked by this plan's own open Steps S286/S293. My `_journal_repository.py` is a real base class, not a shim; it is not referenced in the gate or its baseline, and the Family-1 cross-package-private-import test passed.
