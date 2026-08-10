---
tags:
  - '#plan'
  - '#legal-corpus-vintage'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:caca938f4933562fa34dec4daab237fe463fa9bdd9a1de5cba8e4fe179799647'
tier: L2
related:
  - "[[2026-08-10-legal-corpus-vintage-adr]]"
  - "[[2026-08-10-legal-corpus-vintage-reference]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace legal-corpus-vintage with a kebab-case feature tag, e.g. #foo-bar.
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

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - The related: field carries the AUTHORIZING documents (ADR, research,
       reference, prior plan) for every Step in this plan. Steps inherit this
       chain; per-row reference footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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

# `legal-corpus-vintage` plan

<!-- One-line headline summary plan. -->

## Description

<!-- Briefly describe the proposed work. Reference `{adr}`s,
`{research}`, `{reference}`. Supporting documentation must be read prior to
writing the plan document. A plan may execute one ADR or a cluster; when
several feed it, state here which Wave or Phase each ADR governs. -->

## Steps

### Phase `P01` - The negative clause

Give the gate a way to say a clause must be ABSENT, and make the failure message distinguish the two opposite defects.

- [ ] `P01.S01` - Add an optional forbidden-text clause to the legal-catalogue entry schema alongside required_text, evaluated at registry build. The failure message names WHICH clause fired, because a missing required phrase and a present forbidden phrase diagnose opposite defects and one message conflates them; `src/cadrumo/_data/registry/aeat/legal/, src/cadrumo/domain/calculations/registry/`.
- [ ] `P01.S02` - Prove the new clause bites and prove it does not over-reach in the same row. The refusal must fire on a document containing a forbidden phrase, and the CONTROL that decides closure is that every one of the 606 existing entries still loads unchanged, with the deliberately vintaged excerpts named explicitly because they legitimately contain text current law does not. Do not close on the refusal firing; `src/cadrumo/domain/calculations/registry/tests/`.

### Phase `P02` - Author the clauses that are already evidenced

Only two entries have a hand-checked divergence behind them. Author those and stop, rather than sweeping.

- [ ] `P02.S03` - Author the forbidden-text clause for ley-35-2006 art-81 in the same change as the corpus_ref repoint the sibling audit prepared, naming the repealed cotizaciones ceiling as text the cited document must not contain. This is the operator-stamped entry, so the authoring is prepared and the stamp is not an agent act; `src/cadrumo/_data/registry/aeat/legal/irpf.toml`.
- [ ] `P02.S04` - Author the forbidden-text clause for ley-37-1992 art-122 and art-124, naming the superseded regimen simplificado eligibility wording. Note before starting that one of art-122's two existing required_text phrases exists ONLY in the superseded formulation, so that phrase is itself part of the defect and removing it is part of the fix rather than collateral; `src/cadrumo/_data/registry/aeat/legal/`.

### Phase `P03` - Reach the unmeasured population

157 excerpt-backed entries have no offline oracle. This phase is mechanical acquisition, not adjudication.

- [ ] `P03.S05` - Acquire the redaction history for the 157 excerpt-backed entries that have no bundled consolidated counterpart, through dev/corpus/fetch_boe_normative.py and never by hand. Three traps are already measured and must be carried: act.php lists versions NEWEST first while the open-data article endpoint concatenates them OLDEST first, so a take-the-last rule is right for one and bundles repealed law for the other; a fresh BOE payload is CRLF while .gitattributes declares eol=lf, so the extracted sidecar records a sha that no checkout reproduces unless the source is normalised to LF BEFORE extracting; and legal text must never pass through a shell. Read every written file back before trusting it; `src/cadrumo/_data/corpus/normatives/html/`.
- [ ] `P03.S06` - Re-run the clause-level divergence measurement over the newly reachable entries and report the split, without proposing a remedy. The disconfirming observation: if the newly measured population's catch rate differs materially from the 3-of-72 already measured, the 104 comparable entries were not representative and the ADR's premise needs re-examining rather than extending; `src/cadrumo/_data/registry/aeat/legal/`.
- [ ] `P03.S07` - Check one of the nine ley-37-1992 art-163 entries BY HAND rather than by count, comparing the excerpt against the consolidated article the way art-122 was checked. They report 100 per cent clause absence and 100 per cent excerpt-only phrases, which is as consistent with an anchor-mapping mismatch on Roman-ordinal article names as with wholesale supersession. If it is a mismatch, the other eight are too and the finding dissolves. If it is real it is the OSS and IOSS special regimes; `src/cadrumo/_data/corpus/normatives/html/`.


## Parallelization

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelized when they share no hard
interdependency. -->

## Verification

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in the plan is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the authorizing
documents linked in the `related:` frontmatter. -->
