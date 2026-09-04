---
tags:
  - '#reference'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:5a95f569ce521504ec3727623512196a0a03ff639bfded9295b02ed5aee0d015'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #reference) and one feature tag.
     Replace reachability-burndown with a kebab-case feature tag, e.g. #foo-bar.
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

# `reachability-burndown` reference: entrypoint reachability and semantic uniqueness

## Scope

The shipped package carries code no declared console script can reach. The reachability
audit walks the import graph from `[project.scripts]` and counts only non-test
`src/cadrumo` modules as use, so a module or symbol that only tests or `dev/` touch is
reported with that outside use shown as a label. This document surveys that backlog and
records the technique for deciding what each finding is.

## Measured backlog

Measured 2026-09-04 from a live `dev.audit.unreachable_code` run:

| Finding class | Count |
| --- | --- |
| Unreachable modules | 27 |
| Module-exec-only modules | 15 |
| Type-only modules | 1 |
| Unused symbols, `exact` confidence | 602 |
| Unused symbols, `name-match` | 215 |
| Unused symbols, `name-match-data` | 591 |
| Orphaned test modules | 21 |
| Shipped modules reachable at runtime | 2039 of 2089 |

## The gate gap this closes

`dev.quality.unreachable_module_ratchet` exits 0 against this tree. It adjudicates
modules only, defers the `cadrumo.entrypoints.tui` prefix and its exclusive-supplier
closure, and carries fourteen `allowed` entries. Unused symbols and orphaned test modules
are ungated entirely. A green ratchet is therefore not evidence of a zero backlog, and
1408 symbol findings currently sit outside every gate.

## Where the backlog concentrates

Unreachable modules by area: `entrypoints/tui` 26, `application/operator_surface` 3,
`adapters/outbound` 2, `adapters/persistence` 2, `application/modelo` 2,
`application/wizard` 2, and single modules in `domain/fincas`, `core`, and
`domain/calculations`.

`exact`-confidence symbols by area: `domain/calculations` 106, `entrypoints/cli` 77,
`application/modelo` 60, `adapters/persistence` 46, `entrypoints/tui` 22,
`application/user_profile` 21, `application/filing` 20.

Outside-use labels on the module findings are the sharpest signal available: 27 modules
are reached only by tests, 11 by `dev` and tests, 2 by `dev` alone, and 3 by nothing at
all. The first two classes are the large ones and they are not the same problem as the
third.

## Semantic uniqueness technique

Reachability says a thing is not reached. It cannot say whether the behaviour is
duplicated elsewhere, already superseded, or genuinely missing a caller — and those need
different remedies. Semantic search answers that question where a name-based search
cannot, because the live equivalent rarely shares the dead one's identifiers.

Module level: query the behaviour plus its domain nouns, restricted to production, and
read whether a live module already does the job.

```
uvx vaultspec-rag search "<behaviour> <domain nouns> only:prod" --type code
```

Class level: query the type's responsibility rather than its name, then confirm the
candidate's exact symbols with grep. A finding whose responsibility is already discharged
by a reachable class is a supersession, not an orphan.

Decision grounding: `--type vault --doc-type adr` recovers whether the capability was
deliberately staged ahead of a dependency. A module built to be wired later is not dead
code, and deleting it discards a decision.

A worked result: probing the `operator_surface` cluster returned `crud_registry.py`,
whose own docstring states it is the source of truth "consumed by cross-cutting
conformance tests" and names the consuming harness. It is test support shipped inside the
wheel, which is a relocation, not a deletion.

## Resolution taxonomy

Every finding resolves into exactly one of these, and the class determines the remedy:

- **Test support shipped in the wheel.** Reached only by tests, and its purpose is to
  serve them. Move it under `src/cadrumo/tests/`, which the wheel excludes.
- **Harness code.** Reached only by `dev`. Move it beside the `dev/` consumer that drives
  it.
- **Superseded capability.** A reachable module already discharges the responsibility.
  Delete it with its tests; semantic search is what establishes this, not the name.
- **Deliberately staged capability.** Built ahead of a dependency that has not landed, and
  an accepted decision records why. Classify `[[intentional]]` with that rationale, never
  delete.
- **Orphaned capability.** Nothing reaches it and no decision explains it. Delete it with
  its tests.
- **Capability that should be live.** A product command needs it and the wiring is
  missing. Wire it, and the missing wiring is itself the defect.
- **Deferred by ownership.** Inside a frozen prefix owned by another in-flight campaign.
  Out of scope until that campaign lands.

## Constraints carried from the duplication campaign

The ratchet's `allowed` list is shrink-only and adding a line to it is how the boundary
erodes. Findings resolve through relocation, deletion, wiring, or an `[[intentional]]`
classification with a stated rationale — never a threshold, exclusion, baseline, skip, or
allowlist widening. Missing, unsupported, deferred, and proven-absent stay distinct
states.

Deleting or relocating shipped capability changes the product surface, so each class needs
its owner's decision recorded before execution, not after.
