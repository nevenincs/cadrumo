---
tags:
  - '#exec'
  - '#user-docs-weight'
date: '2026-10-06'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:e8ba8a0a0f5fd6027c0946080d85e9a4b86fad8fd0150bc1f3e1102c17881380'
related:
  - "[[2026-10-06-user-docs-weight-plan]]"
---

# `user-docs-weight` ledger

## Changes

- `S01` `A` `dev/docs/shared_structure.py`
- `S01` `A` `dev/docs/tests/test_shared_structure.py`
- `S01` `verify:` `pytest dev/docs/tests/test_shared_structure.py` -> `pass`
- `S01` `verify:` `ruff check and format on both files` -> `pass`
- `S01` `verify:` `ty check on both files` -> `pass`
- `S01` `verify:` `factor and compose the four desktop roots built 2026-10-06 (561 pages, 2244 comparisons, 0 mismatches)` -> `pass`
- `S02` `A` `dev/docs/language_roots.py`
- `S02` `A` `dev/docs/tests/test_language_roots.py`
- `S02` `verify:` `pytest dev/docs/tests/test_language_roots.py dev/docs/tests/test_shared_structure.py (23 tests)` -> `pass`
- `S02` `verify:` `ruff check and format on both files` -> `pass`
- `S02` `verify:` `ty check on both files` -> `pass`
- `S02` `verify:` `store the four desktop roots built 2026-10-06 (382.1 MB, 62720 files) as 156.0 MB and compare every file composed back (0 differences)` -> `pass`
- `S09` `M` `dev/docs/pagefind_index.py`
- `S09` `M` `dev/docs/pagefind_inject.py`
- `S09` `M` `dev/docs/build.py`
- `S09` `M` `dev/docs/build_paths.py`
- `S09` `M` `dev/packaging/native/docs_build.py`
- `S09` `M` `docs/_static/cadrumo-docs.js`
- `S09` `M` `docs/_templates/base.html`
- `S09` `M` `docs/_templates/search.html`
- `S09` `M` `docs/conf.py`
- `S09` `D` `docs/pagefind.yml`
- `S09` `A` `dev/docs/tests/test_shared_search_index.py`
- `S09` `M` `dev/docs/tests/test_pagefind_index.py`
- `S09` `M` `dev/docs/tests/test_pagefind_config.py`
- `S09` `M` `dev/docs/tests/test_pagefind_inject_site.py`
- `S09` `M` `dev/docs/tests/test_deployment_search_parity.py`
- `S09` `M` `dev/docs/tests/test_docs_desktop_flavor.py`
- `S09` `M` `dev/packaging/native/tests/test_docs_build_environment.py`
- `S09` `verify:` `pytest test_shared_search_index test_pagefind_config test_pagefind_index test_pagefind_inject_site test_pagefind_index_write_target test_docs_desktop_flavor (58 tests)` -> `pass`
- `S09` `verify:` `one index over the four built desktop roots: 31.9 MB in 16,824 files against 62.7 MB in 60,261` -> `pass`
- `S09` `verify:` `ruff and ty on the touched Python` -> `pass`
- `S09` `by:` `vaultspec-high-executor`
- `S03` `M` `dev/packaging/native/docs_stage.py`
- `S03` `M` `dev/packaging/tests/test_native_docs_staging.py`
- `S03` `M` `dev/packaging/tests/test_native_docs_references.py`
- `S03` `M` `dev/docs/tests/test_shared_structure.py`
- `S03` `verify:` `pytest dev/packaging/tests/test_native_docs_staging.py dev/packaging/tests/test_native_docs_references.py` -> `pass`
- `S03` `verify:` `stage the four desktop roots built 2026-10-06 with the real stage_roots: 107.2 MB in 15,706 files, every built file composed back and compared` -> `pass`
- `S04` `A` `native/desktop/src-tauri/src/docs/compose.rs`
- `S04` `M` `native/desktop/src-tauri/src/docs/site.rs`
- `S04` `M` `native/desktop/src-tauri/src/docs/request.rs`
- `S04` `M` `native/desktop/src-tauri/src/docs/mod.rs`
- `S04` `M` `native/desktop/src-tauri/src/docs/tests.rs`
- `S04` `M` `native/desktop/tests/packaged.test.mjs`
- `S04` `M` `native/CONTRACT.md`
- `S04` `verify:` `cargo test --locked (desktop host crate, 144 tests)` -> `pass`
- `S04` `verify:` `cargo clippy --locked --all-targets -- -D warnings` -> `pass`
- `S04` `verify:` `rustfmt --check src/docs` -> `pass`
- `S04` `by:` `vaultspec-high-executor`

## Notes

- `S09` The published web site keeps one index per language: its delivery checks are per-language and move with S05.
- `S09` docs/pagefind.yml was never read by the index pass; its selectors now live in `dev/docs/pagefind_index.py` and take effect, so navigation, header, footer and recorded JSON leave page records.
- `S09` One stemmer serves every language, so plurals of languages other than Spanish no longer fold; exact and prefix matching is unaffected.
- `S03` native/package-layout.json needed no change: its entry and search keys now name addresses.
- `S04` The packaged end-to-end test and the live-package test were not run: both need an assembled package in the new form.
