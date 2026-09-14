---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:55bec3f665bd6eaf9296846e720ee0d6ad1f623c226212f42fc85386dddb30b4'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# `registry-authority-artifact-boundary` audit: `authoring relocation`

## Scope

Audited Step `W03.P04.S06` against the accepted immutable-runtime-publication decision. The review covered relocation of authored-registry, source-evidence, record-design, and compiler-conformance tests; the shipped-test census; preservation of relocated test intent; and removal of ignored raw-root parameters from the registry scenario runner and all callers.

## Findings

### authored-reader-census | high | The relocation gate passes while shipped tests still read authoring inputs

`test_shipped_registry_tests_have_no_operative_authored_registry_reader` originally recognized only calls whose statically reconstructed literal contained `registry/aeat`. It therefore reported zero offenders while shipped tests still scanned authored verification declarations and reached source evidence or record-design inputs indirectly through `bundled_path()`. The affected conformance responsibilities belonged under development dependencies.

### subprocess-reader-evasion | high | A shipped authoring-history reader still evades the strengthened census

After direct and dynamic filesystem reads were covered, a shipped naming test still invoked `git grep` over `src/cadrumo/_data/registry`. The authored path lived inside a subprocess argument list, so the filesystem-call detector missed it and the boundary suite passed despite the operative reader.

Closure (2026-09-12): resolved. Authored-source, record-design, and history/conformance tests now live under `dev/registry/tests`; test-name inventory confirms the moves and split preserved their tests. The census recognizes direct registry scans, dynamic `bundled_path()` receivers, official corpus reads, and subprocess list or tuple arguments for `run`, `check_call`, `check_output`, and `Popen`. Its adversarial cases pass, the shipped-tree sweep reports no operative authored reader, and the complete packaging boundary suite passes all seven tests. The scenario runner accepts only `scenario`; all 41 call sites were migrated without changing the runner's artifact-backed execution. No unresolved high or critical finding remains.

## Recommendations

Retain the adversarial reader cases and the shipped-test population floor as release-boundary regression guards. Extend the detector alongside any new filesystem or process abstraction that can access authored registry or corpus inputs.
