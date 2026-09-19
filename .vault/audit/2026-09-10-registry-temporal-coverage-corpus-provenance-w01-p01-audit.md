---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:15fe9a90e7e6c13e137ee0b871c99c2bcbc3d903a67fb56cfcddf910b72dae55'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# `registry-temporal-coverage` audit: `Corpus provenance classifier review`

## Scope

Review the W01.P01 classifier and fixture suite before it becomes the shared provenance boundary for registry validation.

## Findings

### path-containment | high | Initial resolution accepted escaped normative paths

The first implementation confined resolved target files only to a broad source root. Review identified traversal plus file and directory symlink paths, including both direct and packaged-data layouts, that could otherwise select bytes outside the normative corpus. The final resolver requires strict descent from its expected normative tree and each tree's containing root. Regression fixtures cover traversal, file and directory escapes, packaged-data escape, and equality-symlink bypasses.

### test-isolation | low | The initial out-of-scope proof patched a production path method globally

The first fixture used a global `Path.read_bytes` patch to show that non-normative targets are not read. Review rejected that observation mechanism because it could affect unrelated work. The final test proves the early return through the public resolver and classifier without patching production filesystem methods.

## Recommendations

Keep corpus resolution centralized at this boundary. Any future caller that derives provenance must use the resolver rather than reconstructing a corpus path from a registry string.
