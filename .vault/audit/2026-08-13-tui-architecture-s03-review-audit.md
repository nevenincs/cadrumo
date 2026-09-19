---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:816c82fd8524d0b381f003a9a1cf95ed095be28cf8bdabd4bbd51b61f7b94b09'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `W01.P01.S03 TUI AST boundary review`

## Scope

Independent review of `W01.P01.S03` against the accepted TUI architecture decision, research, S01/S02 authorities, current import-hygiene scanner and gate tests, S03 execution evidence, and applicable architecture and quality rules.

## Findings

### private-name-facade-import | high | Static private-facade imports through a public module path are not detected

`find_tui_boundary_violations` tests `has_private_component(site.target_mod)` but never evaluates `site.imported_names`. A canonical TUI module can therefore use `from cadrumo.application.operations import _registry` or an equivalent private exported name while the target module remains the public facade and no `PRIVATE_FACADE` violation is emitted. The planted test reaches the deep module directly, so it does not exercise the facade-bypass form D11 explicitly forbids.

### annotation-expression-bypass | high | Non-string annotation expressions can name the TUI without detection

`_annotation_strings` returns only string constants inside annotation ASTs. With `import cadrumo` followed by `def consume(value: cadrumo.entrypoints.tui.App)`, the static import targets only `cadrumo` and the annotation contains attributes rather than a string constant, so neither static-import nor annotation detection fires. The sole annotation test uses a quoted forward-reference string and does not prove the general annotation prohibition.

### legacy-textual-admission | high | Legacy Textual permission is broader than the accepted S01 migration facts

The live gate builds `accepted_legacy_consumers` from every S01 row consumer, then exempts any such module from Textual-location enforcement. S01 pins legacy-TUI declarations and consumer edges, not Textual imports, so an already-listed consumer may add a new direct Textual import without changing the S01 digest. In addition, every present or future module beneath `dev.tui` is unconditionally exempt. These package/consumer-wide permissions contradict the claimed fixed-point join and admit new Textual identities during migration.

### registration-name-allowlist | medium | Registration detection recognizes only five hard-coded call names

`_registration_strings` scans literal arguments only when the called leaf name is one of `register`, `register_plugin`, `add_plugin`, `load_plugin`, or `entry_point`. A semantically equivalent registration such as `registry.add("cadrumo.entrypoints.tui.launcher:main")` or a project-specific registrar escapes. The single planted `register_plugin` case proves only membership in this name allowlist, not the D11 prohibition on registering from the TUI.

## Recommendations

- Reuse the canonical private-import resolution semantics for both module targets and imported private names, and add public-facade/private-name plus dynamic-public-module/private-attribute bite tests.
- Resolve annotation name and attribute expressions as well as strings; plant both forms so either detector regression reds the gate.
- Derive exact admitted Textual importer facts from a digest-bound census of Textual locations, with no consumer-wide or future-package-root exemption; prove a new Textual import in an existing S01 consumer and a new `dev.tui` module both fail.
- Replace the registration call-name allowlist with resolved registration semantics or a complete static string-reference rule scoped to executable call operands, and prove alias and alternate-registrar forms.

## Final re-review disposition

### private-name-facade-import | closed | Public-facade private imported names are rejected

The scanner now checks `site.imported_names` for underscore identities inside the canonical TUI and emits `PRIVATE_FACADE`; the focused matrix plants `from cadrumo.application.operations import _registry` alongside direct-private and dynamic-private forms.

### annotation-expression-bypass | closed | Expression annotations resolve aliases and attribute chains

`_annotation_references` now resolves names and complete attribute expressions through the import-alias map as well as quoted strings. The planted `import cadrumo as root` plus `root.entrypoints.tui.App` annotation proves the previously missed form.

### legacy-textual-admission | open-high | S01 consumer modules still receive blanket Textual permission

The package-root exemptions were narrowed and planted new files under both legacy roots now fail, but the live gate still constructs `accepted_modules` from every S01 legacy module and every S01 consumer, then exempts an importer whenever its module name is in that set. The S01 digest binds module and consumer identity, not the existence of a Textual import edge. An already accepted CLI, application, test, or development consumer can therefore add `from textual...` without changing the S01 digest and remain exempt. This is not an exact digest-governed Textual-location census.

### registration-name-allowlist | open-medium | Literal targets still depend on registrar-name tokens

Object-reference arguments now cross any non-dynamic call boundary, but literal string targets are recorded only when the called leaf contains `register`, `bind`, `provide`, `plugin`, or `mount`. The new `bind_target` string and `provide(object)` tests exercise those recognized shapes; an arbitrary semantic registration such as `registry.add("cadrumo.entrypoints.tui.launcher:main")` still escapes, preserving the original name-vocabulary defect.

Exact focused evidence is recorded: 15 TUI-boundary tests passed in 159.94 seconds and Ruff passed. Those results prove the implemented cases but do not close the two remaining fail-open forms.

## Final closure disposition

### legacy-textual-admission | closed | Exact consumer-target edges are digest governed

The scanner now admits only exact `(consumer module, Textual target)` pairs. The live census is checked against fixed digest `ff45a174acd6c53d0f6265770462d9b28b65b03dd72127f8a9e64de0a63b7ebe` before those pairs are supplied to the boundary scan. The planted accepted-consumer case admits its existing `textual.app` edge but rejects a newly added `textual.containers` edge, closing the former module-wide exemption.

### registration-name-allowlist | closed | Literal TUI targets cross every ordinary call boundary

`_registration_references` now examines literal and resolved object arguments for every call except the separately governed dynamic-import callables, without inspecting the callee name. The planted `registry.add('cadrumo.entrypoints.tui.launcher:main')` case directly proves the previously escaping arbitrary-call form.

The exact focused gate evidence is complete: 16 tests passed and 19 were deselected in 170.46 seconds for `tui_boundary or accepted_textual_consumer`; the focused Ruff check passed. No critical, high, or medium findings remain.
