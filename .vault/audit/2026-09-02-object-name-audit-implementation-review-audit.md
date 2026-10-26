---
tags:
  - '#audit'
  - '#object-name-audit'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:adb382f4a30b1817ba70c228baeb7959dfae125f20526a2937d0dae9f0ad516e'
related:
  - "[[2026-07-01-import-centralization-adr]]"
---
# `object-name-audit` audit: `implementation review`

## Scope

Reviewed the object-name census, its focused contract tests, and the `audit-object-names` just recipe against the accepted canonical-definition decision and the approved boundary: public module-level declarations in `src/` and `dev/` are enforced, while private and test declarations are advisory. The review checked declaration coverage, duplicate and singular-name classification, deterministic reporting, fail-closed behavior, detector teeth, recipe execution, and isolation from unrelated worktree changes.

## Findings

### declaration-census | high | same-module and conditional declarations escape the uniqueness check

`declarations_in_source` visits only direct children of `Module.body`, so a class or function bound at module scope inside `if`, `try`, `with`, or loop statements is absent from the census. Separately, `analyse` reduces all declarations to one entry per path and kind before comparison. That reduction correctly needs to account for overload sets, but it also accepts two ordinary class definitions or two ordinary function definitions with the same public name in one module. A focused probe returned no declarations for `if True: class Invoice: ...` and no enforced finding for two consecutive public `Invoice` class definitions. Both cases allow multiple definition sites or an overwritten binding to pass the check, contrary to the object-uniqueness boundary and the accepted single-definition authority.

### root-enrolment | high | absent source roots pass cleanly

`_python_files` silently excludes any configured root for which `is_dir()` is false. Consequently, scanning absent `src/` and `dev/` roots returns zero declarations and zero enforced findings. A checkout, invocation, or path-resolution defect can therefore remove the entire authority surface from inspection while the command exits successfully. Source parse and read errors fail closed, but root enrolment does not.

### singularity-heuristic | medium | singular names ending in s are rejected

The class and enum rule treats nearly every final PascalCase word ending in `s` as plural. The live audit flags `OperatorActionAxis` and `OrthogonalAxis`, although "axis" is singular. The fixed exception tuple cannot make an open natural-language vocabulary sound, so other legitimate singular terms can also fail. This creates deterministic output but not a reliable singularity invariant and risks forcing semantically incorrect renames.

### detector-teeth | medium | tests encode a blanket redeclaration exemption and omit command-level failure contracts

The focused suite passes, including a test that treats every repeated function name in one module as an overload without requiring `@overload`. It does not demonstrate detection of an ordinary same-module redeclaration, a conditional module-level declaration, an absent root, or a legitimate singular noun ending in `s`. It also does not exercise `main` or the just recipe to prove exit zero for a clean fixture and exit one for an enforced defect. The present tests therefore validate the implementation's blind spots instead of proving the requested gate boundary end to end.

### module-main-exemption | high | the function entry-point exemption suppresses public module collisions

The shared `main` name exemption is applied after declarations of every kind have been grouped. With modules now enrolled, two public `main.py` stems produce no finding, and a public `main.py` module colliding with a module-level class named `main` is also suppressed. A focused probe enrolled two module sites and one class site named `main` across `src/` and `dev/` but returned no finding. The conventional entry-point exemption is valid for repeated functions, not for the newly required public module-stem uniqueness or cross-kind object-uniqueness boundary. The focused tests do not cover this interaction.

## Recommendations

- Replace the direct-`Module.body` census with a scope-aware traversal that enrolls declarations which bind the module namespace while excluding methods and nested function/class bodies. Preserve every definition site.
- Exempt only syntactically verified overload declarations, and distinguish supported mutually exclusive definitions explicitly; report ordinary same-module redeclarations.
- Require every configured scan root to exist and be readable, emitting an enforced source/enrolment error otherwise.
- Replace the suffix heuristic with an explicit, reviewed naming policy that can prove singular terms such as "axis" pass. If singularity cannot be decided mechanically without false positives, separate uncertain cases into advisory findings.
- Add defect fixtures for all missed census and enrolment paths, plus direct `main` exit-code coverage and a focused recipe smoke test.
- Scope the `main` exemption to function declarations only, and add module/module and module/object defect tests for the `main` stem.

## Re-review status

- Resolved: the declaration census now traverses module control-flow without descending into class or function scopes. Ordinary same-module redeclarations retain both sites and fail; a syntactically decorated overload family with one concrete implementation collapses to one binding.
- Resolved: every configured root is checked before enumeration, and an absent root emits an enforced source error with exit code one.
- Resolved: `axis` is included in the reviewed non-plural suffix vocabulary, and `OrthogonalAxis` passes the singularity check.
- Resolved: focused detector tests now cover same-module redeclarations, conditional module declarations, genuine overloads, missing-root refusal, the `Axis` lexical exception, and exit-code behavior. The 17-test suite passes. A live `just audit-object-names` smoke run also propagated exit code one from the current repository findings.

No open implementation-review finding remains from this audit. The live repository still contains reported object-name findings; those are audit results to remediate, not defects in the detector surfaces reviewed here.

## Final module-extension review

Public module stems are enrolled at deterministic path-and-line sites, exact duplicate stems fail across `src/` and `dev/`, plural public stems fail, and module/class/function collisions share the same exact-name engine. Private module stems and test-path modules remain advisory. Reverse-order and live-scan behavior remain deterministically sorted. The prior control-flow, same-module redeclaration, overload, missing-root, and `Axis` fixes remain intact; the focused suite passes 20 tests.

The actual `just audit-object-names` command runs successfully as a gate and propagates exit code one for the live inventory of 61,507 declarations, 781 enforced findings, and 1,523 advisory findings. Final closure remains blocked only by the `main` module/cross-kind exemption recorded above.

## Final closure

Resolved: the `main` exemption is now applied only to declarations whose kind is `function`. Public `main.py` module stems remain in the comparable declaration set, and module/module plus module/class collisions produce enforced findings. A combined probe with two public `main` modules, a class named `main`, and repeated entry-point functions returned one enforced finding containing exactly the two module sites and the class site; the functions remained exempt.

The two dedicated regression tests pass, and the complete focused suite passes 22 tests. The actual `just audit-object-names` command still propagates exit code one for the live repository inventory of 61,510 declarations, 781 enforced findings, and 1,523 advisory findings. No implementation-review finding remains open.

## Live findings inventory

Measured from the shared worktree on 2026-09-02 with `just audit-object-names --json`. The command exited one after scanning 61,496 declarations. It reported 2,303 findings: 781 enforced findings, comprising 189 exact duplicate-name collisions and 592 plural-looking public names, plus 1,522 advisory private or test collisions. No source-read or source-parse error was present. The enforced population touches 898 unique Python paths. A final same-day remeasurement after a concurrent tree edit counted 61,497 declarations while all finding counts and classifications remained unchanged.

### gate-state | critical | the repository has 781 enforced object-name violations

The gate is operational but red. Its default human renderer prints the first 50 findings and truncates 2,253; remediation must therefore use the deterministic JSON output as the complete manifest and rerun the live command before and after each batch. A passing detector test does not change this repository-level failure.

### duplicate-name-population | high | 189 collisions require semantic adjudication before renaming

The duplicate set contains 69 module-only, 55 function-only, 54 function-and-module, nine class-only, one class-and-enum, and one enum-only collision. Site cardinality ranges from two to 68. Of the 189 findings, 120 are wholly below `src`, 40 wholly below `dev`, and 29 cross the two roots. High-cardinality generic stems include `errors`, `conftest`, `models`, `secure_objects`, `protocols`, `service`, `schema`, `manager`, and `screen_authority`. These findings prove competing names, not equivalent implementations: each needs an owner-versus-distinct-concept decision before a target name is selected.

### plural-name-population | high | 592 public names are lexical rename candidates, mostly modules

The plural set comprises 429 modules, 158 classes, and five functions. It is concentrated in `src/cadrumo` with 548 findings; development tooling contributes 42 and `src/cadrumo_harness` contributes two. Frequent final nouns include `errors` (74), `facts` (39), `models` (39), `bindings` (19), `records` (15), `inputs` (13), `fields` (11), `details` (11), and `protocols` (11). The detector uses a conservative hard-coded suffix heuristic rather than domain semantics, so every proposed singular name still needs a vocabulary check; blind singularization can produce a misleading or already-claimed name.

### advisory-population | medium | 1,522 private and test collisions remain visible but do not fail the gate

All advisory findings are exact-name collisions. They are outside the zero-tolerance surface by design, but they should remain in the JSON inventory during remediation because a public rename can collide with an advisory declaration or change whether a finding is enforced. Advisory cleanup must not be mixed into an enforced batch unless its ownership and test intent are explicit.

### detector-boundary | high | object-name results do not prove absence of overlapping code content

The audit parses Python below `src` and `dev`, inventories module stems and module-level classes, enums, and functions, and checks exact-name collisions plus plural-looking final nouns. It excludes methods and nested declarations, exempts `main` functions, and does not compare bodies, behavior fingerprints, copy similarity, or responsibility overlap under different names. A green object-name gate would make responsibilities easier to identify, but it cannot by itself establish that the codebase contains no semantic duplication.

### rename-blast-radius | critical | module renames can escape the edited Python file set

The 429 plural modules and 123 collision findings involving modules are the highest-risk surface. A module rename must update direct and type-only imports, dynamic import strings, plugin or registry lookup strings, import-boundary configuration, packaging manifests, API-documentation directives, tests, and generated references through their owning generators. The displaced path must then be removed atomically without an alias module, re-export, forwarding wrapper, or compatibility shim.

## Remediation safety boundary

Before any live rename, build a reviewed one-to-one old-to-new manifest and reject duplicate targets, targets already present in the declaration census, ambiguous ownership, and mixed unrelated edits. Re-measure the live tree immediately before each small ownership-isolated batch.

Rehearse the exact batch against a disposable copy of the current dirty tree under the system temporary directory, not against a clean `HEAD` snapshot that omits contributor changes. Apply only the manifest there, then inspect the complete changed-path set and run the object-name audit, focused import and owning tests, import-boundary checks, static typing and linting, generator checks, and residue searches for both symbol and module spellings. The rehearsal is acceptable only when every changed path is explained, intended findings disappear without new findings, the old import path is absent, and no unrelated module moves. Delete or abandon only that verified temporary target.

Apply the identical reviewed manifest to the live worktree only after the rehearsal passes. Re-read affected files and the live diff first, preserve concurrent edits, and run the same gates sequentially. Stop the batch on unexpected changed paths, newly introduced collisions, dynamic-reference residue, generated drift, or unrelated failures that prevent proving the rename. Do not compensate with a shim or broad cleanup.

## Audit disposition

The detector implementation review is closed, but repository remediation is not ready for blind execution. The complete enforced JSON inventory is the authoritative work queue for naming violations; collision entries require semantic ownership decisions, while plural entries require reviewed singular vocabulary. A separate semantic-duplication audit is required if the acceptance criterion includes absence of overlapping code behavior rather than name clarity alone.
