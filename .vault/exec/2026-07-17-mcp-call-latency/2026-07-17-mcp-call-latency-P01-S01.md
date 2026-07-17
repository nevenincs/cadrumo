---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace mcp-call-latency with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
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
     The Add a validation-verdict record keyed by the complete registry-tree, convenio, and source-evidence fingerprint tuples plus package version and outcome, with load, store, and delete-on-mismatch helpers using real filesystem behavior and ## Scope

- `src/cadrumo/domain/calculations/registry/_validate_verdict.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a validation-verdict record keyed by the complete registry-tree, convenio, and source-evidence fingerprint tuples plus package version and outcome, with load, store, and delete-on-mismatch helpers using real filesystem behavior

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_verdict.py`

## Description

- Add `_validate_verdict.py`: a strict pydantic `ValidationVerdict` record (`extra="forbid"`, frozen) carrying `verdict_key`, `package_version`, and `outcome`.
- Add `compute_verdict_key` folding the complete fingerprint tuples the authority already computes (registry tree plus convenio, and the source-evidence set) plus the package version into one SHA-256, with a per-group label so a tuple cannot collide across groups.
- Add `verdict_cache_path` deriving the writable per-storage-root location from a new settings field, filename hashed on the resolved root path so distinct registry roots never share a file while a fingerprint change on one root rewrites in place.
- Add `bundled_verdict_path` returning the read-only shipped location as a sibling of the bundled tree (never inside the fingerprinted tree it certifies), and `None` for any mutable authoring tree.
- Add `read_verdict` (strict-parse, `None` on absent/unreadable/foreign), `write_verdict` (atomic sibling-temp plus `os.replace`), and best-effort `delete_verdict`.
- Add `registry_validation_is_certified` (writable verdict first with delete-on-mismatch, then the read-only shipped verdict) and `certify_registry_validation` (persist a fresh green verdict).
- Add the `cadrumo_validation_verdict_cache_dir` settings field and its `cache/registry-verdict` state-root derivation; classify it unbounded-by-design in the settings lifecycle gate.
- Add real-filesystem helper tests: location derivation, distinct-root files, sibling shipped path, roundtrip, foreign-file tolerance, certify-then-match, and delete-on-mismatch.

## Outcome

Landed the verdict record and its load/store/delete-on-mismatch helpers plus the settings surface. `ruff check`, `ruff format --check`, and `ty check` clean on the touched files. `test_validation_verdict_location.py` (10 helper tests), the settings lifecycle and state-root gates, and the registry reviewability line-budget gate all pass; the new `_validate_verdict.py` stays well under the 300-line `_validate*.py` reviewability ceiling. Registry collection is clean.

The authority read/skip wiring (S02), the release-build stamp (S03), and the authority-integration regression pin (S04) build on these helpers.

## Notes

The verdict is derived and rebuildable: a key mismatch or a foreign record deletes the writable verdict and forces a full re-validation, with no migration path per no-legacy-compatibility. The shipped verdict is deliberately a sibling of the registry root so its own presence never perturbs the fingerprint it certifies. No incidents; no scaffolds left in code.
