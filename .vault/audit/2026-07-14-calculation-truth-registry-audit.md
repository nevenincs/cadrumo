---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-07-14'
modified: '2026-07-14'
related:
  - "[[2026-07-12-calculation-truth-registry-plan]]"
  - "[[2026-07-12-calculation-truth-registry-reference]]"
  - "[[2026-05-03-calculation-truth-registry-rebuild-plan]]"
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace calculation-truth-registry with a kebab-case feature tag, e.g. #foo-bar.
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

# `calculation-truth-registry` audit: `Modelo-wave family disposition ledger`

## Scope

Continuation of the reopened `P01.S01`/`P01.S02` classification work after the
2026-07-14 review rejected the prior lexical-only 58/647 partition
(`2026-07-12-calculation-truth-registry-classification-review-audit`, finding
`row-level-closure-invalid`). This pass classifies the bounded Modelo-Wave
family of the legacy 705-row plan (`Wave 0` through `Wave 27`, source lines
315-2604, 306 unchecked rows) using real technical verification — registry
directory presence, legacy-package existence, and cross-reference against the
concurrently running `calculation-export-import-adjudication` plan — instead
of a regex over checklist prose. `Tasks` (2605-3135, 35 rows), `Teardown
Replacement Contract` (3136-5064, 359 rows), and the `VAT Centralization
Roll-Out Ledger` (5123-5301, 5 rows) are explicitly **out of scope** for this
pass; see Recommendations. No production code, tests, registry data, or legacy
checkbox changed.

## Findings

### legacy-package-confirmed-deleted | info | `src/aeat` no longer exists; the entire rebuild lived under `src/cadrumo`

`ls src/aeat` returns "no such file or directory". Every legacy Wave and
Teardown-section row that names a `src/aeat/...` path as the authority to
remove is checking a path that has already been physically deleted at the
package-tree level. This confirms the coarse teardown claim but does not, by
itself, prove that a specific named anti-pattern (a filing builder that
constructs drafts without a validated snapshot, a CLI command exposing a
hydrate/generation flow) is absent from the `src/cadrumo` equivalent — that
requires per-claim verification, which is the `Teardown Replacement Contract`
family scoped out below.

### registry-modelo-presence-confirmed | info | all 26 non-retired legacy-wave modelos have live registry directories; Modelo 037 is the sole registry-absent wave

`ls src/cadrumo/_data/registry/aeat/modelos/` lists 71 modelo directories,
covering every Wave-1-through-27 modelo except `037`. Modelo 037 is a
non-registry retired identifier per `cadrumo.core.NON_REGISTRY_MODELOS`
(`modelo-identifiers-use-core-enum` rule; enforced by
`test_modelo.py`'s registry-parity carve-out). Wave 20's 18 unchecked rows
("Modelo 037 audit", "legal basis", "casilla schema", "formulas", "export
linkage", "teardown", "quality gate", "completion gate", etc.) are therefore
**superseded**: the accepted retirement decision displaces the legacy plan's
assumption that Modelo 037 needs its own full registry build. This matches
`P02.S04`/`P03.S16` of the concurrently running
`calculation-export-import-adjudication` plan, which independently reached the
same retirement disposition for Modelo 037's outbound/inbound surfaces.

### family-classification-rule | info | four real (non-lexical) dispositions cover the 306-row Modelo-Wave family

Reading every Wave section in full (Wave 1 Modelo 130 and Wave 5 Modelo 131
read completely; all others read via the unchecked-row grep plus registry
directory checks) shows the same repeating structural template per modelo, so
one rule set — not a single regex — classifies every row in this family:

1. **Blocked-external.** A row whose action is capturing, sanitizing, or
   retrying a live/authenticated/read-only AEAT filed artefact (e.g. "Modelo
   131 live sanitized fixture", "Modelo 202 live/filed-data tests", "Modelo 200
   live cross-reference guard" rows that stay open "until a real read-only
   AEAT artefact exists"). This is grounded, not lexical: `aeat-safety-legal-gates`
   forbids fabricating filed evidence and `local-filed-observations-are-non-official-evidence`
   forbids treating a local/synthetic substitute as official. The app cannot
   close these rows by writing code; they wait on real authenticated capture.
   Applies to every Wave's "live \* discovery/fixture/tests" rows.
2. **Superseded (greenfield N/A).** A row whose own inline text already states
   the modelo was greenfield with no legacy authority to remove — Modelo 347
   (`- [ ] Modelo 347 teardown: N/A — Modelo 347 was greenfield...`), Modelo 232,
   Modelo 720, Modelo 840. These four modelos' "teardown" rows are self-evidently
   moot; only their sibling gate rows stay blocked-derivative (below) pending
   their own live-fixture rows.
3. **Blocked-derivative (gate rows).** Every "teardown" (non-greenfield),
   "quality gate", and "completion gate" row states its own closing condition
   as "no unchecked row remains" for that wave. These rows cannot be
   individually adjudicated ahead of their siblings; verifying them requires
   the same per-file, per-anti-pattern check as the `Teardown Replacement
   Contract` family (a Wave's "teardown" row is a compressed restatement of
   that section's entries for the same modelo). Scoped out to the
   recommended follow-up pass below, not silently marked delivered.
4. **Genuinely actionable.** A residual concrete coverage gap that is neither
   live-blocked nor a teardown/gate restatement. Verified directly against the
   registry TOML tree:
   - Modelo 131's 2024 revision directory
     (`src/cadrumo/_data/registry/aeat/modelos/131/revisions/2024/`) has no
     `parameters/` or `0003-modulos-engine.toml` formula/casilla file, while
     the 2025 and 2026 revisions do — confirming the legacy plan's "Modelo 131
     DPA 2024 schema" / activity-detail gap (source lines 858-866) is a real,
     still-open coverage gap, not a stale claim.
   - Modelo 184/308/309/322/353/360/369/840 export-layout and casilla-corpus
     gap rows (source lines 2463-2604) overlap the candidates the
     `calculation-export-import-adjudication` plan is actively adjudicating
     (`P02.S03`-`S15`, `P03.S16`-`S22`); this audit does not re-adjudicate
     them to avoid duplicate, possibly divergent dispositions. Their final
     disposition should be inherited from that plan's published audit
     (`P04.S24`) once it completes, rather than re-derived here.
   - Modelo 100's "hand-author `input_kind = "bound"`" outstanding sub-step
     (source line 2408) remains an open, Renta-specific coverage item requiring
     its own verification against the current Modelo 100 registry tree; not
     yet independently confirmed in this pass.

## Recommendations

- Do not close `P01.S01` or `P01.S02`. This pass adds real, evidence-backed
  dispositions for the 306-row Modelo-Wave family (Wave 0 through Wave 27) but
  does not cover the `Tasks` (35), `Teardown Replacement Contract` (359), or
  `VAT Centralization Roll-Out Ledger` (5) sections — 399 of 705 rows remain
  unclassified by any evidence-backed methodology.
- Open a second bounded adjudication plan, mirroring the shape of
  `2026-07-14-calculation-export-import-adjudication-plan`, scoped to the
  `Teardown Replacement Contract` family: one Step per named `src/aeat/...`
  path, each Step confirming whether the specific anti-pattern it names (raw
  casilla dicts bypassing snapshot validation, hardcoded export layouts,
  hydrate/generation CLI flows) is genuinely absent from the `src/cadrumo`
  equivalent, not merely that the old path is gone.
- Open a third bounded pass (or fold into the same plan) for the `Tasks`
  section's cross-cutting hygiene items (banned-vocabulary scans, migration
  guard removal, per-modelo XLS/XLSX workbook discovery) and the `VAT
  Centralization Roll-Out Ledger`'s 5 residual rows.
- Do not re-adjudicate the export-layout/extraction-profile candidates already
  owned by `2026-07-14-calculation-export-import-adjudication-plan`
  (`P02`/`P03`); inherit its published disposition once `P04.S24` lands.
- `P02.S03` of this plan (write the canonical registry implementation
  backlog) stays open. The only backlog item this pass can defensibly emit
  today is the confirmed Modelo 131 2024 DPA/activity-detail schema gap; a
  full backlog requires the two follow-up passes above to complete first.
