---
tags:
  - '#plan'
  - '#censo-g313-launcher-fix'
date: '2026-07-10'
modified: '2026-07-10'
tier: L2
related:
  - '[[2026-07-10-censo-g313-launcher-fix-adr]]'
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
     Replace censo-g313-launcher-fix with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
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
     in plan body. Authorizing documents go in the plan's `related:`
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
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `censo-g313-launcher-fix` plan

### Phase `P01` - capture the authenticated censal page

Produce the ground-truth artefact every later step depends on: the authenticated MdcAcceso and es13 Mis Datos Censales HTML, identity redacted.


<!-- One-line headline summary plan. -->

- [ ] `P01.S01` - Capture the authenticated MdcAcceso and es13 Mis Datos Censales HTML/trace with identity redacted, and record whether the MdcAcceso to es13 transition is a passive redirect or an active dispatch; `src/aeat/adapters/outbound/aeat/sede/tests/`.

### Phase `P02` - fix the driver and parser grounding

Make the driver wait for the es13 censal content before capture, and re-ground labels/constants only where the capture proves drift.

- [ ] `P02.S02` - Wait for the es13 censal content marker (fallback networkidle) bounded by the selector-probe timeout before capturing the G313 HTML, preserving the fail-closed landing-URL read guard; `src/aeat/adapters/outbound/aeat/sede/_censo_live.py`.
- [ ] `P02.S03` - Follow the Acceso dispatch explicitly only if the capture proves an active access control rather than a passive redirect; `src/aeat/adapters/outbound/aeat/sede/_censo_live.py`.
- [ ] `P02.S04` - Re-ground the G313 parser field labels against the captured es13 page only where they have drifted; `src/aeat/adapters/outbound/aeat/sede/_censo.py`.
- [ ] `P02.S05` - Update the launcher path or censal markers only if the capture requires it; `src/aeat/core/external_constants.toml`.

### Phase `P03` - verify

Prove the fix with a recorded-navigation regression and one operator-run live pull returning a populated CensoFactSet.

- [ ] `P03.S06` - Add a recorded-navigation regression through the browser_session_factory seam proving the MdcAcceso to es13 wait then a populated CensoFactSet, plus the empty-access-page refusal; `src/aeat/adapters/outbound/aeat/sede/tests/test_censo.py`.
- [ ] `P03.S07` - Run one operator-mediated live config profile censo pull and record a populated CensoFactSet or the exact residual blocker; `.vault/exec/2026-07-10-censo-g313-launcher-fix`.

## Description

Fix the outbound G313 (Mis Datos Censales) driver premature-capture defect
grounded in the research and decided in the ADR: the driver captures HTML on the
AEAT Acceso launcher before the authenticated es13 censal SPA loads, so the
parser sees no censal fields and the caller refuses with an empty
`CensoFactSet`. The fix keeps the published Acceso entry point and waits for the
es13 content before capture. The work is capture-first because the exact wait
target, the transition shape, and any parser-label drift can only be confirmed
against a real authenticated page, which only the operator can produce.

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
     Wave depends on it, and which authorizing documents back it.

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

The phases are hard-sequenced: P01 (capture) gates all of P02, because the wait
target, transition shape, and parser labels are decided by the captured page.
Within P02, S02 is the core change; S03/S04/S05 are conditional and executed
only if the capture proves an active dispatch, label drift, or a constant
change. P03.S06 (regression) follows the P02 code changes; P03.S07 (operator
live pull) is the final gate and is operator-scheduled.

## Verification

- A captured authenticated es13 Mis Datos Censales page exists (identity
  redacted) and its transition shape and field labels are recorded.
- The recorded-navigation regression proves the driver waits past the Acceso
  page to the es13 content and yields a populated `CensoFactSet`, and still
  refuses on a genuine empty/access-gate landing.
- Focused lint/tests on the touched sede driver, parser, and constants pass.
- One operator-mediated live `config profile censo pull` returns a populated
  `CensoFactSet`; recorded as the closing exec record. An unresolved live
  blocker keeps `P03.S07` open per the external-blocker discipline.
