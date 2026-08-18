---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:2a5be9d7a859d717802433b9eae5cc0d7ab2c9d2302002fef7774fef851917b7'
step_id: 'S183'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S183 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Have Terra XHigh bring the whole-tree type gate green at rest so it can function as the tripwire it already has the capability to be, since it resolves every import across the source tree with unresolved imports configured as hard errors and reaches both type-checking-guarded edges and production modules no test imports, which makes it the one mechanism that can see a deletion landing without its consumer sweep, and a gate standing red at rest is indistinguishable from an absent one because no reader can tell a new break from the standing noise and ## Scope

- `src/cadrumo/ and pyproject.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Terra XHigh bring the whole-tree type gate green at rest so it can function as the tripwire it already has the capability to be, since it resolves every import across the source tree with unresolved imports configured as hard errors and reaches both type-checking-guarded edges and production modules no test imports, which makes it the one mechanism that can see a deletion landing without its consumer sweep, and a gate standing red at rest is indistinguishable from an absent one because no reader can tell a new break from the standing noise

## Scope

- `src/cadrumo/ and pyproject.toml`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

The campaign's own share of the whole-tree type gate is fixed (commit `bd64e92ab6`-adjacent type commit): the user-profile facade's 248 lazy exports are now statically visible through a TYPE_CHECKING import block (self-aliased re-exports per module), which cleared the facade's 18 reportUnsupportedDunderAll/Unknown diagnostics AND the 22 evidence/filing member-access unknowns that flowed from consumers importing lazy names; the capsule-archive JSON payload is narrowed to `dict[str, object]` after the isinstance guard (6 diagnostics). Gate totals moved 1171 → 1123.

## Notes

The gate cannot go green at rest while the concurrent registry campaign's half-landed refactor stands: 636 pyrefly + 24 basedpyright diagnostics in `application/calculations/_row_set_assembly.py` (the uncommitted Gasto193 work), ~100 more across the registry domain and its tests, plus pre-existing harness/test debt. The residual is routed to the owning campaigns with the baseline enumerated (`types_full.log` retained); this row closes with our share delivered and the tripwire-once-green dependency recorded — same blocked-externally class as S195.
