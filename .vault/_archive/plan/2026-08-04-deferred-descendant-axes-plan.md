---
tags:
  - '#plan'
  - '#deferred-descendant-axes'
date: '2026-08-04'
modified: '2026-08-04'
body_hash: 'sha256:d751bc5f70bf6a554973afb45c1855447d199af23c8c5e222d321e8f2625980a'
tier: L2
related:
  - '[[2026-08-04-minimo-descendientes-eligibility-deferred-descendant-axes-adr]]'
  - '[[2026-08-04-minimo-descendientes-eligibility-audit]]'
  - '[[2026-05-27-descendant-profile-axis-adr]]'
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
     Replace deferred-descendant-axes with a kebab-case feature tag, e.g. #foo-bar.
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

# `deferred-descendant-axes` plan

<!-- One-line headline summary plan. -->

## Description

Executes the deferred-descendant-axes ADR, whose amendment corrected all four of its
own original decisions and refuted one outright. The ADR carries the parent campaign's
feature tag with a topic infix; the plan verb has no topic flag, so this document takes
its own feature tag and names the ADR in `related:` instead. A reader looking for the
governing decision should follow that link rather than the tag.

The four conditions the ADR addresses look like four items and are one. Each was blocked
by the same absence: a descendant model carrying less distinction than the law it serves.
LIRPF draws the descendant line twice and the two lines do not coincide. Art. 58.1
assimilates persons linked by tutela and acogimiento, so they take the tranche amounts.
Art. 58.2 grants the under-three increase, independently of the child's age, only for
adopcion and acogimiento tanto preadoptivo como permanente. The gap between those two
sentences is a real household, the temporal acogimiento carer, who is assimilated for
the tranches and excluded from the increase.

Phase P01 lands the two precondition axes and is complete. Phase P02 carries what they
unblock: one condition now expressible, and two blocked on groundings named in the
Parallelization section below.

Every condition here errs toward under-claiming today, which harms the taxpayer rather
than the revenue. That is what made them deferrable at all and is not a reason to leave
them untracked.

## Steps

### Phase `P01` - the descendant axes, landed

Delivers the two precondition axes the ADR decided, so the conditions below become expressible. The relacion axis distinguishes the Art. 58.1 assimilated set from the narrower Art. 58.2 entitling set, and the two named entry-event dates replace the single adoption-named field that could express neither the acogimiento anchor nor the cap-not-restart window.

- [ ] `P01.S01` - Add the DescendantRelacion closed set, the two named entry-event dates replacing adoption_date, and their flag, wizard and locale entry surface; `src/cadrumo/core/_descendant_relacion.py`.
- [ ] `P01.S02` - Scope the Art. 58.2 missing-anchor advisory to descendants that actually carry a tranche; `src/cadrumo/domain/contribuyente/family.py`.

### Phase `P02` - the conditions the axes unblock

Carries the remaining ADR decisions. One is now expressible and open, two are blocked on groundings that are named here rather than left as a deprioritisation, so a later reader sees a blocker and knows what would clear it.

- [ ] `P02.S03` - Give the Art. 81.1 maternidad adoption clause its own date-scoped three-year window, separate from the Art. 58.2 period-scoped one; `src/cadrumo/domain/contribuyente/family.py`.
- [ ] `P02.S04` - Model month-level guarderia spend as an optional sparse per-month map alongside the annual figure, refusing both at once for one child; `src/cadrumo/domain/contribuyente/family.py`.
- [ ] `P02.S05` - Assimilate an economically dependent descendant where the filer declares no anualidades at all, sweeping the existing incompatibility injector in the same change; `src/cadrumo/application/modelo/_profile_binding.py`.

## Parallelization

`P01.S01` had to be one Step and one commit rather than three. Retiring `adoption_date`
is a field removal, and the standing relocation discipline requires the canonical-site
change, every consumer, every fixture and every test to share one index and one commit,
so splitting the axis from its entry surface would have left the tree uncollectable in
between. `P01.S02` followed as a separate commit because it corrects a defect found by
self-review after the first landed, not because the two are independent.

`P02.S03` is open and unblocked. Both entry-event dates now exist, so the Art. 81.1
adoption clause can be given the date-scoped window it actually carries rather than
borrowing the Art. 58.2 period-scoped one. The two windows genuinely diverge, and one
predicate serving both would silently apply one statute's window to the other's
deduction.

`P02.S04` is BLOCKED and must not be started. The Art. 81.2 increase extends into the
period the child turns three for spend incurred after the birthday and up to the month
before the second cycle of infant education may begin. That upper bound is a
per-comunidad regional determination rather than a fixed month, grounded on 2026-08-04,
so the engine cannot hard-code one. Until the regional table exists, any persisted
pre-split shape would bake an unverified answer into stored data. The blocker is the
table, not the modelling.

`P02.S05` is BLOCKED and must not be started. It is REOPENED from retired: the ADR
retired the dependencia assimilation on the reasoning that the statutory carve-out for
judicial anualidades removes the one common household shape and no reachable case could
be constructed, and both halves were refuted against the live authority. The carve-out
turns on anualidades actually being PAID, not on the regime being available, and the
authority states the supposedly unconstructible case as entitled in terms. The blocker
is per-child attribution of anualidades. The staged boundary the ADR names is to
assimilate only where the filer declares none at all, which errs toward under-grant with
a visible advisory. Whoever takes it must sweep the existing incompatibility injector in
the same change, because landing one half of an incompatibility pair is this campaign's
most frequently repeated defect.

## Verification

`P01.S01` is verified: the closed set carries all five members with the entitling subset
declared once and derived everywhere, `adoption_date` survives only in docstrings
explaining the re-anchoring, and the cap is measured rather than asserted, with a child
fostered in 2019 and adopted in 2022 granted three periods and nothing after. The
persisted-shape change carries a save-load-strict-equality roundtrip over one record per
relacion with every defaultable field set to a non-default value, plus an anti-tautology
proof that deleting the stored token changes the reloaded record and changes it toward
under-grant rather than toward entitlement. Coverage is structural rather than numeric,
so nothing re-derives a registry formula against itself; the monetary side stays grounded
against the bundled worked example, whose child is adopted and which therefore evidences
the adopcion route only.

Three mutations were run against `P01.S01` and each must turn the suite red: removing the
relacion check from the entry-date resolver, making the coherence validator a no-op, and
switching the window anchor from the earliest entitling event to the latest. The first
mutation initially left every test green, because the coherence validator makes that
check unreachable through the model, so a second-layer test constructing the forbidden
record directly was added. Any later change to these guards should re-run that probe
rather than reason about coverage.

`P01.S02` is verified by a case table asserting the missing-anchor report stays silent
wherever nothing is lost: a descendant already under three, one the statute excludes from
the limb, one not cohabiting, and one over 25 with no discapacidad.

`P02.S03` is complete when the Art. 81.1 window is date-scoped and a test shows it
diverging from the Art. 58.2 period-scoped window for the same child.

`P02.S04` and `P02.S05` are complete only when their named blockers are cleared first.
Neither may be closed by narrowing its scope to the unblocked part; the ADR records both
at full scope deliberately, and a campaign that narrows its own completion criterion
reads as rigour while leaving the gap open.

Standing for every Step: ruff, the project type gate, and a clean tree-wide collection,
with a code review before the Step is closed.
