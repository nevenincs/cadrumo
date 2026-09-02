---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:1aa7343ddeff99341786cc41f8299eb0cee92a973aab324b2165dd7c1248e661'
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

# `object-name-declustering` audit: `s04 manifest tests review`

## Scope

Reviewed `dev/quality/tests/test_object_name_manifest.py` for `W01.P02.S04`
against the current production manifest loader, accepted ADR, repository
reference, plan, and detector-teeth rules. The review covered real TOML parsing,
strict schema refusal, path safety, ambiguity and repeated finding operations,
inventory and byte drift, advisory findings, target collisions, locator/path
binding, Python module targets, linked paths, generated ownership, canonical
digesting, execution selection, and successful symbol and module manifests. No
production or test code was changed.

The suite exercises the real `scan`, TOML loader, Pydantic models, live
filesystem preconditions, validator, digest serializer, and execution selector.
It completed with 37 passing tests and no skip. Ruff lint and formatting passed
for the test and production modules, and canonical `ty` checking passed for both.

## Findings

### target-refusal-teeth | medium | Canonical target and Python-module refusals are not exercised

The success helpers derive `new_locator` with the same `dataclasses.replace`
shape used by production, but no negative test deliberately makes a symbol
locator disagree with its path or binding occurrence, makes a module locator
disagree with its target package, or gives a module rename a non-`.py` target.
These checks closed a high and a medium during S03 review. Without direct
counterexamples, deleting or weakening the production target-binding and suffix
guards leaves all 37 tests green. The existing module move-without-name-change
case exercises a separate semantic-name refusal and does not cover these guards.

### prohibited-disposition-teeth | medium | The raw-zero disposition prohibition has no regression case

The strict-schema parametrization checks coercion, unknown fields, lifecycle
typing, and operation-ID syntax, but never submits `keep-distinct`. Removing that
literal closed an S03 high finding and implements the ADR's raw-zero contract.
Reintroducing it as an adjudication-only disposition would not fail the current
suite because only valid lexical and `merge-authority` operations are exercised.

### manifest-link-boundary | low | Linked affected paths are covered but linked manifest files are not

The real symlink test proves `_repo_path_without_links` refuses a linked changed
path component and ran successfully on this host. No test presents the TOML
loader itself with a symlinked manifest, so the separate `is_link_like(path)`
guard in `load_object_name_manifest` can regress unnoticed. This is a narrow
loader-boundary gap; the broader mutation-surface link safety has detector teeth.

## Recommendations

Add isolated refusal cases that mutate an otherwise valid symbol target's module
and binding occurrence, mutate a module target's package locator, and set the
module target path and move target to a non-`.py` suffix. Each case should call
the production validator and assert the owning refusal rather than an incidental
earlier model error.

Add `keep-distinct` to the real-TOML strict-loader refusal matrix so the accepted
vocabulary cannot widen silently.

Add a filesystem-backed manifest symlink case for
`load_object_name_manifest`, retaining the existing affected-component symlink
test. Platform inability may skip only the link construction case; the current
host demonstrated that link creation is available.

## Resolution evidence

The amended suite now sends otherwise valid operations through the production
model and validator with a symbol target in the wrong module, a changed binding
occurrence, a module locator in the wrong package, and a non-`.py` module target.
Each reaches and asserts its owning target-binding or Python-source refusal.
This closes `target-refusal-teeth`.

A dedicated production-model case now submits `keep-distinct` and asserts the
strict accepted disposition vocabulary. Reintroducing the prohibited value can
no longer leave the focused suite green, closing
`prohibited-disposition-teeth`.

A real TOML manifest is now addressed through a filesystem symlink and the
production loader refuses it as non-regular input. The case ran on this host
without a skip, complementing the existing affected-component link test and
closing `manifest-link-boundary`.

The final focused suite completed with 42 passing tests and no skip. Ruff lint,
Ruff formatting, and canonical `ty` checking passed for the test and production
modules. No critical, high, medium, or low finding remains open for
`W01.P02.S04`.
