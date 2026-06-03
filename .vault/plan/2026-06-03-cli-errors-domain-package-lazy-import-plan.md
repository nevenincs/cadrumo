---
tags:
  - '#plan'
  - '#cli-errors-domain-package-lazy-import'
date: '2026-06-03'
tier: L2
related:
  - '[[2026-06-03-cli-errors-domain-package-lazy-import-adr]]'
  - '[[2026-06-03-cli-errors-domain-package-lazy-import-research]]'
  - '[[2026-06-03-user-profile-lazy-import-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace cli-errors-domain-package-lazy-import with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'. The related field
     carries the AUTHORISING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add frontmatter fields
     outside the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorising documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `cli-errors-domain-package-lazy-import` `Lazy domain-package boundary execution` plan

### Phase `P01` - make the domain-package boundary lazy

Convert aeat.domain.user_profile/__init__.py to dispatch UserProfilePortableExport through PEP 562 __getattr__ and land the producer-side probe.


<!-- One-line headline summary plan. -->

- [ ] `P01.S01` - convert to dispatch UserProfilePortableExport via module-level __getattr__ (PEP 562); `src/aeat/domain/user_profile/__init__.py`.
- [ ] `P01.S02` - add producer-side regression probe asserting fresh-interpreter import places zero registry modules; `src/aeat/domain/user_profile/test_lazy_boundary.py`.

### Phase `P02` - verify the CLI gate is green end-to-end

Run the CLI lazy-command-tree gate plus the producer probes to confirm 6/6 green and the application-package boundary is preserved.

- [ ] `P02.S03` - run pytest test_lazy_command_tree and confirm 6/6 green; `src/aeat/entrypoints/cli/test_lazy_command_tree.py`.
- [ ] `P02.S04` - re-run application-side probe to confirm parent boundary preserved; `src/aeat/application/user_profile/test_lazy_boundary.py`.
- [ ] `P02.S05` - re-run cli suite and confirm no new reds beyond pre-existing baseline; `src/aeat/entrypoints/cli`.

## Description

Successor execution to the application-package boundary fix that landed under the parent ADR. The parent ADR's accepted scope made `aeat.application.user_profile` lazy-by-default via PEP 562 dispatch and the producer probe at `src/aeat/application/user_profile/test_lazy_boundary.py` confirms that contract. The CLI-side gate at `src/aeat/entrypoints/cli/test_lazy_command_tree.py` remains red for all five state-free-surface tests because the leak vector is one layer deeper than the parent ADR's scope: the eager re-export of `UserProfilePortableExport` from `aeat.domain.user_profile/__init__.py` (which transitively pulls `aeat.domain.modelos._calculation_revision`, which imports the registry at module scope).

The successor ADR adopts Pattern (a) / (E) - lazy domain-package boundary via PEP 562. The fix mirrors the parent ADR's mechanism one layer down the import graph: dispatch `UserProfilePortableExport` through a module-level `__getattr__` while keeping every lightweight re-export (errors, values, schema, loader, registry-contract) eager. No consumer code changes; the public surface is unchanged. The producer-side regression probe lands in the same atomic commit.

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorising documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

Phase `P01` and Phase `P02` are sequential: `P02` runs the gate that confirms `P01` met its contract. Within `P01`, `S01` and `S02` are designed to land atomically in one commit (the source change and the producer-side probe share a single explicit-path commit per the relocation-atomicity clause), so they are not run as independent units. Within `P02`, `S03`, `S04`, and `S05` are independent test invocations that may run in parallel; verification is complete only when all three are green.

## Verification

The plan is complete when every Step closes against a verifiable gate:

- All six tests in `src/aeat/entrypoints/cli/test_lazy_command_tree.py` are green (the five originally-red state-free-surface tests plus `test_dispatching_a_subcommand_loads_its_module` which must remain green).
- The producer-side probe at `src/aeat/domain/user_profile/test_lazy_boundary.py` passes: a fresh-interpreter `import aeat.domain.user_profile` places zero `aeat.domain.calculations.registry*` modules in `sys.modules`.
- The producer-side probe at `src/aeat/application/user_profile/test_lazy_boundary.py` continues to pass: the parent campaign's application-package boundary is preserved.
- The CLI suite under `src/aeat/entrypoints/cli/` shows no new reds beyond the pre-existing baseline at the start of this campaign.
- The relocation lands as one atomic explicit-path commit per the `aeat-architecture-boundaries` symbol-relocation atomicity clause.

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in every Wave is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter. -->
