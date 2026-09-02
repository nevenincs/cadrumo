---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:8487f89b8a1a01b5b744830a51db50cb535c94268fd3b54b4b2efdfe04b3ef7b'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `s09 transform review`

## Scope

Reviewed the live `dev/quality/object_name_transform.py` implementation for
`W02.P04.S09` against the accepted ADR, reference, plan, and current manifest
and graph contracts. The review covered read-only proposal behavior, raw-byte
preconditions, exact allowlist equality, module moves, LibCST definition and
qualified-reference handling, dynamic and generated refusal, unsupported
constructs, deterministic outputs, and the no-shim boundary. No implementation
or test file was changed.

The live implementation performs no filesystem mutation, resolves normalized
paths without traversing links, rechecks every declared byte precondition,
sorts operations and outputs deterministically, refuses declared dynamic and
generated reference classes, refuses string-literal references on affected
Python surfaces, and requires the actual proposed path set to equal the reviewed
allowlist. Ruff lint and formatting, canonical `ty` checking, bytecode
compilation, and live import passed.

## Findings

### definition-locator-selection | high | Definition discovery ignores the locator's symbol name

`_definition_lines` selects every declaration with the requested kind and
binding occurrence but does not compare the declaration name from the old
locator. Binding occurrences are counted per kind-and-name, so ordinary distinct
classes or functions in one module commonly all have occurrence one. A
disposable production-path probe renaming `Widgets` in a file that also defines
`Other` caused both lines to be selected; transformation then refused the valid
operation because the `Other` line did not name `Widgets`. This prevents safe
renames in normal multi-declaration modules and makes the expected-definition
hit count describe the wrong binding set.

### cross-package-relative-import | high | Module moves can silently retarget relative imports

A module move may cross package boundaries, but transformation parses and emits
the source using its old module context and copies those bytes to the new target.
Relative imports inside the moved module that do not themselves name the renamed
module are left unchanged. A disposable production-path probe moved
`src/cadrumo/old.py` containing `from .support import VALUE` to
`src/other/new.py`; the proposal succeeded and emitted the same relative import,
changing its runtime authority from `cadrumo.support` to `other.support`. The
manifest and allowlist can therefore be satisfied while the moved module's
meaning changes silently.

## Recommendations

Resolve `definition-locator-selection` by parsing the old locator's qualified
leaf and selecting declarations only when kind, name, and binding occurrence all
match. Preserve overload-family behavior and require the resulting exact lines
to be transformed. Add a multi-class and multi-function regression fixture in
`W02.P04.S10`.

Resolve `cross-package-relative-import` by either rewriting every relative
import against the old package into an equivalent import valid at the new
package, or refusing cross-package moves whenever package-relative semantics are
present. Refusal is safer for the first controlled engine. Cover same-package
success, cross-package absolute-import success, and cross-package relative-import
refusal in S10.

Retain the current read-only output contract, exact byte and allowlist checks,
linked-path refusal, unsupported reference-class refusal, deterministic
ordering, and absence of compatibility shims. Comprehensive detector-teeth
coverage for these working paths remains assigned to S10. Two high findings
remain open; no critical, medium, or low finding is recorded.
