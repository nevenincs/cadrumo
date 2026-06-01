---
tags:
  - '#plan'
  - '#verification-fixture-roles'
date: '2026-06-01'
tier: L2
related:
  - '[[2026-06-01-verification-fixture-roles-adr]]'
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
     Replace verification-fixture-roles with a kebab-case feature tag, e.g. #foo-bar.
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

# `verification-fixture-roles` `role-aware verification fixtures` plan

### Phase `P01` - sidecar provenance schema and stamp

Add explicit provenance (real_corpus|synthetic_generated) and role (parser_anchor|formula_verification) to the fixture sidecar, stamped automatically by the synthetic generator and the real sanitiser manifest writer.


<!-- One-line headline summary plan. -->

- [ ] `P01.S01` - Stamp provenance=synthetic_generated and role=formula_verification into the synthetic fixture sidecar writer _write_sidecar; `src/aeat/tests/fixtures/justificantes/_generate.py`.
- [ ] `P01.S02` - Stamp provenance=real_corpus and role=parser_anchor in the real sanitiser manifest writer so sanitised real specimens self-declare their provenance; `src/aeat/adapters/inbound/sanitizer/_records.py`.

### Phase `P02` - backfill committed sidecars

Backfill provenance/role into every committed fixture sidecar: real_corpus/parser_anchor for the real specimens (M100, M111, M190, M390/2021), synthetic_generated/formula_verification for the rest.

- [ ] `P02.S06` - Backfill provenance/role into every committed fixture sidecar under the justificantes tree: real_corpus/parser_anchor for the real specimens (M100, M111, M190, M390/2021), synthetic_generated/formula_verification for the rest; regenerate synthetic sidecars via the generator and hand-stamp the real ones; `src/aeat/tests/fixtures/justificantes`.

### Phase `P03` - gate rewrite

Make the verification-source gate per-fixture: read each sidecar's declared provenance and cross-check it against the physical /Producer evidence; delete the _REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS allowlist.

- [ ] `P03.S03` - Rewrite the verification-source gate to read each fixture's sidecar provenance and assert it agrees with the physical /Producer (synthetic must carry the signature, real must not); `delete _REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS; `src/aeat/domain/calculations/registry/test_verification_source_fixture_metadata.py`.

### Phase `P04` - verify and codify

Prove the M390 mixed pool passes allowlist-free with both the verification-source gate and the corpus-roundtrip test green, then promote the fixture-provenance-declared-in-sidecar rule.

- [ ] `P04.S04` - Run the gate battery green allowlist-free: verification-source gate + corpus-sidecar roundtrip; `confirm the M390 mixed pool (real 2021 + synthetic 2022/2023) passes both; `src/aeat/domain/calculations/registry/test_verification_source_fixture_metadata.py`.
- [ ] `P04.S05` - Codify the fixture-provenance-declared-in-sidecar rule via vaultspec-core spec rules add (provenance declared in sidecar; `gates read sidecar + cross-check physical evidence; no hardcoded per-fixture exception allowlists); `.vaultspec/rules/rules/project/fixture-provenance-declared-in-sidecar.md`.

## Description

<!-- Briefly describe the proposed work. Reference `{adr}`s,
`{research}`, `{reference}`. Supporting documentation must be read prior to
writing the plan document. -->

Implements the accepted ADR's Option A: fixtures declare their provenance
(`real_corpus` | `synthetic_generated`) and role (`parser_anchor` |
`formula_verification`) in their `.json` sidecar, so the verification-source
honesty gate becomes per-fixture and the `W06.P16.S37` allowlist
`_REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS` is deleted. The synthetic generator and
the real sanitiser each stamp the sidecar at write time; committed sidecars are
backfilled once; the gate reads each sidecar's declared provenance and
cross-checks it against the physical `/Producer` evidence (defence in depth). The
corpus-roundtrip test continues to consume the real M390 2021 anchor unchanged.
The parallel `_PERIOD_EQUALS_EJERCICIO` list is a documented out-of-scope
follow-up (it encodes layout, not provenance).

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

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelised when they share no hard
interdependency. -->

P01.S01 and P01.S02 are independent (synthetic generator vs real sanitiser) and
parallelisable. P02 (backfill) depends on P01 (the stamp fields must exist), and
P03 (gate rewrite) depends on P02 (sidecars must carry provenance before the gate
reads them). P04 verification gates the whole chain; P04.S05 (codify) runs only
after P04.S04 is green.

## Verification

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in every Wave is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter. -->

Success criteria, each a verifiable check:

- `test_verification_source_fixture_metadata` passes with
  `_REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS` deleted (grep confirms the symbol is
  gone).
- The M390 mixed pool (real `2021-0A` + synthetic `2022-0A`/`2023-0A`) passes the
  verification-source gate via sidecar-declared provenance.
- `test_corpus_sidecar_roundtrip` stays green (the real 2021 anchor is unchanged).
- A deliberately mis-stamped sidecar (claim `synthetic_generated` on the real
  2021 PDF) reds the gate via the `/Producer` cross-check — proving the honesty
  property survives.
- Every committed fixture sidecar carries a `provenance` field; the synthetic
  generator and real sanitiser stamp it automatically (re-running the generator
  is a no-op diff for unchanged fixtures).
- The `fixture-provenance-declared-in-sidecar` rule is registered (P04.S05).
