---
tags:
  - '#audit'
  - '#desktop-shell'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:6a53931cfce4e4f2aa108fa46e13f36f2396b9d892a0ea50c18d47b0d221995b'
related:
  - "[[2026-10-04-desktop-shell-plan]]"
  - "[[2026-10-04-canonical-environment-plan]]"
---

# `desktop-shell` audit: `desktop-shell committed work review`

## Scope

Independent read-only review on 2026-10-05 of committed desktop-shell work (S01 docs and delegated-inventory parts of a87038dd6d, d12e3e06b2, 233a8c2e33; S02 a18b028b54; S03 5aabe8be7e; S08 da945b366f and 10066c1c71; S18 89fe544a85 and a7b9e8e891) and canonical-environment S01 c4214c73a9 with its projection 00f44b5ae1, against the accepted desktop-shell, canonical-environment, interpreter-foundation, distribution, runtime-manager and sign-in decisions. Uncommitted S04 to S07 and another writer's in-flight storage-vector move were excluded. Verdict: revision required. S08 fails on one high boundary finding; S01, S02, S03 and canonical-environment S01 and S02 pass with findings; S18 passes.

## Findings

### contract-step-ids | high | contract.ts names plan Step identifiers in shipped frontend source

`native/desktop/frontend/src/ipc/contract.ts` introduced in da945b366f labels types with plan Step identifiers and fences the terminal block with Step-named markers, which the rule that code stands alone forbids. Comments must describe behavior, for example that a command is not yet served or that a field is present only when the page lists the feature. Reopens S08.

### relocated-root-test | medium | S02 relocated-layout test asserts the working-directory default that canonical-environment rejects

`native/desktop/src-tauri/src/terminal/tests.rs:289-291,361` at a18b028b54, carried into the uncommitted `terminal/tests/live.rs`, asserts that installed mode anchors at the launch directory and that an unpinned child nests. It passes only because `native/platform/src/lib.rs` still walks the working directory, and fails once canonical-environment S03 lands. The tui-kind block asserts nothing directly.

### product-allowlist-development-root | medium | the product allowlist projects the development-only root variable into installed packages

`src/cadrumo/core/storage_environment.py:505` builds the product allowlist from both root variables, so the generated contract lets the installed host pass the development variable to children, contrary to the accepted decision's statement that it is not projected into installed packages. The decision's wording is itself inconsistent between two passages.

### import-load-targets-stale | medium | committed import-load targets omit the new dev modules

At a7b9e8e891 `dev/quality/metadata/import_load_targets.dev.json` lacks `dev.docs.desktop_palette`, `dev.locales.desktop_chrome` and the three new `dev.packaging.native` docs and inventory modules, so the collectability gate fails at HEAD.

### docs-build-root-literal | medium | docs_build.py spells the storage root variable literally

`dev/packaging/native/docs_build.py:39` writes the root variable name as a literal inside the canonical-environment literal-gate scope; it predates the decision's acceptance. `native/cmake/Packaging.cmake:64,71` test environments carry the same literal and belong to the packaging owner.

### json-array-token | low | committed contract and dispatcher disagree on a JSON byte-array body

contract.ts says a byte-array body carries the token in the header, while `app.rs:52` at a18b028b54 reads only the argument from any JSON body. No committed command uses that path; the uncommitted dispatcher change fixes it and needs a test landing with it.

### remote-gate-coverage | low | the remote-reference gate checks HTML attributes only

`dev/packaging/native/docs_stage.py:64-75,129-148` does not scan staged CSS url() and import rules, inline style attributes, refresh meta, form actions or imagesrcset.

### inventory-path-parity | low | three inventory readers validate member paths differently

Python and Rust agree; `native/interpreter/bootstrap.py:45-49` lacks reserved-name, trailing-dot and control-character refusals, and no shared vectors prove parity.

### web-flavor-identity | low | the web flavor byte-identity verification was narrowed to the script list

`dev/docs/tests/test_docs_desktop_flavor.py:211` compares script sources only, not the fixture page the plan named.

### temporary-files-spelling | low | the declaration module spells the temporary-files location twice

`src/cadrumo/core/storage_environment.py:491` spells the variable and subpath while `child_environment` reads the taxonomy member.

### pending-verification | low | end-to-end proof remains pending and is not a code defect

Pending: the full four-language docs build and rebuild behavior, the Release docs bundle and the shell frame-src change (S01); the adversarial docs-frame isolation proof (S10, no interactive session in Session 0); a re-run of S02 live tests on a current package; Rust replay of the conformance vectors (canonical-environment S03) and the literal gate (S05); confirmation that Windows profile workers receive non-secret settings through the operation request.

### localized-term-records | medium | localized docs search returns Spanish-key term titles and domain crumbs

Observed by the designer session on 2026-10-05 against the 2026-10-04 Catalan web-flavor build with the current bridge: term results carry unaccented lowercase Spanish keys as titles (for example "regimen del recargo de equivalencia") and Spanish domain words in the crumb, taken from Pagefind record meta read at `docs/_static/cadrumo-docs.js:554-571` and produced by the record injection in `dev/docs/pagefind_inject.py` and `dev/docs/terminology/concept_card_projection.py`. Needs confirmation on a fresh desktop-flavor build, currently blocked by the stale authority; if confirmed, the localized term records should carry the localized display title and domain label rather than the canonical key.

## Recommendations

- contract-step-ids: rewrite the comments behaviorally when S08 adds the terminal types.
- relocated-root-test: derive the expected root from an explicit absolute root or the per-user default and assert the tui exit status.
- product-allowlist-development-root: project only the primary root variable for installed packages, give development its own projection, and reconcile the canonical-environment decision wording.
- import-load-targets-stale and docs-build-root-literal: regenerate and commit the targets; read the variable from the declaration and hand the CMake literals to the packaging owner.
- Low findings: extend the remote gate to CSS and attributes, add shared path vectors replayed by pytest and Rust, either restore the fixture-page comparison or record the narrower claim, read the temporary-files member, and land the dispatcher array test with the S04 to S07 commit.
- Add a test proving app plugins expose no invoke handler beyond the dispatcher, and include Docs.cmake only when docs are packaged or the desktop is configured.
