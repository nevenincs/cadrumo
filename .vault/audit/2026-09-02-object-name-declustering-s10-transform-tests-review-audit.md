---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:4cbe9767cd7f3d1fd1ece828eb48e09b10f4f80df36c96954176d5843e289075'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace object-name-declustering with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `object-name-declustering` audit: `s10 transform tests review`

## Scope

Reviewed `dev/quality/tests/test_object_name_transform.py` for `W02.P04.S10`
against the current transformer, accepted ADR, reference, plan, and resolved S09
audit. The review mapped detector teeth for exact symbol and module edits, import
forms, binding precision, cross-package relative imports, dynamic and generated
classes, star and string references, ambiguity, parsing failures, byte and path
safety, occupied targets, allowlist equality, determinism, and live-tree
immutability. No implementation or test file was changed.

The suite exercises the real object-name inventory, strict manifest model,
LibCST metadata transformer, filesystem bytes, and immutable proposal result.
It completed with 16 passing tests and no skip. Ruff lint and formatting and
canonical `ty` checking passed for the test and production modules.

## Findings

### distinct-name-locator-teeth | medium | The S09 definition-selection defect can regress undetected

`test_binding_locator_renames_only_the_selected_redeclaration` uses two
declarations with the same name and selects occurrence two. The defective S09
algorithm selected by kind and occurrence, so it would already choose only the
second declaration and pass this test. The bug appeared when distinct class or
function names in one module each had occurrence one. Reverting the production
fix from exact `qualified_locator` matching to kind-plus-occurrence therefore
leaves all current tests green. The test does not close the exact reviewed
counterexample.

### module-package-boundaries | medium | Supported module-move boundaries lack positive evidence

The suite proves same-package absolute import rewriting and cross-package
relative-import refusal, but it does not prove a same-package move containing a
relative import succeeds unchanged or that a cross-package move containing only
absolute imports remains supported. These positive boundary cases were explicit
S09 review recommendations. A guard broadened to refuse every relative import or
every cross-package move could pass the current tests, leaving safe reviewed
module operations unusable.

### linked-path-authority | low | Link refusal is tested through a mock rather than a linked fixture

The linked-component case replaces `is_link_like` with a lambda. It proves the
transformer reacts to a positive signal but does not exercise real path
traversal, symlink or junction detection, or interaction with `Path.is_file` in
the isolated repository. The repository detector-teeth rule calls for mutating
an isolated fixture so a safety test fails for the owning real reason. S04 has
real manifest-link coverage, but it does not protect this transform path.

## Recommendations

Add the exact multi-declaration regression with `Widgets` and an unrelated
`Other` class or function, both occurrence one, and assert only `Widgets` is
renamed. This test must fail if `_definition_lines` stops comparing complete
qualified locators.

Add a same-package module move whose source retains a relative import, plus a
cross-package move whose source uses only absolute imports. Assert exact target
bytes and live-tree immutability in both supported cases while retaining the
existing cross-package-relative refusal.

Replace or complement the mocked linked-component case with a real symlinked
directory or file inside `tmp_path`, skipping only when the host genuinely
cannot create the link. Retain the current broad coverage for exact edits,
absolute import forms, declared unsupported classes, star/string/f-string and
ambiguous references, syntax errors, stale bytes, unsafe authored paths,
occupied targets, allowlist mismatch, determinism, fresh content views, and live
immutability. Two medium and one low finding remain open; no critical or high
finding is recorded.
