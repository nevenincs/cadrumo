---
tags:
  - '#exec'
  - '#user-docs-weight'
date: '2026-10-06'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:62549ff4e9482b9f61976542b7df8bf5ef2ff2b6a1ba28b4090dd19b30f46657'
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
- `S05` `M` `dev/deploy/docs_site_build.py`
- `S05` `M` `dev/deploy/docs_site_languages.py`
- `S05` `M` `dev/deploy/docs_site_preflight.py`
- `S05` `M` `dev/deploy/docs_delivery_contracts.py`
- `S05` `M` `dev/deploy/docs_asset_manifest.py`
- `S05` `M` `dev/deploy/docs_delivery_probe.py`
- `S05` `M` `dev/deploy/docs_health.py`
- `S05` `M` `dev/deploy/tests/test_docs_static_site.py`
- `S05` `M` `dev/deploy/tests/test_docs_asset_delivery.py`
- `S05` `M` `dev/deploy/tests/test_publish_preflight_search_records.py`
- `S05` `M` `dev/deploy/tests/test_published_delivery_content.py`
- `S05` `M` `dev/docs/tests/test_deployment_search_parity.py`
- `S05` `verify:` `pytest dev/deploy (122 tests)` -> `pass`
- `S05` `verify:` `pytest dev/docs/tests/test_deployment_search_parity.py (26 tests)` -> `pass`
- `S05` `verify:` `compose the published layout over the four roots built 2026-10-06: one apex index, 25.5 MB in 16,713 files, preflight accepted` -> `pass`
- `S05` `verify:` `ruff and ty on dev/deploy` -> `pass`
- `S05` `by:` `vaultspec-high-executor`

## Notes

- `S09` The published web site keeps one index per language: its delivery checks are per-language and move with S05.
- `S09` docs/pagefind.yml was never read by the index pass; its selectors now live in `dev/docs/pagefind_index.py` and take effect, so navigation, header, footer and recorded JSON leave page records.
- `S09` One stemmer serves every language, so plurals of languages other than Spanish no longer fold; exact and prefix matching is unaffected.
- `S03` native/package-layout.json needed no change: its entry and search keys now name addresses.
- `S04` The packaged end-to-end test and the live-package test were not run: both need an assembled package in the new form.
- `S05` The publisher takes its pages from one producer function and still compiles each language there; composing them from the one compile is that function's change once S06 to S08 are proven.
- `S05` No real web-flavour build and no network delivery were run; the English full-scope root under en/ is covered by a test over real built pages.
- `S05` A release published before this change is refused by manual rollback and activate until the next successful publish; automatic recovery inside a publish is unaffected. Supporting both release shapes is left to the operator.
